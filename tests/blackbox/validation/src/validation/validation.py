import asyncio
from typing import List

from prettytable import PrettyTable

from utils.models import Model
from validation.scenario_mock_responses import ScenarioMockResponses
from validation.validator import ModelValidator, Validator


class Validation:
    validators: List[Validator]
    _model_scores: dict[str, float] = {}

    def __init__(self, models: List[Model], data: List[ScenarioMockResponses]):
        self.validators = [ModelValidator(model, data) for model in models]

    async def validate(self):
        tasks = [validator.run() for validator in self.validators]
        await asyncio.gather(*tasks)

    @property
    def model_scores(self) -> dict[str, float]:
        self.validators.sort(key=lambda x: x.score, reverse=True)
        for validator in self.validators:
            self._model_scores[validator.model.name] = validator.score
        return self._model_scores

    def get_best_rated_model(self) -> str:
        return max(self.model_scores, key=self.model_scores.get)

    def print_report(self):
        table = PrettyTable()
        table.field_names = ["Model", "Score", "Short Report"]
        for validator in self.validators:
            table.add_row([validator.model.name, validator.score, validator.report])
        print(table)

    def print_full_report(self):
        table = PrettyTable()
        table.field_names = ["Model", "Score", "Full Report"]
        for validator in self.validators:
            table.add_row([validator.model.name, validator.score, validator.full_report])
        print(table)
