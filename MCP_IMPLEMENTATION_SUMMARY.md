# Research Draw MCP Server Implementation Summary

## Status: v0.1.5 development — MCP workflow and session isolation implemented

The current development version is `v0.1.5` and has not yet been released. The MCP server exposes chart recommendations, one-step and batch rendering, result revision, detailed schemas and validation, file management, chunked uploads, and session-isolated workspaces.

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
  - 统计二维: 10 plots (box, violin, scatter, bar, column, line, histogram, area, volcano, forest)
  - 学科二维: 29 plots (biomedical, clinical, materials, etc.)
  - 三维图型: 11 plots (scatter3d, surface3d, wireframe3d, etc.)
  - 地理地图: 7 plots (world, china, choropleth, raster, points)
- `list_plots(group=None)`: Lists all plots or filtered by group with detailed metadata
- `get_plot_schema(plot)`: Returns detailed schema for any plot including:
  - Required fields
  - Optional fields with defaults
  - Dependency hints for file, map, and advanced plotting modes
  - Aliases and demo information

### 4. Core Render Tool (Phase 3 - Implemented)
- `render_plot(mode, plot, config)`: Main rendering tool supporting:
  - **demo mode**: Uses built-in demo data (no file needed)
  - **custom mode**: Renders from provided parameters (x, y, group, etc.)
  - **file mode**: Renders from data file (pandas and openpyxl are included in the base dependencies)
  
  Returns:
  - Success status and message
  - Image content (as ImageContent with base64-encoded PNG)
  - Filesystem path to saved image
  - Plot type and mode used

## MCP workspace handling

### Logical workspace selection
- The server maps configured logical names to physical directories through `RESEARCH_DRAW_MCP_WORKSPACES`.
- `RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE` names the default entry in that map. Tools accept an optional `workspace` name; clients do not pass filesystem paths.
- The configured directories must exist and be outside the project directory.
- Each MCP connection receives a private directory under `<workspace>/.mcp-sessions/<opaque-key>/`.
- Imported files are copied to the session directory's `inputs/mcp/`.
- Rendered files and revision manifests are saved under the session directory's `outputs/mcp/`.
- Chunked upload parts stay in the session's private staging directory and are removed after completion, cancellation, or expiry cleanup.
- User supplied input paths are resolved and checked against the workspace boundary. Files already present in the shared logical workspace can be imported by relative path, avoiding model-generated Base64 transfer; MCP-managed private session directories remain excluded.
- Each render gets a unique output name, and the runner returns that exact file instead of selecting the most recently modified image.

### New MCP tools
- `list_workspaces()`: Lists configured logical names and the default without exposing filesystem paths.
- `suggest_plots(file_id, goal, workspace?)`: Profiles numeric, categorical, date, and identifier columns; ranks chart recommendations and provides field mappings.
- `create_plot(file_id, goal, plot?, config?, workspace?)`: Selects or accepts a chart, infers file-column mappings, validates the request, renders it, and returns the image and diagnostics.
- `create_plots(file_id, goal, plots, config?, plot_configs?, workspace?)`: Inspects one file once and renders several requested chart types with shared or per-chart overrides.
- `start_render_job(request_id, mode, plot, config, ...)` provides a required-argument path for asynchronous direct renders; `start_plot_job(operation, request_id, ...)` handles file plots, batches, and revisions. `get_plot_job_status` and `get_plot_job_result` poll durable status and retrieve typed image results.
- `revise_plot(render_id, changes, workspace?)`: Reuses stored plot parameters and rerenders with title, palette, colormap, or axis-label changes.
- `import_data_file(source_path, workspace?)`: Imports CSV, TSV, TXT, XLSX, or XLS from the current session or shared logical workspace root. Shared-root reads are bounded to the selected allowlisted workspace, then copied into the current session input area.
- `upload_data_file(filename, content_base64, workspace?)`: Accepts a bounded Base64 upload into the selected workspace.
- `begin_data_upload`, `upload_data_chunk`, `complete_data_upload`, and `cancel_data_upload`: Upload tables in session-scoped chunks up to 200 MiB total by default, with 4 MiB maximum decoded chunks and 16,384 chunks per upload. The model-facing default is 8 KiB per chunk to keep Base64 tool arguments bounded even for high-entropy data; direct SDK clients may select larger chunks. Gzip remains optional and is useful only when it reduces the payload.
- `list_workspace_files(limit, offset, workspace?)`: Lists imported files in the selected workspace's managed input directory.
- `inspect_data_file(file_id, preview_rows, workspace?)`: Returns columns, types, null counts, row count, and a bounded preview from the selected workspace.
- `validate_plot_config(mode, plot, config, workspace?)`: Checks CLI parameter schema, paths in the selected workspace, explicit column names, selected required fields, and basic dependency availability; returns structured diagnostics and safe column-name suggestions.
- `get_plot_schema(plot)`: Returns field-level types, descriptions, examples, defaults, choices, ranges, and mode requirements.
- `list_render_outputs(limit, offset, workspace?)`: Lists recent rendered images for the current session, including `render_id` and revision availability.

### MCP usability improvements
- `suggest_plots` infers column roles from a bounded data preview, ranks general and goal-matched specialist charts, and returns rationale, field mappings, and ready-to-use configs. Specialist suggestions require recognizable field names where the meaning cannot be inferred from a data type alone.
- `create_plot` combines file inspection, suggestions, mapping, validation, and rendering. It returns the image and saved path with the selected chart, mappings, warnings, diagnostics, and column profile; unresolved required fields are reported for an explicit retry.
- `get_plot_schema` exposes parameter types, descriptions, examples, defaults, choices, known ranges, and mode requirements. File mode additionally describes column roles, alternative required field groups, and minimum data requirements.
- `validate_plot_config` preserves readable errors and warnings while adding machine-readable diagnostics, candidate column names, and a corrected config only when the best correction is sufficiently distinct.
- Batch rendering reuses one table inspection and returns each chart's outcome independently. Revision manifests preserve the original result and generate a new render; only visual fields can be changed through `revise_plot`.
- Long and batch renders can use an idempotent asynchronous job flow, so MCP clients receive a job ID before rendering starts and can recover after transport timeouts. Job state is private to the session workspace, retained for seven days, and capped at eight active jobs per session; interrupted in-process work is reported explicitly after server restart. Completed chart images are returned as typed MCP image blocks separately from the structured metadata.
- Direct render tool calls also move the blocking render work off the MCP event loop, so status and unrelated MCP requests remain serviceable while a caller waits for a quick render.
- Chunked upload stores each Base64 chunk separately, rejects duplicate chunks and incomplete finalization, and only publishes a file after its assembled size matches the declaration. The default model-facing chunk is 8 KiB, while larger chunks remain available to programmatic clients; per-upload chunk count is bounded.
- HTTP transport is stateful so each MCP session maps to an opaque session directory. Stdio uses one private workspace per server process.

### Remote amd64 Docker service
- `Dockerfile.mcp` builds an MCP-only Linux `amd64` image on Python 3.13.15; Web frontend and test dependencies are excluded.
- The image serves Streamable HTTP at `/mcp`; the existing stdio entry point remains the default outside HTTP mode.
- HTTP requests require a bearer token loaded from a Docker Secret file at container startup. The token is not stored in the image, build arguments, or repository.
- The HTTP endpoint applies Host/Origin allowlists, a 48 MiB MCP body limit, and stateful transport; Compose binds port 8000 to localhost for a TLS reverse proxy.
- Compose bind-mounts a deployment-configured common host workspace root at `/host-workspaces`; the server resolves logical names from its allowlist into that mount. Remote clients can upload supported tables up to 32 MiB in one request or 200 MiB through chunks by default.
- Sessions choosing the same logical workspace have separate file namespaces; separate logical workspaces are still recommended for different trust domains.

### Tag-triggered image publishing
- `.github/workflows/publish-mcp-image.yml` runs for `v*` tag pushes or a manual retry from the exact existing release-tag ref; it validates a stable `vMAJOR.MINOR.PATCH` tag against `VERSION`.
- It publishes `linux/amd64` to `ghcr.io/keyingshuzhi/keying-research-draw-mcp` under `vX.Y.Z`, `X.Y.Z`, and `latest` tags when a matching stable version tag is pushed.
- `.env*`, output folders, and local secret files are excluded from the build context; deployment settings and credentials are supplied only at runtime.

## Key Features

### Smart Parameter Handling
- Exposes `mode`, `plot`, `config`, and an optional logical `workspace` selector (avoids overwhelming LLM with 100+ CLI parameters)
- `config` dictionary maps directly to CLI argument names (underscores converted to hyphens)
- Reuses existing Research Draw CLI validation and dependency system

### Robust Error Handling
- Graceful error returns instead of exceptions
- Clear dependency guidance for optional map and machine-learning plotting extras
- Headless mode enforced for server compatibility (`MPLBACKEND=Agg`)

### Multiple Output Formats
- Returns both filesystem path AND embedded image data
- Image returned as base64-encoded PNG in ImageContent format (MCP-native)
- Clients can either display image directly or read from file path

## Earlier Verification Results

Before the terminal environment issue occurred, I successfully tested:
- ✅ Version tool: Returned the version configured at the time
- ✅ List groups tool: Returns 4 groups with correct plot counts
- ✅ List plots tool: Returned the then-current plot catalog with metadata
- ✅ Schema tool: Returns detailed schema for box plot (requires group_col, value_col)
- ✅ Render plot tool:
  - Demo mode box plot: Success, 55KB PNG image
  - Custom mode scatter plot: Success, 136KB PNG image  
  - Demo mode scatter3d plot: Success, 481KB PNG image
  - File mode: The earlier baseline reported missing file-reading dependencies clearly; pandas is now included in the base dependencies

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
compose.mcp.yaml        # Secret, common host workspace-root bind mount, and localhost port binding

MCP_SERVER_README.md           # Setup and tool usage
MCP_IMPLEMENTATION_SUMMARY.md  # Implementation notes
```

## Usage

```bash
# Install with MCP support
uv sync --extra mcp

# Run the MCP server (stdio transport)
RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE="research" \
RESEARCH_DRAW_MCP_WORKSPACES='{"research":"/path/to/research-draw-workspace"}' \
uv run --extra mcp research-draw-mcp

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

1. **Task-oriented tools**: Provide recommendation, one-step rendering, batch comparison, and revision while retaining explicit low-level tools
2. **Parameter abstraction**: Keep detailed CLI parameters inside a config object and expose typed schema guidance
3. **Dependency reuse**: Use Research Draw validation, demo data, and rendering paths
4. **Dual output**: Return both a saved file path and embedded image data
5. **Session isolation**: Keep each MCP session's imported files and renders in its own directory
6. **Headless enforcement**: Ensure server compatibility in containerized/headless environments

## v0.1.5 Acceptance Status

The project owner has confirmed completion of the v0.1.5 end-to-end testing. The recorded Koying Pilot scenarios and their concrete results are maintained in [the manual MCP test record](tests/manual/mcp-v0.1.5/MCP_v0.1.5_KoyingPilot_人工端到端测试.md), including workspace-file transfer, chunked upload, data inspection, plotting, asynchronous rendering, and result handoff. The verification notes above describe the earlier MCP baseline and should be read as historical checks, not as the v0.1.5 acceptance record. The remote GHCR image build remains a separate release operation.

The current MCP implementation provides LLM clients with the ability to:
- Discover and understand available plots and their parameters
- Analyze uploaded data and receive plot recommendations with field mappings
- Create one chart, batch several chart types, or revise an existing result
- Upload, inspect, and validate data with actionable diagnostics
- Keep data and render outputs isolated by MCP session
- Receive rendered results as displayable images through a standardized MCP interface
