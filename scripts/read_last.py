# FILE: scripts/read_last.py
from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from scripts.sheets_repo import get_repo


def _print_json(data: Any) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Lê as últimas linhas da planilha (após o cabeçalho)."
    )
    parser.add_argument(
        "--n",
        type=int,
        default=1,
        help="Quantas linhas finais mostrar (padrão: 1).",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Imprime JSON puro (lista de dicts) sem formatação extra.",
    )
    args = parser.parse_args(argv)

    try:
        repo = get_repo()
        # Garantir cliente/worksheet prontos
        repo._ensure_client()  # ok usar internamente aqui para utilidade de debug
        ws = repo._ws
        if ws is None:
            print("Erro: worksheet não inicializada.", file=sys.stderr)
            sys.exit(1)

        # Pega todos os registros (ignora cabeçalho automaticamente)
        rows: List[Dict[str, Any]] = ws.get_all_records()

        if not rows:
            print("Planilha vazia.")
            return

        n = max(1, int(args.n or 1))
        start = max(0, len(rows) - n)
        tail = rows[start:]

        if args.raw:
            _print_json(tail)
            return

        # Bonitinho no terminal
        total = len(rows)
        for idx, item in enumerate(tail, start=1):
            abs_idx = start + idx  # índice “humano” considerando a lista de registros (começa em 1)
            print("=" * 80)
            print(f"[{idx}/{len(tail)}] Registro #{abs_idx} de {total}")
            print("-" * 80)
            _print_json(item)

    except Exception as e:
        print(f"Erro ao ler a planilha: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()