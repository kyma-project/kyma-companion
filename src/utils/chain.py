import logging
from typing import Any

from langchain.schema.runnable import RunnableConfig, RunnableSequence
from tenacity import (
    RetryCallState,
    retry,
    stop_after_attempt,
    wait_incrementing,
)

logger = logging.getLogger(__name__)


def after_log(retry_state: RetryCallState) -> None:
    """Log retry attempts with appropriate log levels.

    Args:
        retry_state (RetryCallState): Current state of the retry operation
    """
    loglevel = logging.INFO if retry_state.attempt_number < 1 else logging.WARNING
    logger.log(
        loglevel,
        "Retrying %s: attempt %s",
        f"{retry_state.fn.__module__}.{retry_state.fn.__name__}",
        retry_state.attempt_number,
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_incrementing(start=2, increment=3),
    after=after_log,
    reraise=True,
)
async def ainvoke_chain(
    chain: RunnableSequence,
    inputs: dict[str, Any] | Any,
    *,
    config: RunnableConfig | None = None,
) -> Any:
    """Invokes a LangChain chain asynchronously.
    Retries the LLM calls if they fail with the provided wait strategy.
    Tries 3 times, waits 2 seconds between attempts, i.e. 2, 5.
    Logs warnings and raises an error.

    Args:
        chain (Chain): The LangChain chain to invoke
        inputs (Union[Dict[str, Any], Any]): Input parameters for the chain. Can be either a dictionary
            of inputs or a single value that will be wrapped in a dict with key "input"
        config (Optional[Dict[str, Any]], optional): Additional configuration for chain execution.
            Defaults to None.

    Returns:
        Any: The chain execution results
    """
    # Convert single value input to dict if needed
    chain_inputs = inputs if isinstance(inputs, dict) else {"input": inputs}

    logger.debug(f"Invoking chain with inputs: {chain_inputs}")

    result = await chain.ainvoke(
        input=chain_inputs,
        config=config,
    )

    logger.debug(f"Chain execution completed. Result: {result}")
    return result
