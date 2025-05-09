from typing import Protocol

from deepeval.models import DeepEvalBaseLLM
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI
from langchain.prompts import PromptTemplate
from deepeval.evaluate import EvaluationResult
from deepeval.metrics import GEval
from deepeval.test_case import LLMTestCaseParams, LLMTestCase
from deepeval import evaluate
from evaluation.scenario.scenario import Scenario

TEMPLATE = PromptTemplate(
    template="""Please only answer with one word, YES or NO:
    Does the following statement apply for the following text? 
    The fact: 'The text {expectation}'. 
    The text: '{response}'""",
    input_variables=["expectation", "response"],
)


class IValidator(Protocol):
    def get_deepeval_evaluate(self, scenario: Scenario) -> EvaluationResult: ...


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


class ChatOpenAIValidator:
    model: LangChainOpenAI

    def __init__(self, name: str, temperature: str, deployment_id: str) -> None:
        model = ChatOpenAI(
            model_name=name,
            temperature=temperature,
            deployment_id=deployment_id,
        )
        self.model = LangChainOpenAI(model=model)


    def get_deepeval_evaluate(self, scenario: Scenario) -> EvaluationResult:
        evaluation_metrics = []
        for i, expectation in enumerate(scenario.expectations):
            new_metric = GEval(
                name=expectation.name,
                model=self.model,
                threshold=expectation.threshold,
                # criteria=expectation,
                # NOTE: you can only provide either criteria or evaluation_steps, and not both
                # TODO: Decide whether to use criteria or evaluation_steps.
                evaluation_steps=[expectation.statement],
                evaluation_params=[LLMTestCaseParams.INPUT, LLMTestCaseParams.ACTUAL_OUTPUT],
                async_mode=False,
                verbose_mode=False,
            )
            # add the new metric to the list.
            evaluation_metrics.append(new_metric)

        test_case = LLMTestCase(
            input=scenario.user_query,
            actual_output=scenario.actual_response,
        )

        result =  evaluate(
            test_cases=[test_case],
            metrics=evaluation_metrics,
            run_async=False,
            # verbose_mode=False,
            # show_indicator=False,
            # print_results=False,
            # write_cache=False,
        )
        if len(result.test_results) == 0:
            raise ValueError("No test results found.")
        return result
