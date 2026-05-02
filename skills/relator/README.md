# relator

Skill que gera relatório narrativo dos últimos 7 dias e manda no WhatsApp via Evolution API.

## Instalação

1. Copia esta pasta pro seu diretório de skills do Claude Code:
   ```bash
   cp -r relator ~/.claude/skills/
   ```

2. Configura as variáveis no `.env` do seu projeto:
   ```env
   META_ACCESS_TOKEN=EAAxxxx...
   META_AD_ACCOUNT_ID=act_1234567890
   OBSIDIAN_VAULT_PATH=/Users/voce/Documents/obsidian-bravo
   EVOLUTION_API_URL=https://evo.seu-dominio.com
   EVOLUTION_API_KEY=sua-apikey-global
   EVOLUTION_INSTANCE=bravo-bot
   ```

3. Instala dependências Python (se for usar os `scripts/`):
   ```bash
   pip install requests python-dotenv
   ```

## Uso

No Claude Code:
```
manda o relatório do acme pro joão
```

A skill puxa contexto + histórico + métricas, monta a narrativa, mostra a prévia, e envia no WhatsApp do João depois do seu ok.

Variações que funcionam:
```
manda o relatório do acme pro joão
relatório dos últimos 30 dias do acme pra mim
preview do relatório do acme  (não envia, só mostra)
```

## Como obter as credenciais

**Meta:**
1. [developers.facebook.com](https://developers.facebook.com) → criar app
2. Marketing API → token long-lived com `ads_read`
3. `act_id` em [adsmanager.facebook.com](https://adsmanager.facebook.com)

**Evolution API:**
1. Sobe sua instância Evolution (Docker ou hosted)
2. Pega a `apikey` global do `.env` da Evolution
3. Cria a instância (`bravo-bot`) e conecta o número via QR code

## Roadmap

- [ ] Suporte a janela customizada (7d, 14d, 30d, mês corrente)
- [ ] Envio de gráfico (imagem) junto com o texto
- [ ] Comparativo semana vs semana anterior
- [ ] Versão em áudio (TTS) pro WhatsApp
