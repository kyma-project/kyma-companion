from typing import List

from gen_ai_hub.proxy.langchain import ChatOpenAI

from validation.scenario_mock_responses import ScenarioMockResponses
from validation.validator import ModelValidator

COMPANION_FOLDER = "/Users/I504380/Go/src/github.com/muralov/kyma-companion"


class Validation:
    validators: List[ModelValidator]
    _model_scores: dict[str, float] = {}

    def __init__(self, llms: List[ChatOpenAI], data: List[ScenarioMockResponses]):
        self.validators = [ModelValidator(llm, data) for llm in llms]

    # TODO: this should start a new coroutine per model
    def validate(self):
        for validator in self.validators:
            score = validator.run()
            self._model_scores[validator.model.model_name] = score

    @property
    def model_scores(self):
        return self._model_scores
