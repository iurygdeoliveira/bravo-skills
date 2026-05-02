"""
baselines.py — calcula médias de referência dos últimos 14 dias.

Saída padrão (dict):
{
  "cpa_14d":           32.10,   # custo médio por aquisição (purchase / lead) últimos 14d
  "spend_avg_14d":    287.50,   # gasto diário médio últimos 14d
  "spend_today":      412.00,   # gasto do dia corrente
  "cpa_today":         58.20,   # CPA do dia corrente
  "purchases_14d":    127,      # total de conversões últimos 14d
  "days_with_data":    13,
  "raw_daily":        [...]
}

Conversion event: tenta primeiro `purchase`, depois `lead`, depois `complete_registration`.
"""
from __future__ import annotations

from typing import Any

CONVERSION_PRIORITY = (
    "purchase",
    "offsite_conversion.fb_pixel_purchase",
    "lead",
    "offsite_conversion.fb_pixel_lead",
    "complete_registration",
    "offsite_conversion.fb_pixel_complete_registration",
)


def _pick_action_count(actions: list[dict] | None) -> tuple[int, str | None]:
    """Retorna (count, action_type_usado)."""
    if not actions:
        return 0, None
    by_type = {a.get("action_type"): a for a in actions}
    for t in CONVERSION_PRIORITY:
        if t in by_type:
            try:
                return int(float(by_type[t].get("value", 0))), t
            except (TypeError, ValueError):
                continue
    return 0, None


def _safe_float(v: Any) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def compute_baselines(daily_14d: list[dict], today: list[dict]) -> dict[str, Any]:
    """
    daily_14d: saída de meta.insights_daily('last_14d')  — 1 row por dia
    today:     saída de meta.insights('today')           — 1 row agregada
    """
    total_spend = 0.0
    total_purchases = 0
    days_with_data = 0
    chosen_type: str | None = None

    for row in daily_14d:
        spend = _safe_float(row.get("spend"))
        purchases, t = _pick_action_count(row.get("actions"))
        if spend > 0 or purchases > 0:
            days_with_data += 1
        total_spend += spend
        total_purchases += purchases
        if chosen_type is None and t is not None:
            chosen_type = t

    cpa_14d = (total_spend / total_purchases) if total_purchases > 0 else 0.0
    spend_avg_14d = (total_spend / days_with_data) if days_with_data > 0 else 0.0

    # hoje
    today_row = today[0] if today else {}
    spend_today = _safe_float(today_row.get("spend"))
    purchases_today, _ = _pick_action_count(today_row.get("actions"))
    cpa_today = (spend_today / purchases_today) if purchases_today > 0 else 0.0

    return {
        "cpa_14d": round(cpa_14d, 2),
        "spend_avg_14d": round(spend_avg_14d, 2),
        "spend_today": round(spend_today, 2),
        "cpa_today": round(cpa_today, 2),
        "purchases_14d": total_purchases,
        "purchases_today": purchases_today,
        "days_with_data": days_with_data,
        "conversion_event": chosen_type,
        "raw_daily": daily_14d,
        "raw_today": today_row,
    }
