"""
HostRelayClient — C3-T-02.

Cliente WebSocket do host forge_shell. Conecta ao relay, registra como host
e envia PTY output codificado em base64 para broadcast aos viewers.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from typing import Callable

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore

log = logging.getLogger(__name__)


class HostRelayClient:
    """
    Conecta ao relay como host e envia terminal output.

    Uso:
        client = HostRelayClient(relay_url, session_id, token)
        await client.connect()
        await client.send_output(b"ls -la\\n")
        await client.close()
    """

    def __init__(
        self,
        relay_url: str,
        session_id: str,
        token: str,
        ssl=None,
    ) -> None:
        self._url = relay_url
        self._session_id = session_id
        self._token = token
        self._ssl = ssl
        self._ws = None
        self._task: asyncio.Task | None = None

    async def connect(
        self,
        on_suggest: Callable[[dict], None] | None = None,
        on_chat: Callable[[dict], None] | None = None,
        on_input: Callable[[bytes], None] | None = None,
    ) -> None:
        if websockets is None:
            raise RuntimeError("websockets não instalado")
        kwargs = {}
        if self._ssl is not None:
            kwargs["ssl"] = self._ssl
        self._ws = await websockets.connect(self._url, **kwargs)
        # registrar como host
        await self._ws.send(json.dumps({
            "type": "session_join",
            "session_id": self._session_id,
            "payload": {"role": "host", "token": self._token},
        }).encode())
        self._on_chat = on_chat
        # iniciar loop de recepção em background
        if on_suggest is not None or on_chat is not None or on_input is not None:
            self._task = asyncio.create_task(self._receive_loop(on_suggest, on_chat, on_input))

    async def send_output(self, data: bytes) -> None:
        """Enviar chunk de PTY output para o relay (codificado em base64)."""
        if self._ws is None:
            raise RuntimeError("HostRelayClient: não conectado")
        msg = json.dumps({
            "type": "terminal_output",
            "session_id": self._session_id,
            "payload": {"data": base64.b64encode(data).decode()},
        })
        await self._ws.send(msg.encode())

    async def send_chat(self, text: str, sender: str = "host") -> None:
        """Send a chat message to the relay for broadcast."""
        if self._ws is None:
            raise RuntimeError("HostRelayClient: não conectado")
        msg = json.dumps({
            "type": "chat",
            "session_id": self._session_id,
            "payload": {"text": text, "sender": sender},
        })
        await self._ws.send(msg.encode())

    async def _receive_loop(
        self,
        on_suggest: Callable[[dict], None] | None,
        on_chat: Callable[[dict], None] | None,
        on_input: Callable[[bytes], None] | None = None,
    ) -> None:
        if self._ws is None:
            return
        try:
            async for raw in self._ws:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue
                msg_type = msg.get("type", "")
                if msg_type == "terminal_input" and on_input:
                    data = base64.b64decode(msg.get("payload", {}).get("data", ""))
                    if data:
                        on_input(data)
                elif msg_type == "suggest" and on_suggest:
                    on_suggest(msg.get("payload", {}))
                elif msg_type == "chat" and on_chat:
                    on_chat(msg.get("payload", {}))
        except Exception as exc:
            log.debug("HostRelayClient: receive loop encerrado (%s)", exc)

    async def close(self) -> None:
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
