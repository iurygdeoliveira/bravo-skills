"""
state.py — persistência do estado do vigia por cliente.

Estado vive em <vault>/clientes/<cliente>/vigia/state.json:

{
  "cooldowns": {
    "cpa":    "2026-05-01T14:32:10",
    "saldo":  "2026-05-01T11:00:00",
    "status": null,
    "pacing": null
  },
  "last_alerts": {
    "cpa": { "value": 58.2, "baseline": 32.1, "ts": "..." },
    ...
  }
}

Cooldown padrão: 60 minutos por olho.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

DEFAULT_COOLDOWN_MIN = 60
EYES = ("cpa", "saldo", "status", "pacing")


def vigia_dir(vault: Path, cliente: str) -> Path:
    """<vault>/clientes/<cliente>/vigia/  — cria se não existir."""
    p = vault / "clientes" / cliente / "vigia"
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_path(vault: Path, cliente: str) -> Path:
    return vigia_dir(vault, cliente) / "state.json"


def log_path(vault: Path, cliente: str) -> Path:
    return vigia_dir(vault, cliente) / "log.md"


def load_state(vault: Path, cliente: str) -> dict[str, Any]:
    p = state_path(vault, cliente)
    if not p.exists():
        return {"cooldowns": {e: None for e in EYES}, "last_alerts": {}}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {"cooldowns": {e: None for e in EYES}, "last_alerts": {}}


def save_state(vault: Path, cliente: str, state: dict[str, Any]) -> None:
    p = state_path(vault, cliente)
    p.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def in_cooldown(state: dict, eye: str, cooldown_min: int = DEFAULT_COOLDOWN_MIN) -> bool:
    ts = state.get("cooldowns", {}).get(eye)
    if not ts:
        return False
    try:
        last = datetime.fromisoformat(ts)
    except Exception:
        return False
    return datetime.now() - last < timedelta(minutes=cooldown_min)


def mark_fired(state: dict, eye: str, payload: dict | None = None) -> None:
    now = datetime.now().isoformat(timespec="seconds")
    state.setdefault("cooldowns", {})[eye] = now
    if payload is not None:
        state.setdefault("last_alerts", {})[eye] = {**payload, "ts": now}


def append_log(vault: Path, cliente: str, line: str) -> None:
    """Append-only log em Markdown."""
    p = log_path(vault, cliente)
    if not p.exists():
        p.write_text(
            f"# Vigia 24h — log de eventos · {cliente}\n\n"
            "Append-only. Cada linha é um ciclo ou alerta.\n\n",
            encoding="utf-8",
        )
    with p.open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")
