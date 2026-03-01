"""LLMPort — contrato para adaptadores de LLM."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable

from src.domain.value_objects import NLResponse


class LLMPort(ABC):
    """Interface que todo adaptador de LLM deve implementar."""

    @abstractmethod
    def request(
        self,
        text: str,
        context: dict,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NLResponse | None:
        """Gerar sugestão de comando a partir de linguagem natural."""

    @abstractmethod
    def explain(
        self,
        command: str,
        context: dict,
        on_chunk: Callable[[str], None] | None = None,
    ) -> NLResponse | None:
        """Explicar o que um comando faz."""
