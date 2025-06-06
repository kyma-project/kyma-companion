from typing import Any, Protocol

from deepeval import evaluate
from deepeval.evaluate import AsyncConfig, CacheConfig, DisplayConfig
from deepeval.evaluate.types import EvaluationResult
from deepeval.metrics import BaseMetric, GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from gen_ai_hub.proxy.langchain.openai import ChatOpenAI

from evaluation.scenario.scenario import Query


class IValidator(Protocol):
    """Interface for the validator."""

    def get_deepeval_evaluate(self, query: Query) -> EvaluationResult:
        """Evaluate the query using the model and expectations."""
        ...


class LangChainOpenAI(DeepEvalBaseLLM):
    """Inherited from DeepEvalBaseLLM to use LangChain OpenAI model."""

    def __init__(self, model: Any) -> None:
        self.model = model

    def load_model(self) -> Any:
        """Loads the model."""
        return self.model

    def generate(self, prompt: str) -> str:
        """Generates a response from the model."""
        chat_model = self.load_model()
        res = chat_model.invoke(prompt).content
        return str(res)

    async def a_generate(self, prompt: str) -> str:
        """Asynchronously generates a response from the model."""
        chat_model = self.load_model()
        res = await chat_model.ainvoke(prompt)
        return str(res.content)

    def get_model_name(self) -> str:
        """Returns the model name."""
        return "Custom Azure OpenAI Model"


class ChatOpenAIValidator:
    """Validator for ChatOpenAI model."""

    model: LangChainOpenAI

    def __init__(self, name: str, temperature: str, deployment_id: str) -> None:
        model = ChatOpenAI(
            model_name=name,
            temperature=temperature,
            deployment_id=deployment_id,
        )
        self.model = LangChainOpenAI(model=model)

    def get_deepeval_evaluate(self, query: Query) -> EvaluationResult:
        """Evaluate the query using the model and expectations."""
        evaluation_metrics: list[BaseMetric] = []
        for expectation in query.expectations:
            # create a new metric for each expectation.
            new_metric = GEval(
                name=expectation.get_deepeval_metric_name(),
                model=self.model,
                threshold=expectation.threshold,
                evaluation_steps=[expectation.statement],
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                ],
                async_mode=False,
                verbose_mode=False,
            )
            # add the new metric to the list.
            evaluation_metrics.append(new_metric)

        # define the test case.
        test_case = LLMTestCase(
            input=query.user_query,
            actual_output=query.actual_response,
        )

        result = evaluate(
            test_cases=[test_case],
            metrics=evaluation_metrics,
            async_config=AsyncConfig(run_async=False),
            display_config=DisplayConfig(show_indicator=False, print_results=False),
            cache_config=CacheConfig(write_cache=False),
        )
        if len(result.test_results) == 0:
            raise ValueError("No test results found.")
        return result
