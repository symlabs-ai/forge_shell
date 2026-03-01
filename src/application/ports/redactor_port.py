"""RedactorPort — contrato para redação de informações sensíveis."""
from __future__ import annotations

from abc import ABC, abstractmethod


class RedactorPort(ABC):
    """Interface que todo redactor deve implementar."""

    @abstractmethod
    def redact(self, text: str) -> str:
        """Mascarar informações sensíveis no texto."""
