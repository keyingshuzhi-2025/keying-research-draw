from __future__ import annotations

import base64
import gzip
import random
import string
from pathlib import Path

import pytest

from src.mcp_server.workspace import (
    DEFAULT_MODEL_UPLOAD_CHUNK_BYTES,
    MCPWorkspace,
    WorkspaceError,
)


def _workspace(tmp_path: Path) -> MCPWorkspace:
    workspace_root = tmp_path / "workspace"
    project_root = tmp_path / "project"
    workspace_root.mkdir()
    project_root.mkdir()
    return MCPWorkspace(workspace_root, project_root)


def test_import_from_shared_logical_workspace_root(tmp_path: Path) -> None:
    shared_root = tmp_path / "shared"
    session_root = shared_root / ".mcp-sessions" / "session-key"
    project_root = tmp_path / "project"
    session_root.mkdir(parents=True)
    project_root.mkdir()
    source = shared_root / "source.csv"
    content = b"group,value\nA,1\nB,2\n"
    source.write_bytes(content)
    workspace = MCPWorkspace(
        session_root,
        project_root,
        shared_workspace_root=shared_root,
    )

    imported = workspace.import_data_file("source.csv")

    assert imported["success"] is True
    assert (workspace.input_dir / imported["file_id"]).read_bytes() == content


def test_import_cannot_read_another_mcp_session_directory(tmp_path: Path) -> None:
    shared_root = tmp_path / "shared"
    session_root = shared_root / ".mcp-sessions" / "current-session"
    project_root = tmp_path / "project"
    private_source = (
        shared_root / ".mcp-sessions" / "other-session" / "inputs" / "mcp" / "private.csv"
    )
    private_source.parent.mkdir(parents=True)
    session_root.mkdir(parents=True)
    project_root.mkdir()
    private_source.write_text("secret,value\nA,1\n", encoding="utf-8")
    workspace = MCPWorkspace(
        session_root,
        project_root,
        shared_workspace_root=shared_root,
    )

    with pytest.raises(WorkspaceError, match="不能从 MCP 管理的会话私有目录导入文件"):
        workspace.import_data_file(".mcp-sessions/other-session/inputs/mcp/private.csv")


def test_chunked_upload_accepts_gzip_encoded_blocks(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    content = b"id,treatment,day,response\n" + (b"Control,1,10\n" * 6000)
    chunk_size = 64 * 1024
    chunks = (content[:chunk_size], content[chunk_size:])

    upload = workspace.begin_data_upload(
        "study.csv", total_size=len(content), chunk_size=chunk_size
    )
    assert upload["chunk_count"] == 2

    received = []
    for chunk_index, chunk in enumerate(chunks):
        encoded = base64.b64encode(gzip.compress(chunk, mtime=0)).decode("ascii")
        received.append(
            workspace.upload_data_chunk(
                upload["upload_id"],
                chunk_index,
                encoded,
                content_encoding="gzip",
            )
        )

    assert [result["received_bytes"] for result in received] == [chunk_size, len(content)]
    assert all(result["content_encoding"] == "gzip" for result in received)

    completed = workspace.complete_data_upload(upload["upload_id"])
    assert completed["success"] is True
    assert completed["size"] == len(content)
    assert (workspace.input_dir / completed["file_id"]).read_bytes() == content


def test_chunked_upload_keeps_identity_encoding_compatible(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    content = b"x,y\n1,2\n"
    upload = workspace.begin_data_upload(
        "small.csv", total_size=len(content), chunk_size=len(content)
    )

    result = workspace.upload_data_chunk(
        upload["upload_id"],
        0,
        base64.b64encode(content).decode("ascii"),
    )

    assert result["success"] is True
    assert result["received_bytes"] == len(content)
    assert result["content_encoding"] == "identity"


def test_two_small_identity_chunks_accept_high_entropy_data(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    rng = random.Random(7412)
    alphabet = string.ascii_letters + string.digits
    payload = "".join(rng.choices(alphabet, k=12 * 1024 - 12)).encode("ascii")
    content = b"id,value\n1," + payload + b"\n"
    chunk_size = DEFAULT_MODEL_UPLOAD_CHUNK_BYTES

    upload = workspace.begin_data_upload("high-entropy.csv", total_size=len(content))
    assert upload["chunk_size"] == chunk_size
    assert upload["chunk_count"] == 2

    chunks = (content[:chunk_size], content[chunk_size:])
    for index, chunk in enumerate(chunks):
        result = workspace.upload_data_chunk(
            upload["upload_id"],
            index,
            base64.b64encode(chunk).decode("ascii"),
        )
        assert result["success"] is True
        assert result["content_encoding"] == "identity"

    completed = workspace.complete_data_upload(upload["upload_id"])
    assert completed["success"] is True
    assert (workspace.input_dir / completed["file_id"]).read_bytes() == content


def test_gzip_chunk_cannot_expand_past_declared_size(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    chunk_size = 64 * 1024
    upload = workspace.begin_data_upload(
        "oversized.csv", total_size=chunk_size, chunk_size=chunk_size
    )
    oversized = gzip.compress(b"x" * (chunk_size + 1), mtime=0)

    with pytest.raises(WorkspaceError, match="gzip 分块解压后超过预期大小"):
        workspace.upload_data_chunk(
            upload["upload_id"],
            0,
            base64.b64encode(oversized).decode("ascii"),
            content_encoding="gzip",
        )


def test_chunked_upload_rejects_unknown_content_encoding(tmp_path: Path) -> None:
    workspace = _workspace(tmp_path)
    content = b"x,y\n1,2\n"
    upload = workspace.begin_data_upload(
        "unknown.csv", total_size=len(content), chunk_size=len(content)
    )

    with pytest.raises(WorkspaceError, match="content_encoding 仅支持 identity 或 gzip"):
        workspace.upload_data_chunk(
            upload["upload_id"],
            0,
            base64.b64encode(content).decode("ascii"),
            content_encoding="br",
        )
