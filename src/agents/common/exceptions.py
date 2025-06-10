class SubtasksMissingError(Exception):
    """Exception raised when no subtasks are created for the given query."""

    def __init__(self, query: str):
        self.query = query
        super().__init__(f"Subtasks are missing for the given query: {query}")


class TotalChunksLimitExceededError(Exception):
    """Exception raised when the total number of chunks exceeds the limit."""

    def __init__(self):
        super().__init__("Total number of chunks exceeds TOTAL_CHUNKS_LIMIT")
