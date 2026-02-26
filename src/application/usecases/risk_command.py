"""
RiskCommand — usecase :risk <cmd>.

Classifica o risco de um comando usando o RiskEngine, sem executá-lo.
"""
from __future__ import annotations

from src.infrastructure.intelligence.risk_engine import RiskEngine, RiskLevel


class RiskCommand:
    """Usecase :risk <cmd> — classificação de risco sem execução."""

    def __init__(self, engine: RiskEngine) -> None:
        self._engine = engine

    def run(self, command: str) -> RiskLevel:
        return self._engine.classify(command)
