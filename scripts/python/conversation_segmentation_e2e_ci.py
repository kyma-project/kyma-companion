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
E2E_SCHEMA_PATTERN = re.compile(r"^KC_SEG_E2E_[A-Z0-9_]+$")
MODEL_CONFIG_PURPOSE = "conversation-segmentation-e2e-model"
HANA_CONFIG_PURPOSE = "conversation-segmentation-e2e-hana"
CLEANUP_CONFIG_PURPOSE = "conversation-segmentation-e2e-cleanup"

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

_MODEL_STRING_FIELDS = (
    "AICORE_AUTH_URL",
    "AICORE_BASE_URL",
    "AICORE_CLIENT_ID",
    "AICORE_CLIENT_SECRET",
    "AICORE_RESOURCE_GROUP",
    "MODEL_NAME",
    "MODEL_DEPLOYMENT_ID",
)
_HANA_STRING_FIELDS = (
    "DATABASE_URL",
    "DATABASE_USER",
    "DATABASE_PASSWORD",
    "SEGMENTATION_E2E_SCHEMA",
)
_EXPECTED_LOG_MARKERS = {
    "seed": re.compile(r"^seeded_conversations=2 seeded_complete_turns=3$"),
    "append": re.compile(r"^appended_conversations=1 appended_complete_turns=1$"),
    "segment-initial": re.compile(r"^Wrote run: turns=3 failed=0 conversations=2 topics=[0-9]+$"),
    "segment-incremental": re.compile(r"^Wrote run: turns=1 failed=0 conversations=2 topics=[0-9]+$"),
    "segment-noop": re.compile(r"^Wrote run: turns=0 failed=0 conversations=2 topics=[0-9]+$"),
    "validate-1": re.compile(
        r"^validated_runs=1 assignments=[0-9]+ aggregates=[0-9]+ watermarks=2 "
        r"conversations=2 turns=3 failed_turns=0$"
    ),
    "validate-2": re.compile(
        r"^validated_runs=2 assignments=[0-9]+ aggregates=[0-9]+ watermarks=2 "
        r"conversations=2 turns=4 failed_turns=0$"
    ),
    "validate-3": re.compile(
        r"^validated_runs=3 assignments=[0-9]+ aggregates=[0-9]+ watermarks=2 "
        r"conversations=2 turns=4 failed_turns=0$"
    ),
}


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


def _require_purpose(config: dict[str, Any], purpose: str, invariant: str) -> None:
    _require(config.get("SEGMENTATION_E2E_PURPOSE") == purpose, invariant)


def _require_string_fields(config: dict[str, Any], fields: tuple[str, ...]) -> None:
    for field in fields:
        _require(isinstance(config.get(field), str) and bool(config[field]), f"CONFIG_{field}")


def build_minimal_config(model_path: Path, hana_path: Path, table_prefix: str) -> dict[str, Any]:
    """Build the allowlisted config exposed to the untrusted PR image."""
    prefix = validate_table_prefix(table_prefix)
    model = _load_object(model_path, "MODEL_CONFIG_JSON")
    hana = _load_object(hana_path, "HANA_CONFIG_JSON")
    _require_purpose(model, MODEL_CONFIG_PURPOSE, "MODEL_CONFIG_PURPOSE")
    _require_purpose(hana, HANA_CONFIG_PURPOSE, "HANA_CONFIG_PURPOSE")
    _require_string_fields(model, _MODEL_STRING_FIELDS)
    _require_string_fields(hana, _HANA_STRING_FIELDS)
    schema = str(hana["SEGMENTATION_E2E_SCHEMA"])
    _require(bool(E2E_SCHEMA_PATTERN.fullmatch(schema)), "HANA_E2E_SCHEMA_MARKER")
    _require(hana["DATABASE_USER"] == schema, "HANA_RUNTIME_SCHEMA_OWNERSHIP")

    model_name = str(model["MODEL_NAME"])
    selected_model = {
        "name": model_name,
        "deployment_id": model["MODEL_DEPLOYMENT_ID"],
        "temperature": float(model.get("MODEL_TEMPERATURE", 0)),
    }
    config = {field: model[field] for field in _MODEL_STRING_FIELDS if field.startswith("AICORE_")}
    config.update({field: hana[field] for field in ("DATABASE_URL", "DATABASE_USER", "DATABASE_PASSWORD")})
    config.update(
        {
            "SEGMENTATION_E2E_PURPOSE": HANA_CONFIG_PURPOSE,
            "SEGMENTATION_E2E_SCHEMA": schema,
            "DATABASE_PORT": int(hana.get("DATABASE_PORT", 443)),
            "models": [selected_model],
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


def sanitize_log_text(raw_log: str, expected_kind: str) -> list[str]:
    """Reject canaries and return only explicitly allowlisted count/status messages."""
    _require(expected_kind in _EXPECTED_LOG_MARKERS, "LOG_EXPECTATION_KIND")
    normalized_log = normalize_sensitive_text(raw_log)
    for canary in CANARIES:
        _require(normalize_sensitive_text(canary) not in normalized_log, "LOG_PRIVACY_CANARY")
    safe_lines = [
        match.group(0)
        for line in raw_log.splitlines()
        for pattern in _SAFE_LOG_PATTERNS
        for match in pattern.finditer(line)
    ]
    _require(any(_EXPECTED_LOG_MARKERS[expected_kind].fullmatch(line) for line in safe_lines), "LOG_EXPECTED_MARKER")
    return safe_lines


def _drop_tables(cleanup_config_path: Path, table_prefix: str) -> None:
    from hdbcli import dbapi  # noqa: PLC0415

    prefix = validate_table_prefix(table_prefix)
    source = _load_object(cleanup_config_path, "CLEANUP_CONFIG_JSON")
    _require_purpose(source, CLEANUP_CONFIG_PURPOSE, "CLEANUP_CONFIG_PURPOSE")
    _require_string_fields(source, _HANA_STRING_FIELDS)
    schema = str(source["SEGMENTATION_E2E_SCHEMA"])
    cleanup_user = str(source["DATABASE_USER"])
    _require(bool(E2E_SCHEMA_PATTERN.fullmatch(schema)), "HANA_E2E_SCHEMA_MARKER")
    _require(bool(E2E_SCHEMA_PATTERN.fullmatch(cleanup_user)), "HANA_CLEANUP_USER_MARKER")
    _require(cleanup_user != schema, "HANA_CLEANUP_PRINCIPAL_SEPARATION")
    tables = tuple(f"{prefix}_{suffix}" for suffix in TABLE_SUFFIXES)

    connection = dbapi.Connection(
        address=str(source["DATABASE_URL"]),
        port=int(source.get("DATABASE_PORT", 443)),
        user=cleanup_user,
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
    config = build_minimal_config(Path(args.model_config), Path(args.hana_config), args.table_prefix)
    output = Path(args.output)
    output.write_text(json.dumps(config, separators=(",", ":")))
    output.chmod(0o600)
    print(f"runtime_config_fields={len(config)} runtime_config_models={len(config['models'])}")


def _sanitize_logs(args: argparse.Namespace) -> None:
    raw_log = Path(args.input).read_text(errors="replace")
    safe_lines = sanitize_log_text(raw_log, args.expected_kind)
    for line in safe_lines:
        print(line)
    print(f"log_privacy_status=passed safe_log_lines={len(safe_lines)}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)

    build = subparsers.add_parser("build-config")
    build.add_argument("--model-config", required=True)
    build.add_argument("--hana-config", required=True)
    build.add_argument("--table-prefix", required=True)
    build.add_argument("--output", required=True)

    drop = subparsers.add_parser("drop-tables")
    drop.add_argument("--cleanup-config", required=True)
    drop.add_argument("--table-prefix", required=True)

    sanitize = subparsers.add_parser("sanitize-logs")
    sanitize.add_argument("--input", required=True)
    sanitize.add_argument("--expected-kind", choices=sorted(_EXPECTED_LOG_MARKERS), required=True)
    return parser


def main() -> None:
    """Dispatch a CI helper command with privacy-safe failures."""
    args = _parser().parse_args()
    try:
        if args.action == "build-config":
            _write_minimal_config(args)
        elif args.action == "drop-tables":
            _drop_tables(Path(args.cleanup_config), args.table_prefix)
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
