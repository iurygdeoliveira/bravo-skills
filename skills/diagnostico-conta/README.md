# diagnostico-conta

Skill que faz auditoria da conta em 4 frentes e devolve lista priorizada de correções.

## Instalação

1. Copia esta pasta pro seu diretório de skills do Claude Code:
   ```bash
   cp -r diagnostico-conta ~/.claude/skills/
   ```

2. Configura as variáveis no `.env` do seu projeto:
   ```env
   META_ACCESS_TOKEN=EAAxxxx...
   META_AD_ACCOUNT_ID=act_1234567890
   OBSIDIAN_VAULT_PATH=/Users/voce/Documents/obsidian-bravo
   PAGESPEED_API_KEY=AIzaSy...   # opcional
   ```

3. Instala dependências Python:
   ```bash
   pip install requests python-dotenv
   ```

## Uso

No Claude Code:
```
faz diagnóstico da conta do acme
```

A skill:
1. Roda os 4 checks
2. Salva em `clientes/acme/diagnostico-2025-01-15.md`
3. No chat, mostra resumo + top 3 de alta prioridade

Variações:
```
diagnóstico do acme
auditoria da conta acme
checa só estrutura do acme   (roda só 1 check)
```

## Como obter as credenciais

**Meta:** veja `subir-campanha/README.md`.

**PageSpeed (opcional):**
1. [console.cloud.google.com](https://console.cloud.google.com) → criar projeto
2. APIs & Services → ativar PageSpeed Insights API
3. Credentials → criar API Key

## Roadmap

- [ ] Comparar com diagnóstico anterior (mostrar evolução)
- [ ] Gerar versão PDF do diagnóstico
- [ ] Check de Google Ads (versão multi-plataforma)
- [ ] Sugestões automáticas de correção (criar tickets pra outras skills)
- [ ] Score consolidado da conta (0-100)
