"""
estrutura.py — Auditoria de estrutura da conta.

Detecta:
- Campanhas com mesmo objetivo + mesmo público (duplicação)
- BCS (Cost Cap, Bid Cap) sem dados pra suportar
- Mais de 5 conjuntos por campanha (provável overlap)
- Conjuntos pausados há > 30 dias (limpeza)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

# bid strategies que dependem de histórico — usar sem dados é furada
BID_STRATEGIES_RISKY = {"COST_CAP", "LOWEST_COST_WITH_BID_CAP", "BID_CAP", "TARGET_COST"}


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        # formato Meta: "2024-09-15T10:23:00-0300"
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _adset_signature(adset: dict[str, Any]) -> str:
    """Gera assinatura grosseira de público pra detectar duplicação."""
    t = adset.get("targeting") or {}
    parts: list[str] = []
    parts.append(str(t.get("age_min", "")))
    parts.append(str(t.get("age_max", "")))
    parts.append(",".join(sorted(t.get("genders") or [str(g) for g in t.get("genders", [])])))
    spec = t.get("flexible_spec") or t.get("targeting_spec") or []
    interests: list[str] = []
    if isinstance(spec, list):
        for block in spec:
            for it in (block or {}).get("interests", []) or []:
                interests.append(str(it.get("id") or it.get("name") or ""))
    parts.append(",".join(sorted(interests)))
    geo = (t.get("geo_locations") or {})
    countries = ",".join(sorted(geo.get("countries") or []))
    parts.append(countries)
    return "|".join(parts)


def run(
    *,
    campaigns: list[dict[str, Any]],
    adsets: list[dict[str, Any]],
    ads: list[dict[str, Any]],
    insights_by_campaign: dict[str, dict[str, Any]],
    insights_by_adset: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    campaigns_by_id = {c["id"]: c for c in campaigns}
    adsets_by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in adsets:
        adsets_by_campaign[a.get("campaign_id", "")].append(a)

    # ── 1. Campanhas duplicadas (mesmo objetivo + mesma assinatura de público) ──
    sig_groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for c in campaigns:
        if c.get("effective_status") not in ("ACTIVE", "PAUSED"):
            continue
        objective = c.get("objective", "")
        c_adsets = adsets_by_campaign.get(c["id"], [])
        if not c_adsets:
            continue
        # usa primeira assinatura — heurística simples
        sig = _adset_signature(c_adsets[0])
        sig_groups[(objective, sig)].append(c["name"])

    for (objective, _), names in sig_groups.items():
        if len(names) >= 2:
            findings.append({
                "frente": "Estrutura",
                "severity": "alta",
                "titulo": f"{len(names)} campanhas duplicadas — objetivo {objective}",
                "descricao": (
                    f"Detectadas campanhas com objetivo `{objective}` e assinatura de público "
                    f"praticamente idêntica: {', '.join(names[:5])}. Elas competem entre si no "
                    "leilão e canibalizam o aprendizado."
                ),
                "recomendacao": (
                    f"Mantenha a campanha de melhor CPA, pause as outras e migre os criativos "
                    f"vencedores. Sugestão: consolidar em 1 campanha com CBO."
                ),
            })

    # ── 2. BCS arriscado sem volume ──
    for c in campaigns:
        if c.get("effective_status") != "ACTIVE":
            continue
        strategy = (c.get("bid_strategy") or "").upper()
        if strategy not in BID_STRATEGIES_RISKY:
            continue
        ins = insights_by_campaign.get(c["id"], {})
        try:
            spend = float(ins.get("spend", 0) or 0)
        except (TypeError, ValueError):
            spend = 0.0
        # actions = conversões agregadas
        n_conversions = 0
        for act in ins.get("actions") or []:
            if any(k in (act.get("action_type") or "") for k in ("purchase", "lead", "complete_registration")):
                try:
                    n_conversions += int(float(act.get("value", 0)))
                except (TypeError, ValueError):
                    pass
        if spend < 200 or n_conversions < 50:
            findings.append({
                "frente": "Estrutura",
                "severity": "alta",
                "titulo": f"`{c['name']}` usa {strategy} sem dados pra suportar",
                "descricao": (
                    f"Campanha rodando com bid strategy `{strategy}` mas só tem {n_conversions} "
                    f"conversões e R$ {spend:.0f} de gasto nos últimos 30 dias. Estratégias de "
                    "Cost Cap / Bid Cap precisam de pelo menos 50 conversões pra funcionar — "
                    "abaixo disso o algoritmo não calibra e a campanha entrega mal."
                ),
                "recomendacao": (
                    "Troque pra `LOWEST_COST_WITHOUT_CAP` (volume máximo) até bater 50 conversões/semana "
                    "estáveis. Só então volte pra Cost/Bid Cap se realmente precisar de previsibilidade."
                ),
            })

    # ── 3. Campanhas com > 5 conjuntos (overlap potencial) ──
    for c in campaigns:
        if c.get("effective_status") not in ("ACTIVE",):
            continue
        c_adsets = [a for a in adsets_by_campaign.get(c["id"], []) if a.get("effective_status") == "ACTIVE"]
        if len(c_adsets) > 5:
            findings.append({
                "frente": "Estrutura",
                "severity": "media",
                "titulo": f"`{c['name']}` tem {len(c_adsets)} conjuntos ativos",
                "descricao": (
                    f"Campanhas com mais de 5 conjuntos ativos quase sempre têm overlap de público "
                    f"e canibalizam orçamento entre si. Cada conjunto precisa de 50 conversões/semana "
                    f"pra sair de aprendizado — com {len(c_adsets)} conjuntos isso fica matemática "
                    "muito difícil de fechar."
                ),
                "recomendacao": (
                    "Consolide em 2-3 conjuntos no máximo. Pause os com pior CPA dos últimos 14 dias "
                    "e mova orçamento pros vencedores. Ou ative CBO pra Meta distribuir."
                ),
            })

    # ── 4. Conjuntos pausados há > 30 dias (limpeza) ──
    stale_pausados: list[str] = []
    for a in adsets:
        if a.get("effective_status") != "PAUSED":
            continue
        updated = _parse_dt(a.get("updated_time"))
        if updated and (now - updated).days > 30:
            stale_pausados.append(a["name"])

    if stale_pausados:
        # 1 finding agregado pra não inflar a lista
        findings.append({
            "frente": "Estrutura",
            "severity": "baixa",
            "titulo": f"{len(stale_pausados)} conjuntos pausados há mais de 30 dias",
            "descricao": (
                "Há conjuntos pausados sem alteração há mais de 30 dias poluindo a conta. "
                f"Exemplos: {', '.join(stale_pausados[:5])}"
                + (f" (+{len(stale_pausados) - 5})" if len(stale_pausados) > 5 else "")
                + ". Limpeza facilita navegação e reduz risco de reativar conjunto velho por engano."
            ),
            "recomendacao": (
                "Arquive (não delete) os conjuntos pausados há > 30 dias que você não pretende "
                "reativar. Use a coluna 'Última edição' como filtro."
            ),
        })

    return findings
