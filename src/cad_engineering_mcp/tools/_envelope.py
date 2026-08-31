"""Structured envelope for every CAD Engineering MCP tool.

Each tool returns a JSON-friendly mapping with this shape::

    {
        "status":          "PASS" | "FAIL" | "INCOMPLETE" | "ERROR",
        "tool":            "<tool_name>",
        "started_at_iso":  "2026-08-31T12:34:56.789012+00:00",
        "duration_ms":     123,
        "data":            {...} | None,
        "warnings":        ["..."],
        "errors":          ["..."],
    }

Phase 1 only exposes read/verification tools, so the typical status is
``PASS`` (data returned) or ``ERROR`` (path security, parse failure,
or other unrecoverable condition). ``INCOMPLETE`` is reserved for cases
where the underlying artifact is genuinely missing required fields (e.g.
``TBD`` diameter in the optical-window system). ``FAIL`` is reserved for
checks that *can* be evaluated and come back negative (not currently used
by read tools but the slot exists for future verification tools).
"""
from __future__ import annotations

import datetime as _dt
import time
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


def utcnow_iso() -> str:
    """Return the current UTC time as an ISO-8601 string with timezone."""
    return _dt.datetime.now(_dt.timezone.utc).isoformat()


def make_envelope(
    *,
    tool: str,
    started_at_iso: str,
    duration_ms: int,
    status: str,
    data: Any = None,
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    """Build a structured envelope."""
    return {
        "status": status,
        "tool": tool,
        "started_at_iso": started_at_iso,
        "duration_ms": int(duration_ms),
        "data": data,
        "warnings": list(warnings or []),
        "errors": list(errors or []),
    }


def run_tool(name: str, func: F, *args: Any, **kwargs: Any) -> dict[str, Any]:
    """Execute ``func`` and return its result wrapped in an envelope.

    Any uncaught exception is captured into ``errors`` and the envelope
    status is set to ``ERROR`` rather than being propagated as a Python
    traceback, so MCP clients always see a structured response.
    """
    started = utcnow_iso()
    t0 = time.perf_counter()
    warnings: list[str] = []
    errors: list[str] = []
    data: Any = None
    status = "PASS"
    try:
        result = func(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 -- tools must not propagate
        errors.append(f"{type(exc).__name__}: {exc}")
        status = "ERROR"
    else:
        # A tool may return either a plain dict (already an envelope),
        # a dict with a `data` key, or some other serialisable value.
        if isinstance(result, dict) and {"data", "status"} <= set(result):
            status = str(result.get("status", status))
            data = result.get("data", data)
            warnings.extend(result.get("warnings", []))
            errors.extend(result.get("errors", []))
        elif isinstance(result, dict) and "data" in result:
            data = result["data"]
            warnings.extend(result.get("warnings", []))
            errors.extend(result.get("errors", []))
        else:
            data = result
    duration_ms = int((time.perf_counter() - t0) * 1000)
    return make_envelope(
        tool=name,
        started_at_iso=started,
        duration_ms=duration_ms,
        status=status,
        data=data,
        warnings=warnings,
        errors=errors,
    )