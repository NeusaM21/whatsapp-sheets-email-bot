# FILE: scripts/sheets_repo.py
from __future__ import annotations

import os
from typing import List, Optional
from datetime import datetime

from dotenv import load_dotenv
import gspread

# Cabeçalho padrão (ordem usada no append)
HEADERS: List[str] = [
    "timestamp",
    "nome",
    "telefone",
    "mensagem",
    "origem",
    "status_email",
    "wamid",
]

load_dotenv(override=True)

def now_iso() -> str:
    """Timestamp local em ISO (até segundos)."""
    return datetime.now().isoformat(timespec="seconds")

def _service_account():
    """
    Cria cliente gspread via Service Account.
    Use no .env:
      GOOGLE_APPLICATION_CREDENTIALS=./seu-arquivo.json
    ou   SERVICE_ACCOUNT_JSON=./seu-arquivo.json
    """
    path = (os.getenv("GOOGLE_APPLICATION_CREDENTIALS") or os.getenv("SERVICE_ACCOUNT_JSON") or "").strip()
    if not path:
        raise RuntimeError(
            "Credenciais não encontradas. Defina GOOGLE_APPLICATION_CREDENTIALS (ou SERVICE_ACCOUNT_JSON) no .env apontando para o JSON da Service Account."
        )
    if not os.path.exists(path):
        raise RuntimeError(
            f"Arquivo de credenciais não existe: {path}. Confirme o caminho no .env."
        )
    try:
        return gspread.service_account(filename=path)
    except Exception as e:
        raise RuntimeError(f"Falha ao carregar Service Account: {e}")

def _open_spreadsheet(client) -> gspread.Spreadsheet:
    """
    Abre a planilha por ID ou por nome.
    .env aceitos:
      GOOGLE_SHEETS_SPREADSHEET_ID (recomendado)
      GOOGLE_SHEETS_SPREADSHEET_NAME (alternativo)
    """
    ssid = (os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") or "").strip()
    ssname = (os.getenv("GOOGLE_SHEETS_SPREADSHEET_NAME") or "").strip()

    if ssid:
        try:
            return client.open_by_key(ssid)
        except Exception as e:
            raise RuntimeError(f"Não consegui abrir por ID '{ssid}': {e}")

    if ssname:
        try:
            return client.open(ssname)
        except Exception as e:
            raise RuntimeError(f"Não consegui abrir por NOME '{ssname}': {e}")

    raise RuntimeError(
        "Defina no .env GOOGLE_SHEETS_SPREADSHEET_ID (ou GOOGLE_SHEETS_SPREADSHEET_NAME)."
    )

def _ensure_headers(ws: gspread.Worksheet) -> None:
    """
    Garante cabeçalho na linha 1 exatamente como em HEADERS.
    Se a linha 1 estiver vazia ou diferente, sobrescreve.
    """
    try:
        first_row = ws.row_values(1)
    except Exception:
        first_row = []

    needs_update = (len(first_row) < len(HEADERS)) or any(
        (i >= len(first_row)) or (first_row[i].strip().lower() != HEADERS[i].lower())
        for i in range(len(HEADERS))
    )

    if needs_update:
        ws.update("A1:G1", [HEADERS])  # uma linha (lista de listas)

def get_sheet() -> gspread.Worksheet:
    """
    Retorna a worksheet definida no .env:
      GOOGLE_SHEETS_WORKSHEET=leads   (default)
    """
    client = _service_account()
    sh = _open_spreadsheet(client)
    ws_name = (os.getenv("GOOGLE_SHEETS_WORKSHEET") or "leads").strip()

    try:
        ws = sh.worksheet(ws_name)
    except Exception:
        # se não existe, cria
        try:
            ws = sh.add_worksheet(title=ws_name, rows=1000, cols=20)
        except Exception as e:
            raise RuntimeError(f"Falha ao abrir/criar worksheet '{ws_name}': {e}")

    _ensure_headers(ws)
    return ws

def find_wamid(ws: gspread.Worksheet, wamid: str) -> bool:
    """
    Verifica se já existe esse WAMID na coluna G (7).
    Ignora o cabeçalho.
    """
    if not wamid:
        return False
    try:
        col = ws.col_values(7)  # G
    except Exception as e:
        raise RuntimeError(f"Falha ao ler coluna G (wamid): {e}")

    # Remove header e compara exato
    for val in col[1:]:
        if val.strip() == wamid:
            return True
    return False

def append_row(ws: gspread.Worksheet, row: list) -> None:
    """Append na worksheet com USER_ENTERED (respeita formatos)."""
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
    except Exception as e:
        raise RuntimeError(f"Falha ao inserir linha: {e}")