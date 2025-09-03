# FILE: scripts/list_sheets.py
from __future__ import annotations
import gspread, os, pathlib
from dotenv import load_dotenv

# carrega o .env (pra pegar GOOGLE_SERVICE_ACCOUNT_JSON etc.)
load_dotenv(override=True)


def client() -> gspread.Client:
    sa = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    alt = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    if sa and pathlib.Path(sa).exists():
        return gspread.service_account(filename=sa)
    if alt and pathlib.Path(alt).exists():
        return gspread.service_account(filename=alt)
    return gspread.service_account()


def main():
    gc = client()
    sheets = gc.openall()  # retorna todas as planilhas visíveis para a SA

    if not sheets:
        print("[!] Nenhuma planilha visível para esta Service Account.")
        print("→ Compartilhe a planilha dos testes com o client_email da SA (Editor).")
        return

    print("=== Spreadsheets visíveis pela Service Account ===")
    for sh in sheets:
        url = getattr(sh, "url", f"https://docs.google.com/spreadsheets/d/{sh.id}")
        print(f"- {sh.title} | ID: {sh.id}\n  {url}")
    print("==================================================")


if __name__ == "__main__":
    main()