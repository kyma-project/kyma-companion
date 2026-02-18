import json
import logging
from http import HTTPStatus
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
        # Given
        expected_method = "GET"
        expected_path = "/api/test"
        expected_status_code = HTTPStatus.OK
        expected_duration_ms = 123.45
        expected_client = "192.168.1.1"

        record.path = expected_path
        record.status_code = expected_status_code
        record.duration_ms = expected_duration_ms
        record.client = expected_client

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["method"] == expected_method
        assert log_data["path"] == expected_path
        assert log_data["status_code"] == expected_status_code
        assert log_data["duration_ms"] == expected_duration_ms
        assert log_data["client"] == expected_client

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
        # Given
        expected_path = "/api/slow"
        expected_duration_ms = 5000.0

        # Add only some extra fields
        record.path = expected_path
        record.duration_ms = expected_duration_ms

        result = formatter.format(record)
        log_data = json.loads(result)

        assert log_data["path"] == expected_path
        assert log_data["duration_ms"] == expected_duration_ms
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
