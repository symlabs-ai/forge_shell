# TASK LIST — sym_shell · cycle-01 · Fase 1.0 Linux MVP

> Fonte: PRD v1.0 normalizado (2026-02-25)
> Scope: Fase 1.0 Linux apenas. macOS (1.1) e Windows (1.2) são ciclos futuros.

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
| T-02  | Event bus: schema de eventos padronizados (TerminalOutput, UserInput, NLRequest, AuditEvent, etc.) | P0 | S | pending | — |
| T-03  | CLI entrypoint: `sym_shell` + subcomandos `share` e `doctor` (argparse/click) | P0 | S | pending | — |

---

## Pilar 2 — Terminal Engine (PTY)

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-04  | PTY spawn: criar PTY master/slave e spawnar `/bin/bash` interativo | P0 | M | pending | US-02 |
| T-05  | Termios: entrar em raw mode + restauração garantida no exit e crash (try/finally + signal handlers) | P0 | M | pending | US-02 |
| T-06  | I/O loop: repasse stdin→pty e pty→stdout sem corrupção (UTF-8, alta taxa de output) | P0 | M | pending | US-02 |
| T-07  | Sinais: Ctrl+C (SIGINT), Ctrl+Z (SIGTSTP), job control (`bg`/`fg`) | P0 | M | pending | US-02 |
| T-08  | Resize: capturar SIGWINCH e atualizar dimensões do PTY | P0 | S | pending | US-02 |
| T-09  | Full-screen apps: `vim`, `top`, `less`, `fzf` funcionando sem quebras | P0 | M | pending | US-02 |
| T-10  | Alternate screen buffer detection: desativar interceptação NL quando ativo, reativar ao sair | P0 | M | pending | US-02 |
| T-11  | `sudo` sem quebrar TTY: `sudo -v` e `sudo ls` funcionando | P0 | S | pending | US-02 |
| T-12  | `ssh` interativo: login remoto + retorno correto ao prompt local | P0 | S | pending | US-02 |

---

## Pilar 3 — NL Mode + ForgeLLM

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-13  | ForgeLLM adapter: request/response + streaming + timeout + retry + fallback silencioso | P0 | M | pending | US-01 |
| T-14  | Schema de resposta LLM: definir e validar (`commands[]`, `explanation`, `risk_level`, `assumptions[]`, `required_user_confirmation`) | P0 | S | pending | US-01 |
| T-15  | NL Mode trigger: `Ctrl+Space` (toggle) e prefixo `??` | P0 | S | pending | US-01 |
| T-16  | NL flow: exibir sugestão + explicação + classificação de risco | P0 | M | pending | US-01 |
| T-17  | Confirmation flow: confirmação padrão + double confirm para risco alto | P0 | S | pending | US-01, US-03 |
| T-18  | Risk engine: detectar padrões destrutivos (`rm -rf`, `dd`, `mkfs`, `chmod -R`, etc.) | P0 | S | pending | US-03 |
| T-19  | Redaction: remover tokens/keys/senhas do contexto enviado ao ForgeLLM | P0 | S | pending | US-01 |
| T-20  | `:explain <cmd>` — análise e descrição de impacto sem executar | P1 | S | pending | US-03 |
| T-21  | `:risk <cmd>` — classificação de risco sem executar | P1 | XS | pending | US-03 |
| T-22  | Contexto LLM configurável: pwd, últimas N linhas, último cmd, whitelist de variáveis | P1 | S | pending | US-01 |

---

## Pilar 4 — Colaboração Remota

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-23  | WebSocket server: stream de output do terminal em tempo real | P1 | M | pending | US-04 |
| T-24  | Gestão de sessão: `sym_shell share`, geração de token com expiração, revogação | P1 | M | pending | US-04 |
| T-25  | View-only mode: remoto vê terminal, sem injeção de input | P1 | S | pending | US-04 |
| T-26  | Chat: mensagens simples entre host e participantes remotos | P1 | M | pending | US-04 |
| T-27  | Suggest-only (cards): remoto propõe comando + explicação; host aplica explicitamente | P1 | M | pending | US-05 |
| T-28  | Input sensível: quando echo off, não transmitir input para remotos | P1 | S | pending | US-04 |
| T-29  | Indicador de sessão: status "Sessão compartilhada: ATIVA" sempre visível | P1 | XS | pending | US-04 |
| T-30  | TLS: conexão WebSocket com TLS obrigatório | P1 | S | pending | US-04 |
| T-31  | Reconnect: remoto desconecta e reconecta sem corromper sessão | P2 | S | pending | US-04 |

---

## Pilar 5 — Auditoria

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-32  | Audit logger: registrar comandos executados (origem, timestamp, hash) | P1 | S | pending | US-06 |
| T-33  | Registrar aprovações, origem (usuário/LLM/remoto) e eventos join/leave | P1 | S | pending | US-06 |
| T-34  | Export: log em JSON estruturado + texto plano legível | P2 | XS | pending | US-06 |

---

## Pilar 6 — Diagnóstico

| ID    | Tarefa | Priority | Size | Status | US |
|-------|--------|----------|------|--------|----|
| T-35  | `sym_shell doctor`: diagnóstico do terminal engine (PTY, termios, sinais, resize) | P2 | S | pending | — |

---

## Resumo

| Prioridade | Tasks | Total |
|------------|-------|-------|
| **P0** | T-01 a T-19 | **19** |
| **P1** | T-20 a T-33 | **14** |
| **P2** | T-31, T-34, T-35 | **3** |
| **Total** | | **35** |

---

## Ordem de execução sugerida (cycle-01)

```
T-01 → T-02 → T-03          scaffolding + event bus + CLI
T-04 → T-05 → T-06          PTY core (bloqueante de tudo)
T-07 → T-08                 sinais + resize
T-09 → T-10                 full-screen + alternate screen
T-11 → T-12                 sudo + ssh
T-13 → T-14                 ForgeLLM adapter + schema
T-19 → T-18                 redaction + risk engine
T-15 → T-16 → T-17          NL Mode completo
T-23 → T-24 → T-25          WebSocket + sessão + view-only
T-28 → T-29 → T-30          privacidade + indicador + TLS
T-26 → T-27                 chat + cards
T-32 → T-33                 auditoria
P1/P2 restantes
```
