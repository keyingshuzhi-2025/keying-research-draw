# Research Draw MCP Server

This is an MCP (Model Context Protocol) server for the Research Draw scientific visualization toolkit.

## Overview

This server exposes Research Draw's plotting capabilities as MCP tools, allowing LLM clients (like Claude Desktop, Cursor, etc.) to generate scientific visualizations through a standardized interface.

## Installation

The MCP server is installed as part of the Research Draw package. To use it:

```bash
# Install with MCP support
uv sync --extra mcp

# Or install all extras (including MCP)
uv sync --extra all
```

## Usage

### As a standalone MCP server

```bash
uv run research-draw-mcp
```

This will start the MCP server using stdio transport, ready to accept connections from MCP clients.

### Available Tools

The server exposes the following tools:

1. `get_version` - Get the version of Research Draw
2. `list_plot_groups` - List all available plot groups with metadata
3. `list_plots` - List available plots, optionally filtered by group
4. `get_plot_schema` - Get detailed schema for a specific plot type
5. `render_plot` - Render a plot and return the result (supports demo, custom, and file modes)

## Examples

### Getting version
```text
→ get_version()
← "v0.1.3"
```

### Listing plot groups
```text
→ list_plot_groups()
← {
  "groups": [
    {"label": "统计二维", "plot_count": 5, ...},
    {"label": "学科二维", "plot_count": 29, ...},
    ...
  ]
}
```

### Rendering a box plot
```text
→ render_plot(
    mode: "demo",
    plot: "box",
    config: {
      "title": "Test Box Plot",
      "save_name": "test_box"
    }
  )
← {
  "success": true,
  "message": "Successfully rendered box",
  "image": { /* ImageContent with PNG data */ },
  "path": "/path/to/outputs/mcp/test_box.png",
  "plot_type": "box",
  "mode": "demo"
}
```

## Requirements

- Python 3.13.15
- Research Draw dependencies (varies by plot type)
- MCP Python package (`mcp>=1.0`)

## Plot Types Supported

The server supports all 50+ plot types from Research Draw, organized into four groups:
- Statistics 2D (box, violin, scatter, volcano, forest)
- Domain 2D (biomedical, clinical, materials, remote sensing, financial, psychological)
- 3D Plots (scatter3d, surface3d, wireframe3d, etc.)
- Maps (world, china, choropleth, raster, points)

## Notes

- The server forces headless mode (`MPLBACKEND=Agg`, `HEADLESS=1`) for compatibility with server environments
- Output files are saved to `outputs/mcp/` by default
- Some plot types require additional dependencies:
  - Maps: `maps`, `raster` extras
  - 3D plots like `isosurface3d`: `ml` extra
  - File mode: `data` extra (for pandas)