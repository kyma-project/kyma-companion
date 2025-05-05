from unittest.mock import MagicMock

import pytest
from langchain_core.embeddings import Embeddings

from services.metrics import CustomMetrics
from services.probes import (
    LLMReadinessProbe,
    get_llm_readiness_probe,
    is_usage_tracker_ready,
)
from utils.models.factory import IModel


class TestLLMReadinessProbe:
    @pytest.mark.parametrize(
        "test_case, model_factory, expected_has_models, expected_are_llms_ready, expected_states",
        [
            (
                "No models",
                MagicMock(return_value={}),
                False,
                False,
                {},
            ),
            (
                "Single ready IModel",
                MagicMock(
                    return_value={
                        "model1": MagicMock(
                            spec=IModel, invoke=MagicMock(return_value=True)
                        )
                    }
                ),
                True,
                True,
                {"model1": True},
            ),
            (
                "Single not ready IEmbeddings",
                MagicMock(
                    return_value={
                        "embedding1": MagicMock(
                            spec=Embeddings, embed_query=MagicMock(return_value=None)
                        )
                    }
                ),
                True,
                False,
                {"embedding1": False},
            ),
            (
                "Mixed readiness models",
                MagicMock(
                    return_value={
                        "model1": MagicMock(
                            spec=IModel, invoke=MagicMock(return_value=True)
                        ),
                        "embedding1": MagicMock(
                            spec=Embeddings, embed_query=MagicMock(return_value=None)
                        ),
                    }
                ),
                True,
                False,
                {"model1": True, "embedding1": False},
            ),
            (
                "Factory with exception",
                MagicMock(side_effect=Exception("Some error")),
                False,
                False,
                {},
            ),
        ],
    )
    def test_llm_readiness_probe(
        self,
        test_case,
        model_factory,
        expected_has_models,
        expected_are_llms_ready,
        expected_states,
    ):
        """
        Test the LLMReadinessProbe class with various combinations of models.

        This test verifies:
        - The `has_models` method correctly identifies if models are available.
        - The `are_llms_ready` method correctly determines the readiness of all models.
        - The `get_llms_states` method returns the correct readiness states for all models.
        """
        LLMReadinessProbe()._reset_for_tests()

        # When:
        probe = LLMReadinessProbe(model_factory)

        # Then:
        assert probe.has_models() == expected_has_models, test_case
        assert probe.are_llms_ready() == expected_are_llms_ready, test_case
        assert probe.get_llms_states() == expected_states, test_case

        # Clean up by resetting the instance:
        LLMReadinessProbe()._reset_for_tests()

    def test_reset_for_tests(self):
        probe1 = get_llm_readiness_probe()
        probe1._reset_for_tests()
        probe2 = get_llm_readiness_probe()
        assert probe1 != probe2


@pytest.mark.parametrize(
    "test_case, failure_count, expected",
    [
        ("No metric value set yet", None, True),
        ("Metric is zero", 0.0, True),
        ("Metric is nonzero", 1.0, False),
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

    # Clean up:
    metrics._reset_for_tests()
