from __future__ import annotations

import base64
from pathlib import Path

import pytest

from src.mcp_server.workspace import (
    MCPWorkspace,
    WorkspaceError,
    resolve_workspace_location,
)


def test_mcp_paths_map_to_the_host_workspace(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    host_workspace = tmp_path / "koying-workspace" / ".research-draw-mcp"
    host_workspace.mkdir(parents=True)
    workspace = MCPWorkspace(host_workspace, project_root)

    uploaded = workspace.upload_data_file(
        "test.csv", base64.b64encode(b"x,y\n1,2\n").decode("ascii")
    )
    upload_relative = uploaded["workspace_relative_path"]
    assert upload_relative == f"inputs/mcp/{uploaded['file_id']}"
    assert uploaded["path"] == str(host_workspace / upload_relative)
    assert (host_workspace / upload_relative).is_file()

    imported = workspace.import_data_file(uploaded["file_id"])
    import_relative = imported["workspace_relative_path"]
    assert import_relative == f"inputs/mcp/{imported['file_id']}"
    assert (host_workspace / import_relative).is_file()

    output = workspace.output_dir / "test.png"
    output.write_bytes(b"test-image")
    listed = workspace.list_render_outputs()
    assert listed["items"][0]["workspace_relative_path"] == "outputs/mcp/test.png"
    assert (host_workspace / listed["items"][0]["workspace_relative_path"]).is_file()

    files = workspace.list_data_files()
    assert {item["workspace_relative_path"] for item in files["items"]} == {
        upload_relative,
        import_relative,
    }


def test_session_workspace_maps_under_host_root_for_http(tmp_path: Path, monkeypatch) -> None:
    host_root = tmp_path / "host-workspaces"
    host_workspace = host_root / "conversation-a"
    host_workspace.mkdir(parents=True)
    mount_root = tmp_path / "container-mount"
    (mount_root / "conversation-a").mkdir(parents=True)
    monkeypatch.setenv("RESEARCH_DRAW_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT", str(host_root))
    monkeypatch.setenv("RESEARCH_DRAW_MCP_HOST_WORKSPACES_MOUNT", str(mount_root))

    location = resolve_workspace_location(host_workspace)

    assert location.runtime_root == mount_root / "conversation-a"
    assert location.host_root == host_workspace
    assert resolve_workspace_location(str(host_workspace).lstrip("/")) == location

    with pytest.raises(WorkspaceError, match="绝对路径"):
        resolve_workspace_location("unrelated/conversation-a")

    with pytest.raises(WorkspaceError, match="允许的宿主机根目录"):
        resolve_workspace_location(tmp_path / "outside")


def test_two_sessions_write_to_their_own_host_workspaces(tmp_path: Path, monkeypatch) -> None:
    host_root = tmp_path / "host-workspaces"
    session_a = host_root / "session-a"
    session_b = host_root / "session-b"
    session_a.mkdir(parents=True)
    session_b.mkdir(parents=True)
    mount_root = tmp_path / "container-mount"
    runtime_a = mount_root / "session-a"
    runtime_b = mount_root / "session-b"
    runtime_a.mkdir(parents=True)
    runtime_b.mkdir(parents=True)
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setenv("RESEARCH_DRAW_MCP_TRANSPORT", "streamable-http")
    monkeypatch.setenv("RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT", str(host_root))
    monkeypatch.setenv("RESEARCH_DRAW_MCP_HOST_WORKSPACES_MOUNT", str(mount_root))

    location_a = resolve_workspace_location(session_a)
    location_b = resolve_workspace_location(session_b)
    workspace_a = MCPWorkspace(location_a.runtime_root, project_root, display_root=location_a.host_root)
    workspace_b = MCPWorkspace(location_b.runtime_root, project_root, display_root=location_b.host_root)
    content = base64.b64encode(b"x,y\n1,2\n").decode("ascii")

    uploaded_a = workspace_a.upload_data_file("a.csv", content)
    uploaded_b = workspace_b.upload_data_file("b.csv", content)

    assert Path(uploaded_a["path"]).is_relative_to(session_a)
    assert Path(uploaded_b["path"]).is_relative_to(session_b)
    assert (location_a.runtime_root / uploaded_a["workspace_relative_path"]).is_file()
    assert (location_b.runtime_root / uploaded_b["workspace_relative_path"]).is_file()
    assert workspace_a.list_data_files()["total"] == 1
    assert workspace_b.list_data_files()["total"] == 1


def test_http_requires_session_workspace_mount_configuration(monkeypatch, tmp_path: Path) -> None:
    host_workspace = tmp_path / "conversation-a"
    host_workspace.mkdir()
    monkeypatch.setenv("RESEARCH_DRAW_MCP_TRANSPORT", "streamable-http")
    monkeypatch.delenv("RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT", raising=False)
    monkeypatch.delenv("RESEARCH_DRAW_MCP_HOST_WORKSPACES_MOUNT", raising=False)

    with pytest.raises(WorkspaceError, match="必须配置"):
        resolve_workspace_location(host_workspace)
