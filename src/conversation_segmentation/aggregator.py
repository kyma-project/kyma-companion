"""Tally segmented turns into the 9x3 category x judgement crosstab."""

from conversation_segmentation.taxonomy import Category, Judgement, cell_column, crosstab_columns


class Crosstab:
    """Tally of conversation turn classifications into a 9x3 category-judgment grid."""

    def __init__(self) -> None:
        self._cells: dict[str, int] = {c: 0 for c in crosstab_columns()}
        self.total_turns: int = 0
        self.failed_turns: int = 0

    def add(self, category: Category, judgement: Judgement) -> None:
        """Record a turn classified into a category-judgement cell."""
        self._cells[cell_column(category, judgement)] += 1
        self.total_turns += 1

    def add_failure(self) -> None:
        """Record a turn that failed to classify (increases total_turns but not any cell)."""
        self.failed_turns += 1
        self.total_turns += 1

    def cells(self) -> dict[str, int]:
        """Return a copy of all 27 crosstab cells, zero-filled."""
        return dict(self._cells)
