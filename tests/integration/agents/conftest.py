from threading import Thread

import pytest
from deepeval.models.base_model import DeepEvalBaseLLM
from fakeredis import TcpFakeServer

from agents.graph import CompanionGraph
from agents.memory.redis_checkpointer import RedisSaver, initialize_async_pool
from utils.models import LLM, ModelFactory  # noqa: E402
from utils.settings import REDIS_HOST, REDIS_PORT, REDIS_URL


class LangChainOpenAI(DeepEvalBaseLLM):
    def __init__(self, model):
        self.model = model

    def load_model(self):
        return self.model

    # @observe()
    def generate(self, prompt: str) -> str:
        chat_model = self.load_model()
        # print("prompt: " + prompt)
        res = chat_model.invoke(prompt).content
        return res

    # @observe()
    async def a_generate(self, prompt: str) -> str:
        chat_model = self.load_model()
        # print("prompt: " + prompt)
        res = await chat_model.ainvoke(prompt)
        return res.content

    def get_model_name(self):
        return "Custom Azure OpenAI Model"


@pytest.fixture(scope="session")
def app_models():
    model_factory = ModelFactory()
    model = model_factory.create_model(LLM.GPT4O)
    model_mini = model_factory.create_model(LLM.GPT4O_MINI)
    return {
        LLM.GPT4O_MINI: model_mini,
        LLM.GPT4O: model,
    }


@pytest.fixture(scope="session")
def evaluator_model(app_models):
    return LangChainOpenAI(app_models[LLM.GPT4O].llm)


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
def kyma_graph(app_models, start_fake_redis):
    memory = RedisSaver(async_connection=initialize_async_pool(url=REDIS_URL))
    graph = CompanionGraph(app_models, memory)
    return graph
