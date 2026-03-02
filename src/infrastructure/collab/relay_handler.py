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
            ping_interval=20,
            ping_timeout=10,
            **kwargs,
        ) as server:
            self._server = server
            await self._stop_event.wait()

    async def _process_request(self, connection, request):
        """Intercepta HTTP antes do upgrade WebSocket — health check."""
        if request.path == "/health":
            active = sum(1 for s in _sessions.values() if s.get("host"))
            agents = sum(len(s.get("agent", [])) for s in _sessions.values())
            body = json.dumps({"status": "ok", "active_sessions": active, "active_agents": agents})
            return connection.respond(HTTPStatus.OK, body + "\n")

        if request.path.startswith("/session/"):
            session_id = request.path.split("/session/", 1)[1]
            hosts = _sessions.get(session_id, {}).get("host", [])
            online = len(hosts) > 0
            body = json.dumps({"session_id": session_id, "host_online": online})
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
                            _sessions[session_id] = {"host": [], "viewer": [], "agent": []}
                        elif "agent" not in _sessions[session_id]:
                            _sessions[session_id]["agent"] = []
                        # Evictar hosts anteriores (só 1 host ativo por sessão)
                        old_hosts = _sessions[session_id]["host"]
                        if old_hosts:
                            log.debug(
                                "RelayHandler: evicting %d stale host(s) from %s",
                                len(old_hosts), session_id,
                            )
                            for old_ws in old_hosts:
                                try:
                                    await old_ws.close()
                                except Exception:
                                    pass
                            _sessions[session_id]["host"] = []
                        _sessions[session_id][role].append(ws)
                        if token:
                            _session_tokens[session_id] = token
                        log.debug("RelayHandler: %s joined %s as host", id(ws), session_id)

                    elif role in ("viewer", "agent"):
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
                            _sessions[session_id] = {"host": [], "viewer": [], "agent": []}
                        elif "agent" not in _sessions[session_id]:
                            _sessions[session_id]["agent"] = []
                        _sessions[session_id][role].append(ws)
                        log.debug("RelayHandler: %s joined %s as %s", id(ws), session_id, role)

                elif msg_type == "terminal_output" and role == "host":
                    # broadcast para todos os viewers e agents da sessão
                    session = _sessions.get(session_id, {})
                    for peer_role in ("viewer", "agent"):
                        peers = session.get(peer_role, [])
                        dead = []
                        for pws in list(peers):
                            try:
                                await pws.send(raw)
                            except Exception:
                                dead.append(pws)
                        for pws in dead:
                            peers.remove(pws)

                elif msg_type == "terminal_input" and role in ("viewer", "agent"):
                    # forward input para todos os hosts da sessão
                    session = _sessions.get(session_id, {})
                    hosts = session.get("host", [])
                    dead = []
                    for hws in list(hosts):
                        try:
                            await hws.send(raw)
                        except Exception:
                            dead.append(hws)
                    for hws in dead:
                        hosts.remove(hws)

                elif msg_type == "suggest" and role == "agent":
                    # forward suggest apenas para hosts da sessão
                    hosts = _sessions.get(session_id, {}).get("host", [])
                    dead = []
                    for hws in list(hosts):
                        try:
                            await hws.send(raw)
                        except Exception:
                            dead.append(hws)
                    for hws in dead:
                        hosts.remove(hws)

                elif msg_type == "chat":
                    # broadcast para todos (host + viewers + agents)
                    session = _sessions.get(session_id, {})
                    all_ws = session.get("host", []) + session.get("viewer", []) + session.get("agent", [])
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
