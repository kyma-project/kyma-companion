# Load all variables from .env into the environment
# necessary to implicitly import AI Core Env Vars
import os
import sys

from decouple import Config, RepositoryEnv
from dotenv import load_dotenv, find_dotenv


def is_running_pytest():
    return "pytest" in sys.modules


project_root = os.path.dirname(os.path.abspath(__file__))

if is_running_pytest():
    # Use .test.env for tests
    env_path = find_dotenv(".test.env")
    config = Config(RepositoryEnv(env_path))
    load_dotenv(".test.env")
else:
    # Use .env for normal execution
    env_path = find_dotenv(".env")
    config = Config(RepositoryEnv(env_path))
    load_dotenv()

# Define your settings using the config object

LOG_LEVEL = config("LOG_LEVEL", default="INFO")
# Redis
REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
# Langfuse
LANGFUSE_SECRET_KEY = config("LANGFUSE_SECRET_KEY", default="dummy")
LANGFUSE_PUBLIC_KEY = config("LANGFUSE_PUBLIC_KEY", default="dummy")
LANGFUSE_HOST = config("LANGFUSE_HOST", default="localhost")
