# forge_shell

Terminal Bash nativo com linguagem natural, colaboração remota bidirecional e auditoria de sessão.

Engine PTY real (não wrapper) — sudo, vim, ssh e job control funcionam normalmente.

## Instalação

```bash
pip install -e .
```

## Uso

```bash
forge_shell                           # sessão local com NL Mode
forge_shell --passthrough             # PTY puro (debug)
forge_shell share                     # compartilha terminal via relay
forge_shell attach <code> <senha>     # controla terminal remoto (bidirecional)
forge_shell agent <code> <senha>      # conecta como agent IA
forge_shell relay                     # sobe servidor relay (dev local)
forge_shell doctor                    # diagnóstico da engine PTY
forge_shell config [show|edit]        # configuração
```

### NL Mode

Modo padrão. Digite em linguagem natural e o forge_shell traduz para comandos bash com guardrails de risco.

- `!` alterna entre NL Mode e Bash Mode
- `!<cmd>` executa bash direto e retorna ao NL Mode
- `:explain <cmd>` analisa um comando sem executar
- `:risk <cmd>` classifica risco (HIGH/MEDIUM/LOW)
- `:help` ajuda inline

### Colaboração remota

Arquitetura relay 3 camadas — host e clients conectam via WebSocket sem NAT ou portas abertas.

```
Servidor (VPS)           Cliente              Tecnico
+--------------+     +------------+     +---------------+
| forge_relay  |<--->| forge_host |     | forge_shell   |
| (porta 8060) |     | share      |     | attach <code> |
+--------------+     +------------+     +---------------+
      ^                                        |
      +----------------------------------------+
                    WebSocket (wss://)
```

**Host** compartilha o terminal:
```bash
forge_host share       # exibe machine code + senha
```

**Viewer** controla o terminal remoto (bidirecional):
```bash
forge_shell attach <code> <senha>   # Ctrl+] para desconectar
```

**Agent** conecta como IA e envia comandos ou sugestões:
```bash
forge_shell agent <code> <senha>
# stdin JSON: {"type":"input","data":"<base64>"}         (keystrokes)
#             {"commands":[...],"explanation":"..."}       (suggest card)
```

Multiplos viewers e agents podem conectar simultaneamente a uma mesma sessão.

### Chat

F4 abre painel de chat ao lado do terminal. Host, viewers e agents compartilham o chat em tempo real.

## Binários standalone

3 binários via PyInstaller, cada um com papel distinto:

| Binário | Tamanho | Uso |
|---------|---------|-----|
| `forge_shell` | ~50 MB | CLI completo (tecnico) — NL Mode, LLM, agentes, collab |
| `forge_host` | ~5 MB | Host leve (cliente) — PTY + relay, sem LLM |
| `forge_relay` | ~5 MB | Servidor relay WebSocket |

```bash
./scripts/build.sh              # build todos
./scripts/build.sh relay        # apenas forge_relay
```

## Configuração

`~/.forge_shell/config.yaml` — criado automaticamente na primeira execução.

```yaml
nl_mode:
  default_active: true
  context_lines: 50

llm:
  provider: openai
  model: gpt-4o-mini

relay:
  url: wss://relay.palhano.services
  port: 8060
```

## Testes

```bash
pytest tests/ -v
```

## Licença

MIT
