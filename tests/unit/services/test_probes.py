from unittest.mock import MagicMock

import pytest
from langchain_core.embeddings import Embeddings

from services.probes import (
    LLMReadinessProbe,
    UsageTrackerProbe,
    get_llm_readiness_probe,
    get_usage_tracke_probe,
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


class TestUsageTrackerProbe:
    def test_increase_failure_count(self):
        """
        Test that the `increase_failure_count` method increments the failure count by 1.
        """
        # Given:
        expected_count = 1
        probe = get_usage_tracke_probe()

        # When:
        probe.increase_failure_count()

        # Then:
        assert probe.get_failure_count() == expected_count

        # Clean up by resetting the instance:
        probe._reset_for_tests()

    def test_reset_failure_count(self):
        """
        Test that the `reset_failure_count` method resets the failure count to 0.
        """
        # Given:
        expected_count = 0
        probe = UsageTrackerProbe(100, 100)

        # When:
        probe.reset_failure_count()

        # Then:
        assert probe.get_failure_count() == expected_count

        # Clean up by resetting the instance:
        probe._reset_for_tests()

    @pytest.mark.parametrize(
        "test_case, threshold, count, expected_healthiness",
        [
            ("count higher than threshold", 1, 2, False),
            ("count lower than threshold", 2, 1, True),
            ("count equal threshold", 1, 1, False),
        ],
    )
    def test_is_healthy(
        self,
        test_case,
        threshold,
        count,
        expected_healthiness,
    ):
        """
        Test the `is_healthy` method with various threshold and count values.

        Verifies that the method correctly determines healthiness based on the
        failure count and threshold.
        """
        # Given:
        probe = UsageTrackerProbe(threshold, count)

        # When:
        actual_healthiness = probe.is_healthy()

        # Then:
        assert actual_healthiness == expected_healthiness, test_case

        # Clean up by resetting the instance:
        probe._reset_for_tests()
