class SubtasksMissingError(Exception):
    """Exception raised when no subtasks are created for the given query."""

    def __init__(self, query: str):
        self.query = query
        super().__init__(f"Subtasks are missing for the given query: {query}")
