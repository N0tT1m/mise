# Mise

A cooking platform built on one canonical ingredient graph: find recipes,
match against what's in your fridge, generate new ones grounded in real ones.

**Spec:** https://claude.ai/code/artifact/f34f03b2-c297-4554-9365-449e6442ee39

Phase 0 (ingest) is done: 20,366 recipes and 228,067 ingredient lines load
from two source corpora, idempotently, with the original record preserved
verbatim. Phases 1-5 are stubs — extract, resolve, publish, and every HTTP
endpoint still raise or return 501.

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

## The corpus

`data/` is gitignored — the recipe data is not redistributed here. Two
Kaggle-derived sets, one directory each, one JSON file per directory:

    data/recipes/recipe_dataset_simple/training.json   13,495 recipes
    data/recipes/indian_recipe_api/training.json        6,871 recipes

Each file is a JSON array of `{input_data, output_data}` records. Check the
licence on the original datasets before redistributing anything derived from
them; nothing in this repository grants rights to the data.

To point the pipeline at your own corpus, match that shape and directory
layout — one JSON array per directory, `ingest` takes it from there.

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
