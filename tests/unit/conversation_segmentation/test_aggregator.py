"""Tests for the crosstab aggregator."""

import pytest

from conversation_segmentation.aggregator import Crosstab
from conversation_segmentation.taxonomy import Category, Judgement, crosstab_columns

pytestmark = pytest.mark.unit


def test_cells_zero_filled_and_counts_add_up():
    ct = Crosstab()
    ct.add(Category.TROUBLESHOOTING, Judgement.INSUFFICIENT)
    ct.add(Category.TROUBLESHOOTING, Judgement.INSUFFICIENT)
    ct.add(Category.SETUP_CONFIGURATION, Judgement.SUFFICIENT)
    ct.add_failure()
    cells = ct.cells()
    assert set(cells) == set(crosstab_columns())  # all 27 present
    assert cells["C_TROUBLESHOOTING_INSUFFICIENT"] == 2  # noqa: PLR2004
    assert cells["C_SETUP_CONFIGURATION_SUFFICIENT"] == 1  # noqa: PLR2004
    assert sum(cells.values()) == 3  # noqa: PLR2004
    assert ct.total_turns == 4 and ct.failed_turns == 1  # noqa: PLR2004
