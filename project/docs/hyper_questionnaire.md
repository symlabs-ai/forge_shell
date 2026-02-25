# Questionário de Alinhamento — sym_shell

> Gerado pelo ft_coach em hyper-mode a partir do PRD v1.0 (2026-02-25).
> Responda cada pergunta para que os artefatos sejam finalizados e o ciclo TDD possa iniciar.

---

## 🔍 Pontos Ambíguos

### A1 — Login shell vs. aplicativo CLI
**Trecho**: "O sym_shell será login shell (via `chsh`) ou só aplicativo/CLI?" (PRD §14)
**Ambiguidade**: o PRD menciona a decisão mas não a toma. As duas opções têm implicações arquiteturais significativas.
**Interpretação A**: sym_shell é login shell — substitui o Bash como shell padrão do usuário. Máxima integração, mas exige mais robustez (qualquer falha = usuário sem terminal).
**Interpretação B**: sym_shell é um aplicativo CLI — o usuário roda `sym_shell` dentro do terminal existente, como tmux. Mais seguro, mais fácil de adotar e reverter.
**Pergunta**: Para o MVP, sym_shell será login shell ou aplicativo CLI (rodando dentro do terminal existente)?
**Resposta**: ___

---

### A2 — Como o remoto acessa a sessão compartilhada
**Trecho**: "você inicia sessão, manda link/token" (PRD §6); "UI do remoto: browser (web) é MVP" (PRD §14)
**Ambiguidade**: o PRD diz que a UI do remoto é browser, mas não define como o servidor de colaboração é acessado — se há um relay externo, se é acesso direto ao IP do host, ou outro mecanismo.
**Interpretação A**: servidor WebSocket roda localmente no host; o remoto acessa diretamente via IP:porta + token. Requer que o host tenha porta aberta/acessível.
**Interpretação B**: há um relay/servidor intermediário (hospedado pela Symlabs ou auto-hospedado) que faz o proxy da sessão. Sem necessidade de porta aberta no host.
**Pergunta**: O remoto acessa diretamente o host (IP:porta) ou via relay intermediário?
**Resposta**: ___

---

### A3 — Conflito do `Ctrl+Space` como trigger NL
**Trecho**: "`Ctrl+Space` alterna modo NL" (PRD §9)
**Ambiguidade**: `Ctrl+Space` é usado por IDEs integradas ao terminal (ex.: plugins de autocompletar no Zsh/Bash com fzf, tmux, etc.) e pode conflitar.
**Interpretação A**: `Ctrl+Space` é o default, configurável pelo usuário se houver conflito.
**Interpretação B**: escolher um atalho menos conflitante como default (ex.: `Ctrl+\`, `Esc+Space`, ou prefixo dedicado).
**Pergunta**: `Ctrl+Space` é o atalho definitivo ou é configurável? Há preferência por um atalho alternativo menos conflitante?
**Resposta**: ___

---

### A4 — Comportamento de "Aplicar" no card de sugestão
**Trecho**: "'Aplicar' (cola no prompt local, não executa direto por padrão)" (PRD §7.5)
**Ambiguidade**: "cola no prompt" pode significar duas coisas:
**Interpretação A**: o comando aparece no prompt do Bash para o usuário editar/confirmar antes de apertar Enter — máxima segurança.
**Interpretação B**: o comando é executado diretamente após o usuário clicar "Aplicar" — mais fluido, mas menos seguro.
**Pergunta**: "Aplicar" no card apenas cola o comando no prompt (usuário ainda aperta Enter) ou executa diretamente?
**Resposta**: ___

---

## 🕳️ Lacunas

### L1 — Distribuição e instalação
**O que falta**: o PRD não define como o sym_shell é instalado. Isso afeta a estrutura do pacote Python, entrypoints e packaging.
**Por que é necessário**: impacta T-03 (CLI entrypoint) e como o projeto é estruturado desde o início.
**Pergunta**: Como o sym_shell será instalado no MVP? (ex.: `pip install sym-shell`, script de instalação, binário standalone, outro)
**Resposta**: ___

---

### L2 — Autenticação e configuração do ForgeLLM
**O que falta**: o PRD não especifica como o adapter se autentica no ForgeLLM — onde fica o endpoint, como a API key é configurada, formato da autenticação.
**Por que é necessário**: impacta diretamente T-13 (ForgeLLM adapter) — sem isso não dá para implementar.
**Pergunta**: Qual é o endpoint base do ForgeLLM e como a autenticação é feita? (API key em variável de ambiente? arquivo de config? outro)
**Resposta**: ___

---

### L3 — Arquivo de configuração do sym_shell
**O que falta**: o PRD menciona várias coisas configuráveis (contexto enviado ao LLM, redaction, atalhos, etc.) mas não define onde e como o usuário configura o sym_shell.
**Por que é necessário**: sem um contrato de configuração definido, cada componente pode inventar seu próprio formato.
**Pergunta**: Existe um arquivo de config para o sym_shell? (ex.: `~/.sym_shell/config.toml`, variáveis de ambiente, flags na CLI, outro)
**Resposta**: ___

---

### L4 — UI do remoto (browser)
**O que falta**: o PRD diz que a UI do remoto é browser no MVP, mas não define se é uma página servida pelo próprio sym_shell, uma app hospedada, ou outro.
**Por que é necessário**: impacta se o servidor de colaboração (T-23/T-24) também precisa servir HTML/JS ou apenas WebSocket.
**Pergunta**: A UI browser do remoto é servida pelo próprio `sym_shell share` (HTML/JS embutido) ou é uma aplicação separada?
**Resposta**: ___

---

### L5 — Modelo de negócio / licença
**O que falta**: o PRD não define se o sym_shell é open-source, closed-source, freemium, etc.
**Por que é necessário**: afeta decisões de packaging, distribuição e quais dependências podem ser usadas.
**Pergunta**: sym_shell será open-source ou closed-source? Tem planos de monetização relevantes para o MVP?
**Resposta**: ___

---

## 💡 Sugestões de Melhoria

### S1 — `sym_shell attach` — reconectar a sessão existente
**Sugestão**: adicionar subcomando `sym_shell attach <session-id>` para reconectar a uma sessão sym_shell existente (comportamento similar ao `tmux attach`).
**Benefício esperado**: útil para quem desconecta acidentalmente e quer retomar sem criar nova sessão.
**Impacto no escopo**: M — requer gestão de estado de sessão persistente.
**Pergunta**: Confirma incluir no escopo do cycle-01 ou deixar para ciclo futuro?
**Resposta**: ___

---

### S2 — Modo `--passthrough` para debug da engine
**Sugestão**: flag `sym_shell --passthrough` que liga o PTY mas desativa completamente NL Mode, collab e auditoria — útil para testar se um bug é da engine ou das camadas superiores.
**Benefício esperado**: acelera debugging da engine PTY e serve como smoke test de compatibilidade.
**Impacto no escopo**: XS — apenas bypass das camadas.
**Pergunta**: Confirma incluir?
**Resposta**: ___

---

### S3 — Perfis de redaction configuráveis
**Sugestão**: permitir perfis nomeados de redaction (ex.: `dev`, `prod`) com regras diferentes para o que é enviado ao ForgeLLM — em vez de uma única configuração global.
**Benefício esperado**: dev usa perfil permissivo para contexto rico; prod usa perfil restritivo por padrão.
**Impacto no escopo**: S — extensão do sistema de config.
**Pergunta**: Confirma incluir no MVP ou manter redaction simples (regex + lista) por enquanto?
**Resposta**: ___

---

## Resumo de Decisões

> Preenchido após receber as respostas.

| # | Item | Decisão | Impacto no PRD/Tasks |
|---|------|---------|----------------------|
| A1 | Login shell vs CLI | ___ | Arquitetura T-03/T-04 |
| A2 | Acesso remoto: direto vs relay | ___ | Arquitetura T-23/T-24 |
| A3 | Atalho NL Mode | ___ | T-15 |
| A4 | "Aplicar" no card | ___ | T-27 AC |
| L1 | Distribuição/instalação | ___ | T-03 |
| L2 | ForgeLLM auth/endpoint | ___ | T-13 |
| L3 | Arquivo de config | ___ | Todos os pilares |
| L4 | UI browser do remoto | ___ | T-23/T-24 |
| L5 | Modelo de negócio | ___ | Packaging |
| S1 | `sym_shell attach` | incluído / ciclo futuro | T-new |
| S2 | `--passthrough` debug | incluído / descartado | T-new |
| S3 | Perfis de redaction | incluído / simples por ora | T-19 |
