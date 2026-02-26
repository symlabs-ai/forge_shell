"""
ShareSession — usecase sym_shell share (T-29).

Cria uma sessão de colaboração e retorna machine_code + password para o host
compartilhar com o viewer.
"""
from __future__ import annotations

from src.infrastructure.collab.session_manager import SessionManager


class ShareSession:
    """Usecase: iniciar sessão compartilhada no host."""

    def __init__(self, session_manager: SessionManager) -> None:
        self._sm = session_manager

    def run(self, host_id: str, machine_code: str, password: str) -> dict:
        self._sm.create_session(
            host_id=host_id, machine_code=machine_code, password=password
        )
        return {
            "machine_code": machine_code,
            "password": password,
        }
