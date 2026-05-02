# vigia-24h

Skill que monitora a conta 24/7 e alerta no WhatsApp quando algo crítico muda.

## Instalação

1. Copia esta pasta pro seu diretório de skills do Claude Code:
   ```bash
   cp -r vigia-24h ~/.claude/skills/
   ```

2. Configura as variáveis no `.env` do seu projeto:
   ```env
   META_ACCESS_TOKEN=EAAxxxx...
   META_AD_ACCOUNT_ID=act_1234567890
   OBSIDIAN_VAULT_PATH=/Users/voce/Documents/obsidian-bravo
   EVOLUTION_API_URL=https://evo.seu-dominio.com
   EVOLUTION_API_KEY=sua-apikey-global
   EVOLUTION_INSTANCE=bravo-bot
   VIGIA_INTERVAL_MIN=15
   ```

3. Instala dependências Python:
   ```bash
   pip install requests python-dotenv
   ```

4. (Opcional pra produção) Sobe como serviço:
   ```bash
   # systemd, pm2 ou tmux — escolha sua bala
   pm2 start scripts/loop.py --name vigia-acme -- --client acme
   ```

## Uso

No Claude Code:
```
ativa o vigia no acme
```

Pra parar:
```
desativa vigia do acme
```

Pra ver status:
```
status do vigia
```

Quando o vigia detecta algo, você recebe no WhatsApp:
> "CPA do acme dobrou nas últimas 3h (R$ 18 → R$ 41). Conjunto Frio-25-45 tá puxando. Recomendo pausar. **Responde ok que eu sigo.**"

Você responde "ok" → ele pausa e confirma.

## Configurando os limiares

No `clientes/<nome>/contexto.md`, adiciona um bloco:

```yaml
vigia:
  cpa_alvo: 25
  cpa_max_pct: 50         # alerta se passar 50% acima do alvo
  saldo_min: 100
  budget_diario: 300
  pacing_max_pct: 130     # alerta se gastar 130% do budget até 12h
```

Sem esse bloco, a skill usa defaults conservadores.

## Roadmap

- [ ] Vigia simultâneo em N clientes
- [ ] Dashboard web com status de todas as contas vigiadas
- [ ] Alertas de oportunidade (CPA caindo, vale subir budget)
- [ ] Integração com Telegram além de WhatsApp
- [ ] Replay: "o que aconteceu no acme entre 3h e 6h da manhã?"
