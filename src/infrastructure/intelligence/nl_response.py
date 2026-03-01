"""
NLResponse — re-export from domain layer.

Canonical location: src.domain.value_objects.nl_response
This file preserves backward compatibility for existing imports.
"""
from src.domain.value_objects.risk_level import RiskLevel
from src.domain.value_objects.nl_response import NLResponse

__all__ = ["RiskLevel", "NLResponse"]
