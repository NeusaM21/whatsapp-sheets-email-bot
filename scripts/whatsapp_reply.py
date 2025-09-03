# FILE: scripts/whatsapp_reply.py
from __future__ import annotations
import os
import requests
from typing import Tuple

WABA_PHONE_ID = os.getenv("WABA_PHONE_ID", "")
WABA_ACCESS_TOKEN = os.getenv("WABA_ACCESS_TOKEN", "")

def send_whatsapp_text(to_phone_e164: str, body: str) -> Tuple[bool, str]:
    """
    Envia uma mensagem de texto simples via WhatsApp Cloud API.
    `to_phone_e164` ex: "5511987654321"
    """
    if not (WABA_PHONE_ID and WABA_ACCESS_TOKEN):
        return False, "missing WABA_PHONE_ID/WABA_ACCESS_TOKEN"

    url = f"https://graph.facebook.com/v20.0/{WABA_PHONE_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WABA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": to_phone_e164,
        "type": "text",
        "text": {"body": body[:1024]},
    }
    try:
        r = requests.post(url, headers=headers, json=payload, timeout=15)
        if r.status_code // 100 == 2:
            return True, "sent"
        return False, f"error:{r.status_code} {r.text[:200]}"
    except Exception as e:
        return False, f"error:{e}"