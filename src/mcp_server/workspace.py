"""Workspace-scoped file management for the local MCP server."""

from __future__ import annotations

import os
import re
import base64
import binascii
import json
import math
import shutil
import zlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


DEFAULT_WORKSPACE_ENV = "RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE"
WORKSPACES_ENV = "RESEARCH_DRAW_MCP_WORKSPACES"
HOST_WORKSPACES_ROOT_ENV = "RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT"
HOST_WORKSPACES_MOUNT_ENV = "RESEARCH_DRAW_MCP_HOST_WORKSPACES_MOUNT"
ALLOWED_DATA_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}
ALLOWED_RENDER_SUFFIXES = {".png", ".svg", ".pdf"}
DEFAULT_CHUNK_UPLOAD_MB = 200
MAX_UPLOAD_CHUNK_BYTES = 4 * 1024 * 1024
DEFAULT_MODEL_UPLOAD_CHUNK_BYTES = 8 * 1024
MAX_UPLOAD_CHUNKS = 16_384
MAX_PENDING_UPLOADS = 8
UPLOAD_TTL_SECONDS = 24 * 60 * 60


class WorkspaceError(ValueError):
    """Raised when a requested workspace operation is invalid or unsafe."""


@dataclass(frozen=True)
class WorkspaceLocation:
    """The runtime mount path and corresponding host path for one workspace."""

    runtime_root: Path
    host_root: Path


def configured_workspaces() -> dict[str, str]:
    """Read the administrator-defined logical workspace allowlist."""
    raw = os.getenv(WORKSPACES_ENV, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WorkspaceError(f"{WORKSPACES_ENV} 必须是 JSON 对象。") from exc
    if not isinstance(parsed, dict):
        raise WorkspaceError(f"{WORKSPACES_ENV} 必须是逻辑工作区名到绝对路径的 JSON 对象。")

    workspaces: dict[str, str] = {}
    for raw_name, raw_path in parsed.items():
        name = str(raw_name).strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", name):
            raise WorkspaceError(f"非法逻辑工作区名：{name!r}。")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise WorkspaceError(f"逻辑工作区 {name!r} 必须映射到非空绝对路径。")
        path = Path(raw_path.strip()).expanduser()
        if not path.is_absolute():
            raise WorkspaceError(f"逻辑工作区 {name!r} 的路径必须是绝对路径。")
        workspaces[name] = str(path)
    return workspaces


def _default_workspace_selector() -> str | None:
    return os.getenv(DEFAULT_WORKSPACE_ENV, "").strip() or None


def list_configured_workspaces() -> list[dict[str, Any]]:
    """List configured logical names without disclosing host filesystem paths."""
    workspaces = configured_workspaces()
    default = _default_workspace_selector()
    if default and default not in workspaces:
        raise WorkspaceError(
            f"默认逻辑工作区 {default!r} 未在 {WORKSPACES_ENV} 中配置。"
        )
    for path in workspaces.values():
        resolve_workspace_location(path)
    return [
        {"name": name, "is_default": name == default}
        for name in sorted(workspaces)
    ]


def resolve_workspace_selector(
    workspace: str | None = None,
) -> WorkspaceLocation:
    """Resolve a logical workspace name or the configured default."""
    workspaces = configured_workspaces()
    default = _default_workspace_selector()
    if workspace:
        name = str(workspace).strip()
        if name in workspaces:
            selected = workspaces[name]
        else:
            known = ", ".join(sorted(workspaces)) or "（未配置逻辑工作区）"
            raise WorkspaceError(f"未知逻辑工作区 {name!r}。可用工作区：{known}。")
        return resolve_workspace_location(selected)

    if not default:
        raise WorkspaceError(
            f"未配置默认工作区。请设置 {DEFAULT_WORKSPACE_ENV}，或在工具调用中传入 workspace。"
        )
    if default not in workspaces:
        raise WorkspaceError(f"默认逻辑工作区 {default!r} 未在 {WORKSPACES_ENV} 中配置。")
    return resolve_workspace_location(workspaces[default])


def resolve_workspace_location(configured_path: str | Path) -> WorkspaceLocation:
    """Resolve a workspace under the configured common host root."""
    requested = Path(configured_path).expanduser()
    if ".." in requested.parts:
        raise WorkspaceError("工作区配置路径不能包含 .. 路径段。")

    host_root_raw = os.getenv(HOST_WORKSPACES_ROOT_ENV)
    mount_root_raw = os.getenv(HOST_WORKSPACES_MOUNT_ENV)
    transport = os.getenv("RESEARCH_DRAW_MCP_TRANSPORT", "stdio").strip().lower()
    host_root = (
        Path(os.path.normpath(str(Path(host_root_raw).expanduser())))
        if host_root_raw else None
    )
    if host_root is not None and not host_root.is_absolute():
        raise WorkspaceError(f"{HOST_WORKSPACES_ROOT_ENV} 必须是绝对路径。")
    if not requested.is_absolute():
        raise WorkspaceError(f"{WORKSPACES_ENV} 中的工作区目录必须是绝对路径。")
    if transport == "streamable-http" and (not host_root_raw or not mount_root_raw):
        raise WorkspaceError(
            f"HTTP MCP 必须配置 {HOST_WORKSPACES_ROOT_ENV} 和 {HOST_WORKSPACES_MOUNT_ENV}，"
            "并将共同宿主机工作区根目录 bind mount 到容器。"
        )

    if host_root is not None:
        # The host root is intentionally normalized lexically: its original host
        # path is not visible from inside the container.
        normalized_request = Path(os.path.normpath(str(requested)))
        try:
            relative = normalized_request.relative_to(host_root)
        except ValueError as exc:
            raise WorkspaceError(
                f"工作区目录必须位于允许的宿主机根目录 {host_root} 内。"
            ) from exc
        if not relative.parts:
            raise WorkspaceError("工作区目录必须是共同根目录下的具体目录。")

        if mount_root_raw:
            mount_root = Path(mount_root_raw).expanduser().resolve(strict=True)
            runtime_root = (mount_root / relative).resolve(strict=True)
            if not runtime_root.is_relative_to(mount_root):
                raise WorkspaceError("工作区目录解析后越出了容器挂载根目录。")
            host_workspace = host_root / relative
        else:
            # Native stdio deployments access the host filesystem directly.
            runtime_root = normalized_request.resolve(strict=True)
            host_workspace = runtime_root
            resolved_host_root = host_root.resolve(strict=True)
            if not runtime_root.is_relative_to(resolved_host_root):
                raise WorkspaceError("工作区目录通过符号链接越出了允许的宿主机根目录。")
    else:
        if transport == "streamable-http":
            raise WorkspaceError("HTTP MCP 未配置逻辑工作区映射所需的宿主机根目录。")
        runtime_root = requested.resolve(strict=True)
        host_workspace = runtime_root

    if not runtime_root.is_dir():
        raise WorkspaceError(f"配置的工作区不存在或不是目录：{configured_path}")
    return WorkspaceLocation(runtime_root=runtime_root, host_root=host_workspace)


class MCPWorkspace:
    """Manage MCP inputs and outputs under an explicitly configured workspace."""

    def __init__(
        self,
        workspace_root: str | Path | None,
        project_root: Path,
        *,
        display_root: str | Path | None = None,
        shared_workspace_root: str | Path | None = None,
        display_shared_workspace_root: str | Path | None = None,
    ) -> None:
        if workspace_root is None:
            try:
                location = resolve_workspace_selector()
            except WorkspaceError as exc:
                raise WorkspaceError(
                    f"未能解析 MCP 默认工作区。请设置 {DEFAULT_WORKSPACE_ENV}，"
                    f"并在 {WORKSPACES_ENV} 中配置对应目录。原因：{exc}"
                ) from exc
            workspace_root = location.runtime_root
            if display_root is None:
                display_root = location.host_root
        raw_root = workspace_root
        if not raw_root:
            raise WorkspaceError(
                f"本地 MCP 未配置工作区。请设置环境变量 {DEFAULT_WORKSPACE_ENV}，"
                "并指向项目目录以外的本地工作区。"
            )

        root = Path(raw_root).expanduser().resolve()
        if not root.exists() or not root.is_dir():
            raise WorkspaceError(f"MCP 工作区不存在或不是目录：{root}")

        project = project_root.expanduser().resolve()
        if root == project or root.is_relative_to(project):
            raise WorkspaceError(
                f"MCP 工作区不能是项目根目录或其子目录：{project}。"
                "请配置项目目录以外的工作区。"
            )

        self.root = root
        self.display_root = Path(display_root or root).expanduser().resolve(strict=False)
        shared_root = Path(shared_workspace_root or root).expanduser().resolve(strict=True)
        if not shared_root.is_dir():
            raise WorkspaceError(f"逻辑工作区不存在或不是目录：{shared_root}")
        if shared_root == project or shared_root.is_relative_to(project):
            raise WorkspaceError(
                f"逻辑工作区不能是项目根目录或其子目录：{project}。"
            )
        if not root.is_relative_to(shared_root):
            raise WorkspaceError("会话工作区必须位于对应逻辑工作区目录内。")
        self.shared_workspace_root = shared_root
        self.display_shared_workspace_root = Path(
            display_shared_workspace_root or shared_root
        ).expanduser().resolve(strict=False)
        self.project_root = project
        self.input_dir = self._ensure_workspace_dir(Path("inputs") / "mcp")
        self.output_dir = self._ensure_workspace_dir(Path("outputs") / "mcp")

    def _ensure_workspace_dir(self, relative_path: Path) -> Path:
        current = self.root
        for part in relative_path.parts:
            candidate = current / part
            candidate.mkdir(exist_ok=True)
            resolved = self._ensure_inside_workspace(candidate)
            if not resolved.is_dir():
                raise WorkspaceError(f"MCP 工作区路径不是目录：{resolved}")
            if resolved == self.project_root or resolved.is_relative_to(self.project_root):
                raise WorkspaceError("MCP 输入和输出目录不能位于项目根目录内。")
            current = resolved
        return current

    def _ensure_inside_workspace(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError(f"路径必须位于 MCP 工作区内：{resolved}") from exc
        return resolved

    def workspace_relative_path(self, path: str | Path) -> str:
        """Return a path relative to the configured workspace root."""
        resolved = self._ensure_inside_workspace(Path(path))
        return resolved.relative_to(self.root).as_posix()

    def public_path(self, path: str | Path) -> str:
        """Return the path as it appears on the host session workspace."""
        resolved = self._ensure_inside_workspace(Path(path))
        return str(self.display_root / resolved.relative_to(self.root))

    def job_store_path(self) -> Path:
        """Return a private, workspace-scoped SQLite file for render jobs."""
        job_dir = self._ensure_workspace_dir(Path(".mcp-jobs"))
        if job_dir.is_symlink():
            raise WorkspaceError("MCP 作业目录不能是符号链接。")
        job_dir.chmod(0o700)
        database = self._ensure_inside_workspace(job_dir / "jobs.sqlite3")
        if database.is_symlink():
            raise WorkspaceError("MCP 作业数据库不能是符号链接。")
        return database

    def resolve_workspace_file(self, raw_path: str | Path, *, must_exist: bool = True) -> Path:
        """Resolve a file path while keeping it inside the configured workspace."""
        candidate = Path(raw_path).expanduser()
        if candidate.is_absolute():
            for display_base in (self.display_root, self.root):
                try:
                    relative = candidate.relative_to(display_base)
                except ValueError:
                    continue
                candidate = self.root / relative
                break
            else:
                raise WorkspaceError(f"文件路径必须位于当前会话工作区内：{raw_path}")
        else:
            managed_candidate = self.input_dir / candidate
            candidate = managed_candidate if managed_candidate.exists() else self.root / candidate

        try:
            resolved = candidate.resolve(strict=must_exist)
        except OSError as exc:
            raise WorkspaceError(f"无法访问工作区文件：{raw_path}") from exc

        self._ensure_inside_workspace(resolved)
        if must_exist and (not resolved.exists() or not resolved.is_file()):
            raise WorkspaceError(f"工作区文件不存在：{resolved}")
        return resolved

    def resolve_import_source_file(self, raw_path: str | Path) -> Path:
        """Resolve an import source from this session or the shared logical workspace.

        The shared root enables local MCP clients to pass a short relative path
        instead of copying file bytes through a model-generated Base64 argument.
        MCP-managed session internals remain inaccessible through this route.
        """
        raw = Path(raw_path).expanduser()
        allowed_roots = (
            (self.display_root, self.root),
            (self.display_shared_workspace_root, self.shared_workspace_root),
            (self.root, self.root),
            (self.shared_workspace_root, self.shared_workspace_root),
        )

        if raw.is_absolute():
            candidate: Path | None = None
            for display_base, runtime_base in allowed_roots:
                try:
                    relative = raw.relative_to(display_base)
                except ValueError:
                    continue
                candidate = runtime_base / relative
                break
            if candidate is None:
                raise WorkspaceError(
                    "source_path 必须位于当前会话目录或所选逻辑工作区目录内。"
                )
        else:
            possible = (
                self.input_dir / raw,
                self.root / raw,
                self.shared_workspace_root / raw,
            )
            candidate = next((path for path in possible if os.path.lexists(path)), None)
            if candidate is None:
                raise WorkspaceError(
                    f"工作区文件不存在：{raw_path}。可从当前会话目录或逻辑工作区根目录导入。"
                )

        try:
            resolved = candidate.resolve(strict=True)
        except OSError as exc:
            raise WorkspaceError(f"无法访问工作区文件：{raw_path}") from exc

        if not resolved.is_file():
            raise WorkspaceError(f"工作区文件不存在或不是普通文件：{raw_path}")
        in_session = resolved.is_relative_to(self.root)
        in_shared = resolved.is_relative_to(self.shared_workspace_root)
        if not (in_session or in_shared):
            raise WorkspaceError("导入源文件通过符号链接越出了允许的工作区目录。")
        if in_shared and not in_session:
            relative = resolved.relative_to(self.shared_workspace_root)
            private_roots = {".mcp-sessions", ".mcp-upload-staging", ".mcp-jobs"}
            if relative.parts and relative.parts[0] in private_roots:
                raise WorkspaceError("不能从 MCP 管理的会话私有目录导入文件。")
        return resolved

    def resolve_data_file(self, file_id: str) -> Path:
        """Resolve an imported file by its opaque workspace-local ID."""
        if not file_id or Path(file_id).name != file_id or "/" in file_id or "\\" in file_id:
            raise WorkspaceError("file_id 必须是 list_workspace_files 返回的文件标识。")
        path = (self.input_dir / file_id).resolve(strict=True)
        self._ensure_inside_workspace(path)
        if not path.is_file() or path.suffix.lower() not in ALLOWED_DATA_SUFFIXES:
            raise WorkspaceError(f"不支持该工作区数据文件：{file_id}")
        return path

    def import_data_file(self, source_path: str) -> dict[str, Any]:
        source = self.resolve_import_source_file(source_path)
        suffix = source.suffix.lower()
        if suffix not in ALLOWED_DATA_SUFFIXES:
            allowed = ", ".join(sorted(ALLOWED_DATA_SUFFIXES))
            raise WorkspaceError(f"不支持的文件格式 {suffix or '(无扩展名)'}；支持：{allowed}")

        try:
            max_size_mb = max(1, int(os.getenv("RESEARCH_DRAW_MCP_MAX_IMPORT_MB", "200")))
        except ValueError:
            max_size_mb = 200
        max_size = max_size_mb * 1024 * 1024
        if source.stat().st_size > max_size:
            raise WorkspaceError(f"文件超过单文件上限 {max_size_mb} MB。")

        display_name = source.name
        safe_stem = re.sub(r"[^\w.-]+", "_", source.stem, flags=re.UNICODE).strip("._")
        if not safe_stem:
            safe_stem = "data"
        safe_name = f"{safe_stem}{suffix}"
        file_id = f"{uuid4().hex[:12]}_{safe_name}"
        target = self._ensure_inside_workspace(self.input_dir / file_id)

        copied_size = 0
        try:
            with source.open("rb") as src, target.open("xb") as dst:
                while chunk := src.read(1024 * 1024):
                    copied_size += len(chunk)
                    if copied_size > max_size:
                        raise WorkspaceError(f"文件超过单文件上限 {max_size_mb} MB。")
                    dst.write(chunk)
        except Exception:
            target.unlink(missing_ok=True)
            raise

        return {
            "success": True,
            "file_id": file_id,
            "filename": display_name,
            "size": copied_size,
            "path": self.public_path(target),
            "workspace_relative_path": self.workspace_relative_path(target),
        }

    def upload_data_file(self, filename: str, content_base64: str) -> dict[str, Any]:
        """Save a bounded, base64-encoded table uploaded by a remote MCP client."""
        if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise WorkspaceError("filename 只能包含文件名，不能包含目录路径。")
        if len(filename.encode("utf-8")) > 180 or any(ord(char) < 32 for char in filename):
            raise WorkspaceError("filename 过长或包含控制字符。")

        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_DATA_SUFFIXES:
            allowed = ", ".join(sorted(ALLOWED_DATA_SUFFIXES))
            raise WorkspaceError(f"不支持的文件格式 {suffix or '(无扩展名)'}；支持：{allowed}")

        try:
            max_size_mb = max(1, int(os.getenv("RESEARCH_DRAW_MCP_MAX_UPLOAD_MB", "32")))
        except ValueError:
            max_size_mb = 32
        max_size = max_size_mb * 1024 * 1024
        if len(content_base64) > ((max_size + 2) // 3) * 4:
            raise WorkspaceError(f"文件超过远程上传上限 {max_size_mb} MB。")

        try:
            content = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise WorkspaceError("content_base64 必须是有效的标准 Base64 字符串。") from exc
        if not content:
            raise WorkspaceError("不能上传空文件。")
        if len(content) > max_size:
            raise WorkspaceError(f"文件超过远程上传上限 {max_size_mb} MB。")

        safe_stem = re.sub(r"[^\w.-]+", "_", Path(filename).stem, flags=re.UNICODE).strip("._")
        if not safe_stem:
            safe_stem = "data"
        file_id = f"{uuid4().hex[:12]}_{safe_stem}{suffix}"
        target = self._ensure_inside_workspace(self.input_dir / file_id)
        try:
            with target.open("xb") as destination:
                destination.write(content)
        except Exception:
            target.unlink(missing_ok=True)
            raise

        return {
            "success": True,
            "file_id": file_id,
            "filename": Path(filename).name,
            "size": len(content),
            "path": self.public_path(target),
            "workspace_relative_path": self.workspace_relative_path(target),
        }

    @staticmethod
    def _validate_upload_filename(filename: str) -> tuple[str, str]:
        if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
            raise WorkspaceError("filename 只能包含文件名，不能包含目录路径。")
        if len(filename.encode("utf-8")) > 180 or any(ord(char) < 32 for char in filename):
            raise WorkspaceError("filename 过长或包含控制字符。")
        suffix = Path(filename).suffix.lower()
        if suffix not in ALLOWED_DATA_SUFFIXES:
            allowed = ", ".join(sorted(ALLOWED_DATA_SUFFIXES))
            raise WorkspaceError(f"不支持的文件格式 {suffix or '(无扩展名)'}；支持：{allowed}")
        safe_stem = re.sub(r"[^\w.-]+", "_", Path(filename).stem, flags=re.UNICODE).strip("._") or "data"
        return safe_stem, suffix

    def _upload_staging_dir(self) -> Path:
        return self._ensure_workspace_dir(Path(".mcp-upload-staging"))

    @staticmethod
    def _validate_upload_id(upload_id: str) -> str:
        if not re.fullmatch(r"[0-9a-f]{32}", str(upload_id or "")):
            raise WorkspaceError("upload_id 无效；请从 begin_data_upload 的结果中获取。")
        return upload_id

    def _load_upload_state(self, upload_id: str) -> tuple[Path, dict[str, Any]]:
        safe_id = self._validate_upload_id(upload_id)
        staging = self._upload_staging_dir().resolve(strict=True)
        upload_dir = self._ensure_inside_workspace(staging / safe_id)
        if upload_dir.parent != staging or upload_dir.is_symlink() or not upload_dir.is_dir():
            raise WorkspaceError("上传任务目录无效。")
        state_path = upload_dir / "upload.json"
        if state_path.is_symlink():
            raise WorkspaceError("上传任务状态文件无效。")
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkspaceError("上传任务不存在、已过期或状态文件损坏。") from exc
        if not isinstance(state, dict) or state.get("upload_id") != safe_id:
            raise WorkspaceError("上传任务状态无效。")
        try:
            total_size = int(state["total_size"])
            chunk_size = int(state["chunk_size"])
            chunk_count = int(state["chunk_count"])
            max_size_mb = max(
                1,
                int(os.getenv("RESEARCH_DRAW_MCP_MAX_CHUNKED_UPLOAD_MB", str(DEFAULT_CHUNK_UPLOAD_MB))),
            )
        except (KeyError, TypeError, ValueError):
            raise WorkspaceError("上传任务状态参数无效。") from None
        if (
            total_size <= 0
            or total_size > max_size_mb * 1024 * 1024
            or not 1 <= chunk_size <= MAX_UPLOAD_CHUNK_BYTES
            or not 1 <= chunk_count <= MAX_UPLOAD_CHUNKS
            or chunk_count != math.ceil(total_size / chunk_size)
        ):
            raise WorkspaceError("上传任务大小或分块状态不符合服务端限制。")
        return upload_dir, state

    def _prune_expired_uploads(self) -> None:
        staging = self._upload_staging_dir()
        now = datetime.now().timestamp()
        for entry in staging.iterdir():
            if entry.is_symlink() or not entry.is_dir():
                continue
            try:
                if now - entry.stat().st_mtime > UPLOAD_TTL_SECONDS:
                    shutil.rmtree(entry)
            except OSError:
                continue

    def begin_data_upload(
        self,
        filename: str,
        total_size: int,
        chunk_size: int = DEFAULT_MODEL_UPLOAD_CHUNK_BYTES,
    ) -> dict[str, Any]:
        """Create an isolated staging area for a multi-request file upload."""
        safe_stem, suffix = self._validate_upload_filename(filename)
        try:
            total_size = int(total_size)
            chunk_size = int(chunk_size)
            max_size_mb = max(1, int(os.getenv("RESEARCH_DRAW_MCP_MAX_CHUNKED_UPLOAD_MB", str(DEFAULT_CHUNK_UPLOAD_MB))))
        except (TypeError, ValueError):
            raise WorkspaceError("total_size、chunk_size 和上传上限必须是整数。") from None
        if total_size <= 0:
            raise WorkspaceError("total_size 必须大于 0。")
        if total_size > max_size_mb * 1024 * 1024:
            raise WorkspaceError(f"文件超过分块上传上限 {max_size_mb} MB。")
        if not 1 <= chunk_size <= MAX_UPLOAD_CHUNK_BYTES:
            raise WorkspaceError("chunk_size 必须在 1 字节至 4 MiB 之间。")
        chunk_count = math.ceil(total_size / chunk_size)
        if chunk_count > MAX_UPLOAD_CHUNKS:
            minimum_recommended = math.ceil(total_size / MAX_UPLOAD_CHUNKS)
            raise WorkspaceError(
                f"文件需要超过分块数量上限 {MAX_UPLOAD_CHUNKS}；请将 chunk_size 增大到至少 "
                f"{minimum_recommended} 字节。"
            )

        self._prune_expired_uploads()
        staging = self._upload_staging_dir()
        active = [path for path in staging.iterdir() if path.is_dir() and not path.is_symlink()]
        if len(active) >= MAX_PENDING_UPLOADS:
            raise WorkspaceError(f"当前会话最多同时进行 {MAX_PENDING_UPLOADS} 个分块上传。")
        active_bytes = 0
        for active_dir in active:
            try:
                active_state = json.loads((active_dir / "upload.json").read_text(encoding="utf-8"))
                active_bytes += max(0, int(active_state.get("total_size", 0)))
            except (OSError, TypeError, ValueError, json.JSONDecodeError):
                continue
        if active_bytes + total_size > 2 * max_size_mb * 1024 * 1024:
            raise WorkspaceError("当前会话待完成上传的总大小超过服务端暂存上限。")

        upload_id = uuid4().hex
        upload_dir = self._ensure_inside_workspace(staging / upload_id)
        upload_dir.mkdir(mode=0o700)
        state = {
            "upload_id": upload_id,
            "filename": Path(filename).name,
            "safe_stem": safe_stem,
            "suffix": suffix,
            "total_size": total_size,
            "chunk_size": chunk_size,
            "chunk_count": chunk_count,
            "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        }
        (upload_dir / "upload.json").write_text(
            json.dumps(state, ensure_ascii=False), encoding="utf-8"
        )
        return {
            "success": True,
            "upload_id": upload_id,
            "filename": state["filename"],
            "total_size": total_size,
            "chunk_size": chunk_size,
            "chunk_count": state["chunk_count"],
            "max_chunk_bytes": MAX_UPLOAD_CHUNK_BYTES,
            "max_chunk_count": MAX_UPLOAD_CHUNKS,
        }

    def upload_data_chunk(
        self,
        upload_id: str,
        chunk_index: int,
        content_base64: str,
        content_encoding: str = "identity",
    ) -> dict[str, Any]:
        """Store one validated Base64 chunk without buffering the whole file.

        Chunks may be independently gzip-compressed to reduce tool arguments.
        Small chunks are recommended for model-facing clients because gzip may
        not reduce high-entropy data. Chunk sizes describe uncompressed bytes.
        """
        upload_dir, state = self._load_upload_state(upload_id)
        try:
            chunk_index = int(chunk_index)
        except (TypeError, ValueError):
            raise WorkspaceError("chunk_index 必须是整数。") from None
        chunk_count = int(state.get("chunk_count", 0))
        chunk_size = int(state.get("chunk_size", 0))
        total_size = int(state.get("total_size", 0))
        if not 0 <= chunk_index < chunk_count:
            raise WorkspaceError(f"chunk_index 必须在 0 到 {chunk_count - 1} 之间。")
        if not isinstance(content_base64, str):
            raise WorkspaceError("content_base64 必须是标准 Base64 字符串。")
        encoding = str(content_encoding or "identity").strip().lower()
        if encoding not in {"identity", "gzip"}:
            raise WorkspaceError("content_encoding 仅支持 identity 或 gzip。")
        expected_size = (
            chunk_size if chunk_index < chunk_count - 1
            else total_size - chunk_size * (chunk_count - 1)
        )
        max_encoded_bytes = expected_size
        if encoding == "gzip":
            # Gzip can be slightly larger than incompressible input. Bound the
            # compressed payload while leaving room for DEFLATE framing.
            max_encoded_bytes += max(1024, expected_size // 100 + 64)
        if len(content_base64) > ((max_encoded_bytes + 2) // 3) * 4:
            raise WorkspaceError("当前分块编码长度超过预期，请检查 chunk_index 与分块大小。")
        try:
            encoded_content = base64.b64decode(content_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise WorkspaceError("content_base64 必须是有效的标准 Base64 字符串。") from exc
        if encoding == "gzip":
            try:
                decompressor = zlib.decompressobj(16 + zlib.MAX_WBITS)
                content = decompressor.decompress(encoded_content, expected_size + 1)
            except zlib.error as exc:
                raise WorkspaceError("gzip 分块无效或已损坏。") from exc
            if (
                len(content) > expected_size
                or decompressor.unconsumed_tail
                or not decompressor.eof
                or decompressor.unused_data
            ):
                raise WorkspaceError("gzip 分块解压后超过预期大小，或数据流不完整。")
        else:
            content = encoded_content
        if len(content) != expected_size:
            raise WorkspaceError(f"第 {chunk_index} 块应为 {expected_size} 字节，收到 {len(content)} 字节。")

        chunk_path = upload_dir / f"chunk-{chunk_index:08d}.part"
        try:
            with chunk_path.open("xb") as chunk_file:
                chunk_file.write(content)
        except FileExistsError as exc:
            raise WorkspaceError(f"第 {chunk_index} 块已上传；重复分块不会覆盖已有内容。") from exc
        received = sum(
            path.stat().st_size
            for path in upload_dir.glob("chunk-*.part")
            if path.is_file() and not path.is_symlink()
        )
        return {
            "success": True,
            "upload_id": upload_id,
            "chunk_index": chunk_index,
            "chunk_count": chunk_count,
            "received_bytes": received,
            "total_size": total_size,
            "content_encoding": encoding,
        }

    def complete_data_upload(self, upload_id: str) -> dict[str, Any]:
        """Validate all chunks, atomically publish the assembled table, and clear staging."""
        upload_dir, state = self._load_upload_state(upload_id)
        chunk_count = int(state.get("chunk_count", 0))
        total_size = int(state.get("total_size", 0))
        filename = str(state.get("filename", ""))
        safe_stem, suffix = self._validate_upload_filename(filename)
        if state.get("suffix") != suffix or state.get("safe_stem") != safe_stem:
            raise WorkspaceError("上传任务文件名状态无效。")
        chunks = [upload_dir / f"chunk-{index:08d}.part" for index in range(chunk_count)]
        missing = [index for index, path in enumerate(chunks) if not path.is_file() or path.is_symlink()]
        if missing:
            return {
                "success": False,
                "stage": "upload_incomplete",
                "message": "仍有分块未上传。",
                "missing_chunks": missing[:100],
                "missing_count": len(missing),
            }

        file_id = f"{uuid4().hex[:12]}_{safe_stem}{suffix}"
        target = self._ensure_inside_workspace(self.input_dir / file_id)
        temporary = self._ensure_inside_workspace(self.input_dir / f".{file_id}.assembling")
        copied_size = 0
        try:
            with temporary.open("xb") as output:
                for chunk_path in chunks:
                    self._ensure_inside_workspace(chunk_path)
                    with chunk_path.open("rb") as source:
                        while block := source.read(1024 * 1024):
                            copied_size += len(block)
                            if copied_size > total_size:
                                raise WorkspaceError("分块总大小超过声明的 total_size。")
                            output.write(block)
            if copied_size != total_size:
                raise WorkspaceError(f"组装文件应为 {total_size} 字节，实际为 {copied_size} 字节。")
            temporary.replace(target)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        shutil.rmtree(upload_dir)
        return {
            "success": True,
            "file_id": file_id,
            "filename": filename,
            "size": copied_size,
            "path": self.public_path(target),
            "workspace_relative_path": self.workspace_relative_path(target),
        }

    def cancel_data_upload(self, upload_id: str) -> dict[str, Any]:
        """Discard a pending upload in the current session workspace."""
        upload_dir, _ = self._load_upload_state(upload_id)
        shutil.rmtree(upload_dir)
        return {"success": True, "upload_id": upload_id, "cancelled": True}

    def save_render_manifest(
        self, render_id: str, mode: str, plot: str, config: dict[str, Any]
    ) -> None:
        """Persist the request needed to revise a previous render."""
        if not re.fullmatch(r"[\w.-]{1,140}", render_id, flags=re.UNICODE):
            raise WorkspaceError("render_id 无效。")
        metadata_dir = self._ensure_workspace_dir(Path("outputs") / "mcp" / ".mcp-renders")
        manifest = {"render_id": render_id, "mode": mode, "plot": plot, "config": config}
        payload = json.dumps(manifest, ensure_ascii=False, default=str)
        if len(payload.encode("utf-8")) > 2 * 1024 * 1024:
            raise WorkspaceError("绘图参数超过 2 MiB，无法保存可重绘记录。")
        destination = self._ensure_inside_workspace(metadata_dir / f"{render_id}.json")
        temporary = self._ensure_inside_workspace(metadata_dir / f".{render_id}.{uuid4().hex}.tmp")
        temporary.write_text(payload, encoding="utf-8")
        temporary.replace(destination)

    def load_render_manifest(self, render_id: str) -> dict[str, Any]:
        if not re.fullmatch(r"[\w.-]{1,140}", str(render_id or ""), flags=re.UNICODE):
            raise WorkspaceError("render_id 无效；请从绘图结果或 list_render_outputs 获取。")
        metadata_dir = self._ensure_inside_workspace(self.output_dir / ".mcp-renders")
        manifest_path = self._ensure_inside_workspace(metadata_dir / f"{render_id}.json")
        if manifest_path.is_symlink():
            raise WorkspaceError("绘图记录不能是符号链接。")
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise WorkspaceError(f"找不到绘图记录 {render_id}；旧结果或超大参数可能没有可重绘记录。") from exc
        if (
            not isinstance(manifest, dict)
            or manifest.get("render_id") != render_id
            or manifest.get("mode") not in {"demo", "custom", "file"}
            or not isinstance(manifest.get("config"), dict)
        ):
            raise WorkspaceError("绘图记录内容无效。")
        return manifest

    def list_data_files(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))
        files = [
            path
            for path in self.input_dir.iterdir()
            if not path.is_symlink()
            and path.is_file()
            and path.suffix.lower() in ALLOWED_DATA_SUFFIXES
        ]
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        window = files[safe_offset : safe_offset + safe_limit]
        items = [
            {
                "file_id": path.name,
                "filename": path.name[13:] if len(path.name) > 13 and path.name[12] == "_" else path.name,
                "format": path.suffix.lower().lstrip("."),
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                "path": self.public_path(path),
                "workspace_relative_path": self.workspace_relative_path(path),
            }
            for path in window
        ]
        return {
            "success": True,
            "items": items,
            "offset": safe_offset,
            "limit": safe_limit,
            "total": len(files),
            "has_more": safe_offset + len(window) < len(files),
        }

    def inspect_data_file(self, file_id: str, preview_rows: int = 5) -> dict[str, Any]:
        path = self.resolve_data_file(file_id)
        return self.inspect_workspace_file(path, preview_rows)

    def inspect_workspace_file(self, raw_path: str | Path, preview_rows: int = 5) -> dict[str, Any]:
        path = self.resolve_workspace_file(raw_path)
        if path.suffix.lower() not in ALLOWED_DATA_SUFFIXES:
            raise WorkspaceError("数据预览仅支持 CSV、TSV、TXT、XLSX 和 XLS 文件。")
        limit = max(1, min(int(preview_rows), 20))
        try:
            import pandas as pd
        except ImportError as exc:
            raise WorkspaceError("读取表格需要 pandas；请运行 `uv sync --extra data`。") from exc

        if path.suffix.lower() in {".xlsx", ".xls"}:
            frame = pd.read_excel(path)
        else:
            preferred_sep = "\t" if path.suffix.lower() in {".tsv", ".txt"} else ","
            frame = None
            last_error: Exception | None = None
            for encoding in ("utf-8-sig", "utf-8", "gbk"):
                for sep in (preferred_sep, None, ";", "\t", ","):
                    try:
                        kwargs: dict[str, Any] = {"encoding": encoding}
                        if sep is None:
                            kwargs.update({"sep": None, "engine": "python"})
                        else:
                            kwargs["sep"] = sep
                        frame = pd.read_csv(path, **kwargs)
                        break
                    except Exception as exc:  # Try the next common encoding/delimiter.
                        last_error = exc
                if frame is not None:
                    break
            if frame is None:
                raise WorkspaceError(f"无法解析表格文件：{last_error}") from last_error

        preview_json = frame.head(limit).to_json(
            orient="records", date_format="iso", force_ascii=False
        )
        import json

        return {
            "success": True,
            "file_id": path.name if path.parent == self.input_dir else None,
            "filename": path.name[13:] if path.parent == self.input_dir and len(path.name) > 13 and path.name[12] == "_" else path.name,
            "format": path.suffix.lower().lstrip("."),
            "row_count": int(len(frame.index)),
            "column_count": int(len(frame.columns)),
            "columns": [
                {"name": str(column), "dtype": str(frame[column].dtype)}
                for column in frame.columns
            ],
            "missing_values": {
                str(column): int(frame[column].isna().sum())
                for column in frame.columns
            },
            "preview_rows": json.loads(preview_json),
        }

    def list_render_outputs(self, limit: int = 50, offset: int = 0) -> dict[str, Any]:
        safe_limit = max(1, min(int(limit), 200))
        safe_offset = max(0, int(offset))
        files = [
            path
            for path in self.output_dir.iterdir()
            if not path.is_symlink()
            and path.is_file()
            and path.suffix.lower() in ALLOWED_RENDER_SUFFIXES
        ]
        files.sort(key=lambda path: path.stat().st_mtime, reverse=True)
        window = files[safe_offset : safe_offset + safe_limit]
        items = [
            {
                "file_id": path.name,
                "render_id": path.stem,
                "filename": path.name,
                "format": path.suffix.lower().lstrip("."),
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                "path": self.public_path(path),
                "workspace_relative_path": self.workspace_relative_path(path),
                "revisable": (
                    self.output_dir / ".mcp-renders" / f"{path.stem}.json"
                ).is_file() and not (
                    self.output_dir / ".mcp-renders" / f"{path.stem}.json"
                ).is_symlink(),
            }
            for path in window
        ]
        return {
            "success": True,
            "items": items,
            "offset": safe_offset,
            "limit": safe_limit,
            "total": len(files),
            "has_more": safe_offset + len(window) < len(files),
        }
