"""Stage 2 - extract.

Batch a model over every ingredient_lines.raw_text to fill qty_min, qty_max,
unit_raw, name_raw, prep_note, is_optional and confidence.

Does NOT resolve to canonical ingredient ids - that is stage 3.

Never write back to raw_text. Stamp parser_version on every row so a later,
better extractor can backfill selectively.

Run every raw_text through `normalize.clean` before parsing it. The corpus
carries scraping debris -- 2,047 ingredient lines contain non-breaking spaces,
soft hyphens or zero-width characters, and 14,986 instruction strings do. All
of it is invisible in an editor and none of it survives a naive split. Do not
reach for NFKC instead; see the note in `normalize` for why it corrupts
quantities.

Exit gate: >=95% of lines yield a name; 100 hand-checked, including ranges,
"to taste", and parenthetical translations.
"""
from __future__ import annotations

from .config import Config


def run(cfg: Config, limit: int | None = None) -> int:
    """Extract structure from unparsed lines. Returns lines updated."""
    raise NotImplementedError("phase 1")
