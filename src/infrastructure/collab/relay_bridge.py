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

_SENTINEL = object()  # sinal de parada na queue


class RelayBridge:
    """
    Thread asyncio background que lê uma queue.Queue síncrona e envia
    os dados via HostRelayClient.send_output().
    """

    def __init__(
        self,
        relay_url: str,
        session_id: str,
        token: str,
        ssl=None,
    ) -> None:
        self._relay_url = relay_url
        self._session_id = session_id
        self._token = token
        self._ssl = ssl
        self._queue: queue.Queue[bytes | None] = queue.Queue()
        self._input_queue: queue.Queue[bytes] = queue.Queue()     # incoming remote input
        self._suggest_queue: queue.Queue[dict] = queue.Queue()
        self._chat_queue: queue.Queue[dict] = queue.Queue()       # incoming chat
        self._chat_out_queue: queue.Queue[dict] = queue.Queue()   # outgoing chat
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

    def get_input(self) -> bytes | None:
        """Poll non-blocking para input remoto recebido de viewer/agent (thread-safe)."""
        try:
            return self._input_queue.get_nowait()
        except queue.Empty:
            return None

    def get_suggest(self) -> dict | None:
        """Poll non-blocking para sugestões recebidas do agent (thread-safe)."""
        try:
            return self._suggest_queue.get_nowait()
        except queue.Empty:
            return None

    def get_chat(self) -> dict | None:
        """Poll non-blocking para mensagens de chat recebidas (thread-safe)."""
        try:
            return self._chat_queue.get_nowait()
        except queue.Empty:
            return None

    def send_chat(self, text: str, sender: str = "host") -> None:
        """Enfileira mensagem de chat para envio ao relay (thread-safe, síncrono)."""
        self._chat_out_queue.put({"text": text, "sender": sender})

    def _run_loop(self) -> None:
        """Loop asyncio que corre na thread background."""
        asyncio.run(self._async_loop())

    async def _async_loop(self) -> None:
        client = HostRelayClient(
            relay_url=self._relay_url,
            session_id=self._session_id,
            token=self._token,
            ssl=self._ssl,
        )

        def _on_input(data: bytes) -> None:
            self._input_queue.put_nowait(data)

        def _on_suggest(payload: dict) -> None:
            self._suggest_queue.put_nowait(payload)

        def _on_chat(payload: dict) -> None:
            self._chat_queue.put_nowait(payload)

        try:
            await client.connect(on_suggest=_on_suggest, on_chat=_on_chat, on_input=_on_input)
        except Exception as exc:
            log.debug("RelayBridge: falha ao conectar: %s", exc)
            return

        try:
            while True:
                # poll a queue sem bloquear o event loop
                got_data = False
                try:
                    item = self._queue.get_nowait()
                    got_data = True
                except queue.Empty:
                    item = None

                if item is _SENTINEL:
                    break

                if got_data:
                    try:
                        await client.send_output(item)
                    except Exception as exc:
                        log.debug("RelayBridge: erro ao enviar: %s", exc)
                        break

                # drain outgoing chat messages
                try:
                    chat_msg = self._chat_out_queue.get_nowait()
                    await client.send_chat(
                        text=chat_msg["text"],
                        sender=chat_msg.get("sender", "host"),
                    )
                except queue.Empty:
                    pass
                except Exception as exc:
                    log.debug("RelayBridge: erro ao enviar chat: %s", exc)

                if not got_data:
                    await asyncio.sleep(0.01)
        finally:
            try:
                await client.close()
            except Exception:
                pass
