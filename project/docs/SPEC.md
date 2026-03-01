# SPEC.md — forge_shell

> Versão: 0.5.1
> MVP entregue em: 2026-02-25
> Última atualização: 2026-03-01
> Status: active development

---

## Visão

Terminal Bash nativo com linguagem natural integrada, colaboração remota e auditoria de sessão — sem quebrar nada que já funciona no Unix.

**Problema**: Comandos de shell exigem memória de flags e sintaxe precisa; suporte remoto a terminais depende de call + prints; terminais "inteligentes" existentes usam wrappers de texto que quebram sudo, vim e job control.
**Público-alvo**: DevOps/SRE, engenheiros de suporte, tech leads e desenvolvedores que usam terminal como interface primária.
**Diferencial**: Engine PTY real (não wrapper) + ForgeLLM com guardrails + colaboração remota nativa — tudo no mesmo processo Python, sem telnet ou VNC.

---

## Escopo

### O que está incluso

| Feature | User Story | Status | Ciclo |
|---------|-----------|--------|-------|
| PTY real — bash nativo com sudo, vim, ssh, job control | US-02 | Entregue | cycle-01 |
| Termios: raw mode + restauração garantida (try/finally + signals) | US-02 | Entregue | cycle-01 |
| Resize via SIGWINCH propagado ao PTY | US-02 | Entregue | cycle-01 |
| Alternate screen detection (vim/top/less — NL desativado) | US-02 | Entregue | cycle-01 |
| NL Mode como estado padrão — hint na abertura | US-01 | Entregue | cycle-01 |
| Toggle NL Mode ↔ Bash Mode via `!` | US-01 | Entregue | cycle-01 |
| Escape `!<cmd>` — bash direto + retorno ao NL Mode | US-01 | Entregue | cycle-01 |
| ForgeLLMAdapter — ChatAgent + stream_chat + retry + history multi-turn | US-01 | Entregue | cycle-01 |
| Schema NLResponse validado (commands, explanation, risk_level, assumptions) | US-01 | Entregue | cycle-01 |
| RiskEngine — classificação HIGH/MEDIUM/LOW por regex patterns | US-01 US-03 | Entregue | cycle-01 |
| Double confirm para risco HIGH (aviso vermelho, sem injeção automática) | US-01 US-03 | Entregue | cycle-06 |
| Redactor com perfis dev/prod configuráveis | US-01 | Entregue | cycle-01 |
| `:explain <cmd>` — análise e risco sem executar | US-03 | Entregue | cycle-01 |
| `:help` — ajuda inline sem LLM | US-01 | Entregue | cycle-02 |
| Contexto LLM configurável (cwd, last N lines, var_whitelist) | US-01 | Entregue | cycle-01 |
| Supressão de echo de senha (sudo/ssh prompts) | US-04 | Entregue | cycle-02 |
| SessionManager — create/validate/revoke + token expiração | US-04 | Entregue | cycle-01 |
| ShareSession — gera session_id + token com TTL | US-04 | Entregue | cycle-01 |
| RelayHandler — WebSocket server, broadcast host→viewers | US-04 | Entregue | cycle-03 |
| HostRelayClient — WS client role=host + send_output | US-04 | Entregue | cycle-03 |
| RelayBridge — bridge sync→async via queue.Queue + thread daemon | US-04 | Entregue | cycle-04 |
| ViewerClient — WS client role=viewer + receive loop + wait() | US-04 | Entregue | cycle-03 |
| `forge_shell share` — inicia RelayHandler + RelayBridge + PTY streaming | US-04 | Entregue | cycle-06 |
| `forge_shell attach <id>` — asyncio viewer loop com Ctrl+C graceful | US-04 | Entregue | cycle-04 |
| SessionIndicator — banner "Sessão compartilhada: ATIVA" | US-04 | Entregue | cycle-01 |
| AuditLogger — registra commands, approvals, join/leave em memória | US-06 | Entregue | cycle-01 |
| Export auditoria JSON estruturado e texto plano | US-06 | Entregue | cycle-01 |
| AuditLogger wired em todas as sessões | US-06 | Entregue | cycle-04 |
| `forge_shell doctor` — diagnóstico PTY, termios, resize, signals | — | Entregue | cycle-01 |
| `--passthrough` — PTY puro sem NL/collab/audit (debug mode) | — | Entregue | cycle-01 |
| ConfigLoader — `~/.forge_shell/config.yaml` + defaults + `config.yaml.example` | — | Entregue | cycle-06 |
| Event bus — schema de eventos padronizados (TerminalOutputEvent, etc.) | — | Entregue | cycle-01 |
| Relay protocol — RelayMessage framing JSON (encode/decode) | US-04 | Entregue | cycle-01 |
| `pip install -e .` via pyproject.toml + entry point `forge_shell` | — | Entregue | cycle-02 |
| SuggestCard — estrutura de card suggest-only (infra) | US-05 | Entregue | cycle-01 |
| `forge_shell config [show\|edit]` — exibe/edita config YAML sem abrir arquivo | — | Entregue | /feature |
| `forge_shell attach --token` — token auth no viewer (RelayHandler valida) | US-04 | Entregue | /feature |
| TLS no relay — ssl_context em RelayHandler + auto wss:// + cert_file/key_file | US-04 | Entregue | /feature |
| Build distribuível — forge_shell.spec PyInstaller + scripts/build.sh + pipx | — | Entregue | /feature |
| Machine code persistente (NNN-NNN-NNN) + senha de sessão (6 dígitos) | US-04 | Entregue | v0.4.0 |
| Relay 3 camadas — `forge_shell relay` como serviço standalone | US-04 | Entregue | v0.4.0 |
| HTTP `/health` endpoint no relay (status + sessions + agents) | US-04 | Entregue | v0.4.0 |
| `forge_shell agent` — CLI agent role (recebe output, envia suggest via JSON) | US-05 | Entregue | v0.4.1 |
| Chat split terminal — VTScreen + ChatPanel + SplitRenderer (F4 toggle) | US-04 | Entregue | v0.4.2 |
| Chat protocol — `send_chat`/`get_chat` em host, viewer e agent clients | US-04 | Entregue | v0.4.2 |
| Ctrl+X sai da sessão share | US-04 | Entregue | v0.4.3 |
| Refactor: OutputRenderer + ChatManager extraídos de TerminalSession | — | Entregue | v0.4.4 |
| Refactor: Port ABCs (LLMPort, AuditorPort, RedactorPort, RiskEnginePort, AgentPort) | — | Entregue | v0.4.4 |
| Refactor: Domain value objects (RiskLevel, NLResponse movidos para domain/) | — | Entregue | v0.4.4 |
| Refactor: Constructor DI + `_build_session()` factory centralizada | — | Entregue | v0.4.4 |
| Agent system — 7 tools (read/write/edit/list file, sonda, web_search, web_fetch) | US-07 | Entregue | v0.5.0 |
| AgentService — orquestrador com ChatAgent + ToolRegistry + stream_chat multi-round | US-07 | Entregue | v0.5.0 |
| MemoryStore — memória persistente 2 camadas (MEMORY.md + HISTORY.md) + consolidação via LLM | US-07 | Entregue | v0.5.0 |
| AgentConfig — seção `agent:` no config.yaml (enabled, max_tool_rounds, exec_timeout, deny_patterns) | US-07 | Entregue | v0.5.0 |
| NLModeEngine respeita `default_active` do config | US-01 | Entregue | v0.5.1 |

### O que está fora do escopo

- Co-control remoto (injeção de input pelo viewer) — pós-MVP
- UI browser para viewer remoto (cliente é terminal)
- Windows ConPTY (fase 1.2)
- macOS (fase 1.1)
- Login shell (forge_shell é CLI app, não substitui shell padrão)
- Execução automática de comandos LLM sem confirmação do usuário
- VNC / desktop remoto
- Monitoramento sem consentimento

---

## Funcionalidades Principais

### NL Mode (default)

O usuário digita em linguagem natural; forge_shell acumula a linha com echo local, dispara ForgeLLMAdapter em thread separada e exibe sugestão com comando, explicação e classificação de risco. Enter confirma; para risco HIGH o aviso vermelho é exibido e o usuário deve digitar manualmente. Toggle `!` alterna para Bash Mode; `!<cmd>` executa bash direto sem sair do NL Mode.

**User Story**: US-01 — Entrada em linguagem natural
**Entrypoint**: `forge_shell` (sem subcomando)

### Terminal Engine PTY Real

PTYEngine spawna `/bin/bash -i` em PTY master/slave via `pty.fork()`. O I/O loop em `TerminalSession.run()` usa `select()` sobre stdin e master_fd. Termios é salvo antes de entrar em raw mode e restaurado em `try/finally` e signal handlers. SIGWINCH é capturado e propagado ao PTY via `ioctl TIOCSWINSZ`. AlternateScreenDetector rastreia sequências ANSI para desativar NL Mode em apps full-screen.

**User Story**: US-02 — Terminal nativo (PTY real)
**Entrypoint**: `forge_shell` / `forge_shell --passthrough`

### Análise de Comando (`:explain`)

ForgeLLMAdapter.explain() usa system prompt separado para análise sem histórico. Retorna NLResponse com explanation, risk_level e assumptions sem executar o comando.

**User Story**: US-03 — Explicação e análise de risco
**Entrypoint**: `:explain <cmd>` no NL Mode ou Bash Mode

### Sessão Remota (share + attach + relay)

Arquitetura 3 camadas: host e viewers conectam a um relay standalone (`forge_shell relay`), sem necessidade de IP público ou porta aberta no host. `forge_shell share` gera machine code persistente (NNN-NNN-NNN via `~/.forge_shell/machine_id`) e senha de sessão (6 dígitos), conecta ao relay via RelayBridge e streama output do PTY. `forge_shell attach <code> <senha>` conecta como viewer read-only. Chat bidirecional via split terminal (F4 toggle) com VTScreen + ChatPanel + SplitRenderer. Relay expõe HTTP `/health` endpoint para monitoramento.

**User Story**: US-04 — Sessão remota (view-only + chat)
**Entrypoint**: `forge_shell share` | `forge_shell attach <code> <senha>` | `forge_shell relay`

### Agent Suggest (cards + CLI)

SuggestCard define a estrutura de card (comando + explicação) que o agent propõe ao host. `forge_shell agent <code> <senha>` conecta como agent role — recebe output do PTY em stdout e lê sugestões de stdin como JSON. O host recebe o card e decide se aplica.

**User Story**: US-05 — Sugestões remotas (cards)
**Entrypoint**: `forge_shell agent <code> <senha>`

### Auditoria de Sessão

AuditLogger mantém registros em memória (AuditRecord) com action, origin, details e timestamp UTC. Registra comandos executados (com exit_code e origin), aprovações, join/leave de sessão. Export em JSON estruturado (`export_json`) ou texto plano (`export_text`). Wired em todas as sessões via DI em TerminalSession.

**User Story**: US-06 — Auditoria de sessão
**Entrypoint**: `~/.forge_shell/audit/` (configurável via AuditLogger)

### Doctor

DoctorRunner executa 4 checks: pty (pty.openpty), termios (tcgetattr), resize (ioctl TIOCSWINSZ), signals (SIGWINCH). Retorna DoctorReport com status OK/WARN/FAIL por check e overall.

**Entrypoint**: `forge_shell doctor`

### Agent System (NL Mode com tools)

Quando `agent.enabled: true` no config, queries NL são roteadas pelo AgentService em vez da chamada direta ao ForgeLLMAdapter. AgentService cria um ChatAgent (forge_llm) com ToolRegistry contendo 7 tools que permitem ao LLM investigar o ambiente antes de sugerir comandos. Usa `stream_chat(auto_execute_tools=True)` para suportar múltiplas rodadas de tools. Resposta final é JSON idêntico ao NL Mode padrão (NLResponse).

**Tools disponíveis:**
- `read_file`, `write_file`, `edit_file`, `list_dir` — filesystem com workspace boundary
- `sonda` — execução silenciosa de comandos (subprocess.run com deny patterns e timeout)
- `web_search` — Brave Search API
- `web_fetch` — httpx + readability para extração de conteúdo

**Memória:** MemoryStore persiste em `~/.forge_shell/agent/memory/` com MEMORY.md (fatos long-term) e HISTORY.md (log com timestamps). Consolidação periódica via LLM com tool `save_memory`.

**User Story**: US-07 — Agent com investigação via tools
**Entrypoint**: `agent.enabled: true` no config.yaml

### Configuração

ConfigLoader carrega `~/.forge_shell/config.yaml` com merge de defaults. Na primeira execução cria o diretório e `config.yaml.example`. Suporta: NLModeConfig (default_active, context_lines, var_whitelist), LLMConfig (provider, model, api_key, timeout, retries), RelayConfig (url, port, tls), CollabConfig (permanent_password), AgentConfig (enabled, max_tool_rounds, exec_timeout, exec_deny_patterns, memory_enabled, brave_api_key, web_fetch_max_chars), RedactionConfig (default_profile: dev|prod, patterns por perfil).

**Entrypoint**: `~/.forge_shell/config.yaml` | `forge_shell config [show|edit]`

---

## Tech Stack

| Camada | Tecnologia | Motivo |
|--------|-----------|--------|
| Linguagem | Python 3.12 | ecossistema AI, tipagem, asyncio nativo |
| Terminal engine | `pty` + `termios` + `fcntl` (stdlib) | PTY real sem dependências externas |
| LLM | `forge_llm` (symlabs-ai/forge_llm) | provider interno Symlabs; abstrai ollama/openai/anthropic/xai/symrouter |
| WebSocket (relay) | `websockets` | asyncio nativo, suporte a v16 (`close_code is None`) |
| Terminal emulation | `pyte` | VTScreen para split terminal (chat panel) |
| HTTP client | `httpx` | Requisições sync para web_fetch e web_search tools |
| Readability | `readability-lxml` | Extração de conteúdo de páginas web (web_fetch tool) |
| Config | `PyYAML` | YAML legível para config de terminal |
| Testes | `pytest` + `pytest-asyncio` + `pexpect` | TDD, testes PTY reais, testes WebSocket reais |
| Empacotamento | `setuptools` (`setuptools.build_meta`) | entry point `forge_shell` via pip install -e . |
| Arquitetura | Clean / Hexagonal | camadas isoladas: adapters → application → infrastructure |

> Diagramas: `project/docs/diagrams/` (class · components · database · architecture)

---

## Arquitetura

```
Usuário (teclado)
    │
    ▼
stdin (raw mode) ──► TerminalSession.run() [select loop]
                            │
                ┌───────────┴────────────────┐
                │                            │
    alternate/passthrough              NL Mode buffer
                │                            │
                ▼                     ┌──────▼──────┐
           PTYEngine            NLInterceptor        │
           /bin/bash            NLModeEngine ────────┤
                │                 │          │       │
                │          AgentService   Adapter    │
                │          (tools+memory) (direct)   │
                │                 │          │       │
                │                 └────┬─────┘       │
                │                      ▼             │
                │               ForgeLLM             │
                │               RiskEngine           │
                │               Redactor             │
                │                     └──────────────┘
                │
                ▼
     OutputRenderer (display)
                │
          ┌─────┴──────┐
          │            │
     AuditLogger   RelayBridge ──► relay.palhano.services ──► ViewerClient
     (audit/)      ChatManager         (standalone)            AgentClient
                   (split view)
```

> Diagramas: `project/docs/diagrams/` (class · components · database · architecture)

---

## Modo de Manutenção

Este projeto está em **desenvolvimento ativo** (701+ testes passando). Novas features são adicionadas via:

```
/feature <descrição da feature>
```

A skill `/feature` lê este SPEC.md para entender o contexto antes de implementar.
Ao finalizar uma feature (`/feature done`), SPEC.md é atualizado automaticamente.

### Convenções do projeto

- Testes em `tests/unit/` (unitários, mocks) e `tests/smoke/` (processo real, PTY)
- Testes E2E em `tests/e2e/cycle-XX/` com scripts bash + `run-all.sh`
- Commits no formato `feat(cycle-XX): descrição` ou `feat(T-XX): descrição`
- DI explícita via constructor kwargs em TerminalSession, centralizada em `_build_session()` factory
- Port ABCs em `src/application/ports/` definem contratos (LLMPort, AuditorPort, AgentPort, etc.)
- ForgeLLMAdapter nunca lança exceção para o caller — retorna `None` em caso de falha
- AlternateScreenDetector deve ser alimentado com todo output do PTY antes de qualquer decisão de roteamento
- Redactor aplicado ao contexto LLM, nunca ao output do PTY em si
- `asyncio.run()` usado no CLI para subcomandos async; RelayBridge usa thread daemon com loop próprio
- Scripts shell gerados devem ter LF (não CRLF) — `.gitattributes` com `*.sh text eol=lf`

---

## Histórico de Mudanças

| Versão | Data | Feature | Ciclo |
|--------|------|---------|-------|
| 0.1.0 | 2026-02-25 | Scaffolding + PTY engine + NL Mode + ForgeLLM + SessionManager + AuditLogger + EventBus | cycle-01 |
| 0.2.0 | 2026-02-25 | TerminalSession I/O loop + NLInterceptor wired + CLI wiring + pyproject.toml | cycle-02 |
| 0.2.1 | 2026-02-25 | RelayHandler WebSocket + HostRelayClient + ViewerClient + attach CLI | cycle-03 |
| 0.2.2 | 2026-02-25 | RelayBridge sync→async + attach asyncio loop + AuditLogger wired + RelayConfig | cycle-04 |
| 0.3.0 | 2026-02-25 | share CLI com RelayHandler inline + double-confirm HIGH risk + toggle indicator + config.yaml.example | cycle-06 |
| 0.3.1 | 2026-02-26 | Diagramas (class, components, database, architecture) + SPEC.md | — |
| 0.3.2 | 2026-02-26 | :help + :risk + Ctrl-C LLM cancel + múltiplos comandos + context injection (cwd+last_lines) + :explain streaming + SummarizeCompactor + symrouter | /feature |
| 0.3.3 | 2026-02-26 | forge_shell config show/edit + attach --token + TLS relay (ssl_context + wss:// auto) + build distribuível (PyInstaller spec + pipx) | /feature |
| 0.4.0 | 2026-02-26 | Machine code + senha de sessão + relay 3 camadas standalone + HTTP /health + rename sym_shell → forge_shell | /feature |
| 0.4.1 | 2026-02-27 | Agent CLI role (forge_shell agent) + host recebe suggest cards | /feature |
| 0.4.2 | 2026-02-27 | Chat split terminal (VTScreen + ChatPanel + SplitRenderer + F4 toggle) + chat protocol | /feature |
| 0.4.3 | 2026-02-27 | Ctrl+X exit share + ANSI color fix split view + lazy chat activation | /feature |
| 0.4.4 | 2026-03-01 | Refactor: OutputRenderer + ChatManager + Port ABCs + domain value objects + constructor DI + _build_session() | refactor |
| 0.5.0 | 2026-03-01 | Agent system — 7 tools (filesystem, sonda, web) + AgentService + MemoryStore + AgentConfig | /feature |
| 0.5.1 | 2026-03-01 | Fix: NLModeEngine respeita default_active do config | fix |
