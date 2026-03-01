# Documentação do Projeto

Esta pasta contém a documentação principal do projeto.

---

## Binários e Instalação

O forge_shell produz **3 binários standalone** via PyInstaller, cada um com um papel
distinto. Essa separação permite que o cliente que recebe suporte instale apenas
o binário leve (~5 MB), sem carregar dependências de LLM.

### `forge_shell` — CLI completo (~50 MB)

Binário principal usado pelo **técnico de suporte**. Contém toda a stack:
NL Mode, LLM, sistema de agentes, colaboração remota e auditoria.

```
pip install -e .          # desenvolvimento
forge_shell               # sessão local com NL Mode
forge_shell share         # compartilha terminal via relay
forge_shell attach <code> <senha>   # visualiza sessão remota
forge_shell agent <code> <senha>    # conecta como agent IA
forge_shell doctor        # diagnóstico da engine PTY
forge_shell relay         # sobe servidor relay (dev local)
forge_shell config [show|edit]      # configuração
forge_shell --passthrough           # PTY puro (debug)
```

**Dependências incluídas:** forge_llm, pyte, httpx, readability-lxml, websockets, pyyaml

**Quando usar:** na máquina do técnico que presta suporte. É o único binário
que oferece NL Mode, sugestões LLM e o sistema de agentes.

### `forge_host` — Host PTY leve (~5 MB)

Binário usado pelo **cliente que recebe suporte**. Compartilha o terminal
via relay sem NL Mode, sem LLM e sem qualquer dependência pesada.

```
forge_host                # PTY puro local (passthrough)
forge_host share          # compartilha terminal via relay
forge_host share --regen  # regenera machine code permanente
```

**Dependências incluídas:** websockets, pyyaml (apenas)

**Excluído:** forge_llm, pyte, httpx, readability-lxml, sistema de agentes,
NLInterceptor, NLModeEngine

**Quando usar:** instalar na máquina do cliente. O técnico conecta via
`forge_shell attach` ou `forge_shell agent` a partir da sua própria máquina.

### `forge_relay` — Servidor relay WebSocket (~5 MB)

Binário do **servidor relay** que intermedia a comunicação entre host e viewers.
Deploy em servidor com IP público para que host e viewers conectem sem NAT
ou portas abertas.

```
forge_relay                        # porta do config (padrão 8060)
forge_relay --port 9000            # porta customizada
forge_relay --host 127.0.0.1      # bind apenas localhost
```

**Dependências incluídas:** websockets, pyyaml (apenas)

**Excluído:** forge_llm, pyte, httpx, readability-lxml, sistema de agentes,
TerminalSession, engine PTY

**Quando usar:** deploy em servidor público (VPS, cloud) para que
`forge_host share` e `forge_shell attach` conectem via WebSocket.

### Fluxo de deploy típico

```
Servidor (VPS)          Cliente              Técnico
+--------------+     +------------+     +---------------+
| forge_relay  |<--->| forge_host |     | forge_shell   |
| (porta 8060) |     | share      |     | attach <code> |
+--------------+     +------------+     +---------------+
      ^                                        |
      +----------------------------------------+
                    WebSocket
```

1. **Servidor:** `forge_relay` rodando com IP público (ex: relay.empresa.com)
2. **Cliente:** `forge_host share` — exibe machine code + senha
3. **Técnico:** `forge_shell attach <code> <senha>` — visualiza o terminal do cliente

### Build

```bash
./scripts/build.sh            # build todos (relay + host + shell)
./scripts/build.sh relay      # apenas forge_relay
./scripts/build.sh host       # apenas forge_host
./scripts/build.sh shell      # apenas forge_shell
./scripts/build.sh --clean    # limpar + build todos
```

Os binários são gerados em `dist/forge_relay`, `dist/forge_host` e `dist/forge_shell`.

### Instalação via pip (desenvolvimento)

```bash
pip install -e .              # instala os 3 entry points
```

Entry points registrados no `pyproject.toml`:

| Comando | Entry point |
|---------|-------------|
| `forge_shell` | `src.adapters.cli.main:main` |
| `forge_relay` | `src.adapters.cli.relay_main:main` |
| `forge_host` | `src.adapters.cli.host_main:main` |

---

## `docs/integrations/` — Guias Técnicos de Integração

Guias de **integração técnica** com o ForgeBase e Forge LLM:

- `docs/integrations/forgebase_guides/` — Regras, arquitetura, testes e guias do ForgeBase.
- `docs/integrations/forge_llm_guides/` — Guias do Forge LLM Client/SDK (providers, streaming, tool calling, etc.).

Para desenvolvedores e symbiotas de código:

- Use `docs/integrations/` como **guia técnico** para implementar o produto final.
