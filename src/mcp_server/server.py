"""MCP Server for Research Draw.

This server exposes Research Draw's plotting capabilities as MCP tools,
allowing LLM clients to generate scientific visualizations.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from mcp.server.fastmcp import FastMCP
from mcp.types import TextContent, ImageContent

from src.mcp_server.runner import ResearchDrawMCPRunner
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

# Initialize the FastMCP server
mcp = FastMCP("research-draw")

# Initialize the runner (will be set up in main)
_runner: Optional[ResearchDrawMCPRunner] = None
_project_root: Optional[Path] = None


def _get_runner() -> ResearchDrawMCPRunner:
    """Get or create the runner instance."""
    global _runner, _project_root
    if _runner is None:
        if _project_root is None:
            _project_root = Path(__file__).resolve().parents[2]
        _runner = ResearchDrawMCPRunner(_project_root)
    return _runner


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
def render_plot(mode: str, plot: str, config: dict) -> dict:
    """Render a plot and return the result.
    
    Args:
        mode: Rendering mode - "demo" (built-in data), "custom" (parameters only), or "file" (from data file)
        plot: Plot type to render (e.g., "box", "scatter3d", "choropleth_world")
        config: Configuration parameters as key-value pairs. Keys should match CLI argument names.
               For example: {"title": "My Plot", "xlabel": "X Axis", "ylabel": "Y Axis"}
               For file mode: include "file" parameter with path to data file
               For custom mode: include data parameters like "group", "x", "y", etc.
               
    Returns:
        Dictionary containing:
        - success: Boolean indicating if rendering succeeded
        - message: Status message
        - image: Base64-encoded PNG image data (if successful)
        - path: Filesystem path to the saved image (if successful)
        - plot_type: The plot type that was rendered
        - mode: The mode used for rendering
    """
    runner = _get_runner()
    
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
            "path": str(output_path),
            "plot_type": canonical_plot,
            "mode": mode,
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Successfully rendered but failed to read output: {str(e)}",
            "image": None,
            "path": str(output_path) if output_path else None,
        }


# 为了向后兼容和直接运行的支持
def main():
    """Main entry point for the MCP server."""
    # 运行FastMCP服务器（默认使用stdio传输）
    mcp.run()


if __name__ == "__main__":
    main()