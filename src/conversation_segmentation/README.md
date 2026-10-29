# Conversation Segmentation

`conversation_segmentation` is the batch entrypoint that turns recent Companion conversations into conversation-level
topic analytics. It reads conversation history from Redis, classifies only new completed turns, and writes durable
assignments plus a current aggregate snapshot to HANA.

Run it from the Companion image:

```bash
python3.14 -m conversation_segmentation.main segment
```

## Processing contract

1. Scan `kyma_agent_conversation:*` keys without blocking Redis; deduplicate and sort session IDs before applying an
   optional limit.
2. Pair each human message with its final AI answer, skipping intermediate tool-call messages and incomplete turns.
3. Compare each conversation with its HANA watermark and classify only new turns. A failed classification stops that
   conversation's contiguous prefix so the failed turn is retried on the next run.
4. Canonicalize each model proposal into `area/intent/capability-slug` and merge it into the durable
   `(conversation_hash, topic_key)` assignment.
5. Derive assignment identity from the session ID plus first-turn fingerprint, so a reused session ID starts a distinct
   historical conversation while the session-keyed watermark detects continuation.
6. Commit touched assignments and watermarks every configured batch.
7. Insert a run row and atomically replace the cumulative aggregate snapshot after processing completes.

The primary metric is `DISTINCT_CONVERSATION_COUNT`; cumulative `TURN_COUNT` is retained separately. Assignments and
watermarks are retained together for cumulative analytics. An unchanged rerun classifies no turns and rebuilds the same
aggregate from durable assignments.

## Persistence

The connecting `DATABASE_USER` owns four configurable tables:

| Default table | Purpose |
|---|---|
| `CONVERSATION_ANALYSIS_RUN` | Completed-run history, token usage, turn and failure counts. |
| `CONVERSATION_TOPIC_ASSIGNMENT` | Cumulative `(conversation_hash, topic_key)` assignments. |
| `CONVERSATION_TOPIC_AGGREGATE` | Current reporting snapshot by topic. |
| `CONVERSATION_TOPIC_WATERMARK` | Retained processed-turn count and first-turn fingerprint per session. |

Raw Redis session IDs are stored only as SHA-256 hashes. Complete prompts, responses, tool payloads, and model reasoning
are not written to HANA. Capability, label, and summary are model-generated conversation-derived text and pass through
best-effort identifier scrubbing; they are not guaranteed identifier-free. HANA access and retention must reflect that
data classification.

## Configuration

Settings are loaded from `CONFIG_PATH` and environment variables through `python-decouple`.

| Setting | Default | Meaning |
|---|---|---|
| `KYMA_AGENT_CONVERSATION_PREFIX` | `kyma_agent_conversation:` | Redis key prefix. |
| `SEGMENTATION_MODEL_NAME` | `anthropic--claude-4.6-sonnet` | Structured classification model. |
| `SEGMENTATION_RUN_TABLE` | `CONVERSATION_ANALYSIS_RUN` | Run table. |
| `SEGMENTATION_ASSIGNMENT_TABLE` | `CONVERSATION_TOPIC_ASSIGNMENT` | Assignment table. |
| `SEGMENTATION_AGGREGATE_TABLE` | `CONVERSATION_TOPIC_AGGREGATE` | Aggregate table. |
| `SEGMENTATION_WATERMARK_TABLE` | `CONVERSATION_TOPIC_WATERMARK` | Watermark table. |
| `SEGMENTATION_MAX_CONVERSATIONS` | `0` | Maximum conversations; `0` processes all. |
| `SEGMENTATION_PROGRESS_LOG_INTERVAL` | `10` | Progress-log interval in processed turns. |
| `SEGMENTATION_BATCH_SIZE` | `25` | Conversations per HANA checkpoint. |

Redis, HANA, and model credentials use the normal Companion settings. The job intentionally logs counts only.

`TAXONOMY_VERSION` is a persistence compatibility boundary. A run fails before processing when existing run history or
assignments use another version; changing taxonomy requires an explicit migration, table reset, or versioned table set.

## Scaling

Transcript payloads are fetched one at a time, so they are not all resident simultaneously; peak transcript memory still
scales with the largest conversation. The Redis session-ID list and all retained HANA watermarks and assignments are
loaded for each run, so baseline memory and startup time scale with cumulative corpus size. This design targets current
Companion volumes; substantially larger histories require batched state reads and database-side aggregation.

## Code map

- `main.py` — orchestration and CLI entrypoint.
- `redis_reader.py` — transcript scanning and turn pairing.
- `segmenter.py` / `taxonomy.py` — structured model output.
- `canonicalizer.py` — topic keys and best-effort identifier scrubbing.
- `aggregator.py` — cumulative assignments and aggregate rows.
- `hana_writer.py` — table creation, checkpoints, snapshots, and transactions.
- `watermark.py` — session hashing and incremental bookmarks.

Internal deployment procedures, landscape validation records, and the ready-to-edit Job manifest are maintained in the
AI Force repository under `docs/how-tos/conversation-topic-analysis` and `docs/evaluations/conversation-topic-analysis`.
