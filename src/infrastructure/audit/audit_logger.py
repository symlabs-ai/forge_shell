"""
AuditLogger — trilha de auditoria estruturada de sessão forge_shell.

Registra comandos executados, aprovações, origens e eventos de sessão.
Exporta em JSON estruturado e texto plano legível.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from src.application.ports import AuditorPort
from datetime import datetime, timezone
from pathlib import Path

_VALID_ORIGINS = frozenset({"user", "llm", "remote"})


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


@dataclass
class AuditRecord:
    action: str
    origin: str
    details: dict
    timestamp: datetime = field(default_factory=_now)

    def __post_init__(self) -> None:
        if self.origin not in _VALID_ORIGINS:
            raise ValueError(
                f"AuditRecord.origin inválido: '{self.origin}'. Válidos: {sorted(_VALID_ORIGINS)}"
            )

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp.isoformat(),
            "action": self.action,
            "origin": self.origin,
            "details": self.details,
        }

    def to_text(self) -> str:
        ts = self.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        detail_str = " ".join(f"{k}={v}" for k, v in self.details.items())
        return f"[{ts}] {self.action} origin={self.origin} {detail_str}"


class AuditLogger(AuditorPort):
    """
    Logger de auditoria para sessão forge_shell.

    Mantém registros em memória e permite export em JSON ou texto.
    """

    def __init__(self, log_dir: Path | None = None) -> None:
        self._records: list[AuditRecord] = []
        self._log_dir = log_dir or Path.home() / ".forge_shell" / "audit"

    def log_command(self, command: str, origin: str, exit_code: int) -> None:
        self._append(AuditRecord(
            action="command_executed",
            origin=origin,
            details={"command": command, "exit_code": exit_code},
        ))

    def log_approval(self, command: str, approved_by: str, risk_level: str) -> None:
        self._append(AuditRecord(
            action="command_approved",
            origin="user",
            details={"command": command, "approved_by": approved_by, "risk_level": risk_level},
        ))

    def log_session_join(self, session_id: str, participant: str) -> None:
        self._append(AuditRecord(
            action="session_join",
            origin="remote",
            details={"session_id": session_id, "participant": participant},
        ))

    def log_session_leave(self, session_id: str, participant: str) -> None:
        self._append(AuditRecord(
            action="session_leave",
            origin="remote",
            details={"session_id": session_id, "participant": participant},
        ))

    def get_records(self) -> list[AuditRecord]:
        return list(self._records)

    def export_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = [r.to_dict() for r in self._records]
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def export_text(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [r.to_text() for r in self._records]
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def _append(self, record: AuditRecord) -> None:
        self._records.append(record)
