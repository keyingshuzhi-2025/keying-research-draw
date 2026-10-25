"""Runner for Research Draw MCP server.

Handles the conversion from MCP tool parameters to CLI arguments
and execution of the Research Draw application.
"""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from uuid import uuid4

from src.main import ResearchDrawApp
from src.mcp_server.workspace import MCPWorkspace, WorkspaceError


_RENDER_LOCK = threading.RLock()
_OUTPUT_FORMATS = {"png", "svg", "pdf"}


def _dest_to_arg_flag(dest: str) -> str:
    """Convert a destination name (e.g., 'save_name') to CLI argument flag (e.g., '--save-name').
    
    Args:
        dest: Destination name from argparse (underscores)
        
    Returns:
        CLI argument flag with hyphens
    """
    return f"--{dest.replace('_', '-')}"


def _build_argv_from_config(
    mode: str, plot: str, config: Dict[str, Any], project_root: Path
) -> list[str]:
    """Build CLI argument list from MCP tool parameters.

    Args:
        mode: One of "demo", "custom", or "file"
        plot: Plot type name (e.g., "box", "scatter3d")
        config: Configuration dictionary mapping CLI argument names to values
        project_root: Project root directory

    Returns:
        List of command-line arguments suitable for passing to ResearchDrawApp
    """
    argv = ["--mode", mode, "--plot", plot]

    # Handle special cases first
    if mode == "file" and config.get("file"):
        argv.extend(["--file", str(config["file"])])

    # Add all other config parameters
    for key, value in config.items():
        # Skip already handled parameters
        if key in ("mode", "plot", "file"):
            continue

        # Handle None values (skip unless it's a flag that should be False)
        if value is None:
            continue

        # Handle boolean flags
        if isinstance(value, bool):
            if value:
                argv.extend([_dest_to_arg_flag(key)])
            # If False, we don't add the flag (default behavior)
            continue

        # Handle list-like parameters (e.g., --group can be repeated)
        if isinstance(value, (list, tuple)):
            for item in value:
                argv.extend([_dest_to_arg_flag(key), str(item)])
            continue

        # Handle all other parameter types
        argv.extend([_dest_to_arg_flag(key), str(value)])

    return argv


class ResearchDrawMCPRunner:
    """Runner that executes Research Draw and captures results."""

    def __init__(
        self,
        project_root: Optional[Path] = None,
        workspace_root: str | Path | None = None,
        *,
        display_workspace_root: str | Path | None = None,
    ):
        self.project_root = Path(project_root or Path(__file__).resolve().parents[2]).resolve()
        self.workspace = MCPWorkspace(
            workspace_root,
            self.project_root,
            display_root=display_workspace_root,
        )
        self.output_dir = self.workspace.output_dir

    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for headless execution."""
        return {
            "MPLBACKEND": "Agg",
            "PLOT_BACKEND": "Agg",
            "HEADLESS": "1",
            "PLOT_OUTDIR_OVERRIDE": str(self.output_dir),
        }

    def _resolve_config_paths(self, config: Dict[str, Any]) -> Dict[str, Any]:
        resolved = dict(config)
        for key in ("file", "raster_file", "custom_json_file"):
            value = resolved.get(key)
            if value:
                resolved[key] = str(self.workspace.resolve_workspace_file(str(value)))
        if resolved.get("basemap_root"):
            basemap_raw = Path(str(resolved["basemap_root"])).expanduser()
            if not basemap_raw.is_absolute():
                basemap_raw = self.project_root / basemap_raw
            basemap_root = basemap_raw.resolve()
            workspace_root = self.workspace.root
            bundled_map_root = (self.project_root / "data" / "geo").resolve()
            if not (
                basemap_root.is_relative_to(workspace_root)
                or basemap_root.is_relative_to(bundled_map_root)
            ):
                raise WorkspaceError("basemap_root 只能指向工作区或项目自带的 data/geo 目录。")
            if not basemap_root.is_dir():
                raise WorkspaceError(f"basemap_root 不是有效目录：{basemap_root}")
            resolved["basemap_root"] = str(basemap_root)
        if "config" in resolved:
            raise WorkspaceError("MCP config 已是绘图参数对象，不支持再传入 CLI 配置文件路径。")
        if resolved.get("outdir"):
            raise WorkspaceError("MCP 绘图输出目录固定在本地工作区，不能通过 outdir 改写。")
        return resolved

    @staticmethod
    def _unique_save_name(requested: Any) -> str:
        raw = str(requested or "").strip()
        safe = re.sub(r"[^\w.-]+", "_", raw, flags=re.UNICODE).strip("._")
        safe = safe[:80]
        prefix = f"{safe}_" if safe else "mcp_"
        return f"{prefix}{uuid4().hex[:12]}"

    def render_plot(
        self, mode: str, plot: str, config: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Path]]:
        """Render a plot and return the result.

        Args:
            mode: Rendering mode ("demo", "custom", or "file")
            plot: Plot type to render
            config: Configuration parameters for the plot

        Returns:
            Tuple of (success, message, output_path)
            If success is False, output_path is None
            If success is True, output_path is the path to the saved image
        """
        with _RENDER_LOCK:
            try:
                safe_config = self._resolve_config_paths(config)
                fmt = str(safe_config.get("fmt") or "png").lower().lstrip(".")
                if fmt not in _OUTPUT_FORMATS:
                    return False, f"不支持的导出格式：{fmt}；支持 png、svg、pdf。", None

                save_name = self._unique_save_name(safe_config.get("save_name"))
                safe_config["save_name"] = save_name
                safe_config["fmt"] = fmt
                safe_config["no_show"] = True
                argv = _build_argv_from_config(mode, plot, safe_config, self.project_root)
                env_updates = self._prepare_environment()
                previous_env = {key: os.environ.get(key) for key in env_updates}
                try:
                    os.environ.update(env_updates)
                    app = ResearchDrawApp(argv=argv)
                    app.run()
                finally:
                    for key, previous_value in previous_env.items():
                        if previous_value is None:
                            os.environ.pop(key, None)
                        else:
                            os.environ[key] = previous_value

                output_path = self.output_dir / f"{save_name}.{fmt}"
                if not output_path.is_file():
                    return False, "绘图已执行，但没有在工作区输出目录中找到本次生成的图片。", None
                self.workspace._ensure_inside_workspace(output_path)
                return True, f"Successfully rendered {plot}", output_path
            except Exception as e:
                return False, f"Error rendering plot: {str(e)}", None
