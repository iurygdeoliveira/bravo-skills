"""
render.py — Gera markdown priorizado a partir da lista de findings.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

SEVERITY_ORDER = {"alta": 0, "media": 1, "média": 1, "baixa": 2}

SEVERITY_HEADERS = {
    "alta": "🔴 Crítico (alta prioridade)",
    "media": "🟡 Atenção (média prioridade)",
    "baixa": "🟢 Pontos de melhoria (baixa)",
}


def _normalize_severity(sev: str) -> str:
    sev = (sev or "").strip().lower()
    if sev in ("media", "média"):
        return "media"
    if sev == "alta":
        return "alta"
    return "baixa"


def prioritize(findings: list[dict[str, Any]], *, max_total: int = 15) -> list[dict[str, Any]]:
    """Ordena por severidade e limita pra top N."""
    normalized = []
    for f in findings:
        f2 = dict(f)
        f2["severity"] = _normalize_severity(f2.get("severity", "baixa"))
        normalized.append(f2)
    normalized.sort(key=lambda f: SEVERITY_ORDER.get(f["severity"], 99))
    return normalized[:max_total]


def summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"alta": 0, "media": 0, "baixa": 0}
    for f in findings:
        counts[_normalize_severity(f.get("severity", "baixa"))] += 1
    return counts


def render_markdown(
    *,
    client: str,
    findings: list[dict[str, Any]],
    skipped_audits: list[str],
    errored_audits: list[tuple[str, str]],
    account_info: dict[str, Any] | None,
    generated_at: datetime,
) -> str:
    findings = prioritize(findings)
    counts = summary(findings)
    total = len(findings)

    lines: list[str] = []
    date_iso = generated_at.strftime("%Y-%m-%d")
    lines.append(f"# Diagnóstico — {client}")
    lines.append(f"> {date_iso} · {total} findings ({counts['alta']} críticos, "
                 f"{counts['media']} médios, {counts['baixa']} menores)")
    lines.append("")

    if account_info:
        nome = account_info.get("name") or "?"
        moeda = account_info.get("currency") or ""
        tz = account_info.get("timezone_name") or ""
        lines.append(f"**Conta:** {nome} · {moeda} · {tz}")
        lines.append("")

    if skipped_audits:
        lines.append(f"_Audits pulados: {', '.join(skipped_audits)}_")
        lines.append("")

    if errored_audits:
        for name, err in errored_audits:
            lines.append(f"_⚠ Audit `{name}` deu erro: {err}_")
        lines.append("")

    if total == 0:
        lines.append("Nenhum problema crítico detectado nos audits que rodaram. ")
        lines.append("Isso não significa conta perfeita — significa que os checks automatizados ")
        lines.append("não pegaram nada. Revisão manual ainda agrega.")
        lines.append("")
        return "\n".join(lines)

    # Agrupa por severidade
    by_sev: dict[str, list[dict[str, Any]]] = {"alta": [], "media": [], "baixa": []}
    for f in findings:
        by_sev[_normalize_severity(f["severity"])].append(f)

    for sev in ("alta", "media", "baixa"):
        items = by_sev[sev]
        if not items:
            continue
        lines.append(f"## {SEVERITY_HEADERS[sev]}")
        lines.append("")
        for f in items:
            lines.append(f"### {f.get('titulo', '(sem título)')}")
            lines.append(f"**Frente:** {f.get('frente', '-')}  ")
            descricao = (f.get("descricao") or "").strip()
            recomendacao = (f.get("recomendacao") or "").strip()
            lines.append(f"**Descrição:** {descricao}  ")
            lines.append(f"**Recomendação:** {recomendacao}")
            lines.append("")
            lines.append("---")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"
