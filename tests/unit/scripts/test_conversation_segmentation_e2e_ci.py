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


def _model_config() -> dict:
    return {
        "SEGMENTATION_E2E_PURPOSE": "conversation-segmentation-e2e-model",
        "AICORE_AUTH_URL": "https://auth.invalid",
        "AICORE_BASE_URL": "https://api.invalid",
        "AICORE_CLIENT_ID": "client",
        "AICORE_CLIENT_SECRET": "secret",
        "AICORE_RESOURCE_GROUP": "default",
        "MODEL_NAME": "gpt-test",
        "MODEL_DEPLOYMENT_ID": "deployment",
        "MODEL_TEMPERATURE": 0,
        "TEST_CLUSTER_AUTH_TOKEN": "must-not-survive",
        "LANGFUSE_SECRET_KEY": "must-not-survive",
    }


def _hana_config() -> dict:
    return {
        "SEGMENTATION_E2E_PURPOSE": "conversation-segmentation-e2e-hana",
        "SEGMENTATION_E2E_SCHEMA": "KC_SEG_E2E_RUNTIME",
        "DATABASE_URL": "hana.invalid",
        "DATABASE_PORT": 443,
        "DATABASE_USER": "KC_SEG_E2E_RUNTIME",
        "DATABASE_PASSWORD": "password",
        "UNRELATED_HANA_CREDENTIAL": "must-not-survive",
    }


def test_build_minimal_config_allowlists_fields(tmp_path: Path) -> None:
    model = tmp_path / "model.json"
    hana = tmp_path / "hana.json"
    model.write_text(json.dumps(_model_config()))
    hana.write_text(json.dumps(_hana_config()))

    config = ci.build_minimal_config(model, hana, "KC_SEG_PR_1504_123_1")

    assert config["SEGMENTATION_MAX_CONVERSATIONS"] == EXPECTED_FIXTURE_CONVERSATIONS
    assert config["REDIS_HOST"] == "redis-stack.redis.svc.cluster.local"
    assert config["KYMA_AGENT_CONVERSATION_PREFIX"] == "kyma_agent_conversation:"
    assert config["KYMA_AGENT_CONVERSATION_INSTANCE_PREFIX"] == "kyma_agent_conversation_instance:"
    assert config["SEGMENTATION_CLASSIFICATION_MAX_ATTEMPTS"] == 3  # noqa: PLR2004
    assert config["SEGMENTATION_CLASSIFICATION_RETRY_BASE_SECONDS"] == 1
    assert config["models"] == [{"name": "gpt-test", "deployment_id": "deployment", "temperature": 0}]
    assert "TEST_CLUSTER_AUTH_TOKEN" not in config
    assert "LANGFUSE_SECRET_KEY" not in config
    assert "UNRELATED_HANA_CREDENTIAL" not in config


@pytest.mark.parametrize(
    ("field", "value", "invariant"),
    [
        ("SEGMENTATION_E2E_PURPOSE", "wrong", "HANA_CONFIG_PURPOSE"),
        ("SEGMENTATION_E2E_SCHEMA", "LANDSCAPE_SCHEMA", "HANA_E2E_SCHEMA_MARKER"),
        ("DATABASE_USER", "KC_SEG_E2E_OTHER", "HANA_RUNTIME_SCHEMA_OWNERSHIP"),
    ],
)
def test_build_minimal_config_fails_closed_on_hana_contract(
    tmp_path: Path, field: str, value: str, invariant: str
) -> None:
    model = tmp_path / "model.json"
    hana = tmp_path / "hana.json"
    model.write_text(json.dumps(_model_config()))
    hana_config = _hana_config()
    hana_config[field] = value
    hana.write_text(json.dumps(hana_config))

    with pytest.raises(ci.CIInvariantError, match=invariant):
        ci.build_minimal_config(model, hana, "KC_SEG_PR_1504_123_1")


def test_build_minimal_config_fails_closed_on_model_purpose(tmp_path: Path) -> None:
    model = tmp_path / "model.json"
    hana = tmp_path / "hana.json"
    model_config = _model_config()
    model_config["SEGMENTATION_E2E_PURPOSE"] = "wrong"
    model.write_text(json.dumps(model_config))
    hana.write_text(json.dumps(_hana_config()))

    with pytest.raises(ci.CIInvariantError, match="MODEL_CONFIG_PURPOSE"):
        ci.build_minimal_config(model, hana, "KC_SEG_PR_1504_123_1")


def test_cleanup_contract_requires_separate_marked_principal(tmp_path: Path) -> None:
    cleanup = tmp_path / "cleanup.json"
    cleanup.write_text(
        json.dumps(
            {
                "SEGMENTATION_E2E_PURPOSE": "conversation-segmentation-e2e-cleanup",
                "SEGMENTATION_E2E_SCHEMA": "KC_SEG_E2E_RUNTIME",
                "DATABASE_URL": "hana.invalid",
                "DATABASE_USER": "KC_SEG_E2E_RUNTIME",
                "DATABASE_PASSWORD": "password",
            }
        )
    )

    with pytest.raises(ci.CIInvariantError, match="HANA_CLEANUP_PRINCIPAL_SEPARATION"):
        ci._drop_tables(cleanup, "KC_SEG_PR_1504_123_1")


@pytest.mark.parametrize("prefix", ["unsafe", "KC_SEG_PR_x_1", "KC_SEG_PR_1_2_3;DROP"])
def test_validate_table_prefix_rejects_unsafe_values(prefix: str) -> None:
    with pytest.raises(ci.CIInvariantError, match="TABLE_PREFIX_FORMAT"):
        ci.validate_table_prefix(prefix)


def test_sanitize_log_text_returns_only_allowlisted_messages() -> None:
    raw = "metadata that must not be printed\nWrote run: turns=3 failed=0 conversations=2 topics=3\n"
    assert ci.sanitize_log_text(raw, "segment-initial") == ["Wrote run: turns=3 failed=0 conversations=2 topics=3"]


def test_sanitize_log_text_requires_action_marker() -> None:
    with pytest.raises(ci.CIInvariantError, match="LOG_EXPECTED_MARKER"):
        ci.sanitize_log_text("Conversation 1: complete_turns=2 new_turns=2", "segment-initial")


@pytest.mark.parametrize("canary", ["DEMO-CLIENT", "192.0.2.42", "  Seg-E2E-Private-Pod  "])
def test_sanitize_log_text_rejects_normalized_canaries(canary: str) -> None:
    with pytest.raises(ci.CIInvariantError, match="LOG_PRIVACY_CANARY"):
        ci.sanitize_log_text(f"prefix {canary} suffix", "seed")


def test_cleanup_uses_automatic_dedicated_environment_and_secret() -> None:
    workflow = (_SCRIPT.parents[2] / ".github/workflows/e2e-tests-conversation-segmentation-reusable.yaml").read_text()
    assert "environment: segmentation-e2e-cleanup" in workflow
    assert "secrets.SEGMENTATION_E2E_HANA_CLEANUP_CONFIG" in workflow


def test_cleanup_requirement_hash_matches_lockfile() -> None:
    root = _SCRIPT.parents[2]
    requirement = (root / "scripts/requirements/conversation-segmentation-e2e-cleanup.txt").read_text()
    expected_hash = "sha256:8dae4357c648b199e1a10bddd29c87a7d8a23d3b1899b1d9e70b0bd3274ceae9"
    assert requirement == f"hdbcli==2.30.27 --hash={expected_hash}\n"
    assert expected_hash in (root / "poetry.lock").read_text()


def test_pull_image_build_stamps_head_revision() -> None:
    root = _SCRIPT.parents[2]
    dockerfile = (root / "Dockerfile").read_text()
    workflow = (root / ".github/workflows/pull-build-image.yaml").read_text()
    assert 'ARG IMAGE_REVISION="unknown"' in dockerfile
    assert 'LABEL org.opencontainers.image.revision="${IMAGE_REVISION}"' in dockerfile
    assert "IMAGE_REVISION=${{ github.event.pull_request.head.sha }}" in workflow
