from routes.api import chatting, init_chat


def test_init_chat():
    assert init_chat() == {"message": "Chat is initialized!"}


def test_chatting():
    assert chatting() == {"message": "Hello!"}
