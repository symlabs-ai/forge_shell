"""AgentPort — contrato para o agent system."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from src.domain.value_objects import NLResponse


class AgentPort(ABC):
    """Interface que o agent system deve implementar."""

    @abstractmethod
    def process(
        self,
        text: str,
        context: dict,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NLResponse | None:
        """Processar query NL usando tools e retornar resposta estruturada."""

    @abstractmethod
    def shutdown(self) -> None:
        """Liberar recursos do agent."""
