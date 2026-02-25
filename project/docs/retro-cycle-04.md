# Retro — cycle-04 (Wiring Final + MVP Completo)

**Data:** 2026-02-25
**E2E Gate:** PASSED — 407 testes (326 unit+integration + 50 e2e regressão + 31 novos), 1 skipped

## Tarefas concluídas

| ID      | Tarefa                                    | Status |
|---------|-------------------------------------------|--------|
| C4-T-01 | RelayConfig em SymShellConfig             | ✓      |
| C4-T-02 | attach CLI — asyncio.run() viewer loop    | ✓      |
| C4-T-03 | AuditLogger wired no TerminalSession      | ✓      |
| C4-T-04 | RelayBridge — ponte sync→async            | ✓      |
| C4-T-05 | share wired com _relay_bridge injetável   | ✓      |

## O que correu bem

- RelayBridge com thread+queue isolada do event loop principal — padrão limpo e testável
- `asyncio.run()` no attach resolve elegantemente a integração sync→async no CLI
- DI pattern consistente: `_relay_bridge`, `_auditor`, `_interceptor` injetáveis no TerminalSession
- Regressão zero: 326 testes anteriores continuam passando

## Obstáculos encontrados

1. **Loop infinito no attach**: primeira implementação usava `while True: await asyncio.sleep()`. Substituído por `viewer.wait()` que aguarda o receive_task nativo.
2. **Testes cycle-03 quebraram**: `test_attach_wired` usava `MagicMock` sem `wait = AsyncMock`. Fix: helper `_make_mock_vc()` centralizado com connect/wait/close mockados.
3. **AsyncMock não importado**: import esquecido ao atualizar `test_c3t06`. Fix trivial.

## Estado do MVP (Fase 1.0 Linux)

| User Story | Status |
|------------|--------|
| US-01 NL Mode default | ✓ Implementado + wired |
| US-02 PTY real | ✓ Implementado + wired |
| US-03 Explain/Risk | ✓ Implementado |
| US-04 Sessão remota | ✓ Infra completa (relay + host + viewer + bridge) |
| US-05 Suggest-only cards | ✓ SuggestCard implementado |
| US-06 Auditoria | ✓ AuditLogger wired no TerminalSession |

## Dívidas técnicas (pós-MVP)

- `sym_shell share` não inicia RelayHandler inline ainda — requer orquestração de processo
- Token de viewer no attach está vazio (`""`) — autenticação real fica pós-MVP
- RelayBridge só funciona quando relay já está rodando — startup automático fica pós-MVP
- TLS efetivo (não apenas flag) fica pós-MVP (fase 1.1)
- Windows ConPTY (fase 1.2) não iniciado

## Decisão ft_manager

**MVP cycle-04 = DONE.** Todos os 4 ciclos encerrados com E2E Gate PASSED.
Próximo passo: release v0.1.0 (tag git + pyproject.toml bump).
