# Mise

A cooking platform built on one canonical ingredient graph: find recipes,
match against what's in your fridge, generate new ones grounded in real ones.

**Spec:** https://claude.ai/code/artifact/f34f03b2-c297-4554-9365-449e6442ee39

This is a scaffold. Nothing is implemented yet — every stage and endpoint is a
stub. The schema is real and applies cleanly.

## Layout

    db/         schema + seed data (language-neutral, the substance)
    pipeline/   Python: ingest -> extract -> resolve -> publish (offline only)
    api/        Go HTTP API (stdlib net/http; reads only)

## The one rule

The pipeline writes, the app reads. No parsing in the request path.

## Local setup

Postgres 17 with `vector`, `pg_trgm`, and `intarray`, via Docker. The image
carries all three; the schema and seed apply automatically on first start.

    cp .env.example .env        # then set POSTGRES_PASSWORD
    docker compose up -d

The init scripts run only when the volume is empty. After a schema change:
`docker compose down -v && docker compose up -d`, which also destroys the data.

Then the pipeline (uv manages the venv and Python):

    uv run --project pipeline mise-pipeline --help
    cd pipeline && uv run --extra dev pytest

And the API (Go 1.25+, no dependencies yet):

    cd api && cp .env.example .env
    set -a; . ./.env; set +a && go run .

## Build order

Phases are in the spec, section 8.

Phase 0 (ingest) is done. The corpus lives in `data/` — gitignored, two source
files, 20,366 recipes and 228,067 ingredient lines between them:

    uv run --project pipeline mise-pipeline ingest \
        --source dataset:western --path data/recipes/recipe_dataset_simple
    uv run --project pipeline mise-pipeline ingest \
        --source dataset:indian  --path data/recipes/indian_recipe_api

One directory per call, holding exactly one JSON file. `source_ref` is the
record's index within that file, unique per source, so re-running is a no-op
rather than a duplicate.

Next is phase 1 (extract): structure all 228,067 `raw_text` values. Run each
through `normalize.clean` first — 2,047 ingredient lines carry non-breaking
spaces, soft hyphens or zero-width characters. Never write back to `raw_text`.
