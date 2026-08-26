"""Tests for corpus text normalisation.

The cases here are drawn from real corpus lines, not invented ones -- each
string below appears verbatim in the datasets the pipeline ingests.
"""
from mise.normalize import clean, is_dirty


class TestFractions:
    def test_whole_and_fraction_keeps_them_separate(self):
        # The NFKC trap: "23/4" would parse as 5.75 instead of 2.75.
        assert clean("2¾ tsp. kosher salt") == "2 3/4 tsp. kosher salt"

    def test_bare_fraction_gains_no_leading_space(self):
        assert clean("½ cup rice") == "1/2 cup rice"

    def test_every_glyph_expands(self):
        assert clean("¼ ⅓ ⅜ ⅝ ⅞") == "1/4 1/3 3/8 5/8 7/8"

    def test_fraction_inside_a_range(self):
        assert clean("1½-2 lb. chicken") == "1 1/2-2 lb. chicken"


class TestInvisibleCharacters:
    def test_nbsp_becomes_a_space(self):
        assert clean("To begin making the Masala Karela Recipe") == (
            "To begin making the Masala Karela Recipe"
        )

    def test_soft_hyphen_is_deleted_not_spaced(self):
        # "extra- virgin" would be just as unmatchable as "extra-\xadvirgin".
        assert clean("1/4 cup extra-­virgin olive oil") == (
            "1/4 cup extra-virgin olive oil"
        )

    def test_zero_width_space_is_deleted(self):
        assert clean("black​pepper") == "blackpepper"

    def test_bom_and_bidi_marks_are_deleted(self):
        assert clean("﻿salt‎") == "salt"

    def test_thin_and_narrow_spaces_become_spaces(self):
        assert clean("200 grams okra") == "200 grams okra"


class TestWhitespace:
    def test_runs_collapse(self):
        assert clean("2  sprig   Coriander") == "2 sprig Coriander"

    def test_tabs_and_newlines_collapse(self):
        assert clean("1 onion\t-\nthinly sliced") == "1 onion - thinly sliced"

    def test_surrounding_whitespace_is_stripped(self):
        assert clean("  salt  ") == "salt"

    def test_empty_string_survives(self):
        assert clean("") == ""


class TestPreservation:
    def test_devanagari_is_untouched(self):
        # 15,083 corpus lines are Hindi. Normalisation must not mangle them;
        # what to DO with them is a resolve-stage policy question.
        assert clean("1/2 कप मूंगफली - सेक ले") == "1/2 कप मूंगफली - सेक ले"

    def test_clean_text_is_unchanged(self):
        line = "2 tablespoons mango or other store-bought chutney"
        assert clean(line) == line

    def test_clean_is_idempotent(self):
        once = clean("2¾ tsp. kosher salt")
        assert clean(once) == once


class TestIsDirty:
    def test_flags_only_strings_that_would_change(self):
        assert is_dirty("the recipe")
        assert not is_dirty("the recipe")
