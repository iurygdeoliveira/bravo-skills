"""
meta_api.py — Wrapper Graph API (somente leitura).

A skill nunca escreve nada na conta — só GET endpoints da Marketing API.
"""
from __future__ import annotations

import time
from typing import Any, Iterable
from urllib.parse import urlencode

import requests

GRAPH_VERSION = "v21.0"
GRAPH_BASE = f"https://graph.facebook.com/{GRAPH_VERSION}"

# Conservador pra não estourar rate limit em contas grandes.
DEFAULT_LIMIT = 100
MAX_PAGES = 20  # 2k itens por request paginada — mais que suficiente


class MetaAPIError(Exception):
    """Erro de qualquer chamada à Graph API."""


class MetaClient:
    def __init__(self, access_token: str, ad_account_id: str, *, timeout: int = 30):
        if not access_token:
            raise MetaAPIError("META_ACCESS_TOKEN vazio.")
        if not ad_account_id:
            raise MetaAPIError("META_AD_ACCOUNT_ID vazio.")
        if not ad_account_id.startswith("act_"):
            ad_account_id = f"act_{ad_account_id}"
        self.access_token = access_token
        self.ad_account_id = ad_account_id
        self.timeout = timeout
        self._session = requests.Session()

    # ── HTTP base ────────────────────────────────────────────────

    def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        params = dict(params or {})
        params["access_token"] = self.access_token
        url = f"{GRAPH_BASE}/{path.lstrip('/')}"
        try:
            r = self._session.get(url, params=params, timeout=self.timeout)
        except requests.RequestException as e:
            raise MetaAPIError(f"Falha de rede em GET {path}: {e}") from e
        if r.status_code == 429 or (500 <= r.status_code < 600):
            # 1 retry simples — Graph API costuma estabilizar rápido
            time.sleep(2)
            r = self._session.get(url, params=params, timeout=self.timeout)
        if not r.ok:
            try:
                err = r.json().get("error", {})
                msg = err.get("message") or r.text
            except Exception:
                msg = r.text
            raise MetaAPIError(f"GET {path} {r.status_code}: {msg}")
        try:
            return r.json()
        except ValueError as e:
            raise MetaAPIError(f"Resposta não-JSON em {path}: {e}") from e

    def _paginate(self, path: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        params = dict(params or {})
        params.setdefault("limit", DEFAULT_LIMIT)
        page = 0
        next_url: str | None = None
        while True:
            page += 1
            if page > MAX_PAGES:
                break
            if next_url:
                # next_url já contém todos params + token
                try:
                    r = self._session.get(next_url, timeout=self.timeout)
                except requests.RequestException as e:
                    raise MetaAPIError(f"Falha de rede ao paginar {path}: {e}") from e
                if not r.ok:
                    break
                payload = r.json()
            else:
                payload = self._get(path, params)
            data = payload.get("data") or []
            items.extend(data)
            next_url = (payload.get("paging") or {}).get("next")
            if not next_url:
                break
        return items

    # ── Endpoints ───────────────────────────────────────────────

    def account_info(self) -> dict[str, Any]:
        fields = "name,account_status,currency,timezone_name,age,amount_spent,balance"
        return self._get(self.ad_account_id, {"fields": fields})

    def campaigns(self, *, effective_status: Iterable[str] | None = None) -> list[dict[str, Any]]:
        fields = ",".join([
            "id", "name", "status", "effective_status",
            "objective", "buying_type", "bid_strategy",
            "daily_budget", "lifetime_budget",
            "created_time", "updated_time", "start_time", "stop_time",
            "special_ad_categories",
        ])
        params: dict[str, Any] = {"fields": fields, "limit": DEFAULT_LIMIT}
        if effective_status:
            params["effective_status"] = list(effective_status)
        return self._paginate(f"{self.ad_account_id}/campaigns", params)

    def adsets(self, *, effective_status: Iterable[str] | None = None) -> list[dict[str, Any]]:
        fields = ",".join([
            "id", "name", "status", "effective_status",
            "campaign_id", "optimization_goal", "billing_event",
            "bid_strategy", "bid_amount",
            "daily_budget", "lifetime_budget",
            "targeting", "created_time", "updated_time",
            "start_time", "end_time",
        ])
        params: dict[str, Any] = {"fields": fields, "limit": DEFAULT_LIMIT}
        if effective_status:
            params["effective_status"] = list(effective_status)
        return self._paginate(f"{self.ad_account_id}/adsets", params)

    def ads(self, *, effective_status: Iterable[str] | None = None) -> list[dict[str, Any]]:
        fields = ",".join([
            "id", "name", "status", "effective_status",
            "campaign_id", "adset_id",
            "creative{id,name,thumbnail_url,object_type,effective_object_story_id}",
            "created_time", "updated_time",
        ])
        params: dict[str, Any] = {"fields": fields, "limit": DEFAULT_LIMIT}
        if effective_status:
            params["effective_status"] = list(effective_status)
        return self._paginate(f"{self.ad_account_id}/ads", params)

    def insights(
        self,
        *,
        level: str,
        date_preset: str = "last_30d",
        fields: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Insights agregados. level ∈ {account, campaign, adset, ad}."""
        fields = fields or [
            "campaign_id", "adset_id", "ad_id",
            "impressions", "clicks", "ctr", "cpc", "cpm",
            "spend", "frequency", "reach",
            "actions", "cost_per_action_type",
        ]
        params = {
            "level": level,
            "date_preset": date_preset,
            "fields": ",".join(fields),
            "limit": DEFAULT_LIMIT,
        }
        try:
            return self._paginate(f"{self.ad_account_id}/insights", params)
        except MetaAPIError:
            # insights pode falhar em conta nova / sem permissão de read_insights
            return []

    def pixels(self) -> list[dict[str, Any]]:
        fields = "id,name,last_fired_time,code,is_unavailable"
        try:
            return self._paginate(f"{self.ad_account_id}/adspixels", {"fields": fields})
        except MetaAPIError:
            return []

    def custom_audiences(self) -> list[dict[str, Any]]:
        fields = ",".join([
            "id", "name", "subtype", "approximate_count_lower_bound",
            "lookalike_spec", "data_source", "time_created", "time_updated",
            "rule",
        ])
        try:
            return self._paginate(f"{self.ad_account_id}/customaudiences", {"fields": fields})
        except MetaAPIError:
            return []
