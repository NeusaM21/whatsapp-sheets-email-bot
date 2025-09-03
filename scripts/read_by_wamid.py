# FILE: scripts/read_by_wamid.py
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from scripts.sheets_repo import get_repo


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _row_dict(ws, row_num: int) -> Dict[str, Any]:
    """
    Constrói um dict {header: valor} a partir do número da linha (1-based).
    Assume headers na linha 1.
    """
    headers: List[str] = ws.row_values(1)
    values: List[str] = ws.row_values(row_num)

    # normaliza tamanho
    if len(values) < len(headers):
        values += [""] * (len(headers) - len(values))
    elif len(values) > len(headers):
        values = values[: len(headers)]

    return {h.strip(): v for h, v in zip(headers, values)}


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Lê a linha da planilha correspondente a um WAMID específico (e opcionalmente atualiza status_email)."
    )
    parser.add_argument(
        "--wamid",
        required=True,
        help="ID do WhatsApp (WAMID) a localizar.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Imprime JSON puro com a linha encontrada.",
    )
    parser.add_argument(
        "--show-row",
        action="store_true",
        help="Exibe também o número da linha no Google Sheets (1-based).",
    )
    parser.add_argument(
        "--set-status-email",
        dest="set_status_email",
        default=None,
        help="Se definido, atualiza a coluna status_email para esse valor (ex.: 'enviado').",
    )

    args = parser.parse_args(argv)
    wamid = str(args.wamid).strip()
    if not wamid:
        print("Erro: --wamid não pode ser vazio.", file=sys.stderr)
        sys.exit(2)

    try:
        repo = get_repo()
        repo._ensure_client()  # ok usar aqui (utilitário/CLI)
        ws = repo._ws
        if ws is None:
            print("Erro: worksheet não inicializada.", file=sys.stderr)
            sys.exit(2)

        row_num = repo.find_row_by_wamid(wamid)
        if not row_num:
            print(f"Nenhuma linha encontrada para WAMID: {wamid}", file=sys.stderr)
            sys.exit(1)

        # Atualiza status_email se solicitado
        if args.set_status_email is not None:
            try:
                updated = repo.update_status_email(wamid, args.set_status_email)
                if not updated:
                    print(f"Aviso: não foi possível atualizar status_email para o WAMID {wamid}", file=sys.stderr)
                # Recarrega a linha após atualizar
            except Exception as e:
                print(f"Aviso: falha ao atualizar status_email: {e}", file=sys.stderr)

        data = _row_dict(ws, row_num)

        if args.raw:
            out = {"row": row_num, "data": data} if args.show_row else data
            _print_json(out)
            return

        # Saída “bonita”
        print("=" * 80)
        print(f"[OK] Linha encontrada para WAMID: {wamid}")
        if args.show_row:
            print(f"Linha (Sheets, 1-based): {row_num}")
        print("-" * 80)
        _print_json(data)

    except SystemExit:
        raise
    except Exception as e:
        print(f"Erro ao ler/atualizar a planilha: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()