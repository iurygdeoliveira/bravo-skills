#!/usr/bin/env python3
"""
diagnostico-conta — orquestrador CLI

Uso:
    python main.py --client acme
    python main.py --client "joão da silva" --max-findings 20
"""
from __future__ import annotations

import argparse
import os
import re
import sys
import time
import unicodedata
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

from meta_api import MetaAPIError, MetaClient  # noqa: E402
from audits import estrutura as audit_estrutura  # noqa: E402
from audits import criativo as audit_criativo  # noqa: E402
from audits import publico as audit_publico  # noqa: E402
from audits import lp as audit_lp  # noqa: E402
import render  # noqa: E402

REQUIRED_ENV = {
    "META_ACCESS_TOKEN": "Token Meta com permissão `ads_read`",
    "META_AD_ACCOUNT_ID": "ID da conta de anúncios (formato `act_XXXX`)",
    "OBSIDIAN_VAULT_PATH": "Caminho absoluto do vault Obsidian",
}
OPTIONAL_ENV = {
    "PAGESPEED_API_KEY": "(opcional) Google PageSpeed Insights pra audit de LP",
}


# ─────────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="diagnostico-conta",
        description="Auditoria automatizada da conta de Meta Ads em 4 frentes.",
    )
    p.add_argument("--client", required=True, help="Slug ou nome da pasta do cliente em <vault>/clientes/")
    p.add_argument("--max-findings", type=int, default=15, help="Máximo de findings priorizados (default: 15)")
    p.add_argument(
        "--date-preset",
        default="last_30d",
        help="Janela de insights (last_7d, last_14d, last_30d, last_90d). Default: last_30d",
    )
    p.add_argument("--dry-run", action="store_true", help="Não escreve markdown, só imprime resumo")
    return p.parse_args()


def slugify(text: str) -> str:
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")[:60]


# ─────────────────────────────────────────────────────────────────
# ENV CHECK
# ─────────────────────────────────────────────────────────────────

def check_env() -> tuple[dict[str, str], dict[str, str | None]]:
    """Valida vars obrigatórias e devolve dict pra usar. Sai com 2 se faltar required."""
    required: dict[str, str] = {}
    optional: dict[str, str | None] = {}
    missing: list[str] = []

    for var, desc in REQUIRED_ENV.items():
        val = (os.getenv(var) or "").strip()
        if not val or val in ("act_", "/Users/voce/Documents/obsidian-bravo"):
            # placeholder do .env.example também conta como ausente
            missing.append(f"  - {var}: {desc}")
        else:
            required[var] = val

    if missing:
        print("✗ Variáveis de ambiente obrigatórias ausentes ou com placeholder:")
        for m in missing:
            print(m)
        print()
        print("Preencha em `.env` (mesma pasta da skill). Use `.env.example` como referência.")
        sys.exit(2)

    for var, desc in OPTIONAL_ENV.items():
        val = (os.getenv(var) or "").strip()
        if not val:
            print(f"⚠ {var} não definida — audit relacionado pode ser pulado. {desc}")
            optional[var] = None
        else:
            optional[var] = val

    return required, optional


# ─────────────────────────────────────────────────────────────────
# COLETA
# ─────────────────────────────────────────────────────────────────

def fetch_account_data(client: MetaClient, *, date_preset: str) -> dict:
    print("→ Carregando estrutura da conta...")
    account_info = client.account_info()
    print(f"  conta: {account_info.get('name', '?')} ({account_info.get('currency', '?')})")

    print("→ Carregando campanhas, conjuntos e anúncios...")
    campaigns = client.campaigns()
    adsets = client.adsets()
    ads = client.ads()
    print(f"  {len(campaigns)} campanhas · {len(adsets)} conjuntos · {len(ads)} anúncios")

    print(f"→ Carregando insights ({date_preset})...")
    insights_campaign = client.insights(level="campaign", date_preset=date_preset)
    insights_adset = client.insights(level="adset", date_preset=date_preset)
    insights_ad = client.insights(level="ad", date_preset=date_preset)

    insights_by_campaign = {i.get("campaign_id"): i for i in insights_campaign if i.get("campaign_id")}
    insights_by_adset = {i.get("adset_id"): i for i in insights_adset if i.get("adset_id")}
    insights_by_ad = {i.get("ad_id"): i for i in insights_ad if i.get("ad_id")}

    print("→ Carregando custom audiences e pixels...")
    custom_audiences = client.custom_audiences()
    pixels = client.pixels()
    print(f"  {len(custom_audiences)} custom audiences · {len(pixels)} pixels")

    return {
        "account_info": account_info,
        "campaigns": campaigns,
        "adsets": adsets,
        "ads": ads,
        "insights_by_campaign": insights_by_campaign,
        "insights_by_adset": insights_by_adset,
        "insights_by_ad": insights_by_ad,
        "custom_audiences": custom_audiences,
        "pixels": pixels,
    }


# ─────────────────────────────────────────────────────────────────
# RUN AUDITS
# ─────────────────────────────────────────────────────────────────

def run_audits(
    *,
    data: dict,
    client_dir: Path,
    pagespeed_api_key: str | None,
) -> tuple[list[dict], list[str], list[tuple[str, str]]]:
    findings: list[dict] = []
    skipped: list[str] = []
    errored: list[tuple[str, str]] = []

    audits = [
        (
            "estrutura",
            lambda: audit_estrutura.run(
                campaigns=data["campaigns"],
                adsets=data["adsets"],
                ads=data["ads"],
                insights_by_campaign=data["insights_by_campaign"],
                insights_by_adset=data["insights_by_adset"],
            ),
        ),
        (
            "criativo",
            lambda: audit_criativo.run(
                ads=data["ads"],
                adsets=data["adsets"],
                insights_by_ad=data["insights_by_ad"],
                insights_by_adset=data["insights_by_adset"],
            ),
        ),
        (
            "publico",
            lambda: audit_publico.run(
                adsets=data["adsets"],
                custom_audiences=data["custom_audiences"],
            ),
        ),
        (
            "lp",
            lambda: audit_lp.run(
                client_dir=client_dir,
                pagespeed_api_key=pagespeed_api_key,
                pixels=data["pixels"],
            ),
        ),
    ]

    for name, fn in audits:
        if name == "lp" and not pagespeed_api_key and not data.get("pixels"):
            # sem pagespeed E sem pixels → audit é totalmente pulado
            skipped.append(name)
            print(f"  ↷ {name}: pulado (sem PAGESPEED_API_KEY e sem pixels)")
            continue
        print(f"  • rodando audit `{name}`...")
        try:
            result = fn()
            findings.extend(result or [])
            print(f"    {len(result or [])} findings")
        except Exception as e:  # nunca derruba a skill inteira por causa de 1 audit
            errored.append((name, str(e)))
            print(f"    ✗ erro: {e}")

    return findings, skipped, errored


# ─────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────

def main() -> int:
    # Carrega .env da pasta da skill (um nível acima de scripts/)
    load_dotenv(SCRIPT_DIR.parent / ".env")
    load_dotenv()  # cwd, sem sobrescrever

    args = parse_args()
    required, optional = check_env()

    vault = Path(required["OBSIDIAN_VAULT_PATH"]).expanduser().resolve()
    if not vault.exists():
        print(f"✗ OBSIDIAN_VAULT_PATH não existe: {vault}")
        return 2

    client_slug = slugify(args.client)
    client_dir = vault / "clientes" / client_slug
    if not client_dir.exists():
        # tenta nome literal (pode ter espaços, acentos)
        literal = vault / "clientes" / args.client
        if literal.exists():
            client_dir = literal
        else:
            print(f"✗ Pasta do cliente não encontrada:")
            print(f"    tentei: {client_dir}")
            print(f"    e:      {literal}")
            print(f"  Crie `clientes/{client_slug}/` no vault e adicione `contexto.md` com a URL da LP.")
            return 2

    print(f"→ cliente: {args.client} → {client_dir}")

    t0 = time.time()
    try:
        meta = MetaClient(
            access_token=required["META_ACCESS_TOKEN"],
            ad_account_id=required["META_AD_ACCOUNT_ID"],
        )
        data = fetch_account_data(meta, date_preset=args.date_preset)
    except MetaAPIError as e:
        print(f"✗ Falha na Meta API: {e}")
        return 1

    print("→ Rodando audits...")
    findings, skipped, errored = run_audits(
        data=data,
        client_dir=client_dir,
        pagespeed_api_key=optional.get("PAGESPEED_API_KEY"),
    )

    print(f"→ Total bruto: {len(findings)} findings (vou priorizar top {args.max_findings})")

    now = datetime.now()
    md = render.render_markdown(
        client=args.client,
        findings=render.prioritize(findings, max_total=args.max_findings),
        skipped_audits=skipped,
        errored_audits=errored,
        account_info=data.get("account_info"),
        generated_at=now,
    )

    counts = render.summary(render.prioritize(findings, max_total=args.max_findings))
    elapsed = time.time() - t0

    if args.dry_run:
        print("--- markdown (dry-run) ---")
        print(md)
        print(f"✓ pronto em {elapsed:.1f}s · "
              f"{counts['alta']} críticos, {counts['media']} médios, {counts['baixa']} menores")
        return 0

    out_path = client_dir / f"diagnostico-{now.strftime('%Y-%m-%d')}.md"
    out_path.write_text(md, encoding="utf-8")

    print()
    print(f"✓ Diagnóstico salvo em: {out_path}")
    print(f"✓ Resumo: {counts['alta']} críticos, {counts['media']} médios, {counts['baixa']} menores "
          f"(em {elapsed:.1f}s)")
    print(f"✓ Abrir: open '{out_path}'")
    print(f"  ou:    cat '{out_path}'")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
