import pytest

from conversation_segmentation.taxonomy import Category, Judgement, cell_column, crosstab_columns

pytestmark = pytest.mark.unit


def test_nine_categories_three_judgements():
    assert len(list(Category)) == 9  # noqa: PLR2004
    assert {j.value for j in Judgement} == {"SUFFICIENT", "PARTIAL", "INSUFFICIENT"}


def test_crosstab_has_27_unique_uppercase_columns():
    cols = crosstab_columns()
    assert len(cols) == 27  # noqa: PLR2004
    assert len(set(cols)) == 27  # noqa: PLR2004
    assert all(c.isupper() and c.startswith("C_") for c in cols)


def test_cell_column_matches_pattern():
    assert cell_column(Category.TROUBLESHOOTING, Judgement.INSUFFICIENT) == "C_TROUBLESHOOTING_INSUFFICIENT"
