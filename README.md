# Bravo Skills

Skills de **Claude Code** pra gestores de tráfego. Distribuídas durante a **Imersão Bravo**.

> Este repo **cresce ao vivo durante o evento** — cada skill é liberada após o bloco que a apresentou.

## O que é

Cada pasta em `skills/` é uma skill pronta pra usar com o Claude Code. Você instala e roda comandos no seu terminal pra automatizar tarefas do dia a dia: subir campanha, gerar relatório, monitorar conta, diagnosticar performance, espionar concorrente.

Além das skills, este repo também tem:
- `obsidian-template/` — vault Obsidian pronto pra ser a memória viva da sua operação (índices, templates de cliente, padrões de organização).
- `guides/` — guias técnicos prontos pra implementar (ex: tracking Meta Pixel + CAPI).

## Como instalar uma skill

```bash
git clone https://github.com/euisaacsantos/bravo-skills.git
cd bravo-skills/skills/<nome-da-skill>
# leia o README dentro de cada skill
```

Cada skill tem seu próprio `README.md` com instruções específicas.

## Como usar o template Obsidian

```bash
cp -R obsidian-template ~/meu-vault-bravo
# abra a pasta no Obsidian (File → Open vault)
```

Os arquivos `CLAUDE.md` em cada subpasta são lidos automaticamente pelo Claude Code quando você roda comandos dentro do vault — eles ensinam o Claude como organizar suas notas.

## Skills disponíveis

| Skill | O que faz | Status |
|---|---|---|
| `subir-campanha` | Sobe campanha completa no Meta Ads via 1 frase | ✓ |
| `espionar-concorrente` | Baixa ativos da Facebook Ads Library de concorrentes | ✓ |
| `espionar-concorrente-pro` | Versão Pro: transcreve vídeos, descreve imagens, gera HTML report com IA | ✓ |
| `relator` | Gera relatório narrativo no WhatsApp do cliente | ✓ |
| `vigia-24h` | Monitora contas 24/7 e alerta no WhatsApp | ✓ |
| `diagnostico-conta` | Auditoria automatizada da conta | ✓ |

✓ = disponível no repo

## Guias

| Guia | Conteúdo |
|---|---|
| [`guides/META-CAPI-TRACKING.md`](guides/META-CAPI-TRACKING.md) | Implementação de tracking Meta Ads com Pixel (web) + CAPI (server) na Vercel |

## Mentoria Bravo

Pra gestores de tráfego que querem dominar IA, virar fornecedores de tecnologia pros próprios clientes e parar de apagar incêndio. Conheça em **[bravo.growthtap.com.br/mentoria](https://bravo.growthtap.com.br/mentoria)**.

O que está incluso:

1. **Vibe Coding com IA** — codar aplicações do zero com Claude Code (quizzes, dashboards, painéis, integrações) e cobrar dos seus clientes por isso.
2. **Conteúdo direto ao ponto** — aulas sobre o que gestor de tráfego usa no dia a dia: landing pages, criativos, relatórios, rastreamento.
3. **Skills compartilhados** — acesse e compartilhe skills prontos entre membros: automações, prompts, scripts e repositórios.
4. **MCP — Integração com Claude** — a plataforma se conecta ao seu Claude Code. Peça relatórios, busque conteúdo e acesse skills direto pela conversa.
5. **Canvas de geração de imagens** — node-based pra criar e variar criativos com IA. Suba referências, conecte geradores, gere variações em segundos.
6. **ZapFlow (SaaS incluso)** — plataforma completa de automação WhatsApp via API oficial. Instale na sua VPS, use com todos os clientes que quiser.
7. **Calls semanais no Zoom** — sessões ao vivo com o grupo, gravadas e disponíveis na plataforma.
8. **Grupo no WhatsApp** — todos os membros num grupo só, com participação ativa do mentor.
9. **Novos SaaS sem custo extra** — a plataforma cresce junto com a mentoria; membros atuais ganham acesso a cada nova ferramenta lançada.
10. **Agendamento na plataforma (Black)** — membros Black agendam calls 1:1 direto pela plataforma.

E ainda mais skills exclusivas — incluindo a `master`, skill orquestradora que executa a rotina semanal completa de operação.

## Licença

Uso livre pra os participantes da imersão. Não redistribuir o conteúdo desse repo sem permissão.
