from html.parser import HTMLParser


class HtmlTableParser(HTMLParser):
    """Parses a text chunk containing one or more HTML tables.

    Produces:
        tables      — list of (intro, header_cells, data_rows) per table
                      intro: raw text immediately before this table
                      header_cells: list[str] from <th> in first <tr>
                      data_rows: list[list[str]], one inner list per <tr>
        outro_text  — raw text after the last </table>
    """

    def __init__(self) -> None:
        super().__init__()
        self._depth: int = 0  # nesting depth; >0 means inside a table
        self._in_th: bool = False
        self._in_td: bool = False
        self._current_cell: list[str] = []
        self._current_row: list[str] = []
        self._current_header: list[str] = []
        self._header_done: bool = False  # True after first <tr> of current table is closed
        self._current_rows: list[list[str]] = []
        self._pre_table_buf: list[str] = []  # collects text before/between tables
        self._table_started: bool = False
        self._between_buf: list[str] = []  # text between tables
        self.tables: list[tuple[str, list[str], list[list[str]]]] = []
        self.outro_text: str = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        """Track table nesting and collect cell content on opening tags."""
        if tag == "table":
            if self._depth == 0:
                if not self._table_started:
                    intro = "".join(self._pre_table_buf).strip()
                    self._table_started = True
                else:
                    intro = "".join(self._between_buf).strip()
                    self._between_buf = []
                self._current_intro = intro
                self._current_header = []
                self._current_rows = []
                self._header_done = False
            self._depth += 1
        elif tag == "tr" and self._depth == 1:
            self._current_row = []
        elif tag == "th" and self._depth == 1:
            self._in_th = True
            self._current_cell = []
        elif tag == "td" and self._depth == 1:
            self._in_td = True
            self._current_cell = []

    def handle_endtag(self, tag: str) -> None:
        """Finalise cells, rows, and tables on closing tags."""
        if tag == "table":
            self._depth -= 1
            if self._depth == 0:
                self.tables.append((self._current_intro, list(self._current_header), list(self._current_rows)))
        elif tag == "tr" and self._depth == 1:
            if not self._header_done and self._current_header:
                # First <tr> that contained <th> cells is the header row — mark it done
                # so all subsequent <tr>s are treated as data rows.
                self._header_done = True
            elif self._current_row:
                self._current_rows.append(list(self._current_row))
            self._current_row = []
        elif tag == "th" and self._depth == 1:
            self._in_th = False
            cell = " ".join(self._current_cell).strip()
            if cell:
                self._current_header.append(cell)
            self._current_cell = []
        elif tag == "td" and self._depth == 1:
            self._in_td = False
            cell = " ".join(self._current_cell).strip()
            self._current_row.append(cell)
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        """Accumulate text into the active cell or pre/between-table buffer."""
        stripped = data.strip()
        if not stripped:
            return
        if self._in_th or self._in_td:
            self._current_cell.append(stripped)
        elif self._depth == 0:
            if not self._table_started:
                self._pre_table_buf.append(stripped + " ")
            else:
                self._between_buf.append(stripped + " ")

    def close(self) -> None:
        """Flush the parser and finalise outro_text from the trailing buffer."""
        super().close()
        self.outro_text = "".join(self._between_buf).strip()
