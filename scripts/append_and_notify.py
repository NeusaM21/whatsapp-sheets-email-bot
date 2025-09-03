# FILE: scripts/append_and_notify.py
# -*- coding: utf-8 -*-
"""
Append + Notify para o WhatsApp-Sheets-Email-Bot

Fluxo:
  1) Recebe o payload do webhook (Meta/WhatsApp ou simulado)
  2) Extrai e normaliza o lead: {name, phone, email?, message?, wamid, source}
  3) (Opcional) Dedupe por WAMID
  4) Upsert no Google Sheets por WAMID (sheets_write.upsert_by_wamid)
     - 1º upsert grava/atualiza com status_email=pending|skipped
  5) Se for novo: envia e-mail → status_email=sent|error
     Se for dedupe: não envia → status_email=skipped
  6) Upsert FINAL com REGISTRO COMPLETO e updated_at
     - updated_at SEMPRE igual ao timestamp da linha (mesmo valor)
     - preserva o timestamp original em caso de dedupe

Observações:
- Os timestamps são gerados no fuso do .env (TZ, padrão: America/Sao_Paulo)
  e formatados como "YYYY-MM-DD HH:MM:SS" para o Sheets interpretar.
- No writer (sheets_write.py), usamos value_input_option="USER_ENTERED".
"""

from __future__ import annotations

import os
import re
from uuid import uuid4
from typing import Any, Dict, Optional
from datetime import datetime

# zoneinfo: no Windows instale tzdata -> pip install tzdata
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

# -----------------------------------------------------------------------------
# Logs
# -----------------------------------------------------------------------------
try:
    from scripts.logging_setup import setup_logger
    log = setup_logger()
except Exception:  # pragma: no cover
    import logging
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    log = logging.getLogger("append_and_notify")
    log.propagate = False

# -----------------------------------------------------------------------------
# Sheets + Upsert
# -----------------------------------------------------------------------------
try:
    import gspread
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "gspread não encontrado. Instale com: pip install gspread google-auth"
    ) from e

try:
    from sheets_write import upsert_by_wamid  # escreve por NOME DE COLUNA
except Exception as e:  # pragma: no cover
    raise RuntimeError("Não foi possível importar sheets_write.upsert_by_wamid") from e

# E-mail
try:
    from scripts.send_email import send_lead_email
except Exception as e:  # pragma: no cover
    raise RuntimeError("Não foi possível importar scripts.send_email.send_lead_email") from e


# =============================================================================
# Utils
# =============================================================================

def _flag(name: str, default: int = 0) -> bool:
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def _env(name: str, default: str) -> str:
    return (os.getenv(name, default) or "").strip()


def _now_local_str() -> str:
    """
    Retorna data/hora local no fuso do .env (TZ), no formato que o Sheets
    interpreta como Data e hora (ex.: 2025-09-03 16:39:53).
    """
    tzname = os.getenv("TZ", "America/Sao_Paulo")
    try:
        tz = ZoneInfo(tzname) if ZoneInfo else None
    except Exception:
        tz = None
    dt = datetime.now(tz) if tz else datetime.now()
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _digits_only(s: str | None) -> str:
    return re.sub(r"\D+", "", s or "")


def _service_account():
    creds_path = _env("GOOGLE_APPLICATION_CREDENTIALS", "")
    if creds_path and os.path.exists(creds_path):
        return gspread.service_account(filename=creds_path)
    return gspread.service_account()


def _open_ws():
    """Abre a worksheet (aba) configurada; cria se não existir."""
    gc = _service_account()
    sheet_id = _env("SHEET_ID", "")
    sheet_url = _env("SHEET_URL", "")
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


def _header_map(ws) -> dict[str, int]:
    headers = ws.row_values(1)
    return {h.strip().lower(): i + 1 for i, h in enumerate(headers) if h.strip()}


def _find_row_by_wamid(ws, wamid: str) -> Optional[int]:
    """Procura o WAMID apenas na coluna COL_WAMID (mais rápido e previsível)."""
    if not wamid:
        return None
    hmap = _header_map(ws)
    col_name = _env("COL_WAMID", "wamid").lower()
    if col_name not in hmap:
        return None
    col_idx = hmap[col_name]
    try:
        matches = ws.findall(wamid)
        for cell in matches:
            if cell.col == col_idx:
                return cell.row
    except Exception:
        pass
    return None


def _call_upsert(record: Dict[str, Any], preserve_timestamp: bool = False) -> None:
    """
    Wrapper que tenta chamar upsert_by_wamid com preserve_timestamp se existir.
    """
    try:
        upsert_by_wamid(record, preserve_timestamp=preserve_timestamp)  # type: ignore[arg-type]
    except TypeError:
        upsert_by_wamid(record)  # type: ignore[call-arg]


# =============================================================================
# Payload parsing
# =============================================================================

def _extract_from_webhook(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrai o primeiro evento útil:
      entry[0].changes[0].value.messages[0].{id, from, text.body}
      entry[0].changes[0].value.contacts[0].profile.name
    """
    value = (
        (payload.get("entry") or [{}])[0]
        .get("changes", [{}])[0]
        .get("value", {})
    )
    msg = (value.get("messages") or [{}])[0]
    contact = (value.get("contacts") or [{}])[0]

    wamid = (msg.get("id") or "").strip()
    phone = _digits_only(msg.get("from"))
    name = ((contact.get("profile") or {}).get("name") or "").strip()
    text = ((msg.get("text") or {}).get("body") or "").strip()

    # heurística simples pra achar e-mail dentro do texto
    email = None
    m = re.search(r"[\w\.-]+@[\w\.-]+\.\w{2,}", text)
    if m:
        email = m.group(0).lower()

    return {
        "wamid": wamid or None,
        "name": name or None,
        "phone": phone or None,
        "email": email or None,
        "message": text or None,
        "source": "whatsapp",
    }


# =============================================================================
# Core
# =============================================================================

def process_incoming(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Ponto de entrada chamado por app.py.
    Retorna dict serializável com status da operação.
    """
    req = (os.getenv("REQUEST_ID_PREFIX", "WSE") + "-" + str(uuid4())[:8]).upper()
    log.info("[req=%s] webhook recebido", req)

    # 1) Extrair lead
    try:
        lead = _extract_from_webhook(payload)
    except Exception as e:
        log.exception("[req=%s] erro extraindo lead: %s", req, e)
        return {"status": "error", "req": req, "error": "extract_failed", "detail": str(e)}

    if not (lead.get("wamid") or lead.get("phone") or lead.get("name")):
        log.error("[req=%s] payload insuficiente (faltam wamid/phone/name)", req)
        return {"status": "error", "req": req, "error": "invalid_payload"}

    # Aliases de colunas (devem bater com o header da planilha)
    COL_TS   = _env("COL_TIMESTAMP", "timestamp")
    COL_NM   = _env("COL_NAME", "name")
    COL_PH   = _env("COL_PHONE", "phone")
    COL_EM   = _env("COL_EMAIL", "email")
    COL_MSG  = _env("COL_MESSAGE", "message")
    COL_SRC  = _env("COL_SOURCE", "source")
    COL_WID  = _env("COL_WAMID", "wamid")
    COL_SE   = _env("COL_STATUS_EMAIL", "status_email")
    COL_UPD  = _env("COL_UPDATED_AT", "updated_at")

    # 2) Dedupe (opcional) + captura do timestamp já existente (se houver)
    dedupe = _flag("DEDUPE_BY_WAMID", 1)
    is_dup = False
    row_idx: Optional[int] = None
    existing_ts: Optional[str] = None
    ws_for_dedupe = None

    if dedupe and (lead.get("wamid")):
        try:
            ws_for_dedupe = _open_ws()
            row_idx = _find_row_by_wamid(ws_for_dedupe, lead["wamid"])
            is_dup = bool(row_idx)
            if is_dup:
                # lê o timestamp atual da linha para usar também como updated_at
                hmap = _header_map(ws_for_dedupe)
                ts_col_lower = COL_TS.strip().lower()
                if ts_col_lower in hmap:
                    try:
                        existing_ts = ws_for_dedupe.cell(row_idx, hmap[ts_col_lower]).value
                    except Exception:
                        existing_ts = None
        except Exception as e:
            log.warning("[req=%s] dedupe falhou (seguindo sem dedupe): %s", req, e)

    # 3) Upsert inicial (marca pending/skipped)
    now_ts = _now_local_str()
    base_record = {
        COL_TS:  now_ts,
        COL_NM:  lead.get("name"),
        COL_PH:  lead.get("phone"),
        COL_EM:  lead.get("email"),
        COL_MSG: lead.get("message"),
        COL_SRC: lead.get("source") or "whatsapp",
        COL_WID: lead.get("wamid"),
        COL_SE:  "pending" if not is_dup else "skipped",
    }

    try:
        # Preserva timestamp se for update (dedupe) para não mudar a data original.
        _call_upsert(base_record, preserve_timestamp=True)
    except Exception as e:
        log.exception("[req=%s] falha no upsert inicial: %s", req, e)
        return {"status": "error", "req": req, "error": "sheets_upsert_failed", "detail": str(e)}

    # 4) E-mail
    email_status = "skipped" if is_dup else "sent"
    if is_dup:
        log.info("🟨 DEDUPE | req=%s | wamid=%s | linha=%s", req, lead.get("wamid"), row_idx)
    else:
        try:
            ok = send_lead_email({
                "name": lead.get("name"),
                "phone": lead.get("phone"),
                "email": lead.get("email"),
                "message": lead.get("message"),
                "source": lead.get("source") or "whatsapp",
                "wamid": lead.get("wamid"),
            })
            email_status = "sent" if ok else "error"
        except Exception as e:
            log.exception("[req=%s] erro enviando e-mail: %s", req, e)
            email_status = "error"

    # 5) Upsert FINAL — REGISTRO COMPLETO + status + updated_at
    #    Regra: updated_at = timestamp da linha (exato, sem drift).
    try:
        # timestamp a usar = se dedupe, o timestamp que já estava na linha;
        # caso contrário, o timestamp recém-gerado no passo 3.
        ts_for_updated_at = (existing_ts or base_record.get(COL_TS) or now_ts)

        merged_record = {
            COL_TS:  base_record.get(COL_TS) or now_ts,   # writer preserva TS se já existe
            COL_NM:  base_record.get(COL_NM),
            COL_PH:  base_record.get(COL_PH),
            COL_EM:  base_record.get(COL_EM),
            COL_MSG: base_record.get(COL_MSG),
            COL_SRC: base_record.get(COL_SRC),
            COL_WID: base_record.get(COL_WID),
            COL_SE:  email_status,
            COL_UPD: ts_for_updated_at,                   # <- EXATAMENTE igual ao timestamp
        }
        _call_upsert(merged_record, preserve_timestamp=True)
    except Exception as e:
        log.warning("[req=%s] falha ao marcar status_email/updated_at: %s", req, e)

    # 6) Resposta
    status = "dedupe" if is_dup else "ok"
    log.info("✅ %s | req=%s | wamid=%s | email=%s", status.upper(), req, lead.get("wamid"), email_status)

    return {
        "status": status,
        "req": req,
        "wamid": lead.get("wamid"),
        "row": row_idx,  # pode vir None se não buscamos
        "email_status": email_status,
        "lead": {
            "name": lead.get("name"),
            "phone": lead.get("phone"),
            "email": lead.get("email"),
            "source": lead.get("source") or "whatsapp",
        },
    }


# -----------------------------------------------------------------------------
# Debug manual
# -----------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    example = {
        "entry": [{
            "changes": [{
                "value": {
                    "messages": [{
                        "id": "wamid.TEST.DEBUG",
                        "from": "5511999999999",
                        "text": {"body": "Olá, quero orçamento. meuemail@exemplo.com"}
                    }],
                    "contacts": [{
                        "profile": {"name": "Neusa Debug"}
                    }]
                }
            }]
        }]
    }
    print(process_incoming(example))