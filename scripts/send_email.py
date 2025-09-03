# FILE: scripts/send_email.py
from __future__ import annotations

import os
import smtplib
from typing import Dict, List
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr

from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# Logger
# -----------------------------------------------------------------------------
try:
    from scripts.logging_setup import setup_logger
    log = setup_logger()
except Exception:
    import logging
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    log = logging.getLogger("send_email")
    log.propagate = False

# Carrega .env uma vez
load_dotenv(override=True)


def _flag(name: str, default: int = 0) -> bool:
    """Converte 1/true/on para bool."""
    return str(os.getenv(name, str(default))).strip().lower() in {"1", "true", "yes", "on"}


def _recipients_from_env_and_record(record: Dict) -> List[str]:
    """Monta lista de destinatários: EMAIL_TO + (opcional) e-mail do lead."""
    env_to = os.getenv("EMAIL_TO", "")
    recipients = [e.strip() for e in env_to.split(",") if e.strip()]

    lead_email = (record.get("email") or "").strip()
    if lead_email and "@" in lead_email:
        recipients.append(lead_email)

    # dedupe preservando ordem
    seen, uniq = set(), []
    for r in recipients:
        k = r.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    return uniq


def _smtp_send(subject: str, html_body: str, to_list: List[str]) -> bool:
    """Envia o e-mail de fato respeitando EMAIL_ENABLED/EMAIL_DRY_RUN e SMTP_*."""
    if not _flag("EMAIL_ENABLED", 0):
        log.info("EMAIL_ENABLED=0 — envio desativado. Pulando.")
        return True

    if not to_list:
        log.error("Nenhum destinatário (EMAIL_TO vazio e sem e-mail do lead).")
        return False

    host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    port = int(os.getenv("SMTP_PORT", "587"))
    use_tls = _flag("SMTP_TLS", 1)
    user = os.getenv("SMTP_USER", "")
    pwd = os.getenv("SMTP_PASS", "")

    email_from = os.getenv("EMAIL_FROM", user or "no-reply@example.com")

    # Mensagem multipart (texto + HTML)
    text_body = _strip_html(html_body)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    # se EMAIL_FROM tiver "Nome <email>", deixa como está; senão formata
    if "<" in email_from and ">" in email_from:
        msg["From"] = email_from
        from_addr = email_from[email_from.find("<") + 1 : email_from.find(">")]
    else:
        msg["From"] = formataddr(("Leads Bot", email_from))
        from_addr = email_from
    msg["To"] = ", ".join(to_list)
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    if _flag("EMAIL_DRY_RUN", 0):
        log.info("EMAIL_DRY_RUN=1 — não enviando. Assunto='%s' To=%s", subject, to_list)
        return True

    try:
        with smtplib.SMTP(host, port, timeout=20) as s:
            if use_tls:
                s.starttls()
            if user and pwd:
                s.login(user, pwd)
            s.sendmail(from_addr, to_list, msg.as_string())
        log.info("E-mail enviado com sucesso para %s", to_list)
        return True
    except Exception as e:
        log.exception("Falha ao enviar e-mail: %s", e)
        return False


def _strip_html(html: str) -> str:
    """Fallback simples de texto a partir do HTML (sem dependências)."""
    # troca <br> por quebras de linha e remove tags básicas
    text = html.replace("<br>", "\n").replace("<br/>", "\n").replace("<br />", "\n")
    for tag in ("<p>", "</p>", "<ul>", "</ul>", "<li>", "</li>", "<b>", "</b>", "<strong>", "</strong>"):
        text = text.replace(tag, "")
    # remove o resto das tags
    out, skip = [], False
    for ch in text:
        if ch == "<":
            skip = True
        elif ch == ">":
            skip = False
        elif not skip:
            out.append(ch)
    return "".join(out).strip()


# -----------------------------------------------------------------------------
# API pública
# -----------------------------------------------------------------------------
def send_lead_email(record: Dict) -> bool:
    """
    Envia e-mail de notificação de lead usando os placeholders do .env:
      EMAIL_SUBJECT = "[Lead WhatsApp] {name} — {phone}"
      EMAIL_TO      = "seu@email.com,outro@exemplo.com"
    Também inclui o e-mail do lead (record['email']) se existir/for válido.
    """
    subject_tpl = os.getenv("EMAIL_SUBJECT", "[Lead WhatsApp] {name} — {phone}")
    subject = subject_tpl.format(
        name=record.get("name", "(sem nome)"),
        phone=record.get("phone", "(sem phone)"),
    )

    html = (
        "<h2>Novo lead do WhatsApp</h2>"
        "<ul>"
        f"<li><b>Nome:</b> {record.get('name','')}</li>"
        f"<li><b>Telefone:</b> {record.get('phone','')}</li>"
        f"<li><b>E-mail:</b> {record.get('email','')}</li>"
        f"<li><b>Mensagem:</b> {str(record.get('message','')).replace(chr(10), '<br>')}</li>"
        f"<li><b>Origem:</b> {record.get('source','whatsapp')}</li>"
        f"<li><b>WAMID:</b> {record.get('wamid','')}</li>"
        "</ul>"
    )

    to_list = _recipients_from_env_and_record(record)
    return _smtp_send(subject, html, to_list)


# Compatibilidade com a versão antiga usada no projeto
def send_email(assunto: str, corpo_html: str, to_email: str | None = None) -> bool:
    """
    Versão genérica (legado). Se to_email for None, usa EMAIL_TO do .env.
    """
    env_to = os.getenv("EMAIL_TO", "")
    to_list = [to_email.strip()] if to_email else [e.strip() for e in env_to.split(",") if e.strip()]
    return _smtp_send(assunto, corpo_html, to_list)