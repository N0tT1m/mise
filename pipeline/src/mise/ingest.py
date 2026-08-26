"""Stage 1 - ingest.

Load source recipes into `recipes` with `raw_payload` preserved verbatim, and
one `ingredient_lines` row per line carrying `raw_text` ONLY. No parsing here.

Exit gate: row counts match the source exactly, every raw_text is non-null,
and any original record can be reconstructed from the database alone.
"""
from __future__ import annotations

import psycopg

from .config import Config
import json
from pathlib import Path
from psycopg.types.json import Jsonb

CHUNK = 500

def _validate(records: object, source_file: Path) -> list[dict]:
    """Assert the corpus shape. Inspects only - never filters or repairs."""
    if not isinstance(records, list):
        raise ValueError(
            f"{source_file}: expected a JSON array of records, "
            f"got {type(records).__name__}"
        )

    for index, record in enumerate(records):
        where = f"{source_file} record {index}"
        if not isinstance(record, dict):
            raise ValueError(f"{where}: expected a JSON object, got {type(record).__name__}")

        for key in ("input_data", "output_data"):
            if not isinstance(record.get(key), dict):
                raise ValueError(f"{where}: {key} is missing or not an object")

        # run() reads this with ["title"], so a missing one would be a KeyError
        # thousands of inserts into the transaction.
        title = record["output_data"].get("title")
        if not isinstance(title, str) or not title.strip():
            raise ValueError(f"{where}: output_data.title is missing or blank")

        # Absent is allowed: 12 records in the current corpus have no
        # ingredients key at all, and ingest stores them with zero lines.
        ingredients = record["output_data"].get("ingredients")
        if ingredients is not None and not isinstance(ingredients, list):
            raise ValueError(f"{where}: input_data.ingredients is not a list")

    return records

def _load(path: Path) -> list[dict]:
    sorted_path = sorted(path.glob("*.json"))
    count_path = len(sorted_path)

    if count_path == 0:
        raise FileNotFoundError(f"no json file in {path}")
    if count_path == 1:
        json_file = sorted_path[0]

        if json_file.is_file():
            with json_file.open("r", encoding="utf-8") as f:
                content = json.load(f)
        else:
            raise FileNotFoundError("No json file found.")
    else:
        raise ValueError(f"Expected exactly one JSON file in {path}, but found more.")

    return _validate(content, json_file)

def run(cfg: Config, source: str, path: str) -> int:
    """Ingest one source. Returns the number of recipes written."""
    records = _load(Path(path))

    # Pair every record with its position in the file. That index IS source_ref,
    # so it must come from the whole list, not from position within a chunk.
    indexed = list(enumerate(records))
    written = 0

    # Exiting this block commits; any exception rolls the whole thing back.
    with psycopg.connect(cfg.database_url) as conn:
        with conn.cursor() as cursor:
            for start in range(0, len(indexed), CHUNK):
                chunk = indexed[start:start + CHUNK]

                # One flat list of values: five per record, in column order
                params = []
                for index, record in chunk:
                    out = record["output_data"]
                    params.extend([
                        source,
                        str(index),
                        out["title"],
                        Jsonb(out.get("instructions") or []),
                        Jsonb(record),
                    ])

                # One "(%s, %s, %s, %s, %s)" group per record.
                placeholders = ", ".join(["(%s, %s, %s, %s, %s)"] * len(chunk))

                cursor.execute(
                    "INSERT INTO recipes "
                    "(source, source_ref, title, instructions, raw_payload) "
                    f"VALUES {placeholders} "
                    "ON CONFLICT (source, source_ref) DO NOTHING "
                    "RETURNING id, source_ref",
                    params,
                )

                # Rows that conflicted don't come back. No row = already ingested.
                inserted = cursor.fetchall()
                written += len(inserted)

                if not inserted:
                    continue

                # Lines only for recipes that actually inserted.
                with cursor.copy(
                    "COPY ingredient_lines (recipe_id, position, raw_text) FROM STDIN"
                ) as copy:
                    for recipe_id, ref in inserted:
                        record = records[int(ref)]
                        ingredients = record["input_data"].get("ingredients") or []
                        for position, raw_text in enumerate(ingredients):
                            copy.write_row((recipe_id, position, raw_text))

    return written