# FILE: scripts/print_sheet_link.py
from __future__ import annotations
import os
from dotenv import load_dotenv
load_dotenv()

from scripts.sheets_repo import SheetsRepo

if __name__ == "__main__":
    repo = SheetsRepo()
    repo._ensure_client()
    ws = repo._ws  # worksheet já aberto pela tab do .env
    gid = ws.id
    sheet_id = repo.sheet_id
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit#gid={gid}"
    print("Planilha:", sheet_id)
    print("Aba:", repo.tab_name, "gid:", gid)
    print("LINK EXATO:", url)