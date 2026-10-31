from __future__ import annotations
import time
from pathlib import Path
from typing import Any, Optional
import aiosqlite

SCHEMA = """
CREATE TABLE IF NOT EXISTS executions (
    id TEXT PRIMARY KEY,
    playbook TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at REAL NOT NULL,
    finished_at REAL
);

CREATE TABLE IF NOT EXISTS action_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_id TEXT NOT NULL,
    action_name TEXT NOT NULL,
    success INTEGER NOT NULL,
    output TEXT,
    error TEXT,
    simulated INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    execution_id TEXT NOT NULL,
    playbook TEXT NOT NULL,
    action_name TEXT NOT NULL,
    alert_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at REAL NOT NULL,
    resolved_at REAL,
    resolved_by TEXT
);

CREATE TABLE IF NOT EXISTS rate_limits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    scope TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rate_scope_time ON rate_limits(scope, created_at);
CREATE INDEX IF NOT EXISTS idx_approvals_status ON approvals(status);
"""

class State:
    def __init__(self, db_path: str | Path = "./var/state.db"):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    async def init(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()

    async def create_execution(self, exec_id: str, playbook: str, alert_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO executions (id, playbook, alert_id, status, started_at) VALUES (?, ?, ?, 'running', ?)",
                (exec_id, playbook, alert_id, time.time()),
            )
            await db.commit()

    async def finish_execution(self, exec_id: str, status: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE executions SET status=?, finished_at=? WHERE id=?",
                (status, time.time(), exec_id),
            )
            await db.commit()

    async def add_action_result(self, exec_id: str, name: str, result: Any):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO action_results "
                "(execution_id, action_name, success, output, error, simulated, duration_ms, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    exec_id,
                    name,
                    int(result.success),
                    result.output,
                    result.error,
                    int(result.simulated),
                    result.duration_ms,
                    time.time(),
                ),
            )
            await db.commit()

    async def create_approval(self, approval_id: str, exec_id: str, playbook: str, action: str, alert_id: str):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO approvals (id, execution_id, playbook, action_name, alert_id, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
                (approval_id, exec_id, playbook, action, alert_id, time.time()),
            )
            await db.commit()

    async def resolve_approval(self, approval_id: str, status: str, resolved_by: str = "web_ui"):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "UPDATE approvals SET status=?, resolved_at=?, resolved_by=? WHERE id=?",
                (status, time.time(), resolved_by, approval_id),
            )
            await db.commit()

    async def get_approval(self, approval_id: str) -> Optional[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM approvals WHERE id=?", (approval_id,)) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    async def list_pending_approvals(self) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM approvals WHERE status='pending' ORDER BY created_at DESC"
            ) as cur:
                return [dict(r) for r in await cur.fetchall()]

    async def bump_rate(self, scope: str) -> int:
        now = time.time()
        cutoff = now - 3600
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("INSERT INTO rate_limits (scope, created_at) VALUES (?, ?)", (scope, now))
            await db.execute("DELETE FROM rate_limits WHERE created_at < ?", (cutoff,))
            await db.commit()
            async with db.execute(
                "SELECT COUNT(*) FROM rate_limits WHERE scope=? AND created_at>=?",
                (scope, cutoff),
            ) as cur:
                row = await cur.fetchone()
                return int(row[0]) if row else 1

    async def recent_executions(self, limit: int = 50) -> list[dict[str, Any]]:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                "SELECT * FROM executions ORDER BY started_at DESC LIMIT ?", (limit,)
            ) as cur:
                execs = [dict(r) for r in await cur.fetchall()]

            for ex in execs:
                async with db.execute(
                    "SELECT action_name, success, output, error, simulated, duration_ms FROM action_results WHERE execution_id=? ORDER BY id ASC",
                    (ex["id"],),
                ) as cur:
                    ex["actions"] = [dict(a) for a in await cur.fetchall()]
            return execs

    async def get_stats(self) -> dict[str, Any]:
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT COUNT(*) FROM executions") as cur:
                total_execs = (await cur.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM executions WHERE status='success'") as cur:
                successful_execs = (await cur.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM approvals WHERE status='pending'") as cur:
                pending_approvals = (await cur.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM action_results WHERE success=1") as cur:
                actions_taken = (await cur.fetchone())[0]

            return {
                "total_executions": total_execs,
                "successful_executions": successful_execs,
                "pending_approvals": pending_approvals,
                "actions_taken": actions_taken,
            }
