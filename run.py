"""Double-click entry point for the packaged Live Response executable.

PyInstaller runs this file as a plain script, so all project imports stay
absolute. Frozen defaults: run from the exe folder and auto-open the console.
"""
import multiprocessing
import os
import sys
from pathlib import Path

if getattr(sys, "frozen", False):
    multiprocessing.freeze_support()
    # Keep ./config and ./playbooks resolving next to the exe
    os.chdir(Path(sys.executable).parent)
    # --noconsole builds: stdout/stderr are None, keep logging on disk
    if sys.stdout is None or sys.stderr is None:
        Path("var").mkdir(exist_ok=True)
        log = open(Path("var/live_response.log"), "a", buffering=1, encoding="utf-8")
        sys.stdout = log
        sys.stderr = log
    if "--open-browser" not in sys.argv:
        sys.argv.append("--open-browser")

from soar.__main__ import main

main()
