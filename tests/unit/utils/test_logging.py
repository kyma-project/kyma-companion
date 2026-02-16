import json
import logging
from unittest.mock import Mock, patch

import pytest
from tenacity import RetryCallState

from utils.logging import PrettyJSONFormatter, after_log, get_logger


def test_get_logger():
    logger_name = "test_logger"
    logger = get_logger(logger_name)
    assert logger.name == logger_name


@pytest.mark.parametrize(
    "description, module_name, func_name, expected_logger_name",
    [
        ("should work when fn is None", None, None, "tenancy.retry.None"),
        ("should work when function name is empty", "testing", "", "testing.None"),
        (
            "should work when module name is empty",
            "",
            "get_resource",
            "tenancy.retry.get_resource",
        ),
        (
            "should work when both names are non-empty",
            "testing",
            "get_resource",
            "testing.get_resource",
        ),
    ],
)
def test_after_log(description, module_name, func_name, expected_logger_name):
    # Mock retry_state with required attributes
    retry_state = Mock(spec=RetryCallState)
    retry_state.attempt_number = 1

    if module_name is None and func_name is None:
        retry_state.fn = None
    else:
        retry_state.fn = Mock(__module__=module_name, __name__=func_name)

    with patch("utils.logging.get_logger") as mock_get_logger:
        mock_logger = Mock()
        mock_get_logger.return_value = mock_logger

        # when
        after_log(retry_state)

        # then
        mock_get_logger.assert_called_once_with(expected_logger_name)


class TestPrettyJSONFormatter:
    """Tests for PrettyJSONFormatter."""

    def test_format_basic_log_record(self):
        """Test formatting a basic log record with required fields only."""
        formatter = PrettyJSONFormatter()
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["message"] == "Test message"
        assert "timestamp" in log_data

    def test_format_with_extra_fields(self):
        """Test formatting a log record with all extra fields."""
        formatter = PrettyJSONFormatter()
        record = logging.LogRecord(
            name="access",
            level=logging.INFO,
            pathname="main.py",
            lineno=50,
            msg="HTTP Request",
            args=(),
            exc_info=None,
        )
        # Add extra fields
        record.method = "GET"
        record.path = "/api/test"
        record.status_code = 200
        record.duration_ms = 123.45
        record.client = "192.168.1.1"

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["method"] == "GET"
        assert log_data["path"] == "/api/test"
        assert log_data["status_code"] == 200
        assert log_data["duration_ms"] == 123.45
        assert log_data["client"] == "192.168.1.1"

    def test_format_with_partial_extra_fields(self):
        """Test formatting with only some extra fields present."""
        formatter = PrettyJSONFormatter()
        record = logging.LogRecord(
            name="access",
            level=logging.WARNING,
            pathname="main.py",
            lineno=50,
            msg="Slow request",
            args=(),
            exc_info=None,
        )
        # Add only some extra fields
        record.path = "/api/slow"
        record.duration_ms = 5000.0

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["path"] == "/api/slow"
        assert log_data["duration_ms"] == 5000.0
        assert "method" not in log_data
        assert "status_code" not in log_data
        assert "client" not in log_data

    def test_format_output_is_valid_json(self):
        """Test that output is valid pretty-printed JSON."""
        formatter = PrettyJSONFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=100,
            msg="Error occurred",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)

        # Should be valid JSON
        parsed = json.loads(result)
        assert isinstance(parsed, dict)

        # Should be pretty-printed (contains newlines and indentation)
        assert "\n" in result
        assert "  " in result
