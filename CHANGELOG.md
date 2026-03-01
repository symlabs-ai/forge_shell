# Changelog

Todas as mudanças notáveis do forge_shell são documentadas aqui.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/).

## [0.5.1] - 2026-03-01

### Fixed
- NLModeEngine agora respeita `nl_mode.default_active` do config (antes hardcoded `NL_ACTIVE`)

## [0.5.0] - 2026-03-01

### Added
- **Agent system** com 7 tools para investigação do ambiente antes de sugerir comandos
  - `read_file`, `write_file`, `edit_file`, `list_dir` — filesystem com workspace boundary
  - `sonda` — execução silenciosa (deny patterns, timeout, truncation)
  - `web_search` — Brave Search API
  - `web_fetch` — httpx + readability-lxml
- **AgentService** — orquestrador com ChatAgent + ToolRegistry + `stream_chat` multi-round
- **MemoryStore** — memória persistente 2 camadas (MEMORY.md + HISTORY.md) com consolidação via LLM
- **AgentConfig** — seção `agent:` no config.yaml (enabled, max_tool_rounds, exec_timeout, deny_patterns, memory)
- **AgentPort** ABC — contrato para o sistema de agentes
- Dependências: `httpx>=0.27`, `readability-lxml>=0.8`

## [0.4.4] - 2026-03-01

### Changed
- **OutputRenderer** extraído de TerminalSession (formatação ANSI, help, sugestões)
- **ChatManager** extraído de TerminalSession (lifecycle do split view)
- **Port ABCs** adicionados: LLMPort, AuditorPort, RedactorPort, RiskEnginePort, AgentPort
- **Domain value objects**: RiskLevel e NLResponse movidos para `src/domain/value_objects/`
- **Constructor DI** + `_build_session()` factory centralizada em main.py

## [0.4.3] - 2026-02-27

### Added
- Ctrl+X sai da sessão share

### Fixed
- Cores ANSI preservadas no split view
- Chat panel com ativação lazy (só no primeiro message)

## [0.4.2] - 2026-02-27

### Added
- **Chat split terminal** — painel de chat ao lado do terminal (30 colunas)
  - VTScreen (wrapper pyte), ChatPanel, SplitRenderer, InputRouter
  - F4 alterna foco entre terminal e chat
- **Chat protocol** — `send_chat`/`get_chat` em HostRelayClient, ViewerClient e AgentClient
- Chat broadcast via relay (host, viewers e agents)

## [0.4.1] - 2026-02-27

### Added
- `forge_shell agent <code> <senha>` — CLI agent role (recebe output em stdout, envia suggest via JSON stdin)
- Host recebe e exibe suggest cards de agents conectados

## [0.4.0] - 2026-02-26

### Added
- **Machine code** persistente (NNN-NNN-NNN) em `~/.forge_shell/machine_id` + `--regen`
- **Senha de sessão** efêmera (6 dígitos) ou permanente via config
- **Relay 3 camadas** — `forge_shell relay` como serviço standalone (host e viewer conectam externamente)
- HTTP `/health` endpoint no relay (status, active_sessions, active_agents)
- Default relay URL: `wss://relay.palhano.services`

### Changed
- `forge_shell attach` agora usa `<machine_code> <senha>` em vez de UUID + token
- Rename: sym_shell → forge_shell (repo, imports, CLI)

## [0.3.3] - 2026-02-26

### Added
- `forge_shell config [show|edit]` — exibe/edita config YAML
- Token auth no viewer (RelayHandler valida)
- TLS no relay (ssl_context + auto wss:// + cert_file/key_file)
- Build distribuível (PyInstaller spec + scripts/build.sh + pipx)

## [0.3.2] - 2026-02-26

### Added
- `:help` — ajuda inline sem LLM
- `:risk <cmd>` — classificação de risco local
- Ctrl+C cancela chamada LLM em andamento
- Suporte a múltiplos comandos na sugestão
- Context injection (cwd + last N lines) para o LLM
- `:explain` com streaming
- SummarizeCompactor para histórico LLM
- Suporte a symrouter como provider

## [0.3.0] - 2026-02-25

### Added
- `forge_shell share` com RelayHandler inline + RelayBridge + PTY streaming
- Double confirm para risco HIGH (aviso vermelho)
- Toggle indicator no prompt
- `config.yaml.example` gerado na primeira execução

## [0.2.2] - 2026-02-25

### Added
- RelayBridge sync→async via queue.Queue + thread daemon
- `forge_shell attach` com asyncio loop + Ctrl+C graceful
- AuditLogger wired em todas as sessões
- RelayConfig no config.yaml

## [0.2.1] - 2026-02-25

### Added
- RelayHandler WebSocket server (broadcast host→viewers)
- HostRelayClient (WS client role=host)
- ViewerClient (WS client role=viewer + receive loop)
- `forge_shell attach <id>` CLI

## [0.2.0] - 2026-02-25

### Added
- TerminalSession I/O loop com select() sobre stdin + master_fd
- NLInterceptor wired no loop principal
- CLI wiring completo via pyproject.toml entry point

## [0.1.0] - 2026-02-25

### Added
- PTY engine (`pty.fork()` + termios raw mode + SIGWINCH)
- NL Mode (toggle `!`, escape `!<cmd>`, ForgeLLMAdapter)
- SessionManager (create/validate/revoke + TTL)
- AuditLogger (commands, approvals, join/leave)
- EventBus (schema de eventos padronizados)
- RiskEngine (HIGH/MEDIUM/LOW por regex)
- Redactor (perfis dev/prod)
- AlternateScreenDetector
