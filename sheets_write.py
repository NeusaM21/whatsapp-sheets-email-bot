# FILE: sheets_write.py
from __future__ import annotations

import os
import json
from typing import Dict, Any, Optional
from datetime import datetime

import gspread
from gspread.utils import rowcol_to_a1

# -----------------------------------------------------------------------------
# Logger
# -----------------------------------------------------------------------------
try:
    from scripts.logging_setup import setup_logger
    log = setup_logger("whatsapp-sheets-email-bot.sheets_write")
except Exception:
    import logging
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)-8s | %(message)s",
    )
    log = logging.getLogger("sheets_write")
    log.propagate = False

# ---- timezone local (usa TZ do .env) ----
try:
    from zoneinfo import ZoneInfo  # Py3.9+
except Exception:
    ZoneInfo = None  # type: ignore


# =============================================================================
# Helpers de ambiente / nomes de colunas
# =============================================================================
def _env(name: str, default: str = "") -> str:
    return (os.getenv(name, default) or "").strip()

def _colnames() -> Dict[str, str]:
    """Nomes de colunas vindos do .env; todos em lower-case para comparação."""
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
    """String de data/hora local (YYYY-MM-DD HH:MM:SS), respeitando TZ do .env."""
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
    Usa GOOGLE_APPLICATION_CREDENTIALS se existir; senão tenta:
    SERVICE_ACCOUNT_FILE / SERVICE_ACCOUNT_JSON; por fim, default do gspread.
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
def _headers(ws) -> list[str]:
    return [h.strip() for h in ws.row_values(1)]

def _header_index_map(ws) -> Dict[str, int]:
    """Mapa: header_lower -> índice ZERO-based (0..n-1)."""
    idx: Dict[str, int] = {}
    for i, h in enumerate(_headers(ws)):
        if h:
            idx[h.lower()] = i
    return idx


# =============================================================================
# Busca precisa por WAMID
# =============================================================================
def _find_row_by_wamid(ws, wamid: str) -> Optional[int]:
    """
    Retorna número da linha (1-based) onde o WAMID está, ou None.
    Busca APENAS na coluna configurada em COL_WAMID (preciso e rápido).
    """
    wamid = (wamid or "").strip()
    if not wamid:
        return None

    idx_map = _header_index_map(ws)
    wamid_col_name = _colnames()["wamid"]

    if wamid_col_name not in idx_map:
        log.warning("Coluna WAMID não encontrada no header.")
        return None

    col_idx = idx_map[wamid_col_name] + 1  # 1-based
    try:
        # caminho rápido: findall + filtro de coluna e igualdade exata
        matches = ws.findall(wamid)
        for cell in matches:
            if cell.col == col_idx and (cell.value or "").strip() == wamid:
                return cell.row
    except Exception as e:
        log.warning("findall falhou (wamid=%s). Fallback por coluna. err=%s", wamid, e)

    # fallback: varrer apenas a coluna WAMID
    try:
        col_vals = ws.col_values(col_idx)
        for r, val in enumerate(col_vals, start=1):
            if r == 1:  # header
                continue
            if (val or "").strip() == wamid:
                return r
    except Exception as e:
        log.warning("Falha ao ler coluna WAMID | err=%s", e)

    return None


# =============================================================================
# API pública
# =============================================================================
def append_by_header(record: Dict[str, Any]) -> int:
    """
    Apenas adiciona uma nova linha, alinhando pelos nomes do header (case-insensitive).
    Retorna o índice (1-based) da linha criada.
    """
    ws = _open_ws()
    headers = _headers(ws)
    idx_map = _header_index_map(ws)

    row = [""] * max(1, len(headers))
    for field, value in record.items():
        key = (field or "").strip().lower()
        if key in idx_map and idx_map[key] < len(row):
            row[idx_map[key]] = value

    ws.append_row(row, value_input_option="USER_ENTERED", table_range="A1")

    # tentar localizar exatamente a linha criada pelo WAMID, se presente
    wamid_key = "wamid" if "wamid" in record else _colnames()["wamid"]
    wamid_val = (record.get(wamid_key) or "").strip()
    if wamid_val:
        found = _find_row_by_wamid(ws, wamid_val)
        if found:
            return found

    # fallback: número de linhas preenchidas
    try:
        return len(ws.get_all_values())
    except Exception:
        return -1


def upsert_by_wamid(record: Dict[str, Any], preserve_timestamp: bool = True) -> Dict[str, Any]:
    """
    Upsert por WAMID.
    - Se WAMID existir: atualiza a MESMA linha (sem duplicar).
    - Se não existir: cria nova linha.
    - Se preserve_timestamp=True: nunca sobrescreve a coluna 'timestamp'.
    - UPDATE seletivo: apenas colunas presentes no record e não imutáveis.
    Retorna: {"row": int, "created": bool}
    """
    ws = _open_ws()
    headers = _headers(ws)
    idx_map = _header_index_map(ws)
    cols = _colnames()

    # aceita 'wamid' literal ou o alias configurado
    wamid_key = "wamid" if "wamid" in record else cols["wamid"]
    wamid_val = (record.get(wamid_key) or "").strip()
    if not wamid_val:
        raise ValueError("upsert_by_wamid requer campo 'wamid' no record.")

    # localizar linha existente
    row_num = _find_row_by_wamid(ws, wamid_val)

    if row_num is None:
        # ---------------------- INSERT ----------------------
        # monta a nova linha alinhada ao header
        row_values = [""] * max(1, len(headers))
        for field, value in record.items():
            k = (field or "").strip().lower()
            if k in idx_map:
                row_values[idx_map[k]] = value

        ws.append_row(row_values, value_input_option="USER_ENTERED", table_range="A1")
        created = True

        # localizar a linha recém criada
        found = _find_row_by_wamid(ws, wamid_val)
        if found:
            row_num = found
        else:
            try:
                row_num = len(ws.get_all_values())
            except Exception:
                row_num = -1

        log.info("Append concluído | wamid=%s | row=%s", wamid_val, row_num)
        return {"row": row_num, "created": created}

    # ---------------------- UPDATE IN-PLACE (SELETIVO) ----------------------
    ts_name  = cols["timestamp"]
    upd_name = cols["updated_at"]

    # colunas que NUNCA serão tocadas (fórmulas/protegidas). Ex: "timestamp_convertido,updated_at_convertido,diff_minutos"
    immutable = {c.strip().lower() for c in _env("IMMUTABLE_COLS", "").split(",") if c.strip()}

    # 1) preservar timestamp (se solicitado)
    if preserve_timestamp and ts_name in idx_map:
        try:
            current_ts = ws.cell(row_num, idx_map[ts_name] + 1).value
        except Exception:
            current_ts = None
        if current_ts:
            record[ts_name] = current_ts  # injeta o existente para não ser sobrescrito

    # 2) garantir updated_at quando não vier no record
    if upd_name in idx_map and (upd_name not in record or str(record.get(upd_name) or "").strip() == ""):
        record[upd_name] = _now_local_str()

    # 3) aplicar célula a célula somente nas colunas presentes no record e não imutáveis
    updates = 0
    for field, value in record.items():
        k = (field or "").strip().lower()
        if k not in idx_map:
            continue
        if k in immutable:
            continue
        a1 = rowcol_to_a1(row_num, idx_map[k] + 1)
        ws.update(a1, "" if value is None else value, raw=False)
        updates += 1

    log.info("Update seletivo concluído | wamid=%s | row=%s | cols_atualizadas=%s", wamid_val, row_num, updates)
    return {"row": row_num, "created": False}