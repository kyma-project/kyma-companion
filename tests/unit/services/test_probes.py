from unittest.mock import MagicMock

import pytest
from langchain_core.embeddings import Embeddings

from services.metrics import CustomMetrics
from services.probes import (
    LLMReadinessProbe,
    is_usage_tracker_ready,
)
from utils.models.factory import IModel


@pytest.fixture(autouse=True)
def reset_singleton():
    """
    Fixture to reset the singleton instance before each test.
    """
    LLMReadinessProbe._instances = {}


@pytest.mark.parametrize(
    "test_case, models, expected_has_models, expected_are_llms_ready, expected_states",
    [
        (
            "No models",
            {},
            False,
            False,
            {},
        ),
        (
            "Single ready IModel",
            {"model1": MagicMock(spec=IModel, invoke=MagicMock(return_value=True))},
            True,
            True,
            {"model1": True},
        ),
        (
            "Single not ready IEmbeddings",
            {
                "embedding1": MagicMock(
                    spec=Embeddings, embed_query=MagicMock(return_value=[])
                )
            },
            True,
            False,
            {"embedding1": False},
        ),
        (
            "Mixed readiness models",
            {
                "model1": MagicMock(spec=IModel, invoke=MagicMock(return_value=True)),
                "embedding1": MagicMock(
                    spec=Embeddings, embed_query=MagicMock(return_value=[])
                ),
            },
            True,
            False,
            {"model1": True, "embedding1": False},
        ),
    ],
)
def test_llm_readiness_probe(
    test_case, models, expected_has_models, expected_are_llms_ready, expected_states
):
    """
    Test the LLMReadinessProbe class with various combinations of models.

    This test verifies:
    - The `has_models` method correctly identifies if models are available.
    - The `are_llms_ready` method correctly determines the readiness of all models.
    - The `get_llms_states` method returns the correct readiness states for all models.
    """
    # When:
    probe = LLMReadinessProbe(models=models)

    # Then:
    assert probe.has_models() == expected_has_models, test_case
    assert probe.are_llms_ready() == expected_are_llms_ready, test_case
    assert probe.get_llms_states() == expected_states, test_case


@pytest.fixture(autouse=True)
def reset_custom_metrics_singleton():
    CustomMetrics._instance = None
    yield
    CustomMetrics._instance = None


@pytest.mark.parametrize(
    "test_case, failure_count, expected",
    [
        ("No metric value set yet", None, True),
        ("Metric is zero", 0.0, True),
        ("# Metric is nonzero", 1.0, False),
    ],
)
def test_is_usage_tracker_ready_with_real_custom_metrics(
    test_case, failure_count, expected
):
    # Given:
    metrics = CustomMetrics()
    if failure_count is not None:
        for _ in range(int(failure_count)):
            metrics.usage_tracker_publish_failure_count.inc()

    # When:
    result = is_usage_tracker_ready(metrics)

    # Then:
    assert result == expected, test_case
