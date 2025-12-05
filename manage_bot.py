#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

BOT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BOT_DIR.parent
PID_FILE = BOT_DIR / "bot.pid"
LOG_FILE = BOT_DIR / "out.log"


def _read_pid() -> int | None:
    if not PID_FILE.exists():
        return None
    try:
        return int(PID_FILE.read_text().strip())
    except ValueError:
        return None


def _is_running(pid: int | None) -> bool:
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    else:
        return True


def _write_pid(pid: int) -> None:
    PID_FILE.write_text(str(pid))


def _remove_pid() -> None:
    try:
        PID_FILE.unlink()
    except FileNotFoundError:
        pass


def _start(python_exec: str | None) -> None:
    pid = _read_pid()
    if _is_running(pid):
        print(f"Bot already running with PID {pid}.")
        return

    env = os.environ.copy()
    env.setdefault("PYTHONPATH", str(PROJECT_ROOT))

    python = python_exec or sys.executable
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_FILE, "ab", buffering=0) as stream:
        process = subprocess.Popen(
            [python, "-m", "bot.main"],
            cwd=str(PROJECT_ROOT),
            stdout=stream,
            stderr=subprocess.STDOUT,
            env=env,
        )
    _write_pid(process.pid)
    print(f"Bot started with PID {process.pid}.")


def _stop(timeout: float, force: bool) -> None:
    pid = _read_pid()
    if pid is None:
        print("Bot is not running (PID file not found).")
        return

    if not _is_running(pid):
        print("Bot is not running (stale PID file). Cleaning up.")
        _remove_pid()
        return

    print(f"Stopping bot process {pid}...")
    os.kill(pid, signal.SIGTERM)

    deadline = time.time() + timeout
    while _is_running(pid) and time.time() < deadline:
        time.sleep(0.1)

    if _is_running(pid):
        if force:
            print("Process did not exit in time; sending SIGKILL.")
            os.kill(pid, signal.SIGKILL)
        else:
            print("Process is still running; use --force to send SIGKILL.")
            return

    _remove_pid()
    print("Bot stopped.")


def _status() -> None:
    pid = _read_pid()
    if _is_running(pid):
        print(f"Bot is running with PID {pid}.")
    else:
        print("Bot is not running.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Manage the Hypetuning bot process.")
    subparsers = parser.add_subparsers(dest="action", required=True)

    start_parser = subparsers.add_parser("start", help="Start the bot in the background.")
    start_parser.add_argument(
        "--python",
        dest="python_exec",
        metavar="PATH",
        help="Python interpreter to use (defaults to current interpreter).",
    )

    stop_parser = subparsers.add_parser("stop", help="Stop the bot process using the PID file.")
    stop_parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for graceful shutdown before giving up (default: 10).",
    )
    stop_parser.add_argument(
        "--force",
        action="store_true",
        help="Send SIGKILL if the process does not stop within timeout.",
    )

    subparsers.add_parser("status", help="Check whether the bot is running.")

    restart_parser = subparsers.add_parser("restart", help="Restart the bot process.")
    restart_parser.add_argument(
        "--python",
        dest="python_exec",
        metavar="PATH",
        help="Python interpreter to use (defaults to current interpreter).",
    )
    restart_parser.add_argument(
        "--timeout",
        type=float,
        default=10.0,
        help="Seconds to wait for graceful shutdown before forcing stop (default: 10).",
    )
    restart_parser.add_argument(
        "--force",
        action="store_true",
        help="Send SIGKILL if the process does not stop within timeout.",
    )

    args = parser.parse_args(argv)

    if args.action == "start":
        _start(args.python_exec)
    elif args.action == "stop":
        _stop(timeout=args.timeout, force=args.force)
    elif args.action == "status":
        _status()
    elif args.action == "restart":
        _stop(timeout=args.timeout, force=args.force)
        _start(args.python_exec)
    else:
        parser.error("Unknown action")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
