"""Job settings, resolved from env / mounted config.json via python-decouple.

Importing utils.settings (transitively) triggers load_env_from_json(), which
loads CONFIG_PATH's JSON into os.environ, so DATABASE_*/AICORE_*/REDIS_* are set.
"""

from decouple import config

# The prefix constant lives in the app router; re-declared here to avoid importing
# the FastAPI router stack into a batch job. Keep in sync with
# src/routers/common.py:KYMA_AGENT_CONVERSATION_PREFIX.
CONVERSATION_KEY_PREFIX: str = config("KYMA_AGENT_CONVERSATION_PREFIX", default="kyma_agent_conversation:")

SEG_MODEL_NAME: str = config("SEGMENTATION_MODEL_NAME", default="anthropic--claude-4.6-sonnet")
LANDSCAPE: str = config("SEGMENTATION_LANDSCAPE", default="unknown")
AGG_TABLE: str = config("SEGMENTATION_TABLE", default="CONVERSATION_SEGMENTATION")
WATERMARK_TABLE: str = config("SEGMENTATION_WATERMARK_TABLE", default="CONVERSATION_SEGMENTATION_WATERMARK")
# Match the Redis conversation TTL (7d) so a bookmark is pruned ~7d after its chat leaves Redis.
WATERMARK_TTL_SECONDS: int = config("SEGMENTATION_WATERMARK_TTL_SECONDS", default=604800, cast=int)
