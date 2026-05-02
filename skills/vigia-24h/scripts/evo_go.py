"""
evo_go.py — wrapper minimalista pra Evolution Go (WhatsApp).

POST {EVO_API_URL}/send/text/
Headers:  apikey: {EVO_API_KEY}
Body:     { "number": "5511999998888", "text": "...", "delay": 1000 }
"""
from __future__ import annotations

import httpx


class EvoGoError(RuntimeError):
    pass


class EvoGo:
    def __init__(self, api_url: str, api_key: str, instance: str | None = None, timeout: float = 20.0):
        if not api_url:
            raise EvoGoError("EVO_API_URL vazio")
        if not api_key:
            raise EvoGoError("EVO_API_KEY vazio")

        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.instance = instance
        self.client = httpx.Client(timeout=timeout)

    def send_text(self, number: str, text: str, delay_ms: int = 1000) -> dict:
        """
        number: formato internacional sem `+` ou espaços. Ex: 5511999998888
        text:   conteúdo da mensagem (suporta markdown do WhatsApp: *bold*, _italic_)
        """
        if not number:
            raise EvoGoError("number vazio")
        # higieniza number — só dígitos
        clean_number = "".join(c for c in str(number) if c.isdigit())
        if not clean_number:
            raise EvoGoError(f"number sem dígitos: {number!r}")

        # endpoint: /message/sendText/<instance> (Evolution v2) OU /send/text/ (Evo Go simplificada)
        # Tentativa principal: /send/text/  (Evo Go)
        endpoint = f"{self.api_url}/send/text/"
        if self.instance:
            # Evolution API v2: /message/sendText/<instance>
            endpoint_v2 = f"{self.api_url}/message/sendText/{self.instance}"
        else:
            endpoint_v2 = None

        payload = {
            "number": clean_number,
            "text": text,
            "delay": delay_ms,
        }
        headers = {
            "apikey": self.api_key,
            "Content-Type": "application/json",
        }

        last_err: str = ""
        for ep in [endpoint, endpoint_v2]:
            if not ep:
                continue
            try:
                resp = self.client.post(ep, json=payload, headers=headers)
                if resp.status_code < 400:
                    try:
                        return resp.json()
                    except Exception:
                        return {"ok": True, "raw": resp.text}
                last_err = f"HTTP {resp.status_code} em {ep}: {resp.text[:200]}"
            except httpx.HTTPError as exc:
                last_err = f"erro de transporte em {ep}: {exc}"

        raise EvoGoError(f"falha ao enviar WhatsApp — {last_err}")
