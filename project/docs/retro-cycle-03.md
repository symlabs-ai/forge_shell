# Retro — cycle-03 (Relay WebSocket + NL Smoke + Attach)

**Data:** 2026-02-25
**E2E Gate:** PASSED — 345 testes (295 unit+integration + 50 e2e regressão + 22 smoke novos), 1 skipped

## Tarefas concluídas

| ID      | Tarefa                              | Status |
|---------|-------------------------------------|--------|
| C3-T-01 | RelayHandler (WebSocket asyncio)    | ✓      |
| C3-T-02 | HostRelayClient                     | ✓      |
| C3-T-03 | ViewerClient                        | ✓      |
| C3-T-04 | Integration: TerminalSession I/O    | ✓      |
| C3-T-05 | Smoke: pip install                  | ✓      |
| C3-T-06 | NL Mode smoke + attach wired no CLI | ✓      |

## O que correu bem

- Relay WebSocket (host→viewer broadcast) implementado limpo com dict `_sessions[id][role]`
- Dead connection removal automático no broadcast
- Testes de integração WebSocket reais (sem mocks de rede) passaram na primeira tentativa
- NL Mode smoke sem LLM real funcionou com adapter mockado

## Obstáculos encontrados

1. **websockets v16 API change**: `ws.open` removido → `ws.close_code is None`. Detectado nos testes, corrigido imediatamente.
2. **`WebSocketServerProtocol` deprecado**: import removido do relay_handler.py.
3. **CRLF recorrente no run-all.sh**: `.gitattributes` com `eol=lf` não retroage em arquivos já rastreados. O `Write` tool gera CRLF no Linux/WSL em alguns contextos. Workaround: `sed -i 's/\r//'` antes de executar.
4. **REPO_ROOT errado no run-all.sh**: script usava `dirname "$0"` apontando para o diretório do script (`tests/e2e/cycle-03/`) em vez de navegar até a raiz. Corrigido com `BASH_SOURCE[0]` + 3 níveis de `..`.

## Dívidas técnicas

- `attach` no CLI instancia `ViewerClient` mas não chama `viewer.connect()` — conexão real ao relay fica para ciclo futuro
- `relay_url` hardcoded em `ws://localhost:8765` — deve vir do `config.yaml`
- `token` no attach é string vazia — autenticação de viewer fica para ciclo futuro
- Sem testes de reconexão ou timeout no viewer

## Próximo ciclo sugerido

- Completar attach: `viewer.connect()` com on_output→stdout, Ctrl+C graceful
- Wiring relay_url + token via config e flags CLI
- Chat bidirecional (host↔viewers) integrado ao NL Mode
