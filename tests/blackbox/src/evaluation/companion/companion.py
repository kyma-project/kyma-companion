import json
import time
from http import HTTPStatus
from logging import Logger
from typing import Any

import requests
from common.config import Config
from common.metrics import Metrics
from pydantic import BaseModel

from evaluation.companion.response_models import (
    ConversationResponse,
    InitialQuestionsResponse,
)


class ConversationPayload(BaseModel):
    """Payload for the Companion API conversation."""

    query: str = ""
    resource_kind: str
    resource_api_version: str = ""
    resource_name: str = ""
    namespace: str = ""


class CompanionClient:
    """Client for the Companion API."""

    config: Config

    def __init__(self, config: Config):
        self.config = config

    def __get_headers(self) -> dict:
        """Returns the headers for the Companion API requests."""
        return {
            "Authorization": f"Bearer {self.config.companion_token}",
            "X-Cluster-Certificate-Authority-Data": self.config.test_cluster_ca_data,
            "X-Cluster-Url": self.config.test_cluster_url,
            "X-K8s-Authorization": self.config.test_cluster_auth_token,
            "Content-Type": "application/json",
        }

    def fetch_initial_questions(
        self, payload: ConversationPayload, logger: Logger
    ) -> InitialQuestionsResponse:
        """Calls the Companion API to get the initial questions."""
        logger.debug(
            f"querying Companion: {self.config.companion_api_url} for initial questions..."
        )

        req_session = requests.Session()
        start_time = time.time()
        response = req_session.post(
            f"{self.config.companion_api_url}/api/conversations",
            json.dumps(payload.model_dump()),
            headers=self.__get_headers(),
        )
        if response.status_code != HTTPStatus.OK:
            raise ValueError(
                f"failed to get response (status: {response.status_code}). Response: {response.text}"
            )

        # record the response time.
        Metrics.get_instance().record_init_conversation_response_time(
            time.time() - start_time
        )

        # Check if the response structure is valid, and then return the response.
        return InitialQuestionsResponse.model_validate_json(response.content)

    def get_companion_response(
        self, conversation_id: str, payload: ConversationPayload, logger: Logger
    ) -> ConversationResponse:
        """Returns the response and the chunks from the Companion API"""
        headers = self.__get_headers()
        headers["session-id"] = conversation_id

        uri = f"{self.config.companion_api_url}/api/conversations/{conversation_id}/messages"
        req_session = requests.Session()
        start_time = time.time()
        response = req_session.post(
            uri, json.dumps(payload.model_dump()), headers=headers, stream=True
        )
        if response.status_code != HTTPStatus.OK:
            raise ValueError(
                f"failed to get response from the utils API (status: {response.status_code}). Response: {response.text}"
            )

        answer, chunks = self.__extract_final_response(response)

        # record the response time.
        Metrics.get_instance().record_conversation_response_time(
            time.time() - start_time
        )

        return ConversationResponse.model_validate_json(
            json.dumps(
                {
                    "answer": answer,
                    "chunks": chunks,
                }
            )
        )

    def __extract_final_response(self, response: Any) -> tuple[str, list]:
        """Read the stream response and extract the final response from it."""
        obj = None
        chunks = []
        start_time = time.time()
        for chunk in response.iter_lines():
            # Check for timeout
            if time.time() - start_time > self.config.streaming_response_timeout:
                raise Exception("Timeout while waiting for the final response")

            # sometimes it can return multiple chunks in the response.
            # so we need to extract the last chunk.
            lines = chunk.splitlines()
            try:
                obj = json.loads(lines[-1])
            except json.JSONDecodeError as e:
                raise Exception(f"returned chunk is not valid json: {chunk}") from e

            # append the obj to the chunks list.
            chunks.append(obj)

            if "event" not in obj:
                raise Exception(f"'event' key not found in the response: {obj}")

            if obj["event"] == "unknown":
                raise Exception(f"Unknown event in the chunk response: {obj}")

        if obj is None or not obj["data"]:
            raise Exception("No response found in the stream")

        if "error" in obj["data"] and obj["data"]["error"]:
            raise Exception(f"Error in response: {obj['data']['error']}")

        if not obj["data"]["answer"] or not obj["data"]["answer"]["content"]:
            raise Exception("No response found in the stream")

        return obj["data"]["answer"]["content"], chunks
