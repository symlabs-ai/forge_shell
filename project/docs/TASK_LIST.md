# TASK LIST — sym_shell · cycle-01 · Fase 1.0 Linux MVP

> Fonte: PRD v1.0 + decisões do questionário hyper-mode (2026-02-25)
> Scope: Fase 1.0 Linux apenas.

---

## Legenda

| Campo    | Valores |
|----------|---------|
| Priority | P0 (MVP não existe sem isso) · P1 (core feature) · P2 (complementar) |
| Size     | XS (< 30min) · S (30min–2h) · M (2–4h) · L (4h+) |
| Status   | pending · in_progress · done · blocked |
| US       | User Story de referência (PRD §5) |

---

## Pilar 1 — Scaffolding e estrutura base

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-01  | Estrutura de pacotes: `terminal_engine/`, `event_bus/`, `intelligence/`, `collab/`, `audit/` | P0 | S | pending | — |
| T-02  | Event bus: schema de eventos padronizados (`TerminalOutput`, `UserInput`, `NLRequest`, `AuditEvent`, etc.) | P0 | S | pending | — |
| T-03  | CLI entrypoint: `sym_shell` + subcomandos `share`, `doctor`, `attach` (argparse/click) | P0 | S | pending | — |
| T-04  | Config base: `~/.sym_shell/config.yaml` — schema, carregamento, valores default | P0 | S | pending | — |

---

## Pilar 2 — Terminal Engine (PTY)

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-05  | PTY spawn: criar PTY master/slave e spawnar `/bin/bash` interativo | P0 | M | pending | US-02 |
| T-06  | Termios: entrar em raw mode + restauração garantida no exit e crash (try/finally + signal handlers) | P0 | M | pending | US-02 |
| T-07  | I/O loop: repasse stdin→pty e pty→stdout sem corrupção (UTF-8, alta taxa de output) | P0 | M | pending | US-02 |
| T-08  | Sinais: Ctrl+C (SIGINT), Ctrl+Z (SIGTSTP), job control (`bg`/`fg`) | P0 | M | pending | US-02 |
| T-09  | Resize: capturar SIGWINCH e atualizar dimensões do PTY | P0 | S | pending | US-02 |
| T-10  | Full-screen apps: `vim`, `top`, `less`, `fzf` funcionando sem quebras | P0 | M | pending | US-02 |
| T-11  | Alternate screen buffer detection: desativar interceptação NL quando ativo, reativar ao sair | P0 | M | pending | US-02 |
| T-12  | `sudo` sem quebrar TTY: `sudo -v` e `sudo ls` funcionando | P0 | S | pending | US-02 |
| T-13  | `ssh` interativo: login remoto + retorno correto ao prompt local | P0 | S | pending | US-02 |
| T-14  | `--passthrough`: flag que liga PTY puro desativando NL Mode, collab e auditoria — com help detalhado explicando o propósito (debug/smoke test da engine) | P0 | S | pending | — |

---

## Pilar 3 — NL Mode (default) + ForgeLLM

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-15  | ForgeLLM adapter: `ChatSession` + `stream_chat()` + api_key + timeout + retry + fallback silencioso | P0 | M | pending | US-01 |
| T-16  | Schema de resposta LLM: validar (`commands[]`, `explanation`, `risk_level`, `assumptions[]`, `required_user_confirmation`) | P0 | S | pending | US-01 |
| T-17  | NL Mode como estado padrão: hint na abertura (`NL Mode  \|  ! para bash  \|  !<cmd> bash direto`) | P0 | S | pending | US-01 |
| T-18  | Trigger `!<cmd>`: executar comando Bash diretamente e retornar ao NL Mode automaticamente | P0 | S | pending | US-01 |
| T-19  | Trigger `!` sozinho: toggle NL Mode ↔ Bash Mode | P0 | S | pending | US-01 |
| T-20  | NL flow: exibir sugestão + explicação + classificação de risco | P0 | M | pending | US-01 |
| T-21  | Confirmation flow: confirmação padrão + double confirm para risco alto | P0 | S | pending | US-01, US-03 |
| T-22  | Risk engine: detectar padrões destrutivos (`rm -rf`, `dd`, `mkfs`, `chmod -R`, etc.) | P0 | S | pending | US-03 |
| T-23  | Redaction com perfis: perfis `dev` (permissivo) e `prod` (restritivo) configuráveis em `config.yaml` | P0 | M | pending | US-01 |
| T-24  | `:explain <cmd>` — análise e descrição de impacto sem executar | P1 | S | pending | US-03 |
| T-25  | `:risk <cmd>` — classificação de risco sem executar | P1 | XS | pending | US-03 |
| T-26  | Contexto LLM configurável: pwd, últimas N linhas, último cmd, whitelist de variáveis (via `config.yaml`) | P1 | S | pending | US-01 |

---

## Pilar 4 — Colaboração Remota (relay + terminal client)

> Arquitetura: `sym_shell` (host) ↔ **relay intermediário** ↔ `sym_shell` (client terminal)
> Cliente é terminal, não browser. Relay tem UI administrativa separada.

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-27  | Protocolo host↔relay: definir mensagens, framing e tratamento de erros | P1 | M | pending | US-04 |
| T-28  | Relay server: recebe stream do host e distribui para clients conectados | P1 | L | pending | US-04 |
| T-29  | Gestão de sessão no host: `sym_shell share` gera token + estado persistente local; relay recupera estado do host | P1 | M | pending | US-04 |
| T-30  | `sym_shell attach <session-id>`: reconectar sessão existente (estado no host, relay informa ao client) | P1 | M | pending | US-04 |
| T-31  | Client terminal: view-only — recebe e renderiza output do terminal remoto; sem injeção de input | P1 | M | pending | US-04 |
| T-32  | Chat: mensagens simples entre host e participantes via relay | P1 | M | pending | US-04 |
| T-33  | Suggest-only (cards): client propõe comando + explicação; host executa após confirmação explícita | P1 | M | pending | US-05 |
| T-34  | Input sensível: quando echo off, não transmitir input para relay/clients | P1 | S | pending | US-04 |
| T-35  | Indicador de sessão: status "Sessão compartilhada: ATIVA" sempre visível no host | P1 | XS | pending | US-04 |
| T-36  | TLS: conexão host↔relay com TLS obrigatório | P1 | S | pending | US-04 |
| T-37  | Tokens: expiração curta + revogação | P1 | S | pending | US-04 |
| T-38  | Reconnect client: desconecta e reconecta sem corromper sessão | P2 | S | pending | US-04 |

---

## Pilar 5 — Auditoria

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-39  | Audit logger: registrar comandos executados (origem, timestamp, hash) | P1 | S | pending | US-06 |
| T-40  | Registrar aprovações, origem (usuário/LLM/remoto) e eventos join/leave | P1 | S | pending | US-06 |
| T-41  | Export: JSON estruturado + texto plano legível | P2 | XS | pending | US-06 |

---

## Pilar 6 — Distribuição e diagnóstico

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-42  | `sym_shell doctor`: diagnóstico da engine (PTY, termios, sinais, resize) | P2 | S | pending | — |
| T-43  | Build pipeline PyInstaller: gerar binário standalone Linux | P1 | M | pending | — |

---

## Resumo

| Prioridade | Tasks | Total |
|------------|-------|-------|
| **P0** | T-01 a T-23 | **23** |
| **P1** | T-24 a T-26, T-27 a T-37, T-39, T-40, T-43 | **17** |
| **P2** | T-38, T-41, T-42 | **3** |
| **Total** | | **43** |

---

## Ordem de execução sugerida (cycle-01)

```
T-01 → T-02 → T-03 → T-04     scaffolding + event bus + CLI + config
T-05 → T-06 → T-07             PTY core (bloqueante de tudo)
T-08 → T-09                    sinais + resize
T-10 → T-11                    full-screen + alternate screen
T-12 → T-13                    sudo + ssh
T-14                           --passthrough (smoke test mode)
T-15 → T-16                    ForgeLLM adapter + schema
T-23                           redaction com perfis
T-22                           risk engine
T-17 → T-18 → T-19 → T-20 → T-21   NL Mode completo
T-27 → T-28 → T-29             protocolo relay + relay server + sessão
T-36 → T-37                    TLS + tokens
T-30 → T-31                    attach + client terminal view-only
T-34 → T-35                    privacidade + indicador
T-32 → T-33                    chat + cards
T-39 → T-40                    auditoria
T-43                           build PyInstaller
P1/P2 restantes
```
