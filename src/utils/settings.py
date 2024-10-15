# Load all variables from .env into the environment
# necessary to implicitly import AI Core Env Vars
import logging
import os
import sys

from decouple import Config, RepositoryEnv, config
from dotenv import find_dotenv, load_dotenv


def is_running_pytest() -> bool:
    """Check if the code is running with pytest.
    This is needed to identify if tests are running.
    """
    return "pytest" in sys.modules


project_root = os.path.dirname(os.path.abspath(__file__))

if is_running_pytest():
    # Use .test.env for tests
    env_path = find_dotenv(".test.env")
    if env_path and os.path.exists(env_path):
        config = Config(RepositoryEnv(env_path))
        load_dotenv(".test.env")
    else:
        logging.warning("No .test.env file found. Using .env file.")
        load_dotenv()
else:
    load_dotenv()

LOG_LEVEL = config("LOG_LEVEL", default="INFO")
# Redis
REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
# Langfuse
LANGFUSE_SECRET_KEY = config("LANGFUSE_SECRET_KEY", default="dummy")
LANGFUSE_PUBLIC_KEY = config("LANGFUSE_PUBLIC_KEY", default="dummy")
LANGFUSE_HOST = config("LANGFUSE_HOST", default="localhost")
