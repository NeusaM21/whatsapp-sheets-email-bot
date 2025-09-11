# whatsapp-sheets-email-bot — Guia Local (dev)

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.10+-blue?style=for-the-badge&logo=python"/>
  <img src="https://img.shields.io/badge/Flask-2.x-black?style=for-the-badge&logo=flask"/>
  <img src="https://img.shields.io/badge/Google%20Sheets-API-green?style=for-the-badge&logo=googlesheets"/>
  <img src="https://img.shields.io/badge/Gmail-SMTP-red?style=for-the-badge&logo=gmail"/>
  <img src="https://img.shields.io/badge/SQLite-Anti--Duplicados-lightgrey?style=for-the-badge&logo=sqlite"/>
  <img src="https://img.shields.io/badge/Logs-Enabled-orange?style=for-the-badge&logo=logstash"/>
  <img src="https://img.shields.io/badge/Deployment-Ready%20(roadmap)-purple?style=for-the-badge&logo=railway"/>
  <img src="https://img.shields.io/badge/Status-Local%20Only-yellow?style=for-the-badge"/>
</p>

---

## ⚡ Guia rápido

### Ativar ambiente
- **Windows (CMD):** `.venv\Scripts\activate`
- **Windows (PowerShell):** `& ".\.venv\Scripts\Activate.ps1"`
- **Linux/Mac:** `source .venv/bin/activate`

### Instalar dependências
`pip install gspread google-auth python-dotenv Flask waitress`

### Rodar scripts básicos
- Setup planilha: `python scripts\setup_sheet.py`
- Adicionar lead: `python scripts\append_lead.py`
- Adicionar + enviar e-mail: `python scripts\append_and_notify.py`

### Rodar webhook
`python scripts\webhook.py`  
- Healthcheck: `http://localhost:5000/` → `OK`  
- Endpoint: `http://localhost:5000/webhook`

### Abrir túnel (ngrok)
`ngrok http 5000` → use a URL pública no Meta Developers

> Para o manual completo, role 👇

---

## 🔄 Fluxo visual resumido

📱 WhatsApp (mensagem do cliente)
     │
     ▼
🌐 Webhook Flask (recebe evento do Meta)
     │
     ▼
📊 Google Sheets (salva lead e atualiza status)
     │
     ▼
✉️ E-mail (envio automático para equipe)
     │
     ▼
📝 Logs + Anti-duplicados (monitoramento e prevenção)

---

## 🧱 Estrutura do projeto (esperada)

whatsapp-sheets-email-bot/  
├─ .env  
├─ creds/  
│  └─ service-account.json  
├─ data/  
│  └─ state.db                  # criado automaticamente (anti-duplicados)  
├─ logs/  
│  └─ app.log                   # logs do webhook  
├─ scripts/  
│  ├─ setup_sheet.py  
│  ├─ append_lead.py  
│  ├─ send_email.py  
│  ├─ append_and_notify.py  
│  ├─ dedupe.py  
│  └─ webhook.py  
└─ .venv/                       # ambiente virtual  

---

## ✅ Pré-requisitos

- Python 3.10+ e `pip`
- Conta Google + **Google Cloud** com:
  - **Google Sheets API** e **Google Drive API** habilitadas
  - **Service Account** (arquivo JSON baixado)
- Conta **WhatsApp Cloud API** no Meta Developers (app em modo dev já serve)
- **Senha de app** no Gmail (para SMTP)

---

## 🔐 Configuração do `.env`

Colar na raiz (`whatsapp-sheets-email-bot/.env`):

# ---------------------------
# Flask / Servidor
# ---------------------------
PORT=5000
DEBUG=true

# ---------------------------
# WhatsApp Cloud API
# ---------------------------
WHATSAPP_VERIFY_TOKEN=um_token_bem_forte_aqui   # usado na verificação do webhook
WHATSAPP_TOKEN=EAAGxxxxxxxxxxxxxxxxxxxxxxxx     # token real do Meta (para chamadas ativas se precisar)

# ---------------------------
# Google Sheets
# ---------------------------
GOOGLE_SERVICE_ACCOUNT_JSON=creds/service-account.json
SHEET_ID=1s_Wnma6jzxUiBYcxv-aWGA5hJsk34XXg8Rup4cBP25w   # ID da planilha (trecho entre /d/ e /edit)
SHEET_TAB=leads             # nome da aba (sem espaços/acentos é mais seguro)
SHARE_WITH_EMAIL=whatsapp.bot.teste@gmail.com   # service account precisa estar como EDITOR

# ---------------------------
# E-mail (SMTP / Gmail)
# ---------------------------
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=whatsapp.bot.teste@gmail.com
SMTP_PASS=pstsdanopjqtjpnw             # senha de app do Gmail (não a senha normal)
EMAIL_TO=whatsapp.bot.teste@gmail.com  # destino dos leads
EMAIL_SUBJECT=Novo lead do WhatsApp

# ---------------------------
# Opcional (personalização do e-mail)
# ---------------------------
EMAIL_LOGO_URL=   # pode colar aqui a URL de uma logo se quiser que apareça no topo do email

---

## 📦 Instalação de dependências

🖥️ **Windows (CMD)**  
python -m venv .venv  
.venv\Scripts\activate  
pip install gspread google-auth python-dotenv Flask waitress  

🖥️ **Windows (PowerShell)**  
python -m venv .venv  
& ".\.venv\Scripts\Activate.ps1"  
pip install gspread google-auth python-dotenv Flask waitress  

🐧 **Linux/Mac**  
python3 -m venv .venv  
source .venv/bin/activate  
pip install gspread google-auth python-dotenv Flask waitress  

---

## 🧪 Testes em camadas

### 1) Sheets — criar aba e cabeçalhos 
python scripts\setup_sheet.py  
Esperado: `✅ Planilha OK! Worksheet='leads' pronta com cabeçalhos.`

### 2) Sheets — inserir lead manual
python scripts\append_lead.py  
Esperado: `✅ Lead adicionado com sucesso!` (confira a planilha)

### 3) E-mail — inserir e enviar
python scripts\append_and_notify.py  
Esperado:  
- `✅ Lead adicionado com sucesso!`  
- `📧 Email enviado!`  
- `📝 status_email atualizado para 'enviado' na linha X`

---

## 🌐 Webhook Flask (WhatsApp Cloud API)

### 1) Subir o servidor local
python scripts\webhook.py  

Acessos úteis:  
- Healthcheck: `http://localhost:5000/` → `OK`  
- Webhook: `http://localhost:5000/webhook` (GET para verificação / POST para eventos)

### 2) Abrir túnel HTTPS (ngrok)
ngrok http 5000  
Copie a **URL pública** do ngrok, ex.: `https://abc123.ngrok.io`.

### 3) Configurar no Meta (Developers)
No app → **WhatsApp → Configuration**:  
- **Webhook URL**: `https://abc123.ngrok.io/webhook`  
- **Verify Token**: o mesmo do `.env` (WHATSAPP_VERIFY_TOKEN)  
- **Verify and Save**  
- Em **Webhook Fields → Manage**: marque **messages**

### 4) Testes

**Verificação manual (GET):**  
curl -X GET "https://abc123.ngrok.io/webhook?hub.mode=subscribe&hub.verify_token=um_token_bem_forte_aqui&hub.challenge=123"  
Resposta esperada: `123`.

**Simular payload local (POST):**

🖥️ **Windows (PowerShell/CMD)**  
curl -X POST "http://localhost:5000/webhook" ^  
  -H "Content-Type: application/json" ^  
  -d "{\"entry\":[{\"changes\":[{\"value\":{\"messages\":[{\"id\":\"wamid.TESTE123\",\"from\":\"5511999999999\",\"text\":{\"body\":\"Olá, quero orçamento\"}}],\"contacts\":[{\"profile\":{\"name\":\"Maria Teste\"}}]}]}]}]}"

🐧 **Linux/Mac (bash/zsh)**  
curl -X POST "http://localhost:5000/webhook" \  
  -H "Content-Type: application/json" \  
  -d '{"entry":[{"changes":[{"value":{"messages":[{"id":"wamid.TESTE123","from":"5511999999999","text":{"body":"Olá, quero orçamento"}}],"contacts":[{"profile":{"name":"Maria Teste"}}]}}]}]}'

Resultado: novo lead no Sheets + e-mail + `status_email = enviado`.

**Log do webhook:**  
- Em tempo real no terminal  
- Arquivo: `logs/app.log`

---

## 🧠 Anti-duplicados

- Implementado em `scripts/dedupe.py` via SQLite (`data/state.db`).  
- Usa `message.id` do WhatsApp como chave (TTL padrão 24h).  
- Mensagens repetidas no período são ignoradas (`duplicate_ignored`).  

---

## ✉️ E-mail com botão “Responder no WhatsApp”

- O e-mail inclui um botão com link `https://wa.me/55XXXXXXXXXXX` (normalizado).  
- Para exibir uma logo no topo, defina `EMAIL_LOGO_URL` no `.env`.  

---

## 🧯 Problemas comuns (e correções)

- **403 (Sheets API desabilitada)**  
  → Habilite **Google Sheets API** e **Google Drive API** no mesmo projeto do `service-account.json`.

- **SpreadsheetNotFound / PermissionError**  
  → Compartilhe a planilha com o **`client_email`** da service account como **Editor**.

- **`Faltam variáveis no .env para SMTP/EMAIL_TO`**  
  → Preencha `SMTP_HOST/PORT/USER/PASS` e `EMAIL_TO`.  
  → **SMTP_PASS** deve ser **senha de app** do Gmail (Conta Google → Segurança → Senhas de app).

- **E-mail não chega**  
  → Checar caixa de spam, senha de app correta, e porta 587 com STARTTLS.

- **ngrok não acessa**  
  → Garanta que o Flask rodou (`http://localhost:5000`) antes do `ngrok http 5000`.

---

## 🧩 Comandos úteis

🖥️ **Windows (CMD)**  
.venv\Scripts\activate  

🖥️ **Windows (PowerShell)**  
& ".\.venv\Scripts\Activate.ps1"  

🐧 **Linux/Mac**  
source .venv/bin/activate  

### Scripts
python scripts\setup_sheet.py  
python scripts\append_lead.py  
python scripts\append_and_notify.py  

### Rodar webhook
python scripts\webhook.py  

### Ver logs
type .\logs\app.log   (Windows)  
cat ./logs/app.log    (Linux/Mac)

---

## 🗺️ Roadmap (quando quiser)

- Resposta ativa no WhatsApp (enviar mensagem automática usando `WHATSAPP_TOKEN`)  
- Filtro anti-duplicados por telefone + janela de tempo  
- Deploy (Railway/Render/VPS) usando `waitress`  
- Painel simples (HTML) pra listar últimos leads  

---

**Status atual**: ✅ Sheets OK | ✅ E-mail OK | ✅ Webhook pronto | ✅ Anti-duplicados | ✅ Logs  
Qualquer ajuste, anota aqui no README e seguimos o baile. 🚀

---

## 👩‍💻 Autora & Contato

**Autora:** [NeusaM21](https://github.com/NeusaM21)  
**Contato:** [contact.neusam21@gmail.com](mailto:contact.neusam21@gmail.com)