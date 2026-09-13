import pytest

from utils.models.thinking import (
    get_anthropic_thinking_fields,
    get_openai_reasoning_effort,
    supports_openai_reasoning,
)
from utils.settings import ThinkingEffort


class TestSupportsOpenAIReasoning:
    """Test suite for supports_openai_reasoning."""

    @pytest.mark.parametrize(
        ("model_name", "expected"),
        [
            ("gpt-5", True),
            ("gpt-5-mini", True),
            ("gpt-5.5", True),
            ("gpt-5.5-mini", True),
            ("gpt-6", True),
            ("gpt-7", True),
            ("gpt-10", True),
            ("o1", True),
            ("o3-mini", True),
            ("o4", True),
            ("gpt-4.1", False),
            ("gpt-4.1-mini", False),
            ("gpt-4o", False),
            ("anthropic--claude-4.6-sonnet", False),
        ],
    )
    def test_supports_openai_reasoning(self, model_name, expected):
        assert supports_openai_reasoning(model_name) is expected


class TestGetOpenAIReasoningEffort:
    """Test suite for get_openai_reasoning_effort."""

    @pytest.mark.parametrize(
        ("effort", "expected"),
        [
            (ThinkingEffort.OFF, "minimal"),
            (ThinkingEffort.LOW, "low"),
            (ThinkingEffort.MEDIUM, "medium"),
            (ThinkingEffort.HIGH, "high"),
        ],
    )
    def test_get_openai_reasoning_effort(self, effort, expected):
        assert get_openai_reasoning_effort(effort) == expected


class TestGetAnthropicThinkingFields:
    """Test suite for get_anthropic_thinking_fields."""

    def test_off_disables_thinking(self):
        assert get_anthropic_thinking_fields(ThinkingEffort.OFF) == {"thinking": {"type": "disabled"}}

    @pytest.mark.parametrize(
        ("effort", "expected_budget"),
        [
            (ThinkingEffort.LOW, 2048),
            (ThinkingEffort.MEDIUM, 8192),
            (ThinkingEffort.HIGH, 16384),
        ],
    )
    def test_enabled_levels_set_budget(self, effort, expected_budget):
        assert get_anthropic_thinking_fields(effort) == {
            "thinking": {"type": "enabled", "budget_tokens": expected_budget}
        }
