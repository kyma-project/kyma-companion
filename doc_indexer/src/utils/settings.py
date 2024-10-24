# Load all variables from .env into the environment                                                                                                                                                                                                                                                                                                                              ─╯
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
    env_path = find_dotenv(".env.test")
    if env_path and os.path.exists(env_path):
        config = Config(RepositoryEnv(env_path))
        load_dotenv(env_path)
    else:
        logging.warning("No .test.env file found. Using .env file.")
        load_dotenv()
else:
    load_dotenv()

EMBEDDING_MODEL_DEPLOYMENT_ID = config("EMBEDDING_MODEL_DEPLOYMENT_ID")
EMBEDDING_MODEL_NAME = config("EMBEDDING_MODEL_NAME")

DATABASE_URL = config("DATABASE_URL")
DATABASE_PORT = config("DATABASE_PORT", cast=int)
DATABASE_USER = config("DATABASE_USER")
DATABASE_PASSWORD = config("DATABASE_PASSWORD")
