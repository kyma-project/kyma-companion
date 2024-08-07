"""CalibrationAnswer is a class that contains the information of a calibration answer.
A calibration answer is a fake answer that is used to test how a given model can 
evaluate an answer against the defined expectations."""

from typing import List

from pydantic import BaseModel

from src.models.validation.wanted_result import WantedResultList


class MockResponse(BaseModel):
    """CalibrationAnswer is a class that contains the information of a calibration answer."""

    mock_response_id: str
    mock_response_content: str
    wanted_results: WantedResultList

    def add_actual_result(self, expectation_id: str, result: bool) -> None:
        """Adds an actual result to the calibration answer."""
        self.wanted_results.set_actual_result(expectation_id, result)

    def has_actual_result(self, expectation_id: str) -> bool:
        """Returns true if the calibration answer has an
        actual result for the given expectation ID."""
        return self.wanted_results.has_actual_result(expectation_id)

    def does_match(self, expectation_id: str) -> bool:
        """Returns true if the calibration answer matches the expectation."""
        return self.wanted_results.does_match(expectation_id)


class MockResponseList(BaseModel):
    """CalibrationAnswerDict is a dictionary that contains calibration answers."""

    items: List[MockResponse]

    def has_actual_result(self, mock_response_id: str, expectation_id: str) -> bool:
        """Returns true if the calibration answer has actual results
        for the given expectation ID."""
        for mock_resonse in self.items:
            if mock_resonse.mock_response_id == mock_response_id:
                return mock_resonse.has_actual_result(expectation_id)
        raise ValueError(
            f"Validation answer ID {mock_response_id} not found in validation answers."
        )

    def add_actual_result(
        self, calibration_answer_id: str, expectation_id: str, result: bool
    ) -> None:
        """Adds an actual result to the calibration answer."""
        for calibration_answer in self.items:
            if calibration_answer.mock_response_id == calibration_answer_id:
                calibration_answer.add_actual_result(expectation_id, result)
                return
        raise ValueError(
            f"Calibration answer ID {calibration_answer_id} not found in calibration answers."
        )

    def get_mock_response(self, mock_response_id: str) -> MockResponse:
        """Get the calibration answer by its ID."""
        for mock_response in self.items:
            if mock_response.mock_response_id == mock_response_id:
                return mock_response
        raise ValueError(
            f"Calibration answer ID {mock_response_id} not found in calibration answers."
        )
