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
