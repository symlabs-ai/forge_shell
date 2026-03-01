"""AuditorPort — contrato para loggers de auditoria."""
from __future__ import annotations

from abc import ABC, abstractmethod


class AuditorPort(ABC):
    """Interface que todo logger de auditoria deve implementar."""

    @abstractmethod
    def log_command(self, command: str, origin: str, exit_code: int) -> None:
        """Registrar comando executado."""
