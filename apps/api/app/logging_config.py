"""
Configuracion de logging estructurado para Fiscal Agent API.
Usa stdlib logging con formato JSON-like para facilitar observabilidad en Cloud Run.
"""

import logging
import json
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formateador que emite registros de log en formato JSON estructurado."""

    def format(self, record: logging.LogRecord) -> str:
        """Convierte un LogRecord a una linea JSON estructurada."""
        log_entry: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra_data"):
            log_entry["data"] = record.extra_data
        return json.dumps(log_entry, ensure_ascii=False)


def setup_logging(level: int = logging.INFO) -> None:
    """Inicializa el logging estructurado para toda la aplicacion."""
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Evitar duplicar handlers si se llama mas de una vez
    if root_logger.handlers:
        return

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JSONFormatter())
    root_logger.addHandler(handler)

    # Reducir ruido de librerias externas
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
