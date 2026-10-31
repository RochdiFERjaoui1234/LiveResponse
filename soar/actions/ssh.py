from __future__ import annotations
import asyncio
import time
from pathlib import Path
from ..models import Alert, ActionResult

async def execute(params: dict, alert: Alert, ctx: dict) -> ActionResult:
    target_name = params.get("target", "production_server")
    target = ctx["config"].get(f"targets.{target_name}")
    command = ctx["render"](params.get("command", ""))
    started = time.time()

    if not target or target.get("type") != "ssh":
        return ActionResult(
            action=f"ssh:{target_name}",
            success=False,
            error=f"Target '{target_name}' not configured or not type 'ssh'",
            duration_ms=0,
        )

    if ctx["dry_run"]:
        return ActionResult(
            action=f"ssh:{target_name}",
            success=True,
            simulated=True,
            output=f"[DRY-RUN SIMULATION] Would execute on {target.get('host')}:{target.get('port', 22)}:\n$ {command}",
            duration_ms=int((time.time() - started) * 1000),
        )

    def _ssh_exec() -> tuple[str, str, int]:
        try:
            import paramiko
        except ImportError:
            raise RuntimeError("Python library 'paramiko' is required for live SSH execution. Install with: pip install paramiko")

        client = paramiko.SSHClient()
        known_hosts = target.get("known_hosts")
        if known_hosts and Path(known_hosts).exists():
            client.load_system_host_keys(known_hosts)
            client.set_missing_host_key_policy(paramiko.RejectPolicy())
        else:
            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        key_file = target.get("key_file")
        if key_file and not Path(key_file).exists():
            key_file = None

        client.connect(
            hostname=target["host"],
            port=int(target.get("port", 22)),
            username=target.get("user", "soar"),
            key_filename=key_file,
            timeout=15,
        )
        try:
            _, stdout, stderr = client.exec_command(command, timeout=30)
            exit_status = stdout.channel.recv_exit_status()
            out_str = stdout.read().decode("utf-8", errors="replace")
            err_str = stderr.read().decode("utf-8", errors="replace")
            return out_str, err_str, exit_status
        finally:
            client.close()

    try:
        out, err, code = await asyncio.to_thread(_ssh_exec)
        return ActionResult(
            action=f"ssh:{target_name}",
            success=(code == 0),
            output=out.strip(),
            error=err.strip() if code != 0 else "",
            duration_ms=int((time.time() - started) * 1000),
        )
    except Exception as e:
        return ActionResult(
            action=f"ssh:{target_name}",
            success=False,
            error=f"SSH Execution Error: {str(e)}",
            duration_ms=int((time.time() - started) * 1000),
        )
