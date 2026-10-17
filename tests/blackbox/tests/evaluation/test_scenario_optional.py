import pytest
from deepeval.evaluate.types import EvaluationResult, TestResult
from deepeval.test_run.api import MetricData
from evaluation.scenario.enums import TestStatus
from evaluation.scenario.scenario import Expectation, Query, Resource, Scenario, ScenarioList
from pydantic import ValidationError

THRESHOLD = 0.5
HALF_PASSED_RATE = 50.0


def make_scenario(scenario_id: str, status: TestStatus, optional: bool = False, reason: str = "") -> Scenario:
    query = Query(
        user_query="q",
        resource=Resource(kind="Cluster"),
        expectations=[Expectation(name="e", statement="s")],
        test_status=status,
    )
    return Scenario(
        id=scenario_id,
        description="d",
        queries=[query],
        test_status=status,
        optional=optional,
        optional_reason=reason,
    )


def test_scenario_defaults_to_required() -> None:
    scenario = make_scenario("s1", TestStatus.FAILED)
    assert scenario.optional is False
    assert scenario.is_blocking_failure() is True


def test_optional_scenario_requires_reason() -> None:
    with pytest.raises(ValidationError, match="optional_reason"):
        make_scenario("s1", TestStatus.PENDING, optional=True)
    with pytest.raises(ValidationError, match="optional_reason"):
        make_scenario("s1", TestStatus.PENDING, optional=True, reason="   ")


def test_optional_reason_loaded_from_yaml_dict() -> None:
    scenario = Scenario.model_validate(
        {"id": "s1", "description": "d", "optional": True, "optional_reason": "known issue", "queries": []}
    )
    assert scenario.optional is True
    assert scenario.optional_reason == "known issue"


@pytest.mark.parametrize(
    ("scenarios", "expected"),
    [
        pytest.param(
            [make_scenario("a", TestStatus.COMPLETED), make_scenario("b", TestStatus.PASSED)],
            True,
            id="all required scenarios pass",
        ),
        pytest.param(
            [make_scenario("a", TestStatus.COMPLETED), make_scenario("b", TestStatus.FAILED)],
            False,
            id="a required scenario fails",
        ),
        pytest.param(
            [make_scenario("a", TestStatus.COMPLETED), make_scenario("b", TestStatus.FAILED, True, "known")],
            True,
            id="only an optional scenario fails",
        ),
        pytest.param(
            [make_scenario("a", TestStatus.FAILED), make_scenario("b", TestStatus.FAILED, True, "known")],
            False,
            id="required and optional scenarios fail",
        ),
        pytest.param(
            [make_scenario("a", TestStatus.COMPLETED), make_scenario("b", TestStatus.COMPLETED, True, "known")],
            True,
            id="optional scenario passes",
        ),
    ],
)
def test_is_test_passed_ignores_optional_failures(scenarios: list[Scenario], expected: bool) -> None:
    assert ScenarioList(items=scenarios).is_test_passed() is expected


def test_optional_failed_scenario_stays_visible_in_report() -> None:
    scenario_list = ScenarioList(
        items=[
            make_scenario("a", TestStatus.COMPLETED),
            make_scenario("b", TestStatus.FAILED, optional=True, reason="known issue"),
        ]
    )

    assert [s.id for s in scenario_list.optional_failed_scenarios()] == ["b"]

    report = scenario_list.build_full_report()
    counts = report["summary"]["status_counts"]["scenarios"]
    assert counts == {"passed": 1, "failed": 1, "optional_failed": 1}

    optional_detail = next(s for s in report["scenarios"] if s["scenario_id"] == "b")
    assert optional_detail["passed"] is False
    assert optional_detail["status"] == TestStatus.FAILED.value
    assert optional_detail["optional"] is True
    assert optional_detail["optional_reason"] == "known issue"

    required_detail = next(s for s in report["scenarios"] if s["scenario_id"] == "a")
    assert required_detail["optional"] is False


def set_score(scenario: Scenario, score: float) -> None:
    metric = MetricData(name="required_e", threshold=THRESHOLD, success=score >= THRESHOLD, score=score)
    scenario.queries[0].evaluation_result = EvaluationResult(
        test_results=[TestResult(name="t", success=score >= THRESHOLD, metrics_data=[metric], conversational=False)],
        confident_link=None,
        test_run_id=None,
    )


def test_optional_scenario_score_counts_in_success_rate() -> None:
    """The success score stays honest: an optional scenario's score is still part of it."""
    passing = make_scenario("a", TestStatus.COMPLETED)
    set_score(passing, 1.0)
    optional_failed = make_scenario("b", TestStatus.FAILED, optional=True, reason="known issue")
    set_score(optional_failed, 0.0)

    assert ScenarioList(items=[passing, optional_failed]).get_overall_success_rate() == HALF_PASSED_RATE


def test_real_scenario_question_20_is_optional() -> None:
    from pathlib import Path

    import yaml

    path = Path(__file__).parents[2] / "data/test-cases/20_question_kyma_regions/scenario.yml"
    scenario = Scenario.model_validate(yaml.safe_load(path.read_text()))
    assert scenario.id == "test-question-20"
    assert scenario.optional is True
    assert scenario.optional_reason
