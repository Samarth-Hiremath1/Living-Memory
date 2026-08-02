"""
Structured logging and per-node timing for both LangGraph graphs.

Emits one JSON line per node execution:

    {"ts": "...", "event": "node", "graph": "arrival_pipeline",
     "node": "history_node", "duration_ms": 1843.2, "status": "ok"}

Why JSON lines: they are greppable by hand and ingestible by any log pipeline
without a parser. Why per-node: the whole point of the parallel fan-out is that
three nodes overlap in wall time, and you cannot demonstrate that without
per-node start and end timestamps.

The `instrument` decorator is applied to LangGraph node functions. It records
duration, catches nothing (errors propagate), but logs status=error with the
exception type before re-raising so a failure is never silent.

Timings are also accumulated in a process-local registry so a benchmark can
read them back without scraping logs — see `get_timings` / `reset_timings`.
"""

from __future__ import annotations

import functools
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from typing import Any, Callable

_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logger = logging.getLogger("living_memory")


class JsonFormatter(logging.Formatter):
    """Render each record as a single JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # Anything attached via `extra=` lands in __dict__; pull the known keys.
        for key in (
            "event",
            "graph",
            "node",
            "duration_ms",
            "status",
            "error_type",
            "tool",
            "steps",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)
        return json.dumps(payload)


def configure_logging() -> None:
    """Install the JSON formatter on the package logger. Idempotent."""
    if getattr(configure_logging, "_done", False):
        return
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.setLevel(_LEVEL)
    logger.addHandler(handler)
    logger.propagate = False
    configure_logging._done = True  # type: ignore[attr-defined]


# ── Timing registry ──────────────────────────────────────────────────────────
#
# Records (node, start_perf, end_perf, duration_ms) per graph run so a benchmark
# can compute overlap. Wall-clock start/end are needed — summing durations tells
# you nothing about whether nodes ran concurrently.

_timings_lock = threading.Lock()
_timings: list[dict] = []


def reset_timings() -> None:
    with _timings_lock:
        _timings.clear()


def get_timings() -> list[dict]:
    with _timings_lock:
        return list(_timings)


def _record(entry: dict) -> None:
    with _timings_lock:
        _timings.append(entry)


def instrument(graph_name: str, node_name: str) -> Callable:
    """
    Decorator for a LangGraph node function.

    Logs one structured line per execution and records wall-clock start/end so
    concurrency can be measured after the fact.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            configure_logging()
            start = time.perf_counter()
            status = "ok"
            error_type = None
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                status = "error"
                error_type = type(exc).__name__
                raise
            finally:
                end = time.perf_counter()
                duration_ms = round((end - start) * 1000, 2)
                _record(
                    {
                        "graph": graph_name,
                        "node": node_name,
                        "start": start,
                        "end": end,
                        "duration_ms": duration_ms,
                        "status": status,
                    }
                )
                logger.info(
                    "node %s finished in %.1fms (%s)",
                    node_name,
                    duration_ms,
                    status,
                    extra={
                        "event": "node",
                        "graph": graph_name,
                        "node": node_name,
                        "duration_ms": duration_ms,
                        "status": status,
                        **({"error_type": error_type} if error_type else {}),
                    },
                )

        return wrapper

    return decorator


def summarize_parallel_section(nodes: list[str], graph_name: str) -> dict:
    """
    Given node names expected to run concurrently, compute:
      - serial_ms:   sum of their individual durations (what a chain would cost)
      - wall_ms:     span from earliest start to latest end (what actually elapsed)
      - speedup:     serial_ms / wall_ms
      - overlap_ms:  serial_ms - wall_ms

    Returns zeros if the nodes were not recorded.
    """
    entries = [
        t for t in get_timings() if t["graph"] == graph_name and t["node"] in nodes
    ]
    if not entries:
        return {"serial_ms": 0.0, "wall_ms": 0.0, "speedup": 0.0, "overlap_ms": 0.0}

    serial_ms = round(sum(e["duration_ms"] for e in entries), 2)
    wall_ms = round(
        (max(e["end"] for e in entries) - min(e["start"] for e in entries)) * 1000, 2
    )
    speedup = round(serial_ms / wall_ms, 2) if wall_ms > 0 else 0.0
    return {
        "serial_ms": serial_ms,
        "wall_ms": wall_ms,
        "speedup": speedup,
        "overlap_ms": round(serial_ms - wall_ms, 2),
        "nodes": {e["node"]: e["duration_ms"] for e in entries},
    }
