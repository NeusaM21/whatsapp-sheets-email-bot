# FILE: sheets_write.py
import os
import json
from typing import Dict, List, Optional
from datetime import datetime

import gspread
from gspread.utils import rowcol_to_a1

# ---- timezone local (usa TZ do .env) ----
try:
    from zoneinfo import ZoneInfo  # Py3.9+
except Exception:  # Windows sem zoneinfo -> pip install tzdata
    ZoneInfo = None  # type: ignore


# =============================================================================
# Helpers de ambiente / nomes de colunas
# =============================================================================

def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()

def _colnames() -> Dict[str, str]:
    """
    Nomes de colunas vindos do .env; tudo em lower-case para comparação.
    """
    return {
        "timestamp":    _env("COL_TIMESTAMP", "timestamp").lower(),
        "name":         _env("COL_NAME", "name").lower(),
        "phone":        _env("COL_PHONE", "phone").lower(),
        "email":        _env("COL_EMAIL", "email").lower(),
        "message":      _env("COL_MESSAGE", "message").lower(),
        "source":       _env("COL_SOURCE", "source").lower(),
        "wamid":        _env("COL_WAMID", "wamid").lower(),
        "status_email": _env("COL_STATUS_EMAIL", "status_email").lower(),
        "updated_at":   _env("COL_UPDATED_AT", "updated_at").lower(),
    }

def _now_local_str() -> str:
    """
    Retorna string de data/hora local no formato que o Sheets interpreta
    (YYYY-MM-DD HH:MM:SS), respeitando TZ do .env (default America/Sao_Paulo).
    """
    tzname = _env("TZ", "America/Sao_Paulo")
    try:
        tz = ZoneInfo(tzname) if ZoneInfo else None
    except Exception:
        tz = None
    dt = datetime.now(tz) if tz else datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


# =============================================================================
# Conexão / abertura de planilha
# =============================================================================

def _service_account():
    """
    Usa GOOGLE_APPLICATION_CREDENTIALS se existir; senão tenta SERVICE_ACCOUNT_FILE
    / SERVICE_ACCOUNT_JSON; por fim, cai no default do gspread.
    """
    cred_path = _env("GOOGLE_APPLICATION_CREDENTIALS")
    if cred_path and os.path.isfile(cred_path):
        return gspread.service_account(filename=cred_path)

    sa_file = _env("SERVICE_ACCOUNT_FILE")
    if sa_file and os.path.isfile(sa_file):
        return gspread.service_account(filename=sa_file)

    sa_json = _env("SERVICE_ACCOUNT_JSON")
    if sa_json:
        return gspread.service_account_from_dict(json.loads(sa_json))

    return gspread.service_account()

def _open_ws():
    """
    Abre a worksheet conforme .env:
      - SHEET_ID ou SHEET_URL
      - SHEET_TAB_LEADS (default: "leads")
    """
    gc = _service_account()

    sheet_id = _env("SHEET_ID")
    sheet_url = _env("SHEET_URL")
    tab = _env("SHEET_TAB_LEADS", "leads") or "leads"

    if sheet_id:
        sh = gc.open_by_key(sheet_id)
    elif sheet_url:
        sh = gc.open_by_url(sheet_url)
    else:
        raise RuntimeError("Configure SHEET_ID ou SHEET_URL no .env")

    try:
        return sh.worksheet(tab)
    except gspread.WorksheetNotFound:
        return sh.add_worksheet(title=tab, rows=1000, cols=26)


# =============================================================================
# Cabeçalho / mapeamento
# =============================================================================

def _headers(ws) -> List[str]:
    return [h.strip() for h in ws.row_values(1)]

def _header_index_map(ws) -> Dict[str, int]:
    """
    Mapa: header_lower -> índice ZERO-based.
    """
    idx: Dict[str, int] = {}
    for i, h in enumerate(_headers(ws)):
        if h:
            idx[h.lower()] = i
    return idx


# =============================================================================
# API pública
# =============================================================================

def append_by_header(record: Dict[str, str]) -> None:
    """
    Insere ao final mapeando pelos nomes EXATOS do cabeçalho (case-insensitive).
    Só preenche as colunas existentes no header.
    """
    ws = _open_ws()
    headers = _headers(ws)
    idx_map = _header_index_map(ws)

    row = [""] * max(1, len(headers))
    for field, value in record.items():
        key = (field or "").strip().lower()
        if key in idx_map and idx_map[key] < len(row):
            row[idx_map[key]] = value

    # Fundamental para o Sheets interpretar datas/formatos:
    ws.append_row(row, value_input_option="USER_ENTERED")


def _find_row_by_wamid(ws, wamid: str) -> Optional[int]:
    """
    Retorna número da linha (1-based) onde o WAMID está, ou None.
    Busca APENAS na coluna configurada em COL_WAMID.
    """
    if not wamid:
        return None
    idx_map = _header_index_map(ws)
    colnames = _colnames()
    wamid_col_name = colnames["wamid"]

    if wamid_col_name not in idx_map:
        return None

    col_idx_1based = idx_map[wamid_col_name] + 1
    try:
        values = ws.col_values(col_idx_1based)
    except Exception:
        return None

    # values[0] é header; dados começam na linha 2
    for i, v in enumerate(values[1:], start=2):
        if (v or "").strip() == wamid.strip():
            return i
    return None


def upsert_by_wamid(record: Dict[str, str], preserve_timestamp: bool = True) -> Dict[str, str]:
    """
    Se existir WAMID, atualiza a linha; senão, insere.
      - preserve_timestamp=True: mantém a coluna 'timestamp' da linha existente.
      - Se 'updated_at' NÃO vier no record e a coluna existir, o writer preenche.
    Retorna: {"action": "inserted"|"updated", "row": "<número>"}
    """
    colnames = _colnames()
    if not record.get("wamid") and not record.get(colnames["wamid"]):
        raise AssertionError("upsert_by_wamid requer a chave 'wamid' no record")

    ws = _open_ws()
    headers = _headers(ws)
    idx_map = _header_index_map(ws)

    # aceita 'wamid' normal ou com o nome de coluna do .env
    wamid_key = "wamid" if "wamid" in record else colnames["wamid"]
    wamid_val = (record.get(wamid_key) or "").strip()
    if not wamid_val:
        raise AssertionError("record['wamid'] está vazio")

    # monta a linha alvo com o tamanho do cabeçalho
    row_values = [""] * max(1, len(headers))
    for field, value in record.items():
        k = (field or "").strip().lower()
        if k in idx_map:
            row_values[idx_map[k]] = value

    # localizar linha existente
    row_num = _find_row_by_wamid(ws, wamid_val)

    if row_num is None:
        # INSERT
        ws.append_row(row_values, value_input_option="USER_ENTERED")
        # tenta recuperar a linha pelo WAMID recém gravado
        try:
            row_num = _find_row_by_wamid(ws, wamid_val)
        except Exception:
            row_num = None
        if row_num is None:
            # fallback: conta linhas preenchidas
            try:
                row_num = len(ws.get_all_values())
            except Exception:
                row_num = -1
        return {"action": "inserted", "row": str(row_num)}

    # UPDATE -------------------------------------------------------------
    # preserva timestamp existente (se habilitado)
    ts_col_name = colnames["timestamp"]
    if preserve_timestamp and ts_col_name in idx_map:
        ts_col_1based = idx_map[ts_col_name] + 1
        try:
            current_ts = ws.cell(row_num, ts_col_1based).value
        except Exception:
            current_ts = None
        if current_ts:
            row_values[idx_map[ts_col_name]] = current_ts

    # updated_at: só preenche se NÃO veio no record
    upd_col_name = colnames["updated_at"]
    if upd_col_name in idx_map:
        has_value_in_record = (
            upd_col_name in record and str(record[upd_col_name] or "").strip() != ""
        )
        if not has_value_in_record:
            row_values[idx_map[upd_col_name]] = _now_local_str()

    # range A1 da linha inteira (A -> última coluna do header)
    end_col = len(headers)
    a1_range = f"{rowcol_to_a1(row_num, 1)}:{rowcol_to_a1(row_num, end_col)}"

    ws.update(a1_range, [row_values], value_input_option="USER_ENTERED")
    return {"action": "updated", "row": str(row_num)}