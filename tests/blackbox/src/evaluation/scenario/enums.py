from enum import IntEnum, StrEnum


class TestStatus(StrEnum):
    """Category represents enum for the category of an expectation."""

    PASSED = "passed"  # PASSED means that the test results are 100% as expected.
    COMPLETED = (
        "completed"  # COMPLETED means that the test is completed but with score < 100%.
    )
    FAILED = (
        "failed"  # FAILED means that the test failed to get response from companion.
    )
    PENDING = "pending"  # PENDING means that the test is not yet completed.
