---
purpose: Como este projeto chega em produção. Leitura rápida para devs.
maintained_by: DevOps (~/dev/devops)
full_guide: ~/dev/devops/kb/dev-deploy-guide.md
---

# Deploy — ForgeShell Relay

## Fluxo

```
git push main → Staging (automático) → promote forge-shell → Produção
```

## Staging (automático)

Push na `main` dispara Gitea Actions. Sem ação manual.

## Produção (self-service)

```bash
promote forge-shell
```

O script faz tudo: valida staging, atualiza produção, reinicia serviço, health check.

**Detalhes**: porta 8060, domínio relay.symlabs.ai, systemd `forge-shell-relay.service`, sem migrations.

## Primeiro deploy?

Se o ForgeShell Relay nunca foi para produção, use `/ask devops`.

## Se algo deu errado

Use `/ask devops` para rollback ou investigação.
