#!/usr/bin/env python3
"""
vigia-24h — orquestrador CLI

Uso:
    python main.py --client acme --once             # 1 ciclo, sai (demo)
    python main.py --client acme                    # loop infinito (default 15min)
    python main.py --client acme --interval 5       # loop a cada 5min
    python main.py --client acme --once --no-send   # roda, mas não manda WhatsApp
    python main.py --client acme --once --to 5511999998888

Estado em <vault>/clientes/<cliente>/vigia/state.json
Log    em <vault>/clientes/<cliente>/vigia/log.md
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import alert  # noqa: E402
import baselines as baselines_mod  # noqa: E402
import eyes as eyes_mod  # noqa: E402
import state as state_mod  # noqa: E402
from evo_go import EvoGo, EvoGoError  # noqa: E402
from meta_api import MetaAPI, MetaAPIError  # noqa: E402

# ── env validation (mesmo padrão da espionar-full) ──────────
REQUIRED_ENV = {
    "META_ACCESS_TOKEN": "Token Meta com ads_read e ads_management",
    "META_AD_ACCOUNT_ID": "act_XXXX",
    "OBSIDIAN_VAULT_PATH": "Caminho absoluto do vault",
    "EVO_API_URL": "URL Evo Go (https://...sem / no final)",
    "EVO_API_KEY": "apikey UUID",
}


def check_env() -> dict[str, str]:
    """Valida variáveis de ambiente. Em caso de falta, imprime e exit 2."""
    missing: list[tuple[str, str]] = []
    values: dict[str, str] = {}
    for key, descr in REQUIRED_ENV.items():
        v = os.getenv(key, "").strip()
        if not v or v.startswith("act_") and v == "act_":
            missing.append((key, descr))
        else:
            values[key] = v

    if missing:
        print("✗ variáveis faltando no .env:")
        for k, d in missing:
            print(f"  - {k}  ({d})")
        print("")
        print(f"  edita: {SCRIPT_DIR.parent / '.env'}")
        print(f"  template: {SCRIPT_DIR.parent / '.env.example'}")
        sys.exit(2)

    return values


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="vigia-24h",
        description="Monitor 24/7 de Meta Ads — 4 olhos: CPA, saldo, status, pacing.",
    )
    p.add_argument("--client", required=True, help="Slug do cliente (ex: acme)")
    p.add_argument(
        "--once",
        action="store_true",
        help="Roda 1 ciclo e sai (modo demo). Default: loop infinito.",
    )
    p.add_argument(
        "--interval",
        type=int,
        default=int(os.getenv("VIGIA_INTERVAL_MIN", "15")),
        help="Intervalo em minutos entre ciclos (default 15 ou env VIGIA_INTERVAL_MIN)",
    )
    p.add_argument(
        "--to",
        type=str,
        default=os.getenv("VIGIA_ALERT_NUMBER", ""),
        help="Número WhatsApp (formato 5511999998888). Default: env VIGIA_ALERT_NUMBER.",
    )
    p.add_argument(
        "--no-send",
        action="store_true",
        help="Não envia alerta no WhatsApp (só imprime no terminal).",
    )
    p.add_argument(
        "--cooldown",
        type=int,
        default=60,
        help="Cooldown em minutos por olho (default 60).",
    )
    return p.parse_args()


# ── 1 ciclo ─────────────────────────────────────────────────
def run_cycle(
    cliente: str,
    vault: Path,
    meta: MetaAPI,
    evo: EvoGo | None,
    number: str,
    cooldown_min: int,
    send: bool,
) -> dict:
    """Roda 1 ciclo: pega métricas, calcula baselines, roda olhos, alerta se preciso."""
    cycle_started = datetime.now().isoformat(timespec="seconds")
    print(f"→ ciclo {cycle_started}")

    # ── 1. Meta API ──
    try:
        account_info = meta.account_info()
        daily_14d = meta.insights_daily("last_14d")
        today = meta.insights("today")
        adsets = meta.adsets()
        ads = meta.ads()
    except MetaAPIError as exc:
        print(f"✗ Meta API falhou: {exc}")
        state_mod.append_log(
            vault, cliente,
            f"- {cycle_started} — ✗ Meta API falhou: {exc}",
        )
        return {"ok": False, "error": str(exc)}

    # ── 2. baselines ──
    bl = baselines_mod.compute_baselines(daily_14d, today)
    print(
        f"  baselines: CPA 14d=R${bl['cpa_14d']:.2f} · spend_avg=R${bl['spend_avg_14d']:.2f} · "
        f"hoje=R${bl['spend_today']:.2f} · CPA hoje=R${bl['cpa_today']:.2f}"
    )

    # ── 3. olhos ──
    results = eyes_mod.run_all_eyes(account_info, adsets, ads, bl)
    alert.print_eye_summary(results)

    # ── 4. alertas ──
    state = state_mod.load_state(vault, cliente)
    fired_now: list[dict] = []
    suppressed: list[str] = []

    for r in results:
        if not r.get("fired"):
            continue
        eye = r["eye"]
        if state_mod.in_cooldown(state, eye, cooldown_min):
            suppressed.append(eye)
            continue
        fired_now.append(r)
        # marca cooldown imediatamente
        state_mod.mark_fired(state, eye, payload={
            "current": r.get("current"),
            "baseline": r.get("baseline"),
        })

    if suppressed:
        print(f"  ⏸  suprimidos por cooldown ({cooldown_min}min): {', '.join(suppressed)}")

    sent_ok = False
    if fired_now:
        msg = alert.format_alert(cliente, fired_now)
        print("")
        print("─── alerta WhatsApp ─────────────────────────────────")
        print(msg)
        print("─────────────────────────────────────────────────────")
        print("")
        if send and evo and number:
            try:
                alert.send_alert(msg, evo, number)
                sent_ok = True
                print(f"✓ alerta enviado pra {number}")
            except EvoGoError as exc:
                print(f"✗ falha ao enviar WhatsApp: {exc}")
        elif not send:
            print("  (--no-send: não enviado)")
        elif not number:
            print("  (sem --to e sem VIGIA_ALERT_NUMBER no env: não enviado)")

    state_mod.save_state(vault, cliente, state)

    # ── 5. log ──
    eyes_summary = " · ".join(
        f"{r.get('level', '?')}{r.get('eye')}" for r in results
    )
    fired_summary = ",".join(r["eye"] for r in fired_now) or "—"
    state_mod.append_log(
        vault, cliente,
        f"- {cycle_started} · {eyes_summary} · disparou: {fired_summary} · "
        f"enviado: {'sim' if sent_ok else 'não'}"
    )

    return {
        "ok": True,
        "fired": [r["eye"] for r in fired_now],
        "suppressed": suppressed,
        "sent": sent_ok,
        "results": results,
        "baselines": {k: v for k, v in bl.items() if k not in ("raw_daily", "raw_today")},
    }


# ── main ────────────────────────────────────────────────────
def main() -> int:
    load_dotenv(SCRIPT_DIR.parent / ".env")
    load_dotenv()

    args = parse_args()
    env = check_env()

    vault = Path(env["OBSIDIAN_VAULT_PATH"]).expanduser().resolve()
    if not vault.exists():
        print(f"✗ OBSIDIAN_VAULT_PATH não existe: {vault}")
        return 2

    cliente_dir = vault / "clientes" / args.client
    if not cliente_dir.exists():
        print(f"⚠ cliente '{args.client}' ainda não tem pasta em {cliente_dir}")
        print("  vou criar automaticamente.")
        cliente_dir.mkdir(parents=True, exist_ok=True)

    meta = MetaAPI(
        access_token=env["META_ACCESS_TOKEN"],
        ad_account_id=env["META_AD_ACCOUNT_ID"],
    )

    evo: EvoGo | None = None
    if not args.no_send:
        try:
            evo = EvoGo(
                api_url=env["EVO_API_URL"],
                api_key=env["EVO_API_KEY"],
                instance=os.getenv("EVO_INSTANCE_NAME"),
            )
        except EvoGoError as exc:
            print(f"⚠ Evo Go indisponível: {exc} — seguindo sem envio.")
            evo = None

    print(f"→ cliente: {args.client}")
    print(f"→ vault:   {vault}")
    print(f"→ conta:   {env['META_AD_ACCOUNT_ID']}")
    print(f"→ modo:    {'once' if args.once else f'loop ({args.interval}min)'}")
    print(f"→ envio:   {'desligado' if args.no_send else (args.to or 'env VIGIA_ALERT_NUMBER')}")
    print("")

    if args.once:
        result = run_cycle(
            cliente=args.client,
            vault=vault,
            meta=meta,
            evo=evo,
            number=args.to,
            cooldown_min=args.cooldown,
            send=not args.no_send,
        )
        if not result.get("ok"):
            return 1
        if result["fired"]:
            print(f"✓ ciclo único — disparou: {', '.join(result['fired'])}")
        else:
            print("✓ ciclo único — tudo dentro do esperado.")
        return 0

    # ── loop ──
    print(f"→ loop iniciado. Ctrl+C pra parar.")
    print("")
    try:
        while True:
            run_cycle(
                cliente=args.client,
                vault=vault,
                meta=meta,
                evo=evo,
                number=args.to,
                cooldown_min=args.cooldown,
                send=not args.no_send,
            )
            print(f"→ próximo ciclo em {args.interval}min …")
            print("")
            time.sleep(args.interval * 60)
    except KeyboardInterrupt:
        print("")
        print("→ vigia parado pelo usuário (Ctrl+C). Estado salvo.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
