# -*- coding: utf-8 -*-
import json
from scripts.append_and_notify import _extract_payload

data = {
  "object": "whatsapp_business_account",
  "entry": [{
    "id": "WABA_ID_TESTE",
    "changes": [{
      "field": "messages",
      "value": {
        "messaging_product": "whatsapp",
        "metadata": {
          "display_phone_number": "55 11 99999-9999",
          "phone_number_id": "PNID_TESTE"
        },
        "contacts": [{
          "profile": {"name": "Maria Teste"},
          "wa_id": "5511999999"
        }],
        "messages": [{
          "id": "wamid.TESTE123",
          "from": "5511999999",
          "text": {"body": "Olá, quero orçamento"},
          "type": "text"
        }]
      }
    }]
  }]
}

print(_extract_payload(data))
