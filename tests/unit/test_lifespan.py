import pytest
from fastapi.testclient import TestClient

from main import app


class TestLifespanAllowlistGuard:
    def test_startup_fails_when_allowlist_is_empty(self, monkeypatch):
        # given
        monkeypatch.setattr("services.k8s.ALLOWED_K8S_DOMAINS", [])

        # when / then
        with pytest.raises(RuntimeError, match="ALLOWED_K8S_DOMAINS"), TestClient(app):
            pass

    def test_startup_fails_when_allowlist_has_blank_entry(self, monkeypatch):
        # given
        monkeypatch.setattr("services.k8s.ALLOWED_K8S_DOMAINS", ["kyma.ondemand.com", "   "])

        # when / then
        with pytest.raises(RuntimeError, match="ALLOWED_K8S_DOMAINS"), TestClient(app):
            pass

    def test_startup_succeeds_with_configured_allowlist(self, monkeypatch):
        # given
        monkeypatch.setattr("services.k8s.ALLOWED_K8S_DOMAINS", ["kyma.ondemand.com"])

        # when / then: entering the context runs the lifespan; no RuntimeError means startup passed
        with TestClient(app):
            pass
