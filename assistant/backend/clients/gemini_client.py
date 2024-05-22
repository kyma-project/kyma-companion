import os

from timeit import default_timer
from ai_api_client_sdk.ai_api_v2_client import AIAPIV2Client
from ai_api_client_sdk.models.deployment_query_response import Deployment
from .gemini import GeminiResponse

from helpers.logging import LogUtil
from .exceptions import InvalidLlmMessages
from .exceptions import ModelServerNotAvailable

logger = LogUtil.get_logger()


class GeminiClient:
    GET_DEPLOYMENTS_ENDPOINT = "/lm/deployments"

    _client = AIAPIV2Client(
        base_url=os.getenv("AICORE_BASE_URL"),
        auth_url=os.getenv("AICORE_AUTH_URL"),
        client_id=os.getenv("AICORE_CLIENT_ID"),
        client_secret=os.getenv("AICORE_CLIENT_SECRET"),
        resource_group=os.getenv("AICORE_RESOURCE_GROUP"),
    )
    _cache = {}

    def __init__(self, deployment_id: str, model_name: str = "gemini-1.0-pro", temperature: int = 0,
                 max_output_tokens: int = 5000):
        self.deployment_id = deployment_id
        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def invoke(self, messages):
        if len(messages) < 1:
            raise InvalidLlmMessages(
                "Invalid messages: {} pass to gemini model".format(messages)
            )

        role = messages[-1].get("role")
        prompt = messages[-1].get("content")

        request_body = {
            "contents": [{"role": role, "parts": {"text": prompt}}],
            "generation_config": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
            },
        }

        start_time = default_timer()
        llm_output: GeminiResponse = GeminiResponse(
            **self._invoke_restapi(
                request_body=request_body,
            )
        )
        end_time = default_timer()
        logger.info(f"Time taken to generate response: {end_time - start_time} seconds")

        logger.info(llm_output)

        llm_response_content = llm_output.candidates[0].content.parts[0].text

        return llm_response_content

    def _invoke_restapi(self, request_body: dict):
        deployment = Deployment.from_dict(
            self._client.rest_client.get(f"{self.GET_DEPLOYMENTS_ENDPOINT}/{self.deployment_id}")
        )
        server_url = deployment.deployment_url
        if not server_url:
            logger.warning("No server is available for model: {}".format(self.model_name))
            raise ModelServerNotAvailable(
                "No server is available for model: {}".format(self.model_name)
            )
        request_url = (
                server_url.replace(self._client.base_url, "") + f"/models/{self.model_name}:"
        )
        if self.model_name.startswith("gemini"):
            request_url += "generateContent"
        else:
            request_url += "predict"

        response = self._client.rest_client.post(request_url, body=request_body)
        return response
