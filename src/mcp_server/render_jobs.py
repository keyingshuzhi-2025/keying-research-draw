"""Persistent job tracking for MCP render operations.

Jobs are stored inside each isolated MCP session workspace. The worker is
process-local, while the SQLite record lets a client recover status after a
transport interruption or server restart.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import sqlite3
import threading
import time
from contextlib import contextmanager
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterator

from src.mcp_server.workspace import MCPWorkspace


_SESSION_SCOPE_RE = re.compile(r"^[0-9a-f]{32}$")
_JOB_ID_RE = re.compile(r"^(?P<scope>[0-9a-f]{32})\.(?P<token>[0-9a-f]{32})$")
_REQUEST_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_RETENTION_SECONDS = 7 * 24 * 60 * 60
_MAX_ACTIVE_JOBS_PER_SESSION = 8


def session_scope_from_job_id(job_id: str) -> str:
    """Return the opaque session scope embedded in a job capability."""
    match = _JOB_ID_RE.fullmatch(str(job_id or ""))
    if not match:
        raise ValueError("job_id 格式无效；请使用 start_plot_job 返回的任务标识。")
    return match.group("scope")


class RenderJobStore:
    """SQLite-backed job records with a single in-process render worker."""

    def __init__(self, max_workers: int = 1) -> None:
        self._executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="research-draw-render",
        )
        self._lock = threading.RLock()
        self._schema_lock = threading.RLock()
        self._initialized_databases: set[str] = set()
        self._futures: dict[str, Future[Any]] = {}

    @staticmethod
    @contextmanager
    def _connect(database: Path) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(str(database), timeout=20)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA busy_timeout=20000")
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _ensure_schema(self, database: Path) -> None:
        key = str(database)
        with self._schema_lock:
            if key in self._initialized_databases:
                return
            database.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with self._connect(database) as connection:
                connection.execute("PRAGMA journal_mode=WAL")
                connection.execute("PRAGMA synchronous=FULL")
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS render_jobs (
                        job_id TEXT PRIMARY KEY,
                        request_id TEXT NOT NULL UNIQUE,
                        request_fingerprint TEXT NOT NULL,
                        operation TEXT NOT NULL,
                        payload_json TEXT NOT NULL,
                        state TEXT NOT NULL,
                        stage TEXT NOT NULL,
                        result_json TEXT,
                        error TEXT,
                        created_at REAL NOT NULL,
                        updated_at REAL NOT NULL,
                        started_at REAL,
                        finished_at REAL,
                        worker_pid INTEGER
                    )
                    """
                )
                connection.execute(
                    "CREATE INDEX IF NOT EXISTS idx_render_jobs_state ON render_jobs(state, created_at)"
                )
            try:
                database.chmod(0o600)
            except OSError:
                # The containing directory is private; some platforms do not
                # implement POSIX file mode changes.
                pass
            self._initialized_databases.add(key)

    def _prune_expired_jobs(self, database: Path) -> None:
        with self._connect(database) as connection:
            connection.execute(
                "DELETE FROM render_jobs WHERE created_at < ?",
                (time.time() - _RETENTION_SECONDS,),
            )

    @staticmethod
    def _public_record(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "job_id": row["job_id"],
            "request_id": row["request_id"],
            "operation": row["operation"],
            "state": row["state"],
            "stage": row["stage"],
            "error": row["error"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "started_at": row["started_at"],
            "finished_at": row["finished_at"],
        }

    @staticmethod
    def _interrupted_result() -> dict[str, Any]:
        return {
            "success": False,
            "stage": "server_interrupted",
            "message": (
                "MCP 服务在绘图期间重启，无法确认任务是否完成。请调用 list_render_outputs 检查结果；"
                "如需重试，请使用新的 request_id。"
            ),
        }

    def _mark_dead_running_jobs(self, database: Path) -> None:
        """Free queue capacity and persist an explicit state for dead workers."""
        with self._connect(database) as connection:
            rows = connection.execute(
                "SELECT job_id, worker_pid FROM render_jobs WHERE state='running'"
            ).fetchall()
            now = time.time()
            for row in rows:
                if self._pid_is_alive(row["worker_pid"]):
                    continue
                result = self._interrupted_result()
                connection.execute(
                    """
                    UPDATE render_jobs
                    SET state='failed', stage='server_interrupted', result_json=?, error=?,
                        finished_at=?, updated_at=?, worker_pid=NULL
                    WHERE job_id=? AND state='running'
                    """,
                    (
                        json.dumps(result, ensure_ascii=False),
                        result["message"],
                        now,
                        now,
                        row["job_id"],
                    ),
                )

    def _read_row(self, database: Path, job_id: str) -> sqlite3.Row | None:
        self._ensure_schema(database)
        self._mark_dead_running_jobs(database)
        with self._connect(database) as connection:
            return connection.execute(
                "SELECT * FROM render_jobs WHERE job_id = ?", (job_id,)
            ).fetchone()

    def submit(
        self,
        workspace: MCPWorkspace,
        session_scope: str,
        request_id: str,
        operation: str,
        payload: dict[str, Any],
        worker: Callable[[], dict[str, Any]],
    ) -> tuple[dict[str, Any], bool]:
        """Create or idempotently return a job, then enqueue it."""
        if not _SESSION_SCOPE_RE.fullmatch(session_scope):
            raise ValueError("MCP 会话工作区标识无效。")
        if not _REQUEST_ID_RE.fullmatch(str(request_id or "")):
            raise ValueError(
                "request_id 必须是 1–128 位字母、数字、点、下划线、冒号或短横线，"
                "并在重试时保持不变。"
            )

        database = workspace.job_store_path()
        payload_json = json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str
        )
        fingerprint = hashlib.sha256(
            json.dumps(
                {"operation": operation, "payload": payload},
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            ).encode("utf-8")
        ).hexdigest()
        now = time.time()
        reused = False

        self._ensure_schema(database)
        self._mark_dead_running_jobs(database)
        with self._connect(database) as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                "SELECT * FROM render_jobs WHERE request_id = ?", (request_id,)
            ).fetchone()
            if existing:
                if existing["request_fingerprint"] != fingerprint:
                    raise ValueError(
                        "request_id 已用于不同的绘图参数；重试时请复用原参数，"
                        "新任务请使用新的 request_id。"
                    )
                job_id = existing["job_id"]
                reused = True
            else:
                active_jobs = connection.execute(
                    "SELECT COUNT(*) FROM render_jobs WHERE state IN ('queued', 'running')"
                ).fetchone()[0]
                if active_jobs >= _MAX_ACTIVE_JOBS_PER_SESSION:
                    raise ValueError(
                        f"当前会话已有 {_MAX_ACTIVE_JOBS_PER_SESSION} 个绘图任务排队或运行；"
                        "请等待已有任务完成后再提交。"
                    )
                job_id = f"{session_scope}.{secrets.token_hex(16)}"
                connection.execute(
                    """
                    INSERT INTO render_jobs (
                        job_id, request_id, request_fingerprint, operation,
                        payload_json, state, stage, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'queued', 'queued', ?, ?)
                    """,
                    (job_id, request_id, fingerprint, operation, payload_json, now, now),
                )
        record = self.load(workspace, job_id)
        if record is None:
            raise RuntimeError("绘图任务记录无法读取。")
        if record["state"] == "queued":
            self.schedule(workspace, job_id, worker)
        return record, reused

    def schedule(
        self,
        workspace: MCPWorkspace,
        job_id: str,
        worker: Callable[[], dict[str, Any]],
    ) -> None:
        """Schedule a queued job once in this server process."""
        session_scope_from_job_id(job_id)
        database = workspace.job_store_path()
        future_key = f"{database}:{job_id}"
        with self._lock:
            current = self._futures.get(future_key)
            if current is not None and not current.done():
                return
            future = self._executor.submit(self._run, database, job_id, worker)
            self._futures[future_key] = future
            future.add_done_callback(
                lambda completed, key=future_key: self._forget_future(key, completed)
            )

    def _forget_future(self, key: str, future: Future[Any]) -> None:
        with self._lock:
            if self._futures.get(key) is future:
                self._futures.pop(key, None)

    def _run(
        self,
        database: Path,
        job_id: str,
        worker: Callable[[], dict[str, Any]],
    ) -> None:
        self._ensure_schema(database)
        now = time.time()
        with self._connect(database) as connection:
            cursor = connection.execute(
                """
                UPDATE render_jobs
                SET state='running', stage='rendering', started_at=?, updated_at=?, worker_pid=?
                WHERE job_id=? AND state='queued'
                """,
                (now, now, os.getpid(), job_id),
            )
            if cursor.rowcount != 1:
                return

        try:
            result = worker()
            if not isinstance(result, dict):
                result = {"success": False, "stage": "render", "message": "绘图任务返回了无效结果。"}
            succeeded = bool(result.get("success"))
            state = "succeeded" if succeeded else "failed"
            error = None if succeeded else str(result.get("message") or result.get("stage") or "绘图失败")
            result_json = json.dumps(result, ensure_ascii=False, default=str)
        except SystemExit as exc:
            state = "failed"
            error = f"SystemExit: {exc.code}"
            result_json = json.dumps(
                {"success": False, "stage": "render", "message": error},
                ensure_ascii=False,
            )
        except Exception as exc:
            state = "failed"
            error = f"{type(exc).__name__}: {exc}"
            result_json = json.dumps(
                {"success": False, "stage": "render", "message": error},
                ensure_ascii=False,
            )

        finished = time.time()
        with self._connect(database) as connection:
            connection.execute(
                """
                UPDATE render_jobs
                SET state=?, stage=?, result_json=?, error=?, finished_at=?, updated_at=?, worker_pid=NULL
                WHERE job_id=?
                """,
                (state, state, result_json, error, finished, finished, job_id),
            )

    def load(self, workspace: MCPWorkspace, job_id: str) -> dict[str, Any] | None:
        """Load a job and flag work interrupted by a dead server process."""
        session_scope_from_job_id(job_id)
        database = workspace.job_store_path()
        row = self._read_row(database, job_id)
        if row is None:
            return None

        public = self._public_record(row)
        public["payload"] = json.loads(row["payload_json"])
        public["result"] = json.loads(row["result_json"]) if row["result_json"] else None
        return public

    @staticmethod
    def _pid_is_alive(pid: int | None) -> bool:
        if not pid or pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False


render_job_store = RenderJobStore()
