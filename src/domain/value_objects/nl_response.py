"""
NLResponse — resposta estruturada do LLM para NL Mode.

Value object imutável. Toda resposta do LLM deve ser deserializada nesta
estrutura antes de qualquer ação. Resposta fora do schema → rejeição silenciosa.
"""
from __future__ import annotations

from dataclasses import dataclass

from src.domain.value_objects.risk_level import RiskLevel


@dataclass(frozen=True)
class NLResponse:
    commands: list[str]
    explanation: str
    risk_level: RiskLevel
    assumptions: list[str]
    required_user_confirmation: bool

    def __post_init__(self) -> None:
        if not self.commands:
            raise ValueError("NLResponse.commands não pode ser vazio")
        if not self.explanation or not self.explanation.strip():
            raise ValueError("NLResponse.explanation não pode ser vazio")
