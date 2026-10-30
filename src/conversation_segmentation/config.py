"""Job settings, resolved from env / mounted config.json via python-decouple."""

from decouple import config

from utils.settings import load_env_from_json

_MAX_SEG_MODEL_NAME_LENGTH = 128

# This module is imported before the batch task imports app services. Load the
# mounted config explicitly so SEGMENTATION_* settings work from CONFIG_PATH,
# not only when supplied as pod environment variables.
load_env_from_json()

# The prefix constant lives in the app router; re-declared here to avoid importing
# the FastAPI router stack into a batch job. Keep in sync with
# src/routers/common.py:KYMA_AGENT_CONVERSATION_PREFIX.
CONVERSATION_KEY_PREFIX: str = config("KYMA_AGENT_CONVERSATION_PREFIX", default="kyma_agent_conversation:")
CONVERSATION_INSTANCE_KEY_PREFIX: str = config(
    "KYMA_AGENT_CONVERSATION_INSTANCE_PREFIX", default="kyma_agent_conversation_instance:"
)

SEG_MODEL_NAME: str = config("SEGMENTATION_MODEL_NAME", default="anthropic--claude-4.6-sonnet")
if len(SEG_MODEL_NAME) > _MAX_SEG_MODEL_NAME_LENGTH:
    raise ValueError("SEGMENTATION_MODEL_NAME exceeds the HANA persistence limit")
# Normalized topic-analysis tables, each schema-qualified with the connecting DATABASE_USER.
RUN_TABLE: str = config("SEGMENTATION_RUN_TABLE", default="CONVERSATION_ANALYSIS_RUN")
ASSIGNMENT_TABLE: str = config("SEGMENTATION_ASSIGNMENT_TABLE", default="CONVERSATION_TOPIC_ASSIGNMENT")
AGGREGATE_TABLE: str = config("SEGMENTATION_AGGREGATE_TABLE", default="CONVERSATION_TOPIC_AGGREGATE")
WATERMARK_TABLE: str = config("SEGMENTATION_WATERMARK_TABLE", default="CONVERSATION_TOPIC_WATERMARK")
# Zero means process all matching conversations. A positive value selects the
# first N conversations in deterministic session-id order, primarily for a
# bounded Dev/test run. Negative values are clamped to zero (process all).
MAX_CONVERSATIONS: int = max(0, config("SEGMENTATION_MAX_CONVERSATIONS", default=0, cast=int))
PROGRESS_LOG_INTERVAL: int = max(1, config("SEGMENTATION_PROGRESS_LOG_INTERVAL", default=10, cast=int))
# Conversations are streamed one transcript at a time and progress is checkpointed to
# HANA every BATCH_SIZE conversations. A crash loses at most one batch; a re-run resumes
# from the committed watermarks. Keep > 0.
BATCH_SIZE: int = max(1, config("SEGMENTATION_BATCH_SIZE", default=25, cast=int))
# Retry transient model/provider failures within one Job before leaving the turn at its
# existing watermark and returning a failing process status for Kubernetes to retry.
CLASSIFICATION_MAX_ATTEMPTS: int = max(1, config("SEGMENTATION_CLASSIFICATION_MAX_ATTEMPTS", default=3, cast=int))
CLASSIFICATION_RETRY_BASE_SECONDS: float = max(
    0.0, config("SEGMENTATION_CLASSIFICATION_RETRY_BASE_SECONDS", default=1.0, cast=float)
)
