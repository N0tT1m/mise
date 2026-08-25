"""Stage 3 - resolve.

Cluster extracted names into canonical ingredients, propose aliases, and set
ingredient_lines.ingredient_id where confidence is high enough.

Everything below the threshold goes to review_queue with an impact_count -
the number of lines the decision would unblock. The queue is always worked in
impact order; an alphabetical queue wastes the effort.

Exit gate: >=80% of lines resolve, and the 200 most common ingredients are
human-confirmed.
"""
from __future__ import annotations

from .config import Config

AUTO_APPLY_CONFIDENCE = 0.90


def run(cfg: Config) -> tuple[int, int]:
    """Resolve what is confident, queue the rest. Returns (resolved, queued)."""
    raise NotImplementedError("phase 2")
