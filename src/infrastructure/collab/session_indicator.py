"""
SessionIndicator — T-35.

Rastreia participantes ativos e gera texto de status visível no host:
"Sessão compartilhada: ATIVA (2 participantes)"
"""
from __future__ import annotations


class SessionIndicator:
    """Mantém estado de presença de participantes e gera status legível."""

    def __init__(self) -> None:
        self._participants: set[str] = set()

    def on_participant_joined(self, participant_id: str) -> None:
        self._participants.add(participant_id)

    def on_participant_left(self, participant_id: str) -> None:
        self._participants.discard(participant_id)

    @property
    def is_active(self) -> bool:
        return len(self._participants) > 0

    def status_text(self) -> str:
        if not self.is_active:
            return ""
        count = len(self._participants)
        label = "participante" if count == 1 else "participantes"
        return f"Sessão compartilhada: ATIVA ({count} {label})"
