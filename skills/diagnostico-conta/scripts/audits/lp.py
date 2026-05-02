"""
lp.py — Auditoria de Landing Page (opcional, depende de PAGESPEED_API_KEY).

Detecta:
- Score PageSpeed mobile/desktop < 50 → critical
- Score 50-75 → atenção
- Pixel não disparou recentemente (via Meta API)
- Sem PAGESPEED_API_KEY: pula audit, marca como "pulado"
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import requests

PAGESPEED_URL = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"


def _parse_dt(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def _read_lp_url(client_dir) -> str | None:
    """Tenta ler a URL da LP do contexto.md do cliente."""
    contexto = client_dir / "contexto.md"
    if not contexto.exists():
        return None
    try:
        text = contexto.read_text(encoding="utf-8")
    except Exception:
        return None
    import re
    # procura primeira URL http(s) no contexto
    m = re.search(r"https?://[^\s\)\]\>]+", text)
    if m:
        return m.group(0).rstrip(".,;)")
    return None


def _pagespeed(url: str, *, strategy: str, api_key: str) -> dict[str, Any] | None:
    params = {
        "url": url,
        "strategy": strategy,  # mobile | desktop
        "key": api_key,
        "category": "performance",
    }
    try:
        r = requests.get(PAGESPEED_URL, params=params, timeout=60)
    except requests.RequestException:
        return None
    if not r.ok:
        return None
    try:
        return r.json()
    except ValueError:
        return None


def _extract_score(payload: dict[str, Any]) -> int | None:
    try:
        score = payload["lighthouseResult"]["categories"]["performance"]["score"]
        return int(round(score * 100))
    except (KeyError, TypeError):
        return None


def run(
    *,
    client_dir,
    pagespeed_api_key: str | None,
    pixels: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    now = datetime.now(timezone.utc)

    # ── 1. Pixel não disparando ──
    if pixels:
        for px in pixels:
            last = _parse_dt(px.get("last_fired_time"))
            name = px.get("name") or px.get("id")
            if not last:
                findings.append({
                    "frente": "LP",
                    "severity": "alta",
                    "titulo": f"Pixel `{name}` sem registro de disparo",
                    "descricao": (
                        "A API não retornou `last_fired_time` para este pixel. Pode significar "
                        "pixel novo ou pixel parado de fato. Sem PageView caindo, não tem como "
                        "criar públicos custom de site, retargeting nem otimização por conversão."
                    ),
                    "recomendacao": (
                        "Abra a LP no Chrome com o Meta Pixel Helper instalado e confirme "
                        "PageView. Se não disparar, revise se o pixel está embutido no <head> "
                        "e se a LP tá usando o ID correto."
                    ),
                })
                continue
            hours = (now - last).total_seconds() / 3600
            if hours > 24:
                findings.append({
                    "frente": "LP",
                    "severity": "alta",
                    "titulo": f"Pixel `{name}` sem disparo há {int(hours)}h",
                    "descricao": (
                        f"Último PageView registrado pela Meta foi há ~{int(hours)} horas. "
                        "Se a LP tá com tráfego pago rodando, isso é furo na instrumentação — "
                        "você está cego pra otimização de conversão e retargeting."
                    ),
                    "recomendacao": (
                        "Confirme com Pixel Helper que PageView dispara em todas as páginas "
                        "do funil (LP, obrigado, checkout). Verifique se algum bloqueador / "
                        "consent banner está suprimindo o disparo."
                    ),
                })

    # ── 2. PageSpeed (opcional) ──
    if not pagespeed_api_key:
        # marca audit como pulado, sem virar finding
        return findings

    lp_url = _read_lp_url(client_dir)
    if not lp_url:
        findings.append({
            "frente": "LP",
            "severity": "baixa",
            "titulo": "URL da LP não encontrada no contexto.md",
            "descricao": (
                f"Esperava encontrar uma URL `http(s)://...` em `{client_dir.name}/contexto.md` "
                "pra rodar PageSpeed Insights. Sem isso, audit de performance da LP é pulado."
            ),
            "recomendacao": (
                "Adicione a URL da LP atual no `contexto.md` do cliente. Idealmente com label "
                "tipo `LP atual: https://...` pra outras skills também usarem."
            ),
        })
        return findings

    for strategy in ("mobile", "desktop"):
        try:
            payload = _pagespeed(lp_url, strategy=strategy, api_key=pagespeed_api_key)
        except Exception:
            payload = None
        if not payload:
            findings.append({
                "frente": "LP",
                "severity": "baixa",
                "titulo": f"Erro ao consultar PageSpeed ({strategy}) para `{lp_url}`",
                "descricao": (
                    "PageSpeed Insights API não respondeu ou retornou erro. Pode ser rate "
                    "limit, URL inválida ou bloqueio do robô. Os outros audits seguiram normalmente."
                ),
                "recomendacao": (
                    "Tente abrir manualmente em https://pagespeed.web.dev/ com a URL e veja "
                    "se há mensagem de erro específica."
                ),
            })
            continue
        score = _extract_score(payload)
        if score is None:
            continue
        if score < 50:
            findings.append({
                "frente": "LP",
                "severity": "alta",
                "titulo": f"PageSpeed {strategy} = {score}/100 — crítico",
                "descricao": (
                    f"Performance crítica em {strategy}: score {score}. LP lenta machuca tudo: "
                    "bounce sobe, qualidade do tráfego cai, CPA explode. Em mobile especialmente, "
                    "cada segundo a mais derruba conversão dramaticamente."
                ),
                "recomendacao": (
                    f"Abra https://pagespeed.web.dev/?url={quote(lp_url)} e ataque os 3 itens "
                    "vermelhos do topo: provavelmente imagens não otimizadas, JS bloqueante e/ou "
                    "fontes carregando síncronas."
                ),
            })
        elif score < 75:
            findings.append({
                "frente": "LP",
                "severity": "media",
                "titulo": f"PageSpeed {strategy} = {score}/100",
                "descricao": (
                    f"Score {score}/100 em {strategy} — funcional mas com gordura pra cortar. "
                    "Comparado a LPs otimizadas (>85), essa diferença pode custar 10-20% em "
                    "conversão dependendo do device do tráfego."
                ),
                "recomendacao": (
                    f"Veja relatório completo em https://pagespeed.web.dev/?url={quote(lp_url)}. "
                    "Foque em LCP < 2.5s e CLS < 0.1."
                ),
            })

    return findings
