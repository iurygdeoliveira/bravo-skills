"""
alert.py — formata alerta + envia WhatsApp via Evo Go.

Formato:

*Vigia 24h · {cliente}*
{emoji} {olho_que_disparou}: {dado_atual} (baseline: {baseline})

Recomendação: {ação concreta}.

Responde *ok* que eu sigo, *cancela* que ignoro.
"""
from __future__ import annotations

from typing import Any

from evo_go import EvoGo, EvoGoError


# ── formatação por olho ────────────────────────────────────
def _line_cpa(r: dict) -> str:
    cur = r.get("current", 0)
    base = r.get("baseline", 0)
    pct = r.get("delta_pct", 0)
    sign = "+" if pct >= 0 else ""
    return f"🔴 CPA estourou: R${cur:.2f} (baseline: R${base:.2f}, {sign}{pct:.0f}%)"


def _reco_cpa(r: dict) -> str:
    return (
        "Recomendação: pausar o conjunto que tá com o CPA mais alto e "
        "relocar 70% do budget pros 1-2 que estão dentro da meta."
    )


def _line_saldo(r: dict) -> str:
    cur = r.get("current") or 0
    days = r.get("days_left")
    extra = f" — sobra {days}d no ritmo atual" if days is not None else ""
    return f"🔴 Saldo baixo: R${cur:.2f} (mín: R${r.get('min', 100):.0f}){extra}"


def _reco_saldo(r: dict) -> str:
    return "Recomendação: recarregar a conta agora antes que o Meta pause tudo automaticamente."


def _line_status(r: dict) -> str:
    issues = r.get("issues", [])
    if not issues:
        return "🔴 Status anormal detectado"
    bits = []
    for it in issues:
        if it["kind"] == "account":
            bits.append(f"conta status={it['status_code']} ({it.get('disable_reason') or 'sem motivo informado'})")
        elif it["kind"] == "ads":
            bits.append(f"{it['count']} anúncio(s) em status problemático há +{6}h")
    return "🔴 Status: " + "; ".join(bits)


def _reco_status(r: dict) -> str:
    issues = r.get("issues", [])
    has_account = any(i["kind"] == "account" for i in issues)
    if has_account:
        return "Recomendação: abrir suporte da Meta na hora — conta inativa = zero entrega."
    return "Recomendação: revisar criativos reprovados, ajustar e reenviar pra revisão."


def _line_pacing(r: dict) -> str:
    spend = r.get("spend_today", 0)
    budget = r.get("daily_budget_total", 0)
    ratio = r.get("ratio", 0)
    return f"🔴 Pacing: gastou R${spend:.2f} de R${budget:.2f} ({ratio*100:.0f}% do daily)"


def _reco_pacing(r: dict) -> str:
    return (
        "Recomendação: cortar o daily budget pela metade nos conjuntos que estão queimando "
        "e checar se o lance subiu (concorrência ou audiência saturada)."
    )


_FORMATTERS = {
    "cpa":    (_line_cpa, _reco_cpa),
    "saldo":  (_line_saldo, _reco_saldo),
    "status": (_line_status, _reco_status),
    "pacing": (_line_pacing, _reco_pacing),
}


# ── alert principal ────────────────────────────────────────
def format_alert(cliente: str, fired_eyes: list[dict]) -> str:
    """
    Recebe lista de olhos que dispararam (fired=True). Monta mensagem única.
    Se vários dispararem, lista todos com 1 recomendação por olho.
    """
    lines = [f"*Vigia 24h · {cliente}*", ""]

    for r in fired_eyes:
        eye = r.get("eye")
        fmt = _FORMATTERS.get(eye)
        if not fmt:
            continue
        line_fn, reco_fn = fmt
        lines.append(line_fn(r))
        lines.append("")
        lines.append(reco_fn(r))
        lines.append("")

    lines.append("Responde *ok* que eu sigo, *cancela* que ignoro.")
    return "\n".join(lines)


def send_alert(message: str, evo: EvoGo, number: str) -> dict:
    """Envia via Evo Go. Levanta EvoGoError se falhar."""
    return evo.send_text(number=number, text=message, delay_ms=1000)


# ── pretty print pro terminal ──────────────────────────────
def print_eye_summary(eyes: list[dict]) -> None:
    """Imprime resumo bonitinho dos 4 olhos no terminal."""
    print("")
    print("┌─ olhos ─────────────────────────────────────────────")
    for r in eyes:
        eye = r.get("eye", "?")
        level = r.get("level", "?")
        if r.get("fired"):
            tag = "DISPAROU"
        else:
            tag = "ok"
        # detalhe curto
        if eye == "cpa":
            detail = f"hoje R${r.get('current', 0):.2f} · 14d R${r.get('baseline', 0):.2f}"
        elif eye == "saldo":
            cur = r.get("current")
            detail = f"R${cur:.2f}" if isinstance(cur, (int, float)) else (r.get("reason") or "n/a")
        elif eye == "status":
            issues = r.get("issues", [])
            detail = f"{len(issues)} issue(s)" if issues else "limpo"
        elif eye == "pacing":
            detail = f"R${r.get('spend_today', 0):.2f}/R${r.get('daily_budget_total', 0):.2f}"
        else:
            detail = ""
        print(f"│ {level} {eye:<7} {tag:<10} {detail}")
    print("└─────────────────────────────────────────────────────")
    print("")
