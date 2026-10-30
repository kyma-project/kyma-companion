# Conversation Segmentation

`conversation_segmentation` is the batch entrypoint that turns recent Companion conversations into conversation-level topic analytics. It reads the conversation history from Redis, classifies only newly completed turns, and writes durable assignments and a current aggregate snapshot to HANA.
topic analytics. It reads conversation history from Redis, classifies only new completed turns, and writes durable

Run it from the Companion image:

```bash
python3.14 -m conversation_segmentation.main segment
```

## Processing contract

1. Scan `kyma_agent_conversation:*` keys without blocking Redis; deduplicate and sort session IDs before applying an optional limit.
2. Pair each human message with its final AI answer, skipping intermediate tool-call messages and incomplete turns.
3. Compare each conversation with its HANA watermark and classify only new turns. Classification uses bounded exponential
   backoff. A final failure stops that conversation's contiguous prefix while other conversations continue. After
   persistence, the process exits nonzero so the scheduled Job controller can retry it.
4. Canonicalize each model proposal into `area/intent/capability-slug` and merge it into the durable
   `(conversation_hash, topic_key)` assignment.
5. Derive assignment identity from the session ID plus an opaque instance ID stored in a separate Redis metadata key.
   Application saves choose and write that ID atomically while preserving the existing list-valued history format for
   rolling compatibility. Recreating an expired history receives a new ID even when its first query repeats. Existing
   histories without metadata use their first-turn fingerprint when metadata is first introduced.
6. Commit touched assignments and watermarks every configured batch.
7. Insert a run row and atomically replace the cumulative aggregate snapshot after processing completes.

The primary metric is `DISTINCT_CONVERSATION_COUNT`; cumulative `TURN_COUNT` is retained separately. Assignments and
watermarks are retained together for cumulative analytics. An unchanged rerun classifies no turns and rebuilds the same
aggregate from durable assignments.

## Persistence

The connecting `DATABASE_USER` owns four configurable tables:

| Default table | Purpose |
|---|---|
| `CONVERSATION_ANALYSIS_RUN` | Finalized-attempt history, token usage, turn and failure counts. |
| `CONVERSATION_TOPIC_ASSIGNMENT` | Cumulative `(conversation_hash, topic_key)` assignments. |
| `CONVERSATION_TOPIC_AGGREGATE` | Cumulative reporting snapshot by topic, replaced after each run. |
| `CONVERSATION_TOPIC_WATERMARK` | Retained processed-turn count and opaque instance fingerprint per session. |

HANA stores Redis session IDs only as SHA-256 hashes; Redis source keys still contain the raw session ID. Complete prompts,
responses, and raw tool payloads are not directly written to HANA, and classification does not request model reasoning.
Capability, label, and summary are model-generated conversation-derived text and pass through best-effort identifier
scrubbing; they are not guaranteed identifier- or payload-free. HANA access and retention must reflect that classification.
The separate Redis instance key contains only the session hash and either a random ID or a legacy first-turn fingerprint;
it uses the conversation TTL. Pause segmentation during a mixed-version rollout: older pods preserve the history format
but do not refresh instance metadata, so analytics identity is guaranteed only after all writers run the new code.

## Configuration

Settings are loaded from `CONFIG_PATH` and environment variables through `python-decouple`.

| Setting | Default | Meaning |
|---|---|---|
| `KYMA_AGENT_CONVERSATION_PREFIX` | `kyma_agent_conversation:` | Redis key prefix. |
| `KYMA_AGENT_CONVERSATION_INSTANCE_PREFIX` | `kyma_agent_conversation_instance:` | Redis instance-metadata key prefix. |
| `SEGMENTATION_MODEL_NAME` | `anthropic--claude-4.6-sonnet` | Structured classification model. |
| `SEGMENTATION_RUN_TABLE` | `CONVERSATION_ANALYSIS_RUN` | Run table. |
| `SEGMENTATION_ASSIGNMENT_TABLE` | `CONVERSATION_TOPIC_ASSIGNMENT` | Assignment table. |
| `SEGMENTATION_AGGREGATE_TABLE` | `CONVERSATION_TOPIC_AGGREGATE` | Aggregate table. |
| `SEGMENTATION_WATERMARK_TABLE` | `CONVERSATION_TOPIC_WATERMARK` | Watermark table. |
| `SEGMENTATION_MAX_CONVERSATIONS` | `0` | Maximum conversations; `0` processes all. |
| `SEGMENTATION_PROGRESS_LOG_INTERVAL` | `10` | Progress-log interval in processed turns. |
| `SEGMENTATION_BATCH_SIZE` | `25` | Conversations per HANA checkpoint. |
| `SEGMENTATION_CLASSIFICATION_MAX_ATTEMPTS` | `3` | Model attempts per turn before the run records a failure. |
| `SEGMENTATION_CLASSIFICATION_RETRY_BASE_SECONDS` | `1` | Base delay for exponential retry backoff. |

Redis, HANA, and model credentials use the normal Companion settings. The job intentionally avoids logging conversation
content and credentials; its operational logs contain counts, table-creation events, and exception classes.

`TAXONOMY_VERSION` is a persistence compatibility boundary. A run fails before processing when existing run history or
assignments use another version; changing taxonomy requires an explicit migration, table reset, or versioned table set.

Existing tables are checked for required column names; startup does not migrate them or validate every type, constraint,
or grant. Earlier session-only assignment hashes require an explicit migration/reset before using conversation-instance
hashes. The current taxonomy check alone does not detect that older identity scheme.

Retrying a failed turn still requires its conversation to be available in Redis. The rolling Redis TTL does not extend
when analytics runs; retention and retry scheduling must account for conversations expiring before the next attempt.

Only one writer may use a given segmentation table set at a time. The CronJob enforces `concurrencyPolicy: Forbid`; operators
must also verify that no scheduled or manual segmentation Job is active before starting a one-off Job against those tables.
The persistence protocol does not provide a database lease, so overlapping writers can overwrite newer absolute counts.

## Scaling

Transcript payloads are fetched one at a time, so they are not all resident simultaneously; peak transcript memory still

## Code map

- `main.py` — orchestration and CLI entrypoint.
- `redis_reader.py` — transcript scanning and turn pairing.
- `segmenter.py` / `taxonomy.py` — structured model output.
- `canonicalizer.py` — topic keys and best-effort identifier scrubbing.
- `aggregator.py` — cumulative assignments and aggregate rows.
- `hana_writer.py` — table creation, checkpoints, snapshots, and transactions.
- `watermark.py` — session hashing and incremental bookmarks.

Internal deployment procedures, landscape validation records, and the ready-to-edit Job manifest are maintained in the AI Force repository under `docs/how-tos/conversation-topic-analysis` and `docs/evaluations/conversation-topic-analysis`.
