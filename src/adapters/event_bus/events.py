"""
Event bus — schema de eventos padronizados do forge_shell.

Todos os eventos transitam pelo sistema como dataclasses imutáveis
com timestamp automático e kind discriminante.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


class EventKind(str, Enum):
    TERMINAL_OUTPUT = "terminal_output"
    USER_INPUT = "user_input"
    NL_REQUEST = "nl_request"
    AUDIT = "audit"
    SESSION = "session"


class SessionEventKind(str, Enum):
    JOIN = "join"
    LEAVE = "leave"
    SHARE_START = "share_start"
    SHARE_STOP = "share_stop"


VALID_AUDIT_ORIGINS = frozenset({"user", "llm", "remote"})


@dataclass(frozen=True)
class TerminalOutputEvent:
    """Chunk de output produzido pelo terminal (PTY → consumidores)."""
    data: bytes
    kind: EventKind = field(default=EventKind.TERMINAL_OUTPUT, init=False)
    timestamp: datetime = field(default_factory=_now)


@dataclass(frozen=True)
class UserInputEvent:
    """
    Input do usuário capturado antes de ser enviado ao PTY.

    Regras de NL Mode:
    - ``!<cmd>\\n`` → is_nl_escape=True  (executa bash direto, volta ao NL Mode)
    - ``!\\n``      → is_nl_toggle=True  (alterna NL Mode ↔ Bash Mode)
    - qualquer outro → input normal
    """
    data: bytes
    kind: EventKind = field(default=EventKind.USER_INPUT, init=False)
    timestamp: datetime = field(default_factory=_now)

    @property
    def _text(self) -> str:
        return self.data.decode("utf-8", errors="replace").rstrip("\n\r")

    @property
    def is_nl_toggle(self) -> bool:
        """``!`` sozinho → toggle de modo."""
        return self._text == "!"

    @property
    def is_nl_escape(self) -> bool:
        """``!<cmd>`` com conteúdo → executa bash direto e volta ao NL Mode."""
        return self._text.startswith("!") and len(self._text) > 1


@dataclass(frozen=True)
class NLRequestEvent:
    """Requisição de linguagem natural a ser processada pelo ForgeLLM."""
    text: str
    kind: EventKind = field(default=EventKind.NL_REQUEST, init=False)
    timestamp: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if not self.text or not self.text.strip():
            raise ValueError("NLRequestEvent.text não pode ser vazio")


@dataclass(frozen=True)
class AuditEvent:
    """
    Evento de auditoria — registra ações relevantes para trilha de auditoria.

    origin: ``"user"`` | ``"llm"`` | ``"remote"``
    """
    action: str
    origin: str
    details: dict[str, Any]
    kind: EventKind = field(default=EventKind.AUDIT, init=False)
    timestamp: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.origin not in VALID_AUDIT_ORIGINS:
            raise ValueError(
                f"AuditEvent.origin inválido: '{self.origin}'. "
                f"Válidos: {sorted(VALID_AUDIT_ORIGINS)}"
            )


@dataclass(frozen=True)
class SessionEvent:
    """Evento de ciclo de vida de sessão colaborativa."""
    session_id: str
    participant: str
    session_kind: SessionEventKind
    kind: EventKind = field(default=EventKind.SESSION, init=False)
    timestamp: datetime = field(default_factory=_now)

    def __init__(
        self,
        kind: SessionEventKind,
        session_id: str,
        participant: str,
    ) -> None:
        object.__setattr__(self, "session_kind", kind)
        object.__setattr__(self, "session_id", session_id)
        object.__setattr__(self, "participant", participant)
        object.__setattr__(self, "kind", EventKind.SESSION)
        object.__setattr__(self, "timestamp", _now())
