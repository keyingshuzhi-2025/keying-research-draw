"""Workspace-scoped file management for the local MCP server."""

from __future__ import annotations

import os
import re
import base64
import binascii
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4


WORKSPACE_ENV = "RESEARCH_DRAW_MCP_WORKSPACE"
ALLOWED_DATA_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx", ".xls"}
ALLOWED_RENDER_SUFFIXES = {".png", ".svg", ".pdf"}


class WorkspaceError(ValueError):
    """Raised when a requested workspace operation is invalid or unsafe."""


class MCPWorkspace:
    """Manage MCP inputs and outputs under an explicitly configured workspace."""

    def __init__(self, workspace_root: str | Path | None, project_root: Path) -> None:
        raw_root = workspace_root or os.getenv(WORKSPACE_ENV)
        if not raw_root:
            raise WorkspaceError(
                f"本地 MCP 未配置工作区。请设置环境变量 {WORKSPACE_ENV}，"
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

    def resolve_workspace_file(self, raw_path: str | Path, *, must_exist: bool = True) -> Path:
        """Resolve a file path while keeping it inside the configured workspace."""
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
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
        source = self.resolve_workspace_file(source_path)
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
            "path": str(target),
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
        }

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
                "filename": path.name,
                "format": path.suffix.lower().lstrip("."),
                "size": path.stat().st_size,
                "modified_at": datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
                "path": str(path),
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
