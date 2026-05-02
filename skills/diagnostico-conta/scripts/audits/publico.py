"""
publico.py — Auditoria de público.

Detecta:
- Públicos com overlap calculado > 30% (heurístico, baseado em targeting)
- Lookalikes com fonte (seed) > 90 dias sem refresh
- Idades amplas demais (ex: 18-65) sem segmentação por interesse/comportamento
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


def _interest_set(adset: dict[str, Any]) -> set[str]:
    t = adset.get("targeting") or {}
    ids: set[str] = set()
    spec = t.get("flexible_spec") or [t.get("targeting_spec")] or []
    if isinstance(spec, list):
        for block in spec:
            if not block:
                continue
            for it in (block.get("interests") or []):
                key = str(it.get("id") or it.get("name") or "")
                if key:
                    ids.add(key)
            for it in (block.get("behaviors") or []):
                key = str(it.get("id") or it.get("name") or "")
                if key:
                    ids.add(f"b:{key}")
    # custom audiences inclusas
    for ca in (t.get("custom_audiences") or []):
        ids.add(f"ca:{ca.get('id')}")
    return ids


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def run(
    *,
    adsets: list[dict[str, Any]],
    custom_audiences: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    active_adsets = [a for a in adsets if a.get("effective_status") == "ACTIVE"]

    # ── 1. Overlap heurístico entre conjuntos (Jaccard sobre interesses+behaviors+CAs) ──
    overlap_pairs: list[tuple[str, str, float, int]] = []
    by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for a in active_adsets:
        by_campaign[a.get("campaign_id", "")].append(a)

    # só compara conjuntos da mesma campanha (overlap entre campanhas é caso à parte)
    for camp_id, group in by_campaign.items():
        sigs = [(a, _interest_set(a)) for a in group]
        for i in range(len(sigs)):
            for j in range(i + 1, len(sigs)):
                a1, s1 = sigs[i]
                a2, s2 = sigs[j]
                if not s1 or not s2:
                    continue
                j_score = _jaccard(s1, s2)
                if j_score > 0.30:
                    overlap_pairs.append((a1["name"], a2["name"], j_score, len(s1 & s2)))

    overlap_pairs.sort(key=lambda x: x[2], reverse=True)
    for n1, n2, score, shared in overlap_pairs[:5]:
        findings.append({
            "frente": "Público",
            "severity": "alta",
            "titulo": f"Overlap {score * 100:.0f}% entre `{n1}` e `{n2}`",
            "descricao": (
                f"Os dois conjuntos compartilham {shared} interesses/comportamentos — overlap "
                f"estimado em {score * 100:.0f}% (Jaccard). Significa que estão dando lance um "
                "contra o outro no mesmo público, pagando CPM mais caro pelo mesmo lead."
            ),
            "recomendacao": (
                f"Use o Audience Overlap Tool da Meta pra confirmar e consolide num só conjunto. "
                f"Mantenha o de melhor CPA. Se precisar testar variações, use exclusões mútuas "
                "(adiciona um como exclusion no targeting do outro)."
            ),
        })

    # ── 2. Lookalikes com seed > 90 dias ──
    stale_lookalikes: list[tuple[str, int]] = []
    for ca in custom_audiences:
        if ca.get("subtype") not in ("LOOKALIKE",):
            continue
        # Lookalike refletindo conversões: se time_updated > 90 dias atrás, considera velho
        updated = _parse_dt(ca.get("time_updated") or ca.get("time_created"))
        if not updated:
            continue
        days = (now - updated).days
        if days > 90:
            stale_lookalikes.append((ca.get("name", "?"), days))

    stale_lookalikes.sort(key=lambda x: x[1], reverse=True)
    for name, days in stale_lookalikes[:5]:
        findings.append({
            "frente": "Público",
            "severity": "media",
            "titulo": f"Lookalike `{name}` sem refresh há {days} dias",
            "descricao": (
                "Lookalikes degradam com o tempo — a seed muda (clientes velhos, perfil de "
                f"conversão evolui). {days} dias sem atualizar significa que a Meta tá expandindo "
                "a partir de uma base que não reflete mais o melhor cliente atual."
            ),
            "recomendacao": (
                f"Recrie a seed do lookalike com conversões dos últimos 60-90 dias e gere "
                "lookalike novo. Mantém o antigo só pra teste A/B se quiser comparar."
            ),
        })

    # ── 3. Idade ampla sem segmentação ──
    wide_age: list[str] = []
    for adset in active_adsets:
        t = adset.get("targeting") or {}
        age_min = int(t.get("age_min", 0) or 0)
        age_max = int(t.get("age_max", 0) or 0)
        # 18-65 / 18+ / faixa muito ampla
        wide = (age_max - age_min) >= 40 or (age_min <= 18 and age_max >= 60)
        interests = _interest_set(adset)
        # se idade ampla E sem afunilamento por interesse/CA → suspeito
        if wide and not interests:
            wide_age.append(f"{adset['name']} ({age_min}-{age_max})")

    if wide_age:
        findings.append({
            "frente": "Público",
            "severity": "baixa",
            "titulo": f"{len(wide_age)} conjuntos com idade muito ampla e sem segmentação",
            "descricao": (
                "Faixas de idade abertas (18-65) sem interesse/comportamento nem custom audience "
                "deixam o algoritmo decidir tudo. Isso pode funcionar em conta com muito histórico, "
                f"mas costuma diluir entrega quando o orçamento é baixo. Conjuntos: {', '.join(wide_age[:5])}"
                + (f" (+{len(wide_age) - 5})" if len(wide_age) > 5 else "")
                + "."
            ),
            "recomendacao": (
                "Estreite pra faixa do avatar real (ex: 25-45) ou adicione ao menos uma camada "
                "de interesse/comportamento. Se quiser testar 'open targeting', isole num conjunto "
                "específico pra comparar contra o segmentado."
            ),
        })

    return findings
