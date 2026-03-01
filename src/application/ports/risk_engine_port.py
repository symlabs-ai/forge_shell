"""RiskEnginePort — contrato para classificação de risco de comandos."""
from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.value_objects import RiskLevel


class RiskEnginePort(ABC):
    """Interface que todo risk engine deve implementar."""

    @abstractmethod
    def classify(self, command: str) -> RiskLevel:
        """Classificar o nível de risco de um comando."""

    @abstractmethod
    def requires_double_confirm(self, command: str) -> bool:
        """Verificar se o comando requer confirmação dupla."""
