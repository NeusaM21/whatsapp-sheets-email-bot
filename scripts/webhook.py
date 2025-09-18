# FILE: scripts/webhook.py
from __future__ import annotations

import os
import sys
import json
import importlib.util
from pathlib import Path
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify

# Logger plugável (PowerShell-friendly)
try:
    from scripts.logging_setup import setup_logger, set_request_id, with_request_id
except Exception:  # fallback mínimo
    import logging

    def setup_logger(name: str = "whatsapp-sheets-email-bot"):
        logging.basicConfig(
            level=os.getenv("LOG_LEVEL", "INFO").upper(),
            format="%(asctime)s | %(levelname)-8s | %(message)s",
        )
        lg = logging.getLogger(name)
        lg.propagate = False
        return lg

    def set_request_id(_: str) -> None: ...
    from contextlib import contextmanager
    @contextmanager
    def with_request_id(_: str):
        yield

log = setup_logger("whatsapp-sheets-email-bot.webhook")

# -----------------------------------------------------------------------------
# Config
# -----------------------------------------------------------------------------
VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "um_token_bem_forte_aqui")

# url_prefix = "/webhook" → rotas: /webhook (GET/POST) e /webhook/status (GET)
webhook_bp = Blueprint("webhook", __name__, url_prefix="/webhook")


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def _shorten(s: Optional[str], n: int = 1200) -> str:
    if not s:
        return ""
    return s if len(s) <= n else (s[:n] + "...")

def _import_handler():
    """
    Tenta importar handle_incoming_message primeiro via package (scripts.append_and_notify),
    depois por caminho absoluto ao arquivo scripts/append_and_notify.py.
    """
    # 1) Tentativa via package
    try:
        from scripts.append_and_notify import handle_incoming_message  # type: ignore
        log.debug("Handler importado: scripts.append_and_notify.handle_incoming_message")
        return handle_incoming_message
    except Exception as e:
        log.debug(f"Import via package falhou: {e!r}")

    # 2) Tentativa via caminho absoluto
    mod_path = Path(__file__).with_name("append_and_notify.py")
    if not mod_path.exists():
        raise ImportError(f"Arquivo não encontrado: {mod_path}")

    spec = importlib.util.spec_from_file_location("append_and_notify", str(mod_path))
    if not spec or not spec.loader:  # type: ignore
        raise ImportError("spec inválido para append_and_notify")

    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore
    log.debug(f"Handler carregado via caminho: {mod_path}")
    return getattr(mod, "handle_incoming_message")


def _extract_request_id(payload: Dict[str, Any]) -> str:
    """
    Tenta extrair um identificador estável do evento (ex.: WAMID); se não, gera genérico.
    """
    # comuns em payloads WhatsApp Cloud
    try:
        # tente achar 'wamid' em qualquer nível
        text = json.dumps(payload, ensure_ascii=False)
        # heurística simples
        if "wamid" in payload:
            return str(payload["wamid"])
        if '"wamid"' in text:
            # best-effort: pega o primeiro trecho depois de "wamid":
            import re
            m = re.search(r'"wamid"\s*:\s*"([^"]+)"', text)
            if m:
                return m.group(1)
    except Exception:
        pass
    # fallback
    from datetime import datetime
    return f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}"


# -----------------------------------------------------------------------------
# Healthcheck do blueprint (útil pra debug)
# -----------------------------------------------------------------------------
@webhook_bp.get("/status")
def webhook_status():
    return jsonify(scope="webhook", status="ok"), 200


# -----------------------------------------------------------------------------
# Verificação do Webhook (Meta) — GET /webhook?hub.*
# -----------------------------------------------------------------------------
@webhook_bp.get("")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")

    log.info("Verificando webhook (GET) | mode=%s", mode)

    if mode == "subscribe" and token == VERIFY_TOKEN:
        log.info("Webhook verificado com sucesso ✅")
        # deve responder o challenge puro como texto
        return (challenge or ""), 200

    log.warning("Verificação falhou ❌ | token inválido ou mode diferente")
    # Meta recomenda 403 em caso de token inválido
    return "Forbidden", 403


# -----------------------------------------------------------------------------
# Recebimento de eventos — POST /webhook
# -----------------------------------------------------------------------------
@webhook_bp.post("")
def receive():
    raw = request.get_data(as_text=True) or ""
    log.debug("POST /webhook | RAW(head)=%s", _shorten(raw, 600))

    # Parse robusto
    try:
        data: Dict[str, Any] = request.get_json(force=True, silent=False) or {}
    except Exception as e:
        log.error("Falha ao parsear JSON: %r", e, exc_info=False)
        # Responder 200 evita reentrega excessiva; devolve erro semanticamente no corpo
        return jsonify({"ok": False, "error": "invalid_json"}), 200

    log.debug("JSON topo keys=%s", list(data.keys()))

    # Cria/usa um request_id (deixa os logs encadeados bonitos p/ GIF)
    req_id = _extract_request_id(data)
    set_request_id(req_id)
    with with_request_id(req_id):
        try:
            handle_incoming_message = _import_handler()

            log.info("Evento recebido 📩 | request_id=%s", req_id)
            log.info("Processando → salvar no Google Sheets…")
            result = handle_incoming_message(data)

            # Esperado do handler: {"ok": True, "detail": "...", ...}
            log.info("Resultado do handler: %s", result.get("detail", "OK"))
            # Se o handler enviar e-mail, incentive um log lá também (status_email=sent)
            if result.get("ok"):
                log.info("Fluxo concluído ✅ (WhatsApp → Sheets → Email)")
            else:
                log.warning("Fluxo terminou com ok=False | result=%s", result)

            return jsonify(result), 200

        except Exception as e:
            # Mantemos 200 para não gerar storm de reentregas, mas informamos o erro no corpo
            log.exception("Erro no processamento do webhook")
            return jsonify({"ok": False, "error": str(e)}), 200