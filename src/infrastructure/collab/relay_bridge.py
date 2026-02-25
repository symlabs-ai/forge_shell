"""
RelayBridge — C4-T-04.

Ponte sync→async entre TerminalSession (síncrono) e HostRelayClient (asyncio).
Roda um event loop asyncio em thread background e expõe send() síncrono.

Uso:
    bridge = RelayBridge(relay_url, session_id, token)
    bridge.start()
    bridge.send(b"PTY output chunk")
    bridge.stop()
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
from typing import Any

from src.infrastructure.collab.host_relay_client import HostRelayClient

log = logging.getLogger(__name__)

_SENTINEL = None  # sinal de parada na queue


class RelayBridge:
    """
    Thread asyncio background que lê uma queue.Queue síncrona e envia
    os dados via HostRelayClient.send_output().
    """

    def __init__(self, relay_url: str, session_id: str, token: str) -> None:
        self._relay_url = relay_url
        self._session_id = session_id
        self._token = token
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._started = False

    def start(self) -> None:
        """Inicia thread asyncio background."""
        if self._started:
            return
        self._started = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Encerra thread background graciosamente."""
        if not self._started:
            return
        self._started = False
        self._queue.put(_SENTINEL)
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def send(self, data: bytes) -> None:
        """Enfileira dados para envio ao relay (thread-safe, síncrono)."""
        self._queue.put(data)

    def _run_loop(self) -> None:
        """Loop asyncio que corre na thread background."""
        asyncio.run(self._async_loop())

    async def _async_loop(self) -> None:
        client = HostRelayClient(
            relay_url=self._relay_url,
            session_id=self._session_id,
            token=self._token,
        )
        try:
            await client.connect()
        except Exception as exc:
            log.debug("RelayBridge: falha ao conectar: %s", exc)
            return

        try:
            while True:
                # poll a queue sem bloquear o event loop
                try:
                    item = self._queue.get_nowait()
                except queue.Empty:
                    await asyncio.sleep(0.01)
                    continue

                if item is _SENTINEL:
                    break

                try:
                    await client.send_output(item)
                except Exception as exc:
                    log.debug("RelayBridge: erro ao enviar: %s", exc)
                    break
        finally:
            try:
                await client.close()
            except Exception:
                pass
