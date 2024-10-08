from deepeval.models.base_model import DeepEvalBaseLLM
from dotenv import load_dotenv

load_dotenv()

from agents.supervisor.agent import SupervisorAgent  # noqa: E402
from utils.models import LLM, ModelFactory  # noqa: E402

supervisor_agent: SupervisorAgent
model_factory = ModelFactory()


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


model = model_factory.create_model(LLM.GPT4O)
custom_llm = LangChainOpenAI(model.llm)

model_mini = model_factory.create_model(LLM.GPT4O_MINI)
custom_llm_mini = LangChainOpenAI(model_mini.llm)
