from typing import Any
from unittest.mock import AsyncMock, Mock

import pytest
from langchain.chains.base import Chain

from utils.chain import ainvoke_chain


@pytest.fixture
def mock_chain():
    """Fixture for creating a mock LangChain chain."""
    chain = Mock(spec=Chain)
    chain.ainvoke = AsyncMock()
    return chain


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "input_data,config,mock_response,expected_chain_input,expected_output,expected_calls,expected_exception",
    [
        # Success cases
        pytest.param(
            {"query": "test question"},  # input
            None,  # config
            {"answer": "test response"},  # mock return/side effect
            {"query": "test question"},  # expected chain input
            {"answer": "test response"},  # expected output
            1,  # expected calls
            None,  # expected exception
            id="dict-input-no-config",
        ),
        pytest.param(
            "test question",  # input
            None,  # config
            {"answer": "test response"},  # mock return/side effect
            {"input": "test question"},  # expected chain input
            {"answer": "test response"},  # expected output
            1,  # expected calls
            None,  # expected exception
            id="single-value-input",
        ),
        pytest.param(
            {"query": "test"},  # input
            {"temperature": 0.7},  # config
            {"answer": "test response"},  # mock return/side effect
            {"query": "test"},  # expected chain input
            {"answer": "test response"},  # expected output
            1,  # expected calls
            None,  # expected exception
            id="with-config",
        ),
        # Retry cases
        pytest.param(
            {"query": "test"},  # input
            None,  # config
            [  # mock return/side effect
                Exception("First failure"),
                Exception("Second failure"),
                {"answer": "success"},
            ],
            {"query": "test"},  # expected chain input
            {"answer": "success"},  # expected output
            3,  # expected calls
            None,  # expected exception
            id="retry-success-after-two-failures",
        ),
        pytest.param(
            {"query": "test"},  # input
            None,  # config
            [Exception("Persistent failure")] * 3,  # mock return/side effect
            {"query": "test"},  # expected chain input
            None,  # expected output
            3,  # expected calls
            Exception,  # expected exception
            id="max-retries-exceeded",
        ),
    ],
)
async def test_ainvoke_chain(
    mock_chain,
    input_data: dict[str, Any] | str,
    config: dict[str, Any] | None,
    mock_response: Any,
    expected_chain_input: dict[str, Any],
    expected_output: dict[str, Any] | None,
    expected_calls: int,
    expected_exception: type[Exception] | None,
):
    """Test chain invocations with various inputs, configs, and retry scenarios."""
    # Setup
    if isinstance(mock_response, list):
        mock_chain.ainvoke.side_effect = mock_response
    else:
        mock_chain.ainvoke.return_value = mock_response

    # Execute and Assert
    if expected_exception:
        with pytest.raises(expected_exception):
            await ainvoke_chain(mock_chain, input_data, config=config)
    else:
        result = await ainvoke_chain(mock_chain, input_data, config=config)
        assert result == expected_output

    assert mock_chain.ainvoke.call_count == expected_calls

    # Verify first call arguments
    mock_chain.ainvoke.assert_called_with(input=expected_chain_input, config=config)
