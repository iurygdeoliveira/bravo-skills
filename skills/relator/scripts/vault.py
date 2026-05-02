"""
vault — leitura do Obsidian Vault do cliente.

Estrutura esperada:
    OBSIDIAN_VAULT_PATH/clientes/<nome>/
        contexto.md      (com frontmatter YAML opcional)
        historico.md
        contatos.md      (opcional)
        relatorios/
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


class VaultError(RuntimeError):
    pass


def client_dir(vault_path: Path, client_name: str) -> Path:
    p = vault_path / "clientes" / client_name
    if not p.is_dir():
        raise VaultError(f"cliente não encontrado: {p}")
    return p


def read_contexto(client_path: Path) -> dict[str, Any]:
    """
    Lê contexto.md, separa frontmatter YAML simples (key: value)
    do corpo. Retorna dict {frontmatter, body, raw}.
    """
    f = client_path / "contexto.md"
    if not f.is_file():
        return {"frontmatter": {}, "body": "", "raw": ""}

    raw = f.read_text(encoding="utf-8")
    fm, body = _split_frontmatter(raw)
    return {"frontmatter": fm, "body": body, "raw": raw}


def read_historico(client_path: Path, days: int = 7) -> dict[str, Any]:
    """
    Lê historico.md e retorna {entries: [...], raw, recent_text}.
    Cada entrada: linhas começando com `- ` ou `* ` ou data ISO.
    `recent_text` é o corpo dos últimos N dias (best-effort por data ISO no início da linha).
    """
    f = client_path / "historico.md"
    if not f.is_file():
        return {"entries": [], "raw": "", "recent_text": ""}

    raw = f.read_text(encoding="utf-8")
    cutoff = datetime.now().date() - timedelta(days=days)

    entries = []
    recent_lines: list[str] = []

    current_date = None
    for line in raw.splitlines():
        m = re.match(r"^[#\-\*\s]*?(\d{4}-\d{2}-\d{2})\b", line.strip())
        if m:
            try:
                current_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            except ValueError:
                current_date = None

        if current_date and current_date >= cutoff:
            recent_lines.append(line)

        if line.strip().startswith(("- ", "* ")):
            entries.append(line.strip()[2:])

    # se não conseguiu parsear data nenhuma, usa as últimas 30 linhas como fallback
    if not recent_lines:
        recent_lines = raw.splitlines()[-30:]

    return {
        "entries": entries,
        "raw": raw,
        "recent_text": "\n".join(recent_lines).strip(),
    }


def read_contatos(client_path: Path) -> dict[str, str]:
    """
    Lê contatos.md (se existir) e retorna {nome_lower: numero}.
    Aceita formatos:
        - João: 5511999998888
        - Joao da Silva — +55 11 99999-8888
        joão: (11) 99999-8888
    """
    f = client_path / "contatos.md"
    if not f.is_file():
        return {}

    raw = f.read_text(encoding="utf-8")
    out: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip().lstrip("-*").strip()
        if not line:
            continue
        # tenta separar por : ou — ou -
        m = re.match(r"^([^:—\-]+?)\s*[:—\-]\s*(.+)$", line)
        if not m:
            continue
        name = m.group(1).strip().lower()
        number = _normalize_phone(m.group(2).strip())
        if number:
            out[name] = number
    return out


def resolve_recipient(
    target: str,
    client_path: Path,
    contexto_fm: dict[str, Any],
) -> tuple[str, str]:
    """
    Resolve destinatário em (nome_legível, numero_e164_sem_+).

    Ordem:
      1. Se `target` é só dígito → usa direto
      2. Procura em contatos.md (case-insensitive, match substring)
      3. Procura em frontmatter do contexto.md (chaves comuns: contatos, whatsapp)
    """
    digits = _normalize_phone(target)
    if digits and target.replace("+", "").replace(" ", "").replace("-", "").isdigit():
        return target, digits

    name_key = target.strip().lower()

    contatos = read_contatos(client_path)
    if contatos:
        if name_key in contatos:
            return target, contatos[name_key]
        for k, v in contatos.items():
            if name_key in k or k in name_key:
                return k, v

    # frontmatter — tenta `contatos:` como dict YAML simples ou `whatsapp_<nome>:`
    fm = contexto_fm or {}
    fm_contatos = fm.get("contatos")
    if isinstance(fm_contatos, dict):
        for k, v in fm_contatos.items():
            if name_key in str(k).lower():
                num = _normalize_phone(str(v))
                if num:
                    return str(k), num

    # chaves chapadas tipo `whatsapp_joao: 5511...`
    for k, v in fm.items():
        if name_key in str(k).lower() and "whatsapp" in str(k).lower():
            num = _normalize_phone(str(v))
            if num:
                return str(k), num

    raise VaultError(
        f"não consegui resolver '{target}' como destinatário. "
        f"Adiciona em {client_path}/contatos.md (ex: '- {target}: 5511999998888') "
        f"ou passa o número direto com --to."
    )


def append_historico(client_path: Path, line: str) -> None:
    """
    Adiciona entrada datada no final do historico.md.
    Cria o arquivo se não existir.
    """
    f = client_path / "historico.md"
    today = datetime.now().strftime("%Y-%m-%d")
    entry = f"\n- {today} — {line}\n"
    if f.is_file():
        with f.open("a", encoding="utf-8") as fh:
            fh.write(entry)
    else:
        f.write_text(f"# Histórico\n{entry}", encoding="utf-8")


def save_relatorio(client_path: Path, recipient_label: str, content: str) -> Path:
    """
    Salva o relatório em clientes/<nome>/relatorios/YYYY-MM-DD-<destinatario>.md.
    Retorna o path criado.
    """
    rel_dir = client_path / "relatorios"
    rel_dir.mkdir(parents=True, exist_ok=True)
    today = datetime.now().strftime("%Y-%m-%d")
    slug = _slug(recipient_label)
    f = rel_dir / f"{today}-{slug}.md"

    header = (
        f"---\n"
        f"data: {today}\n"
        f"destinatario: {recipient_label}\n"
        f"---\n\n"
    )
    f.write_text(header + content + "\n", encoding="utf-8")
    return f


# ── helpers ─────────────────────────────────────────────────────────


def _split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    fm_block = parts[1].strip()
    body = parts[2].lstrip("\n")

    fm: dict[str, Any] = {}
    current_key: str | None = None
    nested: dict[str, Any] | None = None

    for raw_line in fm_block.splitlines():
        if not raw_line.strip() or raw_line.strip().startswith("#"):
            continue
        # nested simples: "  chave: valor" debaixo de uma chave-pai
        if raw_line.startswith((" ", "\t")) and current_key and nested is not None:
            sub = raw_line.strip()
            if ":" in sub:
                k, v = sub.split(":", 1)
                nested[k.strip()] = v.strip().strip("\"'")
            continue

        if ":" in raw_line:
            k, v = raw_line.split(":", 1)
            k = k.strip()
            v = v.strip()
            if not v:
                # abre um bloco nested
                nested = {}
                fm[k] = nested
                current_key = k
            else:
                fm[k] = v.strip("\"'")
                current_key = k
                nested = None
    return fm, body


def _normalize_phone(s: str) -> str:
    """Remove tudo que não for dígito. Retorna string vazia se não sobrar nada."""
    digits = re.sub(r"\D", "", s)
    return digits


def _slug(text: str) -> str:
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", text)
    ascii_only = nfkd.encode("ascii", "ignore").decode("ascii")
    return re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")[:40] or "destinatario"
