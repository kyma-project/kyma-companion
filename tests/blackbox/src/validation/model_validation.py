import asyncio
from typing import Protocol

from prettytable import PrettyTable

from validation.scenario_mock_responses import ValidationScenario
from validation.utils.models import Model
from validation.validator import ModelValidator, Validator


class Validation(Protocol):
    async def validate(self) -> None: ...

    @property
    def model_scores(self) -> dict[str, float]: ...

    def print_results(self) -> None: ...

    def print_full_report(self) -> None: ...


class ModelValidation:
    validators: list[Validator]
    _model_scores: dict[str, float] = {}

    def __init__(
        self, models: list[Model], vaidation_scenarios: list[ValidationScenario]
    ):
        self.validators = [
            ModelValidator(model, vaidation_scenarios) for model in models
        ]

    async def validate(self):
        tasks = [validator.run() for validator in self.validators]
        await asyncio.gather(*tasks)

    @property
    def model_scores(self) -> dict[str, float]:
        self.validators.sort(key=lambda x: x.score, reverse=True)
        for validator in self.validators:
            self._model_scores[validator.model.name] = validator.score
        return self._model_scores

    def print_results(self):
        table = PrettyTable()
        table.field_names = ["Model", "Score", "Relative"]
        for validator in self.validators:
            score_field = f"{validator.score}/{validator.max_score}"
            relative_field = f"{validator.score / validator.max_score * 100:.2f}%"
            table.add_row([validator.model.name, score_field, relative_field])
        print(table)

    def print_full_report(self):
        for validator in self.validators:
            print(validator.full_report)
        self.print_results()


def create_validation(
    models: list[Model], validation_scenarios: list[ValidationScenario]
) -> Validation:
    return ModelValidation(models, validation_scenarios)
