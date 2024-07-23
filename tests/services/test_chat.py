import asyncio

import pytest

from services.chat import handle_request, init_chat

pytestmark = pytest.mark.asyncio(scope="module")

"""
It’s highly recommended for neighboring tests to use the same event loop scope. For example, 
all tests in a class or module should use the same scope. Assigning neighboring tests to different 
event loop scopes is discouraged as it can make test code hard to follow. For references:
- https://pytest-asyncio.readthedocs.io/en/latest/concepts.html#test-discovery-modes
- https://pytest-asyncio.readthedocs.io/en/latest/how-to-guides/run_module_tests_in_same_loop.html
"""
loop: asyncio.AbstractEventLoop


async def test_init_chat():
    global loop  # noqa F811
    actual_result = await init_chat()
    expected_result = {"message": "Chat is initialized!"}
    assert expected_result == actual_result


async def test_process_chat_request():
    global loop  # noqa F811
    async for event in handle_request():
        assert isinstance(event, str)
        assert event.startswith('{"step":')
        assert event.endswith("}\n")
