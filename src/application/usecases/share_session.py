"""
ShareSession — usecase sym_shell share (T-29).

Cria uma sessão de colaboração e retorna token + session_id para o host
compartilhar com participantes.
"""
from __future__ import annotations

from src.infrastructure.collab.session_manager import SessionManager


class ShareSession:
    """Usecase: iniciar sessão compartilhada no host."""

    def __init__(self, session_manager: SessionManager) -> None:
        self._sm = session_manager

    def run(self, host_id: str, expire_minutes: int = 60) -> dict:
        session = self._sm.create_session(host_id=host_id, expire_minutes=expire_minutes)
        return {
            "session_id": session.session_id,
            "token": session.token,
            "expires_at": session.expires_at.isoformat(),
        }
