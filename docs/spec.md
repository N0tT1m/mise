<!-- Exported from the Mise en Place spec artifact. This file is the
     canonical copy; the README links here. -->

Build Specification

# Mise en Place


A cooking platform that finds recipes, tells you what you can cook from what's in your fridge, and generates new ones — all from a single normalized ingredient graph.

**Scope**
Single user

**Runs**
Local first, Azure later

**Database**
PostgreSQL + pgvector

**Seed corpus**
20,366 recipes

**Status**
Ready to build

## 1. What it does


Three features. Everything in this document exists to serve them.

### Find a recipe


Search a private corpus of real recipes by name, ingredient, cuisine, or plain description — without the ad walls, the life stories, or the SEO padding. Results come from a database you own.

### Cook what you have


Tell the system what's in your kitchen. It answers two questions: *what can I make right now*, and *what am I one or two items away from*. The second is the more useful one — "you're two items from four dinners" is a decision you can act on; "you can't make this" is not.

### Generate something new


When nothing in the corpus fits your constraints — dietary restrictions, what's in the fridge, who's coming to dinner — generate a recipe instead, grounded in real ones so it doesn't invent impossible ratios.  The insight

These look like three subsystems. They are three queries against one shared asset. Section 2 is that asset, and it is the only part of this system nobody can hand you off the shelf.

## 2. The core idea: a canonical ingredient graph


Recipes on the internet describe ingredients in free text. The same thing appears a dozen ways:  Real lines from the seed corpus

```
"6 Karela (Bitter Gourd/ Pavakkai) - deseeded"
"3 tablespoon Gram flour (besan)"
"Salt - to taste"
"2 1/4 cups all-purpose flour"
"extra-virgin olive oil, for drizzling"
```


Quantities that aren't numbers. Ingredients with three names. Parenthetical translations. Preparation notes glued to the end. Non-breaking spaces in the middle.

**The ingredient graph turns each of those into a structured record pointing at a stable ID.** Once every recipe references canonical IDs instead of strings, all three features become straightforward database queries:

| Feature | Becomes |
| --- | --- |
| Find a recipe | Full-text and vector search, filtered by ingredient ID |
| Cook what you have | Set containment: is the recipe's required ID set inside your pantry's? |
| Generate something new | Retrieve real recipes by ID overlap, use them as grounding, generate |


Skip this layer and you will build three worse versions of it. That is not a hypothetical — it is what happened in every prior attempt, and section 9 documents the exact failures.

### What the graph contains
        ``    ````

| Element | Example | Why it's needed |
| --- | --- | --- |
| Canonical ingredient | flour.all_purpose | The stable identity everything else points at |
| Aliases | scallion = green onion = spring onion | One ingredient, many names, across cuisines |
| Hierarchy | flour.bread is a flour | A recipe wanting "flour" should match your bread flour |
| Staple flag | salt, water, black pepper | Assumed present. Without this, fridge-match is unusable |
| Substitutions | buttermilk ← milk + acid | Turns a miss into a near-miss you can actually cook |
| Unit conversion | 1 cup flour ≈ 120 g | Lets quantities be compared and scaled |


### How the vocabulary gets built


You do not write the ingredient list by hand, and you do not derive it by counting strings. You cluster it out of your own corpus with a language model, then review the clusters.

Here is why that specific approach, measured against the 20,366 recipes already on disk:

| Measurement | Count |
| --- | --- |
| Ingredient lines in the corpus | 228,067 |
| Distinct raw lines | 97,163 |
| Distinct ingredient names after crude extraction | 28,261 |


Reviewing 28,261 names is not a task a person completes. But the distribution is steep — the most common names cover most of the corpus:

| Review the top… | Covers |
| --- | --- |
| 500 names | 68.4% |
| 1,000 names | 76.0% |
| 2,000 names | 82.0% |
| 5,000 names | 88.1% |


And that curve *understates* the real coverage, because it counts strings rather than ingredients. Look at what sits at the top of it:  Top of the frequency distribution

```
salt            7,828      ← the same ingredient,
kosher salt     4,140         counted twice

garlic          2,329      ← and again
garlic cloves   2,255

extra           2,100      ← a parse failure: "extra-virgin olive oil"
                              truncated at the hyphen
```


Every one of those splits is a merge that clustering collapses, so the same 500 review decisions buy substantially more than 68%. That is the argument for a model doing the clustering rather than a frequency count doing it.

And `extra` at 2,100 occurrences is a parse bug produced by four lines of regex — which is the argument for the model doing the *extraction* too, not just the grouping. Ingredient parsing looks easy and is not.  Review in leverage order

Never present a flat list to review. Order the queue by how many ingredient lines each decision would resolve. An evening spent on the 500 highest-impact clusters is worth more than a week spent alphabetically.

## 3. Data model


PostgreSQL, one database, three extensions: `vector` for semantic search, `pg_trgm` for fuzzy text, `intarray` for fast set operations on ingredient IDs.

### The rule that governs everything
  Never destroy the raw string

Every ingredient line keeps its original text forever, alongside a parser version number. You will get parsing wrong repeatedly. Re-running the parser must always be possible, and it is only possible if the input still exists.

A prior version of this system parsed destructively at crawl time. `"2 cups flour"` became unit `cup` and ingredient `"s flour"`, and the original was gone. Every recipe it ingested was permanently corrupted.

### Tables
  Core recipe storage

```
recipes
  id                      bigserial primary key
  source                  text        -- 'dataset:indian' | 'crawl:site' | 'generated'
  source_ref              text null   -- URL or dataset row id
  title                   text not null
  description             text null
  servings                int null
  prep_minutes            int null
  cook_minutes            int null
  instructions            jsonb       -- ordered array of step strings
  raw_payload             jsonb       -- untouched original record. never modified.
  all_ingredient_ids      int[]       -- maintained; every resolved ingredient
  required_ingredient_ids int[]       -- staples and optionals removed. the match key.
  embedding               vector(384) null
  parser_version          int not null default 0
  created_at              timestamptz not null default now()

  indexes:
    gin (required_ingredient_ids)   -- gin__int_ops, for containment
    gin (all_ingredient_ids)
    gin (to_tsvector('english', title || ' ' || coalesce(description,'')))
    hnsw (embedding vector_cosine_ops)
```
   The parse layer — one row per line of a recipe

```
ingredient_lines
  id              bigserial primary key
  recipe_id       bigint not null references recipes(id) on delete cascade
  position        int not null        -- order within the recipe
  raw_text        text not null       -- IMMUTABLE. "3 tablespoon Gram flour (besan)"
  qty_min         numeric null        -- 3
  qty_max         numeric null        -- handles "2-3 cloves"; null when unquantified
  unit_raw        text null           -- "tablespoon"
  unit_id         int null references units(id)
  name_raw        text null           -- "Gram flour"
  ingredient_id   int null references ingredients(id)   -- null until resolved
  prep_note       text null           -- "deseeded", "finely chopped"
  is_optional     bool not null default false           -- "to taste", "for garnish"
  grams           numeric null        -- computed when convertible
  confidence      real null           -- 0..1, drives the review queue
  parser_version  int not null

  index: (ingredient_id), (recipe_id, position), (confidence) where ingredient_id is null
```
   The vocabulary

```
ingredients
  id                int primary key generated always as identity
  canonical_name    text not null unique     -- 'flour.all_purpose'
  display_name      text not null            -- 'all-purpose flour'
  category          text null                -- 'dry_good', 'produce', 'dairy'
  parent_id         int null references ingredients(id)   -- hierarchy
  is_staple         bool not null default false
  density_g_per_ml  numeric null
  grams_per_count   numeric null             -- 'one onion is ~150 g'
  line_count        int not null default 0   -- how common. drives ranking.

ingredient_aliases
  id             bigserial primary key
  ingredient_id  int not null references ingredients(id)
  alias          text not null unique     -- 'besan', 'gram flour', 'chickpea flour'
  origin         text not null            -- 'llm' | 'human' | 'dataset'

units
  id             int primary key generated always as identity
  name           text not null unique     -- 'tablespoon'
  kind           text not null            -- 'volume' | 'mass' | 'count'
  to_base        numeric not null         -- 14.79 (ml), 28.35 (g), 1 (count)

substitutions
  id             bigserial primary key
  ingredient_id  int not null references ingredients(id)
  substitute_id  int not null references ingredients(id)
  ratio          numeric not null default 1
  note           text null                -- 'add 1 tbsp acid per cup'
  confidence     real not null
```
   User state and provenance

```
pantry_items
  id             bigserial primary key
  user_id        int not null default 1   -- unused today. free now, a migration later.
  ingredient_id  int not null references ingredients(id)
  qty            numeric null
  unit_id        int null references units(id)
  added_at       timestamptz not null default now()
  expires_at     timestamptz null
  unique (user_id, ingredient_id)

review_queue
  id             bigserial primary key
  kind           text not null            -- 'cluster' | 'line' | 'substitution'
  payload        jsonb not null           -- the proposal awaiting a human
  impact_count   int not null             -- lines unblocked. ORDER BY this DESC.
  status         text not null default 'open'
  resolved_at    timestamptz null

generation_runs
  id                  bigserial primary key
  recipe_id           bigint not null references recipes(id)
  model               text not null
  prompt_version      text not null
  grounding_recipe_ids int[] not null     -- which real recipes informed it
  constraints         jsonb not null
  created_at          timestamptz not null default now()

cook_log
  id          bigserial primary key
  user_id     int not null default 1
  recipe_id   bigint not null references recipes(id)
  cooked_at   timestamptz not null default now()
  rating      int null                    -- 1..5
  notes       text null
```
   Why cook_log matters

A crawled recipe has been cooked by its author and validated by commenters. A generated recipe has been cooked by nobody. `cook_log` is how a generated recipe earns the same standing — it is the only signal in the system that distinguishes "plausible" from "actually worked."

## 4. The three queries


### Cook what you have


This is the query the whole schema is shaped around, so it needs to be exactly right.

Let **P** be the set of ingredient IDs in your pantry, and **R** be a recipe's `required_ingredient_ids` — which already has staples and optional items removed, because those were excluded when the column was built.  Match tiers

```
missing = R − P

Cookable now      |missing| = 0
Nearly there      1 ≤ |missing| ≤ N        (N defaults to 2)
Substitutable     every item in `missing` has a substitution
                   edge to something already in P
```


In SQL, containment is a single index-assisted operation. The `intarray` extension supplies the operators and a GIN opclass that makes them fast:  Query shape

```
-- cookable now
select id, title
from   recipes
where  required_ingredient_ids <@ :pantry_ids
and    cardinality(required_ingredient_ids) > 0;

-- nearly there, ranked
select id, title,
       required_ingredient_ids - :pantry_ids   as missing
from   recipes
where  required_ingredient_ids && :pantry_ids       -- indexed prefilter
and    icount(required_ingredient_ids - :pantry_ids) between 1 and :n
order by icount(required_ingredient_ids - :pantry_ids) asc,
         shopping_difficulty(required_ingredient_ids - :pantry_ids) asc;
```


**Ranking is the product.** Two recipes both missing one item are not equal — one needs an onion, the other needs saffron. Sort first by how many items are missing, then by how hard they are to buy, using `ingredients.line_count` as the proxy: an ingredient that appears in thousands of recipes is one your shop stocks.  Staples are not optional

If salt, water, oil, and black pepper count as missing ingredients, almost nothing in the corpus will ever match, and every result will read "you are missing: salt." Mark staples in the vocabulary and exclude them when building `required_ingredient_ids`. Let the user un-staple something when they genuinely run out.

### Find a recipe


Two independent searches, fused. Keyword search catches exact names; vector search catches "something warm with lentils." Neither alone is enough.

1. **Keyword** — Postgres full-text search over title, description, and the display names of resolved ingredients. Add a trigram index so typos still land.
2. **Semantic** — cosine similarity over `recipes.embedding`, using a small local embedding model (384 dimensions keeps the index manageable).
3. **Fuse** — reciprocal rank fusion. For each result, sum `1 / (60 + rank)` across both lists and sort by the total. No score normalization needed, and it is four lines of code.
4. **Filter** — cuisine, total time, must-include and must-exclude ingredient IDs, all as ordinary `WHERE` clauses.
  Embed selectively

Embeddings are the one part of this that isn't small. Four million recipes at 384 dimensions is roughly 6 GB before index overhead. Embed the subset you would plausibly cook, not the entire corpus — keyword search covers the long tail perfectly well.

### Generate something new


Generation is retrieval plus a model, and the retrieval is what keeps it honest.

1. **Collect constraints** — dietary restrictions, cuisine, time budget, servings, and optionally "use my pantry."
2. **Retrieve grounding** — six to eight real recipes, chosen by ingredient overlap when the request is pantry-driven, by vector similarity otherwise.
3. **Generate** — prompt the model with the constraints and the retrieved recipes, and require structured JSON output: title, servings, ingredient lines as plain strings, ordered steps.
4. **Parse the output through the same pipeline.** The generated ingredient lines go through the identical extraction and resolution used on crawled recipes.
5. **Store it as a recipe** with `source = 'generated'` and a `generation_runs` row recording the model, prompt version, and which real recipes grounded it.
  Why step 4 matters more than it looks

Running generated output through the same parser means generated recipes land in the same table, become searchable, become fridge-matchable, and are held to the same standard. If the model emits an ingredient line your parser can't resolve, that's a signal worth having — and a separate "generated recipes" code path would have hidden it.

## 5. Pipeline and serving


Two programs, one database, one rule between them: **the pipeline writes, the app reads.**

Pipeline · 1

Ingest

Load recipes into `recipes` with `raw_payload` intact. No parsing yet.

Pipeline · 2

Extract

Model batch over every ingredient line → qty, unit, name, prep, optional, confidence.

Pipeline · 3

Resolve

Cluster names, propose canonicals, queue low-confidence cases for review.

Pipeline · 4

Publish

Rebuild `required_ingredient_ids`, compute embeddings, refresh `line_count`.

App

Search

Keyword + vector, fused and filtered.

App

Pantry

Add, remove, list. The only meaningful write path.

App

Match

Cookable now and nearly-there, ranked.

App

Generate

Retrieve grounding, call the model, parse, store.

The separation is not stylistic. It means a broken pipeline can never take the app down, and it keeps the deployed artifact small and fast to start.  This exact failure has happened before

A prior system imported its recipe-generation helper at module load in the web layer. One malformed file — a source file written with literal `\n` escapes instead of newlines — raised a `SyntaxError` at import, and the entire API server failed to start. Not one endpoint: the whole process.

Keep the parser out of the request path and that class of bug can only ever break a batch job.

### HTTP surface
       `` `` `` `` `` `` `` `` `` `` ``

| Method & path | Does |
| --- | --- |
| GET /recipes/search | Fused keyword + semantic search, with filters |
| GET /recipes/{id} | One recipe, with resolved ingredient lines |
| GET /pantry | Current pantry contents |
| POST /pantry | Add or update an item |
| DELETE /pantry/{ingredient_id} | Remove an item |
| GET /match/cookable | Recipes fully covered by the pantry |
| GET /match/nearly?missing=2 | Recipes within N items, ranked |
| POST /generate | Constraints in, grounded recipe out |
| POST /cooked | Log that you made it, with a rating |
| GET /review/next | Highest-impact open review item |
| POST /review/{id} | Accept, correct, or reject a proposal |


## 6. Stack


The contracts in sections 3 and 4 are language-neutral. Build the app in whatever you want to get better at — this is the most reversible decision here.        ``    **

| Layer | Choice | Why |
| --- | --- | --- |
| Database | PostgreSQL 16+ | Recipes are relational and fridge-match is set containment — both native.                   pgvector covers semantic search and generation grounding in the                   same system, so there is no second datastore to operate. |
| Pipeline | Python | Extraction, clustering, and embeddings live in Python's ecosystem. Runs offline;                   never in the request path. |
| App | Go or C# | See below. Both are good fits and the schema doesn't care. |
| Client | Flutter | This is a phone-and-tablet app used standing at a counter. One codebase covers                   both, plus desktop if wanted. |
| Inference | Local model now | Behind one interface, so swapping to a hosted API later is a config change. |


### Go or C#


Genuinely close. The honest breakdown:

**C# is stronger on the merits for this specific project.** The domain is relational and transformation-heavy, which is exactly where EF Core and LINQ shine and where Go's manual SQL and hand-rolled loops are weakest. And .NET on Azure is the most first-class pairing in that cloud.

**Go is stronger if the crawler matters early or the binary size does.** A static binary in a scratch container starts faster and deploys smaller. For a single-user app hit a few times a day, that difference is not something you will ever perceive.

Pick by which skill you want this project to build. Nothing in this document changes either way.

### Why not Elasticsearch


It is the obvious choice for recipe search and it is the wrong one here. Fridge-match is a set-containment query, which SQL does natively and a search engine does awkwardly. Choosing it means running two datastores and keeping them in sync, and it is precisely the operational weight that stalled a previous attempt at this — a three-node cluster provisioned to search a recipe corpus that never made it to deployment. Postgres full-text plus trigram indexes closes most of the quality gap at personal scale.

## 7. Where it runs


### Phase A — everything local


Postgres, the pipeline, the inference server, and the app all run on one machine at home. Access over the LAN or a private network overlay. No cloud, no cost, no deployment step while the design is still moving.

### Phase B — the Azure lift


The split falls naturally along size, because most of what a cooking app serves is tiny:

| Stays home | Moves to Azure |
| --- | --- |
| Raw crawled HTML — hundreds of GB | Normalized recipe rows — single-digit GB |
| Full-resolution recipe images | Pantry and cook log — megabytes |
| Model weights and checkpoints | Embeddings for the curated subset |
| The crawler and the batch pipeline | The app itself |


Home stays the **system of record**: you crawl, parse, canonicalize, and embed there. Azure receives a derived, read-mostly artifact plus the small writable tables for pantry and cook log. Publishing an update is a snapshot, not a live connection.  Never expose the home database

If the cloud app needs to reach home, the connection is outbound-only from home through a private network overlay or a tunnel. Never a forwarded port, never a public IP in a connection string.

The prior attempt at this shipped a mobile app containing a hardcoded database password and a residential WAN address, committed to version control in three separate files, with the very same paths listed in `.gitignore` under a comment reading "NEVER commit these." A `.gitignore` rule does nothing to a file that is already tracked.

### What "later Azure" means for generation


Hosting your own model in Azure is the expensive path — GPU virtual machines run dollars per hour with no scale-to-zero. The realistic version is that generation moves to a hosted API while everything else lifts unchanged. That is why the inference interface exists from day one: one method, two implementations, config selects between them.

## 8. Build phases


Each phase is independently useful and has a measurable exit gate. Phase 3 is already a working app you would use.  00

### Storage


Create the schema. Load the seed recipes with `raw_payload` preserved and `ingredient_lines` populated with `raw_text` only — no parsing.

**Gate** Row counts match the source exactly. Every `ingredient_lines.raw_text` is non-null. You can reconstruct any original record from the database alone.    01

### Extraction


Batch the model over all 228,067 lines. Fill quantity, unit, name, prep note, optional flag, and confidence. Do not resolve to canonical IDs yet.

**Gate** ≥95% of lines yield a name. Spot-check 100 by hand, including the awkward ones — ranges, "to taste", parenthetical translations.    02

### Vocabulary


Cluster the extracted names, propose canonicals and aliases, and populate the review queue in impact order. Review the top clusters. Set staple flags and the hierarchy.

**Gate** ≥80% of ingredient lines resolve to a canonical ID, and the 200 most common ingredients are human-confirmed.    03

### Fridge match — first real feature


Pantry CRUD, `required_ingredient_ids` maintenance, and both match tiers with ranking. A usable client, even a rough one.

**Gate** A realistic 20-item pantry returns sensible results in under 100 ms, and the nearly-there list surfaces things you would actually cook.    04

### Search


Full-text and trigram indexes, embeddings for the curated subset, rank fusion, filters.

**Gate** Ten hand-written queries — a mix of exact names and vague descriptions — all return a relevant result in the top five.    05

### Generation


Grounding retrieval, the inference interface with its local implementation, structured output, and the parse-back step.

**Gate** Generated recipes parse through the standard pipeline at the same resolution rate as corpus recipes, and appear correctly in fridge-match results.    06

### Azure lift


App and database to the cloud, generation to a hosted API, pipeline and bulk data stay home. Snapshot-based publishing.

**Gate** The deployed app returns identical results to local for a fixed set of test queries. No inbound path to the home network exists.    07

### Your own corpus


The crawler, feeding the same pipeline as a second source. This is where the corpus stops being borrowed and starts being yours, with images and real provenance.

**Gate** Crawled recipes resolve at the same rate as dataset ones, robots.txt is honored, and the user agent you check rules for is the one you send.

## 9. Known traps


Every item here is a bug that was actually shipped in a previous attempt at this problem, verified by running the code. They are cheap to avoid in advance and expensive to find later.        ````````  ````````    ``  ``  ``    ````    ``

| Trap | What went wrong | Guard |
| --- | --- | --- |
| Destructive parsing | "2 cups flour" stored as unit cup, ingredient                   "s flour" — original discarded | Keep raw_text forever; version the parser |
| Alternation order | cup|cups matches "cup" and leaves an orphan "s".                   l|liter turns "2 large eggs" into unit l,                   ingredient "arge eggs" | Longest alternative first; anchor with word boundaries |
| Substring matching | Pantry "ice" satisfied a recipe needing "rice"; "eggplant" satisfied "egg" | Match on canonical IDs, never on string containment |
| Ignoring quantity | An item with quantity 0 still counted as in stock | Treat non-positive quantities as absent |
| Unvalidated regex | [{}[\]" — an unterminated character class — panicked at runtime on                   every single call | Compile all patterns at startup, in a test |
| Fatal in a handler | A search error called log.Fatal, exiting the whole server process on                   one bad query | Handlers return errors; only startup may exit |
| Import-time coupling | One malformed module stopped the entire API from starting | Pipeline out of the request path; lazy-load optional services |
| Committed credentials | Database password and a residential WAN IP in three tracked files, all named in                   .gitignore | Secrets from environment only; .gitignore cannot untrack |
| Fail-open auth | Empty API key meant no authentication, and the deployment never set one | Missing credentials must refuse to start, not open the door |
| Ungated tests | continue-on-error: true on a test step that could not have passed                   anyway — it ran against a project the build never compiled | Tests gate the deploy or they are decoration |
| Docs ahead of code | A 19 KB implementation guide describing a feature that has never compiled | Exit gates in section 8 are measured, not asserted |
   The pattern underneath

Nine of these eleven are invisible until something is run. A build-and-test step in continuous integration would have caught every compile-level failure in the list on the day it was introduced. Set that up in phase 0, before there is anything to break.

Sections 1–4 are the design. Sections 5–7 are the deployment. Section 8 is the order to build it in and 9 is what to avoid on the way. Start at phase 0 — the corpus is already on disk.

