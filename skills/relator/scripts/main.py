#!/usr/bin/env python3
"""
relator — orquestrador CLI

Uso:
    python main.py --client acme --to joao
    python main.py --client acme --to 5511999998888 --days 14
    python main.py --client acme --to joao --preview
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import meta_api  # noqa: E402
import narrative  # noqa: E402
import vault  # noqa: E402
import evo_go  # noqa: E402


REQUIRED_ENV = {
    "META_ACCESS_TOKEN": "Token Meta com ads_read (developers.facebook.com)",
    "META_AD_ACCOUNT_ID": "Conta de anúncios (act_XXXX)",
    "OBSIDIAN_VAULT_PATH": "Caminho absoluto do vault (sem / no final)",
    "EVO_API_URL": "URL da Evo Go com https://, sem / no final",
    "EVO_API_KEY": "apikey da instância Evo Go (UUID)",
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="relator",
        description="Gera relatório narrativo dos últimos N dias e manda no WhatsApp via Evo Go.",
    )
    p.add_argument("--client", required=True, help="Nome do cliente (pasta em clientes/)")
    p.add_argument("--to", required=True, help="Destinatário: nome (resolve em contatos.md) ou número puro")
    p.add_argument("--days", type=int, default=7, help="Janela em dias (default: 7)")
    p.add_argument("--preview", action="store_true", help="Imprime no terminal sem mandar nem salvar histórico")
    return p.parse_args()


def check_env(env_path: Path) -> bool:
    missing = []
    for key, desc in REQUIRED_ENV.items():
        v = os.getenv(key, "").strip()
        if not v or v.startswith(("act_$", "/Users/voce")):
            # `act_$` é um placeholder que nunca foi preenchido; idem `/Users/voce`
            missing.append((key, desc))
        # checa templates óbvios não preenchidos
        if key == "META_AD_ACCOUNT_ID" and v == "act_":
            missing.append((key, desc))

    # remove duplicatas mantendo ordem
    seen = set()
    missing = [(k, d) for k, d in missing if not (k in seen or seen.add(k))]

    if not missing:
        return True

    print("\n✗ Variáveis ausentes no .env:")
    for k, d in missing:
        print(f"  - {k}  ({d})")
    print(f"\n→ edita: {env_path}")
    print("→ depois roda o comando de novo.\n")
    return False


def main() -> int:
    # carrega .env (uma pasta acima de scripts/)
    env_path = (SCRIPT_DIR.parent / ".env").resolve()
    load_dotenv(env_path)
    load_dotenv()  # cwd, sem sobrescrever

    args = parse_args()

    if not check_env(env_path):
        return 2

    vault_path = Path(os.environ["OBSIDIAN_VAULT_PATH"]).expanduser().resolve()
    if not vault_path.is_dir():
        print(f"✗ OBSIDIAN_VAULT_PATH não existe: {vault_path}")
        return 2

    # ── 1. Cliente ────────────────────────────────────────────
    try:
        client_path = vault.client_dir(vault_path, args.client)
    except vault.VaultError as e:
        print(f"✗ {e}")
        return 1

    print(f"→ cliente: {client_path}")
    print(f"→ janela: {args.days}d")

    # ── 2. Contexto + histórico ──────────────────────────────
    contexto = vault.read_contexto(client_path)
    historico = vault.read_historico(client_path, days=args.days)

    # ── 3. Destinatário ──────────────────────────────────────
    try:
        recipient_label, recipient_number = vault.resolve_recipient(
            target=args.to,
            client_path=client_path,
            contexto_fm=contexto.get("frontmatter") or {},
        )
    except vault.VaultError as e:
        print(f"✗ {e}")
        return 1

    print(f"→ destinatário: {recipient_label} ({_mask(recipient_number)})")

    # ── 4. Métricas Meta ─────────────────────────────────────
    print(f"→ buscando métricas dos últimos {args.days}d na Meta...")
    try:
        metrics = meta_api.fetch_insights(
            access_token=os.environ["META_ACCESS_TOKEN"],
            ad_account_id=os.environ["META_AD_ACCOUNT_ID"],
            days=args.days,
        )
    except meta_api.MetaAPIError as e:
        print(f"✗ {e}")
        return 1

    if metrics.get("has_data"):
        print(
            f"  spend R$ {metrics['spend']:.2f} · "
            f"purchases {metrics['purchases']:.0f} · "
            f"cpa R$ {metrics.get('cpa', 0):.2f} · "
            f"roas {metrics.get('roas', 0):.2f}"
        )
    else:
        print("  conta sem dados na janela (zero retorno).")

    # ── 5. Narrativa ─────────────────────────────────────────
    text = narrative.build_narrative(
        client_name=args.client,
        metrics=metrics,
        historico=historico,
        contexto=contexto,
        days=args.days,
    )

    # ── 6. Preview ou envio ──────────────────────────────────
    print("\n" + "─" * 60)
    print(text)
    print("─" * 60 + "\n")

    if args.preview:
        print("→ modo preview — nada foi enviado nem salvo.")
        return 0

    print(f"→ enviando para {recipient_label} ({_mask(recipient_number)}) via Evo Go...")
    try:
        evo_go.send_text(
            api_url=os.environ["EVO_API_URL"],
            api_key=os.environ["EVO_API_KEY"],
            number=recipient_number,
            text=text,
        )
    except evo_go.EvoGoError as e:
        print(f"✗ {e}")
        return 1
    print("✓ mensagem enviada.")

    # ── 7. Salva relatório no vault ─────────────────────────
    saved = vault.save_relatorio(client_path, recipient_label, text)
    print(f"✓ relatório salvo em: {saved}")

    # ── 8. Atualiza histórico ───────────────────────────────
    vault.append_historico(
        client_path,
        f"manda relatório de {args.days}d pro {recipient_label}",
    )
    print(f"✓ histórico atualizado: {client_path / 'historico.md'}")

    return 0


def _mask(number: str) -> str:
    if len(number) < 6:
        return number
    return number[:4] + "*" * (len(number) - 8) + number[-4:]


if __name__ == "__main__":
    raise SystemExit(main())
