"""
Config loader — ~/.sym_shell/config.yaml

Carrega configuração do sym_shell com merge de defaults.
Valores ausentes no arquivo são preenchidos pelos defaults definidos aqui.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


# ---------------------------------------------------------------------------
# Value objects de configuração
# ---------------------------------------------------------------------------

VALID_REDACTION_PROFILES = frozenset({"dev", "prod"})


@dataclass
class RedactionProfileConfig:
    """Perfil de redaction: lista de padrões regex a mascarar antes de enviar ao LLM."""
    patterns: list[str] = field(default_factory=list)


@dataclass
class RedactionConfig:
    default_profile: str = "prod"
    profiles: dict[str, RedactionProfileConfig] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.profiles:
            self.profiles = _default_redaction_profiles()


@dataclass
class NLModeConfig:
    default_active: bool = True
    context_lines: int = 20          # últimas N linhas enviadas ao LLM
    var_whitelist: list[str] = field(default_factory=list)


@dataclass
class LLMConfig:
    api_key: str | None = None
    provider: str = "ollama"         # ollama | openai | anthropic | openrouter
    model: str = "llama3"
    timeout_seconds: int = 30
    max_retries: int = 2


@dataclass
class SymShellConfig:
    nl_mode: NLModeConfig = field(default_factory=NLModeConfig)
    redaction: RedactionConfig = field(default_factory=RedactionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)


# ---------------------------------------------------------------------------
# Defaults de redaction
# ---------------------------------------------------------------------------

def _default_redaction_profiles() -> dict[str, RedactionProfileConfig]:
    # Padrões comuns de segredos (regex simplificado para MVP)
    base_patterns = [
        r"(?i)(password|passwd|pwd)\s*[:=]\s*\S+",
        r"(?i)(api[_-]?key|apikey)\s*[:=]\s*\S+",
        r"(?i)(secret|token)\s*[:=]\s*\S+",
        r"(?i)(aws_access_key_id|aws_secret_access_key)\s*[:=]\s*\S+",
        r"sk-[A-Za-z0-9]{20,}",           # OpenAI-style keys
        r"ghp_[A-Za-z0-9]{36}",            # GitHub personal tokens
        r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
    ]
    prod_extra = [
        r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",   # IPs internos
        r"(?i)(db_url|database_url)\s*[:=]\s*\S+",
        r"(?i)(smtp_password|mail_password)\s*[:=]\s*\S+",
    ]
    return {
        "dev": RedactionProfileConfig(patterns=base_patterns),
        "prod": RedactionProfileConfig(patterns=base_patterns + prod_extra),
    }


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

class ConfigLoader:
    """
    Carrega ``~/.sym_shell/config.yaml`` e faz merge com os defaults.

    Se o arquivo não existir, retorna config com todos os defaults.
    Se uma chave estiver ausente no arquivo, o default é usado.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        self._path = config_path or Path.home() / ".sym_shell" / "config.yaml"

    def load(self) -> SymShellConfig:
        raw: dict[str, Any] = {}
        if self._path.exists():
            with self._path.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}

        return self._build(raw)

    def _build(self, raw: dict[str, Any]) -> SymShellConfig:
        nl_raw = raw.get("nl_mode", {})
        redaction_raw = raw.get("redaction", {})
        llm_raw = raw.get("llm", {})

        nl_mode = NLModeConfig(
            default_active=nl_raw.get("default_active", True),
            context_lines=nl_raw.get("context_lines", 20),
            var_whitelist=nl_raw.get("var_whitelist", []),
        )

        default_profile = redaction_raw.get("default_profile", "prod")
        if default_profile not in VALID_REDACTION_PROFILES:
            raise ValueError(
                f"redaction.default_profile inválido: '{default_profile}'. "
                f"Válidos: {sorted(VALID_REDACTION_PROFILES)}"
            )

        # Merge de perfis de redaction: defaults + overrides do arquivo
        profiles = _default_redaction_profiles()
        for name, profile_data in redaction_raw.get("profiles", {}).items():
            if isinstance(profile_data, dict):
                profiles[name] = RedactionProfileConfig(
                    patterns=profile_data.get("patterns", [])
                )

        redaction = RedactionConfig(
            default_profile=default_profile,
            profiles=profiles,
        )

        llm = LLMConfig(
            api_key=llm_raw.get("api_key", None),
            provider=llm_raw.get("provider", "ollama"),
            model=llm_raw.get("model", "llama3"),
            timeout_seconds=llm_raw.get("timeout_seconds", 30),
            max_retries=llm_raw.get("max_retries", 2),
        )

        return SymShellConfig(nl_mode=nl_mode, redaction=redaction, llm=llm)
