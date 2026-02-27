"""Integration test: host ↔ viewer ↔ agent chat via relay."""
import asyncio
import json
import pytest
import pytest_asyncio

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

from src.infrastructure.collab.relay_handler import RelayHandler
from src.infrastructure.collab.host_relay_client import HostRelayClient
from src.infrastructure.collab.viewer_client import ViewerClient
from src.infrastructure.collab.agent_client import AgentClient

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(not HAS_WEBSOCKETS, reason="websockets not installed"),
]


@pytest.fixture
def free_port():
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest_asyncio.fixture
async def relay(free_port):
    handler = RelayHandler(host="127.0.0.1", port=free_port)
    task = asyncio.create_task(handler.start())
    await asyncio.sleep(0.1)
    yield handler, free_port
    handler.stop()
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


async def test_host_viewer_chat(relay):
    """Host sends chat, viewer receives it."""
    _, port = relay
    url = f"ws://127.0.0.1:{port}"
    session_id = "test-chat-1"
    token = "pass123"

    viewer_chats = []

    host = HostRelayClient(url, session_id, token)
    viewer = ViewerClient(url, session_id, token)

    await host.connect(on_chat=lambda p: None)
    await asyncio.sleep(0.05)
    await viewer.connect(on_chat=lambda p: viewer_chats.append(p))
    await asyncio.sleep(0.05)

    await host.send_chat("hello from host", sender="host")
    await asyncio.sleep(0.2)

    assert len(viewer_chats) == 1
    assert viewer_chats[0]["text"] == "hello from host"
    assert viewer_chats[0]["sender"] == "host"

    await host.close()
    await viewer.close()


async def test_viewer_host_chat(relay):
    """Viewer sends chat, host receives it."""
    _, port = relay
    url = f"ws://127.0.0.1:{port}"
    session_id = "test-chat-2"
    token = "pass456"

    host_chats = []

    host = HostRelayClient(url, session_id, token)
    viewer = ViewerClient(url, session_id, token)

    await host.connect(on_chat=lambda p: host_chats.append(p))
    await asyncio.sleep(0.05)
    await viewer.connect(on_chat=lambda p: None)
    await asyncio.sleep(0.05)

    await viewer.send_chat("oi from viewer", sender="viewer")
    await asyncio.sleep(0.2)

    assert len(host_chats) == 1
    assert host_chats[0]["text"] == "oi from viewer"
    assert host_chats[0]["sender"] == "viewer"

    await host.close()
    await viewer.close()


async def test_agent_host_chat(relay):
    """Agent sends chat, host receives it."""
    _, port = relay
    url = f"ws://127.0.0.1:{port}"
    session_id = "test-chat-3"
    token = "pass789"

    host_chats = []

    host = HostRelayClient(url, session_id, token)
    agent = AgentClient(url, session_id, token)

    await host.connect(on_chat=lambda p: host_chats.append(p))
    await asyncio.sleep(0.05)
    await agent.connect(on_chat=lambda p: None)
    await asyncio.sleep(0.05)

    await agent.send_chat("suggestion context", sender="agent")
    await asyncio.sleep(0.2)

    assert len(host_chats) == 1
    assert host_chats[0]["text"] == "suggestion context"

    await host.close()
    await agent.close()


async def test_three_way_chat(relay):
    """Host, viewer, and agent all exchange chat messages."""
    _, port = relay
    url = f"ws://127.0.0.1:{port}"
    session_id = "test-chat-4"
    token = "pass000"

    host_chats = []
    viewer_chats = []
    agent_chats = []

    host = HostRelayClient(url, session_id, token)
    viewer = ViewerClient(url, session_id, token)
    agent = AgentClient(url, session_id, token)

    await host.connect(on_chat=lambda p: host_chats.append(p))
    await asyncio.sleep(0.05)
    await viewer.connect(on_chat=lambda p: viewer_chats.append(p))
    await asyncio.sleep(0.05)
    await agent.connect(on_chat=lambda p: agent_chats.append(p))
    await asyncio.sleep(0.05)

    # Host sends
    await host.send_chat("msg from host", sender="host")
    await asyncio.sleep(0.2)

    # Viewer and agent should receive
    assert any(c["text"] == "msg from host" for c in viewer_chats)
    assert any(c["text"] == "msg from host" for c in agent_chats)

    # Viewer sends
    await viewer.send_chat("msg from viewer", sender="viewer")
    await asyncio.sleep(0.2)

    # Host and agent should receive
    assert any(c["text"] == "msg from viewer" for c in host_chats)
    assert any(c["text"] == "msg from viewer" for c in agent_chats)

    await host.close()
    await viewer.close()
    await agent.close()
