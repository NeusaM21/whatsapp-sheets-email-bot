import os, yagmail
from dotenv import load_dotenv

load_dotenv()
EMAIL_FROM = os.getenv("EMAIL_FROM")
EMAIL_APP_PASSWORD = os.getenv("EMAIL_APP_PASSWORD")

to = EMAIL_FROM
subject = "Teste do whatsapp-sheets-email-bot"
body = "Se chegou, as credenciais de e-mail estão ok. 🚀"

yag = yagmail.SMTP(EMAIL_FROM, EMAIL_APP_PASSWORD)
yag.send(to=to, subject=subject, contents=body)
print("E-mail de teste enviado.")