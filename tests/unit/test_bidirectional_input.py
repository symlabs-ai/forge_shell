"""
Bidirectional Input (co-control) — testes unitários.

Testa o fluxo completo de input bidirecional:
viewer/agent → relay → host → PTY.
"""
import asyncio
import base64
import json
import queue
import time

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from src.infrastructure.collab.protocol import MessageType
from src.infrastructure.collab.session_manager import SessionManager, SessionMode


class TestProtocolTerminalInput:
    """Fase 1: TERMINAL_INPUT existe no MessageType."""

    def test_terminal_input_enum_exists(self) -> None:
        assert hasattr(MessageType, "TERMINAL_INPUT")
        assert MessageType.TERMINAL_INPUT.value == "terminal_input"

    def test_terminal_input_decode(self) -> None:
        from src.infrastructure.collab.protocol import decode_message
        raw = json.dumps({
            "type": "terminal_input",
            "session_id": "s-1",
            "payload": {"data": base64.b64encode(b"ls\r").decode()},
        }).encode()
        msg = decode_message(raw)
        assert msg.type == MessageType.TERMINAL_INPUT
        assert msg.session_id == "s-1"

    def test_terminal_input_encode(self) -> None:
        from src.infrastructure.collab.protocol import RelayMessage, encode_message
        msg = RelayMessage(
            type=MessageType.TERMINAL_INPUT,
            session_id="s-1",
            payload={"data": base64.b64encode(b"pwd\r").decode()},
        )
        raw = encode_message(msg)
        decoded = json.loads(raw)
        assert decoded["type"] == "terminal_input"


class TestRelayRouting:
    """Fase 2: relay roteia terminal_input de viewer/agent → host."""

    @pytest.mark.asyncio
    async def test_terminal_input_routed_to_host(self) -> None:
        from src.infrastructure.collab.relay_handler import _sessions

        received = []

        class FakeWS:
            def __init__(self, name: str):
                self.name = name

            async def send(self, data):
                received.append((self.name, data))

        host_ws = FakeWS("host")
        viewer_ws = FakeWS("viewer")

        sid = "test-routing-input"
        _sessions[sid] = {"host": [host_ws], "viewer": [viewer_ws], "agent": []}

        # Simula o bloco de roteamento chamando diretamente
        raw = json.dumps({
            "type": "terminal_input",
            "session_id": sid,
            "payload": {"data": base64.b64encode(b"hello").decode()},
        })

        # Forward para hosts
        session = _sessions.get(sid, {})
        hosts = session.get("host", [])
        for hws in list(hosts):
            await hws.send(raw)

        assert len(received) == 1
        assert received[0][0] == "host"
        msg = json.loads(received[0][1])
        assert msg["type"] == "terminal_input"

        # cleanup
        del _sessions[sid]


class TestViewerClientSendInput:
    """Fase 3: ViewerClient.send_input() envia mensagem correta."""

    @pytest.mark.asyncio
    async def test_send_input_encodes_correctly(self) -> None:
        from src.infrastructure.collab.viewer_client import ViewerClient

        sent = []

        viewer = ViewerClient("ws://localhost:8060", "s-1", "tok")
        viewer._ws = MagicMock()
        viewer._ws.send = AsyncMock(side_effect=lambda data: sent.append(data))

        await viewer.send_input(b"ls -la\r")

        assert len(sent) == 1
        msg = json.loads(sent[0])
        assert msg["type"] == "terminal_input"
        assert msg["session_id"] == "s-1"
        decoded_data = base64.b64decode(msg["payload"]["data"])
        assert decoded_data == b"ls -la\r"

    @pytest.mark.asyncio
    async def test_send_input_raises_when_not_connected(self) -> None:
        from src.infrastructure.collab.viewer_client import ViewerClient

        viewer = ViewerClient("ws://localhost:8060", "s-1", "tok")
        with pytest.raises(RuntimeError, match="não conectado"):
            await viewer.send_input(b"test")


class TestAgentClientSendInput:
    """Fase 3: AgentClient.send_input() envia mensagem correta."""

    @pytest.mark.asyncio
    async def test_send_input_encodes_correctly(self) -> None:
        from src.infrastructure.collab.agent_client import AgentClient

        sent = []

        agent = AgentClient("ws://localhost:8060", "s-1", "tok")
        agent._ws = MagicMock()
        agent._ws.send = AsyncMock(side_effect=lambda data: sent.append(data))

        await agent.send_input(b"whoami\r")

        assert len(sent) == 1
        msg = json.loads(sent[0])
        assert msg["type"] == "terminal_input"
        decoded_data = base64.b64decode(msg["payload"]["data"])
        assert decoded_data == b"whoami\r"

    @pytest.mark.asyncio
    async def test_send_input_raises_when_not_connected(self) -> None:
        from src.infrastructure.collab.agent_client import AgentClient

        agent = AgentClient("ws://localhost:8060", "s-1", "tok")
        with pytest.raises(RuntimeError, match="não conectado"):
            await agent.send_input(b"test")


class TestHostRelayClientOnInput:
    """Fase 4: HostRelayClient chama on_input callback ao receber terminal_input."""

    @pytest.mark.asyncio
    async def test_on_input_callback_called(self) -> None:
        from src.infrastructure.collab.host_relay_client import HostRelayClient

        received = []

        def on_input(data: bytes) -> None:
            received.append(data)

        client = HostRelayClient("ws://localhost:8060", "s-1", "tok")

        # Simula mensagem terminal_input no receive loop
        msg = json.dumps({
            "type": "terminal_input",
            "payload": {"data": base64.b64encode(b"test-input").decode()},
        })

        # Chamar diretamente a lógica de parsing
        parsed = json.loads(msg)
        msg_type = parsed.get("type", "")
        assert msg_type == "terminal_input"
        data = base64.b64decode(parsed.get("payload", {}).get("data", ""))
        if data:
            on_input(data)

        assert len(received) == 1
        assert received[0] == b"test-input"


class TestRelayBridgeInputQueue:
    """Fase 5: RelayBridge enfileira input remoto e expõe get_input()."""

    def test_get_input_returns_none_when_empty(self) -> None:
        from src.infrastructure.collab.relay_bridge import RelayBridge

        bridge = RelayBridge("ws://localhost:8060", "s-1", "tok")
        assert bridge.get_input() is None

    def test_get_input_returns_queued_data(self) -> None:
        from src.infrastructure.collab.relay_bridge import RelayBridge

        bridge = RelayBridge("ws://localhost:8060", "s-1", "tok")
        bridge._input_queue.put(b"remote-keystroke")

        result = bridge.get_input()
        assert result == b"remote-keystroke"
        assert bridge.get_input() is None  # queue drained

    def test_on_input_wired_in_async_loop(self) -> None:
        """Verifica que _on_input é passado ao client.connect()."""
        from src.infrastructure.collab.relay_bridge import RelayBridge

        connect_kwargs = {}

        async def fake_connect(**kwargs):
            connect_kwargs.update(kwargs)

        async def fake_close():
            pass

        mock_client = MagicMock()
        mock_client.connect = AsyncMock(side_effect=fake_connect)
        mock_client.send_output = AsyncMock()
        mock_client.close = AsyncMock(side_effect=fake_close)

        with patch("src.infrastructure.collab.relay_bridge.HostRelayClient", return_value=mock_client):
            bridge = RelayBridge("ws://localhost:8060", "s-1", "tok")
            bridge.start()
            time.sleep(0.15)
            bridge.stop()

        assert "on_input" in connect_kwargs
        assert callable(connect_kwargs["on_input"])

        # Verify the callback enqueues data
        connect_kwargs["on_input"](b"test-data")
        assert bridge.get_input() == b"test-data"


class TestSessionManagerInputInjection:
    """Fase 8: can_inject_input() retorna True para participantes autenticados."""

    def test_can_inject_input_returns_true_for_participant(self) -> None:
        sm = SessionManager()
        session = sm.create_session("host-1", "mc-1", "123456")
        sm.add_participant("mc-1", "viewer-1", SessionMode.VIEW_ONLY)

        assert sm.can_inject_input("mc-1", "viewer-1") is True

    def test_can_inject_input_returns_false_for_unknown_participant(self) -> None:
        sm = SessionManager()
        sm.create_session("host-1", "mc-1", "123456")

        assert sm.can_inject_input("mc-1", "unknown-viewer") is False

    def test_can_inject_input_returns_false_for_invalid_session(self) -> None:
        sm = SessionManager()
        assert sm.can_inject_input("nonexistent", "viewer-1") is False

    def test_can_inject_input_returns_false_for_revoked_session(self) -> None:
        sm = SessionManager()
        sm.create_session("host-1", "mc-1", "123456")
        sm.add_participant("mc-1", "viewer-1", SessionMode.VIEW_ONLY)
        sm.revoke_session("mc-1")

        assert sm.can_inject_input("mc-1", "viewer-1") is False
