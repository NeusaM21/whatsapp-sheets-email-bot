# FILE: scripts/mailer.py
# -*- coding: utf-8 -*-
"""
Mailer plugável (SMTP) para whatsapp-sheets-email-bot.

• Controlado por .env:
  - EMAIL_ENABLED (1/0)
  - EMAIL_DRY_RUN (1/0)
  - SMTP_HOST, SMTP_PORT, SMTP_TLS, SMTP_SSL, SMTP_USER, SMTP_PASS, SMTP_FROM, SMTP_TO_DEFAULT
  - SMTP_TIMEOUT (segundos, opcional; padrão 10)

• Recursos:
  - DRY-RUN (não envia de verdade, só retorna status)
  - TLS (STARTTLS) ou SSL puro (porta 465)
  - Fallback de texto simples a partir do HTML
  - Logs bonitos se scripts.logging_setup existir
  - Retorno estruturado para exibir no console/README

Uso típico:
    from scripts.mailer import send_email
    result = send_email(None, "Novo lead", "<b>Chegou!</b>")
    # 'to' None → usa SMTP_TO_DEFAULT
"""

from __future__ import annotations

import os
import re
import smtplib
import ssl
from typing import Optional, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# logger preguiçoso (só inicializa se disponível)
_LOGGER = None


def _bool(v: Optional[str]) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "on")


def _first_nonempty(*vals: Optional[str]) -> str:
    for v in vals:
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _plaintext_from_html(html: str) -> str:
    # remove tags simples e normaliza espaços — suficiente p/ fallback
    text = re.sub(r"<\s*br\s*/?\s*>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<\s*/p\s*>", "\n\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _log(level: str, msg: str):
    global _LOGGER
    try:
        if _LOGGER is None:
            from scripts.logging_setup import setup_logger  # opcional
            _LOGGER = setup_logger()
    except Exception:
        _LOGGER = None

    if _LOGGER:
        # prefixo ✉️ para destacar eventos de e-mail nos logs
        line = f"✉️  {msg}"
        if hasattr(_LOGGER, level):
            getattr(_LOGGER, level)(line)
        else:
            _LOGGER.info(line)


def _cfg() -> Dict[str, Any]:
    return {
        "enabled": _bool(os.getenv("EMAIL_ENABLED")),
        "dry": _bool(os.getenv("EMAIL_DRY_RUN")),
        "host": os.getenv("SMTP_HOST", ""),
        "port": int(os.getenv("SMTP_PORT", "587")),
        "user": os.getenv("SMTP_USER", ""),
        "password": os.getenv("SMTP_PASS", ""),
        "from_addr": os.getenv("SMTP_FROM", os.getenv("SMTP_USER", "")),
        "to_default": os.getenv("SMTP_TO_DEFAULT", ""),
        "tls": _bool(os.getenv("SMTP_TLS", "1")),         # STARTTLS (padrão)
        "use_ssl": _bool(os.getenv("SMTP_SSL", "0")),     # SSL puro (465)
        "timeout": int(os.getenv("SMTP_TIMEOUT", "10")),  # segundos
    }


def validate_smtp_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Valida config mínima para envio real (ignora se for dry-run)."""
    issues = []
    required = ("host", "port", "from_addr")
    for k in required:
        if not cfg.get(k):
            issues.append(f"faltando SMTP_{k.upper() if k != 'from_addr' else 'FROM'}")

    # Se há user, precisa de password (e vice-versa)
    if (cfg.get("user") and not cfg.get("password")) or (cfg.get("password") and not cfg.get("user")):
        issues.append("SMTP_USER/SMTP_PASS incompletos")

    return {"ok": len(issues) == 0, "issues": issues}


def send_email(
    to: Optional[str],
    subject: str,
    html: str,
    text: Optional[str] = None,
    *,
    cc: Optional[str] = None,
    bcc: Optional[str] = None,
    dry_run: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Envia e-mail via SMTP conforme .env.
    Retorna dict com status: disabled | skip | dry-run | sent | error
    """
    cfg = _cfg()
    if not cfg["enabled"]:
        _log("info", "envio desativado (EMAIL_ENABLED=0)")
        return {"status": "disabled"}

    to_addr = _first_nonempty(to, cfg["to_default"])
    if not to_addr:
        _log("info", "sem destinatário (lead sem e-mail e SMTP_TO_DEFAULT vazio)")
        return {"status": "skip", "reason": "no_to"}

    if dry_run is None:
        dry_run = cfg["dry"]

    # Construção da mensagem (multipart/alternative)
    plaintext = text or _plaintext_from_html(html)
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = cfg["from_addr"]
    msg["To"] = to_addr
    if cc:
        msg["Cc"] = cc

    msg.attach(MIMEText(plaintext, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Lista real de destinatários (To + Cc + Bcc)
    recipients = [to_addr]
    if cc:
        recipients += [r.strip() for r in cc.split(",") if r.strip()]
    if bcc:
        recipients += [r.strip() for r in bcc.split(",") if r.strip()]

    # DRY-RUN: não conecta no SMTP
    if dry_run:
        _log("info", f"DRY-RUN | to={to_addr} | subject={subject}")
        return {
            "status": "dry-run",
            "to": to_addr,
            "cc": cc,
            "bcc": bcc,
            "subject": subject,
        }

    # Validação para envio real
    v = validate_smtp_cfg(cfg)
    if not v["ok"]:
        _log("error", f"configuração SMTP inválida: {', '.join(v['issues'])}")
        return {"status": "error", "error": "invalid_config", "issues": v["issues"]}

    try:
        # SSL puro (porta 465) ou STARTTLS
        if cfg["use_ssl"] or cfg["port"] == 465:
            context = ssl.create_default_context()
            with smtplib.SMTP_SSL(cfg["host"], cfg["port"], context=context, timeout=cfg["timeout"]) as server:
                if cfg["user"]:
                    server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_addr"], recipients, msg.as_string())
        else:
            with smtplib.SMTP(cfg["host"], cfg["port"], timeout=cfg["timeout"]) as server:
                if cfg["tls"]:
                    server.starttls(context=ssl.create_default_context())
                if cfg["user"]:
                    server.login(cfg["user"], cfg["password"])
                server.sendmail(cfg["from_addr"], recipients, msg.as_string())

        _log("info", f"enviado | to={to_addr} | subject={subject}")
        return {"status": "sent", "to": to_addr, "subject": subject, "recipients": recipients}

    except Exception as e:
        _log("error", f"falha ao enviar: {e.__class__.__name__}: {e}")
        return {"status": "error", "type": e.__class__.__name__, "error": str(e)}


__all__ = ["send_email", "validate_smtp_cfg"]