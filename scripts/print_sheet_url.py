# FILE: scripts/print_sheet_url.py
from __future__ import annotations

# Import resiliente: funciona rodando como módulo (-m) ou como arquivo direto
try:
    from scripts.sheets_repo import get_sheet
except ModuleNotFoundError:
    import os, sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))  # adiciona ./scripts
    from sheets_repo import get_sheet  # fallback quando rodado direto

def main() -> None:
    ws = get_sheet()
    sh = ws.spreadsheet
    url = getattr(sh, "url", f"https://docs.google.com/spreadsheets/d/{sh.id}")
    print("===================================")
    print(" Planilha REAL em uso pelo bot")
    print("-----------------------------------")
    print(" URL        :", url)
    print(" Spreadsheet:", sh.title)
    print(" Worksheet  :", ws.title)
    print("===================================")

if __name__ == "__main__":
    main()