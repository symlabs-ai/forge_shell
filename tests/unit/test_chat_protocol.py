"""Unit tests for chat protocol — send_chat/get_chat in clients and bridge."""
import asyncio
import json
import queue
import pytest

from unittest.mock import AsyncMock, MagicMock, patch

from src.infrastructure.collab.host_relay_client import HostRelayClient
from src.infrastructure.collab.viewer_client import ViewerClient
from src.infrastructure.collab.agent_client import AgentClient
from src.infrastructure.collab.relay_bridge import RelayBridge


class TestHostRelayClientChat:
    @pytest.mark.asyncio
    async def test_send_chat(self):
        client = HostRelayClient("ws://localhost:8060", "sess1", "token1")
        client._ws = AsyncMock()
        await client.send_chat("hello", sender="host")
        client._ws.send.assert_called_once()
        sent = json.loads(client._ws.send.call_args[0][0])
        assert sent["type"] == "chat"
        assert sent["session_id"] == "sess1"
        assert sent["payload"]["text"] == "hello"
        assert sent["payload"]["sender"] == "host"

    @pytest.mark.asyncio
    async def test_receive_chat(self):
        client = HostRelayClient("ws://localhost:8060", "sess1", "token1")
        received = []

        def on_chat(payload):
            received.append(payload)

        # Simulate receive loop with a chat message
        chat_msg = json.dumps({
            "type": "chat",
            "session_id": "sess1",
            "payload": {"text": "hi", "sender": "viewer"},
        }).encode()

        async def fake_ws_iter():
            yield chat_msg

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: fake_ws_iter()
        client._ws = mock_ws

        await client._receive_loop(on_suggest=None, on_chat=on_chat)
        assert len(received) == 1
        assert received[0]["text"] == "hi"
        assert received[0]["sender"] == "viewer"


class TestViewerClientChat:
    @pytest.mark.asyncio
    async def test_send_chat(self):
        client = ViewerClient("ws://localhost:8060", "sess1", "token1")
        client._ws = AsyncMock()
        await client.send_chat("oi", sender="viewer")
        client._ws.send.assert_called_once()
        sent = json.loads(client._ws.send.call_args[0][0])
        assert sent["type"] == "chat"
        assert sent["payload"]["text"] == "oi"
        assert sent["payload"]["sender"] == "viewer"

    @pytest.mark.asyncio
    async def test_receive_chat(self):
        client = ViewerClient("ws://localhost:8060", "sess1", "token1")
        received = []

        def on_chat(payload):
            received.append(payload)

        chat_msg = json.dumps({
            "type": "chat",
            "session_id": "sess1",
            "payload": {"text": "hello", "sender": "host"},
        }).encode()

        async def fake_ws_iter():
            yield chat_msg

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: fake_ws_iter()
        client._ws = mock_ws

        await client._receive_loop(on_output=None, on_chat=on_chat)
        assert len(received) == 1
        assert received[0]["text"] == "hello"


class TestAgentClientChat:
    @pytest.mark.asyncio
    async def test_send_chat(self):
        client = AgentClient("ws://localhost:8060", "sess1", "token1")
        client._ws = AsyncMock()
        await client.send_chat("sugestão via chat", sender="agent")
        client._ws.send.assert_called_once()
        sent = json.loads(client._ws.send.call_args[0][0])
        assert sent["type"] == "chat"
        assert sent["payload"]["text"] == "sugestão via chat"
        assert sent["payload"]["sender"] == "agent"

    @pytest.mark.asyncio
    async def test_receive_chat(self):
        client = AgentClient("ws://localhost:8060", "sess1", "token1")
        received = []

        def on_chat(payload):
            received.append(payload)

        chat_msg = json.dumps({
            "type": "chat",
            "session_id": "sess1",
            "payload": {"text": "msg from host", "sender": "host"},
        }).encode()

        async def fake_ws_iter():
            yield chat_msg

        mock_ws = AsyncMock()
        mock_ws.__aiter__ = lambda self: fake_ws_iter()
        client._ws = mock_ws

        await client._receive_loop(on_output=None, on_suggest_ack=None, on_chat=on_chat)
        assert len(received) == 1
        assert received[0]["text"] == "msg from host"


class TestRelayBridgeChat:
    def test_send_chat_enqueues(self):
        bridge = RelayBridge("ws://localhost:8060", "sess1", "token1")
        bridge.send_chat("hello", sender="host")
        msg = bridge._chat_out_queue.get_nowait()
        assert msg["text"] == "hello"
        assert msg["sender"] == "host"

    def test_get_chat_empty(self):
        bridge = RelayBridge("ws://localhost:8060", "sess1", "token1")
        assert bridge.get_chat() is None

    def test_get_chat_returns_message(self):
        bridge = RelayBridge("ws://localhost:8060", "sess1", "token1")
        bridge._chat_queue.put_nowait({"text": "hi", "sender": "viewer"})
        msg = bridge.get_chat()
        assert msg is not None
        assert msg["text"] == "hi"
        assert msg["sender"] == "viewer"

    def test_get_chat_drains_one_at_a_time(self):
        bridge = RelayBridge("ws://localhost:8060", "sess1", "token1")
        bridge._chat_queue.put_nowait({"text": "msg1", "sender": "a"})
        bridge._chat_queue.put_nowait({"text": "msg2", "sender": "b"})
        msg1 = bridge.get_chat()
        msg2 = bridge.get_chat()
        msg3 = bridge.get_chat()
        assert msg1["text"] == "msg1"
        assert msg2["text"] == "msg2"
        assert msg3 is None
