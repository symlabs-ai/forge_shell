"""
Redactor — mascara segredos antes de enviar contexto ao ForgeLLM.

Suporta perfis dev (permissivo) e prod (restritivo), configuráveis
em ~/.sym_shell/config.yaml.
"""
from __future__ import annotations

import re
from enum import Enum

_MASK = "[REDACTED]"


class RedactionProfile(str, Enum):
    DEV = "dev"
    PROD = "prod"


# Padrões base (aplicados em ambos os perfis)
_BASE_PATTERNS: list[str] = [
    r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+",
    r"(?i)(api[_-]?key|apikey)\s*[:=]\s*\S+",
    r"(?i)(secret|token)\s*[:=]\s*\S+",
    r"(?i)(aws_access_key_id|aws_secret_access_key)\s*[:=]\s*\S+",
    r"sk-[A-Za-z0-9]{20,}",
    r"ghp_[A-Za-z0-9]{36}",
    r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
]

# Padrões extras apenas para prod
_PROD_EXTRA_PATTERNS: list[str] = [
    r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
    r"(?i)(db_url|database_url)\s*[:=]\s*\S+",
    r"(?i)(smtp_password|mail_password)\s*[:=]\s*\S+",
]

_PROFILE_PATTERNS: dict[RedactionProfile, list[re.Pattern[str]]] = {
    RedactionProfile.DEV: [re.compile(p) for p in _BASE_PATTERNS],
    RedactionProfile.PROD: [re.compile(p) for p in _BASE_PATTERNS + _PROD_EXTRA_PATTERNS],
}


class Redactor:
    """Mascara segredos em texto usando padrões regex do perfil configurado."""

    def __init__(self, profile: RedactionProfile = RedactionProfile.PROD) -> None:
        self.profile = profile
        self._patterns = _PROFILE_PATTERNS[profile]

    @classmethod
    def from_profile_name(cls, name: str) -> "Redactor":
        try:
            return cls(profile=RedactionProfile(name))
        except ValueError:
            raise ValueError(
                f"Perfil de redaction inválido: '{name}'. Válidos: dev, prod"
            )

    def redact(self, text: str) -> str:
        """Mascarar segredos no texto. Retorna texto com [REDACTED]."""
        result = text
        for pat in self._patterns:
            result = pat.sub(_MASK, result)
        return result
