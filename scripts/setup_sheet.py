# FILE: scripts/setup_sheet.py
from __future__ import annotations

import os
import sys
from dotenv import load_dotenv

# Reaproveita a lógica central de Sheets do projeto
from .sheets_repo import get_sheet, ensure_headers, HEADERS

load_dotenv(override=True)


def _require_env(name: str) -> str:
    """Busca variável obrigatória do .env e falha com mensagem clara se faltar."""
    val = os.getenv(name)
    if not val or not str(val).strip():
        raise RuntimeError(f"Variável de ambiente obrigatória ausente: {name}")
    return str(val).strip()


def main() -> None:
    # Lê as variáveis padronizadas (coerentes com o resto do projeto)
    spreadsheet_name = _require_env("GOOGLE_SHEETS_SPREADSHEET_NAME")
    worksheet_name = _require_env("GOOGLE_SHEETS_WORKSHEET")

    # Caminho do JSON (checagem extra, mensagem amigável)
    sa_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    if not sa_path:
        raise RuntimeError(
            "GOOGLE_SERVICE_ACCOUNT_JSON não definido no .env. "
            "Ex.: GOOGLE_SERVICE_ACCOUNT_JSON=./creds/service-account.json"
        )
    if not os.path.exists(sa_path):
        raise FileNotFoundError(
            f"Arquivo de credenciais não encontrado: {sa_path}\n"
            "→ Coloque o service-account.json no caminho informado "
            "ou ajuste a variável GOOGLE_SERVICE_ACCOUNT_JSON."
        )

    # Abre/cria planilha e worksheet
    ws = get_sheet()  # já usa as envs acima internamente
    ensure_headers(ws)  # garante: timestamp | wamid | from | name | body

    # Infos úteis
    sh = ws.spreadsheet
    url = getattr(sh, "url", None) or f"https://docs.google.com/spreadsheets/d/{sh.id}"

    print("===============================================")
    print("[OK] Planilha pronta para uso!")
    print(f" Spreadsheet : {sh.title}")
    print(f" Worksheet   : {ws.title}")
    print(f" URL         : {url}")
    print("-----------------------------------------------")
    print(" Cabeçalho   :", " | ".join(HEADERS))
    print(" Dica: Fixe a primeira linha no Google Sheets (Exibir → Congelar → 1 linha).")
    print("===============================================")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        # Mensagem clara + código de saída ≠ 0 para CI/scripts
        print(f"[ERRO] {e}", file=sys.stderr)
        sys.exit(1)