"""
RelayServer — T-28.

Gerencia sessões de relay: recebe output do host e distribui para clients.
Cada RelaySession mantém a lista de WebSocket clients conectados.

A comunicação real via WebSocket é gerenciada pelo relay_handler (T-28 full),
mas a lógica de sessão e broadcast fica aqui, testável sem rede.
"""
from __future__ import annotations

import asyncio
import logging

from src.infrastructure.collab.protocol import RelayMessage, encode_message

log = logging.getLogger(__name__)


class RelaySession:
    """
    Sessão de relay: mantém clients WebSocket e faz broadcast de mensagens.
    """

    def __init__(self, session_id: str, token: str) -> None:
        self.session_id = session_id
        self.token = token
        # client_id → websocket-like object com método .send(bytes)
        self._clients: dict[str, object] = {}

    @property
    def client_count(self) -> int:
        return len(self._clients)

    def add_client(self, client_id: str, ws: object) -> None:
        self._clients[client_id] = ws

    def remove_client(self, client_id: str) -> None:
        self._clients.pop(client_id, None)

    async def broadcast(self, msg: RelayMessage) -> None:
        """Enviar mensagem para todos os clients. Remove clients desconectados."""
        raw = encode_message(msg)
        to_remove = []
        for client_id, ws in list(self._clients.items()):
            try:
                await ws.send(raw)
            except Exception as exc:
                log.warning("RelaySession: client %s desconectado (%s)", client_id, exc)
                to_remove.append(client_id)
        for client_id in to_remove:
            self.remove_client(client_id)


class RelayServer:
    """
    Gerencia múltiplas RelaySession.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, RelaySession] = {}
        self._token_index: dict[str, str] = {}  # token → session_id

    def create_session(self, session_id: str, token: str) -> RelaySession:
        session = RelaySession(session_id=session_id, token=token)
        self._sessions[session_id] = session
        self._token_index[token] = session_id
        return session

    def get_session(self, session_id: str) -> RelaySession | None:
        return self._sessions.get(session_id)

    def get_session_by_token(self, token: str) -> RelaySession | None:
        session_id = self._token_index.get(token)
        if not session_id:
            return None
        return self._sessions.get(session_id)

    def remove_session(self, session_id: str) -> None:
        session = self._sessions.pop(session_id, None)
        if session:
            self._token_index.pop(session.token, None)
