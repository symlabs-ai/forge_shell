"""
RelayHandler — C3-T-01.

Servidor WebSocket asyncio que usa RelayServer para gerenciar sessões
e fazer broadcast de terminal output do host para viewers conectados.

Protocolo de registro:
  - host:   {"type": "session_join", "session_id": "...", "payload": {"role": "host",   "token": "..."}}
  - viewer: {"type": "session_join", "session_id": "...", "payload": {"role": "viewer", "token": "..."}}

Após registro, host envia terminal_output e viewer recebe broadcast.
Token auth: o relay armazena o token enviado pelo host e valida o token do viewer.
            Viewer com token inválido recebe erro e tem a conexão encerrada.
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from http import HTTPStatus
from typing import Callable

try:
    import websockets
except ImportError:
    websockets = None  # type: ignore

log = logging.getLogger(__name__)

# session_id → {role → list[ws]}
_sessions: dict[str, dict[str, list]] = {}
# session_id → token (registrado pelo host)
_session_tokens: dict[str, str] = {}


class RelayHandler:
    """Servidor WebSocket relay."""

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 8060,
        ssl_context=None,
    ) -> None:
        self._host = host
        self._port = port
        self._ssl_context = ssl_context
        self._server = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        if websockets is None:
            raise RuntimeError("websockets não instalado: pip install websockets")
        kwargs = {}
        if self._ssl_context is not None:
            kwargs["ssl"] = self._ssl_context
        async with websockets.serve(
            self._handle,
            self._host,
            self._port,
            process_request=self._process_request,
            **kwargs,
        ) as server:
            self._server = server
            await self._stop_event.wait()

    async def _process_request(self, connection, request):
        """Intercepta HTTP antes do upgrade WebSocket — health check."""
        if request.path == "/health":
            active = sum(1 for s in _sessions.values() if s.get("host"))
            body = json.dumps({"status": "ok", "active_sessions": active})
            return connection.respond(HTTPStatus.OK, body + "\n")

    def stop(self) -> None:
        self._stop_event.set()

    async def _handle(self, ws) -> None:
        session_id = None
        role = None
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except (json.JSONDecodeError, ValueError):
                    continue

                msg_type = msg.get("type", "")
                session_id = msg.get("session_id", "")
                payload = msg.get("payload", {})

                if msg_type == "session_join":
                    role = payload.get("role", "viewer")
                    token = payload.get("token", "")

                    if role == "host":
                        # Registrar sessão e armazenar token do host
                        if session_id not in _sessions:
                            _sessions[session_id] = {"host": [], "viewer": []}
                        _sessions[session_id][role].append(ws)
                        if token:
                            _session_tokens[session_id] = token
                        log.debug("RelayHandler: %s joined %s as host", id(ws), session_id)

                    elif role == "viewer":
                        # Validar token se o host registrou um
                        registered_token = _session_tokens.get(session_id)
                        if registered_token and token != registered_token:
                            await ws.send(json.dumps({
                                "type": "error",
                                "payload": {"message": "Token inválido. Acesso negado."},
                            }))
                            await ws.close()
                            return
                        if session_id not in _sessions:
                            _sessions[session_id] = {"host": [], "viewer": []}
                        _sessions[session_id][role].append(ws)
                        log.debug("RelayHandler: %s joined %s as viewer", id(ws), session_id)

                elif msg_type == "terminal_output" and role == "host":
                    # broadcast para todos os viewers da sessão
                    viewers = _sessions.get(session_id, {}).get("viewer", [])
                    dead = []
                    for vws in list(viewers):
                        try:
                            await vws.send(raw)
                        except Exception:
                            dead.append(vws)
                    for vws in dead:
                        viewers.remove(vws)

                elif msg_type == "chat":
                    # broadcast para todos (host + viewers)
                    session = _sessions.get(session_id, {})
                    all_ws = session.get("host", []) + session.get("viewer", [])
                    for peer in list(all_ws):
                        if peer is not ws:
                            try:
                                await peer.send(raw)
                            except Exception:
                                pass

        except Exception as exc:
            log.debug("RelayHandler: connection closed (%s)", exc)
        finally:
            if session_id and role:
                peers = _sessions.get(session_id, {}).get(role, [])
                if ws in peers:
                    peers.remove(ws)
