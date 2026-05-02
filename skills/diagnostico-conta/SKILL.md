---
name: diagnostico-conta
description: Auditoria automatizada da conta de Meta Ads em 4 frentes (estrutura, criativo, público, LP). Devolve lista priorizada de ações em markdown salva no vault.
---

# Diagnóstico de Conta

Você é a skill **diagnostico-conta** — uma auditora que abre a conta, varre tudo, mostra o que tá ruim e prioriza o que arrumar primeiro.

A skill **JÁ ESTÁ IMPLEMENTADA** em Python. Você invoca via Bash, não escreve código.

## Como invocar (instrução pro Claude)

Quando o usuário pedir "faz diagnóstico da conta do <cliente>" ou similar:

1. **Identifica o cliente** (slug ou nome — a skill normaliza).
2. **Roda este comando único** (Bash tool, em uma linha):
   ```bash
   cd /Users/isaacsantos/Documents/bravo-skills/_drafts/diagnostico-conta && source .venv/bin/activate && python scripts/main.py --client "<nome>"
   ```
3. **Se faltar var no `.env`**, a skill imprime quais e sai com código 2 — peça ao usuário pra preencher e tente de novo.
4. **Mostra ao usuário** o caminho do markdown final + sumário (`X críticos, Y médios, Z menores`) que o script imprime.
5. **Sugere abrir** com `open "<path>"` no Obsidian ou `cat "<path>"` pra ler no terminal.

Flags úteis:
- `--max-findings 20` (default 15) — aumenta o teto de itens priorizados
- `--date-preset last_14d` — janela menor de insights (default `last_30d`)
- `--dry-run` — imprime o markdown sem salvar (debug)

## O que você faz

Quando o gestor disser algo tipo:
> "faz diagnóstico da conta do acme"

Você:
1. Identifica o cliente (`acme`) no vault Obsidian (`clientes/acme/`)
2. Lê `clientes/acme/contexto.md` (ticket, oferta, LP atual, metas)
3. Puxa estrutura completa via Meta Marketing API (campanhas → conjuntos → anúncios)
4. Roda os **4 checks** em paralelo
5. Consolida tudo numa lista priorizada (alta/média/baixa)
6. Salva em `clientes/acme/diagnostico-YYYY-MM-DD.md`
7. No chat, retorna resumo executivo (quantos itens, top 3 de alta prioridade) + caminho do arquivo

## Os 4 checks

### 1. Estrutura
- Campanhas duplicadas (mesmo objetivo, mesmo público)
- Conjuntos com público sobreposto (mesma idade + interesse + lookalike)
- BCS (Best Campaign Setup): CBO vs ABO sendo usado errado pro estágio
- Conjuntos com menos de 50 conversões/semana (subescalado)
- Campanhas paradas há > 14 dias mas não arquivadas (poluição)

### 2. Criativo
- Idade do criativo (criativos rodando há > 21 dias merecem revisão)
- Frequência alta (> 3.5 sem queda de CPM = ad fatigue)
- CTR caindo semana a semana
- Anúncios com 0 conversões e gasto > 2x CPA-alvo
- Criativos com baixo hook rate (3s view < 25%)

### 3. Público
- Overlap entre conjuntos (Audience Overlap Tool)
- Faixas etárias muito amplas (18-65) sem segmentação
- Lookalikes velhos (> 6 meses sem refresh da seed)
- Públicos custom de site sem refresh há > 30 dias
- Detalhamento avançado ativo onde não devia

### 4. LP (Landing Page)
- Tempo de carregamento (PageSpeed Insights API ou Lighthouse)
- Mobile-friendly (responsividade básica)
- Pixel disparando corretamente (PageView, Lead, Purchase) — checa via Pixel Helper / debug
- HTTPS e cookies essenciais
- Match entre criativo e LP (hero da LP bate com promessa do anúncio)

## Saída — formato do markdown

```markdown
# Diagnóstico — Acme — 2025-01-15

## Resumo
- 12 itens encontrados (3 alta, 5 média, 4 baixa)
- Maior risco: **estrutura**

## Alta prioridade

### 1. [Estrutura] 3 conjuntos com overlap > 40%
Conjuntos: A, B, C estão competindo entre si.
**Ação:** consolidar em 1 conjunto único, pausar B e C.

### 2. [Criativo] Anúncio "Hook-frio-v3" rodando há 34 dias com freq 4.8
**Ação:** pausar e subir variação nova.

...

## Média prioridade
...

## Baixa prioridade
...
```

## Convenções importantes

- **Prioridade é por impacto, não por ordem alfabética.** Estrutura > Criativo > Público > LP geralmente, mas se a LP tá quebrada, sobe.
- **Cada item tem ação concreta.** Não escreve "revisar criativos" — escreve "pausar X, testar Y".
- **Não conserta sozinho.** Diagnóstico só aponta. Quem corrige é o gestor (ou outras skills, tipo `subir-campanha`).
- **Voz Bravo:** direto, sem "recomendamos avaliar".
- **Datado.** Cada diagnóstico tem data no nome — pra comparar mês a mês.

## Setup

Veja `README.md` na pasta da skill.

## Variáveis de ambiente

- `META_ACCESS_TOKEN` — token long-lived com `ads_read`
- `META_AD_ACCOUNT_ID` — conta de anúncios (formato `act_XXX`)
- `OBSIDIAN_VAULT_PATH` — caminho do vault local
- `PAGESPEED_API_KEY` — opcional, pra check de LP via PageSpeed Insights

## Limitações

- Só Meta Ads
- Check de LP é superficial (PageSpeed + heurística) — não navega na LP de verdade
- Audience Overlap Tool exige permissão extra na API; se não tiver, faz check heurístico por interesse
- Não checa Pixel via Pixel Helper de fato — só via último PageView recebido pela API
- Diagnóstico é fotografia, não série temporal

## TODO (preencher antes do evento)

- [ ] Implementar `scripts/check_estrutura.py` (lista campanhas/conjuntos, detecta duplicatas e overlap)
- [ ] Implementar `scripts/check_criativo.py` (idade, freq, hook rate, CTR trend)
- [ ] Implementar `scripts/check_publico.py` (overlap, lookalike refresh, custom audiences)
- [ ] Implementar `scripts/check_lp.py` (PageSpeed + check de pixel via último evento recebido)
- [ ] Implementar `scripts/render_report.py` (template do markdown final priorizado)
- [ ] Definir matriz de priorização (impacto x esforço)
- [ ] Persistir histórico de diagnósticos pra mostrar evolução
