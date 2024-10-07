import asyncio
from typing import Protocol

from prettytable import PrettyTable

from validation.scenario_mock_responses import MockResponse, ValidationScenario
from validation.utils.models import Model
from validation.validator import ModelValidator, Validator


class Validation(Protocol):
    async def validate(self) -> None: ...

    @property
    def model_scores(self) -> dict[str, float]: ...

    def get_best_rated_model(self) -> str: ...

    def print_report(self) -> None: ...

    def print_full_report(self) -> None: ...


class ModelValidation:
    validators: list[Validator]
    _model_scores: dict[str, float] = {}

    def __init__(self, models: list[Model], vaidation_scenarios: list[ValidationScenario]):
        self.validators = [ModelValidator(model, vaidation_scenarios) for model in models]

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


def create_validation(models: list[Model], validation_scenarios: list[ValidationScenario]) -> Validation:
    return ModelValidation(models, validation_scenarios)
