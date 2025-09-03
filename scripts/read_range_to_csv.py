# FILE: scripts/read_range_to_csv.py
from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, List, Optional, Tuple

from scripts.sheets_repo import get_repo


def _col_letter_to_index(letter: str) -> int:
    """Converte 'A'->1, 'B'->2, ..., 'AA'->27 (1-based)."""
    letter = letter.strip().upper()
    if not letter or not re.fullmatch(r"[A-Z]+", letter):
        raise ValueError(f"Coluna inválida: {letter}")
    n = 0
    for ch in letter:
        n = n * 26 + (ord(ch) - ord("A") + 1)
    return n


def _parse_a1_range(a1: str) -> Tuple[Optional[int], Optional[int], Optional[int], Optional[int]]:
    """
    Interpreta range A1 simplificado.
      - "A2:G20"  -> (2,20,1,7)
      - "A:G"     -> (None,None,1,7)
      - "2:100"   -> (2,100,None,None)
      - "A1"      -> (1,1,1,1)
    Retorna (row_start,row_end,col_start,col_end), todos 1-based (ou None).
    """
    a1 = a1.replace(" ", "")

    m = re.fullmatch(r"([A-Za-z]+)(\d+):([A-Za-z]+)(\d+)", a1)
    if m:
        c1, r1, c2, r2 = m.group(1), int(m.group(2)), m.group(3), int(m.group(4))
        return (r1, r2, _col_letter_to_index(c1), _col_letter_to_index(c2))

    m = re.fullmatch(r"([A-Za-z]+):([A-Za-z]+)", a1)
    if m:
        c1, c2 = m.group(1), m.group(2)
        return (None, None, _col_letter_to_index(c1), _col_letter_to_index(c2))

    m = re.fullmatch(r"(\d+):(\d+)", a1)
    if m:
        r1, r2 = int(m.group(1)), int(m.group(2))
        return (r1, r2, None, None)

    m = re.fullmatch(r"([A-Za-z]+)(\d+)", a1)
    if m:
        c, r = m.group(1), int(m.group(2))
        return (r, r, _col_letter_to_index(c), _col_letter_to_index(c))

    # fallback
    return (None, None, None, None)


def _slice_headers_for_range(ws, col_start: Optional[int], col_end: Optional[int]) -> List[str]:
    headers: List[str] = ws.row_values(1)
    if not headers:
        return []
    if col_start is None or col_end is None:
        return headers
    start_idx = max(0, col_start - 1)
    end_idx_exclusive = max(start_idx, col_end)  # já 1-based -> exclusivo
    return headers[start_idx:end_idx_exclusive]


def _normalize_row_len(row: List[Any], size: int) -> List[str]:
    r = [str(x) if x is not None else "" for x in row]
    if len(r) < size:
        r += [""] * (size - len(r))
    elif len(r) > size:
        r = r[:size]
    return r


def _default_outfile() -> Path:
    # salva no diretório do projeto (pai de scripts)/exports
    base = Path(__file__).resolve().parents[1]  # projeto
    outdir = base / "exports"
    outdir.mkdir(parents=True, exist_ok=True)
    tag = datetime.now().strftime("%Y%m%d_%H%M%S")
    return outdir / f"sheets_export_{tag}.csv"


def _unique_path(p: Path) -> Path:
    """Se o caminho existir, gera um nome único acrescentando _1, _2, ..."""
    if not p.exists():
        return p
    stem, suffix = p.stem, p.suffix
    parent = p.parent
    i = 1
    while True:
        candidate = parent / f"{stem}_{i}{suffix}"
        if not candidate.exists():
            return candidate
        i += 1


def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        description="Exporta um intervalo A1 do Google Sheets para CSV."
    )
    parser.add_argument("--range", "-r", dest="a1", required=True,
                        help='Range A1 (ex.: "A2:G20", "A:G", "2:100").')
    parser.add_argument("--with-headers", action="store_true",
                        help="Usa headers da linha 1 (só das colunas do range) como primeira linha do CSV.")
    parser.add_argument("--outfile", "-o", type=str, default="",
                        help="Caminho do CSV de saída. Se vazio, cria em exports/ com timestamp.")
    parser.add_argument("--delimiter", "-d", type=str, default=",",
                        help="Delimitador do CSV (padrão: ,). Use ';' para Excel brasileiro.")
    parser.add_argument("--encoding", type=str, default="utf-8-sig",
                        help="Encoding do arquivo (padrão: utf-8-sig para abrir bem no Excel/Windows).")
    parser.add_argument("--overwrite", action="store_true",
                        help="Se definido, sobrescreve o arquivo de saída se já existir.")
    args = parser.parse_args(argv)

    if not args.delimiter:
        print("Erro: --delimiter não pode ser vazio.", file=sys.stderr)
        sys.exit(2)
    if len(args.delimiter) != 1:
        print("Erro: --delimiter deve ter 1 caractere (ex.: ',' ou ';').", file=sys.stderr)
        sys.exit(2)

    try:
        repo = get_repo()
        repo._ensure_client()
        ws = repo._ws
        if ws is None:
            print("Erro: worksheet não inicializada.", file=sys.stderr)
            sys.exit(2)

        values: List[List[Any]] = ws.get(args.a1) or []
        if not values:
            print("Intervalo vazio (sem dados). Nada a exportar.")
            return

        row_start, row_end, col_start, col_end = _parse_a1_range(args.a1)
        headers_slice = _slice_headers_for_range(ws, col_start, col_end)

        # Decide arquivo de saída
        outfile = Path(args.outfile) if args.outfile else _default_outfile()
        if outfile.exists() and not args.overwrite:
            outfile = _unique_path(outfile)
        outfile.parent.mkdir(parents=True, exist_ok=True)

        with outfile.open("w", newline="", encoding=args.encoding) as f:
            writer = csv.writer(f, delimiter=args.delimiter, quoting=csv.QUOTE_MINIMAL)

            if args.with_headers:
                # sempre escreve headers com base na linha 1 (recortada pelo range)
                headers_norm = [h.strip() for h in headers_slice] if headers_slice else []
                if headers_norm:
                    writer.writerow(headers_norm)

                # corpo: se o range já inclui a linha 1, evitar duplicar header
                start_idx = 0
                if row_start == 1 and values:
                    # Se a primeira linha do range bate (case-insensitive) com headers_slice, pula
                    v0 = [str(x).strip().lower() for x in values[0]]
                    h0 = [h.strip().lower() for h in headers_norm]
                    if len(v0) == len(h0) and v0 == h0:
                        start_idx = 1

                for row in values[start_idx:]:
                    rown = _normalize_row_len(row, len(headers_norm) if headers_norm else len(row))
                    writer.writerow(rown)
            else:
                # Sem headers: exporta as linhas cruas do range
                for row in values:
                    writer.writerow([str(x) if x is not None else "" for x in row])

        print(f"[OK] CSV exportado: {outfile.resolve()}")
        print(f"Range: {args.a1} | Linhas: {len(values)} | Delimitador: '{args.delimiter}' | Encoding: {args.encoding}")

    except SystemExit:
        raise
    except Exception as e:
        print(f"Erro ao exportar CSV: {e}", file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()