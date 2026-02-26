# Retro Note — Cycle 02

> Data: 2026-02-25
> Duração do ciclo: 1 sessão (continuação do cycle-01)

## O que funcionou

- **Wiring limpo**: todos os 9 tasks conectaram os blocos do cycle-01 sem reescrever lógica — apenas orquestraram
- **TDD mantido**: cada task teve teste falhando antes da implementação, mesmo sendo tasks de integração
- **TerminalSession com DI**: injetar `_engine`, `_detector`, `_interceptor` e `_stdout` tornou os testes de roteamento testáveis sem I/O real
- **NLInterceptor desacoplado**: recebe `NLModeEngine` por injeção — testável com mock; sem dependência de LLM
- **CLI wiring simples**: substituição direta dos stubs por chamadas reais, testes de mock validaram o contrato
- **E2E Gate regressão**: cycle-01 passou íntegro após as mudanças do cycle-02
- **CRLF issue evitado via .gitattributes**: `*.sh text eol=lf` adicionado — não haverá mais problema em novos scripts

## O que não funcionou

- **CRLF no run-all.sh de novo**: mesmo com `.gitattributes`, o arquivo foi gerado com CRLF no mesmo commit. O `.gitattributes` precisa estar commitado **antes** que os arquivos sejam escritos para o hook de normalização ser aplicado. Corrigido via `sed -i 's/\r//'` mas indica que o processo de geração de scripts precisa garantir LF.
- **`forge_shell attach` ainda stub**: task P1 não coberta — relay WebSocket completo fica para cycle-03.
- **I/O loop sem teste de integração real**: `TerminalSession.run()` não tem teste end-to-end de sessão real (stdin→PTY→stdout). Coberto indiretamente pelos testes de cycle-01 (PTY integration), mas o loop completo com NL Mode integrado não foi testado ao vivo.

## Foco do próximo ciclo

- **cycle-03**: Relay WebSocket real (`asyncio + websockets`), `forge_shell attach` wired, NL Mode ao vivo (teste com ollama local), `pip install -e .` + smoke do binário PyInstaller
- **I/O loop integration test**: criar teste de integração que spawna `TerminalSession` com PTY real e valida que input/output fluem corretamente
- **NL Mode ao vivo**: smoke com `ollama` local — confirmar que sugestão aparece no terminal real

## Métricas

| Métrica | Valor |
|---------|-------|
| Tasks completadas | 9 / 9 |
| Testes novos | 45 (unit) + 12 (e2e) = 57 |
| Total acumulado | 306 passed, 1 skipped |
| Novos arquivos de código | 5 (terminal_session, nl_interceptor, pyproject.toml, .gitattributes, + CLI wiring) |
| Tokens consumidos | — |
| Horas investidas | — |
