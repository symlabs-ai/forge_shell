"""
SuggestCard — T-33.

Representa um card de sugestão enviado por participante suggest-only.
O host aceita ou rejeita; só após aceitação o comando é executado.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.infrastructure.collab.protocol import RelayMessage, MessageType


@dataclass
class SuggestCard:
    """Card de sugestão de comando enviado por um participante remoto."""

    command: str
    explanation: str
    participant_id: str
    session_id: str
    accepted: bool = field(default=False, init=False)
    _rejected: bool = field(default=False, init=False, repr=False)

    def accept(self) -> None:
        """Host aceita a sugestão — pronto para execução."""
        self.accepted = True

    def reject(self) -> None:
        """Host rejeita a sugestão — não executa."""
        self._rejected = True
        self.accepted = False

    def to_relay_message(self) -> RelayMessage:
        """Serializar como RelayMessage para transmissão via relay."""
        return RelayMessage(
            type=MessageType.SUGGEST,
            session_id=self.session_id,
            payload={
                "command": self.command,
                "explanation": self.explanation,
                "from": self.participant_id,
            },
        )
