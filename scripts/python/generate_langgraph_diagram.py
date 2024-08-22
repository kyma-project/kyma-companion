import os

from dotenv import load_dotenv

from agents.graph import KymaGraph

load_dotenv()

from IPython.display import Image  # noqa: E402

from agents.memory.redis_checkpointer import (  # noqa: E402
    RedisSaver,
    initialize_async_pool,
)
from agents.supervisor.agent import SupervisorAgent  # noqa: E402
from utils.models import LLM, ModelFactory  # noqa: E402

if not os.getenv("MODELS_CONFIG_FILE_PATH"):
    os.environ["MODELS_CONFIG_FILE_PATH"] = "../config/config.yml"

supervisor_agent: SupervisorAgent
model_factory = ModelFactory()

model = model_factory.create_model(LLM.GPT4O_MODEL)
memory = RedisSaver(
    async_connection=initialize_async_pool(url=f"{os.getenv('REDIS_URL')}/0")
)
graph = KymaGraph(model, memory)

try:
    png_bytes = Image(graph.graph.get_graph().draw_mermaid_png())
    # store the image in a file
    with open("../graph.png", "wb") as f:
        f.write(png_bytes.data)
except Exception:
    raise
