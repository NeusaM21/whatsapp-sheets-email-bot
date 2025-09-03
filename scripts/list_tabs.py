from __future__ import annotations
import os, pathlib, gspread
from dotenv import load_dotenv
load_dotenv(override=True)

def client():
    sa = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    alt = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    if sa and pathlib.Path(sa).exists():
        return gspread.service_account(filename=sa)
    if alt and pathlib.Path(alt).exists():
        return gspread.service_account(filename=alt)
    return gspread.service_account()
def main():
    gc = client()
    name_or_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_NAME")
    sh = (gc.open_by_key(name_or_id) if (name_or_id and " " not in name_or_id and len(name_or_id) >= 20) else gc.open(name_or_id))
    print("Spreadsheet:", sh.title)
    print("Abas encontradas:")
    for ws in sh.worksheets():
        t = ws.title
        print(f"- '{t}' | len={len(t)} | ords={[ord(c) for c in t]}")
if __name__ == "__main__":
    main()
