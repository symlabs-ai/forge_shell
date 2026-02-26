# Retro Note — Cycle 01

> Data: 2026-02-25
> Duração do ciclo: 1 sessão (contexto único)

## O que funcionou

- **Hyper Mode** executado corretamente após lembrança do stakeholder — PRD + task list + questionário gerados em passagem única
- **TDD Red→Green** rigoroso: nenhuma implementação começou sem teste falhando primeiro
- **Arquitetura Clean/Hex** clara desde o scaffolding — camadas bem definidas facilitaram cada pilar subsequente
- **forge_llm** integrado via mock nos testes unitários — sem dependência de LLM real para o pipeline de CI
- **PTY Engine** robusto: `read_available()` com polling até deadline eliminou flakiness de timing
- **43/43 tasks** implementadas e testadas em um único ciclo
- **E2E Gate** passou de primeira após ajuste de CRLF no script

## O que não funcionou

- **Hyper Mode não ativado na primeira vez** — ft_manager processou o PRD sem entrar em hyper mode; o stakeholder teve que lembrar. Ponto de atenção no processo.
- **`test_write_pwd` flaky**: depende de timing de startup do bash. Resolvido com `read_available` sem break antecipado + drain do prompt inicial, mas permanece sensível a carga do sistema.
- **`run-all.sh` com CRLF**: arquivo gerado com line endings Windows — corrigido via `sed` mas deve ser prevenido com `.gitattributes`.
- **TASK_LIST sem status atualizado**: tarefas ficaram como `pending` até o final do TDD — ideal seria atualizar progressivamente.
- **pyproject.toml ausente**: projeto não tem manifesto de pacote — impede `pip install -e .` e versionamento semântico via `/push`.

## Foco do próximo ciclo

- **cycle-02**: Integração real com ForgeLLM (provider ollama local) + I/O loop completo (stdin→pty→stdout em sessão interativa)
- **pyproject.toml**: criar manifesto com versão `0.1.0`, dependências e entry point `forge_shell`
- **`.gitattributes`**: definir `text=auto` para evitar CRLF em scripts shell
- **Relay WebSocket real**: T-28 tem a lógica mas falta o handler asyncio/websockets que conecta host↔relay via rede
- **NL Mode interativo**: integrar NLModeEngine com o I/O loop real (interceptar input antes de enviar ao PTY)
- **Config smoke**: validar carregamento real de `~/.forge_shell/config.yaml` com perfis dev/prod

## Métricas

| Métrica | Valor |
|---------|-------|
| Tasks completadas | 43 / 43 |
| Testes unitários passando | 212 |
| Testes de integração passando | 9 (1 skipped — termios/CI) |
| Testes E2E passando | 40 |
| Total de testes | 261 |
| Arquivos de código criados | ~30 |
| Tokens consumidos | — |
| Horas investidas | — |
