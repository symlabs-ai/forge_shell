# PRD — forge_shell

> Projeto: forge_shell
> Autor: stakeholder
> Data: 2026-02-25
> Status: draft

---

## 1. Hipótese

### 1.1 Contexto
O terminal é a interface mais poderosa do desenvolvedor/ops — rápido, automatizável, universal. Porém um comando errado causa prejuízo, e suporte remoto exige fricção alta (prints, calls, logs colados).

### 1.2 Sinal de Mercado
Ferramentas de IA para terminal existem como wrappers de texto (não controlam PTY real), o que as torna incompatíveis com `sudo`, `vim`, job control e apps full-screen. Sessões remotas de terminal dependem de tmux/screen + call de voz para contexto.

### 1.3 Oportunidade
Um terminal que seja nativo de verdade (PTY real), com LLM integrado para linguagem natural e colaboração remota com contexto compartilhado — sem abrir mão da experiência Unix.

### 1.4 Grau de Certeza
Médio-alto (50–75%) — dor vivida pelo autor, observada em equipes de suporte/ops.

---

## 2. Visão

### 2.1 Intenção Central
Terminal Bash nativo com linguagem natural, colaboração remota e auditoria — sem quebrar nada que já funciona.

### 2.2 Problema
1. Comandos não são humanos → LLM sugere comandos seguros e explicados.
2. Ajuda remota é fricção → sessão compartilhada com chat e contexto real.
3. Assistência sem contexto falha → LLM e pessoas veem o mesmo estado do terminal.
4. Terminal "fake" quebra `sudo`, `vim`, job control → engine PTY/ConPTY real.

### 2.3 Público-Alvo
- **DevOps/SRE**: incidentes, manutenção, comandos de alto risco.
- **Engenheiro de suporte**: acompanha usuário/cliente ao vivo.
- **Tech lead/mentor**: ensino prático, pair terminal.
- **Dev fullstack**: produtividade, menos "qual flag mesmo?".

### 2.4 Diferencial Estratégico
Engine PTY real (não wrapper) + LLM com guardrails + colaboração remota nativa — tudo no mesmo processo, sem telnet/VNC.

---

## 3. Modelo de Negócio

### 3.1 Monetização
[não especificado no PRD — ver questionário L1]

### 3.2 Mercado
Dev/ops solo e times pequenos; mercado de ferramentas de produtividade para terminal (qualitativo para MVP).

---

## 4. Métricas de Sucesso

| Métrica | Meta | Prazo |
|---------|------|-------|
| Sessões ativas/semana | — | pós-lançamento |
| Taxa de sugestões NL aceitas | — | pós-lançamento |
| Terminal state restored rate | 100% | MVP |
| Incidentes de vazamento de dados | 0 | MVP |
| Crash-free rate | > 99% | MVP |

---

## 5. User Stories + Acceptance Criteria

### US-01: Entrada em linguagem natural (NL Mode como default)
**Como** dev/ops, **quero** descrever o que preciso fazer em português/inglês, **para** receber um comando Bash correto sem precisar lembrar flags e sintaxe.

> **NL Mode é o estado padrão.** Ao abrir o forge_shell, o usuário já está em NL Mode.
> Hint exibido na abertura: `forge_shell  |  NL Mode  |  ! para bash  |  !<cmd> executa bash direto`

**Acceptance Criteria:**
- **AC-01**: Given forge_shell está aberto (NL Mode ativo), When digito `listar arquivos maiores que 500MB`, Then forge_shell exibe comando sugerido, explicação curta e classificação de risco (baixo/médio/alto).
- **AC-02**: Given NL Mode ativo, When digito `!ls -al`, Then forge_shell executa `ls -al` diretamente no Bash e retorna ao NL Mode automaticamente.
- **AC-03**: Given NL Mode ativo, When digito `!` sozinho, Then forge_shell alterna para Bash Mode; digitando `!` novamente, retorna ao NL Mode (toggle).
- **AC-04**: Given uma sugestão NL exibida, When seleciono "Executar", Then o comando é executado após confirmação explícita do usuário.
- **AC-05**: Given o risco é classificado como alto, When a sugestão é exibida, Then é exigida confirmação dupla (double confirm) antes de executar.
- **AC-06**: Given o adapter ForgeLLM retorna resposta fora do schema, When NL Mode processa, Then forge_shell exibe "não consegui" sem travar o terminal.

### US-02: Terminal nativo (PTY real)
**Como** usuário do forge_shell, **quero** que o terminal se comporte exatamente como Bash nativo, **para** usar `sudo`, `ssh`, `vim`, `top`, job control e qualquer app interativo sem quebras.

**Acceptance Criteria:**
- **AC-01**: Given forge_shell está rodando, When executo `sudo ls`, Then o prompt de senha aparece e funciona sem quebrar o TTY.
- **AC-02**: Given um processo em foreground, When pressiono Ctrl+Z, Then o processo é suspenso e `bg`/`fg` funcionam corretamente.
- **AC-03**: Given `vim` está aberto, When redimensiono a janela do terminal, Then o vim adapta o layout via SIGWINCH.
- **AC-04**: Given forge_shell é encerrado (normalmente ou por crash), When retorno ao terminal do host, Then o estado do terminal (termios) está restaurado — sem "modo doido".
- **AC-05**: Given `vim` está aberto (alternate screen buffer ativo), When o modo NL é acionado, Then forge_shell não tenta interceptar a linha do vim.

### US-03: Explicação e análise de risco
**Como** dev/ops, **quero** entender o que um comando faz e qual seu risco, **para** tomar decisões seguras antes de executar.

**Acceptance Criteria:**
- **AC-01**: Given um comando qualquer, When digito `:explain rm -rf /tmp/teste`, Then forge_shell exibe descrição do que o comando faz e impacto esperado.
- **AC-02**: Given um comando destrutivo (`rm -rf`, `dd`, `mkfs`, `chmod -R`), When o risk engine analisa, Then a classificação retorna "alto" e é exigido double confirm.
- **AC-03**: Given `:risk <cmd>`, When executado, Then forge_shell exibe classificação de risco sem executar o comando.

### US-04: Sessão remota (view-only + chat)
**Como** engenheiro de suporte ou mentor, **quero** visualizar o terminal de outro usuário em tempo real com chat lateral, **para** orientar sem precisar de call ou troca de prints.

**Acceptance Criteria:**
- **AC-01**: Given o host executa `forge_shell share`, When o remoto acessa com o token recebido, Then o remoto vê o terminal do host em tempo real (read-only).
- **AC-02**: Given uma sessão ativa, When o remoto digita no chat, Then a mensagem aparece para o host (e vice-versa).
- **AC-03**: Given uma sessão ativa com modo view-only, When o remoto tenta injetar input no terminal, Then a ação é bloqueada — sem efeito no terminal do host.
- **AC-04**: Given uma sessão ativa, When o host está digitando uma senha (echo off), Then o input não é transmitido para o remoto.
- **AC-05**: Given uma sessão ativa, When abro o terminal, Then um indicador de "Sessão compartilhada: ATIVA" está sempre visível.

### US-05: Sugestões remotas (suggest-only / cards)
**Como** engenheiro de suporte ou mentor remoto, **quero** propor comandos ao host em forma de cards, **para** orientar ações sem executar nada por conta própria.

**Acceptance Criteria:**
- **AC-01**: Given o remoto está em modo suggest-only, When propõe um comando, Then o host recebe um card com comando, explicação e botão "Aplicar".
- **AC-02**: Given o host clica em "Aplicar" no card, When o comando é aplicado, Then ele é colado no prompt do Bash — não executado automaticamente.
- **AC-03**: Given o remoto está em modo suggest-only, When tenta injetar input direto no terminal, Then a ação é bloqueada.

### US-06: Auditoria de sessão
**Como** tech lead ou responsável por segurança, **quero** um log estruturado de tudo que aconteceu na sessão, **para** auditoria, treinamento e diagnóstico pós-incidente.

**Acceptance Criteria:**
- **AC-01**: Given uma sessão encerrada, When exporto o log, Then o arquivo contém: comandos executados, origem (usuário/LLM/remoto), aprovações e eventos de join/leave.
- **AC-02**: Given o log, When exporto em JSON, Then o schema é válido e parseável.
- **AC-03**: Given o log, When exporto em texto plano, Then é legível por humanos sem ferramentas especiais.

---

## 6. Requisitos Não-Funcionais

| Requisito | Descrição | Prioridade |
|-----------|-----------|------------|
| Performance | Terminal sem lag perceptível; LLM e collab assíncronos (não bloqueiam I/O) | P0 |
| Confiabilidade | Termios restaurado em 100% dos casos de saída (normal ou crash) | P0 |
| Segurança | TLS obrigatório para sessão remota; tokens com expiração curta + revogação | P0 |
| Privacidade | Redaction de secrets antes de enviar contexto ao ForgeLLM | P0 |
| Compatibilidade | Linux (1.0), macOS (1.1), Windows ConPTY (1.2) | P1 |

---

## 7. Restrições Técnicas + Decision Log

### 7.1 Restrições
- Core em **Python** (engine + IA + collab)
- Shell alvo Unix: **Bash** (não reimplementa parser)
- LLM: **ForgeLLM** (provider obrigatório no MVP)
- Windows 1.2: backend nativo **Rust/C** para ConPTY, controlado via IPC pelo Python

### 7.2 Decision Log

| # | Decisão | Contexto | Alternativas Consideradas | Data |
|---|---------|----------|---------------------------|------|
| 1 | PTY real (não wrapper de texto) | Compatibilidade com sudo, vim, job control | Wrapper readline, expect | 2026-02-25 |
| 2 | ForgeLLM como biblioteca Python (`symlabs-ai/forge_llm`) | Integração interna Symlabs; abstrai múltiplos providers | HTTP endpoint próprio | 2026-02-25 |
| 3 | View-only + suggest-only no MVP (co-control pós-MVP) | Risco de abuso; complexidade de RBAC | Co-control desde o início | 2026-02-25 |
| 4 | Confirmação obrigatória (nunca auto-executar via NL) | Segurança; LLM não vira root | Auto-execução com flag | 2026-02-25 |
| 5 | Windows apenas na fase 1.2 | Backend ConPTY requer Rust/C; risco alto | Windows desde 1.0 | 2026-02-25 |
| 6 | CLI (aplicativo), não login shell | Mais seguro, fácil de adotar/reverter; falha não deixa usuário sem terminal | Login shell via chsh | 2026-02-25 |
| 7 | NL Mode como estado padrão | UX orientada a linguagem natural; bash acessível via `!` | Bash como default, NL via atalho | 2026-02-25 |
| 8 | Relay intermediário (host↔relay↔client); cliente é terminal | Sem necessidade de porta aberta no host; UI administrativa no relay | Acesso direto IP:porta | 2026-02-25 |
| 9 | Binário standalone via PyInstaller | Instalação sem dependência de Python no host | pip install, conda | 2026-02-25 |
| 10 | Config em `~/.forge_shell/config.yaml` | Padrão Unix para apps de terminal; YAML legível | .env, TOML, flags only | 2026-02-25 |
| 11 | Perfis de redaction (`dev`/`prod`) no MVP | Contexto rico em dev; máxima privacidade em prod | Redaction global única | 2026-02-25 |
| 12 | MIT open-source | Sem restrições de dependências; adoção comunitária | Closed-source, BSL | 2026-02-25 |

---

## 8. Riscos e Mitigações

| Risco | Impacto | Probabilidade | Mitigação |
|-------|---------|---------------|-----------|
| Engine PTY é traiçoeira (edge cases) | Alto | Alta | Checklist técnico §15 + `doctor` + testes repetidos |
| LLM sugere comando errado com confiança | Alto | Média | Confirmação padrão + schema + risk engine |
| Sessão remota vira vetor de abuso | Alto | Baixa | Consentimento + indicador + tokens curtos + RBAC |
| Windows vira buraco negro de bugs | Médio | Alta | Só entra no 1.2 com backend mínimo validado |
| Termios não restaurado → terminal quebrado | Alto | Baixa | Try/finally + signal handlers + `doctor` |

---

## 9. Fora de Escopo (v1)

- VNC/desktop remoto completo
- Execução automática de comandos LLM (sem confirmação)
- Monitoramento sem consentimento
- Co-control remoto (pós-MVP)
- 100% de compatibilidade Bash em todos os cenários (meta é compatibilidade pragmática)
- Windows (fase 1.2), macOS (fase 1.1)
- UI browser para cliente remoto (cliente é terminal; relay pode ter admin web separado)
- Login shell (forge_shell é aplicativo CLI, não substitui o shell padrão do sistema)
