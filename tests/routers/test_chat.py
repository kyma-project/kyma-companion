from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from main import app
from services.chat import Chat, ChatInterface


class MockChat(ChatInterface):
    def __init__(self) -> None:
        self.conversations.return_value = {"message": "Chat is initialized!"}
        self.handle_request = MagicMock()

@pytest.fixture(scope='session')
def client():
    test_app = app
    test_app.dependency_overrides[Chat] = MockChat
    return TestClient(test_app)

@pytest.fixture
def test_conversations(client):
    response = client.post("/chat/conversations")
    
    assert response.status_code == 200
