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
import unicodedata
from collections.abc import Sequence
from typing import Any

EXPECTED_CONVERSATIONS = 2
EXPECTED_INITIAL_TURNS = 3
EXPECTED_INCREMENTAL_TURNS = 4
EXPECTED_FIRST_RUNS = 1
EXPECTED_SECOND_RUNS = 2
EXPECTED_THIRD_RUNS = 3

_SESSION_ALPHA = "seg-e2e-session-alpha"
_SESSION_BETA = "seg-e2e-session-beta"
_IDENTITY_SMOKE_SESSION = "seg-e2e-identity-smoke"
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

_APPENDED_TURN: list[dict[str, Any]] = [
    {
        "type": "human",
        "content": "How do I deploy function seg-e2e-private-function with a runtime and resource limits?",
    },
    {
        "type": "ai",
        "content": "Create a Function resource with the desired runtime and configure its resource requests and limits.",
    },
]

_RAW_VALUES = (
    _SESSION_ALPHA,
    _SESSION_BETA,
    "seg-e2e-private-a",
    "seg-e2e-private-pod",
    "seg-e2e-private-function",
    "demo-client",
    "demo-server",
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
    *(
        str(message.get("content", ""))
        for messages in _CONVERSATIONS.values()
        for message in messages
        if message.get("content")
    ),
    *(str(message["content"]) for message in _APPENDED_TURN),
)
_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


class E2EValidationError(RuntimeError):
    """An E2E invariant was not satisfied."""


def _require(condition: bool, invariant: str) -> None:
    if not condition:
        raise E2EValidationError(invariant)


def _normalize(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _session_hash(session_id: str) -> str:
    return hashlib.sha256(session_id.encode()).hexdigest()


def _conversation_hash(session_id: str, conversation_id: str) -> str:
    return hashlib.sha256(f"{session_id}\0{conversation_id}".encode()).hexdigest()


def _table_names() -> tuple[str, str, str, str]:
    from conversation_segmentation import config  # noqa: PLC0415

    tables = (config.RUN_TABLE, config.ASSIGNMENT_TABLE, config.AGGREGATE_TABLE, config.WATERMARK_TABLE)
    _require(all(_IDENTIFIER.fullmatch(table) for table in tables), "TABLE_IDENTIFIER")
    return tables


def _hana_connection() -> tuple[Any, str]:
    from hdbcli import dbapi  # noqa: PLC0415

    from utils.settings import DATABASE_PASSWORD, DATABASE_PORT, DATABASE_URL, DATABASE_USER  # noqa: PLC0415

    _require(
        all(value is not None for value in (DATABASE_URL, DATABASE_USER, DATABASE_PASSWORD)),
        "HANA_CONFIG",
    )
    connection = dbapi.Connection(
        address=str(DATABASE_URL),
        port=DATABASE_PORT,
        user=str(DATABASE_USER),
        password=str(DATABASE_PASSWORD),
    )
    schema = str(DATABASE_USER)
    _require(bool(_IDENTIFIER.fullmatch(schema)), "HANA_SCHEMA_IDENTIFIER")
    return connection, schema


def _query(connection: Any, sql: str, params: Sequence[Any] = ()) -> list[tuple[Any, ...]]:
    with connection.cursor() as cursor:
        cursor.execute(sql, tuple(params))
        return list(cursor.fetchall())


async def _seed() -> None:
    from routers.common import (  # noqa: PLC0415
        KYMA_AGENT_CONVERSATION_INSTANCE_PREFIX,
        KYMA_AGENT_CONVERSATION_PREFIX,
        _deserialize_messages,
        save_conversation_history,
    )
    from services.redis import get_redis  # noqa: PLC0415

    redis_service = get_redis()
    connection = redis_service.get_connection()
    try:
        for session_id, messages in _CONVERSATIONS.items():
            await save_conversation_history(redis_service, session_id, _deserialize_messages(messages))
        smoke_hash = _session_hash(_IDENTITY_SMOKE_SESSION)
        smoke_history_key = f"{KYMA_AGENT_CONVERSATION_PREFIX}{_IDENTITY_SMOKE_SESSION}"
        smoke_instance_key = f"{KYMA_AGENT_CONVERSATION_INSTANCE_PREFIX}{smoke_hash}"
        try:
            smoke_messages = _deserialize_messages(
                [{"type": "human", "content": "synthetic identity smoke"}, {"type": "ai", "content": "ok"}]
            )
            await save_conversation_history(redis_service, _IDENTITY_SMOKE_SESSION, smoke_messages)
            first_id = await connection.get(smoke_instance_key)
            await save_conversation_history(redis_service, _IDENTITY_SMOKE_SESSION, smoke_messages)
            _require(first_id is not None and await connection.get(smoke_instance_key) == first_id, "REDIS_STABLE_ID")
            await connection.set(smoke_history_key, "{malformed", ex=60)
            await save_conversation_history(redis_service, _IDENTITY_SMOKE_SESSION, smoke_messages)
            repaired_id = await connection.get(smoke_instance_key)
            repaired_history = await connection.get(smoke_history_key)
            _require(repaired_id is not None and repaired_id != first_id, "REDIS_MALFORMED_REPAIR_ID")
            _require(isinstance(json.loads(repaired_history), list), "REDIS_MALFORMED_REPAIR_HISTORY")
        finally:
            await connection.delete(smoke_history_key, smoke_instance_key)
        _require(await connection.ping(), "REDIS_SEED_PING")
    finally:
        await connection.aclose()
    print(f"seeded_conversations={EXPECTED_CONVERSATIONS} seeded_complete_turns={EXPECTED_INITIAL_TURNS}")


async def _append_turn() -> None:
    from routers.common import (  # noqa: PLC0415
        _deserialize_messages,
        load_conversation_history,
        save_conversation_history,
    )
    from services.redis import get_redis  # noqa: PLC0415

    redis_service = get_redis()
    connection = redis_service.get_connection()
    try:
        messages = await load_conversation_history(redis_service, _SESSION_BETA)
        _require(bool(messages), "REDIS_APPEND_SOURCE")
        marker = _APPENDED_TURN[0]["content"]
        if not any(message.content == marker for message in messages):
            messages.extend(_deserialize_messages(_APPENDED_TURN))
            await save_conversation_history(redis_service, _SESSION_BETA, messages)
        _require(await connection.ping(), "REDIS_APPEND_PING")
    finally:
        await connection.aclose()
    print("appended_conversations=1 appended_complete_turns=1")


async def _read_conversation_ids() -> dict[str, str]:
    from conversation_segmentation import config  # noqa: PLC0415
    from conversation_segmentation.redis_reader import read_conversation_id  # noqa: PLC0415
    from services.redis import get_redis  # noqa: PLC0415

    connection = get_redis().get_connection()
    try:
        conversation_ids = {
            session_id: await read_conversation_id(connection, config.CONVERSATION_INSTANCE_KEY_PREFIX, session_id)
            for session_id in _CONVERSATIONS
        }
        _require(all(re.fullmatch(r"[0-9a-f]{64}", value) for value in conversation_ids.values()), "REDIS_INSTANCE_IDS")
        _require(len(set(conversation_ids.values())) == EXPECTED_CONVERSATIONS, "REDIS_INSTANCE_ID_UNIQUENESS")
        return conversation_ids
    finally:
        await connection.aclose()


def _validate(expected_runs: int) -> None:  # noqa: PLR0915
    from conversation_segmentation.taxonomy import TAXONOMY_VERSION  # noqa: PLC0415

    _require(
        expected_runs in (EXPECTED_FIRST_RUNS, EXPECTED_SECOND_RUNS, EXPECTED_THIRD_RUNS),
        "EXPECTED_RUN_COUNT",
    )
    conversation_ids = asyncio.run(_read_conversation_ids())
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

    expected_run_turns = {
        EXPECTED_FIRST_RUNS: [EXPECTED_INITIAL_TURNS],
        EXPECTED_SECOND_RUNS: [EXPECTED_INITIAL_TURNS, 1],
        EXPECTED_THIRD_RUNS: [EXPECTED_INITIAL_TURNS, 1, 0],
    }[expected_runs]
    expected_total_turns = (
        EXPECTED_INITIAL_TURNS if expected_runs == EXPECTED_FIRST_RUNS else EXPECTED_INCREMENTAL_TURNS
    )
    _require(len(runs) == expected_runs, "RUN_ROW_COUNT")
    _require([int(row[2]) for row in runs] == expected_run_turns, "RUN_TURN_COUNTS")
    _require(all(int(row[3]) == 0 for row in runs), "RUN_FAILED_TURNS")
    _require(all(row[4] == TAXONOMY_VERSION for row in runs), "RUN_TAXONOMY")
    if expected_runs > EXPECTED_FIRST_RUNS:
        _require(runs[-1][1] is not None, "RUN_WINDOW_START")

    expected_hashes = {
        _conversation_hash(_SESSION_ALPHA, conversation_ids[_SESSION_ALPHA]),
        _conversation_hash(_SESSION_BETA, conversation_ids[_SESSION_BETA]),
    }
    _require(bool(assignments), "ASSIGNMENT_ROWS_PRESENT")
    _require({str(row[0]) for row in assignments} == expected_hashes, "ASSIGNMENT_CONVERSATION_COUNTS")
    _require(sum(int(row[3]) for row in assignments) == expected_total_turns, "ASSIGNMENT_TURN_COUNT")
    _require(all(0.0 <= float(row[2]) <= 1.0 for row in assignments), "ASSIGNMENT_CONFIDENCE")
    _require(all(row[4] == TAXONOMY_VERSION for row in assignments), "ASSIGNMENT_TAXONOMY")

    expected_aggregates: dict[str, tuple[int, int]] = {}
    for _, topic_key, _, turn_count, _ in assignments:
        conversations, turns = expected_aggregates.get(str(topic_key), (0, 0))
        expected_aggregates[str(topic_key)] = (conversations + 1, turns + int(turn_count))
    actual_aggregates = {
        str(topic_key): (int(conversations), int(turns)) for topic_key, conversations, turns, _, _ in aggregates
    }
    _require(bool(aggregates), "AGGREGATE_ROWS_PRESENT")
    _require(len(actual_aggregates) == len(aggregates), "AGGREGATE_TOPIC_UNIQUENESS")
    _require(actual_aggregates == expected_aggregates, "AGGREGATE_COUNTS")
    _require(all(row[3] == TAXONOMY_VERSION for row in aggregates), "AGGREGATE_TAXONOMY")
    _require(all(row[4] == runs[-1][0] for row in aggregates), "AGGREGATE_RUN_ID")

    expected_watermarks = {
        _session_hash(_SESSION_ALPHA): (2, conversation_ids[_SESSION_ALPHA]),
        _session_hash(_SESSION_BETA): (
            1 if expected_runs == EXPECTED_FIRST_RUNS else 2,
            conversation_ids[_SESSION_BETA],
        ),
    }
    actual_watermarks = {str(key): (int(turns), str(fingerprint)) for key, turns, fingerprint in watermarks}
    _require(actual_watermarks == expected_watermarks, "WATERMARK_COUNTS")

    persisted_values = tuple(_normalize(str(value)) for row in all_rows for value in row if value is not None)
    _require(
        not any(_normalize(raw_value) in persisted for raw_value in _RAW_VALUES for persisted in persisted_values),
        "HANA_PRIVACY_CANARY",
    )
    print(
        f"validated_runs={len(runs)} assignments={len(assignments)} aggregates={len(aggregates)} "
        f"watermarks={len(watermarks)} conversations={EXPECTED_CONVERSATIONS} "
        f"turns={expected_total_turns} failed_turns=0"
    )


def main() -> None:
    """Run setup, validation, or cleanup without exposing exception details."""
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("seed", "append", "validate"))
    parser.add_argument("--expected-runs", type=int, default=0)
    args = parser.parse_args()
    try:
        if args.action == "seed":
            asyncio.run(_seed())
        elif args.action == "append":
            asyncio.run(_append_turn())
        elif args.action == "validate":
            _validate(args.expected_runs)
    except E2EValidationError as error:
        print(f"helper_status=failed invariant={error} exception={type(error).__name__} error_count=1")
        raise SystemExit(1) from None
    except Exception as error:
        print(f"helper_status=failed invariant=HELPER_UNEXPECTED exception={type(error).__name__} error_count=1")
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
