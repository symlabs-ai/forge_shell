# TASK LIST — sym_shell · cycle-02 · Wiring & I/O Loop

> Fonte: retro cycle-01 + gap analysis das stubs em main.py
> Objetivo: transformar blocos isolados em produto funcional (executável real)

---

## Legenda

| Campo    | Valores |
|----------|---------|
| Priority | P0 · P1 · P2 |
| Size     | XS · S · M · L |
| Status   | pending · in_progress · done |

---

## Pilar 1 — Packaging

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C2-T-01 | `pyproject.toml` — manifest, `version = "0.1.0"`, entry_point `sym_shell`, dependências | P0 | XS | done |
| C2-T-02 | `.gitattributes` — `text=auto`, `*.sh text eol=lf`, `*.py text eol=lf` | P0 | XS | done |

---

## Pilar 2 — TerminalSession (I/O Loop real)

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C2-T-03 | `TerminalSession` — loop stdin→PTY e PTY→stdout, raw mode, SIGWINCH handler, termios restore | P0 | L | done |
| C2-T-04 | Wire `--passthrough` → `TerminalSession` em modo puro sem NL/collab/audit | P0 | S | done |

---

## Pilar 3 — NL Mode wired no I/O Loop

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C2-T-05 | `NLInterceptor` — intercepta linha digitada, detecta `!`/`!<cmd>`/NL, roteia para NLModeEngine | P0 | M | done |
| C2-T-06 | Wire `NLInterceptor` no `TerminalSession` — ativo quando NL Mode e não alternate screen | P0 | M | done |

---

## Pilar 4 — CLI subcommands wired

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C2-T-07 | Wire `doctor` subcommand → `DoctorRunner.run()` + output formatado no terminal | P0 | S | done |
| C2-T-08 | Wire `share` subcommand → `ShareSession.run()` + exibir token + session-id | P1 | S | done |

---

## Pilar 5 — Config wiring

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C2-T-09 | Wire `ConfigLoader` ao startup do `TerminalSession` — NL default, perfil redaction, LLMConfig | P0 | S | done |

---

## Resumo

| Prioridade | Tasks | Total |
|------------|-------|-------|
| **P0** | C2-T-01 a C2-T-07, C2-T-09 | **8** |
| **P1** | C2-T-08 | **1** |
| **Total** | | **9** |

---

## Ordem de execução

```
C2-T-01 → C2-T-02              packaging (pré-requisito para entry point)
C2-T-09                        config wiring (pré-requisito para TerminalSession)
C2-T-03                        TerminalSession I/O loop (core)
C2-T-04                        --passthrough wired
C2-T-05 → C2-T-06              NL Mode integrado
C2-T-07                        doctor wired
C2-T-08                        share wired
```

---

## Critério de done (cycle-02)

- `pip install -e .` instala o pacote e `sym_shell --help` funciona
- `sym_shell --passthrough` abre Bash real e passa input/output sem corrupção
- `sym_shell doctor` imprime relatório com checks OK/WARN/FAIL
- `sym_shell` (sem flags) inicia com hint NL Mode e responde a `!` + `!<cmd>`
- E2E Gate cycle-02 passando (run-all.sh)
