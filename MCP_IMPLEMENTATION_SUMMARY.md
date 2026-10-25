# Research Draw MCP Server Implementation Summary

## Status: dev-0.1.4 MCP expansion and tag-triggered GHCR workflow configured

The MCP server now exposes the original plot discovery and rendering tools plus workspace-scoped data import, inspection, validation, and output listing.

## MCP Implementation Baseline

### 1. Environment Setup (Phase 0 - Verified)
- Confirmed Python 3.13.15 availability via uv
- Verified core Research Draw functionality works (CLI demo renders)
- Tested multiple plot types: box (stats_2d), scatter3d (plots_3d), world (maps)

### 2. MCP Server Core (Phase 1 - Implemented)
- Created `src/mcp_server/` module with:
  - `__init__.py`: Empty init file
  - `runner.py`: Handles conversion from MCP parameters to CLI arguments and executes ResearchDrawApp
  - `server.py`: FastMCP-based MCP server with tool definitions

### 3. Read-Only Tools (Phase 2 - Implemented)
- `get_version()`: Returns the current version from the root `VERSION` file.
- `list_plot_groups()`: Returns 4 plot groups with metadata:
  - 统计二维: 5 plots (box, violin, scatter, volcano, forest)
  - 学科二维: 29 plots (biomedical, clinical, materials, etc.)
  - 三维图型: 11 plots (scatter3d, surface3d, wireframe3d, etc.)
  - 地理地图: 7 plots (world, china, choropleth, raster, points)
- `list_plots(group=None)`: Lists all plots or filtered by group with detailed metadata
- `get_plot_schema(plot)`: Returns detailed schema for any plot including:
  - Required fields
  - Optional fields with defaults
  - Dependencies (data, maps, ml extras)
  - Aliases and demo information

### 4. Core Render Tool (Phase 3 - Implemented)
- `render_plot(mode, plot, config)`: Main rendering tool supporting:
  - **demo mode**: Uses built-in demo data (no file needed)
  - **custom mode**: Renders from provided parameters (x, y, group, etc.)
  - **file mode**: Renders from data file (requires data extra for pandas)
  
  Returns:
  - Success status and message
  - Image content (as ImageContent with base64-encoded PNG)
  - Filesystem path to saved image
  - Plot type and mode used

## Added for dev-0.1.4

### Local workspace boundary
- Requires `RESEARCH_DRAW_MCP_WORKSPACE` for file and render tools.
- The configured directory must exist and be outside the project directory.
- Imported files are copied to `<workspace>/inputs/mcp/`.
- Rendered files are saved to `<workspace>/outputs/mcp/`.
- User supplied input paths are resolved and checked against the workspace boundary.
- Each render gets a unique output name, and the runner returns that exact file instead of selecting the most recently modified image.

### New MCP tools
- `import_data_file(source_path)`: Imports CSV, TSV, TXT, XLSX, or XLS from inside the workspace.
- `upload_data_file(filename, content_base64)`: Accepts a bounded Base64 upload from remote MCP clients.
- `list_workspace_files(limit, offset)`: Lists imported files in the managed input directory.
- `inspect_data_file(file_id, preview_rows)`: Returns columns, types, null counts, row count, and a bounded preview.
- `validate_plot_config(mode, plot, config)`: Checks CLI parameter schema, workspace paths, explicit column names, selected required fields, and basic dependency availability without rendering.
- `list_render_outputs(limit, offset)`: Lists recent rendered images saved inside the workspace.

### Remote amd64 Docker service
- `Dockerfile.mcp` builds an MCP-only Linux `amd64` image on Python 3.13.15; Web frontend and test dependencies are excluded.
- The image serves Streamable HTTP at `/mcp`; the existing stdio entry point remains the default outside HTTP mode.
- HTTP requests require a bearer token loaded from a Docker Secret file at container startup. The token is not stored in the image, build arguments, or repository.
- The HTTP endpoint applies Host/Origin allowlists, a 48 MiB MCP body limit, and stateless transport; Compose binds port 8000 to localhost for a TLS reverse proxy.
- Compose persists imported data and render outputs in a dedicated Docker volume. Remote clients can upload supported tables up to 32 MiB by default.
- A local `research-draw-mcp:dev-0.1.4-amd64` image was built before the project version source was advanced to v0.1.4; it has not been pushed to a registry.

### Tag-triggered image publishing
- `.github/workflows/publish-mcp-image.yml` runs only for `v*` tag pushes and validates a stable `vMAJOR.MINOR.PATCH` tag against `VERSION`.
- It publishes `linux/amd64` to `ghcr.io/keyingshuzhi/keying-research-draw-mcp` under `vX.Y.Z`, `X.Y.Z`, and `latest` tags.
- `.env*`, output folders, and local secret files are excluded from the build context; deployment settings and credentials are supplied only at runtime.

## Key Features

### Smart Parameter Handling
- Only exposes 3 top-level parameters: `mode`, `plot`, `config` (avoids overwhelming LLM with 100+ CLI parameters)
- `config` dictionary maps directly to CLI argument names (underscores converted to hyphens)
- Reuses existing Research Draw CLI validation and dependency system

### Robust Error Handling
- Graceful error returns instead of exceptions
- Clear dependency error messages (e.g., "文件模式读取 需要依赖 `pandas`")
- Headless mode enforced for server compatibility (`MPLBACKEND=Agg`)

### Multiple Output Formats
- Returns both filesystem path AND embedded image data
- Image returned as base64-encoded PNG in ImageContent format (MCP-native)
- Clients can either display image directly or read from file path

## Earlier Verification Results

Before the terminal environment issue occurred, I successfully tested:
- ✅ Version tool: Returned the version configured at the time
- ✅ List groups tool: Returns 4 groups with correct plot counts
- ✅ List plots tool: Returns 50+ plots with metadata
- ✅ Schema tool: Returns detailed schema for box plot (requires group_col, value_col)
- ✅ Render plot tool:
  - Demo mode box plot: Success, 55KB PNG image
  - Custom mode scatter plot: Success, 136KB PNG image  
  - Demo mode scatter3d plot: Success, 481KB PNG image
  - File mode: Properly reports missing pandas dependency when appropriate

## MCP Source Files

```
src/mcp_server/
├── __init__.py
├── runner.py          # Parameter conversion, rendering, and output paths
├── server.py          # FastMCP tool definitions
├── workspace.py       # Local workspace file management and path checks
├── http_auth.py       # Bearer-token ASGI middleware for remote HTTP mode
└── harness_bridge.py  # Compatibility bridge using the same workspace-scoped runner

Dockerfile.mcp          # MCP-only linux/amd64 image
compose.mcp.yaml        # Secret, persistent workspace volume, and localhost port binding

MCP_SERVER_README.md           # Setup and tool usage
MCP_IMPLEMENTATION_SUMMARY.md  # Implementation notes
```

## Usage

```bash
# Install with MCP support
uv sync --extra mcp

# Run the MCP server (stdio transport)
RESEARCH_DRAW_MCP_WORKSPACE="/path/to/research-draw-workspace" uv run research-draw-mcp

# The server will accept MCP connections from clients like:
# - Claude Desktop
# - Cursor
# - Any MCP-compatible client
```

## Dependencies Added

- `mcp>=1.0,<2.0` (MCP Python SDK)
- Added to `pyproject.toml` as both `mcp` extra and part of `all` extra
- Entry point: `research-draw-mcp = "src.mcp_server.server:main"`

## Design Decisions

1. **Lean MVP Approach**: Focused on core rendering functionality rather than data management/history tools
2. **Parameter Abstraction**: Reduced 100+ CLI parameters to 3 logical parameters for better LLM usability
3. **Dependency Reuse**: Leveraged existing Research Draw validation, demo data, and error handling systems
4. **Dual Output**: Provides both file path and embedded image for maximum client flexibility
5. **Headless Enforcement**: Ensures server compatibility in containerized/headless environments

The verification notes above describe the earlier MCP toolset. The current `dev-0.1.4` tools have not been run through an automated test suite in this change.

The current MCP implementation provides LLM clients with the ability to:
- Discover what plots are available
- Understand what parameters each plot requires
- Render plots and receive the results as displayable images
- Do all this through a standardized MCP interface
