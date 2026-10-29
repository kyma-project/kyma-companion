"""Privacy-safe setup and assertions for the conversation segmentation E2E test.

The helper runs inside the Companion image. It deliberately reports counts only: raw
Redis values, HANA values, credentials, and identifiers must never reach CI logs.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any

EXPECTED_CONVERSATIONS = 2
EXPECTED_TURNS = 3
EXPECTED_FIRST_RUNS = 1
EXPECTED_SECOND_RUNS = 2

_SESSION_ALPHA = "seg-e2e-session-alpha"
_SESSION_BETA = "seg-e2e-session-beta"
_CONVERSATIONS: dict[str, list[dict[str, Any]]] = {
    _SESSION_ALPHA: [
        {
            "type": "human",
            "content": (
                "How do I configure mTLS between demo-client and demo-server in "
                "namespace:seg-e2e-private-a? Reference 123e4567-e89b-12d3-a456-426614174000."
            ),
        },
        {"type": "ai", "content": "", "tool_calls": [{"name": "synthetic_lookup", "args": {}}]},
        {
            "type": "ai",
            "content": "Use a peer authentication policy and destination rules for strict workload mTLS.",
        },
        {
            "type": "human",
            "content": (
                "Why does my APIRule return 401 for synthetic-user@example.invalid at "
                "https://segmentation.invalid/private-path?"
            ),
        },
        {
            "type": "ai",
            "content": "Check the APIRule authentication access strategy and the credentials sent by the client.",
        },
    ],
    _SESSION_BETA: [
        {
            "type": "human",
            "content": "How can I troubleshoot pod seg-e2e-private-pod in CrashLoopBackOff at 192.0.2.42?",
        },
        {
            "type": "ai",
            "content": "Inspect the pod events, container state, and previous container logs to find the crash cause.",
        },
    ],
}

_RAW_VALUES = (
    _SESSION_ALPHA,
    _SESSION_BETA,
    "seg-e2e-private-a",
    "seg-e2e-private-pod",
    "123e4567-e89b-12d3-a456-426614174000",
    "synthetic-user@example.invalid",
    "https://segmentation.invalid/private-path",
    *(
        str(message.get("content", ""))
        for messages in _CONVERSATIONS.values()
        for message in messages
        if message.get("content")
    ),
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


class E2EValidationError(RuntimeError):
    """An E2E invariant was not satisfied."""


def _require(condition: bool) -> None:
    if not condition:
        raise E2EValidationError


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def _head_fingerprint(session_id: str) -> str:
    first_query = next(message["content"] for message in _CONVERSATIONS[session_id] if message["type"] == "human")
    return hashlib.sha256(first_query.encode()).hexdigest()


def _table_names() -> tuple[str, str, str, str]:
    from conversation_segmentation import config  # noqa: PLC0415

    tables = (config.RUN_TABLE, config.ASSIGNMENT_TABLE, config.AGGREGATE_TABLE, config.WATERMARK_TABLE)
    _require(all(_IDENTIFIER.fullmatch(table) for table in tables))
    return tables


def _hana_connection() -> tuple[Any, str]:
    from hdbcli import dbapi  # noqa: PLC0415

    from utils.settings import DATABASE_PASSWORD, DATABASE_PORT, DATABASE_URL, DATABASE_USER  # noqa: PLC0415

    _require(all(value is not None for value in (DATABASE_URL, DATABASE_USER, DATABASE_PASSWORD)))
    connection = dbapi.Connection(
        address=str(DATABASE_URL),
        port=DATABASE_PORT,
        user=str(DATABASE_USER),
        password=str(DATABASE_PASSWORD),
    )
    schema = str(DATABASE_USER)
    _require(bool(_IDENTIFIER.fullmatch(schema)))
    return connection, schema


def _query(connection: Any, sql: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(sql, tuple(params))
        return list(cursor.fetchall())


async def _seed() -> None:
    from redis.asyncio import Redis  # noqa: PLC0415

    from utils.settings import (  # noqa: PLC0415
        REDIS_DB_NUMBER,
        REDIS_HOST,
        REDIS_PASSWORD,
        REDIS_PORT,
        REDIS_SSL_ENABLED,
    )

    connection = Redis(
        host=str(REDIS_HOST),
        port=REDIS_PORT,
        db=REDIS_DB_NUMBER,
        password=str(REDIS_PASSWORD) or None,
        ssl=bool(REDIS_SSL_ENABLED),
    )
    try:
        for session_id, messages in _CONVERSATIONS.items():
            await connection.set(f"kyma_agent_conversation:{session_id}", json.dumps(messages))
        _require(await connection.ping())
    finally:
        await connection.aclose()
    print(f"seeded_conversations={EXPECTED_CONVERSATIONS} seeded_complete_turns={EXPECTED_TURNS}")


def _validate(expected_runs: int) -> None:  # noqa: PLR0915
    from conversation_segmentation.taxonomy import TAXONOMY_VERSION  # noqa: PLC0415

    _require(expected_runs in (EXPECTED_FIRST_RUNS, EXPECTED_SECOND_RUNS))
    connection, schema = _hana_connection()
    run_table, assignment_table, aggregate_table, watermark_table = _table_names()
    try:
        runs = _query(
            connection,
            f"SELECT RUN_ID, WINDOW_START, TURNS_ANALYZED, FAILED_TURNS, TAXONOMY_VERSION "
            f'FROM "{schema}"."{run_table}" ORDER BY CREATED_AT, RUN_ID',
        )
        assignments = _query(
            connection,
            f"SELECT CONVERSATION_HASH, TOPIC_KEY, CONFIDENCE, TURN_COUNT, TAXONOMY_VERSION "
            f'FROM "{schema}"."{assignment_table}"',
        )
        aggregates = _query(
            connection,
            f"SELECT TOPIC_KEY, DISTINCT_CONVERSATION_COUNT, TURN_COUNT, TAXONOMY_VERSION, RUN_ID "
            f'FROM "{schema}"."{aggregate_table}"',
        )
        watermarks = _query(
            connection,
            f'SELECT SESSION_KEY, TURNS_SEGMENTED, HEAD_FINGERPRINT FROM "{schema}"."{watermark_table}"',
        )
        all_rows = [
            *_query(connection, f'SELECT * FROM "{schema}"."{run_table}"'),
            *_query(connection, f'SELECT * FROM "{schema}"."{assignment_table}"'),
            *_query(connection, f'SELECT * FROM "{schema}"."{aggregate_table}"'),
            *_query(connection, f'SELECT * FROM "{schema}"."{watermark_table}"'),
        ]
    finally:
        connection.close()

    _require(len(runs) == expected_runs)
    expected_run_turns = [EXPECTED_TURNS] if expected_runs == EXPECTED_FIRST_RUNS else [EXPECTED_TURNS, 0]
    _require([int(row[2]) for row in runs] == expected_run_turns)
    _require(all(int(row[3]) == 0 for row in runs))
    _require(all(row[4] == TAXONOMY_VERSION for row in runs))
    if expected_runs == EXPECTED_SECOND_RUNS:
        _require(runs[-1][1] is not None)

    expected_hashes = {_session_hash(_SESSION_ALPHA), _session_hash(_SESSION_BETA)}
    _require(bool(assignments))
    _require({str(row[0]) for row in assignments} == expected_hashes)
    _require(sum(int(row[3]) for row in assignments) == EXPECTED_TURNS)
    _require(all(0.0 <= float(row[2]) <= 1.0 for row in assignments))
    _require(all(row[4] == TAXONOMY_VERSION for row in assignments))

    expected_aggregates: dict[str, tuple[int, int]] = {}
    for _, topic_key, _, turn_count, _ in assignments:
        conversations, turns = expected_aggregates.get(str(topic_key), (0, 0))
        expected_aggregates[str(topic_key)] = (conversations + 1, turns + int(turn_count))
    actual_aggregates = {
        str(topic_key): (int(conversations), int(turns)) for topic_key, conversations, turns, _, _ in aggregates
    }
    _require(bool(aggregates))
    _require(len(actual_aggregates) == len(aggregates))
    _require(actual_aggregates == expected_aggregates)
    _require(all(row[3] == TAXONOMY_VERSION for row in aggregates))
    _require(all(row[4] == runs[-1][0] for row in aggregates))

    expected_watermarks = {
        _session_hash(_SESSION_ALPHA): (2, _head_fingerprint(_SESSION_ALPHA)),
        _session_hash(_SESSION_BETA): (1, _head_fingerprint(_SESSION_BETA)),
    }
    actual_watermarks = {str(key): (int(turns), str(fingerprint)) for key, turns, fingerprint in watermarks}
    _require(actual_watermarks == expected_watermarks)

    persisted_values = tuple(str(value) for row in all_rows for value in row if value is not None)
    _require(not any(raw_value in persisted for raw_value in _RAW_VALUES for persisted in persisted_values))
    print(
        f"validated_runs={len(runs)} assignments={len(assignments)} aggregates={len(aggregates)} "
        f"watermarks={len(watermarks)} conversations={EXPECTED_CONVERSATIONS} "
        f"turns={EXPECTED_TURNS} failed_turns=0"
    )


def _drop_tables() -> None:
    connection, schema = _hana_connection()
    tables = _table_names()
    found = 0
    try:
        for table in tables:
            exists = _query(
                connection,
                "SELECT COUNT(*) FROM M_TABLES WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?",
                (schema, table),
            )[0][0]
            if int(exists) > 0:
                found += 1
                with connection.cursor() as cursor:
                    cursor.execute(f'DROP TABLE "{schema}"."{table}"')
        connection.commit()
        remaining = sum(
            int(
                _query(
                    connection,
                    "SELECT COUNT(*) FROM M_TABLES WHERE SCHEMA_NAME = ? AND TABLE_NAME = ?",
                    (schema, table),
                )[0][0]
            )
            for table in tables
        )
        _require(remaining == 0)
    finally:
        connection.close()
    print(f"cleanup_tables_found={found} cleanup_tables_remaining=0")


def main() -> None:
    """Run setup, validation, or cleanup without exposing exception details."""
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "validate", "drop"))
    parser.add_argument("--expected-runs", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.action == "seed":
            asyncio.run(_seed())
        elif args.action == "validate":
            _validate(args.expected_runs)
        else:
            _drop_tables()
    except Exception:
        print("helper_status=failed error_count=1")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
