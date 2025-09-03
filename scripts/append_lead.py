# FILE: scripts/append_lead.py
from __future__ import annotations
import os
from datetime import datetime
import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv

def get_ws():
    load_dotenv()
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_file(
        os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON"),
        scopes=scopes
    )
    gc = gspread.authorize(creds)
    sh = gc.open_by_key(os.getenv("SHEET_ID"))
    return sh.worksheet(os.getenv("WORKSHEET_NAME", "leads"))

def append_lead(nome: str, telefone: str, mensagem: str, origem: str = "whatsapp") -> int:
    ws = get_ws()
    # Quantas linhas já existem na coluna A (timestamp)? Header ocupa a linha 1.
    count_before = len(ws.col_values(1))  # A coluna A
    row_index = count_before + 1          # próxima linha onde o append vai cair

    row = [
        datetime.now().isoformat(timespec="seconds"),
        nome,
        telefone,
        mensagem,
        origem,
        "pendente"
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")
    print("✅ Lead adicionado com sucesso!")
    return row_index  # devolve a linha em que foi inserido

if __name__ == "__main__":
    append_lead("Teste Bot", "+55 11 99999-9999", "Quero saber preços", "whatsapp")