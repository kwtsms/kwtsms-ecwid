"""Structured logging with database and console output."""

import json
import logging
from datetime import datetime, timezone

# Sensitive keys to redact
_SENSITIVE_KEYS = {"password", "secret", "token", "credential", "encryption_key", "api_key"}


def _redact_dict(data: dict) -> dict:
    """Redact sensitive values from a dict."""
    redacted = {}
    for k, v in data.items():
        if any(s in k.lower() for s in _SENSITIVE_KEYS):
            redacted[k] = "***"
        elif isinstance(v, dict):
            redacted[k] = _redact_dict(v)
        else:
            redacted[k] = v
    return redacted


class PluginLogger:
    """Logger that writes to console and optionally to the debug_log database table."""

    def __init__(self, module_name: str):
        self.module_name = module_name
        self._logger = logging.getLogger(f"kwtsms.{module_name}")
        if not self._logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(
                logging.Formatter("[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
            )
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)

    def _format_details(self, details) -> str | None:
        if details is None:
            return None
        if isinstance(details, dict):
            return json.dumps(_redact_dict(details))
        return str(details)

    async def _write_to_db(self, level: str, message: str, details=None):
        """Write a log entry to the debug_log table."""
        try:
            from app.database import execute_query

            await execute_query(
                "INSERT INTO debug_log (created_at, level, module, message, details) "
                "VALUES (datetime('now'), ?, ?, ?, ?)",
                (level, self.module_name, message, self._format_details(details)),
            )
        except Exception:
            # Don't let logging failures crash the app
            pass

    def debug(self, msg: str, details=None):
        self._logger.debug(msg)
        return self._write_to_db("DEBUG", msg, details)

    def info(self, msg: str, details=None):
        self._logger.info(msg)
        return self._write_to_db("INFO", msg, details)

    def warning(self, msg: str, details=None):
        self._logger.warning(msg)
        return self._write_to_db("WARNING", msg, details)

    def error(self, msg: str, details=None):
        self._logger.error(msg)
        return self._write_to_db("ERROR", msg, details)


def get_logger(module_name: str) -> PluginLogger:
    """Get a logger instance for the given module."""
    return PluginLogger(module_name)
