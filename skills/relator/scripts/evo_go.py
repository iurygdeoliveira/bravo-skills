"""
evo_go — cliente da Evolution Go (NÃO confundir com a Evolution antiga).

Endpoint:
    POST {EVO_API_URL}/send/text/
    Headers:
        apikey: {EVO_API_KEY}
        Content-Type: application/json
    Body:
        { "number": "5511999998888", "text": "...", "delay": 1000 }
"""
from __future__ import annotations

from typing import Any

import httpx


class EvoGoError(RuntimeError):
    pass


def send_text(
    api_url: str,
    api_key: str,
    number: str,
    text: str,
    delay_ms: int = 1000,
    timeout: float = 30.0,
) -> dict[str, Any]:
    """
    Manda mensagem de texto no WhatsApp via Evo Go.

    Args:
        api_url: ex `https://api.suavps.com.br` (sem `/` no fim)
        api_key: UUID da instância
        number: número E.164 só dígitos (ex `5511999998888`)
        text: corpo da mensagem
        delay_ms: delay simulado de digitação (default 1s)

    Returns:
        Resposta JSON da API.

    Raises:
        EvoGoError em qualquer falha (rede, status != 2xx, JSON inválido).
    """
    url = api_url.rstrip("/") + "/send/text/"
    headers = {
        "apikey": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "number": number,
        "text": text,
        "delay": delay_ms,
    }

    try:
        resp = httpx.post(url, headers=headers, json=payload, timeout=timeout)
    except httpx.HTTPError as e:
        raise EvoGoError(f"falha de rede ao chamar Evo Go: {e}") from e

    if resp.status_code >= 300:
        raise EvoGoError(
            f"Evo Go {resp.status_code} em {url} — body: {resp.text[:500]}"
        )

    try:
        return resp.json()
    except ValueError:
        return {"raw": resp.text}
