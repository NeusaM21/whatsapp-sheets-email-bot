# FILE: app.py
from __future__ import annotations

import os
import logging
from typing import Any, Dict

from dotenv import load_dotenv
from flask import Flask, request, jsonify, send_from_directory

# -----------------------------------------------------------------------------
# ENV
# -----------------------------------------------------------------------------
load_dotenv(override=True)

# -----------------------------------------------------------------------------
# Logger
# -----------------------------------------------------------------------------
try:
    from scripts.logging_setup import setup_logger
    log = setup_logger()
except Exception:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    log = logging.getLogger("whatsapp-sheets-email-bot")
    log.propagate = False

# -----------------------------------------------------------------------------
# Flask app & config
# -----------------------------------------------------------------------------
app = Flask(__name__, static_folder="static")

ENV = (os.getenv("ENV", "dev") or "dev").lower()
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
DEBUG = ENV != "prod"

# Pipeline: append + e-mail + marcar status
from scripts.append_and_notify import process_incoming  # noqa: E402

# -----------------------------------------------------------------------------
# Rotas básicas
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def home():
    return jsonify({
        "status": "ok",
        "service": "whatsapp-sheets-email-bot",
        "hint": "use /status (GET) e /webhook (GET verify | POST eventos)"
    }), 200


@app.route("/status", methods=["GET"])
def status():
    return jsonify({
        "status": "ok",
        "service": "whatsapp-sheets-email-bot",
        "env": ENV,
    }), 200


@app.route("/static/<path:filename>", methods=["GET"])
def static_files(filename: str):
    return send_from_directory(app.static_folder, filename)

# -----------------------------------------------------------------------------
# Webhook (Meta)
# -----------------------------------------------------------------------------
@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    # GET: verificação (hub.challenge)
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")
        expected = os.getenv("VERIFY_TOKEN", "")

        if mode == "subscribe" and expected and token == expected:
            log.info("Webhook verificado (GET /webhook).")
            return (challenge or ""), 200

        if mode:
            # veio tentativa de verificação mas token não bateu
            return "Forbidden", 403

        # Dev/local: dica de uso
        return jsonify({"ok": True, "hint": "POST your WhatsApp webhook payload here"}), 200

    # POST: delega tudo ao pipeline process_incoming
    try:
        payload: Dict[str, Any] = request.get_json(force=True, silent=True) or {}
        log.info("POST /webhook recebido")
        result = process_incoming(payload)
        return jsonify(result), 200
    except Exception as e:
        log.exception("Erro no process_incoming: %s", e)
        return jsonify({"status": "error", "error": "internal", "detail": str(e)}), 500


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    log.info(
        "Subindo serviço %s | env=%s | http://%s:%s",
        "whatsapp-sheets-email-bot", ENV, HOST, PORT
    )
    app.run(debug=DEBUG, host=HOST, port=PORT)