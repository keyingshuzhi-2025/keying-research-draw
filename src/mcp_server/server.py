"""MCP Server for Research Draw.

This server exposes Research Draw's plotting capabilities as MCP tools,
allowing LLM clients to generate scientific visualizations.
"""

from __future__ import annotations

import os
import json
import logging
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ImageContent

from src.cli.config_schema import validate_cli_config_payload
from src.cli.parser import build_parser
from src.mcp_server.runner import ResearchDrawMCPRunner
from src.mcp_server.http_auth import BearerTokenAuthMiddleware
from src.mcp_server.workspace import (
    ALLOWED_DATA_SUFFIXES,
    WorkspaceError,
    resolve_workspace_location,
)
from src.registry import (
    canonical_plots_by_group,
    group_metadata,
    plot_registry_payload,
    public_plot_name,
    required_fields_for_plot,
    default_args_for_plot,
    demo_data_path_for_plot,
)
from src.registry.plot_registry import (
    ALL_PUBLIC_PLOTS,
    PLOT_DEPENDENCY_HINTS,
    PLOT_ALIASES,
)


_COLUMN_CONFIG_KEYS = {
    "group_col", "value_col", "x_col", "y_col", "z_col", "z3d_col",
    "u_col", "v_col", "w_col", "scalar_col", "log2fc_col", "p_col",
    "label_col", "forest_label_col", "effect_col", "ci_low_col", "ci_high_col",
    "weight_col", "mean_col", "term_col", "count_col", "ratio_col", "hit_col",
    "score_col", "prob_col", "true_col", "pred_col", "time_col", "event_col",
    "class_col", "item_col", "response_col", "a_col", "b_col", "c_col",
    "factor_col", "loading_col", "date_col", "open_col", "high_col", "low_col",
    "close_col", "volume_col", "return_col", "price_col", "key_col", "lon_col",
    "lat_col", "size_col", "hue_col",
}
_BUNDLED_MAP_ONLY_PLOTS = {"world", "world_admin1", "china"}
_MODE_REQUIRED_PATH = {"raster": "raster_file"}
_CUSTOM_REQUIRED_FIELDS = {
    "box": ("group",),
    "violin": ("group",),
    "scatter": ("x", "y"),
    "volcano": ("log2fc", "pvals"),
    "forest": ("forest_labels", "effects", "ci_low", "ci_high"),
    "scatter3d": ("x", "y", "z"),
    "surface3d": ("x", "y", "z"),
    "wireframe3d": ("x", "y", "z"),
    "contour3d": ("x", "y", "z"),
    "line3d": ("x", "y", "z"),
    "isosurface3d": ("x", "y", "z", "scalar"),
    "slice3d": ("x", "y", "z", "scalar"),
    "quiver3d": ("x", "y", "z", "u", "v", "w"),
    "waterfall3d": ("x", "y", "z"),
    "mesh3d": ("x", "y", "z"),
}
_PLOT_IMPORTS = {
    "data": ("pandas",),
    "maps": ("geopandas",),
    "raster": ("rasterio",),
}


def _required_imports_for_plot(
    plot: str,
    mode: str,
    dependency_extra: str | None,
    config: dict[str, Any],
) -> tuple[str, ...]:
    modules = list(_PLOT_IMPORTS.get(dependency_extra or "", ()))
    if (
        (mode == "file" and plot not in _BUNDLED_MAP_ONLY_PLOTS and plot != "raster")
        or plot in canonical_plots_by_group().get("domain_2d", [])
        or plot == "embedding3d"
    ):
        modules.append("pandas")
    if plot in canonical_plots_by_group().get("maps", []):
        modules.append("geopandas")
    if plot == "upset":
        modules.append("upsetplot")
    elif plot == "isosurface3d":
        modules.append("skimage")
    elif plot in {"embedding", "embedding3d"} and str(config.get("embed_method", "pca")).lower() == "umap":
        modules.append("umap")
    return tuple(dict.fromkeys(modules))


# Initialize the FastMCP server
mcp = FastMCP(
    "research-draw",
    instructions=(
        "文件工具每次调用都要把当前会话选中的工作区绝对路径作为顶层参数 "
        "workspace_path 传入；macOS/Linux 路径开头的 / 不可省略。切换会话后使用新会话的路径。"
        "render_plot 的 workspace_path 是顶层参数，不能放入 config。"
    ),
)

_project_root: Optional[Path] = None


def _get_runner(workspace_path: str) -> ResearchDrawMCPRunner:
    """Get a runner scoped to the active Koying session workspace."""
    global _project_root
    if not workspace_path:
        raise WorkspaceError("每次工作区工具调用都必须提供当前会话的 workspace_path。")
    location = resolve_workspace_location(workspace_path)
    if _project_root is None:
        _project_root = Path(__file__).resolve().parents[2]
    return ResearchDrawMCPRunner(
        _project_root,
        location.runtime_root,
        display_workspace_root=location.host_root,
    )


@mcp.tool()
def get_version() -> str:
    """Get the version of Research Draw.
    
    Returns:
        Version string in the format "vX.Y.Z"
    """
    try:
        from src.version import __version__
        return f"v{__version__}"
    except Exception:
        # Fallback to reading VERSION file directly
        version_file = Path(__file__).resolve().parents[2] / "VERSION"
        if version_file.exists():
            return f"v{version_file.read_text().strip()}"
        return "v0.0.0"


@mcp.tool()
def list_plot_groups() -> dict:
    """List all available plot groups with metadata.
    
    Returns:
        Dictionary containing plot groups with their labels, descriptions, 
        order, scene description, and plot count.
    """
    groups = group_metadata()
    # Add plot count to each group
    plots_by_group = canonical_plots_by_group()
    for group_key, group_info in groups.items():
        group_info["plot_count"] = len(plots_by_group.get(group_key, []))
    return {"groups": groups}


@mcp.tool()
def list_plots(group: Optional[str] = None) -> dict:
    """List available plots, optionally filtered by group.
    
    Args:
        group: Optional group name to filter by (stats_2d, domain_2d, plots_3d, maps)
        
    Returns:
        Dictionary containing plots with their metadata including:
        - dispatch_key: Internal dispatcher key
        - group: Group the plot belongs to
        - required_fields: List of required parameter names
        - defaults: Default parameter values
        - dependency_extra: Required extra dependencies (if any)
        - demo_data: Path to demo data file (if applicable)
        - aliases: Alternative names/aliases for the plot
    """
    payload = plot_registry_payload()
    plots = payload["plots"]
    
    if group:
        # Filter plots by group
        filtered_plots = {
            name: info for name, info in plots.items() 
            if info["group"] == group
        }
        return {"plots": filtered_plots, "group": group}
    
    return {"plots": plots}


@mcp.tool()
def get_plot_schema(plot: str) -> dict:
    """Get detailed schema for a specific plot type.
    
    Args:
        plot: Plot type name (can be alias or canonical name)
        
    Returns:
        Dictionary containing detailed plot schema including:
        - name: Canonical plot name
        - group: Group the plot belongs to
        - required_fields: List of required parameter names
        - optional_fields: List of optional parameter names with defaults
        - aliases: Alternative names for the plot
        - demo_info: Information about demo data (if available)
        - dependencies: Required extra dependencies
        - description: Human-readable description
    """
    # Normalize the plot name
    canonical_name = public_plot_name(plot)
    if not canonical_name:
        return {
            "error": f"Unknown plot type: {plot}",
            "available_plots": list(ALL_PUBLIC_PLOTS)[:20]  # Show first 20 as examples
        }
    
    # Get basic info
    group = None
    for g, plots in canonical_plots_by_group().items():
        if canonical_name in plots:
            group = g
            break
    
    # Get dependencies
    dependency_extra = PLOT_DEPENDENCY_HINTS.get(canonical_name)
    
    # Get demo info
    demo_data_path = demo_data_path_for_plot(canonical_name, Path(__file__).resolve().parents[2])
    demo_info = None
    if demo_data_path and demo_data_path.exists():
        demo_info = {
            "path": str(demo_data_path),
            "exists": True
        }
    
    return {
        "name": canonical_name,
        "group": group,
        "required_fields": required_fields_for_plot(canonical_name),
        "optional_fields": list(default_args_for_plot(canonical_name).keys()),
        "aliases": PLOT_ALIASES.get(canonical_name, [canonical_name]),
        "demo_info": demo_info,
        "dependencies": dependency_extra,
        "description": f"{canonical_name} plot from the {group} group" if group else f"{canonical_name} plot",
    }


@mcp.tool()
def import_data_file(source_path: str, workspace_path: str) -> dict:
    """Import a supported file from the active Koying session workspace.

    workspace_path must be the absolute root of the current conversation's workspace.
    Pass it on every workspace tool call so different sessions remain isolated.
    """
    try:
        return _get_runner(workspace_path).workspace.import_data_file(source_path)
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@mcp.tool()
def upload_data_file(filename: str, content_base64: str, workspace_path: str) -> dict:
    """Upload a supported table into the active Koying session workspace.

    workspace_path is a top-level argument: copy the current conversation's exact
    absolute workspace folder, including the first slash on macOS/Linux.
    """
    try:
        return _get_runner(workspace_path).workspace.upload_data_file(filename, content_base64)
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@mcp.tool()
def list_workspace_files(workspace_path: str, limit: int = 50, offset: int = 0) -> dict:
    """List imported tabular files in the active Koying session workspace."""
    try:
        return _get_runner(workspace_path).workspace.list_data_files(limit=limit, offset=offset)
    except Exception as exc:
        return {"success": False, "message": str(exc), "items": []}


@mcp.tool()
def inspect_data_file(file_id: str, workspace_path: str, preview_rows: int = 5) -> dict:
    """Inspect a file_id within the active Koying session workspace."""
    try:
        return _get_runner(workspace_path).workspace.inspect_data_file(file_id, preview_rows)
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@mcp.tool()
def validate_plot_config(mode: str, plot: str, config: dict, workspace_path: str) -> dict:
    """Preflight a plot request without rendering it."""
    errors: list[str] = []
    warnings: list[str] = []
    if mode not in ("demo", "custom", "file"):
        errors.append("mode 必须是 demo、custom 或 file。")

    canonical_plot = public_plot_name(plot)
    if not canonical_plot or canonical_plot not in ALL_PUBLIC_PLOTS:
        errors.append(f"未知图型：{plot}。请先调用 list_plots。")
    if not isinstance(config, dict):
        errors.append("config 必须是键值对象。")
        config = {}

    normalized_config: dict[str, Any] = dict(config)
    if not errors:
        try:
            normalized_config = validate_cli_config_payload(build_parser(), normalized_config)
        except Exception as exc:
            errors.append(str(exc))

    runner: ResearchDrawMCPRunner | None = None
    if not errors:
        try:
            runner = _get_runner(workspace_path)
            for path_key in ("file", "raster_file", "custom_json_file"):
                if normalized_config.get(path_key):
                    normalized_config[path_key] = str(
                        runner.workspace.resolve_workspace_file(str(normalized_config[path_key]))
                    )
            if normalized_config.get("basemap_root"):
                runner._resolve_config_paths({"basemap_root": normalized_config["basemap_root"]})
        except Exception as exc:
            errors.append(str(exc))

    if canonical_plot and canonical_plot in ALL_PUBLIC_PLOTS and mode in ("demo", "custom", "file"):
        if mode == "file":
            path_key = _MODE_REQUIRED_PATH.get(canonical_plot, "file")
            if canonical_plot in _BUNDLED_MAP_ONLY_PLOTS:
                path_key = ""
            if path_key and not normalized_config.get(path_key):
                errors.append(f"file 模式需要配置 {path_key}。")
            elif path_key and normalized_config.get(path_key) and runner:
                try:
                    input_path = Path(str(normalized_config[path_key]))
                    if input_path.suffix.lower() in ALLOWED_DATA_SUFFIXES:
                        inspection = runner.workspace.inspect_workspace_file(input_path)
                        available_columns = {column["name"] for column in inspection["columns"]}
                        for key in _COLUMN_CONFIG_KEYS:
                            value = normalized_config.get(key)
                            if isinstance(value, str) and value and value not in available_columns:
                                errors.append(f"{key} 指定的列“{value}”不在文件中。")
                        required_fields = required_fields_for_plot(canonical_plot)
                        missing_fields = [
                            field
                            for field in required_fields
                            if not normalized_config.get(field)
                            and not (field == "z_col" and normalized_config.get("z3d_col"))
                        ]
                        if missing_fields:
                            warnings.append(
                                "未显式指定字段："
                                + ", ".join(missing_fields)
                                + "；该图型可能会尝试自动识别列。"
                            )
                except Exception as exc:
                    errors.append(str(exc))
        elif mode == "custom":
            required = _CUSTOM_REQUIRED_FIELDS.get(canonical_plot, ())
            missing = [field for field in required if not normalized_config.get(field)]
            if missing:
                errors.append("custom 模式缺少参数：" + ", ".join(missing))
            if canonical_plot in canonical_plots_by_group().get("domain_2d", []) or canonical_plot == "embedding3d":
                custom_data = normalized_config.get("custom_json")
                custom_file = normalized_config.get("custom_json_file")
                if not custom_data and not custom_file:
                    errors.append("该图型的 custom 模式需要 custom_json 或 custom_json_file。")
                elif custom_data:
                    try:
                        decoded = json.loads(custom_data)
                        if not isinstance(decoded, (list, dict)):
                            errors.append("custom_json 必须是对象或数组。")
                    except (TypeError, json.JSONDecodeError):
                        errors.append("custom_json 不是有效的 JSON。")
                elif custom_file:
                    try:
                        decoded = json.loads(Path(str(custom_file)).read_text(encoding="utf-8"))
                        if not isinstance(decoded, (list, dict)):
                            errors.append("custom_json_file 内容必须是对象或数组。")
                    except (OSError, json.JSONDecodeError):
                        errors.append("custom_json_file 不存在或不是有效的 JSON。")

    dependency_extra = PLOT_DEPENDENCY_HINTS.get(canonical_plot) if canonical_plot else None
    missing_modules = [
        module
        for module in _required_imports_for_plot(
            canonical_plot or "", mode, dependency_extra, normalized_config
        )
        if find_spec(module) is None
    ]
    if missing_modules:
        errors.append(
            f"缺少依赖 {', '.join(missing_modules)}；请安装 `uv sync --extra {dependency_extra}`。"
        )

    return {
        "valid": not errors,
        "plot": canonical_plot,
        "mode": mode,
        "errors": errors,
        "warnings": warnings,
        "dependency_extra": dependency_extra,
        "normalized_config": normalized_config,
    }


@mcp.tool()
def list_render_outputs(workspace_path: str, limit: int = 50, offset: int = 0) -> dict:
    """List recent rendered files in the active Koying session workspace."""
    try:
        return _get_runner(workspace_path).workspace.list_render_outputs(limit=limit, offset=offset)
    except Exception as exc:
        return {"success": False, "message": str(exc), "items": []}


@mcp.tool()
def render_plot(mode: str, plot: str, config: dict, workspace_path: str) -> dict:
    """Render a plot and return the result.
    
    Args:
        mode: Rendering mode - "demo" (built-in data), "custom" (parameters only), or "file" (from data file)
        plot: Plot type to render (e.g., "box", "scatter3d", "choropleth_world")
        config: Configuration parameters as key-value pairs. Keys should match CLI argument names.
               For example: {"title": "My Plot", "xlabel": "X Axis", "ylabel": "Y Axis"}
               For file mode: include "file" parameter with path to data file
               For custom mode: include data parameters like "group", "x", "y", etc.
        workspace_path: Top-level argument with the exact absolute root of the active
                        Koying conversation workspace. Include the leading slash on
                        macOS/Linux; do not put this argument inside config.
               
    Returns:
        Dictionary containing:
        - success: Boolean indicating if rendering succeeded
        - message: Status message
        - image: Base64-encoded PNG image data (if successful)
        - path: Filesystem path to the saved image (if successful)
        - plot_type: The plot type that was rendered
        - mode: The mode used for rendering
    """
    # Validate mode
    if mode not in ("demo", "custom", "file"):
        return {
            "success": False,
            "message": f"Invalid mode: {mode}. Must be 'demo', 'custom', or 'file'",
            "image": None,
            "path": None,
        }
    
    # Validate plot
    canonical_plot = public_plot_name(plot)
    if not canonical_plot or canonical_plot not in ALL_PUBLIC_PLOTS:
        return {
            "success": False,
            "message": f"Unknown plot type: {plot}. Use list_plots() to see available plots.",
            "image": None,
            "path": None,
        }

    if not isinstance(config, dict):
        return {
            "success": False,
            "message": "config 必须是键值对象。",
            "image": None,
            "path": None,
        }

    try:
        runner = _get_runner(workspace_path)
    except Exception as exc:
        return {
            "success": False,
            "message": str(exc),
            "image": None,
            "path": None,
        }
    
    # Run the rendering
    success, message, output_path = runner.render_plot(mode, canonical_plot, config)
    
    if not success or output_path is None:
        return {
            "success": False,
            "message": message,
            "image": None,
            "path": None,
        }
    
    # Read the image file and return as base64
    try:
        import base64
        with open(output_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        # Determine media type based on file extension
        ext = output_path.suffix.lower()
        if ext == ".png":
            media_type = "image/png"
        elif ext == ".jpg" or ext == ".jpeg":
            media_type = "image/jpeg"
        elif ext == ".svg":
            media_type = "image/svg+xml"
        elif ext == ".pdf":
            media_type = "application/pdf"
        else:
            media_type = "application/octet-stream"
        
        return {
            "success": True,
            "message": message,
            "image": ImageContent(
                type="image",
                data=image_data,
                mimeType=media_type
            ),
            "path": runner.workspace.public_path(output_path),
            "workspace_relative_path": runner.workspace.workspace_relative_path(output_path),
            "plot_type": canonical_plot,
            "mode": mode,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Successfully rendered but failed to read output: {str(e)}",
            "image": None,
            "path": runner.workspace.public_path(output_path) if output_path else None,
        }


# 为了向后兼容和直接运行的支持
def main():
    """Start local stdio mode or authenticated remote Streamable HTTP mode."""
    transport = os.getenv("RESEARCH_DRAW_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run()
        return
    if transport != "streamable-http":
        raise SystemExit("RESEARCH_DRAW_MCP_TRANSPORT must be 'stdio' or 'streamable-http'.")

    token_path = os.getenv("RESEARCH_DRAW_MCP_TOKEN_FILE", "").strip()
    if not token_path:
        raise SystemExit("RESEARCH_DRAW_MCP_TOKEN_FILE is required for Streamable HTTP mode.")
    try:
        token = Path(token_path).read_bytes().strip()
    except OSError as exc:
        raise SystemExit(f"Cannot read MCP bearer token file: {token_path}") from exc
    if len(token) < 32 or any(byte < 33 or byte > 126 for byte in token):
        raise SystemExit("MCP bearer token must contain at least 32 visible ASCII characters.")

    def csv_setting(name: str, default: list[str]) -> list[str]:
        raw = os.getenv(name, "")
        values = [value.strip() for value in raw.split(",") if value.strip()]
        return values or default

    allowed_hosts = csv_setting(
        "RESEARCH_DRAW_MCP_ALLOWED_HOSTS", ["localhost:*", "127.0.0.1:*"]
    )
    allowed_origins = csv_setting("RESEARCH_DRAW_MCP_ALLOWED_ORIGINS", [])
    security = TransportSecuritySettings(
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )

    try:
        port = int(os.getenv("RESEARCH_DRAW_MCP_PORT", "8000"))
    except ValueError as exc:
        raise SystemExit("RESEARCH_DRAW_MCP_PORT must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("RESEARCH_DRAW_MCP_PORT must be between 1 and 65535.")
    try:
        max_request_body_mb = max(
            1, min(256, int(os.getenv("RESEARCH_DRAW_MCP_MAX_REQUEST_BODY_MB", "48")))
        )
    except ValueError:
        max_request_body_mb = 48

    import uvicorn

    # FastMCP keeps HTTP transport options on its settings object; the pinned
    # SDK's streamable_http_app() factory does not accept keyword arguments.
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    mcp.settings.stateless_http = True
    mcp.settings.max_request_body_size = max_request_body_mb * 1024 * 1024
    mcp.settings.transport_security = security
    app = mcp.streamable_http_app()
    protected_app = BearerTokenAuthMiddleware(app, token)
    uvicorn.run(
        protected_app,
        host="0.0.0.0",
        port=port,
        log_level=os.getenv("RESEARCH_DRAW_MCP_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
