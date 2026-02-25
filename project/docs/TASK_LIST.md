# TASK LIST — sym_shell · cycle-01 · Fase 1.0 Linux MVP

> Fonte: PRD v1.0 (25/02/2026)
> Scope: apenas entregas da Fase 1.0 (Linux). Windows (1.2) e macOS (1.1) são ciclos futuros.

---

## Legenda

| Campo    | Valores                                      |
|----------|----------------------------------------------|
| Priority | P0 (bloqueante · MVP não existe sem isso) · P1 (core feature) · P2 (complementar) |
| Size     | XS (< 2h) · S (meio dia) · M (1–2 dias) · L (3–5 dias) |
| Status   | pending · in_progress · done · blocked       |

---

## Pilar 1 — Terminal Engine (PTY)

| ID    | Tarefa                                                      | Priority | Size | Status  | Referência PRD |
|-------|-------------------------------------------------------------|----------|------|---------|----------------|
| T-01  | PTY spawn: criar PTY master/slave e spawnar `/bin/bash`     | P0       | M    | pending | §7.1, §15.1    |
| T-02  | Termios raw mode + restauração garantida no exit/crash      | P0       | M    | pending | §7.1, §8, §15.1 |
| T-03  | I/O loop: repasse stdin→pty e pty→stdout sem corrupção (UTF-8, alta taxa) | P0 | M | pending | §7.1, §15.1 |
| T-04  | Sinais: Ctrl+C (SIGINT), Ctrl+Z (SIGTSTP), job control (bg/fg) | P0    | M    | pending | §7.1, §15.1    |
| T-05  | Resize: capturar SIGWINCH e atualizar tamanho do PTY        | P0       | S    | pending | §7.1, §15.1    |
| T-06  | Full-screen apps: `vim`, `top`, `less`, `fzf` funcionando   | P0       | M    | pending | §7.1, §15.1    |
| T-07  | Alternate screen buffer detection (ativar/desativar intercepção) | P0   | M    | pending | §7.1, §15.2    |
| T-08  | `sudo` sem quebrar TTY (`sudo -v`, `sudo ls`)               | P0       | S    | pending | §15.1          |
| T-09  | `ssh` interativo: login remoto + retorno ao prompt local    | P0       | S    | pending | §15.1          |
| T-10  | `sym_shell doctor`: diagnóstico do terminal engine          | P2       | S    | pending | §9             |

---

## Pilar 2 — NL Mode + ForgeLLM

| ID    | Tarefa                                                      | Priority | Size | Status  | Referência PRD |
|-------|-------------------------------------------------------------|----------|------|---------|----------------|
| T-11  | ForgeLLM adapter: request/response + timeout + retry + fallback | P0   | M    | pending | §7.4, §15.4    |
| T-12  | Schema de resposta LLM: definir e validar (`commands[]`, `explanation`, `risk_level`, `assumptions[]`, `required_user_confirmation`) | P0 | S | pending | §7.4, §15.4 |
| T-13  | NL Mode trigger: `Ctrl+Space` e prefixo `??`               | P0       | S    | pending | §7.3, §9       |
| T-14  | NL flow: exibir comando sugerido + explicação + risco       | P0       | M    | pending | §7.3           |
| T-15  | Confirmation flow: confirmação padrão + double confirm para risco alto | P0 | S | pending | §7.3, §15.4  |
| T-16  | Risk engine: identificar padrões destrutivos (`rm -rf`, `dd`, `mkfs`, etc.) | P0 | S | pending | §7.3, §15.4 |
| T-17  | Redaction: remover tokens/keys/senhas do contexto enviado ao LLM | P0  | S    | pending | §7.3, §7.4, §15.4 |
| T-18  | `:explain <cmd>` e `:risk <cmd>` (análise sem executar)    | P1       | S    | pending | §9             |
| T-19  | Contexto LLM configurável: pwd, últimas N linhas, último cmd, whitelist de vars | P1 | S | pending | §7.3 |

---

## Pilar 3 — Colaboração Remota

| ID    | Tarefa                                                      | Priority | Size | Status  | Referência PRD |
|-------|-------------------------------------------------------------|----------|------|---------|----------------|
| T-20  | WebSocket server: stream de output do terminal em tempo real | P1      | M    | pending | §7.5, §15.3    |
| T-21  | Gestão de sessão: `sym_shell share`, geração de token, expiração | P1  | M    | pending | §7.5, §9       |
| T-22  | View-only mode: remoto vê terminal, sem injeção de input    | P1       | S    | pending | §7.5, §15.3    |
| T-23  | Chat: mensagens simples entre host e participantes          | P1       | M    | pending | §7.5           |
| T-24  | Suggest-only (cards): remoto propõe comando, host aplica explicitamente | P1 | M | pending | §7.5, §15.3 |
| T-25  | Input sensível: quando echo off, não transmitir input para remotos | P1 | S | pending | §7.5, §15.3 |
| T-26  | Indicador de sessão: banner/status sempre visível no terminal | P1     | XS   | pending | §7.5, §15.3    |
| T-27  | Reconnect: remoto cai e volta sem corromper sessão          | P2       | S    | pending | §15.3          |

---

## Pilar 4 — Auditoria

| ID    | Tarefa                                                      | Priority | Size | Status  | Referência PRD |
|-------|-------------------------------------------------------------|----------|------|---------|----------------|
| T-28  | Audit logger: registrar comandos executados (origem, timestamp, hash) | P1 | S | pending | §7.6, §15.5  |
| T-29  | Registrar aprovações + origem (usuário/LLM/remoto) + join/leave de sessão | P1 | S | pending | §7.6, §15.5 |
| T-30  | Export: log em JSON + texto plano                           | P2       | XS   | pending | §7.6, §15.5    |

---

## Pilar 5 — Estrutura base e scaffolding

| ID    | Tarefa                                                      | Priority | Size | Status  | Referência PRD |
|-------|-------------------------------------------------------------|----------|------|---------|----------------|
| T-31  | Scaffolding do projeto: estrutura de pacotes (`terminal_engine/`, `event_bus/`, `intelligence/`, `collab/`, `audit/`) | P0 | S | pending | §10 |
| T-32  | Event bus: definir schema de eventos padronizados do terminal | P0      | S    | pending | §10            |
| T-33  | CLI entrypoint: `sym_shell` e subcomandos (`share`, `doctor`) | P0     | XS   | pending | §9             |

---

## Resumo por prioridade

| Prioridade | Tasks                                       | Total |
|------------|---------------------------------------------|-------|
| **P0**     | T-01 a T-09, T-11 a T-17, T-31, T-32, T-33 | **20** |
| **P1**     | T-18 a T-26, T-28, T-29                    | **11** |
| **P2**     | T-10, T-27, T-30                            | **3**  |
| **Total**  |                                             | **34** |

---

## Ordem de execução sugerida (cycle-01)

1. **T-31, T-32, T-33** — scaffolding + event bus + CLI base
2. **T-01, T-02, T-03** — PTY core (sem isso nada funciona)
3. **T-04, T-05** — sinais + resize
4. **T-06, T-07** — full-screen apps + alternate screen detection
5. **T-08, T-09** — sudo + ssh
6. **T-11, T-12** — ForgeLLM adapter + schema
7. **T-17, T-16** — redaction + risk engine
8. **T-13, T-14, T-15** — NL Mode completo
9. **T-20, T-21** — WebSocket server + sessão
10. **T-22, T-25, T-26** — view-only + privacidade + indicador
11. **T-23, T-24** — chat + cards
12. **T-28, T-29** — auditoria
13. P1/P2 restantes (T-18, T-19, T-27, T-30, T-10)
