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

from agents.common.state import CompanionState, ResourceInformation
from agents.graph import CompanionGraph
from agents.memory.async_redis_checkpointer import AsyncRedisSaver
from utils.config import get_config
from utils.models.factory import ModelFactory, ModelType
from utils.settings import REDIS_DB_NUMBER, REDIS_HOST, REDIS_PASSWORD, REDIS_PORT


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
    return {
        ModelType.GPT4O_MINI: model_factory.create_model(ModelType.GPT4O_MINI),
        ModelType.GPT4O: model_factory.create_model(ModelType.GPT4O),
        ModelType.TEXT_EMBEDDING_3_LARGE: model_factory.create_model(
            ModelType.TEXT_EMBEDDING_3_LARGE
        ),
    }


@pytest.fixture(scope="session")
def evaluator_model(app_models):
    return LangChainOpenAI(app_models[ModelType.GPT4O].llm)


@pytest.fixture(scope="session")
def start_fake_redis():
    server_address = (REDIS_HOST, REDIS_PORT)
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
    memory = AsyncRedisSaver.from_conn_info(
        host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB_NUMBER, password=REDIS_PASSWORD
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
    resource_info = ResourceInformation(
        kind=None,
        api_version=None,
        name=None,
        namespace=None,
    )

    return CompanionState(
        resource_information=resource_info,
        messages=messages,
        next="",
        subtasks=subtasks,
        final_response="",
        error=None,
    )
