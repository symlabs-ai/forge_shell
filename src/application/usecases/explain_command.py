"""
ExplainCommand — usecase :explain <cmd>.

Analisa e descreve o impacto de um comando sem executá-lo.
Usa o ForgeLLMAdapter em modo explain (não request).
"""
from __future__ import annotations

from src.infrastructure.intelligence.forge_llm_adapter import ForgeLLMAdapter
from src.infrastructure.intelligence.nl_response import NLResponse


class ExplainCommand:
    """Usecase :explain <cmd> — análise sem execução."""

    def __init__(self, adapter: ForgeLLMAdapter) -> None:
        self._adapter = adapter

    def run(self, command: str, context: dict) -> NLResponse | None:
        return self._adapter.explain(command=command, context=context)
