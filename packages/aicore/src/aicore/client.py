"""SAP AI Core OAuth2 token fetching and deployment URL resolution."""

import threading
import time

import httpx
from decouple import config


class AICoreClient:
    """Fetches OAuth2 tokens and resolves deployment URLs for SAP AI Core.

    Credentials are read from environment variables (or config.json keys):
      AICORE_AUTH_URL, AICORE_BASE_URL, AICORE_CLIENT_ID,
      AICORE_CLIENT_SECRET, AICORE_RESOURCE_GROUP
    """

    def __init__(self) -> None:
        self._auth_url: str = config("AICORE_AUTH_URL")
        self._base_url: str = config("AICORE_BASE_URL").rstrip("/")
        self._client_id: str = config("AICORE_CLIENT_ID")
        self._client_secret: str = config("AICORE_CLIENT_SECRET")
        self._resource_group: str = config("AICORE_RESOURCE_GROUP", default="default")

        self._lock = threading.Lock()
        self._token: str = ""
        self._token_exp: float = 0.0
        self._deployment_cache: dict[str, str] = {}

    def get_token(self) -> str:
        """Return a cached or freshly fetched OAuth2 bearer token."""
        with self._lock:
            if self._token and time.time() < self._token_exp:
                return self._token

            resp = httpx.post(
                f"{self._auth_url}/oauth/token",
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp.raise_for_status()
            body = resp.json()
            self._token = body["access_token"]
            self._token_exp = time.time() + body["expires_in"] - 60
            return self._token

    def get_deployment_url(self, deployment_id: str) -> str:
        """Return the deploymentUrl for the given deployment ID (cached)."""
        with self._lock:
            if deployment_id in self._deployment_cache:
                return self._deployment_cache[deployment_id]

        token = self.get_token()
        resp = httpx.get(
            f"{self._base_url}/lm/deployments/{deployment_id}",
            headers={
                "Authorization": f"Bearer {token}",
                "AI-Resource-Group": self._resource_group,
            },
        )
        resp.raise_for_status()
        body = resp.json()
        url: str = body.get("deploymentUrl", "")
        if not url:
            raise ValueError(f"Deployment {deployment_id!r} has no deploymentUrl (not running?)")

        with self._lock:
            self._deployment_cache[deployment_id] = url
        return url
