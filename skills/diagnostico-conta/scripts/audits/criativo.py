"""
criativo.py — Auditoria de criativos.

Detecta:
- Criativos rodando há > 30 dias com freq > 3x (ad fatigue)
- Conjunto sem variação criativa (1 só anúncio)
- Anúncios com CTR < 0.5% rodando há > 7 dias
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def run(
    *,
    ads: list[dict[str, Any]],
    adsets: list[dict[str, Any]],
    insights_by_ad: dict[str, dict[str, Any]],
    insights_by_adset: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    active_ads = [a for a in ads if a.get("effective_status") == "ACTIVE"]
    ads_by_adset: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in active_ads:
        ads_by_adset[a.get("adset_id", "")].append(a)

    # ── 1. Ad fatigue (>30 dias + freq > 3) ──
    fatiguing: list[tuple[str, int, float]] = []
    for ad in active_ads:
        created = _parse_dt(ad.get("created_time"))
        if not created:
            continue
        days = (now - created).days
        if days < 30:
            continue
        ins = insights_by_ad.get(ad["id"], {})
        freq = _safe_float(ins.get("frequency"))
        if freq >= 3.0:
            fatiguing.append((ad["name"], days, freq))

    # ordena por freq desc — pega os piores
    fatiguing.sort(key=lambda x: x[2], reverse=True)
    for name, days, freq in fatiguing[:5]:
        findings.append({
            "frente": "Criativo",
            "severity": "alta",
            "titulo": f"Ad fatigue em `{name}`",
            "descricao": (
                f"Anúncio rodando há {days} dias com frequência {freq:.1f}x. Acima de 3x o "
                "público começa a saturar — CPM sobe, CTR cai e o criativo vira ruído. Esse "
                "é o padrão clássico de fadiga criativa."
            ),
            "recomendacao": (
                f"Pause `{name}` agora e suba 2-3 variações novas (ângulo diferente, hook diferente) "
                "no mesmo conjunto. Mantém o aprendizado e oxigena a entrega."
            ),
        })

    # ── 2. Conjuntos sem variação criativa ──
    no_variation: list[str] = []
    for adset in adsets:
        if adset.get("effective_status") != "ACTIVE":
            continue
        adset_ads = ads_by_adset.get(adset["id"], [])
        if len(adset_ads) == 1:
            no_variation.append(adset["name"])

    if no_variation:
        findings.append({
            "frente": "Criativo",
            "severity": "media",
            "titulo": f"{len(no_variation)} conjuntos com 1 só criativo ativo",
            "descricao": (
                "Sem variação criativa, qualquer queda de performance no único anúncio derruba "
                "o conjunto inteiro. Além disso, o algoritmo não tem nada pra otimizar — não "
                f"existe 'melhor anúncio' quando só tem um. Conjuntos: {', '.join(no_variation[:5])}"
                + (f" (+{len(no_variation) - 5})" if len(no_variation) > 5 else "")
                + "."
            ),
            "recomendacao": (
                "Suba pelo menos 3 variações por conjunto: hook diferente, formato diferente "
                "(vídeo curto + estática + carrossel) e ângulo diferente (dor x desejo x prova)."
            ),
        })

    # ── 3. CTR baixo + rodando há > 7 dias ──
    low_ctr: list[tuple[str, float, float]] = []
    for ad in active_ads:
        created = _parse_dt(ad.get("created_time"))
        if not created or (now - created).days < 7:
            continue
        ins = insights_by_ad.get(ad["id"], {})
        ctr = _safe_float(ins.get("ctr"))
        spend = _safe_float(ins.get("spend"))
        # filtra ruído: precisa ter spend mínimo pra CTR fazer sentido
        if spend < 50:
            continue
        if 0 < ctr < 0.5:
            low_ctr.append((ad["name"], ctr, spend))

    low_ctr.sort(key=lambda x: x[2], reverse=True)  # piores spend primeiro
    for name, ctr, spend in low_ctr[:5]:
        findings.append({
            "frente": "Criativo",
            "severity": "media",
            "titulo": f"CTR {ctr:.2f}% em `{name}` (R$ {spend:.0f} gastos)",
            "descricao": (
                f"Anúncio com CTR de {ctr:.2f}% — abaixo do piso saudável de 0.5% pra Meta Ads. "
                f"Já consumiu R$ {spend:.0f} sem engajar o público. Sinal claro de hook fraco "
                "ou criativo desalinhado da audiência."
            ),
            "recomendacao": (
                f"Pause `{name}`. Antes de subir versão nova, revise: o primeiro segundo do "
                "vídeo / a manchete da estática prende atenção? Está prometendo algo que o "
                "público quer? Se não, refaça do zero — não tente 'salvar' criativo ruim."
            ),
        })

    return findings
