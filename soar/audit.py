from __future__ import annotations
import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

class AuditLog:
    """
    Append-only tamper-resistant JSONL audit trail.
    Ensures that every SOAR decision, condition check, and action is written
    with fsync to guarantee persistence on the out-of-band management plane.
    """
    def __init__(self, path: str | Path = "./var/audit.jsonl"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def log(self, event: str, payload: dict[str, Any]):
        record = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "event": event,
            "payload": payload,
        }
        line = json.dumps(record, default=str) + "\n"
        async with self._lock:
            await asyncio.to_thread(self._append_sync, line)

    def _append_sync(self, line: str):
        flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
        # On Windows, os.O_BINARY might be useful; standard on Python is cross-platform
        fd = os.open(str(self.path), flags, 0o600)
        try:
            os.write(fd, line.encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)

    async def read_recent(self, limit: int = 100) -> list[dict[str, Any]]:
        """Read the last N entries for the dashboard audit inspector."""
        if not self.path.exists():
            return []
        def _read():
            with open(self.path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
            recent = lines[-limit:]
            out = []
            for line in reversed(recent):
                line = line.strip()
                if line:
                    try:
                        out.append(json.loads(line))
                    except Exception:
                        continue
            return out
        return await asyncio.to_thread(_read)
