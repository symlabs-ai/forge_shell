"""
RiskEngine — classificação de risco de comandos Bash.

Identifica padrões destrutivos e atribui nível de risco para que o
NL Mode possa exigir confirmação adequada antes de executar.
"""
from __future__ import annotations

import re
from src.infrastructure.intelligence.nl_response import RiskLevel

# ---------------------------------------------------------------------------
# Padrões de risco ALTO — deleção irreversível / formatação / sistema crítico
# ---------------------------------------------------------------------------
_HIGH_PATTERNS: list[re.Pattern[str]] = [
    # rm -rf com caminhos perigosos
    re.compile(r"\brm\s+.*-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(/[^ ]*|~[^ ]*|\*)", re.IGNORECASE),
    re.compile(r"\brm\s+.*-[a-zA-Z]*f[a-zA-Z]*r[a-zA-Z]*\s+(/[^ ]*|~[^ ]*|\*)", re.IGNORECASE),
    # dd sobre dispositivos
    re.compile(r"\bdd\b.*\bof=/dev/", re.IGNORECASE),
    # mkfs — formata partição
    re.compile(r"\bmkfs\b", re.IGNORECASE),
    # chmod agressivo em raiz ou /etc
    re.compile(r"\bchmod\s+.*-[Rr].*\s+(777|000|666)\s+(/|/etc|/usr|/bin|/sbin|/lib)", re.IGNORECASE),
    re.compile(r"\bchmod\s+.*-[Rr].*\s+(777|000|666)\s+(/|/etc)", re.IGNORECASE),
    # truncar arquivos críticos
    re.compile(r">\s*/etc/(passwd|shadow|sudoers|hosts|fstab)", re.IGNORECASE),
    re.compile(r"\bcat\s+/dev/null\s*>\s*/etc/", re.IGNORECASE),
    # fork bomb
    re.compile(r":\(\)\s*\{.*\|.*&.*\}", re.IGNORECASE),
    re.compile(r":\(\)\s*\{.*:\|:.*\}", re.IGNORECASE),
    # rm -rf / ou rm -rf /*
    re.compile(r"\brm\s+.*\s+/\s*$"),
    re.compile(r"\brm\s+.*\s+/\*"),
]

# ---------------------------------------------------------------------------
# Padrões de risco MÉDIO — modificações reversíveis / kill / restart
# ---------------------------------------------------------------------------
_MEDIUM_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bkill\b", re.IGNORECASE),
    re.compile(r"\bpkill\b", re.IGNORECASE),
    re.compile(r"\bkillall\b", re.IGNORECASE),
    re.compile(r"\bsystemctl\s+(stop|restart|disable|mask)\b", re.IGNORECASE),
    re.compile(r"\bservice\s+\w+\s+(stop|restart)\b", re.IGNORECASE),
    re.compile(r"\bsudo\s+apt[- ]get\s+(remove|purge)\b", re.IGNORECASE),
    re.compile(r"\bsudo\s+\w", re.IGNORECASE),  # qualquer sudo
    re.compile(r"\bchmod\b", re.IGNORECASE),
    re.compile(r"\bchown\b", re.IGNORECASE),
    re.compile(r"\bmv\s+/etc/", re.IGNORECASE),
    re.compile(r"\brm\b", re.IGNORECASE),  # rm sem -rf já é médio
]


class RiskEngine:
    """Classifica o nível de risco de um comando Bash."""

    def classify(self, command: str) -> RiskLevel:
        if not command.strip():
            return RiskLevel.LOW

        for pat in _HIGH_PATTERNS:
            if pat.search(command):
                return RiskLevel.HIGH

        for pat in _MEDIUM_PATTERNS:
            if pat.search(command):
                return RiskLevel.MEDIUM

        return RiskLevel.LOW

    def requires_double_confirm(self, command: str) -> bool:
        """True se o comando exige confirmação dupla (risco alto)."""
        return self.classify(command) == RiskLevel.HIGH
