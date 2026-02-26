"""
C3-T-01 a C3-T-03 — Relay WebSocket: handler, host client, viewer client
DADO um RelayHandler asyncio rodando em porta local
QUANDO host envia output PTY e viewer conecta
ENTÃO viewer recebe os dados via broadcast
"""
import asyncio
import json
import pytest
import pytest_asyncio

pytestmark = pytest.mark.asyncio

from src.infrastructure.collab.relay_handler import RelayHandler
from src.infrastructure.collab.host_relay_client import HostRelayClient
from src.infrastructure.collab.viewer_client import ViewerClient
from src.infrastructure.collab.protocol import MessageType
from src.infrastructure.collab.agent_client import AgentClient


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
    await asyncio.sleep(0.1)  # aguarda server subir
    yield handler, free_port
    handler.stop()
    task.cancel()
    try:
        await task
    except (asyncio.CancelledError, Exception):
        pass


class TestRelayHealthCheck:
    async def test_health_returns_200_json(self, relay) -> None:
        handler, port = relay
        reader, writer = await asyncio.open_connection("127.0.0.1", port)
        writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
        await writer.drain()
        response = await asyncio.wait_for(reader.read(4096), timeout=3)
        text = response.decode()
        writer.close()
        assert "200 OK" in text
        body = text.split("\r\n\r\n", 1)[1]
        data = json.loads(body)
        assert data["status"] == "ok"
        assert "active_sessions" in data

    async def test_health_counts_active_sessions(self, relay) -> None:
        handler, port = relay
        import websockets

        # Register a host session
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            await ws.send(json.dumps({
                "type": "session_join",
                "session_id": "s-health",
                "payload": {"role": "host", "token": "tok"},
            }).encode())
            await asyncio.sleep(0.05)

            reader, writer = await asyncio.open_connection("127.0.0.1", port)
            writer.write(b"GET /health HTTP/1.1\r\nHost: localhost\r\n\r\n")
            await writer.drain()
            response = await asyncio.wait_for(reader.read(4096), timeout=3)
            body = response.decode().split("\r\n\r\n", 1)[1]
            data = json.loads(body)
            assert data["active_sessions"] == 1
            writer.close()


class TestRelayHandler:
    async def test_handler_accepts_connection(self, relay) -> None:
        handler, port = relay
        import websockets
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            # websockets 14+: state ou close_code indicam estado; sem exceção = conectado
            assert ws.close_code is None  # conexão aberta não tem close_code

    async def test_host_can_register_session(self, relay) -> None:
        handler, port = relay
        import websockets
        async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
            msg = json.dumps({
                "type": "session_join",
                "session_id": "s-test",
                "payload": {"role": "host", "token": "tok-test"},
            })
            await ws.send(msg.encode())
            await asyncio.sleep(0.05)
            # sem exceção = sessão registrada

    async def test_viewer_receives_terminal_output(self, relay) -> None:
        handler, port = relay
        import websockets
        received = []

        async def viewer():
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                # registrar como viewer
                await ws.send(json.dumps({
                    "type": "session_join",
                    "session_id": "s-broadcast",
                    "payload": {"role": "viewer", "token": "tok-test"},
                }).encode())
                # aguardar mensagem
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    received.append(msg)
                except asyncio.TimeoutError:
                    pass

        async def host():
            await asyncio.sleep(0.05)
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                # registrar como host
                await ws.send(json.dumps({
                    "type": "session_join",
                    "session_id": "s-broadcast",
                    "payload": {"role": "host", "token": "tok-test"},
                }).encode())
                await asyncio.sleep(0.05)
                # enviar terminal output
                await ws.send(json.dumps({
                    "type": "terminal_output",
                    "session_id": "s-broadcast",
                    "payload": {"data": "SGVsbG8="},  # base64 "Hello"
                }).encode())
                await asyncio.sleep(0.1)

        await asyncio.gather(viewer(), host())
        assert len(received) > 0
        data = json.loads(received[0])
        assert data.get("type") == "terminal_output"


class TestHostRelayClient:
    async def test_client_connects_and_sends(self, relay) -> None:
        handler, port = relay
        client = HostRelayClient(
            relay_url=f"ws://127.0.0.1:{port}",
            session_id="s-host-test",
            token="tok-host",
        )
        await client.connect()
        await client.send_output(b"hello\r\n")
        await client.close()

    async def test_client_send_output_encodes_base64(self, relay) -> None:
        handler, port = relay
        received = []
        import websockets

        async def spy():
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({
                    "type": "session_join",
                    "session_id": "s-spy",
                    "payload": {"role": "viewer", "token": "tok-spy"},
                }).encode())
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.5)
                    received.append(json.loads(msg))
                except asyncio.TimeoutError:
                    pass

        async def sender():
            await asyncio.sleep(0.05)
            client = HostRelayClient(
                relay_url=f"ws://127.0.0.1:{port}",
                session_id="s-spy",
                token="tok-spy",
            )
            await client.connect()
            await asyncio.sleep(0.05)
            await client.send_output(b"SMOKE")
            await asyncio.sleep(0.1)
            await client.close()

        await asyncio.gather(spy(), sender())
        assert len(received) > 0
        import base64
        assert base64.b64decode(received[0]["payload"]["data"]) == b"SMOKE"


class TestViewerClient:
    async def test_viewer_connects(self, relay) -> None:
        handler, port = relay
        viewer = ViewerClient(
            relay_url=f"ws://127.0.0.1:{port}",
            session_id="s-viewer-test",
            token="tok-viewer",
        )
        output_received = []
        await viewer.connect(on_output=lambda data: output_received.append(data))
        await asyncio.sleep(0.1)
        await viewer.close()

    async def test_viewer_receives_output_via_callback(self, relay) -> None:
        handler, port = relay
        received = []

        async def run_viewer():
            viewer = ViewerClient(
                relay_url=f"ws://127.0.0.1:{port}",
                session_id="s-cb-test",
                token="tok-cb",
            )
            await viewer.connect(on_output=lambda data: received.append(data))
            await asyncio.sleep(0.5)
            await viewer.close()

        async def run_host():
            await asyncio.sleep(0.1)
            client = HostRelayClient(
                relay_url=f"ws://127.0.0.1:{port}",
                session_id="s-cb-test",
                token="tok-cb",
            )
            await client.connect()
            await asyncio.sleep(0.05)
            await client.send_output(b"VIEWER_TEST")
            await asyncio.sleep(0.2)
            await client.close()

        await asyncio.gather(run_viewer(), run_host())
        assert b"VIEWER_TEST" in b"".join(received)


class TestAgentRole:
    async def test_agent_connects_and_receives_output(self, relay) -> None:
        handler, port = relay
        received = []

        async def run_agent():
            agent = AgentClient(
                relay_url=f"ws://127.0.0.1:{port}",
                session_id="s-agent-out",
                token="tok-agent",
            )
            await agent.connect(on_output=lambda data: received.append(data))
            await asyncio.sleep(0.5)
            await agent.close()

        async def run_host():
            await asyncio.sleep(0.1)
            client = HostRelayClient(
                relay_url=f"ws://127.0.0.1:{port}",
                session_id="s-agent-out",
                token="tok-agent",
            )
            await client.connect()
            await asyncio.sleep(0.05)
            await client.send_output(b"AGENT_SEES_THIS")
            await asyncio.sleep(0.2)
            await client.close()

        await asyncio.gather(run_agent(), run_host())
        assert b"AGENT_SEES_THIS" in b"".join(received)

    async def test_agent_sends_suggest_to_host(self, relay) -> None:
        handler, port = relay
        import websockets
        host_received = []

        async def run_host():
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({
                    "type": "session_join",
                    "session_id": "s-suggest",
                    "payload": {"role": "host", "token": "tok-sug"},
                }).encode())
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.5)
                    host_received.append(json.loads(msg))
                except asyncio.TimeoutError:
                    pass

        async def run_agent():
            await asyncio.sleep(0.1)
            agent = AgentClient(
                relay_url=f"ws://127.0.0.1:{port}",
                session_id="s-suggest",
                token="tok-sug",
            )
            await agent.connect()
            await asyncio.sleep(0.05)
            await agent.send_suggest(["ls -la"], "listar arquivos", "LOW")
            await asyncio.sleep(0.2)
            await agent.close()

        await asyncio.gather(run_host(), run_agent())
        assert len(host_received) > 0
        msg = host_received[0]
        assert msg["type"] == "suggest"
        assert msg["payload"]["commands"] == ["ls -la"]
        assert msg["payload"]["risk_level"] == "LOW"

    async def test_viewer_does_not_receive_suggest(self, relay) -> None:
        handler, port = relay
        import websockets
        viewer_received = []

        async def run_host():
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({
                    "type": "session_join",
                    "session_id": "s-no-sug",
                    "payload": {"role": "host", "token": "tok-ns"},
                }).encode())
                # Consume the suggest message so it doesn't block
                try:
                    await asyncio.wait_for(ws.recv(), timeout=1.0)
                except asyncio.TimeoutError:
                    pass

        async def run_viewer():
            async with websockets.connect(f"ws://127.0.0.1:{port}") as ws:
                await ws.send(json.dumps({
                    "type": "session_join",
                    "session_id": "s-no-sug",
                    "payload": {"role": "viewer", "token": "tok-ns"},
                }).encode())
                try:
                    msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                    viewer_received.append(json.loads(msg))
                except asyncio.TimeoutError:
                    pass

        async def run_agent():
            await asyncio.sleep(0.1)
            agent = AgentClient(
                relay_url=f"ws://127.0.0.1:{port}",
                session_id="s-no-sug",
                token="tok-ns",
            )
            await agent.connect()
            await asyncio.sleep(0.05)
            await agent.send_suggest(["rm -rf /"], "destruir tudo", "HIGH")
            await asyncio.sleep(0.3)
            await agent.close()

        await asyncio.gather(run_host(), run_viewer(), run_agent())
        # Viewer should NOT have received the suggest
        suggest_msgs = [m for m in viewer_received if m.get("type") == "suggest"]
        assert len(suggest_msgs) == 0

    async def test_host_receives_suggest_from_agent(self, relay) -> None:
        """Host com receive loop (on_suggest) recebe suggest do agent."""
        handler, port = relay
        host_suggestions = []

        async def run_host():
            client = HostRelayClient(
                relay_url=f"ws://127.0.0.1:{port}",
                session_id="s-host-recv",
                token="tok-hr",
            )
            await client.connect(on_suggest=lambda p: host_suggestions.append(p))
            await asyncio.sleep(0.5)
            await client.close()

        async def run_agent():
            await asyncio.sleep(0.1)
            agent = AgentClient(
                relay_url=f"ws://127.0.0.1:{port}",
                session_id="s-host-recv",
                token="tok-hr",
            )
            await agent.connect()
            await asyncio.sleep(0.05)
            await agent.send_suggest(["echo hello"], "test suggest", "LOW")
            await asyncio.sleep(0.2)
            await agent.close()

        await asyncio.gather(run_host(), run_agent())
        assert len(host_suggestions) > 0
        assert host_suggestions[0]["commands"] == ["echo hello"]
        assert host_suggestions[0]["risk_level"] == "LOW"

    async def test_agent_auth_validates_token(self, relay) -> None:
        handler, port = relay
        import websockets

        # Host registers with a token
        async with websockets.connect(f"ws://127.0.0.1:{port}") as host_ws:
            await host_ws.send(json.dumps({
                "type": "session_join",
                "session_id": "s-auth-agent",
                "payload": {"role": "host", "token": "correct-token"},
            }).encode())
            await asyncio.sleep(0.05)

        # Agent with wrong token should be rejected
        async with websockets.connect(f"ws://127.0.0.1:{port}") as agent_ws:
            await agent_ws.send(json.dumps({
                "type": "session_join",
                "session_id": "s-auth-agent",
                "payload": {"role": "agent", "token": "wrong-token"},
            }).encode())
            try:
                raw = await asyncio.wait_for(agent_ws.recv(), timeout=1.0)
                msg = json.loads(raw)
                assert msg["type"] == "error"
                assert "Token" in msg["payload"]["message"]
            except asyncio.TimeoutError:
                pytest.fail("Expected error message for invalid token")


class TestAgentCLIParser:
    def test_agent_cli_parser_exists(self) -> None:
        """Parser aceita 'agent MACHINE_CODE SENHA'."""
        from src.adapters.cli.main import build_parser
        parser = build_parser()
        args = parser.parse_args(["agent", "123-456-789", "654321"])
        assert args.command == "agent"
        assert args.machine_code == "123-456-789"
        assert args.password == "654321"
