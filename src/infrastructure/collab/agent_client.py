"""
AgentClient — Agent role no relay.

Cliente WebSocket do agent de IA. Conecta ao relay como agent,
recebe terminal output e envia sugestões (suggest) para o host.
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


class AgentClient:
    """
    Conecta ao relay como agent, recebe output e envia sugestões.

    Uso:
        agent = AgentClient(relay_url, session_id, token)
        await agent.connect(on_output=lambda data: print(data))
        await agent.send_suggest(["ls -la"], "listar arquivos", "LOW")
        await agent.close()
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
        on_output: Callable[[bytes], None] | None = None,
        on_suggest_ack: Callable[[dict], None] | None = None,
        on_chat: Callable[[dict], None] | None = None,
    ) -> None:
        if websockets is None:
            raise RuntimeError("websockets não instalado")
        kwargs = {}
        if self._ssl is not None:
            kwargs["ssl"] = self._ssl
        self._ws = await websockets.connect(self._url, **kwargs)
        # registrar como agent
        await self._ws.send(json.dumps({
            "type": "session_join",
            "session_id": self._session_id,
            "payload": {"role": "agent", "token": self._token},
        }).encode())
        self._on_chat = on_chat
        # iniciar loop de recepção em background
        self._task = asyncio.create_task(self._receive_loop(on_output, on_suggest_ack, on_chat))

    async def send_suggest(
        self,
        commands: list[str],
        explanation: str,
        risk_level: str = "LOW",
    ) -> None:
        """Enviar sugestão para o host via relay."""
        if self._ws is None:
            raise RuntimeError("AgentClient: não conectado")
        msg = json.dumps({
            "type": "suggest",
            "session_id": self._session_id,
            "payload": {
                "commands": commands,
                "explanation": explanation,
                "risk_level": risk_level,
            },
        })
        await self._ws.send(msg.encode())

    async def send_chat(self, text: str, sender: str = "agent") -> None:
        """Send a chat message to the relay for broadcast."""
        if self._ws is None:
            raise RuntimeError("AgentClient: não conectado")
        msg = json.dumps({
            "type": "chat",
            "session_id": self._session_id,
            "payload": {"text": text, "sender": sender},
        })
        await self._ws.send(msg.encode())

    async def _receive_loop(
        self,
        on_output: Callable[[bytes], None] | None,
        on_suggest_ack: Callable[[dict], None] | None,
        on_chat: Callable[[dict], None] | None,
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
                if msg_type == "terminal_output":
                    encoded = msg.get("payload", {}).get("data", "")
                    try:
                        data = base64.b64decode(encoded)
                    except Exception:
                        data = encoded.encode()
                    if on_output:
                        on_output(data)
                elif msg_type == "suggest_ack":
                    if on_suggest_ack:
                        on_suggest_ack(msg.get("payload", {}))
                elif msg_type == "chat" and on_chat:
                    on_chat(msg.get("payload", {}))
        except Exception as exc:
            log.debug("AgentClient: loop encerrado (%s)", exc)

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
