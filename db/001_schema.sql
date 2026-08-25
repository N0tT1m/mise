-- Mise :: schema
--
-- One database. Three extensions:
--   vector    semantic search + generation grounding
--   pg_trgm   fuzzy text matching
--   intarray  fast set operations on ingredient id arrays (the fridge match)
--
-- Governing rule: ingredient_lines.raw_text is immutable. The parser will be
-- wrong repeatedly; re-running it must always be possible, and it is only
-- possible while the original input still exists.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS intarray;

-- ---------------------------------------------------------------- vocabulary

CREATE TABLE units (
    id       int PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    name     text NOT NULL UNIQUE,
    kind     text NOT NULL CHECK (kind IN ('volume', 'mass', 'count')),
    to_base  numeric NOT NULL          -- volume -> ml, mass -> g, count -> 1
);

CREATE TABLE ingredients (
    id               int PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    canonical_name   text NOT NULL UNIQUE,   -- 'flour.all_purpose'
    display_name     text NOT NULL,          -- 'all-purpose flour'
    category         text,                   -- 'produce', 'dairy', 'dry_good'
    parent_id        int REFERENCES ingredients(id),
    is_staple        boolean NOT NULL DEFAULT false,
    density_g_per_ml numeric,
    grams_per_count  numeric,                -- 'one onion is ~150 g'
    line_count       int NOT NULL DEFAULT 0  -- commonness; drives match ranking
);

CREATE INDEX ingredients_parent_idx  ON ingredients (parent_id);
CREATE INDEX ingredients_display_trgm ON ingredients USING gin (display_name gin_trgm_ops);

CREATE TABLE ingredient_aliases (
    id            bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    ingredient_id int NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    alias         text NOT NULL UNIQUE,
    origin        text NOT NULL CHECK (origin IN ('llm', 'human', 'dataset'))
);

CREATE INDEX ingredient_aliases_ing_idx  ON ingredient_aliases (ingredient_id);
CREATE INDEX ingredient_aliases_trgm_idx ON ingredient_aliases USING gin (alias gin_trgm_ops);

CREATE TABLE substitutions (
    id            bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    ingredient_id int NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    substitute_id int NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    ratio         numeric NOT NULL DEFAULT 1,
    note          text,
    confidence    real NOT NULL,
    UNIQUE (ingredient_id, substitute_id),
    CHECK (ingredient_id <> substitute_id)
);

-- ------------------------------------------------------------------- recipes

CREATE TABLE recipes (
    id                      bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    source                  text NOT NULL,   -- 'dataset:indian' | 'crawl:x' | 'generated'
    source_ref              text,
    title                   text NOT NULL,
    description             text,
    servings                int,
    prep_minutes            int,
    cook_minutes            int,
    instructions            jsonb NOT NULL DEFAULT '[]'::jsonb,
    raw_payload             jsonb NOT NULL,  -- untouched original. never modified.
    all_ingredient_ids      int[] NOT NULL DEFAULT '{}',
    required_ingredient_ids int[] NOT NULL DEFAULT '{}',  -- staples/optional removed
    embedding               vector(384),
    parser_version          int NOT NULL DEFAULT 0,
    created_at              timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX recipes_required_idx ON recipes USING gin (required_ingredient_ids gin__int_ops);
CREATE INDEX recipes_all_idx      ON recipes USING gin (all_ingredient_ids gin__int_ops);
CREATE INDEX recipes_source_idx   ON recipes (source);
CREATE INDEX recipes_fts_idx      ON recipes
    USING gin (to_tsvector('english', title || ' ' || coalesce(description, '')));

-- Build once embeddings exist; HNSW on an empty table is wasted work.
-- CREATE INDEX recipes_embedding_idx ON recipes
--     USING hnsw (embedding vector_cosine_ops);

CREATE TABLE ingredient_lines (
    id             bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    recipe_id      bigint NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    position       int NOT NULL,
    raw_text       text NOT NULL,      -- IMMUTABLE. never overwrite.
    qty_min        numeric,
    qty_max        numeric,            -- '2-3 cloves'; null when unquantified
    unit_raw       text,
    unit_id        int REFERENCES units(id),
    name_raw       text,
    ingredient_id  int REFERENCES ingredients(id),  -- null until resolved
    prep_note      text,
    is_optional    boolean NOT NULL DEFAULT false,  -- 'to taste', 'for garnish'
    grams          numeric,
    confidence     real,
    parser_version int NOT NULL DEFAULT 0,
    UNIQUE (recipe_id, position)
);

CREATE INDEX ingredient_lines_ing_idx ON ingredient_lines (ingredient_id);
CREATE INDEX ingredient_lines_unresolved_idx
    ON ingredient_lines (confidence)
    WHERE ingredient_id IS NULL;

-- ---------------------------------------------------------------- user state

CREATE TABLE pantry_items (
    id            bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id       int NOT NULL DEFAULT 1,   -- unused today; free now, migration later
    ingredient_id int NOT NULL REFERENCES ingredients(id) ON DELETE CASCADE,
    qty           numeric,
    unit_id       int REFERENCES units(id),
    added_at      timestamptz NOT NULL DEFAULT now(),
    expires_at    timestamptz,
    UNIQUE (user_id, ingredient_id)
);

CREATE TABLE cook_log (
    id        bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    user_id   int NOT NULL DEFAULT 1,
    recipe_id bigint NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    cooked_at timestamptz NOT NULL DEFAULT now(),
    rating    int CHECK (rating BETWEEN 1 AND 5),
    notes     text
);

CREATE INDEX cook_log_recipe_idx ON cook_log (recipe_id);

-- ------------------------------------------------------- pipeline bookkeeping

CREATE TABLE review_queue (
    id           bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    kind         text NOT NULL CHECK (kind IN ('cluster', 'line', 'substitution')),
    payload      jsonb NOT NULL,
    impact_count int NOT NULL,       -- lines unblocked. always ORDER BY this DESC.
    status       text NOT NULL DEFAULT 'open'
                 CHECK (status IN ('open', 'accepted', 'corrected', 'rejected')),
    resolved_at  timestamptz
);

CREATE INDEX review_queue_open_idx
    ON review_queue (impact_count DESC)
    WHERE status = 'open';

CREATE TABLE generation_runs (
    id                   bigint PRIMARY KEY GENERATED ALWAYS AS IDENTITY,
    recipe_id            bigint NOT NULL REFERENCES recipes(id) ON DELETE CASCADE,
    model                text NOT NULL,
    prompt_version       text NOT NULL,
    grounding_recipe_ids int[] NOT NULL,
    constraints          jsonb NOT NULL,
    created_at           timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX generation_runs_recipe_idx ON generation_runs (recipe_id);
