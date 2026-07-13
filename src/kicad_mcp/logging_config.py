"""Logging estructurado JSON — regla de código #2 de CLAUDE.md.

Cada tool call emite una línea JSON con ``tool_name``, ``snap_id``,
``tokens_est``, ``latency_ms``. Es el instrumento de RNF2 (medición del
presupuesto de contexto), no decoración: sin estas líneas no hay
recalibración post-MVP (ver ADR-0004).
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

_LOGGER_NAME = "kicad_mcp"


def _configure_json_logger() -> logging.Logger:
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


_LOGGER = _configure_json_logger()


def estimate_tokens(text: str) -> int:
    """Estimador provisional del presupuesto de contexto (ADR-0004).

    Fórmula: ``len(texto) / 3.5``. Sirve para presupuestar, no para facturar.
    Se recalibra contra el tokenizador real en Eval A.
    """
    return int(len(text) / 3.5)


def log_tool_call(
    tool_name: str,
    latency_ms: float,
    tokens_est: int,
    snap_id: int | None = None,
    error_code: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emite una línea JSON con los campos del RNF2."""
    record: dict[str, Any] = {
        "tool_name": tool_name,
        "snap_id": snap_id,
        "tokens_est": tokens_est,
        "latency_ms": round(latency_ms, 3),
    }
    if error_code is not None:
        record["error_code"] = error_code
    if extra:
        record.update(extra)
    _LOGGER.info(json.dumps(record, separators=(",", ":"), ensure_ascii=False))


@contextmanager
def tool_call_timer() -> Iterator[dict[str, float]]:
    """Context manager que mide latencia. Uso: ``with tool_call_timer() as t: ...``."""
    result = {"latency_ms": 0.0}
    start = time.perf_counter()
    try:
        yield result
    finally:
        result["latency_ms"] = (time.perf_counter() - start) * 1000


def log_ipc_retry(op_name: str, attempt: int, backoff_ms: int) -> None:
    """Emite una línea JSON por cada retry por ``AS_BUSY`` (sesión 07 D-07.1).

    ``tool_name="ipc_retry"`` es un canal fijo para grep/filter en producción;
    ``op_name`` es la operación IPC concreta que fue reintentada
    (``get_version``, ``list_footprint_refs``, etc.). ``attempt`` es 1-indexed
    (1 = primer retry) y ``backoff_ms`` es la espera aplicada ANTES de este
    intento (el intento inicial es ``attempt=0`` y no se loguea).
    """
    _LOGGER.info(
        json.dumps(
            {
                "tool_name": "ipc_retry",
                "op_name": op_name,
                "attempt": attempt,
                "backoff_ms": backoff_ms,
            },
            separators=(",", ":"),
            ensure_ascii=False,
        )
    )
