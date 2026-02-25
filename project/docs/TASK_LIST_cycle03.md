# TASK LIST — sym_shell · cycle-03 · Relay WebSocket + Integration

> Fonte: retro cycle-02 + gap analysis
> Objetivo: relay WebSocket real, attach wired, I/O integration tests, install smoke

---

## Pilar 1 — Relay WebSocket real

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C3-T-01 | `RelayHandler` — asyncio WebSocket server usando `RelayServer`; roteia host↔viewers | P1 | L | pending |
| C3-T-02 | `HostRelayClient` — cliente WebSocket que conecta ao relay e envia PTY output | P1 | M | pending |
| C3-T-03 | Wire `attach` subcommand → `ViewerClient` WebSocket que renderiza output remoto | P1 | M | pending |

---

## Pilar 2 — Integration tests

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C3-T-04 | Teste de integração `TerminalSession` com PTY real — I/O loop end-to-end | P0 | M | pending |
| C3-T-05 | `pip install -e .` smoke — entry point `sym_shell` instalado funciona | P0 | S | pending |

---

## Pilar 3 — NL Mode smoke

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C3-T-06 | NL Mode smoke condicional — `!`/`!<cmd>` no loop real; skip se sem LLM | P1 | S | pending |

---

## Resumo

| Prioridade | Tasks | Total |
|------------|-------|-------|
| **P0** | C3-T-04, C3-T-05 | **2** |
| **P1** | C3-T-01 a C3-T-03, C3-T-06 | **4** |
| **Total** | | **6** |

---

## Ordem de execução

```
C3-T-04         I/O integration (valida TerminalSession antes de tudo)
C3-T-05         pip install smoke
C3-T-01         RelayHandler WebSocket server
C3-T-02         HostRelayClient
C3-T-03         attach wired (ViewerClient)
C3-T-06         NL Mode smoke (condicional)
```
