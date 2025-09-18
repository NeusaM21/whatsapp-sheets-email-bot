# FILE: scripts/logging_setup.py
# -*- coding: utf-8 -*-
"""
Logger plugável para whatsapp-sheets-email-bot.

.env suportado:
  LOG_LEVEL=DEBUG|INFO|WARNING|ERROR|CRITICAL   (default: INFO)
  LOG_JSON=1                                     (opcional: logs em JSON)
  LOG_COLOR=1                                    (opcional: cores ANSI no console quando não for JSON)
  LOG_FILE=logs/app.log                          (opcional: salva também em arquivo)
  TZ=America/Sao_Paulo                           (informativo; usa timezone do SO)

Recursos:
  - idempotente (não duplica handlers)
  - timestamp local ISO-8601
  - formato texto simples (compatível com PowerShell, CMD, bash) ou JSON
  - cores ANSI opcionais
  - filtro de request_id via contextvars (set_request_id/with_request_id)
"""

from __future__ import annotations

import contextlib
import contextvars
import datetime as _dt
import json
import logging
import os
import sys
from typing import Optional, Dict, Any, Iterator

# -----------------------------------------------------------------------------
# Contexto: request_id global
# -----------------------------------------------------------------------------
_request_id_ctx: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")

def set_request_id(req_id: str) -> None:
    """Define o request_id corrente (exibido se o formatter usar)."""
    _request_id_ctx.set(str(req_id))

@contextlib.contextmanager
def with_request_id(req_id: str) -> Iterator[None]:
    """Context manager para logs com request_id temporário."""
    token = _request_id_ctx.set(str(req_id))
    try:
        yield
    finally:
        _request_id_ctx.reset(token)

class _RequestIdFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "request_id"):
            record.request_id = _request_id_ctx.get()
        return True

# -----------------------------------------------------------------------------
# Formatters
# -----------------------------------------------------------------------------
class _TzFormatter(logging.Formatter):
    """Formatter padrão com timestamp local ISO8601."""
    def formatTime(self, record: logging.LogRecord, datefmt: Optional[str] = None) -> str:
        dt = _dt.datetime.fromtimestamp(record.created).astimezone()
        return dt.isoformat(timespec="seconds")

# Cores por nível (ANSI)
_LEVEL_COLORS = {
    "DEBUG": "\033[36m",    # ciano
    "INFO": "\033[32m",     # verde
    "WARNING": "\033[33m",  # amarelo
    "ERROR": "\033[31m",    # vermelho
    "CRITICAL": "\033[35m", # magenta
}
_RESET = "\033[0m"

def _maybe_enable_windows_ansi() -> None:
    """Melhora suporte a ANSI no Windows 10+ (ignora se falhar)."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass

class _ColorFormatter(_TzFormatter):
    def format(self, record: logging.LogRecord) -> str:
        level = record.levelname.upper()
        color = _LEVEL_COLORS.get(level, "")
        if color:
            record.levelname = f"{color}{record.levelname}{_RESET}"
        return super().format(record)

class _JsonFormatter(logging.Formatter):
    """Formatter JSON enxuto e estável."""
    def format(self, record: logging.LogRecord) -> str:
        dt = _dt.datetime.fromtimestamp(record.created).astimezone().isoformat(timespec="seconds")
        payload: Dict[str, Any] = {
            "ts": dt,
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": getattr(record, "request_id", _request_id_ctx.get()),
            "path": record.pathname,
            "line": record.lineno,
            "func": record.funcName,
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)

# -----------------------------------------------------------------------------
# Setup (idempotente)
# -----------------------------------------------------------------------------
def _as_bool(val: Optional[str], default: bool = False) -> bool:
    if val is None:
        return default
    return str(val).strip().lower() in ("1", "true", "yes", "on")

def _level_from_env() -> int:
    lvl = os.getenv("LOG_LEVEL", "INFO").upper().strip()
    return {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }.get(lvl, logging.INFO)

def setup_logger(name: str = "whatsapp-sheets-email-bot") -> logging.Logger:
    """
    Cria/retorna um logger configurado.
    - Não duplica handlers em chamadas repetidas.
    - Respeita LOG_LEVEL/LOG_JSON/LOG_COLOR/LOG_FILE.
    """
    logger = logging.getLogger(name)
    level = _level_from_env()
    logger.setLevel(level)
    logger.propagate = False

    # Se já tem handlers, só atualiza o nível e retorna
    if logger.handlers:
        for h in logger.handlers:
            h.setLevel(level)
        return logger

    use_json  = _as_bool(os.getenv("LOG_JSON"))
    use_color = _as_bool(os.getenv("LOG_COLOR"))
    log_file  = os.getenv("LOG_FILE")

    # Filtro de request_id
    req_filter = _RequestIdFilter()

    # Console handler
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)

    # Base format “powershell-friendly” (sem colchetes)
    text_fmt = "%(asctime)s | %(levelname)-8s | %(message)s"

    if use_json:
        fmt = _JsonFormatter()
    else:
        if use_color:
            _maybe_enable_windows_ansi()
            fmt = _ColorFormatter(text_fmt)
        else:
            fmt = _TzFormatter(text_fmt)

    console.setFormatter(fmt)
    console.addFilter(req_filter)
    logger.addHandler(console)

    # File handler (opcional)
    if log_file:
        try:
            folder = os.path.dirname(log_file)
            if folder:
                os.makedirs(folder, exist_ok=True)
        except Exception:
            pass
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setLevel(level)
        fh.setFormatter(_JsonFormatter() if use_json else _TzFormatter(text_fmt))
        fh.addFilter(req_filter)
        logger.addHandler(fh)

    return logger

# -----------------------------------------------------------------------------
# Execução direta (smoke test)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    log = setup_logger()
    set_request_id("DEMO-1234")
    log.debug("debug ligado?")
    log.info("logger pronto e feliz 😎")
    log.warning("isso é só um smoke test")
    try:
        1 / 0
    except Exception:
        log.exception("exemplo de exceção capturada")