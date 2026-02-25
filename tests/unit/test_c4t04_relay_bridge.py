"""
C4-T-04 — RelayBridge: ponte sync→async entre TerminalSession e HostRelayClient
DADO RelayBridge com HostRelayClient mockado
QUANDO send(data) é chamado sincronamente
ENTÃO os dados são enfileirados e enviados via HostRelayClient.send_output()
QUANDO start() é chamado
ENTÃO thread asyncio background inicia
QUANDO stop() é chamado
ENTÃO thread asyncio encerra graciosamente
"""
import pytest
import time
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from src.infrastructure.collab.relay_bridge import RelayBridge


class TestRelayBridge:
    def test_relay_bridge_instantiates(self) -> None:
        bridge = RelayBridge(relay_url="ws://localhost:8765", session_id="s-test", token="tok")
        assert bridge is not None

    def test_send_before_start_does_not_crash(self) -> None:
        bridge = RelayBridge(relay_url="ws://localhost:8765", session_id="s-test", token="tok")
        bridge.send(b"data")  # deve enfileirar sem crashar

    def test_start_and_stop(self) -> None:
        bridge = RelayBridge(relay_url="ws://localhost:8765", session_id="s-test", token="tok")
        bridge.start()
        time.sleep(0.05)
        bridge.stop()

    def test_stop_without_start_is_safe(self) -> None:
        bridge = RelayBridge(relay_url="ws://localhost:8765", session_id="s-test", token="tok")
        bridge.stop()  # não deve crashar

    def test_send_enqueues_data(self) -> None:
        bridge = RelayBridge(relay_url="ws://localhost:8765", session_id="s-test", token="tok")
        bridge.send(b"chunk1")
        bridge.send(b"chunk2")
        assert bridge._queue.qsize() >= 2

    def test_data_sent_to_host_client(self) -> None:
        """Dados enfileirados são enviados via HostRelayClient.send_output()."""
        sent = []

        async def fake_connect():
            pass

        async def fake_send(data):
            sent.append(data)

        async def fake_close():
            pass

        mock_client = MagicMock()
        mock_client.connect = AsyncMock(side_effect=fake_connect)
        mock_client.send_output = AsyncMock(side_effect=fake_send)
        mock_client.close = AsyncMock(side_effect=fake_close)

        with patch("src.infrastructure.collab.relay_bridge.HostRelayClient", return_value=mock_client):
            bridge = RelayBridge(relay_url="ws://localhost:8765", session_id="s-test", token="tok")
            bridge.start()
            time.sleep(0.1)  # aguarda thread iniciar e conectar
            bridge.send(b"HELLO")
            time.sleep(0.2)  # aguarda envio
            bridge.stop()

        assert b"HELLO" in sent
