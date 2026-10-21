"""Translate the global ``THINKING_EFFORT`` setting into provider-specific
reasoning parameters for OpenAI and Anthropic (Bedrock Converse) models.

This keeps the reasoning-effort mapping in a single place so the same global
setting behaves consistently across every provider.
"""

import re

from utils.settings import ThinkingEffort

# Non-GPT OpenAI reasoning model prefixes (o-series).
OPENAI_REASONING_MODEL_PREFIXES: tuple[str, ...] = ("o1", "o3", "o4")

# Minimum GPT major version (inclusive) that supports the ``reasoning_effort`` param.
# Anything at or above this is treated as reasoning-capable (gpt-5, gpt-5.5, gpt-6, ...).
OPENAI_REASONING_MIN_GPT_VERSION = 5.0

# Matches the leading version number of a GPT model name, e.g. "gpt-5.5-mini" -> "5.5".
_GPT_VERSION_PATTERN = re.compile(r"^gpt-(\d+(?:\.\d+)?)")

# Anthropic (Bedrock Converse) extended-thinking token budgets per effort level.
_ANTHROPIC_THINKING_BUDGET_TOKENS: dict[ThinkingEffort, int] = {
    ThinkingEffort.LOW: 2048,
    ThinkingEffort.MEDIUM: 8192,
    ThinkingEffort.HIGH: 16384,
}

# OpenAI reasoning models ``reasoning_effort`` values per effort level.
_OPENAI_REASONING_EFFORT: dict[ThinkingEffort, str] = {
    ThinkingEffort.OFF: "minimal",
    ThinkingEffort.LOW: "low",
    ThinkingEffort.MEDIUM: "medium",
    ThinkingEffort.HIGH: "high",
}


def supports_openai_reasoning(model_name: str) -> bool:
    """Return whether the given OpenAI model supports the reasoning_effort param.

    True for the o-series (o1/o3/o4) and for any GPT model at or above version 5
    (e.g. gpt-5, gpt-5-mini, gpt-5.5, gpt-6, gpt-7). Older GPT models such as
    gpt-4.1 or gpt-4o are excluded because they reject the parameter.
    """
    if model_name.startswith(OPENAI_REASONING_MODEL_PREFIXES):
        return True
    match = _GPT_VERSION_PATTERN.match(model_name)
    if match is None:
        return False
    return float(match.group(1)) >= OPENAI_REASONING_MIN_GPT_VERSION


def get_openai_reasoning_effort(effort: ThinkingEffort) -> str:
    """Return the OpenAI ``reasoning_effort`` value for the given thinking effort."""
    return _OPENAI_REASONING_EFFORT[effort]


def get_anthropic_thinking_fields(effort: ThinkingEffort) -> dict:
    """Return ``additional_model_request_fields`` for Claude models.

    OFF explicitly disables (adaptive/extended) thinking; the other levels enable
    extended thinking with an increasing token budget.
    """
    if effort == ThinkingEffort.OFF:
        return {"thinking": {"type": "disabled"}}
    return {
        "thinking": {
            "type": "enabled",
            "budget_tokens": _ANTHROPIC_THINKING_BUDGET_TOKENS[effort],
        }
    }
