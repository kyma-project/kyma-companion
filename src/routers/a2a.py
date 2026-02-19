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


# def _extract_text_from_message(message_data: dict) -> str:
#     """Extract text content from an A2A message."""
#     text_parts = []
#     for part in message_data.get("parts", []):
#         if isinstance(part, dict) and "text" in part:
#             text_parts.append(part["text"])
#     return " ".join(text_parts)


# def _extract_response_from_chunk(chunk: str) -> str | None:
#     """Extract the response content from a graph chunk."""
#     try:
#         chunk_data = json.loads(chunk)
#         for node_name, node_output in chunk_data.items():
#             if isinstance(node_output, dict) and "messages" in node_output:
#                 messages = node_output["messages"]
#                 for msg in messages:
#                     if isinstance(msg, dict) and "content" in msg:
#                         return str(msg["content"])
#                     elif hasattr(msg, "content"):
#                         return str(getattr(msg, "content"))
#     except (json.JSONDecodeError, KeyError, TypeError):
#         pass
#     return None


# @router.get("/.well-known/agent.json", response_model=None)
# async def get_agent_card_endpoint(request: Request) -> JSONResponse:
#     """
#     Return the A2A Agent Card.
    
#     The Agent Card describes the capabilities and skills of Kyma Companion
#     to other agents in the A2A ecosystem.
#     """
#     base_url = str(request.base_url).rstrip("/")
#     card = get_agent_card(f"{base_url}{A2A_ROUTER_PREFIX}")
#     return JSONResponse(content=card.model_dump(mode="json", exclude_none=True))


# @router.post("")
# @router.post("/")
# async def handle_a2a_request(
#     request: Request,
#     graph: Annotated[CompanionGraph, Depends(get_companion_graph)],
# ):
#     """
#     Main A2A JSON-RPC endpoint.
    
#     Handles all A2A protocol methods including:
#     - message/send: Send a message and get a response
#     - message/stream: Send a message and stream the response
#     - tasks/get: Get task status
#     - tasks/cancel: Cancel a task
#     """
#     body = await request.json()
#     method = body.get("method", "")
#     params = body.get("params", {})
#     request_id = body.get("id")
    
#     logger.info(f"A2A request received: method={method}, id={request_id}")
    
#     # Route based on method
#     if method in ("message/send", "tasks/send"):
#         return await _handle_message_send(request, graph, params, request_id)
#     elif method in ("message/stream", "tasks/sendSubscribe"):
#         return await _handle_message_stream(request, graph, params, request_id)
#     elif method == "tasks/get":
#         task_id = params.get("id", "")
#         return JSONResponse(content={
#             "jsonrpc": "2.0",
#             "id": request_id,
#             "result": {
#                 "id": task_id,
#                 "status": {"state": "unknown"},
#             }
#         })
#     elif method == "tasks/cancel":
#         task_id = params.get("id", "")
#         return JSONResponse(content={
#             "jsonrpc": "2.0",
#             "id": request_id,
#             "result": {
#                 "id": task_id,
#                 "status": {"state": "canceled"},
#             }
#         })
#     else:
#         return JSONResponse(
#             content={
#                 "jsonrpc": "2.0",
#                 "id": request_id,
#                 "error": {
#                     "code": -32601,
#                     "message": f"Method not found: {method}",
#                 }
#             },
#             status_code=400,
#         )


# async def _handle_message_send(
#     request: Request,
#     graph: CompanionGraph,
#     params: dict,
#     request_id: str | None,
# ) -> JSONResponse:
#     """Handle message/send method - synchronous response."""
#     try:
#         message_data = params.get("message", {})
#         task_id = params.get("id") or str(uuid4())
        
#         # Extract text from A2A message
#         query_text = _extract_text_from_message(message_data)
#         if not query_text:
#             return JSONResponse(
#                 content={
#                     "jsonrpc": "2.0",
#                     "id": request_id,
#                     "error": {
#                         "code": -32602,
#                         "message": "No message text provided",
#                     }
#                 },
#                 status_code=400,
#             )
        
#         # Check for K8s credentials in headers
#         headers = dict(request.headers)
#         cluster_url = headers.get("x-cluster-url")
#         cluster_ca = headers.get("x-cluster-certificate-authority-data")
#         k8s_auth = headers.get("x-k8s-authorization")
        
#         if not (cluster_url and cluster_ca and k8s_auth):
#             return JSONResponse(
#                 content={
#                     "jsonrpc": "2.0",
#                     "id": request_id,
#                     "error": {
#                         "code": -32602,
#                         "message": "Kubernetes cluster credentials required. "
#                                    "Provide x-cluster-url, x-cluster-certificate-authority-data, "
#                                    "and x-k8s-authorization headers.",
#                     }
#                 },
#                 status_code=400,
#             )
        
#         # Create K8s client
#         from services.k8s import K8sAuthHeaders, K8sClient
#         k8s_headers = K8sAuthHeaders(
#             x_cluster_url=cluster_url,
#             x_cluster_certificate_authority_data=cluster_ca,
#             x_k8s_authorization=k8s_auth,
#         )
#         k8s_client = K8sClient(k8s_headers)
        
#         # Create Companion message
#         companion_message = CompanionMessage(
#             query=query_text,
#             resource_kind=None,
#             resource_api_version=None,
#             resource_name=None,
#             namespace=None,
#         )
        
#         # Process through the graph
#         response_parts: list[str] = []
#         async for chunk in graph.astream(
#             conversation_id=task_id,
#             message=companion_message,
#             k8s_client=k8s_client,
#         ):
#             content = _extract_response_from_chunk(chunk)
#             if content:
#                 response_parts.append(content)
        
#         # Get the final response
#         final_response = response_parts[-1] if response_parts else "Unable to process request."
        
#         return JSONResponse(content={
#             "jsonrpc": "2.0",
#             "id": request_id,
#             "result": {
#                 "id": task_id,
#                 "status": {"state": "completed"},
#                 "artifacts": [{
#                     "parts": [{"type": "text", "text": final_response}],
#                 }],
#             }
#         })
        
#     except Exception as e:
#         logger.exception("Error processing A2A message/send")
#         return JSONResponse(
#             content={
#                 "jsonrpc": "2.0",
#                 "id": request_id,
#                 "error": {
#                     "code": -32000,
#                     "message": str(e),
#                 }
#             },
#             status_code=500,
#         )


# async def _handle_message_stream(
#     request: Request,
#     graph: CompanionGraph,
#     params: dict,
#     request_id: str | None,
# ) -> StreamingResponse:
#     """Handle message/stream method with SSE."""
    
#     async def event_generator():
#         try:
#             message_data = params.get("message", {})
#             task_id = params.get("id") or str(uuid4())
            
#             # Extract text from A2A message
#             query_text = _extract_text_from_message(message_data)
#             if not query_text:
#                 error_event = {
#                     "jsonrpc": "2.0",
#                     "id": request_id,
#                     "error": {
#                         "code": -32602,
#                         "message": "No message text provided",
#                     }
#                 }
#                 yield f"data: {json.dumps(error_event)}\n\n"
#                 return
            
#             # Check for K8s credentials
#             headers = dict(request.headers)
#             cluster_url = headers.get("x-cluster-url")
#             cluster_ca = headers.get("x-cluster-certificate-authority-data")
#             k8s_auth = headers.get("x-k8s-authorization")
            
#             if not (cluster_url and cluster_ca and k8s_auth):
#                 error_event = {
#                     "jsonrpc": "2.0",
#                     "id": request_id,
#                     "error": {
#                         "code": -32602,
#                         "message": "Kubernetes cluster credentials required.",
#                     }
#                 }
#                 yield f"data: {json.dumps(error_event)}\n\n"
#                 return
            
#             # Create K8s client
#             from services.k8s import K8sAuthHeaders, K8sClient
#             k8s_headers = K8sAuthHeaders(
#                 x_cluster_url=cluster_url,
#                 x_cluster_certificate_authority_data=cluster_ca,
#                 x_k8s_authorization=k8s_auth,
#             )
#             k8s_client = K8sClient(k8s_headers)
            
#             # Create Companion message
#             companion_message = CompanionMessage(
#                 query=query_text,
#                 resource_kind=None,
#                 resource_api_version=None,
#                 resource_name=None,
#                 namespace=None,
#             )
            
#             # Send working status
#             working_event = {
#                 "jsonrpc": "2.0",
#                 "id": request_id,
#                 "result": {
#                     "id": task_id,
#                     "status": {"state": "working"},
#                 }
#             }
#             yield f"data: {json.dumps(working_event)}\n\n"
            
#             # Stream responses
#             final_response = ""
#             async for chunk in graph.astream(
#                 conversation_id=task_id,
#                 message=companion_message,
#                 k8s_client=k8s_client,
#             ):
#                 content = _extract_response_from_chunk(chunk)
#                 if content:
#                     final_response = content
#                     # Send incremental update
#                     update_event = {
#                         "jsonrpc": "2.0",
#                         "id": request_id,
#                         "result": {
#                             "id": task_id,
#                             "status": {"state": "working"},
#                             "artifacts": [{
#                                 "parts": [{"type": "text", "text": content}],
#                             }],
#                         }
#                     }
#                     yield f"data: {json.dumps(update_event)}\n\n"
            
#             # Send completion
#             complete_event = {
#                 "jsonrpc": "2.0",
#                 "id": request_id,
#                 "result": {
#                     "id": task_id,
#                     "status": {"state": "completed"},
#                     "artifacts": [{
#                         "parts": [{"type": "text", "text": final_response or "Request processed."}],
#                     }],
#                 }
#             }
#             yield f"data: {json.dumps(complete_event)}\n\n"
            
#         except Exception as e:
#             logger.exception("Error in A2A SSE stream")
#             error_event = {
#                 "jsonrpc": "2.0",
#                 "id": request_id,
#                 "error": {
#                     "code": -32000,
#                     "message": str(e),
#                 }
#             }
#             yield f"data: {json.dumps(error_event)}\n\n"
    
#     return StreamingResponse(
#         event_generator(),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache",
#             "Connection": "keep-alive",
#             "X-Accel-Buffering": "no",
#         },
#     )


# @router.post("/tasks/send")
# async def send_task(
#     request: Request,
#     graph: Annotated[CompanionGraph, Depends(get_companion_graph)],
# ) -> JSONResponse:
#     """Handle synchronous A2A task requests (legacy endpoint)."""
#     body = await request.json()
#     return await _handle_message_send(request, graph, body, body.get("id"))


# @router.post("/tasks/sendSubscribe")
# async def send_subscribe(
#     request: Request,
#     graph: Annotated[CompanionGraph, Depends(get_companion_graph)],
# ):
#     """Handle streaming A2A task requests (legacy endpoint)."""
#     body = await request.json()
#     return await _handle_message_stream(request, graph, body, body.get("id"))


# @router.get("/tasks/{task_id}")
# async def get_task_status(task_id: str) -> JSONResponse:
#     """Get the status of a task (stateless - not persisted)."""
#     return JSONResponse(
#         content={
#             "id": task_id,
#             "status": {"state": "unknown"},
#             "message": "Task status not available. Tasks are processed synchronously.",
#         },
#         status_code=404,
#     )


# @router.post("/tasks/{task_id}/cancel")
# async def cancel_task(task_id: str) -> JSONResponse:
#     """Cancel an ongoing task."""
#     return JSONResponse(
#         content={
#             "id": task_id,
#             "status": {"state": "canceled"},
#             "message": "Cancellation requested.",
#         }
#     )
