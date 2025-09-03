# FILE: scripts/read_by_phone.py
from __future__ import annotations

import argparse
import json
import re
import sys
from typing import Any, Dict, List, Optional

from scripts.sheets_repo import get_repo

def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))

def _normalize_digits(s: str) -> str:
    return re.sub(r"\D+", "", s or "")

def _lower(s: Any) -> str:
    return str(s or "").strip().lower()

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Busca linhas por telefone (parcial ou exato) e, opcionalmente, atualiza status_email."
    )
    parser.add_argument("--phone", required=True, help="Telefone a buscar. Pode ser parcial (ex.: 55119).")
    parser.add_argument("--exact", action="store_true", help="Se definido, casa exatamente o número (após normalizar).")
    parser.add_argument("--limit", type=int, default=50, help="Máximo de linhas a exibir (padrão: 50).")
    parser.add_argument("--raw", action="store_true", help="Imprime JSON puro da lista encontrada.")
    parser.add_argument("--set-status-email", dest="set_status_email", default=None,
                        help="Se definido, atualiza status_email para esse valor em todas as linhas com WAMID.")
    parser.add_argument("--show-row", action="store_true", help="Exibe também o número da linha no Sheets (1-based).")
    args = parser.parse_args(argv)

    try:
        repo = get_repo()
        repo._ensure_client()
        ws = repo._ws
        if ws is None:
            print("Erro: worksheet não inicializada.", file=sys.stderr)
            sys.exit(2)

        rows: List[Dict[str, Any]] = ws.get_all_records()
        if not rows:
            print("Planilha vazia.")
            return

        norm_query = _normalize_digits(args.phone)

        matches: List[Dict[str, Any]] = []
        rownums: List[int] = []  # mapeia cada match ao número da linha original (1-based)

        # get_all_records() ignora header e começa na 2, então linha N do rows -> Sheets row = N + 1
        for i, item in enumerate(rows, start=2):
            tel = _normalize_digits(item.get("telefone") or item.get("phone") or "")
            if not tel:
                continue
            ok = (tel == norm_query) if args.exact else (norm_query in tel)
            if ok:
                matches.append(item)
                rownums.append(i)
                if len(matches) >= max(1, args.limit):
                    break

        if not matches:
            print("Nenhuma linha encontrada para esse telefone.")
            return

        # Atualizar status_email se solicitado (usa wamid por segurança)
        if args.set_status_email is not None:
            for data, rownum in zip(matches, rownums):
                wamid = str(data.get("wamid") or "").strip()
                if not wamid:
                    continue
                try:
                    repo.update_status_email(wamid, args.set_status_email)
                except Exception as e:
                    print(f"Aviso: falha ao atualizar status_email na linha {rownum}: {e}", file=sys.stderr)
            # Recarrega registros atualizados (opcional)
            rows_updated = []
            for rn in rownums:
                # reconstrói dict a partir da linha (inclui qualquer atualização)
                headers: List[str] = ws.row_values(1)
                values: List[str] = ws.row_values(rn)
                if len(values) < len(headers):
                    values += [""] * (len(headers) - len(values))
                elif len(values) > len(headers):
                    values = values[: len(headers)]
                rows_updated.append({h.strip(): v for h, v in zip(headers, values)})
            matches = rows_updated

        if args.raw:
            if args.show_row:
                out = [{"row": rn, "data": m} for rn, m in zip(rownums, matches)]
            else:
                out = matches
            _print_json(out)
            return

        # saída humana
        print("=" * 80)
        mode = "EXATO" if args.exact else "PARCIAL"
        print(f"[OK] {len(matches)} linha(s) encontradas | busca: {mode} | telefone: {args.phone}")
        for idx, (rn, m) in enumerate(zip(rownums, matches), start=1):
            print("-" * 80)
            head = f"[{idx}] Linha (Sheets): {rn} | WAMID: {m.get('wamid','')}" if args.show_row else f"[{idx}] WAMID: {m.get('wamid','')}"
            print(head)
            _print_json(m)

    except Exception as e:
        print(f"Erro ao buscar por telefone: {e}", file=sys.stderr)
        sys.exit(2)

if __name__ == "__main__":
    main()