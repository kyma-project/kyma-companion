"""Tests for trusted conversation segmentation E2E CI utilities."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

_SCRIPT = Path(__file__).parents[3] / "scripts" / "python" / "conversation_segmentation_e2e_ci.py"


def _load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("conversation_segmentation_e2e_ci", _SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


ci = _load_module()
EXPECTED_FIXTURE_CONVERSATIONS = 2


def _source_config() -> dict:
    return {
        "AICORE_AUTH_URL": "https://auth.invalid",
        "AICORE_BASE_URL": "https://api.invalid",
        "AICORE_CLIENT_ID": "client",
        "AICORE_CLIENT_SECRET": "secret",
        "AICORE_RESOURCE_GROUP": "default",
        "DATABASE_URL": "hana.invalid",
        "DATABASE_PORT": 443,
        "DATABASE_USER": "USER",
        "DATABASE_PASSWORD": "password",
        "MAIN_MODEL_NAME": "gpt-test",
        "models": [
            {"name": "gpt-test", "deployment_id": "deployment", "temperature": 0},
            {"name": "unused", "deployment_id": "other"},
        ],
        "TEST_CLUSTER_AUTH_TOKEN": "must-not-survive",
        "LANGFUSE_SECRET_KEY": "must-not-survive",
        "REDIS_HOST": "shared.invalid",
    }


def test_build_minimal_config_allowlists_fields(tmp_path: Path) -> None:
    base = tmp_path / "base.json"
    override = tmp_path / "override.json"
    base.write_text(json.dumps(_source_config()))
    override.write_text("{}")

    config = ci.build_minimal_config(base, override, "KC_SEG_PR_1504_123_1")

    assert config["SEGMENTATION_MAX_CONVERSATIONS"] == EXPECTED_FIXTURE_CONVERSATIONS
    assert config["REDIS_HOST"] == "redis-stack.redis.svc.cluster.local"
    assert config["models"] == [{"name": "gpt-test", "deployment_id": "deployment", "temperature": 0}]
    assert "TEST_CLUSTER_AUTH_TOKEN" not in config
    assert "LANGFUSE_SECRET_KEY" not in config


@pytest.mark.parametrize("prefix", ["unsafe", "KC_SEG_PR_x_1", "KC_SEG_PR_1_2_3;DROP"])
def test_validate_table_prefix_rejects_unsafe_values(prefix: str) -> None:
    with pytest.raises(ci.CIInvariantError, match="TABLE_PREFIX_FORMAT"):
        ci.validate_table_prefix(prefix)


def test_sanitize_log_text_returns_only_allowlisted_messages() -> None:
    raw = "metadata that must not be printed\nWrote run: turns=3 failed=0 conversations=2 topics=3\n"
    assert ci.sanitize_log_text(raw) == ["Wrote run: turns=3 failed=0 conversations=2 topics=3"]


@pytest.mark.parametrize("canary", ["DEMO-CLIENT", "192.0.2.42", "  Seg-E2E-Private-Pod  "])
def test_sanitize_log_text_rejects_normalized_canaries(canary: str) -> None:
    with pytest.raises(ci.CIInvariantError, match="LOG_PRIVACY_CANARY"):
        ci.sanitize_log_text(f"prefix {canary} suffix")
