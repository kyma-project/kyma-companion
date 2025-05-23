from unittest.mock import Mock, patch

import pytest
from tenacity import RetryCallState

from utils.logging import after_log, get_logger


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
