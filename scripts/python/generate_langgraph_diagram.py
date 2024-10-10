"""
This script generates a LangGraph diagram using the KymaGraph class and saves it as a PNG file.
It initializes the necessary components, including the model and memory, and then creates the graph.

Usage:
    poetry run python scripts/python/generate_langgraph_diagram.py
    or
    python scripts/python/generate_langgraph_diagram.py

Environment Variables:
    MODELS_CONFIG_FILE_PATH: Path to the models configuration file (default: "config/config.yml")

Output:
    - graph.png: The generated LangGraph diagram saved as a PNG file.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../../src"))

from IPython.display import Image  # noqa: E402

from agents.graph import CompanionGraph
from agents.memory.redis_checkpointer import (  # noqa: E402
    RedisSaver,
    initialize_async_pool,
)
from agents.supervisor.agent import SupervisorAgent  # noqa: E402
from utils.models import LLM, ModelFactory  # noqa: E402
from utils.settings import REDIS_URL

if not os.getenv("MODELS_CONFIG_FILE_PATH"):
    os.environ["MODELS_CONFIG_FILE_PATH"] = "config/config.yml"

supervisor_agent: SupervisorAgent
model_factory = ModelFactory()

model = model_factory.create_model(LLM.GPT4O)
memory = RedisSaver(async_connection=initialize_async_pool(url=REDIS_URL))
graph = CompanionGraph(model, memory)

try:
    png_bytes = Image(graph.graph.get_graph(xray=1).draw_mermaid_png())
    # store the image in a file
    with open("graph.png", "wb") as f:
        f.write(png_bytes.data)
except Exception:
    raise
