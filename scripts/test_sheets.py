# FILE: scripts/test_sheets.py
from __future__ import annotations
import time
from dotenv import load_dotenv
load_dotenv()

from scripts.sheets_repo import SheetsRepo

if __name__ == "__main__":
    print("=== Testando conexão e append no Google Sheets ===")
    repo = SheetsRepo()
    wamid = f"wamid.TEST_{int(time.time())}"
    lead = {
        "nome": "Teste Manual",
        "telefone": "5511999999999",
        "mensagem": "Lead de teste rodando test_sheets.py",
        "origem": "whatsapp",
        "status_email": "pendente",
        "wamid": wamid,
    }
    try:
        result = repo.append_lead(lead)
        print("Resultado:", result)
        if result.get("saved"):
            print("OK: Linha criada.")
        else:
            print("Info: não salvou (duplicado?).")
    except Exception as e:
        print("ERRO:", e)