"""
narrative — monta os 4 parágrafos do relatório.

Estrutura:
    1. Panorama       — números principais
    2. Mudanças       — o que rodou de diferente nos últimos N dias
    3. Atenção        — o que merece foco
    4. Próximo passo  — recomendação acionável

Voz Bravo: direto, frase curta, sem corporativês.
WhatsApp markdown: *negrito*, _itálico_. Usa estrategicamente.
"""
from __future__ import annotations

from typing import Any


def brl(v: float) -> str:
    """Formata BRL: 12345.6 → '12.345,60'."""
    s = f"{v:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def num(v: int | float) -> str:
    """Formata inteiro: 12345 → '12.345'."""
    if isinstance(v, float):
        v = int(v)
    return f"{v:,}".replace(",", ".")


def build_narrative(
    client_name: str,
    metrics: dict[str, Any],
    historico: dict[str, Any],
    contexto: dict[str, Any],
    days: int,
) -> str:
    """Retorna o texto pronto pra mandar no WhatsApp."""

    if not metrics.get("has_data") or metrics.get("spend", 0) <= 0:
        return _dead_week(client_name, days, historico)

    p1 = _panorama(metrics, days, contexto)
    p2 = _mudancas(metrics, historico, days)
    p3 = _atencao(metrics, contexto)
    p4 = _proximo_passo(metrics, contexto)

    blocks = [b for b in (p1, p2, p3, p4) if b]
    return "\n\n".join(blocks)


# ── parágrafos ──────────────────────────────────────────────────────


def _panorama(m: dict[str, Any], days: int, ctx: dict[str, Any]) -> str:
    spend = m["spend"]
    purchases = int(m.get("purchases") or 0)
    leads = int(m.get("leads") or 0)
    cpa = m.get("cpa") or 0.0
    roas = m.get("roas") or 0.0
    revenue = m.get("purchase_value") or 0.0

    janela = f"últimos {days}d" if days != 7 else "última semana"

    parts = [f"*Panorama ({janela})*"]

    if revenue > 0:
        parts.append(
            f"Faturou *R$ {brl(revenue)}* com R$ {brl(spend)} de mídia — "
            f"ROAS de *{roas:.2f}*."
        )
        if purchases > 0:
            parts.append(
                f"{num(purchases)} venda{'s' if purchases != 1 else ''} no período, "
                f"CPA de R$ {brl(cpa)}."
            )
    elif purchases > 0:
        parts.append(
            f"R$ {brl(spend)} investidos, *{num(purchases)} venda"
            f"{'s' if purchases != 1 else ''}* a CPA de R$ {brl(cpa)}."
        )
    elif leads > 0:
        parts.append(
            f"R$ {brl(spend)} investidos, *{num(leads)} lead"
            f"{'s' if leads != 1 else ''}* a CPL de R$ {brl(cpa)}."
        )
    else:
        parts.append(
            f"R$ {brl(spend)} investidos. Tráfego rodando mas sem conversão "
            f"registrada na janela."
        )

    # sub-métricas inline
    if m["impressions"] > 0:
        parts.append(
            f"{num(m['impressions'])} impressões, CTR {m['ctr']:.2f}%, "
            f"CPM R$ {brl(m['cpm'])}."
        )

    return " ".join(parts)


def _mudancas(m: dict[str, Any], hist: dict[str, Any], days: int) -> str:
    recent = (hist.get("recent_text") or "").strip()

    parts = ["*O que mudou*"]

    if not recent:
        parts.append(
            f"Sem registros novos no histórico nos últimos {days}d — "
            f"conta rodou no piloto automático."
        )
        return " ".join(parts)

    # corta o histórico em até 600 chars pra não estufar o WhatsApp
    snippet = recent
    if len(snippet) > 600:
        snippet = snippet[:600].rstrip() + "..."

    parts.append("Últimos movimentos no histórico:")
    return " ".join(parts) + "\n" + snippet


def _atencao(m: dict[str, Any], ctx: dict[str, Any]) -> str:
    fm = ctx.get("frontmatter") or {}

    cpa_meta = _to_float(fm.get("cpa_meta") or fm.get("meta_cpa"))
    roas_meta = _to_float(fm.get("roas_meta") or fm.get("meta_roas"))
    ticket = _to_float(fm.get("ticket") or fm.get("ticket_medio"))

    alertas: list[str] = []

    cpa = m.get("cpa") or 0.0
    roas = m.get("roas") or 0.0
    ctr = m.get("ctr") or 0.0
    spend = m.get("spend") or 0.0

    if cpa_meta and cpa > cpa_meta * 1.15:
        alertas.append(
            f"CPA estourou — *R$ {brl(cpa)}* contra meta de R$ {brl(cpa_meta)} "
            f"(+{((cpa / cpa_meta) - 1) * 100:.0f}%)."
        )
    if roas_meta and roas > 0 and roas < roas_meta * 0.85:
        alertas.append(
            f"ROAS abaixo da meta — *{roas:.2f}* contra alvo de {roas_meta:.2f}."
        )
    if ticket and m.get("purchase_value", 0) and m.get("purchases", 0):
        avg_ticket = m["purchase_value"] / m["purchases"]
        if avg_ticket < ticket * 0.85:
            alertas.append(
                f"Ticket médio abaixo do esperado — R$ {brl(avg_ticket)} "
                f"(esperado ~R$ {brl(ticket)})."
            )
    if ctr and ctr < 1.0 and spend > 100:
        alertas.append(
            f"CTR baixo (*{ctr:.2f}%*) — sinal de criativo cansando."
        )

    parts = ["*Atenção*"]
    if alertas:
        parts.append(" ".join(alertas))
    else:
        parts.append(
            "Nada crítico. Métricas dentro da curva — segue o jogo."
        )
    return " ".join(parts)


def _proximo_passo(m: dict[str, Any], ctx: dict[str, Any]) -> str:
    fm = ctx.get("frontmatter") or {}
    cpa_meta = _to_float(fm.get("cpa_meta") or fm.get("meta_cpa"))
    roas_meta = _to_float(fm.get("roas_meta") or fm.get("meta_roas"))

    cpa = m.get("cpa") or 0.0
    roas = m.get("roas") or 0.0
    ctr = m.get("ctr") or 0.0
    spend = m.get("spend") or 0.0

    parts = ["*Próximo passo*"]

    if cpa_meta and cpa > cpa_meta * 1.15:
        parts.append(
            "Pausa o conjunto mais caro e sobe 2 criativos novos pra "
            "testar ângulo."
        )
    elif roas_meta and roas > roas_meta * 1.15:
        parts.append(
            "Escalar — sobe 20-30% no orçamento dos conjuntos vencedores."
        )
    elif ctr < 1.0 and spend > 100:
        parts.append(
            "Renovar criativo — o atual já cansou. Bota 2-3 variações "
            "novas no ar."
        )
    elif not m.get("has_data") or spend < 10:
        parts.append(
            "Conta sem volume — verifica se as campanhas estão ativas e "
            "com orçamento liberado."
        )
    else:
        parts.append(
            "Manter ritmo. Vale testar 1 criativo novo pra não depender "
            "dos atuais."
        )
    return " ".join(parts)


def _dead_week(client_name: str, days: int, hist: dict[str, Any]) -> str:
    janela = f"últimos {days}d" if days != 7 else "última semana"
    msg = (
        f"*{client_name} — {janela}*\n\n"
        f"Última {janela.split()[-1]} sem volume — checa se a conta tá rodando "
        f"(orçamento liberado, campanhas ativas, pixel ok).\n\n"
    )
    recent = (hist.get("recent_text") or "").strip()
    if recent:
        msg += f"*Histórico recente:*\n{recent[:400]}"
    return msg.strip()


def _to_float(v: Any) -> float:
    if v is None:
        return 0.0
    try:
        s = str(v).replace(",", ".").strip()
        s = "".join(ch for ch in s if ch.isdigit() or ch == "." or ch == "-")
        return float(s) if s else 0.0
    except (TypeError, ValueError):
        return 0.0
