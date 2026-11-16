from __future__ import annotations

import csv
import json
import os
import queue
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Literal, Optional, TypeVar
from urllib.parse import quote
from uuid import uuid4

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field


PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Web service runs in headless mode by default.
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("PLOT_BACKEND", "Agg")
os.environ.setdefault("HEADLESS", "1")

from src.main import ResearchDrawApp  # noqa: E402
from src.registry import canonical_plots_by_group, plot_registry_payload  # noqa: E402
from src.version import APP_VERSION, __version__  # noqa: E402


WEB_OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "web"
UPLOAD_DIR = WEB_OUTPUT_ROOT / "uploads"
RENDER_DIR = WEB_OUTPUT_ROOT / "renders"
WEB_ASSETS_DIR = PROJECT_ROOT / "web" / "assets"
CONTACT_ASSETS_DIR = WEB_ASSETS_DIR / "images"
USER_MANUAL_FILE = PROJECT_ROOT / "ResearchDrawApp_使用手册.md"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
RENDER_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_UPLOAD_SUFFIX = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}
CONTACT_IMAGE_SUFFIX = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}

def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class WebRuntimeSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")

    task_queue_max_size: int = 128
    task_worker_count: int = 1
    task_max_records: int = 2000
    task_retention_seconds: int = 24 * 3600

    upload_max_files: int = 300
    render_max_files: int = 600
    upload_max_file_mb: int = 200
    upload_max_total_mb: int = 2048
    render_max_total_mb: int = 4096
    upload_retention_days: int = 14
    render_retention_days: int = 30
    cleanup_interval_seconds: int = 600

    @classmethod
    def from_env(cls) -> "WebRuntimeSettings":
        return cls(
            task_queue_max_size=max(8, _env_int("WEB_TASK_QUEUE_MAX_SIZE", 128)),
            task_worker_count=max(1, _env_int("WEB_TASK_WORKER_COUNT", 1)),
            task_max_records=max(100, _env_int("WEB_TASK_MAX_RECORDS", 2000)),
            task_retention_seconds=max(600, _env_int("WEB_TASK_RETENTION_SECONDS", 24 * 3600)),
            upload_max_files=max(10, _env_int("WEB_UPLOAD_MAX_FILES", 300)),
            render_max_files=max(10, _env_int("WEB_RENDER_MAX_FILES", 600)),
            upload_max_file_mb=max(1, _env_int("WEB_UPLOAD_MAX_FILE_MB", 200)),
            upload_max_total_mb=max(1, _env_int("WEB_UPLOAD_MAX_TOTAL_MB", 2048)),
            render_max_total_mb=max(1, _env_int("WEB_RENDER_MAX_TOTAL_MB", 4096)),
            upload_retention_days=max(1, _env_int("WEB_UPLOAD_RETENTION_DAYS", 14)),
            render_retention_days=max(1, _env_int("WEB_RENDER_RETENTION_DAYS", 30)),
            cleanup_interval_seconds=max(30, _env_int("WEB_CLEANUP_INTERVAL_SECONDS", 600)),
        )


SETTINGS = WebRuntimeSettings.from_env()

TASK_QUEUE_MAX_SIZE = SETTINGS.task_queue_max_size
TASK_WORKER_COUNT = SETTINGS.task_worker_count
TASK_MAX_RECORDS = SETTINGS.task_max_records
TASK_RETENTION_SECONDS = SETTINGS.task_retention_seconds

UPLOAD_MAX_FILES = SETTINGS.upload_max_files
RENDER_MAX_FILES = SETTINGS.render_max_files
UPLOAD_MAX_FILE_BYTES = SETTINGS.upload_max_file_mb * 1024 * 1024
UPLOAD_MAX_TOTAL_BYTES = SETTINGS.upload_max_total_mb * 1024 * 1024
RENDER_MAX_TOTAL_BYTES = SETTINGS.render_max_total_mb * 1024 * 1024
UPLOAD_RETENTION_DAYS = SETTINGS.upload_retention_days
RENDER_RETENTION_DAYS = SETTINGS.render_retention_days
UPLOAD_RETENTION_SECONDS = UPLOAD_RETENTION_DAYS * 24 * 3600
RENDER_RETENTION_SECONDS = RENDER_RETENTION_DAYS * 24 * 3600
CLEANUP_INTERVAL_SECONDS = SETTINGS.cleanup_interval_seconds

class RenderRequest(BaseModel):
    mode: Literal["demo", "custom", "file"] = "demo"
    plot: str = "box"
    title: Optional[str] = None
    fmt: Literal["png", "svg", "pdf"] = "png"
    uploaded_file: Optional[str] = None
    args: Dict[str, Any] = Field(default_factory=dict)


class RenderResponse(BaseModel):
    ok: bool
    save_name: str
    fmt: str
    image_url: str
    argv: list[str]


TaskStatus = Literal["queued", "running", "success", "failed", "cancelled"]


class TaskSubmitResponse(BaseModel):
    ok: bool = True
    task_id: str
    status: TaskStatus = "queued"
    queue_size: int = 0
    detail: str = ""


class TaskStatusResponse(BaseModel):
    ok: bool = True
    task_id: str
    status: TaskStatus
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    cancel_requested: bool = False
    detail: str = ""
    save_name: str
    fmt: str
    image_url: Optional[str] = None
    argv: list[str] = Field(default_factory=list)
    error: Optional[str] = None


class TaskListResponse(BaseModel):
    items: list[TaskStatusResponse] = Field(default_factory=list)


class UploadResponse(BaseModel):
    file_id: str
    filename: str
    size: int
    columns: list[str] = Field(default_factory=list)
    preview_rows: list[dict[str, Any]] = Field(default_factory=list)


class UploadFileItem(BaseModel):
    file_id: str
    size: int
    modified_at: str


class UploadListResponse(BaseModel):
    items: list[UploadFileItem] = Field(default_factory=list)
    page: int = 1
    page_size: int = 50
    total: int = 0
    total_pages: int = 0
    has_next: bool = False
    usage_bytes: int = 0
    quota_bytes: int = 0


class RenderFileItem(BaseModel):
    filename: str
    size: int
    modified_at: str
    image_url: str


class RenderListResponse(BaseModel):
    items: list[RenderFileItem] = Field(default_factory=list)
    page: int = 1
    page_size: int = 50
    total: int = 0
    total_pages: int = 0
    has_next: bool = False
    usage_bytes: int = 0
    quota_bytes: int = 0


class DeleteResponse(BaseModel):
    ok: bool = True
    deleted: int = 0
    detail: str = ""


class ContactAssetItem(BaseModel):
    name: str
    url: str


class ContactAssetResponse(BaseModel):
    items: list[ContactAssetItem] = Field(default_factory=list)


class UserManualResponse(BaseModel):
    title: str
    content: str


class VersionResponse(BaseModel):
    version: str


def _safe_resolve_input_file(raw: str) -> Path:
    candidate = Path(raw).expanduser()
    if not candidate.is_absolute():
        candidate = (PROJECT_ROOT / candidate).resolve()
    else:
        candidate = candidate.resolve()
    if not candidate.exists() or not candidate.is_file():
        raise HTTPException(status_code=400, detail=f"输入文件不存在: {candidate}")
    if not str(candidate).startswith(str(PROJECT_ROOT)):
        raise HTTPException(status_code=400, detail="只允许读取项目目录内文件")
    return candidate


def _safe_upload_file(file_id: str) -> Path:
    clean = Path(file_id).name
    p = (UPLOAD_DIR / clean).resolve()
    if not str(p).startswith(str(UPLOAD_DIR.resolve())):
        raise HTTPException(status_code=400, detail="非法上传文件标识")
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail=f"上传文件不存在: {file_id}")
    return p


def _safe_render_file(filename: str) -> Path:
    clean = Path(filename).name
    p = (RENDER_DIR / clean).resolve()
    if not str(p).startswith(str(RENDER_DIR.resolve())):
        raise HTTPException(status_code=400, detail="非法渲染文件路径")
    if not p.exists() or not p.is_file():
        raise HTTPException(status_code=404, detail=f"渲染文件不存在: {filename}")
    return p


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds")


def _sorted_files(root: Path) -> list[Path]:
    files = [p for p in root.iterdir() if p.is_file()]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return files


def _file_size_bytes(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except Exception:
        return 0


def _total_size_bytes(files: list[Path]) -> int:
    total = 0
    for fp in files:
        total += _file_size_bytes(fp)
    return total


def _normalize_page(page: int, page_size: int) -> tuple[int, int]:
    safe_page = max(1, int(page or 1))
    safe_page_size = max(1, min(int(page_size or 50), 200))
    return safe_page, safe_page_size


T = TypeVar("T")


def _paginate_list(items: list[T], page: int, page_size: int) -> tuple[list[T], dict[str, int | bool]]:
    safe_page, safe_page_size = _normalize_page(page, page_size)
    total = len(items)
    total_pages = (total + safe_page_size - 1) // safe_page_size if total > 0 else 0
    start = (safe_page - 1) * safe_page_size
    end = start + safe_page_size
    window = items[start:end] if start < total else []
    return window, {
        "page": safe_page,
        "page_size": safe_page_size,
        "total": total,
        "total_pages": total_pages,
        "has_next": bool(total_pages and safe_page < total_pages),
    }


def _asset_url(relative_path: Path) -> str:
    encoded = "/".join(quote(part) for part in relative_path.as_posix().split("/"))
    return f"/assets/{encoded}"


def _records_from_dataframe(df, limit: int = 5) -> tuple[list[str], list[dict[str, Any]]]:
    cols = [str(c) for c in df.columns]
    head = df.head(limit)
    try:
        head = head.where(head.notna(), None)
    except Exception:
        pass
    rows = head.to_dict(orient="records")
    return cols, rows


def _inspect_upload_file(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    suffix = path.suffix.lower()
    if suffix in {".xlsx", ".xls"}:
        try:
            import pandas as pd  # type: ignore

            df = pd.read_excel(path)
            return _records_from_dataframe(df)
        except Exception:
            return [], []

    seps = [",", "\t", ";"] if suffix in {".csv", ".tsv", ".txt"} else [","]
    for sep in seps:
        for enc in ("utf-8-sig", "utf-8", "gbk"):
            try:
                with path.open("r", encoding=enc, newline="") as f:
                    reader = csv.DictReader(f, delimiter=sep)
                    fieldnames = [str(c) for c in (reader.fieldnames or [])]
                    if not fieldnames:
                        continue
                    preview = []
                    for i, row in enumerate(reader):
                        if i >= 5:
                            break
                        clean = {str(k): (v if v != "" else None) for k, v in (row or {}).items()}
                        preview.append(clean)
                    return fieldnames, preview
            except Exception:
                continue

    try:
        import pandas as pd  # type: ignore

        df = pd.read_csv(path)
        return _records_from_dataframe(df)
    except Exception:
        return [], []


def _flag_name(dest_key: str) -> str:
    return f"--{dest_key.replace('_', '-')}"


def _append_arg(argv: list[str], key: str, value: Any) -> None:
    if value is None:
        return
    flag = _flag_name(key)
    if isinstance(value, bool):
        if value:
            argv.append(flag)
        return
    if isinstance(value, (list, tuple)):
        if key == "group":
            for item in value:
                argv.extend([flag, str(item)])
        elif key in {"x", "y", "z", "u", "v", "w", "scalar", "labels", "forest_labels", "effects", "ci_low", "ci_high", "weights"}:
            joined = ",".join(str(x) for x in value)
            argv.extend([flag, joined])
        else:
            argv.extend([flag, ",".join(str(x) for x in value)])
        return
    if isinstance(value, dict):
        argv.extend([flag, json.dumps(value, ensure_ascii=False)])
        return
    argv.extend([flag, str(value)])


def _build_argv(req: RenderRequest, save_name: str) -> list[str]:
    argv: list[str] = [
        "--mode",
        req.mode,
        "--plot",
        req.plot,
        "--no-show",
        "--outdir",
        str(RENDER_DIR),
        "--save-name",
        save_name,
        "--fmt",
        req.fmt,
    ]
    if req.title:
        argv.extend(["--title", req.title])

    payload_args = dict(req.args or {})
    if req.uploaded_file:
        payload_args["file"] = str(_safe_upload_file(req.uploaded_file))
    elif req.mode == "file" and "file" in payload_args and payload_args["file"]:
        payload_args["file"] = str(_safe_resolve_input_file(str(payload_args["file"])))

    if req.mode == "file" and not payload_args.get("file"):
        raise HTTPException(status_code=400, detail="file 模式需要上传文件或提供 args.file")

    reserved = {"mode", "plot", "title", "fmt", "outdir", "save_name", "no_show", "uploaded_file", "args"}
    for key, value in payload_args.items():
        if key in reserved:
            continue
        _append_arg(argv, key, value)
    return argv


TERMINAL_TASK_STATES = {"success", "failed", "cancelled"}
TASK_QUEUE: queue.Queue[str] = queue.Queue(maxsize=TASK_QUEUE_MAX_SIZE)
TASK_LOCK = threading.Lock()
TASKS: dict[str, dict[str, Any]] = {}
TASK_WORKERS: list[threading.Thread] = []
CLEANUP_WORKER: Optional[threading.Thread] = None
SHUTDOWN_EVENT = threading.Event()
CLEANUP_STATS: dict[str, Any] = {
    "last_run_at": "",
    "last_reason": "",
    "deleted_uploads": 0,
    "deleted_renders": 0,
    "deleted_upload_bytes": 0,
    "deleted_render_bytes": 0,
    "deleted_tasks": 0,
    "upload_files": 0,
    "upload_bytes": 0,
    "upload_quota_bytes": UPLOAD_MAX_TOTAL_BYTES,
    "render_files": 0,
    "render_bytes": 0,
    "render_quota_bytes": RENDER_MAX_TOTAL_BYTES,
}


def _now_ts() -> float:
    return time.time()


def _iso_from_ts(ts: Optional[float]) -> Optional[str]:
    if ts is None:
        return None
    return datetime.fromtimestamp(ts).isoformat(timespec="seconds")


def _delete_file_quiet(path: Path) -> bool:
    try:
        path.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _render_output_path(save_name: str, fmt: str) -> Path:
    return (RENDER_DIR / f"{save_name}.{fmt}").resolve()


def _execute_render_sync(req: RenderRequest, save_name: str, argv: list[str]) -> RenderResponse:
    try:
        ResearchDrawApp(argv).run()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"渲染失败: {e}") from e

    outpath = _render_output_path(save_name, req.fmt)
    if not outpath.exists():
        raise HTTPException(status_code=500, detail=f"渲染完成但未找到输出文件: {outpath}")
    return RenderResponse(
        ok=True,
        save_name=save_name,
        fmt=req.fmt,
        image_url=f"/api/files/{outpath.name}",
        argv=argv,
    )


def _task_to_response(task: dict[str, Any]) -> TaskStatusResponse:
    return TaskStatusResponse(
        ok=True,
        task_id=str(task["task_id"]),
        status=str(task["status"]),  # type: ignore[arg-type]
        created_at=_iso_from_ts(task.get("created_ts")) or "",
        started_at=_iso_from_ts(task.get("started_ts")),
        finished_at=_iso_from_ts(task.get("finished_ts")),
        cancel_requested=bool(task.get("cancel_requested", False)),
        detail=str(task.get("detail", "")),
        save_name=str(task["save_name"]),
        fmt=str(task["fmt"]),
        image_url=task.get("image_url"),
        argv=list(task.get("argv", [])),
        error=task.get("error"),
    )


def _get_task_or_404(task_id: str) -> dict[str, Any]:
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        return dict(task)


def _update_task(task_id: str, **fields: Any) -> Optional[dict[str, Any]]:
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if task is None:
            return None
        task.update(fields)
        return dict(task)


def _set_task_terminal(task_id: str, status: TaskStatus, detail: str, error: Optional[str] = None) -> Optional[dict[str, Any]]:
    return _update_task(
        task_id,
        status=status,
        detail=detail,
        error=error,
        finished_ts=_now_ts(),
    )


def _cleanup_directory(
    root: Path,
    *,
    max_files: int,
    retention_seconds: int,
    max_total_bytes: int,
) -> dict[str, int]:
    now = _now_ts()
    files = _sorted_files(root)
    entries: list[tuple[Path, int, float]] = []
    before_bytes = 0
    for fp in files:
        try:
            st = fp.stat()
            size = int(st.st_size)
            mtime = float(st.st_mtime)
        except Exception:
            size = 0
            mtime = 0.0
        entries.append((fp, size, mtime))
        before_bytes += size

    deleted_files = 0
    deleted_bytes = 0
    kept: list[tuple[Path, int, float]] = []

    for idx, (fp, size, mtime) in enumerate(entries):
        delete_by_count = idx >= max_files
        delete_by_age = (now - mtime) > retention_seconds
        if delete_by_count or delete_by_age:
            if _delete_file_quiet(fp):
                deleted_files += 1
                deleted_bytes += size
            continue
        kept.append((fp, size, mtime))

    if max_total_bytes > 0:
        kept_bytes = sum(size for _, size, _ in kept)
        # kept 按 mtime 逆序（新->旧），从末尾删更符合“保留最近文件”的预期。
        for fp, size, _mtime in list(reversed(kept)):
            if kept_bytes <= max_total_bytes:
                break
            if _delete_file_quiet(fp):
                deleted_files += 1
                deleted_bytes += size
                kept_bytes -= size

    remaining_files = _sorted_files(root)
    after_bytes = _total_size_bytes(remaining_files)
    return {
        "deleted_files": deleted_files,
        "deleted_bytes": deleted_bytes,
        "before_files": len(entries),
        "before_bytes": before_bytes,
        "after_files": len(remaining_files),
        "after_bytes": after_bytes,
    }


def _cleanup_task_records() -> int:
    now = _now_ts()
    deleted = 0
    with TASK_LOCK:
        for task_id, task in list(TASKS.items()):
            status = str(task.get("status", ""))
            finished_ts = float(task.get("finished_ts") or task.get("created_ts") or now)
            if status in TERMINAL_TASK_STATES and (now - finished_ts) > TASK_RETENTION_SECONDS:
                TASKS.pop(task_id, None)
                deleted += 1

        if len(TASKS) <= TASK_MAX_RECORDS:
            return deleted

        def _remove_oldest(candidates: list[tuple[str, dict[str, Any]]]) -> int:
            removed = 0
            for task_id, _task in sorted(candidates, key=lambda item: float(item[1].get("finished_ts") or item[1].get("created_ts") or now)):
                if len(TASKS) <= TASK_MAX_RECORDS:
                    break
                TASKS.pop(task_id, None)
                removed += 1
            return removed

        terminal = [(tid, t) for tid, t in TASKS.items() if str(t.get("status")) in TERMINAL_TASK_STATES]
        deleted += _remove_oldest(terminal)
        if len(TASKS) > TASK_MAX_RECORDS:
            queued = [(tid, t) for tid, t in TASKS.items() if str(t.get("status")) == "queued"]
            deleted += _remove_oldest(queued)
    return deleted


def run_cleanup_policy(reason: str) -> dict[str, Any]:
    upload_cleanup = _cleanup_directory(
        UPLOAD_DIR,
        max_files=UPLOAD_MAX_FILES,
        retention_seconds=UPLOAD_RETENTION_SECONDS,
        max_total_bytes=UPLOAD_MAX_TOTAL_BYTES,
    )
    render_cleanup = _cleanup_directory(
        RENDER_DIR,
        max_files=RENDER_MAX_FILES,
        retention_seconds=RENDER_RETENTION_SECONDS,
        max_total_bytes=RENDER_MAX_TOTAL_BYTES,
    )
    deleted_tasks = _cleanup_task_records()
    CLEANUP_STATS.update(
        {
            "last_run_at": _iso_from_ts(_now_ts()) or "",
            "last_reason": reason,
            "deleted_uploads": upload_cleanup["deleted_files"],
            "deleted_renders": render_cleanup["deleted_files"],
            "deleted_upload_bytes": upload_cleanup["deleted_bytes"],
            "deleted_render_bytes": render_cleanup["deleted_bytes"],
            "deleted_tasks": deleted_tasks,
            "upload_files": upload_cleanup["after_files"],
            "upload_bytes": upload_cleanup["after_bytes"],
            "upload_quota_bytes": UPLOAD_MAX_TOTAL_BYTES,
            "render_files": render_cleanup["after_files"],
            "render_bytes": render_cleanup["after_bytes"],
            "render_quota_bytes": RENDER_MAX_TOTAL_BYTES,
        }
    )
    return dict(CLEANUP_STATS)


def _task_worker_loop(worker_name: str) -> None:
    while not SHUTDOWN_EVENT.is_set():
        try:
            task_id = TASK_QUEUE.get(timeout=0.5)
        except queue.Empty:
            continue
        try:
            snapshot = _get_task_or_404(task_id)
        except HTTPException:
            TASK_QUEUE.task_done()
            continue

        if snapshot.get("cancel_requested"):
            _set_task_terminal(task_id, status="cancelled", detail="任务在队列中已取消")
            TASK_QUEUE.task_done()
            continue

        _update_task(
            task_id,
            status="running",
            detail=f"任务运行中（{worker_name}）",
            started_ts=_now_ts(),
        )

        req = RenderRequest.model_validate(snapshot["request"])
        argv = list(snapshot.get("argv", []))

        try:
            resp = _execute_render_sync(req, save_name=str(snapshot["save_name"]), argv=argv)
            latest = _get_task_or_404(task_id)
            if latest.get("cancel_requested"):
                if resp.image_url:
                    outname = Path(resp.image_url).name
                    _delete_file_quiet(RENDER_DIR / outname)
                _set_task_terminal(task_id, status="cancelled", detail="任务已取消，已丢弃渲染结果")
            else:
                _update_task(
                    task_id,
                    status="success",
                    detail="渲染完成",
                    finished_ts=_now_ts(),
                    image_url=resp.image_url,
                    error=None,
                )
        except HTTPException as e:
            _set_task_terminal(task_id, status="failed", detail="渲染失败", error=str(e.detail))
        except Exception as e:
            _set_task_terminal(
                task_id,
                status="failed",
                detail="渲染失败",
                error=f"{e}\n{traceback.format_exc()}",
            )
        finally:
            TASK_QUEUE.task_done()
            run_cleanup_policy(reason="task-finished")


def _cleanup_worker_loop() -> None:
    while not SHUTDOWN_EVENT.wait(CLEANUP_INTERVAL_SECONDS):
        run_cleanup_policy(reason="periodic")


def _ensure_workers_started() -> None:
    if not TASK_WORKERS:
        for i in range(TASK_WORKER_COUNT):
            worker = threading.Thread(
                target=_task_worker_loop,
                args=(f"worker-{i+1}",),
                daemon=True,
                name=f"render-task-worker-{i+1}",
            )
            worker.start()
            TASK_WORKERS.append(worker)
    global CLEANUP_WORKER
    if CLEANUP_WORKER is None:
        CLEANUP_WORKER = threading.Thread(
            target=_cleanup_worker_loop,
            daemon=True,
            name="render-cleanup-worker",
        )
        CLEANUP_WORKER.start()


def _submit_render_task(req: RenderRequest) -> TaskSubmitResponse:
    save_name = f"web_{uuid4().hex[:10]}"
    argv = _build_argv(req, save_name)
    task_id = f"task_{uuid4().hex[:16]}"
    task = {
        "task_id": task_id,
        "status": "queued",
        "detail": "任务已提交，等待执行",
        "request": req.model_dump(mode="json"),
        "save_name": save_name,
        "fmt": req.fmt,
        "argv": argv,
        "image_url": None,
        "error": None,
        "cancel_requested": False,
        "created_ts": _now_ts(),
        "started_ts": None,
        "finished_ts": None,
    }
    with TASK_LOCK:
        TASKS[task_id] = task
    try:
        TASK_QUEUE.put_nowait(task_id)
    except queue.Full:
        with TASK_LOCK:
            TASKS.pop(task_id, None)
        raise HTTPException(status_code=503, detail="任务队列已满，请稍后重试")
    return TaskSubmitResponse(
        ok=True,
        task_id=task_id,
        status="queued",
        queue_size=TASK_QUEUE.qsize(),
        detail="任务提交成功",
    )


app = FastAPI(title="Research Draw Web API", version=APP_VERSION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)

if WEB_ASSETS_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(WEB_ASSETS_DIR)), name="assets")


@app.on_event("startup")
def on_startup() -> None:
    SHUTDOWN_EVENT.clear()
    _ensure_workers_started()
    run_cleanup_policy(reason="startup")


@app.on_event("shutdown")
def on_shutdown() -> None:
    SHUTDOWN_EVENT.set()
    for worker in TASK_WORKERS:
        worker.join(timeout=1.0)
    if CLEANUP_WORKER is not None:
        CLEANUP_WORKER.join(timeout=1.0)


@app.get("/api/health")
def health() -> dict[str, Any]:
    running = 0
    queued = 0
    with TASK_LOCK:
        for task in TASKS.values():
            st = str(task.get("status"))
            if st == "running":
                running += 1
            elif st == "queued":
                queued += 1
    return {
        "status": "ok",
        "version": __version__,
        "queue_size": TASK_QUEUE.qsize(),
        "tasks_running": running,
        "tasks_queued": queued,
    }


@app.get("/api/version", response_model=VersionResponse)
def get_version() -> VersionResponse:
    return VersionResponse(version=APP_VERSION)


@app.get("/api/maintenance/cleanup")
def get_cleanup_status() -> dict[str, Any]:
    return dict(CLEANUP_STATS)


@app.get("/api/plots")
def list_plots() -> Dict[str, list[str]]:
    return canonical_plots_by_group()


@app.get("/api/plot-registry")
def get_plot_registry() -> Dict[str, Any]:
    return plot_registry_payload()


@app.get("/api/contact-assets", response_model=ContactAssetResponse)
def list_contact_assets() -> ContactAssetResponse:
    if not CONTACT_ASSETS_DIR.exists():
        return ContactAssetResponse(items=[])

    items: list[ContactAssetItem] = []
    for path in sorted(CONTACT_ASSETS_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in CONTACT_IMAGE_SUFFIX:
            continue
        relative = path.relative_to(WEB_ASSETS_DIR)
        items.append(ContactAssetItem(name=path.stem, url=_asset_url(relative)))
    return ContactAssetResponse(items=items)


@app.get("/api/user-manual", response_model=UserManualResponse)
def get_user_manual() -> UserManualResponse:
    if not USER_MANUAL_FILE.exists():
        return UserManualResponse(title="用户手册页面", content="用户手册文件不存在。")
    content = USER_MANUAL_FILE.read_text(encoding="utf-8")
    return UserManualResponse(title="用户手册页面", content=content)


@app.post("/api/upload", response_model=UploadResponse)
def upload_data(file: UploadFile = File(...)) -> UploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in ALLOWED_UPLOAD_SUFFIX:
        raise HTTPException(status_code=400, detail=f"不支持的文件格式: {suffix}")

    file_id = f"{uuid4().hex}{suffix}"
    target = UPLOAD_DIR / file_id
    size = 0
    try:
        with target.open("wb") as out:
            chunk = file.file.read(1024 * 1024)
            while chunk:
                size += len(chunk)
                if UPLOAD_MAX_FILE_BYTES > 0 and size > UPLOAD_MAX_FILE_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=(
                            f"上传文件过大（{size} bytes），"
                            f"单文件上限 {UPLOAD_MAX_FILE_BYTES} bytes。"
                        ),
                    )
                out.write(chunk)
                chunk = file.file.read(1024 * 1024)
    except HTTPException:
        _delete_file_quiet(target)
        raise
    except Exception as e:
        _delete_file_quiet(target)
        raise HTTPException(status_code=500, detail=f"保存上传文件失败: {e}") from e

    if UPLOAD_MAX_TOTAL_BYTES > 0 and size > UPLOAD_MAX_TOTAL_BYTES:
        _delete_file_quiet(target)
        raise HTTPException(
            status_code=413,
            detail=(
                f"上传文件过大（{size} bytes），"
                f"超过上传目录总配额 {UPLOAD_MAX_TOTAL_BYTES} bytes。"
            ),
        )

    columns, preview_rows = _inspect_upload_file(target)
    run_cleanup_policy(reason="upload-create")
    return UploadResponse(
        file_id=file_id,
        filename=file.filename,
        size=size,
        columns=columns,
        preview_rows=preview_rows,
    )


@app.get("/api/uploads", response_model=UploadListResponse)
def list_upload_files(page: int = 1, page_size: int = 50) -> UploadListResponse:
    files = _sorted_files(UPLOAD_DIR)
    usage_bytes = _total_size_bytes(files)
    page_files, meta = _paginate_list(files, page=page, page_size=page_size)
    items = [
        UploadFileItem(
            file_id=p.name,
            size=p.stat().st_size,
            modified_at=_mtime_iso(p),
        )
        for p in page_files
    ]
    return UploadListResponse(
        items=items,
        page=int(meta["page"]),
        page_size=int(meta["page_size"]),
        total=int(meta["total"]),
        total_pages=int(meta["total_pages"]),
        has_next=bool(meta["has_next"]),
        usage_bytes=usage_bytes,
        quota_bytes=UPLOAD_MAX_TOTAL_BYTES,
    )


@app.get("/api/uploads/{file_id}/inspect", response_model=UploadResponse)
def inspect_upload_file(file_id: str) -> UploadResponse:
    fp = _safe_upload_file(file_id)
    columns, preview_rows = _inspect_upload_file(fp)
    return UploadResponse(
        file_id=fp.name,
        filename=fp.name,
        size=fp.stat().st_size,
        columns=columns,
        preview_rows=preview_rows,
    )


@app.delete("/api/uploads/{file_id}", response_model=DeleteResponse)
def delete_upload_file(file_id: str) -> DeleteResponse:
    fp = _safe_upload_file(file_id)
    fp.unlink(missing_ok=False)
    run_cleanup_policy(reason="upload-delete")
    return DeleteResponse(ok=True, deleted=1, detail=f"已删除上传文件: {fp.name}")


@app.delete("/api/uploads", response_model=DeleteResponse)
def clear_upload_files() -> DeleteResponse:
    files = _sorted_files(UPLOAD_DIR)
    deleted = 0
    for fp in files:
        try:
            fp.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            continue
    run_cleanup_policy(reason="upload-clear")
    return DeleteResponse(ok=True, deleted=deleted, detail=f"已清空上传文件: {deleted} 个")


@app.post("/api/tasks/render/submit", response_model=TaskSubmitResponse)
def submit_render_task(req: RenderRequest) -> TaskSubmitResponse:
    _ensure_workers_started()
    return _submit_render_task(req)


@app.get("/api/tasks/{task_id}", response_model=TaskStatusResponse)
def get_task_status(task_id: str) -> TaskStatusResponse:
    task = _get_task_or_404(task_id)
    return _task_to_response(task)


@app.get("/api/tasks", response_model=TaskListResponse)
def list_tasks(limit: int = 100, status: Optional[TaskStatus] = None) -> TaskListResponse:
    cap = max(1, min(int(limit or 100), 500))
    with TASK_LOCK:
        items = list(TASKS.values())
    if status:
        items = [it for it in items if str(it.get("status")) == status]
    items.sort(key=lambda it: float(it.get("created_ts") or 0.0), reverse=True)
    return TaskListResponse(items=[_task_to_response(it) for it in items[:cap]])


@app.post("/api/tasks/{task_id}/cancel", response_model=TaskStatusResponse)
def cancel_task(task_id: str) -> TaskStatusResponse:
    with TASK_LOCK:
        task = TASKS.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail=f"任务不存在: {task_id}")
        status = str(task.get("status"))
        if status in TERMINAL_TASK_STATES:
            return _task_to_response(dict(task))
        task["cancel_requested"] = True
        if status == "queued":
            task["status"] = "cancelled"
            task["detail"] = "任务在队列中已取消"
            task["finished_ts"] = _now_ts()
        else:
            task["detail"] = "任务正在运行，已标记取消（将在可中断点结束）"
        updated = dict(task)
    return _task_to_response(updated)


@app.post("/api/render", response_model=RenderResponse)
def render(req: RenderRequest) -> RenderResponse:
    # Legacy synchronous endpoint kept for backward compatibility.
    save_name = f"web_{uuid4().hex[:10]}"
    argv = _build_argv(req, save_name)
    resp = _execute_render_sync(req, save_name=save_name, argv=argv)
    run_cleanup_policy(reason="render-sync")
    return resp


@app.get("/api/renders", response_model=RenderListResponse)
def list_render_files(page: int = 1, page_size: int = 50) -> RenderListResponse:
    files = _sorted_files(RENDER_DIR)
    usage_bytes = _total_size_bytes(files)
    page_files, meta = _paginate_list(files, page=page, page_size=page_size)
    items = [
        RenderFileItem(
            filename=p.name,
            size=p.stat().st_size,
            modified_at=_mtime_iso(p),
            image_url=f"/api/files/{p.name}",
        )
        for p in page_files
    ]
    return RenderListResponse(
        items=items,
        page=int(meta["page"]),
        page_size=int(meta["page_size"]),
        total=int(meta["total"]),
        total_pages=int(meta["total_pages"]),
        has_next=bool(meta["has_next"]),
        usage_bytes=usage_bytes,
        quota_bytes=RENDER_MAX_TOTAL_BYTES,
    )


@app.delete("/api/renders/{filename}", response_model=DeleteResponse)
def delete_render_file(filename: str) -> DeleteResponse:
    fp = _safe_render_file(filename)
    fp.unlink(missing_ok=False)
    run_cleanup_policy(reason="render-delete")
    return DeleteResponse(ok=True, deleted=1, detail=f"已删除渲染文件: {fp.name}")


@app.delete("/api/renders", response_model=DeleteResponse)
def clear_render_files() -> DeleteResponse:
    files = _sorted_files(RENDER_DIR)
    deleted = 0
    for fp in files:
        try:
            fp.unlink(missing_ok=True)
            deleted += 1
        except Exception:
            continue
    run_cleanup_policy(reason="render-clear")
    return DeleteResponse(ok=True, deleted=deleted, detail=f"已清空渲染文件: {deleted} 个")


@app.get("/api/files/{filename}")
def get_render_file(filename: str):
    fp = _safe_render_file(filename)
    return FileResponse(fp)
