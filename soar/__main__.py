from __future__ import annotations
import argparse
import os
import threading
import time
import webbrowser
from pathlib import Path
import uvicorn
from .config import Config
from .state import State
from .audit import AuditLog
from .safety import load_whitelist
from .engine import PlaybookEngine
from .api import create_app

import sys

def _open_browser_when_ready(port: int) -> None:
    import urllib.request
    url = f"http://127.0.0.1:{port}/"
    for _ in range(120):
        try:
            urllib.request.urlopen(url, timeout=1)
            webbrowser.open(url)
            return
        except Exception:
            time.sleep(0.5)

def main():
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")
            sys.stderr.reconfigure(encoding="utf-8")
        except Exception:
            pass

    # When packaged as a double-click executable, run from the exe's folder
    # so ./config and ./playbooks resolve next to it.
    if getattr(sys, "frozen", False):
        os.chdir(Path(sys.executable).parent)
        if getattr(sys, "_MEIPASS", None):
            import multiprocessing
            multiprocessing.freeze_support()

    # Packaged with --noconsole: stdout/stderr are None; keep logging on disk
    if getattr(sys, "frozen", False) and (sys.stdout is None or sys.stderr is None):
        Path("var").mkdir(exist_ok=True)
        log = open(Path("var/live_response.log"), "a", buffering=1, encoding="utf-8")
        sys.stdout = log
        sys.stderr = log

    parser = argparse.ArgumentParser(
        prog="live-response",
        description="Live Response — Out-of-Band Security Orchestration, Automation, and Response",
    )
    parser.add_argument("--config", default="config/config.yaml", help="Path to config.yaml")
    parser.add_argument("--host", default=None, help="Override server host")
    parser.add_argument("--port", type=int, default=None, help="Override server port")
    parser.add_argument("--live", action="store_true", help="Force live execution (disable dry-run)")
    parser.add_argument("--open-browser", action="store_true", help="Open the web console when the server is up")
    args = parser.parse_args()

    config = Config(args.config)
    if args.live:
        config.set("engine.dry_run", False)

    state = State(config.get("engine.state_db", "./var/state.db"))
    audit = AuditLog(config.get("engine.audit_log", "./var/audit.jsonl"))
    whitelist = load_whitelist(config.get("engine.whitelist_file", "./config/whitelist.txt"))
    playbooks_dir = config.get("engine.playbooks_dir", "./playbooks")

    engine = PlaybookEngine(
        config=config,
        state=state,
        audit=audit,
        playbooks_dir=playbooks_dir,
        whitelist=whitelist,
    )

    ctx = {
        "config": config,
        "state": state,
        "audit": audit,
        "engine": engine,
    }

    app = create_app(ctx)
    host = args.host or config.get("server.host", "0.0.0.0")
    port = args.port or int(config.get("server.port", 8088))

    print("=================================================================")
    print(" [*] LIVE RESPONSE - Out-of-Band Incident Response Platform")
    print(f" [*] Console & API:  http://{'127.0.0.1' if host == '0.0.0.0' else host}:{port}")
    print(f" [*] Dry Run Mode:   {engine.dry_run}")
    print(f" [*] Playbooks Dir:  {playbooks_dir}")
    print(f" [*] Whitelist:      {len(whitelist)} active rules")
    print("=================================================================")

    if args.open_browser:
        threading.Thread(target=_open_browser_when_ready, args=(port,), daemon=True).start()

    uvicorn.run(app, host=host, port=port, log_level="info")

if __name__ == "__main__":
    main()
