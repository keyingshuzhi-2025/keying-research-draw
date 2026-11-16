#!/usr/bin/env python3
"""Start the local Research Draw web backend and frontend together."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from importlib.util import find_spec
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "web" / "frontend"


def relay_output(label: str, stream: object) -> None:
    for line in iter(stream.readline, ""):
        print(f"[{label}] {line}", end="", flush=True)


def stop_process_tree(process: subprocess.Popen[str]) -> None:
    try:
        if os.name == "nt":
            if process.poll() is None:
                process.send_signal(signal.CTRL_BREAK_EVENT)
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (ProcessLookupError, PermissionError):
        pass


def stop_all(processes: list[tuple[str, subprocess.Popen[str]]]) -> None:
    for _, process in reversed(processes):
        stop_process_tree(process)

    for _, process in processes:
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            if os.name == "nt":
                process.kill()
            else:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except (ProcessLookupError, PermissionError):
                    process.kill()
            process.wait()


def main() -> int:
    missing_commands = [name for name in ("npm",) if shutil.which(name) is None]
    if missing_commands:
        print(f"缺少命令：{', '.join(missing_commands)}。请先安装 Node.js/npm。", file=sys.stderr)
        return 1

    if find_spec("uvicorn") is None:
        print(
            "当前 uv 环境未安装 Web 依赖。请用 uv run --extra web --extra data --extra ml "
            "--extra maps --extra raster python scripts/dev_web.py 启动。",
            file=sys.stderr,
        )
        return 1

    if not (FRONTEND / "node_modules").is_dir():
        print("尚未安装前端依赖，请先运行：npm --prefix web/frontend install", file=sys.stderr)
        return 1

    backend_command = [
        sys.executable, "-m", "uvicorn", "web.backend.app:app",
        "--reload", "--host", "127.0.0.1", "--port", "8000",
    ]
    frontend_command = [
        "npm", "--prefix", str(FRONTEND), "run", "dev", "--",
        "--host", "127.0.0.1", "--port", "5173", "--strictPort",
    ]

    processes: list[tuple[str, subprocess.Popen[str]]] = []
    process_group_options = (
        {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
        if os.name == "nt"
        else {"start_new_session": True}
    )

    try:
        for label, command in (("backend", backend_command), ("frontend", frontend_command)):
            process = subprocess.Popen(
                command,
                cwd=ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                **process_group_options,
            )
            processes.append((label, process))
            threading.Thread(
                target=relay_output,
                args=(label, process.stdout),
                daemon=True,
            ).start()

        print("Research Draw Web 已启动：前端 http://127.0.0.1:5173 · 后端 http://127.0.0.1:8000")
        print("按 Ctrl+C 同时停止前端和后端。")

        while True:
            for label, process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    print(f"[{label}] 服务已退出（代码 {exit_code}），正在停止另一端。", file=sys.stderr)
                    return exit_code or 1
            time.sleep(0.25)
    except KeyboardInterrupt:
        print("\n正在停止前端和后端…")
        return 0
    except OSError as exc:
        print(f"启动服务失败：{exc}", file=sys.stderr)
        return 1
    finally:
        stop_all(processes)


if __name__ == "__main__":
    raise SystemExit(main())
