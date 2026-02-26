# Sessão: f3899c34-c45a-444c-8cf1-d5526f3eab6c

## Metadados
- **Session ID:** f3899c34-c45a-444c-8cf1-d5526f3eab6c
- **Session ID (curto):** f3899c34
- **Iniciada:** 2026-02-26T14:00:00Z
- **Branch:** main
- **Projeto:** /home/palhano/dev/research/sym_shell

## Feature Atual
- **Nome:** Relay 3-layer architecture
- **Status:** in_progress
- **Descrição:** Separar o relay do share. `sym_shell relay` = serviço standalone. `sym_shell share` conecta como cliente ao relay remoto. Nenhum dos lados precisa de porta aberta.

## Arquivos Tocados

| Status | Arquivo | Observação |
|--------|---------|------------|
| [M] | src/adapters/cli/main.py | add relay subcommand + remove inline relay from share |
| [C] | tests/unit/test_relay_subcommand.py | testes do novo subcomando relay |
| [M] | tests/unit/test_c4t05_share_wired.py | remove RelayHandler de share patches |
| [M] | tests/unit/test_c6t04_share_relay.py | remove RelayHandler de share patches |

## Decisões Técnicas

| Decisão | Motivo | Data |
|---------|--------|------|
| relay = serviço separado | host não precisa de porta aberta, igual RustDesk | 2026-02-26 |
| share usa apenas RelayBridge | já existia, conecta como cliente ao relay | 2026-02-26 |
| relay --port usa config como default | consistência com resto do sistema | 2026-02-26 |

## TODOs
- [ ] Deploy do relay em palhano.services (DevOps)
