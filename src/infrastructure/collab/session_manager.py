"""
SessionManager — gerencia sessões de colaboração remota do sym_shell.

Responsabilidades:
- Criar sessões com token de acesso com expiração
- Validar tokens
- Gerenciar participantes e suas permissões (view-only, suggest-only)
- Revogar sessões

Arquitetura: estado de sessão fica no HOST, não no relay.
O relay recupera o estado do host via protocolo definido em collab/protocol.py.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum


class SessionMode(str, Enum):
    VIEW_ONLY = "view_only"
    SUGGEST_ONLY = "suggest_only"


class SessionError(Exception):
    pass


@dataclass
class Participant:
    participant_id: str
    mode: SessionMode
    joined_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))


@dataclass
class Session:
    session_id: str
    host_id: str
    token: str
    expires_at: datetime
    participants: dict[str, Participant] = field(default_factory=dict)
    revoked: bool = False

    @property
    def is_valid(self) -> bool:
        if self.revoked:
            return False
        return datetime.now(tz=timezone.utc) < self.expires_at


class SessionManager:
    """Gerencia sessões de colaboração no host."""

    def __init__(self) -> None:
        self._sessions: dict[str, Session] = {}
        self._token_index: dict[str, str] = {}  # token → session_id

    def create_session(self, host_id: str, expire_minutes: int = 60) -> Session:
        session_id = f"s-{secrets.token_hex(8)}"
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(tz=timezone.utc) + timedelta(minutes=expire_minutes)

        session = Session(
            session_id=session_id,
            host_id=host_id,
            token=token,
            expires_at=expires_at,
        )
        self._sessions[session_id] = session
        self._token_index[token] = session_id
        return session

    def get_session(self, session_id: str) -> Session | None:
        return self._sessions.get(session_id)

    def get_session_by_token(self, token: str) -> Session | None:
        session_id = self._token_index.get(token)
        if not session_id:
            return None
        session = self._sessions.get(session_id)
        if session is None or not session.is_valid:
            return None
        return session

    def revoke_session(self, session_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.revoked = True

    def add_participant(
        self, session_id: str, participant_id: str, mode: SessionMode
    ) -> None:
        session = self._sessions.get(session_id)
        if session is None or not session.is_valid:
            raise SessionError(f"Sessão '{session_id}' inválida ou não encontrada")
        session.participants[participant_id] = Participant(
            participant_id=participant_id, mode=mode
        )

    def remove_participant(self, session_id: str, participant_id: str) -> None:
        session = self._sessions.get(session_id)
        if session:
            session.participants.pop(participant_id, None)

    def list_participants(self, session_id: str) -> list[Participant]:
        session = self._sessions.get(session_id)
        if not session:
            return []
        return list(session.participants.values())

    def can_inject_input(self, session_id: str, participant_id: str) -> bool:
        """Verifica se o participante pode injetar input no terminal (nunca, por ora)."""
        # view-only e suggest-only nunca injetam input diretamente
        session = self._sessions.get(session_id)
        if not session:
            return False
        return False  # co-control é pós-MVP

    def can_send_suggestions(self, session_id: str, participant_id: str) -> bool:
        """Verifica se o participante pode enviar cards de sugestão."""
        session = self._sessions.get(session_id)
        if not session:
            return False
        participant = session.participants.get(participant_id)
        if not participant:
            return False
        return participant.mode == SessionMode.SUGGEST_ONLY
