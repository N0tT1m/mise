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

Postgres 16+ with the `vector`, `pg_trgm`, and `intarray` extensions.

    createdb mise
    psql -d mise -f db/001_schema.sql
    psql -d mise -f db/002_seed.sql

Then the pipeline:

    cd pipeline && pip install -e .

And the API (Go 1.25+, no dependencies yet):

    cd api && cp .env.example .env
    export $(grep -v '^#' .env | xargs) && go run .

## Build order

Phases are in the spec, section 8. Start at phase 0: load the seed corpus with
`raw_payload` intact and no parsing at all. The corpus is already on disk at
`ai-apps/chef-genius/cli/` — 20,366 recipes, 228,067 ingredient lines.
