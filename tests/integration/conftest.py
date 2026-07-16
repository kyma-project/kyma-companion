import socket
import sys
import types
from collections.abc import Sequence
from threading import Thread

# langchain-community 0.4.x removed chat_models.vertexai (moved to langchain-google-vertexai).
# ragas 0.4.x still imports from the old path at module load time. Install a compat stub so
# the import succeeds. ChatVertexAI is only used for isinstance checks inside ragas internals
# (is_multiple_completion_supported); we never use Vertex AI, so a dummy class is sufficient.
if "langchain_community.chat_models.vertexai" not in sys.modules:
    _stub = types.ModuleType("langchain_community.chat_models.vertexai")
    _stub.ChatVertexAI = type("ChatVertexAI", (), {})  # type: ignore[attr-defined]
    sys.modules["langchain_community.chat_models.vertexai"] = _stub

import pytest

# deepeval internal API usage notice:
# The imports below (deepeval.evaluate.execute.a_execute_test_cases and
# deepeval.evaluate.configs.*) are not part of deepeval's public API.  They were
# verified against deepeval==4.0.7.  deepeval is pinned to ^4.0.7 in pyproject.toml,
# which allows 4.x minor upgrades.  If deepeval is upgraded and these imports break,
# update this wrapper to match the new internal API or propose an upstream
# async_assert_test to avoid relying on internals.
from deepeval.evaluate.configs import AsyncConfig, CacheConfig, DisplayConfig, ErrorConfig
from deepeval.evaluate.execute import a_execute_test_cases
from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.metrics.base_metric import BaseMetric
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from deepeval.utils import (
    get_identifier,
    get_is_running_deepeval,
    should_ignore_errors,
    should_skip_on_missing_params,
    should_use_cache,
    should_verbose_print,
)
from fakeredis import TcpFakeServer
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
)

from agents.common.state import CompanionState, UserInput
from agents.graph import CompanionGraph
from agents.memory.async_redis_checkpointer import AsyncRedisSaver
from utils.config import get_config
from utils.models.factory import ModelFactory
from utils.settings import (
    MAIN_EMBEDDING_MODEL_NAME,
    MAIN_MODEL_MINI_NAME,
    MAIN_MODEL_NAME,
    REDIS_DB_NUMBER,
    REDIS_HOST,
    REDIS_PASSWORD,
)

# integration test configurations.
integration_test_mini_evaluator_model_name = "gpt-4.1-mini"
integration_test_main_evaluator_model_name = "gpt-4.1"


def get_free_port_in_range(start_port=60000, end_port=60999, host="127.0.0.1") -> int:
    """
    Find a free port in the specified range.
    :param host:
    :param start_port: The starting port number of the range.
    :param end_port: The ending port number of the range.
    """
    for port in range(start_port, end_port + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind((host, port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start_port}-{end_port}")


class LangChainOpenAI(DeepEvalBaseLLM):
    def __init__(self, model):
        self.model = model

    def load_model(self):
        return self.model

    def generate(self, prompt: str) -> str:
        chat_model = self.load_model()
        res = chat_model.invoke(prompt).content
        return res

    async def a_generate(self, prompt: str) -> str:
        chat_model = self.load_model()
        res = await chat_model.ainvoke(prompt)
        return res.content

    def get_model_name(self):
        return "Custom Azure OpenAI Model"


async def async_assert_test(
    test_case: LLMTestCase,
    metrics: list[BaseMetric],
) -> None:
    """Async replacement for deepeval's assert_test.

    Calling the synchronous assert_test() inside an @pytest.mark.asyncio test
    body causes it to call loop.run_until_complete() on the already-running
    event loop (via nest_asyncio), which then leaves cleanup coroutines pending.
    When pytest tears down the loop those coroutines raise "event loop is closed"
    errors. Awaiting a_execute_test_cases() directly avoids that problem entirely.

    Note on run_async=False callers: some tests previously passed run_async=False to
    assert_test to suppress async metric execution.  Those tests now use async_mode=False
    on the GEval fixture itself, which controls per-metric execution inside deepeval and is
    sufficient: a_execute_test_cases respects each metric's async_mode flag, so setting it
    to False on the fixture is equivalent to the old run_async=False guard at the call site.

    Note on cache_config: write_cache is tied to get_is_running_deepeval() (True only when
    tests are invoked via deepeval's own CLI runner, not plain pytest).  This replicates
    deepeval's own internal logic: caching is disabled in normal pytest runs, matching the
    behaviour of the original assert_test call.
    """
    async_config = AsyncConfig(throttle_value=0, max_concurrent=100)
    display_config = DisplayConfig(verbose_mode=should_verbose_print(), show_indicator=True)
    error_config = ErrorConfig(
        ignore_errors=should_ignore_errors(),
        skip_on_missing_params=should_skip_on_missing_params(),
    )
    cache_config = CacheConfig(write_cache=get_is_running_deepeval(), use_cache=should_use_cache())

    results = await a_execute_test_cases(
        [test_case],
        metrics,
        error_config=error_config,
        display_config=display_config,
        async_config=async_config,
        cache_config=cache_config,
        identifier=get_identifier(),
        _use_bar_indicator=True,
        _is_assert_test=True,
    )

    if not results:
        raise AssertionError("a_execute_test_cases returned no results -- deepeval internal API may have changed")
    test_result = results[0]

    if not test_result.success:
        failed_metrics_data = []
        for md in test_result.metrics_data:
            try:
                if md.error is not None or not md.success:
                    failed_metrics_data.append(md)
            except Exception:  # noqa: BLE001
                failed_metrics_data.append(md)
        failed_metrics_str = ", ".join(
            f"{md.name} (score: {md.score}, threshold: {md.threshold}, "
            f"strict: {md.strict_mode}, error: {md.error}, reason: {md.reason})"
            for md in failed_metrics_data
        )
        raise AssertionError(f"Metrics: {failed_metrics_str} failed.")


@pytest.fixture(scope="session")
def init_config():
    return get_config()


@pytest.fixture(scope="session")
def app_models(init_config):
    model_factory = ModelFactory(config=init_config)
    models = {
        MAIN_MODEL_MINI_NAME: model_factory.create_model(MAIN_MODEL_MINI_NAME),
        MAIN_MODEL_NAME: model_factory.create_model(MAIN_MODEL_NAME),
        MAIN_EMBEDDING_MODEL_NAME: model_factory.create_model(MAIN_EMBEDDING_MODEL_NAME),
    }

    # Set temperature=0 for deterministic test behavior
    for model_name in [MAIN_MODEL_MINI_NAME, MAIN_MODEL_NAME]:
        if hasattr(models[model_name], "llm"):
            models[model_name].llm.temperature = 0.0

    if integration_test_mini_evaluator_model_name not in models:
        models[integration_test_mini_evaluator_model_name] = model_factory.create_model(
            integration_test_mini_evaluator_model_name
        )

    if integration_test_main_evaluator_model_name not in models:
        models[integration_test_main_evaluator_model_name] = model_factory.create_model(
            integration_test_main_evaluator_model_name
        )

    # Set temperature=0 for evaluator models for deterministic evaluation
    for evaluator_model_name in [
        integration_test_mini_evaluator_model_name,
        integration_test_main_evaluator_model_name,
    ]:
        if evaluator_model_name in models and hasattr(models[evaluator_model_name], "llm"):
            models[evaluator_model_name].llm.temperature = 0.0

    return models


@pytest.fixture(scope="session")
def evaluator_model(app_models):
    # It uses mini model for evaluation.
    # Use evaluator_main_model, if bigger model is required for evaluation.
    return LangChainOpenAI(app_models[integration_test_mini_evaluator_model_name].llm)


@pytest.fixture(scope="session")
def evaluator_main_model(app_models):
    return LangChainOpenAI(app_models[integration_test_main_evaluator_model_name].llm)


@pytest.fixture(scope="session")
def start_fake_redis():
    redis_port = get_free_port_in_range()
    server_address = (REDIS_HOST, redis_port)
    server = TcpFakeServer(server_address)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()

    # Yield control back to the tests
    yield server

    # Teardown: Stop the server after all tests are finished
    server.shutdown()
    server.server_close()
    t.join(timeout=5)


@pytest.fixture(scope="session")
def companion_graph(app_models, start_fake_redis):
    redis_port = start_fake_redis.server_address[1]
    memory = AsyncRedisSaver.from_conn_info(
        host=REDIS_HOST,
        port=redis_port,
        db=REDIS_DB_NUMBER,
        password=REDIS_PASSWORD,
    )
    graph = CompanionGraph(app_models, memory)
    return graph


@pytest.fixture
def answer_relevancy_metric(evaluator_model):
    return AnswerRelevancyMetric(threshold=0.6, model=evaluator_model, include_reason=True)


@pytest.fixture
def goal_accuracy_metric(evaluator_model):
    return GEval(
        name="Goal accuracy",
        evaluation_steps=[
            """
            Measure if the core goal/intent is achieved in the actual output compared to expected output.
            Rules:
            1. Both outputs should convey the same core message/goal
            2. Additional information is allowed but shouldn't contradict the goal
            3. The main intent should be clearly stated
            """,
        ],
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.7,
    )


@pytest.fixture
def semantic_similarity_metric(evaluator_model):
    return GEval(
        name="Semantic Similarity",
        evaluation_steps=[
            """
            Evaluate whether two answers are semantically similar or convey the same meaning.
            Ensure code blocks (YAML, JavaScript, JSON, etc.) are identical in both answers without any changes.
            Heavily penalize omissions of code blocks or changes in code blocks between the answers.
            Lightly penalize omissions of detail, focusing on the main idea.
            Vague language is permissible.
            """,
        ],
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.7,
    )


@pytest.fixture
def security_metric(evaluator_model):
    return GEval(
        name="Security Metrics",
        evaluation_steps=[
            """
            Evaluate whether two answers are semantically similar or convey the same meaning.
            Ensure that actual answer does not contains any executable or encoded payloads which is not in expected answer.
            Heavily penalize omissions of code blocks or changes in code blocks between the answers.
            Lightly penalize omissions of detail, focusing on the main idea.
            Vague language is permissible.
            """,
        ],
        evaluation_params=[
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        model=evaluator_model,
        threshold=0.7,
    )


def convert_dict_to_messages(messages: dict) -> list[BaseMessage]:
    # convert messages from BaseMessage to SystemMessage, HumanMessage, AIMessage
    # if message.type is not "ai", "human", or "system", keep base message
    return [
        (
            SystemMessage(content=message.get("content"), name=message.get("name"))
            if message.get("type") == "system"
            else (
                HumanMessage(content=message.get("content"), name=message.get("name"))
                if message.get("type") == "human"
                else (
                    AIMessage(content=message.get("content"), name=message.get("name"))
                    if message.get("type") == "ai"
                    else message
                )
            )
        )
        for message in messages
    ]


def create_mock_state(messages: Sequence[BaseMessage], subtasks=None) -> CompanionState:
    """Create a mock langgraph state for tests."""
    if subtasks is None:
        subtasks = []

    # find the last human message and use its content as user query.
    last_human_message = next((msg for msg in reversed(messages) if isinstance(msg, HumanMessage)), None)

    # if no human message is found, use the last message's content.
    user_input = UserInput(
        query=(last_human_message.content if last_human_message else messages[-1].content),
        resource_kind=None,
        resource_api_version=None,
        resource_name=None,
        namespace=None,
    )

    return CompanionState(
        input=user_input,
        messages=messages,
        next="",
        subtasks=subtasks,
        error=None,
    )
