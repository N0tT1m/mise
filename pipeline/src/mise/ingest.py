"""Stage 1 - ingest.

Load source recipes into `recipes` with `raw_payload` preserved verbatim, and
one `ingredient_lines` row per line carrying `raw_text` ONLY. No parsing here.

Exit gate: row counts match the source exactly, every raw_text is non-null,
and any original record can be reconstructed from the database alone.
"""
from __future__ import annotations

from .config import Config


def run(cfg: Config, source: str, path: str) -> int:
    """Ingest one source. Returns the number of recipes written."""
    raise NotImplementedError("phase 0")
