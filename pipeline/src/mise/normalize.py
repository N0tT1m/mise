"""Text normalisation for scraped corpus text.

The corpus arrives with the debris of HTML scraping: non-breaking spaces where
a scraper kept `&nbsp;`, soft hyphens left over from justified text, and the
occasional zero-width space. None of it is visible in an editor and all of it
breaks matching later -- `extra-\xadvirgin olive oil` will never equal
`extra-virgin olive oil`, and the failure is silent.

This module is used by the EXTRACT stage, never by ingest. `raw_payload` and
`ingredient_lines.raw_text` keep the original bytes forever, because the
parser will be wrong repeatedly and re-running it is only possible while the
original input still exists.

The order of operations below is load-bearing. See `clean` for why.
"""
from __future__ import annotations

import re
import unicodedata

# Vulgar fractions, mapped explicitly rather than via NFKC.
#
# NFKC looks like the obvious tool here and is a trap: it rewrites "2\xbe tsp."
# to "23/4 tsp." (with U+2044 FRACTION SLASH), which a quantity parser reads as
# 23/4 = 5.75 instead of 2.75. Vulgar fractions are pervasive in the western
# half of the corpus, so blanket NFKC would corrupt quantities at scale.
# NFKC also leaves soft hyphens untouched, so it does not even solve the
# problem it is reached for.
_FRACTIONS = {
    "¼": "1/4", "½": "1/2", "¾": "3/4",
    "⅐": "1/7", "⅑": "1/9", "⅒": "1/10",
    "⅓": "1/3", "⅔": "2/3",
    "⅕": "1/5", "⅖": "2/5", "⅗": "3/5", "⅘": "4/5",
    "⅙": "1/6", "⅚": "5/6",
    "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8",
    "↉": "0/3",
}

_FRACTION_RE = re.compile("([0-9]?)([" + "".join(_FRACTIONS) + "])")
_WHITESPACE_RE = re.compile(r"\s+")

"""
_expand_fractions(text) -> str — 2¾ → 2 3/4, bare ¾ → 3/4
"""
def _expand_fractions(text):
    """`2¾` -> `2 3/4`, bare `¾` -> `3/4`."""
    def sub(m: re.Match[str]) -> str:
        digit = m.group(1)  # "2"  or  ""
        glyph = m.group(2)  # "¾"
        fraction = _FRACTIONS[glyph]  # "3/4"

        if digit:
            return f"{digit} {fraction}" # "2 3/4"
        return fraction # "3/4"

    return _FRACTION_RE.sub(sub, text)

"""
clean(text) -> str
"""
def clean(text):
    """Normalise one string for parsing. Never applied to stored raw text"""
    # Step 1 - fractions first, while the digit is still next to the glyph
    text = _expand_fractions(text)

    # Steps 2 and 3 - one pass, sorting each character into three outcomes
    out = []
    for ch in text:
        category = unicodedata.category(ch)
        if category == "Cf":
            continue # format char: soft hyphen, ZWSP, BOM - drop it
        if category == "Zs":
            out.append(" ") # space separator: NBSP, thin space - normalise it
        else:
            out.append(ch) # everything else passes through untouched

    # Step 4 - collapse runs of whitespace, then trim the ends.
    return _WHITESPACE_RE.sub(" ", "".join(out).strip())

"""
is_dirty(text) -> bool
"""
def is_dirty(text):
    """True when `clean` would change this string. Cheap enough for auditing."""
    return clean(text) != text