# FILE: scripts/share_sheet.py
from __future__ import annotations

import os
from dotenv import load_dotenv
from scripts.sheets_repo import get_sheet

load_dotenv(override=True)

def main() -> None:
    target = os.getenv("SHARE_WITH_EMAIL", "").strip()
    role = os.getenv("SHARE_WITH_ROLE", "writer").strip()  # reader | commenter | writer
    notify = os.getenv("SHARE_SEND_NOTIFICATION_EMAIL", "1").strip() == "1"

    if not target:
        raise SystemExit(
            "Defina SHARE_WITH_EMAIL=<seu_email@gmail.com> no .env para compartilhar."
        )

    ws = get_sheet()
    sh = ws.spreadsheet
    url = getattr(sh, "url", f"https://docs.google.com/spreadsheets/d/{sh.id}")

    # Importante: 'perm_type' pode ser 'user' (email) ou 'domain' (domínio inteiro)
    sh.share(
        email_address=target,
        perm_type="user",
        role=role,
        notify=notify,
    )

    print("===================================")
    print(f"[OK] Compartilhado com: {target}")
    print(f"     Permissão: {role}")
    print(f"     Notificar por e-mail: {notify}")
    print("-----------------------------------")
    print(" URL da planilha:", url)
    print("===================================")

if __name__ == "__main__":
    main()