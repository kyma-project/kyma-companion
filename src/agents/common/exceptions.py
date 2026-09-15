class TotalChunksLimitExceededError(Exception):
    """Exception raised when the total number of chunks exceeds the limit."""

    def __init__(self):
        super().__init__("Total number of chunks exceeds TOTAL_CHUNKS_LIMIT")
