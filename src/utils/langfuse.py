from langfuse.callback import CallbackHandler

from utils.settings import (
    LANGFUSE_ENABLED,
    LANGFUSE_HOST,
    LANGFUSE_PUBLIC_KEY,
    LANGFUSE_SECRET_KEY,
)
from utils.utils import string_to_bool

handler = CallbackHandler(
    secret_key=LANGFUSE_SECRET_KEY,
    public_key=LANGFUSE_PUBLIC_KEY,
    host=LANGFUSE_HOST,
    enabled=string_to_bool(LANGFUSE_ENABLED),
)
