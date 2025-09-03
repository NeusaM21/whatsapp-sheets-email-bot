# webhook.py
from __future__ import annotations
import os
import sys
import json
from importlib import import_module
import importlib.util
from pathlib import Path
from flask import Blueprint, request, jsonify

# ------------------------------------------------------
# Config
# ------------------------------------------------------
VERIFY_TOKEN: str = os.getenv("WHATSAPP_VERIFY_TOKEN", "um_token_bem_forte_aqui")

# url_prefix = "/webhook" → rotas ficam /webhook (GET/POST) e /webhook/status (GET)
webhook_bp = Blueprint("webhook", __name__, url_prefix="/webhook")

# ------------------------------------------------------
# Healthcheck do blueprint (útil pra debug)
# ------------------------------------------------------
@webhook_bp.get("/status")
def webhook_status():
    return jsonify(scope="webhook", status="ok"), 200

# ------------------------------------------------------
# Verificação do Webhook (Meta) — GET /webhook?hub.*
# ------------------------------------------------------
@webhook_bp.get("")
def verify():
    mode = request.args.get("hub.mode")
    token = request.args.get("hub.verify_token")
    challenge = request.args.get("hub.challenge")
    if mode == "subscribe" and token == VERIFY_TOKEN:
        # responde exatamente o challenge como string
        return challenge or "", 200
    return "Forbidden", 403

# ------------------------------------------------------
# Recebimento de eventos — POST /webhook
# ------------------------------------------------------
@webhook_bp.post("")
def receive():
    # Log do corpo cru
    raw = request.get_data(as_text=True)
    print("[DEBUG] [BP] RAW BODY (head):", (raw or "")[:1200], "...\n")

    # Parse robusto
    try:
        data = request.get_json(force=True, silent=False) or {}
    except Exception as e:
        print("[DEBUG] [BP] get_json ERROR:", e)
        data = {}

    print("[DEBUG] [BP] JSON keys topo:", list(data.keys()))

    try:
        # tenta importar o handler na raiz
        try:
            from scripts.append_and_notify import handle_incoming_message as _him
            mod_file = sys.modules["append_and_notify"].__file__
            print("[DEBUG] [BP] usando handler de:", mod_file)
            handle_incoming_message = _him
        except ModuleNotFoundError:
            # fallback: importa pelo caminho absoluto (raiz do projeto)
            mod_path = Path(__file__).with_name("append_and_notify.py")
            spec = importlib.util.spec_from_file_location("append_and_notify", str(mod_path))
            aan = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(aan)  # type: ignore
            print("[DEBUG] [BP] usando handler via caminho:", mod_path)
            handle_incoming_message = aan.handle_incoming_message

        result = handle_incoming_message(data)
        print("[DEBUG] [BP] RESULT:", result)
        return jsonify(result), 200

    except Exception as e:
        print(f"[ERRO] [BP] webhook POST:", e)
        return jsonify({"ok": False, "error": str(e)}), 200