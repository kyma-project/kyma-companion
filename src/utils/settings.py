from decouple import config
from dotenv import load_dotenv

# Load all variables from .env into the environment
# necessary to implicitly import AI Core Env Vars
load_dotenv()

LOG_LEVEL = config("LOG_LEVEL", default="INFO")
# Redis
REDIS_HOST = config("REDIS_HOST", default="localhost")
REDIS_PORT = config("REDIS_PORT", default=6379, cast=int)
REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"
# Langfuse
LANGFUSE_SECRET_KEY = config("LANGFUSE_SECRET_KEY")
LANGFUSE_PUBLIC_KEY = config("LANGFUSE_PUBLIC_KEY")
LANGFUSE_HOST = config("LANGFUSE_HOST")
