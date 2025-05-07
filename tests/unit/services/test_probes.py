from unittest.mock import MagicMock

import pytest
from langchain_core.embeddings import Embeddings

from services.probes import (
    LLMProbe,
    UsageTrackerProbe,
    get_llm_probe,
    get_usage_tracker_probe,
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
        LLMProbe()._reset_for_tests()

        # When:
        probe = LLMProbe(model_factory)

        # Then:
        assert probe.has_models() == expected_has_models, test_case
        assert probe.are_llms_ready() == expected_are_llms_ready, test_case
        assert probe.get_llms_states() == expected_states, test_case

        # Clean up by resetting the instance:
        LLMProbe()._reset_for_tests()

    def test_llm_readiness_probe_model_tested_once(self):
        LLMProbe()._reset_for_tests()

        # Given:

        # We need to bouild our own mock model that we can assert and we need a mock model factory to return it, as an arg for LLMProbe().
        model_name = "foo"
        model_state = True
        model = MagicMock(spec=IModel, invoke=MagicMock(return_value=model_state))

        def mock_model_factory() -> dict[str, IModel | Embeddings]:
            return {model_name: model}

        probe = LLMProbe(mock_model_factory)

        # When:
        overall_state = probe.are_llms_ready()
        # The only model we pass always reports, that it is ready, so the overall state should be ready.
        assert overall_state == model_state
        # Check if the model we handed over to the probe has a state.
        assert model_name in probe._model_states, "the model should have a state"
        # Check that the state is "True".
        assert (
            probe._model_states.get(model_name) == model_state
        ), "the model state should be 'True'"

        overall_state = probe.are_llms_ready()
        # The overall state should still be True.
        assert overall_state == model_state
        # The state of the specific model should still be there.
        assert model_name in probe._model_states, "the model should have a state"
        # The state of the specific model should still be True.
        assert (
            probe._model_states.get(model_name) == model_state
        ), "the model state should be 'True'"
        # Because the model state should have been set to True in the first call of
        # are_llms_ready, the second call should not have triggered a second call of
        # the models invoke method.
        model.invoke.assert_called_once()

        LLMProbe()._reset_for_tests()

    def test_reset_for_tests(self):
        probe1 = get_llm_probe()
        probe1._reset_for_tests()
        probe2 = get_llm_probe()
        assert probe1 != probe2


class TestUsageTrackerProbe:
    def test_increase_failure_count(self):
        """
        Test that the `increase_failure_count` method increments the failure count by 1.
        """
        # Given:
        expected_count = 1
        probe = get_usage_tracker_probe()

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
