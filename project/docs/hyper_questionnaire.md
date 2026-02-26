# Questionário de Alinhamento — forge_shell

> Gerado pelo ft_coach em hyper-mode a partir do PRD v1.0 (2026-02-25).
> Responda cada pergunta para que os artefatos sejam finalizados e o ciclo TDD possa iniciar.

---

## 🔍 Pontos Ambíguos

### A1 — Login shell vs. aplicativo CLI
**Trecho**: "O forge_shell será login shell (via `chsh`) ou só aplicativo/CLI?" (PRD §14)
**Ambiguidade**: o PRD menciona a decisão mas não a toma. As duas opções têm implicações arquiteturais significativas.
**Interpretação A**: forge_shell é login shell — substitui o Bash como shell padrão do usuário. Máxima integração, mas exige mais robustez (qualquer falha = usuário sem terminal).
**Interpretação B**: forge_shell é um aplicativo CLI — o usuário roda `forge_shell` dentro do terminal existente, como tmux. Mais seguro, mais fácil de adotar e reverter.
**Pergunta**: Para o MVP, forge_shell será login shell ou aplicativo CLI (rodando dentro do terminal existente)?
**Resposta**: B

---

### A2 — Como o remoto acessa a sessão compartilhada
**Trecho**: "você inicia sessão, manda link/token" (PRD §6); "UI do remoto: browser (web) é MVP" (PRD §14)
**Ambiguidade**: o PRD diz que a UI do remoto é browser, mas não define como o servidor de colaboração é acessado — se há um relay externo, se é acesso direto ao IP do host, ou outro mecanismo.
**Interpretação A**: servidor WebSocket roda localmente no host; o remoto acessa diretamente via IP:porta + token. Requer que o host tenha porta aberta/acessível.
**Interpretação B**: há um relay/servidor intermediário (hospedado pela Symlabs ou auto-hospedado) que faz o proxy da sessão. Sem necessidade de porta aberta no host.
**Pergunta**: O remoto acessa diretamente o host (IP:porta) ou via relay intermediário?
**Resposta**: B (esse deve ter UI administrativa), a interface deverá ser de terminal e não Web.

---

### A3 — Conflito do `Ctrl+Space` como trigger NL
**Trecho**: "`Ctrl+Space` alterna modo NL" (PRD §9)
**Ambiguidade**: `Ctrl+Space` é usado por IDEs integradas ao terminal (ex.: plugins de autocompletar no Zsh/Bash com fzf, tmux, etc.) e pode conflitar.
**Interpretação A**: `Ctrl+Space` é o default, configurável pelo usuário se houver conflito.
**Interpretação B**: escolher um atalho menos conflitante como default (ex.: `Ctrl+\`, `Esc+Space`, ou prefixo dedicado).
**Pergunta**: `Ctrl+Space` é o atalho definitivo ou é configurável? Há preferência por um atalho alternativo menos conflitante?
**Resposta**: o estado normal é NL Mode (default), trigger sera !ls -al (envia o comando bash e retorna pra NL Mode ou ! sem parametros funciona como toggle (trigger) alterna o modo (exibir isso como hint na abertura do terminal)

---

### A4 — Comportamento de "Aplicar" no card de sugestão
**Trecho**: "'Aplicar' (cola no prompt local, não executa direto por padrão)" (PRD §7.5)
**Ambiguidade**: "cola no prompt" pode significar duas coisas:
**Interpretação A**: o comando aparece no prompt do Bash para o usuário editar/confirmar antes de apertar Enter — máxima segurança.
**Interpretação B**: o comando é executado diretamente após o usuário clicar "Aplicar" — mais fluido, mas menos seguro.
**Pergunta**: "Aplicar" no card apenas cola o comando no prompt (usuário ainda aperta Enter) ou executa diretamente?
**Resposta**: B

---

## 🕳️ Lacunas

### L1 — Distribuição e instalação
**O que falta**: o PRD não define como o forge_shell é instalado. Isso afeta a estrutura do pacote Python, entrypoints e packaging.
**Por que é necessário**: impacta T-03 (CLI entrypoint) e como o projeto é estruturado desde o início.
**Pergunta**: Como o forge_shell será instalado no MVP? (ex.: `pip install forge-shell`, script de instalação, binário standalone, outro)
**Resposta**: pyinstaller binario standalone

---

### L2 — Autenticação e configuração do ForgeLLM
**O que falta**: o PRD não especifica como o adapter se autentica no ForgeLLM — onde fica o endpoint, como a API key é configurada, formato da autenticação.
**Por que é necessário**: impacta diretamente T-13 (ForgeLLM adapter) — sem isso não dá para implementar.
**Pergunta**: Qual é o endpoint base do ForgeLLM e como a autenticação é feita? (API key em variável de ambiente? arquivo de config? outro)
**Resposta**: _https://github.com/symlabs-ai/forge_llm__

---

### L3 — Arquivo de configuração do forge_shell
**O que falta**: o PRD menciona várias coisas configuráveis (contexto enviado ao LLM, redaction, atalhos, etc.) mas não define onde e como o usuário configura o forge_shell.
**Por que é necessário**: sem um contrato de configuração definido, cada componente pode inventar seu próprio formato.
**Pergunta**: Existe um arquivo de config para o forge_shell? (ex.: `~/.forge_shell/config.toml`, variáveis de ambiente, flags na CLI, outro)
**Resposta**: ___config.yaml, deve ser criado e hospedar esse tipo de configuracao

---

### L4 — UI do remoto (browser)
**O que falta**: o PRD diz que a UI do remoto é browser no MVP, mas não define se é uma página servida pelo próprio forge_shell, uma app hospedada, ou outro.
**Por que é necessário**: impacta se o servidor de colaboração (T-23/T-24) também precisa servir HTML/JS ou apenas WebSocket.
**Pergunta**: A UI browser do remoto é servida pelo próprio `forge_shell share` (HTML/JS embutido) ou é uma aplicação separada?
**Resposta**: ___a interface é terminal, nao vai ter browser no client. Entretanto podemos ter um admin pro relay intermediario

---

### L5 — Modelo de negócio / licença
**O que falta**: o PRD não define se o forge_shell é open-source, closed-source, freemium, etc.
**Por que é necessário**: afeta decisões de packaging, distribuição e quais dependências podem ser usadas.
**Pergunta**: forge_shell será open-source ou closed-source? Tem planos de monetização relevantes para o MVP?
**Resposta**: _opensource MIT__

---

## 💡 Sugestões de Melhoria

### S1 — `forge_shell attach` — reconectar a sessão existente
**Sugestão**: adicionar subcomando `forge_shell attach <session-id>` para reconectar a uma sessão forge_shell existente (comportamento similar ao `tmux attach`).
**Benefício esperado**: útil para quem desconecta acidentalmente e quer retomar sem criar nova sessão.
**Impacto no escopo**: M — requer gestão de estado de sessão persistente.
**Pergunta**: Confirma incluir no escopo do cycle-01 ou deixar para ciclo futuro?
**Resposta**: ___Sim. Esse estado nao deve ficar no relay (motivos de segurança), deve ficar no host. e ser recuperado pelo relay e informado ao client

---

### S2 — Modo `--passthrough` para debug da engine
**Sugestão**: flag `forge_shell --passthrough` que liga o PTY mas desativa completamente NL Mode, collab e auditoria — útil para testar se um bug é da engine ou das camadas superiores.
**Benefício esperado**: acelera debugging da engine PTY e serve como smoke test de compatibilidade.
**Impacto no escopo**: XS — apenas bypass das camadas.
**Pergunta**: Confirma incluir?
**Resposta**: ___sim. coloque um help compreensivo pra essa funcao, esta misteriosa...

---

### S3 — Perfis de redaction configuráveis
**Sugestão**: permitir perfis nomeados de redaction (ex.: `dev`, `prod`) com regras diferentes para o que é enviado ao ForgeLLM — em vez de uma única configuração global.
**Benefício esperado**: dev usa perfil permissivo para contexto rico; prod usa perfil restritivo por padrão.
**Impacto no escopo**: S — extensão do sistema de config.
**Pergunta**: Confirma incluir no MVP ou manter redaction simples (regex + lista) por enquanto?
**Resposta**: __inclua no MVP_

---

## Resumo de Decisões

> Preenchido após receber as respostas.

| # | Item | Decisão | Impacto no PRD/Tasks |
|---|------|---------|----------------------|
| A1 | Login shell vs CLI | **CLI (aplicativo)** — roda dentro do terminal existente | T-03/T-04: sem necessidade de chsh/PAM |
| A2 | Acesso remoto: direto vs relay | **Relay intermediário** com UI administrativa; cliente é **terminal** (não browser) | T-23/T-24: protocolo host↔relay↔client; T-new: relay server + admin UI |
| A3 | Atalho NL Mode | **NL Mode é o default**; `!<cmd>` executa bash e volta; `!` sozinho faz toggle; hint na abertura | T-15: redesign completo do modo NL |
| A4 | "Aplicar" no card | **Executa diretamente** (confirmação já está no flow do card) | T-27: AC atualizado |
| L1 | Distribuição/instalação | **PyInstaller — binário standalone** | T-new: build pipeline PyInstaller |
| L2 | ForgeLLM | **Biblioteca Python** (`symlabs-ai/forge_llm`): `ChatSession`, `stream_chat()`, api_key no init, roteia para OpenAI/Anthropic/Ollama/OpenRouter | T-13: adapter usa ChatSession; sem HTTP próprio |
| L3 | Arquivo de config | **`~/.forge_shell/config.yaml`** | T-new: config base + schema YAML |
| L4 | UI do remoto | **Terminal** (não browser); relay pode ter admin web separado | T-23/T-24: protocolo terminal↔relay↔terminal |
| L5 | Licença | **MIT open-source** | Sem restrições de dependências |
| S1 | `forge_shell attach` | **Incluído** — estado da sessão no host; relay recupera e informa ao client | T-new: attach + gestão de estado no host |
| S2 | `--passthrough` | **Incluído** — com help detalhado e claro | T-new: passthrough mode |
| S3 | Perfis de redaction | **Incluído no MVP** — perfis `dev`/`prod` no config.yaml | T-19: expandido para perfis |
