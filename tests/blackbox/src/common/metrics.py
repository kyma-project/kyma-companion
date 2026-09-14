from typing import Any


class Metrics:
    """Singleton class to store metrics."""

    __instance: "Metrics | None" = None
    conversation_response_times_sec: list[float] = []

    @staticmethod
    def get_instance() -> Any:
        """Static access method."""
        if Metrics.__instance is None:
            Metrics()
        return Metrics.__instance

    def __init__(self):
        """Virtually private constructor."""
        if Metrics.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Metrics.__instance = self

    def record_conversation_response_time(self, time_sec: float) -> None:
        """Record the response time of the conversation endpoint."""
        self.conversation_response_times_sec.append(time_sec)

    def get_conversation_response_summary(self) -> dict:
        """Get the summary of response times for the conversation endpoint."""
        average = 0.0
        maximum = 0.0
        minimum = 0.0

        if len(self.conversation_response_times_sec) != 0:
            average = sum(self.conversation_response_times_sec) / len(self.conversation_response_times_sec)
            maximum = max(self.conversation_response_times_sec)
            minimum = min(self.conversation_response_times_sec)

        return {
            "average": round(average, 4),
            "max": round(maximum, 4),
            "min": round(minimum, 4),
        }
