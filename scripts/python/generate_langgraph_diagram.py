"""
This script generates a LangGraph diagram using the CompanionGraph class and saves it as a PNG file.
It initializes the necessary components, including the model and memory, and then creates the graph.

It generates three diagrams:
- companion.png: The generated LangGraph diagram for the companion graph.
- kyma_agent.png: The generated LangGraph diagram for the kyma agent subgraph.
- k8s_agent.png: The generated LangGraph diagram for the k8s agent subgraph.

Usage:
    poetry run python scripts/python/generate_langgraph_diagram.py
    or
    python scripts/python/generate_langgraph_diagram.py

Environment Variables:
    CONFIG_PATH: Path to the models configuration file (default: "config/config.yml")

Output:
    - companion.png: The generated LangGraph diagram saved as a PNG file.
    - kyma_agent.png: The generated LangGraph diagram saved as a PNG file.
    - k8s_agent.png: The generated LangGraph diagram saved as a PNG file.
"""

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../../src"))

from IPython.display import (
    Image,  # noqa: E402
)
from langchain_core.runnables.graph import MermaidDrawMethod

from agents.graph import CompanionGraph
from agents.k8s.agent import KubernetesAgent
from agents.kyma.agent import KymaAgent
from agents.memory.async_redis_checkpointer import AsyncRedisSaver
from utils.config import get_config
from utils.models.factory import ModelFactory, ModelType  # noqa: E402
from utils.settings import REDIS_DB_NUMBER, REDIS_HOST, REDIS_PORT

if not os.getenv("CONFIG_PATH"):
    os.environ["CONFIG_PATH"] = "config/config.json"
config = get_config()
model_factory = ModelFactory(config=config)
models = model_factory.create_models()

memory = AsyncRedisSaver.from_conn_info(
    host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB_NUMBER
)
graph = CompanionGraph(models, memory)

print("Generating graph diagram for the companion graph...")
try:
    png_bytes = Image(
        graph.graph.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API,
        )
    )
    # store the image in a file
    with open("companion.png", "wb") as f:
        f.write(png_bytes.data)
except Exception:
    raise
print("companion.png generated")

print("Generating graph diagram for the kyma agent...")
kyma_agent = KymaAgent(models)
try:
    png_bytes = Image(
        kyma_agent.graph.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API,
        )
    )
    # store the image in a file
    with open("kyma_agent.png", "wb") as f:
        f.write(png_bytes.data)
except Exception:
    raise

print("kyma_agent.png generated")

print("Generating graph diagram for the k8s agent...")
k8s_agent = KubernetesAgent(models[ModelType.GPT4O])
try:
    png_bytes = Image(
        k8s_agent.graph.get_graph().draw_mermaid_png(
            draw_method=MermaidDrawMethod.API,
        )
    )
    # store the image in a file
    with open("k8s_agent.png", "wb") as f:
        f.write(png_bytes.data)
except Exception:
    raise
print("k8s_agent.png generated")
