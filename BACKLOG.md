# BACKLOG — forge_shell

Items planejados mas não priorizados para o ciclo atual.

---

## Pendente

| # | Feature | Descrição | Impacto |
|---|---------|-----------|---------|
| 4 | **Persistência do histórico multi-turn** | Salvar `_history` (list[ChatMessage]) em `~/.forge_shell/history.json` ao encerrar a sessão e carregar no início. Histórico LLM não se perde entre sessões. | Médio |

---

## Concluído (referência)

| Versão | Feature |
|--------|---------|
| 0.3.3 | `forge_shell config [show\|edit]` |
| 0.3.3 | `forge_shell attach --token` + RelayHandler token auth |
| 0.3.3 | TLS no relay (ssl_context + wss:// auto + cert_file/key_file) |
| 0.3.3 | Build distribuível (PyInstaller spec + pipx + `[standalone]` dep) |
