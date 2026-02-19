"""A2A Router for Kyma Companion.

This module provides the FastAPI router that exposes Kyma Companion
as an A2A-compatible agent for inter-agent communication.
"""

import asyncio
import json
from functools import lru_cache
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from starlette.responses import StreamingResponse

from agents.common.data import Message as CompanionMessage
from agents.graph import CompanionGraph
from agents.memory.async_redis_checkpointer import get_async_redis_saver
from routers.common import API_PREFIX
from services.a2a.agent_card import get_agent_card
from services.a2a.a2a_executor import CompanionA2AExecutor
from utils.config import get_config
from utils.logging import get_logger
from utils.models.factory import ModelFactory
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.apps import A2AStarletteApplication
from starlette.applications import Starlette
from a2a.server.tasks import (
    InMemoryTaskStore,
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
        agent_executor=CompanionA2AExecutor(get_companion_graph()),
        task_store=InMemoryTaskStore()
    )

    # Build the A2A Starlette/FastAPI Application
    a2a_app = A2AStarletteApplication(
        agent_card=get_agent_card("http://localhost:8000/a2a/"),  # Base URL for the agent card
        http_handler=handler
    )
    return a2a_app.build()
