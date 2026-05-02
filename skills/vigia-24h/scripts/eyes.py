"""
eyes.py — os 4 olhos do vigia.

Cada olho retorna um dict { fired: bool, level: 🔴|🟡|🟢, ... } ou None se não tiver dado.

| Olho   | Trigger                                                             |
|--------|---------------------------------------------------------------------|
| CPA    | CPA hoje > 1.5× CPA médio 14d                                       |
| Saldo  | Saldo da conta < R$100  (ou < 1× spend_avg_14d se mais conservador) |
| Status | Conta DISAPPROVED / PENDING_REVIEW / PAUSED há > 6h                 |
| Pacing | Spend hoje > 1.3× daily_budget total dos adsets ativos              |
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

# ── thresholds default ─────────────────────────────────────
CPA_TRIGGER_FACTOR = 1.5      # 50% acima da baseline
SALDO_MIN_BRL = 100.0
STATUS_MAX_HOURS = 6.0
PACING_TRIGGER_FACTOR = 1.30  # 130% do budget diário

PROBLEMATIC_STATUSES = {
    "DISAPPROVED",
    "PENDING_REVIEW",
    "AD_PAUSED",
    "PAUSED_FROM_REVIEW",
    "ADSET_PAUSED",
    "CAMPAIGN_PAUSED",
    "PENDING_BILLING_INFO",
    "DISABLED",
    "WITH_ISSUES",
}

# Account-level statuses problemáticos (`account_status` numérico):
# 1 = ACTIVE; 2 = DISABLED; 3 = UNSETTLED; 7 = PENDING_RISK_REVIEW;
# 8 = PENDING_SETTLEMENT; 9 = IN_GRACE_PERIOD; 100 = PENDING_CLOSURE; etc.
ACCOUNT_STATUS_OK = {1, 9}


def _balance_brl(account_info: dict) -> float | None:
    """
    Meta retorna `balance` em centavos da moeda da conta.
    Pra saldo pré-pago, vem em `funding_source_details.amount` em alguns casos.
    """
    raw = account_info.get("balance")
    if raw is None:
        # tenta funding_source_details (varia por região)
        fsd = account_info.get("funding_source_details") or {}
        raw = fsd.get("amount") or fsd.get("balance")
    if raw is None:
        return None
    try:
        # `balance` é string em centavos (legado) — divide por 100
        return float(raw) / 100.0
    except (TypeError, ValueError):
        return None


# ── eye 1: CPA ─────────────────────────────────────────────
def eye_cpa(baselines: dict[str, Any]) -> dict[str, Any]:
    cpa_today = baselines.get("cpa_today", 0.0)
    cpa_14d = baselines.get("cpa_14d", 0.0)
    purchases_today = baselines.get("purchases_today", 0)

    if cpa_14d <= 0 or purchases_today < 3:
        # baseline insuficiente OU dia ainda muito cedo (volume baixo)
        return {
            "eye": "cpa",
            "fired": False,
            "level": "🟢",
            "reason": "baseline insuficiente" if cpa_14d <= 0 else "volume do dia ainda baixo",
            "current": cpa_today,
            "baseline": cpa_14d,
        }

    ratio = cpa_today / cpa_14d
    pct = (ratio - 1.0) * 100.0
    fired = ratio >= CPA_TRIGGER_FACTOR

    return {
        "eye": "cpa",
        "fired": fired,
        "level": "🔴" if fired else ("🟡" if ratio >= 1.2 else "🟢"),
        "current": round(cpa_today, 2),
        "baseline": round(cpa_14d, 2),
        "delta_pct": round(pct, 1),
        "purchases_today": purchases_today,
        "trigger_factor": CPA_TRIGGER_FACTOR,
    }


# ── eye 2: Saldo ───────────────────────────────────────────
def eye_saldo(account_info: dict, baselines: dict[str, Any]) -> dict[str, Any]:
    saldo = _balance_brl(account_info)
    spend_avg = baselines.get("spend_avg_14d", 0.0)

    if saldo is None:
        return {
            "eye": "saldo",
            "fired": False,
            "level": "🟢",
            "reason": "saldo indisponível (conta pós-paga ou API ainda não atualizou)",
            "current": None,
        }

    fired = saldo < SALDO_MIN_BRL
    days_left = (saldo / spend_avg) if spend_avg > 0 else None

    return {
        "eye": "saldo",
        "fired": fired,
        "level": "🔴" if fired else ("🟡" if (days_left is not None and days_left < 2) else "🟢"),
        "current": round(saldo, 2),
        "min": SALDO_MIN_BRL,
        "spend_avg_14d": spend_avg,
        "days_left": round(days_left, 1) if days_left is not None else None,
    }


# ── eye 3: Status ──────────────────────────────────────────
def _hours_since(iso_ts: str | None) -> float | None:
    if not iso_ts:
        return None
    try:
        # Meta retorna ISO com timezone (+0000)
        s = iso_ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - dt
        return delta.total_seconds() / 3600.0
    except Exception:
        return None


def eye_status(account_info: dict, ads: list[dict]) -> dict[str, Any]:
    issues: list[dict] = []

    # ── conta ──
    acc_status = account_info.get("account_status")
    try:
        acc_status_int = int(acc_status) if acc_status is not None else None
    except (TypeError, ValueError):
        acc_status_int = None

    if acc_status_int is not None and acc_status_int not in ACCOUNT_STATUS_OK:
        issues.append({
            "kind": "account",
            "name": account_info.get("name", "?"),
            "status_code": acc_status_int,
            "disable_reason": account_info.get("disable_reason"),
        })

    # ── ads em status ruim há > 6h ──
    flagged_ads: list[dict] = []
    for ad in ads or []:
        eff = ad.get("effective_status")
        if eff in PROBLEMATIC_STATUSES:
            hrs = _hours_since(ad.get("updated_time"))
            if hrs is None or hrs >= STATUS_MAX_HOURS:
                flagged_ads.append({
                    "id": ad.get("id"),
                    "name": ad.get("name"),
                    "effective_status": eff,
                    "hours_since": round(hrs, 1) if hrs is not None else None,
                })

    if flagged_ads:
        issues.append({"kind": "ads", "count": len(flagged_ads), "items": flagged_ads[:5]})

    fired = bool(issues)
    return {
        "eye": "status",
        "fired": fired,
        "level": "🔴" if fired else "🟢",
        "issues": issues,
        "max_hours": STATUS_MAX_HOURS,
    }


# ── eye 4: Pacing ──────────────────────────────────────────
def eye_pacing(adsets: list[dict], baselines: dict[str, Any]) -> dict[str, Any]:
    spend_today = baselines.get("spend_today", 0.0)

    # soma daily_budget (em centavos) dos adsets ACTIVE
    total_daily_budget = 0.0
    active_count = 0
    for a in adsets or []:
        eff = a.get("effective_status") or a.get("status")
        if eff != "ACTIVE":
            continue
        active_count += 1
        db = a.get("daily_budget")
        if db is None:
            continue
        try:
            total_daily_budget += float(db) / 100.0
        except (TypeError, ValueError):
            continue

    if total_daily_budget <= 0:
        return {
            "eye": "pacing",
            "fired": False,
            "level": "🟢",
            "reason": "sem daily_budget configurado (budget de campanha ou lifetime)",
            "spend_today": spend_today,
            "active_adsets": active_count,
        }

    # hora atual do dia (0-24) — pra normalizar pacing esperado
    now = datetime.now()
    hour_fraction = (now.hour + now.minute / 60.0) / 24.0  # 0.0 .. 1.0
    expected_spend = total_daily_budget * hour_fraction

    ratio_vs_full_day = spend_today / total_daily_budget if total_daily_budget else 0
    fired = ratio_vs_full_day >= PACING_TRIGGER_FACTOR

    # alerta amarelo se já gastou > 80% do budget e ainda não chegou em 16h
    yellow = (not fired) and ratio_vs_full_day >= 0.8 and hour_fraction < 0.66

    return {
        "eye": "pacing",
        "fired": fired,
        "level": "🔴" if fired else ("🟡" if yellow else "🟢"),
        "spend_today": round(spend_today, 2),
        "daily_budget_total": round(total_daily_budget, 2),
        "ratio": round(ratio_vs_full_day, 3),
        "expected_at_now": round(expected_spend, 2),
        "hour_fraction": round(hour_fraction, 2),
        "active_adsets": active_count,
    }


# ── orquestrador ──────────────────────────────────────────
def run_all_eyes(account_info: dict, adsets: list[dict], ads: list[dict], baselines: dict) -> list[dict]:
    """Roda os 4 olhos e retorna lista ordenada (cpa, saldo, status, pacing)."""
    return [
        eye_cpa(baselines),
        eye_saldo(account_info, baselines),
        eye_status(account_info, ads),
        eye_pacing(adsets, baselines),
    ]
