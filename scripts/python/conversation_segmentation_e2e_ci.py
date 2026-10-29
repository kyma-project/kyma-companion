"""Trusted CI utilities for the conversation segmentation E2E workflow.

This module never prints configuration values, HANA values, or raw pod logs. It is
checked out from the protected base branch rather than from the pull request under test.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from pathlib import Path
from typing import Any

TABLE_SUFFIXES = ("RUN", "ASSIGNMENT", "AGGREGATE", "WATERMARK")
MAX_HANA_IDENTIFIER_LENGTH = 127
TABLE_PREFIX_PATTERN = re.compile(r"^KC_SEG_(?:PR|MANUAL)_[0-9]+(?:_[0-9]+){1,2}$")
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9_]+$")

CANARIES = (
    "seg-e2e-session-alpha",
    "seg-e2e-session-beta",
    "demo-client",
    "demo-server",
    "seg-e2e-private-a",
    "seg-e2e-private-pod",
    "seg-e2e-private-function",
    "123e4567-e89b-12d3-a456-426614174000",
    "123e4567",
    "426614174000",
    "synthetic-user@example.invalid",
    "synthetic-user",
    "https://segmentation.invalid/private-path",
    "segmentation.invalid/private-path",
    "private-path",
    "192.0.2.42",
    "192.0.2",
)

_SAFE_LOG_PATTERNS = (
    re.compile(r"context_guard=(?:passed|failed) expected_contexts=[0-9]+ matching_contexts=[0-9]+"),
    re.compile(r"job_status=(?:complete|failed|timeout) completed_jobs=[0-9]+ failed_jobs=[0-9]+"),
    re.compile(r"seeded_conversations=[0-9]+ seeded_complete_turns=[0-9]+"),
    re.compile(r"appended_conversations=[0-9]+ appended_complete_turns=[0-9]+"),
    re.compile(
        r"validated_runs=[0-9]+ assignments=[0-9]+ aggregates=[0-9]+ watermarks=[0-9]+ "
        r"conversations=[0-9]+ turns=[0-9]+ failed_turns=[0-9]+"
    ),
    re.compile(r"helper_status=failed invariant=[A-Z0-9_]+ error_count=[0-9]+"),
    re.compile(r"Starting topic analysis: limit=[0-9]+ batch_size=[0-9]+ taxonomy=[A-Za-z0-9._-]+"),
    re.compile(r"Conversation [0-9]+: complete_turns=[0-9]+ new_turns=[0-9]+"),
    re.compile(r"Progress: conversations=[0-9]+ processed_turns=[0-9]+ failed_turns=[0-9]+"),
    re.compile(r"Wrote run: turns=[0-9]+ failed=[0-9]+ conversations=[0-9]+ topics=[0-9]+"),
)

_CONFIG_STRING_FIELDS = (
    "AICORE_AUTH_URL",
    "AICORE_BASE_URL",
    "AICORE_CLIENT_ID",
    "AICORE_CLIENT_SECRET",
    "AICORE_RESOURCE_GROUP",
    "DATABASE_URL",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
)


class CIInvariantError(RuntimeError):
    """A named privacy, configuration, or cleanup invariant failed."""

    def __init__(self, invariant: str) -> None:
        super().__init__(invariant)
        self.invariant = invariant


def _require(condition: bool, invariant: str) -> None:
    if not condition:
        raise CIInvariantError(invariant)


def normalize_sensitive_text(value: str) -> str:
    """Normalize text for case-insensitive canary comparisons."""
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def validate_table_prefix(prefix: str) -> str:
    """Validate and return a narrowly scoped E2E table prefix."""
    _require(bool(TABLE_PREFIX_PATTERN.fullmatch(prefix)), "TABLE_PREFIX_FORMAT")
    _require(
        all(len(f"{prefix}_{suffix}") <= MAX_HANA_IDENTIFIER_LENGTH for suffix in TABLE_SUFFIXES),
        "TABLE_NAME_LENGTH",
    )
    return prefix


def _load_object(path: Path, invariant: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as error:
        raise CIInvariantError(invariant) from error
    _require(isinstance(value, dict), invariant)
    return value


def build_minimal_config(base_path: Path, override_path: Path, table_prefix: str) -> dict[str, Any]:
    """Build the allowlisted config exposed to the untrusted PR image."""
    prefix = validate_table_prefix(table_prefix)
    source = _load_object(base_path, "BASE_CONFIG_JSON") | _load_object(override_path, "OVERRIDE_CONFIG_JSON")
    for field in _CONFIG_STRING_FIELDS:
        _require(isinstance(source.get(field), str) and bool(source[field]), f"CONFIG_{field}")

    model_name = source.get("MAIN_MODEL_NAME")
    _require(isinstance(model_name, str) and bool(model_name), "CONFIG_MAIN_MODEL_NAME")
    source_models = source.get("models")
    _require(isinstance(source_models, list), "CONFIG_MODELS")
    selected_models = [
        {key: model[key] for key in ("name", "deployment_id", "temperature") if key in model}
        for model in source_models
        if isinstance(model, dict) and model.get("name") == model_name
    ]
    _require(len(selected_models) == 1, "CONFIG_SEGMENTATION_MODEL")
    _require(bool(selected_models[0].get("deployment_id")), "CONFIG_MODEL_DEPLOYMENT")

    config = {field: source[field] for field in _CONFIG_STRING_FIELDS}
    config.update(
        {
            "DATABASE_PORT": int(source.get("DATABASE_PORT", 443)),
            "models": selected_models,
            "MAIN_MODEL_NAME": model_name,
            "SEGMENTATION_MODEL_NAME": model_name,
            "REDIS_HOST": "redis-stack.redis.svc.cluster.local",
            "REDIS_PORT": 6379,
            "REDIS_USER": "",
            "REDIS_PASSWORD": "",
            "REDIS_DB_NUMBER": 0,
            "LOG_LEVEL": "INFO",
            "LOG_FORMAT": "json",
            "LLM_REQUEST_TIMEOUT_SECONDS": 60,
            "SEGMENTATION_RUN_TABLE": f"{prefix}_RUN",
            "SEGMENTATION_ASSIGNMENT_TABLE": f"{prefix}_ASSIGNMENT",
            "SEGMENTATION_AGGREGATE_TABLE": f"{prefix}_AGGREGATE",
            "SEGMENTATION_WATERMARK_TABLE": f"{prefix}_WATERMARK",
            "SEGMENTATION_MAX_CONVERSATIONS": 2,
            "SEGMENTATION_PROGRESS_LOG_INTERVAL": 1,
            "SEGMENTATION_BATCH_SIZE": 2,
        }
    )
    return config


def sanitize_log_text(raw_log: str) -> list[str]:
    """Reject canaries and return only explicitly allowlisted count/status messages."""
    normalized_log = normalize_sensitive_text(raw_log)
    for canary in CANARIES:
        _require(normalize_sensitive_text(canary) not in normalized_log, "LOG_PRIVACY_CANARY")
    return [
        match.group(0)
        for line in raw_log.splitlines()
        for pattern in _SAFE_LOG_PATTERNS
        for match in pattern.finditer(line)
    ]


def _drop_tables(base_path: Path, override_path: Path, table_prefix: str) -> None:
    from hdbcli import dbapi  # noqa: PLC0415

    prefix = validate_table_prefix(table_prefix)
    source = _load_object(base_path, "BASE_CONFIG_JSON") | _load_object(override_path, "OVERRIDE_CONFIG_JSON")
    for field in ("DATABASE_URL", "DATABASE_USER", "DATABASE_PASSWORD"):
        _require(isinstance(source.get(field), str) and bool(source[field]), f"CONFIG_{field}")
    schema = str(source["DATABASE_USER"])
    _require(bool(IDENTIFIER_PATTERN.fullmatch(schema)), "HANA_SCHEMA_IDENTIFIER")
    tables = tuple(f"{prefix}_{suffix}" for suffix in TABLE_SUFFIXES)

    connection = dbapi.Connection(
        address=str(source["DATABASE_URL"]),
        port=int(source.get("DATABASE_PORT", 443)),
        user=schema,
        password=str(source["DATABASE_PASSWORD"]),
    )
    found = 0
    failures = 0
    try:
        for table in tables:
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT COUNT(*) FROM M_TABLES WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?",
                        (schema, table),
                    )
                    row = cursor.fetchone()
                    if row and int(row[0]) > 0:
                        found += 1
                        cursor.execute(f'DROP TABLE "{schema}"."{table}"')
                connection.commit()
            except Exception:
                failures += 1
                connection.rollback()
        _require(failures == 0, "HANA_CLEANUP_DROP")
        remaining = 0
        for table in tables:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT COUNT(*) FROM M_TABLES WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?",
                    (schema, table),
                )
                row = cursor.fetchone()
                remaining += int(row[0]) if row else 0
        _require(remaining == 0, "HANA_CLEANUP_REMAINING")
    finally:
        connection.close()
    print(f"cleanup_tables_found={found} cleanup_tables_remaining=0")


def _write_minimal_config(args: argparse.Namespace) -> None:
    config = build_minimal_config(Path(args.base_config), Path(args.override_config), args.table_prefix)
    output = Path(args.output)
    output.write_text(json.dumps(config, separators=(",", ":")))
    output.chmod(0o600)
    print(f"runtime_config_fields={len(config)} runtime_config_models={len(config['models'])}")


def _sanitize_logs(args: argparse.Namespace) -> None:
    raw_log = Path(args.input).read_text(errors="replace")
    safe_lines = sanitize_log_text(raw_log)
    for line in safe_lines:
        print(line)
    print(f"log_privacy_status=passed safe_log_lines={len(safe_lines)}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    build = subparsers.add_parser("build-config")
    build.add_argument("--base-config", required=True)
    build.add_argument("--override-config", required=True)
    build.add_argument("--table-prefix", required=True)
    build.add_argument("--output", required=True)

    drop = subparsers.add_parser("drop-tables")
    drop.add_argument("--base-config", required=True)
    drop.add_argument("--override-config", required=True)
    drop.add_argument("--table-prefix", required=True)

    sanitize = subparsers.add_parser("sanitize-logs")
    sanitize.add_argument("--input", required=True)
    return parser


def main() -> None:
    """Dispatch a CI helper command with privacy-safe failures."""
    args = _parser().parse_args()
    try:
        if args.action == "build-config":
            _write_minimal_config(args)
        elif args.action == "drop-tables":
            _drop_tables(Path(args.base_config), Path(args.override_config), args.table_prefix)
        else:
            _sanitize_logs(args)
    except CIInvariantError as error:
        print(f"ci_helper_status=failed invariant={error.invariant} error_count=1")
        raise SystemExit(1) from None
    except Exception:
        print("ci_helper_status=failed invariant=CI_HELPER_UNEXPECTED error_count=1")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
