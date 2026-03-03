"""
Config loader — ~/.forge_shell/config.yaml

Carrega configuração do forge_shell com merge de defaults.
Valores ausentes no arquivo são preenchidos pelos defaults definidos aqui.
"""
from __future__ import annotations

import os
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
    provider: str = "ollama"         # ollama | openai | anthropic | openrouter | symrouter
    model: str = "llama3.2"
    base_url: str | None = None      # base URL para providers remotos (ex: symrouter)
    timeout_seconds: int = 30
    max_retries: int = 2


@dataclass
class RelayConfig:
    url: str = "wss://relay.palhano.services"
    port: int = 8060
    tls: bool = False
    cert_file: str | None = None   # caminho para o certificado TLS (servidor)
    key_file: str | None = None    # caminho para a chave privada TLS (servidor)


@dataclass
class CollabConfig:
    permanent_password: str | None = None   # senha fixa entre sessões (None = efêmera)


@dataclass
class AgentConfig:
    """Configuração do agent system (NL Mode com tools)."""
    enabled: bool = False
    max_tool_rounds: int = 15
    exec_timeout: int = 60
    exec_deny_patterns: list[str] = field(default_factory=list)
    memory_enabled: bool = True
    memory_consolidate_every: int = 10
    brave_api_key: str | None = None
    web_fetch_max_chars: int = 50000


@dataclass
class ForgeShellConfig:
    nl_mode: NLModeConfig = field(default_factory=NLModeConfig)
    redaction: RedactionConfig = field(default_factory=RedactionConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    relay: RelayConfig = field(default_factory=RelayConfig)
    collab: CollabConfig = field(default_factory=CollabConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)


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

_CONFIG_EXAMPLE = """\
# forge_shell — configuração (~/.forge_shell/config.yaml)
# Copie para config.yaml e ajuste conforme necessário.

nl_mode:
  default_active: true        # NL Mode ativo por padrão
  context_lines: 20           # últimas N linhas enviadas ao LLM
  var_whitelist: []            # variáveis de ambiente enviadas ao LLM (ex: ["HOME", "USER"])

llm:
  provider: ollama             # ollama | openai | anthropic | openrouter | xai | symrouter
  model: llama3.2              # exemplos por provider:
                               #   ollama:     llama3.2, llama3.1, mistral
                               #   xai:        grok-4.1-fast, grok-4-fast, grok-4
                               #   openai:     gpt-4o, gpt-4o-mini, gpt-4.1
                               #   anthropic:  claude-sonnet-4-6, claude-haiku-4-5-20251001
                               #   symrouter:  qualquer modelo — roteado pelo gateway
  api_key: null                # chave de API (null para Ollama local ou variável de ambiente)
                               #   xai:       XAI_API_KEY
                               #   openai:    OPENAI_API_KEY
                               #   symrouter: SYMROUTER_API_KEY
  timeout_seconds: 30
  max_retries: 2

relay:
  url: wss://relay.palhano.services  # URL do relay para 'forge_shell attach' (ws:// ou wss://)
  port: 8060                   # porta do relay para 'forge_shell share'
  tls: false                   # TLS ativo (true → wss://, requer cert_file + key_file)
  # cert_file: /etc/forge_shell/server.crt   # certificado TLS do servidor (PEM)
  # key_file:  /etc/forge_shell/server.key   # chave privada TLS do servidor (PEM)

collab:
  permanent_password: null     # senha fixa entre sessões (null = nova senha a cada share)

redaction:
  default_profile: prod        # dev (permissivo) | prod (restritivo)

agent:
  enabled: false               # ativa agent system com tools (read_file, sonda, web_search, etc.)
  max_tool_rounds: 15          # máximo de rodadas de tool calling por query
  exec_timeout: 60             # timeout do SondaTool (exec silencioso) em segundos
  # exec_deny_patterns: []     # padrões regex extras para bloquear comandos (além dos defaults)
  memory_enabled: true         # memória persistente entre sessões (~/.forge_shell/agent/memory/)
  memory_consolidate_every: 10 # consolida memória a cada N interações
  brave_api_key: null          # chave Brave Search API (ou variável BRAVE_API_KEY)
  web_fetch_max_chars: 50000   # máximo de caracteres extraídos por web_fetch
"""


class ConfigLoader:
    """
    Carrega ``~/.forge_shell/config.yaml`` e faz merge com os defaults.

    Se o arquivo não existir, retorna config com todos os defaults.
    Se uma chave estiver ausente no arquivo, o default é usado.
    Na primeira execução, cria o diretório e um ``config.yaml.example``.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        env_path = os.environ.get("FORGE_SHELL_CONFIG")
        self._path = config_path or (Path(env_path) if env_path else Path.home() / ".forge_shell" / "config.yaml")
        self._created_example = False

    def ensure_config_dir(self) -> None:
        """Cria ~/.forge_shell/ e config.yaml.example se não existirem (best-effort)."""
        try:
            cfg_dir = self._path.parent
            cfg_dir.mkdir(parents=True, exist_ok=True)
            example = cfg_dir / "config.yaml.example"
            if not example.exists():
                example.write_text(_CONFIG_EXAMPLE, encoding="utf-8")
                self._created_example = True
        except (OSError, PermissionError):
            pass

    @property
    def first_run(self) -> bool:
        """True se o config.yaml.example foi criado nesta execução (primeiro uso)."""
        return self._created_example

    def load(self) -> ForgeShellConfig:
        self.ensure_config_dir()
        raw: dict[str, Any] = {}
        if self._path.exists():
            with self._path.open("r", encoding="utf-8") as fh:
                raw = yaml.safe_load(fh) or {}

        return self._build(raw)

    def _build(self, raw: dict[str, Any]) -> ForgeShellConfig:
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
            model=llm_raw.get("model", "llama3.2"),
            base_url=llm_raw.get("base_url", None),
            timeout_seconds=llm_raw.get("timeout_seconds", 30),
            max_retries=llm_raw.get("max_retries", 2),
        )

        relay_raw = raw.get("relay", {})
        relay = RelayConfig(
            url=relay_raw.get("url", "wss://relay.palhano.services"),
            port=relay_raw.get("port", 8060),
            tls=relay_raw.get("tls", False),
            cert_file=relay_raw.get("cert_file", None),
            key_file=relay_raw.get("key_file", None),
        )

        collab_raw = raw.get("collab", {})
        collab = CollabConfig(
            permanent_password=collab_raw.get("permanent_password", None),
        )

        agent_raw = raw.get("agent", {})
        agent = AgentConfig(
            enabled=agent_raw.get("enabled", False),
            max_tool_rounds=agent_raw.get("max_tool_rounds", 15),
            exec_timeout=agent_raw.get("exec_timeout", 60),
            exec_deny_patterns=agent_raw.get("exec_deny_patterns", []),
            memory_enabled=agent_raw.get("memory_enabled", True),
            memory_consolidate_every=agent_raw.get("memory_consolidate_every", 10),
            brave_api_key=agent_raw.get("brave_api_key", None),
            web_fetch_max_chars=agent_raw.get("web_fetch_max_chars", 50000),
        )

        return ForgeShellConfig(
            nl_mode=nl_mode, redaction=redaction, llm=llm,
            relay=relay, collab=collab, agent=agent,
        )
