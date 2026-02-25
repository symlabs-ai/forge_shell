# PRD — **sym_shell**

**Produto:** sym_shell (shell/terminal colaborativo com linguagem natural)
**Shell alvo (Unix):** **Bash**
**Core:** **Python** (engine de terminal + IA + colaboração)
**LLM:** **ForgeLLM**
**Plataformas (roadmap):** **1.0 Linux → 1.1 macOS → 1.2 Windows (ConPTY via backend nativo Rust/C)**
**Data:** 25/02/2026
**Versão:** 1.0 (PRD abrangente)

---

## 1) Visão em uma frase

O **sym_shell** é um ambiente de terminal **nativo de verdade** (não "wrapper de texto") que roda **Bash** e adiciona:

* **entrada em linguagem natural** (com confirmação, guardrails e explicação), via **ForgeLLM**
* **sessões remotas colaborativas** (assistir + chat + sugestões, e co‑controle opcional depois)
* **auditoria e segurança** pra manutenção e suporte sem virar circo

---

## 2) Problema

Terminal é o melhor e o pior lugar do mundo:

* Melhor: é rápido, automatizável, universal.
* Pior: um comando errado vira prejuízo, e suporte remoto vira "me manda print / cola log / abre call".

As dores que o sym_shell resolve:

1. **Comandos não são humanos** → linguagem natural vira comandos seguros e explicados.
2. **Ajuda remota é fricção** → sessão compartilhada com chat e contexto real.
3. **Assistência sem contexto dá ruim** → LLM e pessoas veem o mesmo estado do terminal.
4. **Terminal "fake" quebra tudo** (`sudo`, `vim`, job control) → engine de terminal real com PTY/ConPTY.

---

## 3) Objetivos do produto

### Objetivos (MVP)

* Ser **usável como terminal do dia a dia**, com experiência **nativa**:

  * `sudo`, `ssh`, `vim`, `top`, `less`, Ctrl+C/Ctrl+Z, job control, resize.
* Modo linguagem natural:

  * gerar **comandos sugeridos**
  * mostrar **explicação + risco**
  * exigir **confirmação** (padrão)
* Sessão remota:

  * **view‑only** e **suggest‑only** no MVP
  * chat lateral
  * trilha de auditoria do que aconteceu

### Objetivos (produto "sério")

* Reduzir erros operacionais (comandos destrutivos)
* Diminuir tempo de diagnóstico e de execução de runbooks
* Tornar suporte e pair debugging mais rápido e auditável

---

## 4) Não‑objetivos (por enquanto)

* Não ser VNC/desktop remoto completo (foco é **terminal**).
* Não executar comandos "no automático" por padrão (LLM não vira root).
* Não "monitorar escondido". Sempre com consentimento e indicador.
* Não prometer "100% compatibilidade com tudo do Bash em todos os cenários" no dia 1; o alvo é **compatibilidade pragmática** com **testes** e transparência do que falta.

---

## 5) Usuários e personas

1. **DevOps/SRE**: incidentes, manutenção, correções rápidas com risco alto.
2. **Engenheiro de suporte**: acompanha usuário/cliente ao vivo e orienta ações.
3. **Tech lead/mentor**: ensino prático, revisão em tempo real, "pair terminal".
4. **Dev fullstack**: quer produtividade com menos "ah, qual flag mesmo?".

---

## 6) Principais casos de uso

1. **NL → comando**

   * "mostrar quem tá consumindo CPU e matar o processo mais pesado"
   * sym_shell propõe: `ps … | sort …` + `kill …` (com confirmação e alertas)

2. **Ajuda remota**

   * você inicia sessão, manda link/token
   * remoto vê terminal em tempo real + chat
   * remoto sugere comandos em cards, você aplica com 1 clique/atalho

3. **Explique este comando**

   * você cola um comando, pede: "explica e diz se é perigoso"
   * sym_shell analisa e descreve impacto

4. **Runbook guiado**

   * LLM sugere passos incrementais, com checkpoints ("primeiro verificar, depois aplicar")

---

## 7) Escopo de funcionalidades

### 7.1 Terminal Engine (o coração)

**Requisito essencial:** sym_shell controla PTY/TTY (Unix) e ConPTY (Windows).
Nada de "pegar uma linha e mandar pro shell" (isso quebra o mundo).

**Unix (Linux/macOS)**

* Criar PTY master/slave
* Spawnar `/bin/bash` (modo interativo)
* Repasse correto de:

  * input (teclado)
  * output (stdout/stderr)
  * sinais (Ctrl+C, Ctrl+Z)
  * resize (SIGWINCH)
  * modos do terminal (raw/cooked via termios)
* Preservar experiência de aplicações full-screen:

  * `vim`, `top`, `less`, `fzf` etc.
  * Detecção de alternate screen buffer (pra saber quando não tentar "interceptar linha")

**Windows (1.2)**

* Backend nativo pequeno (Rust/C) implementa ConPTY
* Python controla via protocolo simples (pipes/stdin/out) ou IPC leve

---

### 7.2 Bash como "shell real"

* Bash é o shell executado dentro do PTY (Linux/macOS).
* Compatibilidade alvo:

  * uso interativo diário
  * scripts básicos e avançados (na medida do que "rodar dentro do bash" cobre)
* sym_shell **não reimplementa** parser do Bash.
* sym_shell **não mexe** em comportamento do Bash; ele adiciona uma camada de:

  * sugestão
  * auditoria
  * colaboração
  * segurança

---

### 7.3 Modo Linguagem Natural (NL Mode)

**Como entra**

* Atalho (ex.: `Ctrl+Space`) ou prefixo (ex.: `??`)
* Ex.: `?? listar arquivos maiores que 500MB e ordenar`

**O que retorna (sempre)**

* 1. Comando(s) sugerido(s)
* 2. Explicação curta ("o que vai acontecer")
* 3. Classificação de risco: **baixo / médio / alto**
* 4. Ações: **Executar**, **Editar**, **Cancelar**

**Regras**

* **Nunca** executar automático por padrão.
* Comandos de risco alto:

  * exigem confirmação reforçada (double confirm)
  * sugerem alternativa segura quando possível (dry-run, listagem antes)

**Contexto enviado à LLM (configurável)**

* diretório atual (pwd)
* tipo de shell (bash)
* últimas N linhas de output (com limite)
* último comando executado (se detectável)
* variáveis permitidas (whitelist)
* nunca enviar segredos (redaction)

---

### 7.4 Integração com ForgeLLM

ForgeLLM será o provider obrigatório no PRD.

**Requisitos de integração**

* Adapter em Python com:

  * request/response normal
  * streaming (se suportado) para UX rápido
  * timeouts e retry controlado
* Output **estruturado e validado** (ex.: JSON com schema):

  * `commands[]`
  * `explanation`
  * `risk_level`
  * `assumptions[]`
  * `required_user_confirmation: bool`

**Guardrails**

* Validação de schema: resposta fora do schema não executa nada; vira mensagem "não consegui".
* Sanitização:

  * bloquear que o LLM devolva "instruções textuais" como se fossem comandos
  * impedir injeção de múltiplas linhas perigosas sem explicação

---

### 7.5 Colaboração remota (terminal + chat)

**Modos**

1. **View-only (MVP):** vê terminal + chat
2. **Suggest-only (MVP):** envia sugestões em cards
3. **Co-control (pós‑MVP):** digita no terminal *apenas com permissão explícita e temporária*

**Sessão**

* Criada pelo usuário local: `sym_shell share`
* Gera link/token com expiração
* Indicador visível no terminal: "Sessão compartilhada: ATIVA"
* Lista de participantes e permissões

**Chat**

* Mensagens + threads simples
* Cards de sugestão:

  * comando proposto
  * explicação
  * "Aplicar" (cola no prompt local, não executa direto por padrão)

**Privacidade no compartilhamento**

* Se input estiver com echo desativado (ex.: senha), **não transmitir** o input.
* Opcional: mascarar padrões sensíveis no output (tokens, chaves, etc.)

---

### 7.6 Auditoria e observabilidade

* Log de eventos:

  * comandos executados (com hash/metadata)
  * quem sugeriu (LLM vs humano remoto)
  * quem aprovou
  * entradas/saídas da sessão remota
* Export:

  * texto + JSON
* Métricas:

  * latência de render
  * latência de sugestão LLM
  * taxa de falhas de spawn/PTY

---

## 8) Requisitos não funcionais

### Performance

* sym_shell não pode "deixar o terminal pesado".
* LLM e colaboração devem ser assíncronos: terminal não congela esperando resposta.

### Confiabilidade

* Ao sair, o terminal do usuário deve ser restaurado (termios), senão vira "modo doido" (isso é pecado capital).

### Segurança

* TLS obrigatório (para sessão remota).
* Tokens com expiração curta + revogação.
* Privilégios mínimos:

  * view/suggest separados
  * co-control só com grant temporário
* Zero stealth: indicador sempre ativo.

### Privacidade

* Redaction de segredos (regex + heurísticas + lista configurável)
* Configurar o que pode ser enviado ao ForgeLLM
* Sem gravação por padrão (se gravar, opt‑in + retenção definida)

---

## 9) UX e comandos (proposta)

### CLI

* `sym_shell` → inicia sessão local (spawn bash)
* `sym_shell share` → inicia share server e imprime link/token
* `sym_shell doctor` → roda diagnóstico do terminal engine

### Interação

* `Ctrl+Space` alterna modo NL
* `?? <texto>` força NL para uma linha
* `:explain <comando>` explica comando
* `:risk <comando>` avalia risco sem executar

---

## 10) Arquitetura técnica (alto nível)

### Componentes (Python)

* `terminal_engine/`

  * PTY (Unix) + abstração de backend
  * sinais, resize, termios, captura de output
* `event_bus/`

  * eventos padronizados do terminal
* `intelligence/`

  * adapter ForgeLLM
  * validação de schema + risk engine
* `collab/`

  * WebSocket server
  * autenticação de sessão
  * chat + cards
* `audit/`

  * logger estruturado + export

### Backend Windows (Rust/C) — 1.2

* Cria ConPTY, spawn do shell do Windows (PowerShell por padrão; opcional WSL bash se suportado)
* Expõe streams + resize + exit code para Python

---

## 11) Roadmap — fases, entregas e validações

### **Fase 1.0 — Linux (MVP)**

**Entregas**

* Terminal engine PTY completo:

  * spawn bash
  * raw/cooked correto
  * sinais (Ctrl+C, Ctrl+Z)
  * resize (SIGWINCH)
  * suporte estável a full-screen apps
* Modo NL com ForgeLLM:

  * sugestão de comandos + explicação + risco
  * confirmação padrão
  * schema validation
  * redaction básica
* Colaboração:

  * view-only + chat
  * suggest-only (cards)
  * tokens expiráveis
* Auditoria:

  * log local de eventos + export

**Validações (gate de release)**

* Bateria de testes interativos (manual + automatizada onde der):

  * `sudo -v` e `sudo ls` (sem quebrar TTY)
  * `ssh user@host`
  * `vim`, `top`, `less`
  * `sleep 100` + Ctrl+Z + `bg` + `fg`
  * resize de janela não quebra UI do `top/vim`
* "Terminal não fica quebrado" após crash/exit (termios restaurado)
* LLM:

  * nunca executa sem confirmação
  * comandos perigosos exigem double confirm
* Colaboração:

  * input de senha não é transmitido quando echo off

---

### **Fase 1.1 — macOS**

**Entregas**

* Reuso do backend Unix com ajustes macOS:

  * termios/PTY edge cases
  * packaging (ex.: brew formula ou instalador)
* Mesma experiência do Linux

**Validações**

* Repetir a bateria do Linux no macOS
* Verificar:

  * estabilidade de resize
  * comportamento de `sudo` e apps full-screen
  * performance (sem lag perceptível)

---

### **Fase 1.2 — Windows**

**Entregas**

* Backend nativo ConPTY (Rust/C):

  * spawn do shell (PowerShell default; opcional WSL bash)
  * resize + streams confiáveis
  * encerramento limpo
* Protocolo Python ↔ backend nativo (documentado)
* Colaboração e NL funcionando igual (com adaptações de comando conforme shell)
* Instalador Windows (MSI/winget/choco — decidir)

**Validações**

* Testes de interactive console no Windows:

  * `pwsh` interativo
  * programas full-screen (quando disponíveis)
  * resize sem corromper output
  * reconexão de sessão remota
* Garantir que input sensível não vaze no share

---

## 12) Métricas de sucesso

* **Adoção**: sessões ativas/semana, tempo de sessão
* **Eficiência**:

  * tempo para completar tarefas comuns vs baseline
  * taxa de sugestões aceitas (sem edição / com edição)
* **Segurança**:

  * taxa de bloqueios/confirmations de comandos perigosos
  * incidentes de vazamento de dados (meta: zero)
* **Qualidade**:

  * crash-free rate
  * "terminal state restored" rate (meta: 100%)

---

## 13) Riscos e mitigação

1. **Engine de terminal é traiçoeira**

   * Mitigação: checklist técnico rígido + `sym_shell doctor` + testes repetidos.

2. **LLM sugere bobagem com confiança**

   * Mitigação: confirmação padrão, schema, risk engine e "modo seguro" por default.

3. **Compartilhamento vira porta de abuso**

   * Mitigação: consentimento, indicador sempre visível, tokens curtos, RBAC e auditoria.

4. **Windows pode virar buraco negro**

   * Mitigação: só entrar no 1.2 com backend nativo mínimo e protocolo simples.

---

## 14) Questões em aberto (decisões que você precisa cravar)

* O sym_shell será **login shell** (via `chsh`) ou só aplicativo/CLI?
  (Login shell dá a experiência mais "nativa" e reduz "camadas").
* UI do remoto: browser (web) é MVP; cliente nativo só se virar gargalo.
* Nível de redaction: regex simples no MVP vs classificador mais forte depois.

---

## 15) Checklist técnico (com validações)

Use isso como "Definition of Done" da engine. Se falhar aqui, não lança.

### 15.1 PTY/TTY — Unix (Linux/macOS)

* [ ] Spawn do bash com PTY slave correto (controlando terminal do child)
* [ ] Termios entra em raw mode quando necessário e **restaura no exit**
* [ ] Repasse de sinais funciona:

  * [ ] Ctrl+C interrompe processo correto
  * [ ] Ctrl+Z suspende e job control funciona (`bg`, `fg`)
* [ ] Resize funciona:

  * [ ] SIGWINCH atualizado e apps se adaptam
* [ ] I/O sem corrupção:

  * [ ] UTF-8 ok
  * [ ] sem "caracteres comidos" em alta taxa de output
* [ ] Full-screen apps:

  * [ ] `vim` abre/fecha sem quebrar prompt
  * [ ] `top` atualiza e respeita resize
  * [ ] `less` rola e sai normal
  * [ ] `fzf` (se instalado) funciona
* [ ] `sudo` funciona **sem quebrar TTY**:

  * [ ] `sudo -v`
  * [ ] `sudo ls`
* [ ] `ssh` funciona:

  * [ ] login interativo remoto
  * [ ] sair retorna ao prompt local corretamente

### 15.2 Engine de detecção de "modo interceptável"

* [ ] Detecta alternate screen buffer e desativa interceptação de linha
* [ ] Reativa ao sair de alternate screen buffer
* [ ] Não quebra readline/editline do bash

### 15.3 Colaboração

* [ ] Stream de output em tempo real (WebSocket)
* [ ] Latência aceitável (meta prática: "não irrita")
* [ ] Reconnect:

  * [ ] remoto cai e volta sem corromper sessão
* [ ] Permissões:

  * [ ] view-only não injeta input
  * [ ] suggest-only só cria cards
* [ ] Input sensível:

  * [ ] quando echo off, não transmite input digitado
* [ ] Indicador de sessão sempre visível

### 15.4 ForgeLLM / NL Mode

* [ ] Adapter ForgeLLM:

  * [ ] timeout configurável
  * [ ] retry controlado
  * [ ] fallback "não consegui" sem travar terminal
* [ ] Resposta da LLM é validada por schema (fora do schema = rejeita)
* [ ] Nunca executa comando sem confirmação
* [ ] Risk engine:

  * [ ] identifica padrões destrutivos (ex.: `rm -rf`, `dd`, `mkfs`, `chmod -R` agressivo)
  * [ ] exige double confirm para risco alto
* [ ] Redaction:

  * [ ] remove tokens/keys/senhas do contexto enviado

### 15.5 Auditoria

* [ ] Log de sessão inclui:

  * [ ] comandos executados
  * [ ] origem (usuário/LLM/remoto)
  * [ ] aprovações
  * [ ] join/leave
* [ ] Export JSON + texto

### 15.6 Windows (1.2)

* [ ] Backend ConPTY em Rust/C:

  * [ ] spawn e kill confiáveis
  * [ ] resize ok
  * [ ] streams sem deadlock
* [ ] Protocolo documentado (mensagens, framing, erros)
* [ ] Mesmo comportamento de permissão e privacidade do share
