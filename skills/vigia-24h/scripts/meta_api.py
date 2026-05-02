"""
meta_api.py — wrapper Meta Marketing API com backoff exponencial em 429.

Endpoints usados:
- /act_<id>?fields=funding_source_details,balance,account_status
- /act_<id>/insights?date_preset=last_14d&fields=...
- /act_<id>/insights?date_preset=today&fields=...
- /act_<id>/adsets?fields=name,status,effective_status,daily_budget
- /act_<id>/ads?fields=name,effective_status,updated_time
"""
from __future__ import annotations

import time
from typing import Any

import httpx

GRAPH_BASE = "https://graph.facebook.com/v21.0"
RETRY_DELAYS = [30, 60, 120]  # segundos — backoff exponencial em 429


class MetaAPIError(RuntimeError):
    pass


class MetaAPI:
    def __init__(self, access_token: str, ad_account_id: str, timeout: float = 30.0):
        if not access_token:
            raise MetaAPIError("META_ACCESS_TOKEN vazio")
        if not ad_account_id:
            raise MetaAPIError("META_AD_ACCOUNT_ID vazio")

        self.token = access_token
        self.account_id = ad_account_id if ad_account_id.startswith("act_") else f"act_{ad_account_id}"
        self.client = httpx.Client(timeout=timeout)

    # ─── transport ────────────────────────────────────────────
    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        params = dict(params or {})
        params["access_token"] = self.token

        url = f"{GRAPH_BASE}/{path.lstrip('/')}"
        last_exc: Exception | None = None

        for attempt, delay in enumerate([0, *RETRY_DELAYS]):
            if delay > 0:
                print(f"  ⏳ Meta API rate limit — aguardando {delay}s antes de retry…")
                time.sleep(delay)

            try:
                resp = self.client.get(url, params=params)
            except httpx.HTTPError as exc:
                last_exc = exc
                continue

            if resp.status_code == 429 or (resp.status_code >= 500 and resp.status_code < 600):
                last_exc = MetaAPIError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                continue

            if resp.status_code >= 400:
                raise MetaAPIError(f"HTTP {resp.status_code} em {path}: {resp.text[:400]}")

            try:
                return resp.json()
            except Exception as exc:
                raise MetaAPIError(f"resposta não-JSON de {path}: {exc}") from exc

        raise MetaAPIError(f"falha após retries em {path}: {last_exc}")

    # ─── conta ────────────────────────────────────────────────
    def account_info(self) -> dict:
        """Saldo, status, funding."""
        fields = ",".join([
            "name",
            "account_status",
            "balance",
            "spend_cap",
            "amount_spent",
            "currency",
            "funding_source_details",
            "disable_reason",
        ])
        return self._get(self.account_id, {"fields": fields})

    # ─── insights ─────────────────────────────────────────────
    def insights(self, date_preset: str = "today", level: str = "account") -> list[dict]:
        """
        Insights agregados.
        date_preset: today | yesterday | last_14d | last_7d
        level: account | campaign | adset | ad
        """
        fields = ",".join([
            "spend",
            "impressions",
            "clicks",
            "actions",
            "cost_per_action_type",
            "cpc",
            "cpm",
            "ctr",
            "date_start",
            "date_stop",
        ])
        params = {
            "fields": fields,
            "date_preset": date_preset,
            "level": level,
        }
        data = self._get(f"{self.account_id}/insights", params)
        return data.get("data", [])

    def insights_daily(self, date_preset: str = "last_14d") -> list[dict]:
        """Insights quebrados por dia (time_increment=1) — pra calcular baseline."""
        fields = ",".join([
            "spend",
            "impressions",
            "clicks",
            "actions",
            "cost_per_action_type",
            "date_start",
            "date_stop",
        ])
        params = {
            "fields": fields,
            "date_preset": date_preset,
            "level": "account",
            "time_increment": "1",
        }
        data = self._get(f"{self.account_id}/insights", params)
        return data.get("data", [])

    # ─── adsets ───────────────────────────────────────────────
    def adsets(self) -> list[dict]:
        fields = ",".join([
            "name",
            "status",
            "effective_status",
            "daily_budget",
            "lifetime_budget",
            "updated_time",
        ])
        params = {"fields": fields, "limit": 200}
        data = self._get(f"{self.account_id}/adsets", params)
        return data.get("data", [])

    # ─── ads ──────────────────────────────────────────────────
    def ads(self) -> list[dict]:
        fields = ",".join([
            "name",
            "status",
            "effective_status",
            "updated_time",
            "issues_info",
        ])
        params = {"fields": fields, "limit": 200}
        data = self._get(f"{self.account_id}/ads", params)
        return data.get("data", [])
