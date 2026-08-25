"""Stage 4 - publish.

Rebuild the derived columns the API reads:

  * recipes.all_ingredient_ids       every resolved ingredient
  * recipes.required_ingredient_ids  staples and optionals removed - the match key
  * ingredients.line_count           commonness, which drives match ranking
  * recipes.embedding                for the curated subset only

Staples are excluded here, once, so the fridge-match query never has to think
about them. Get this wrong and every result reads "you are missing: salt".
"""
from __future__ import annotations

from .config import Config


def run(cfg: Config, embed: bool = False) -> int:
    """Refresh derived columns. Returns recipes touched."""
    raise NotImplementedError("phase 3")
