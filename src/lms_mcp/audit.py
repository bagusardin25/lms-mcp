"""Catatan lokal aksi yang mengubah sesuatu, tanpa token dan tanpa isi file."""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from .formatting import WIB

DEFAULT_AUDIT_PATH = Path.home() / ".lms-mcp" / "audit.log"


def audit_path() -> Path:
    configured = os.environ.get("LMS_AUDIT_LOG")
    return Path(configured).expanduser() if configured else DEFAULT_AUDIT_PATH


def record(action: str, **details: Any) -> None:
    """Menambah satu baris. Kegagalan menulis catatan tidak menggagalkan aksi LMS."""
    event = {
        "time": datetime.now(WIB).isoformat(),
        "action": action,
        **{key: value for key, value in details.items() if value is not None},
    }
    try:
        path = audit_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    except OSError:
        return
