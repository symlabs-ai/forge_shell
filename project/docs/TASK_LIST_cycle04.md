# TASK LIST — sym_shell · cycle-04 · Wiring Final + MVP Completo

> Fonte: retro cycle-03 + gap analysis (attach, relay_url, AuditLogger, share streaming)
> Objetivo: fechar todos os gaps de wiring; MVP funcional end-to-end

---

## Legenda

| Campo    | Valores |
|----------|---------|
| Priority | P0 · P1 · P2 |
| Size     | XS · S · M · L |
| Status   | pending · in_progress · done |

---

## Pilar 1 — Config relay

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C4-T-01 | `RelayConfig` em `SymShellConfig` — relay.url, relay.port com defaults; loader atualizado | P0 | S | pending |

---

## Pilar 2 — attach completo

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C4-T-02 | `attach` CLI — asyncio.run() viewer loop: ViewerClient.connect() + on_output→stdout.buffer + Ctrl+C graceful | P0 | M | pending |

---

## Pilar 3 — AuditLogger wired

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C4-T-03 | Wire AuditLogger no TerminalSession — registrar output PTY (resumido) e input do usuário | P1 | S | pending |

---

## Pilar 4 — RelayBridge (sync→async)

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C4-T-04 | `RelayBridge` — thread asyncio background que lê queue.Queue do TerminalSession e envia via HostRelayClient | P1 | M | pending |

---

## Pilar 5 — share wired com relay streaming

| ID      | Tarefa | Priority | Size | Status |
|---------|--------|----------|------|--------|
| C4-T-05 | Wire share mode: `share` CLI inicia RelayHandler inline + RelayBridge + TerminalSession — host streams PTY ao relay | P1 | L | pending |

---

## Resumo

| Prioridade | Tasks | Total |
|------------|-------|-------|
| **P0** | C4-T-01, C4-T-02 | **2** |
| **P1** | C4-T-03, C4-T-04, C4-T-05 | **3** |
| **Total** | | **5** |

---

## Ordem de execução

```
C4-T-01         RelayConfig (pré-requisito para url nos clientes)
C4-T-02         attach wired (viewer end-to-end)
C4-T-03         AuditLogger wired
C4-T-04         RelayBridge (bridge sync→async)
C4-T-05         share wired (share + bridge + session)
```

---

## Critério de done (cycle-04 / MVP)

- `sym_shell attach <id>` conecta ao relay e renderiza output no terminal
- relay_url lido de config.yaml (não hardcoded)
- AuditLogger registra eventos em `~/.sym_shell/audit.log`
- `sym_shell share` inicia relay inline + streaming PTY→viewers
- E2E Gate cycle-04 passando
