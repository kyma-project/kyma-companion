"""A2A Router for Kyma Companion.

This module provides the FastAPI router that exposes Kyma Companion
as an A2A-compatible agent for inter-agent communication.
"""

from functools import lru_cache

from a2a.server.apps import A2AStarletteApplication
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import (
    InMemoryTaskStore,
)
from starlette.applications import Starlette

from agents.graph import CompanionGraph
from agents.memory.async_redis_checkpointer import get_async_redis_saver
from routers.common import API_PREFIX
from services.a2a.a2a_executor import CompanionA2AExecutor
from services.a2a.agent_card import get_agent_card
from utils.config import get_config
from utils.logging import get_logger
from utils.models.factory import ModelFactory
from utils.settings import (
    HOST_NAME,
)

logger = get_logger(__name__)
A2A_ROUTER_PREFIX = f"{API_PREFIX}/a2a"


@lru_cache(maxsize=1)
def get_companion_graph() -> CompanionGraph:
    """Get or create the CompanionGraph singleton for A2A."""
    config = get_config()
    model_factory = ModelFactory(config=config)
    models = model_factory.create_models()
    checkpointer = get_async_redis_saver()
    return CompanionGraph(models, memory=checkpointer)


def get_a2a_app() -> Starlette:
    """Get the A2A application instance."""
    # Create the Request Handler
    handler = DefaultRequestHandler(
        agent_executor=CompanionA2AExecutor(get_companion_graph()), task_store=InMemoryTaskStore()
    )

    # Build the A2A Starlette/FastAPI Application
    a2a_app = A2AStarletteApplication(
        agent_card=get_agent_card(f"{HOST_NAME}/a2a/"),  # Base URL for the agent card
        http_handler=handler,
    )
    return a2a_app.build()
