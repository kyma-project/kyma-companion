import os
from collections.abc import Sequence
from threading import Thread

import pytest
from deepeval.metrics import AnswerRelevancyMetric, GEval
from deepeval.models.base_model import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCaseParams
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
from utils.models.contants import GPT_41_NANO_MODEL_NAME
from utils.models.factory import ModelFactory
from utils.settings import (
    MAIN_EMBEDDING_MODEL_NAME,
    MAIN_MODEL_MINI_NAME,
    MAIN_MODEL_NAME,
    REDIS_DB_NUMBER,
    REDIS_HOST,
    REDIS_PASSWORD,
)

# the default port for redis is already in use by the system, so we use a different port for integration tests.
integration_test_redis_port = 60379
integration_test_mini_evaluator_model_name = "gpt-4.1-mini"
integration_test_main_evaluator_model_name = "gpt-4.1"


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


@pytest.fixture(scope="session")
def init_config():
    return get_config()


@pytest.fixture(scope="session")
def app_models(init_config):
    model_factory = ModelFactory(config=init_config)
    models = {
        MAIN_MODEL_MINI_NAME: model_factory.create_model(MAIN_MODEL_MINI_NAME),
        MAIN_MODEL_NAME: model_factory.create_model(MAIN_MODEL_NAME),
        GPT_41_NANO_MODEL_NAME: model_factory.create_model(GPT_41_NANO_MODEL_NAME),
        MAIN_EMBEDDING_MODEL_NAME: model_factory.create_model(
            MAIN_EMBEDDING_MODEL_NAME
        ),
    }

    if integration_test_mini_evaluator_model_name not in models:
        models[integration_test_mini_evaluator_model_name] = model_factory.create_model(
            integration_test_mini_evaluator_model_name
        )

    if integration_test_main_evaluator_model_name not in models:
        models[integration_test_main_evaluator_model_name] = model_factory.create_model(
            integration_test_main_evaluator_model_name
        )

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
    os.environ["REDIS_HOST"] = str(integration_test_redis_port)
    server_address = (REDIS_HOST, integration_test_redis_port)
    server = TcpFakeServer(server_address)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()

    # Yield control back to the tests
    yield server

    # Teardown: Stop the server after all tests are finished
    server.shutdown()
    server.server_close()
    t.join(timeout=5)
    if "REDIS_HOST" in os.environ:
        del os.environ["REDIS_HOST"]


@pytest.fixture(scope="session")
def companion_graph(app_models, start_fake_redis):
    memory = AsyncRedisSaver.from_conn_info(
        host=REDIS_HOST,
        port=integration_test_redis_port,
        db=REDIS_DB_NUMBER,
        password=REDIS_PASSWORD,
    )
    graph = CompanionGraph(app_models, memory)
    return graph


@pytest.fixture
def answer_relevancy_metric(evaluator_model):
    return AnswerRelevancyMetric(
        threshold=0.6, model=evaluator_model, include_reason=True
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
    last_human_message = next(
        (msg for msg in reversed(messages) if isinstance(msg, HumanMessage)), None
    )

    # if no human message is found, use the last message's content.
    user_input = UserInput(
        query=(
            last_human_message.content if last_human_message else messages[-1].content
        ),
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
