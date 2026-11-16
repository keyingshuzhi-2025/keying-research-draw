# Research Draw MCP Server

This is an MCP (Model Context Protocol) server for the Research Draw scientific visualization toolkit.

当前开发版本：`v0.1.5`（尚未发布）。MCP 工具、工作区隔离和分块上传均以本版本实现为准。

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

本地运行前，需要配置独立于项目目录的工作区。服务会在逻辑工作区内按 MCP 会话创建隐藏的隔离目录，数据副本、待上传分块和绘图结果分别放入会话目录下的 `inputs/mcp/`、`.mcp-upload-staging/` 和 `outputs/mcp/`。

### 柯影智航 MCP 服务注册指南

在柯影智航的服务注册表单中填写：

1. **基本信息**

   - 服务标识：`research-draw`
   - 显示名称：`Research Draw 科研绘图`
   - 描述：`专业科研可视化工具，支持统计图、领域专业图、3D图及离线地图渲染。`

2. **连接配置**

   - 连接方式：本地命令（stdio）
   - 启动命令：`/opt/homebrew/bin/uv`
   - 参数：

     ```text
     run
     --project
     /Volumes/柯影数智/研发部/项目/keying-research-draw
     --extra
     mcp
     research-draw-mcp
     ```

   - 工作目录：`/Volumes/柯影数智/研发部/项目/keying-research-draw`

   工作目录请填写柯影智航本机安装的项目根目录绝对路径。

   本地 stdio 模式不需要配置“环境变量凭据引用”；没有需要注入的密钥时留空即可。MCP 运行所需的工作区变量应放在普通环境变量配置中：`RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE` 与 `RESEARCH_DRAW_MCP_WORKSPACES`。例如：

   ```text
   RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE=research
   RESEARCH_DRAW_MCP_WORKSPACES={"research":"/path/to/existing/research-workspace"}
   ```

   启动参数中的 `--extra mcp` 会让 `uv` 同步 MCP SDK。若继续使用 `run research-draw-mcp`，但当前项目环境未安装 `mcp` extra，服务会因缺少 Python 包而在初始化时退出。

工作区由服务端通过逻辑名称配置。调用方可以传 `workspace` 选择允许的工作区，也可以省略工作区参数并使用默认值；如需限制本地 stdio 服务可访问的目录，可设置共同根目录：

```text
PYTHONPATH=.
MPLBACKEND=Agg
PLOT_BACKEND=Agg
HEADLESS=1
RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT=/Volumes/柯影数智/研发部/实验
RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE=research
RESEARCH_DRAW_MCP_WORKSPACES='{"research":"/Volumes/柯影数智/研发部/实验/research","team-a":"/Volumes/柯影数智/研发部/实验/team-a"}'
```

`RESEARCH_DRAW_MCP_WORKSPACES` 是逻辑工作区名到服务端绝对路径的 JSON allowlist。目录必须预先存在；配置共同根目录时，所有映射路径都必须位于该根目录内。`list_workspaces` 仅返回逻辑名和默认标记，不返回绝对路径。每个 MCP 会话在选定工作区下有自己的隐藏目录，导入文件、上传暂存分块和绘图结果都写入该会话目录；同一逻辑工作区的其他会话无法通过 MCP 工具枚举或读取这些文件。

```bash
mkdir -p "/Volumes/柯影数智/研发部/实验/research" "/Volumes/柯影数智/研发部/实验/team-a"
```

```bash
cd "/Volumes/柯影数智/研发部/项目/keying-research-draw"
RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT="/Volumes/柯影数智/研发部/实验" \
RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE=research \
RESEARCH_DRAW_MCP_WORKSPACES='{"research":"/Volumes/柯影数智/研发部/实验/research","team-a":"/Volumes/柯影数智/研发部/实验/team-a"}' \
/opt/homebrew/bin/uv run --extra mcp research-draw-mcp
```

`RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE` 必须是 `RESEARCH_DRAW_MCP_WORKSPACES` 中配置的逻辑名。工具调用可省略 `workspace` 使用该默认工作区，也可显式传入 allowlist 中的逻辑名。工作区选择不接受客户端传入的绝对路径。

This will start the MCP server using stdio transport, ready to accept connections from MCP clients.

### 远程 Docker 部署（amd64）

仓库提供只包含 MCP 服务的 Linux `amd64` 镜像，不打包 Web 前端。镜像基于 Python 3.13.15，保留绘图源码和只读离线地图/示例数据；容器以非 root 用户运行。容器只 bind mount `RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT` 指定的共同宿主机目录到 `/host-workspaces`，不把数据持久化在容器层或 Docker volume 中。Compose 将逻辑工作区 allowlist 和默认工作区注入容器；所有映射路径仍限制在共同根目录之内。`.env` 运行配置及令牌文件均不进入镜像，运行配置由 Compose 注入，令牌由 Docker Secret 提供。`.dockerignore` 会排除 `.env*`、输出目录和本地密钥文件，Dockerfile 只复制明确列出的源码、依赖清单和静态数据目录。

HTTP MCP 的调用方可省略工作区参数并使用默认逻辑工作区，也可传入 `workspace` 选择 allowlist 中的目录。服务器只接受位于 `RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT` 之下、且容器挂载中实际存在的目录。请将共同根目录设为实际需要的最窄父目录；例如仅覆盖实验工作区时，可设置为 `/Volumes/柯影数智/研发部/实验`。这会把该共同根目录以读写方式提供给容器。容器以非 root 用户运行：Linux 通常使用 UID/GID `10001:10001`，macOS 应将 `RESEARCH_DRAW_MCP_UID` 和 `RESEARCH_DRAW_MCP_GID` 设为工作区所属账号 ID；容器仍会以附加组 `10001` 读取 Docker Secret。

`RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT` 是服务端的存储边界。逻辑工作区名通过 allowlist 映射到服务端目录；客户端传逻辑名，或省略参数使用默认工作区，不需要传客户端机器上的绝对路径。服务使用有状态 Streamable HTTP 会话，并以 MCP 连接对应的服务端会话对象派生不可预测的目录名；不同会话即使选择同一个逻辑工作区，也会分别写入 `<logical-workspace>/.mcp-sessions/<opaque-session-key>/`。stdio 部署按服务进程隔离。不同信任域仍建议配置不同逻辑工作区。本机 Docker 测试可把 `/Volumes/柯影数智/研发部/实验` 作为共同根目录；部署到阿里云时，应改为服务器上的数据盘或共享存储路径（例如 `/srv/koying/workspaces`），并确保 allowlist 中的目录都位于该目录下。

所有工作区工具都可使用顶层参数 `workspace`，例如 `workspace: "research"`；省略它时使用默认工作区。客户端只选择逻辑名称，物理目录由服务端 allowlist 配置；`render_plot` 的 `workspace` 不能放入 `config`。

服务通过 Streamable HTTP 提供于 `/mcp`。柯影智航连接例如 `https://mcp.example.com/mcp`，并设置请求头 `Authorization: Bearer <团队签发的令牌>`。团队管理员负责核实接入团队、签发和轮换令牌；团队共用令牌标识团队级访问，不能区分具体成员。

推送与根目录 `VERSION` 相符的稳定版本 tag（例如 `v0.1.5`）会自动构建 `linux/amd64` 镜像并发布到 GHCR。发布完成后，镜像地址为 `ghcr.io/keyingshuzhi/keying-research-draw-mcp`，并使用 `vX.Y.Z`、`X.Y.Z` 和 `latest` 标签。管理员可从 Actions 手动重试：必须把 workflow ref 选为已存在的目标 release tag，并在输入框填写同一个 tag；workflow 会拒绝从分支或其他 tag 构建，以确保代码来源与镜像版本一致。workflow 使用 `GITHUB_TOKEN` 发布并关联源仓库；GitHub 说明由工作流创建的 package 会继承该仓库的可见性和权限模型。当前源仓库为公开仓库，因此镜像预期可匿名拉取；package 可见性仍可单独管理，首次发布后可在 GitHub Packages 页面确认。详见 [GitHub Actions package 权限说明](https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions)和 [GHCR 可见性说明](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility)。workflow 不使用仓库中的环境配置或密钥作为 build input。

建议在仓库 Rulesets 中限制 `v*` release tag 的创建和更新权限，只允许发布管理员操作；workflow 本身会拒绝非稳定版本号以及与 `VERSION` 不一致的 tag。

正式发布并确认版本号后，推送 tag 的示例（这会触发 GHCR 镜像构建）：

```bash
git tag v0.1.5
git push origin v0.1.5
```

在部署服务器上创建令牌文件，令牌至少 32 个可见 ASCII 字符：

```bash
sudo install -d -m 700 /etc/research-draw
sudo install -o root -g 10001 -m 440 /dev/null /etc/research-draw/mcp-token
openssl rand -hex 32 | sudo tee /etc/research-draw/mcp-token >/dev/null
```

令牌文件的组 ID `10001` 对应容器内的 MCP 用户组，使非 root 容器进程可以读取 Secret。若服务器使用 rootless Docker 或 user-namespace remapping，需按主机映射后的 UID/GID 调整文件属主和权限。

把 `.env.mcp.example` 复制为 `.env`，设置实际域名、镜像标签、默认逻辑工作区、逻辑工作区 JSON allowlist、Docker Secret 文件路径，以及包含这些目录的共同宿主机根目录。allowlist 中的目录必须预先存在；macOS 还需把 UID/GID 设为工作区所属账号的 `id -u` 与 `id -g` 输出，再在仓库目录拉取并启动：

```bash
cp .env.mcp.example .env
# Edit .env: set the default workspace, JSON workspace allowlist, host root, image, and (on macOS) the owning account's UID/GID.
docker compose -f compose.mcp.yaml pull
docker compose -f compose.mcp.yaml up -d --no-build
```

Compose 使用禁用自动建目录的 bind mount；共同根目录不存在时启动会失败，避免 Docker 自动创建错误路径。

Compose 会使用 `.env` 中的 `RESEARCH_DRAW_MCP_IMAGE`，并把令牌文件作为运行时 Docker Secret 挂载到 `/run/secrets/research_draw_mcp_token`。镜像、构建参数和代码库均不包含令牌值。HTTP 模式在令牌文件缺失或格式不符合要求时会拒绝启动；令牌在进程启动时读取，轮换后需重新创建容器：

```bash
docker compose -f compose.mcp.yaml up -d --force-recreate
```

容器端口默认只绑定服务器的 `127.0.0.1:8000`，由同机反向代理转发并终止 HTTPS。请配置代理速率限制和请求体限制，并通过 `.env` 中的 `RESEARCH_DRAW_MCP_ALLOWED_HOSTS` 设置实际域名；若客户端发送 `Origin`，还需设置 `RESEARCH_DRAW_MCP_ALLOWED_ORIGINS`。部署时不要将明文 HTTP 端口直接暴露到公网。镜像的 HTTP 请求体上限默认为 48 MiB；单次 `upload_data_file` 默认接受不超过 32 MiB。分块上传默认总上限 200 MiB（`RESEARCH_DRAW_MCP_MAX_CHUNKED_UPLOAD_MB`），每块最多 4 MiB，最多 16,384 块。模型工具调用默认使用 8 KiB 原始分块，以控制 Base64 参数大小；高熵数据即使 gzip 后也可能接近原大小，因此小块比依赖压缩更可靠。直接 MCP SDK 客户端可显式采用更大的分块，减少调用次数。调高单次上传或分块大小时，也要相应调整 `RESEARCH_DRAW_MCP_MAX_REQUEST_BODY_MB` 和反向代理请求体上限；HTTP 请求体配置最高为 256 MiB。与 MCP 服务共享逻辑工作区目录的客户端应优先调用 `import_data_file(source_path)`，传入相对路径，由服务器直接读取文件，避免经模型工具参数传送 Base64。

文件已在共享逻辑工作区目录时，调用 `import_data_file(source_path)` 并传入相对路径；服务器会在逻辑工作区根目录或当前会话目录读取并复制文件，路径限定在当前逻辑工作区内，不能读取 MCP 管理的其他会话私有目录。客户端与服务器不共享文件系统时，小文件可调用 `upload_data_file(filename, content_base64)`；大文件使用 `begin_data_upload(filename, total_size)` 分块传输，默认每块 8 KiB，按返回的 `chunk_size`（原始字节数）从 `chunk_index: 0` 开始逐段调用 `upload_data_chunk(upload_id, chunk_index, content_base64)`，最后调用 `complete_data_upload(upload_id)`；中止时可调用 `cancel_data_upload(upload_id)`。模型客户端应优先遵循较小的默认分块，不要假设 gzip 一定能缩小数据；若压缩有效，可对每块独立 gzip，再 Base64 编码并设置 `content_encoding="gzip"`。服务端会先限制解压后的长度，再写入原始分块。未设置 `content_encoding` 时仍按原有 Base64 原始分块处理。每个上传 ID 只在创建它的 MCP 会话内有效，缺失分块会在完成时列出，重复分块不会覆盖原数据。工具返回的 `path` 是宿主机路径，`workspace_relative_path` 相对当前会话目录；渲染图片也会随 MCP 工具响应返回。

令牌文件通过 Compose Secret 注入；Docker 官方资料说明了 [Compose Secret 的文件挂载方式](https://docs.docker.com/compose/how-tos/use-secrets/)以及 [构建阶段不应通过 `ARG`/`ENV` 传递密钥](https://docs.docker.com/reference/build-checks/secrets-used-in-arg-or-env/)。

```text
→ upload_data_file(filename: "study.csv", content_base64: "<standard-base64-file-bytes>")
← {"success": true, "file_id": "a1b2c3d4e5f6_study.csv", "size": 12345, ...}
```

Use the returned `file_id` in `validate_plot_config` and `render_plot`.

### Available Tools

The server exposes the following tools:

1. `get_version` - Get the version of Research Draw
2. `list_workspaces` - List configured logical workspaces without filesystem paths
3. `list_plot_groups` - List all available plot groups with metadata
4. `list_plots` - List available plots, optionally filtered by group
5. `get_plot_schema` - Get field-level types, descriptions, examples, defaults, choices, ranges, and mode requirements
6. `suggest_plots` - Analyze a table and rank suitable charts with suggested column mappings
7. `import_data_file` - Copy a supported local table into the selected workspace input folder
8. `upload_data_file` - Receive a base64-encoded table from a remote MCP client (32 MB default limit)
9. `begin_data_upload` - Start a session-scoped chunked upload (200 MB default total limit)
10. `upload_data_chunk` - Store one Base64 chunk, up to 4 MiB decoded; optionally accept an independently gzip-compressed chunk with `content_encoding="gzip"`
11. `complete_data_upload` - Verify and assemble all chunks into a data file
12. `cancel_data_upload` - Remove an unfinished chunked upload
13. `list_workspace_files` - List imported data files in the current session
14. `inspect_data_file` - Inspect columns, data types, missing values, and a short preview
15. `validate_plot_config` - Check plot parameters and return structured diagnostics and repair suggestions
16. `create_plot` - Map columns, validate, render, and return one result
17. `create_plots` - Inspect one file once and render several chart types with shared or per-chart settings
18. `render_plot` - Render a plot in demo, custom, or file mode and return a `render_id`
19. `revise_plot` - Change a prior render's title, palette, colormap, or axis labels and render a new result
20. `list_render_outputs` - List recent images and their `render_id` values in the current session
21. `start_render_job` - Submit a direct complex or slow plot with required mode, plot, and config arguments
22. `start_plot_job` - Submit file-based, batch, or revision work and return a durable job ID
23. `get_plot_job_status` - Check whether a render job is queued, running, or complete
24. `get_plot_job_result` - Retrieve completed metadata and typed MCP image blocks; retry safely after a transfer timeout

`import_data_file` accepts a source path inside the current session or shared logical workspace root. Shared-root imports are copied into the current session input directory; MCP-managed private session directories cannot be used as import sources. Upload and import support CSV, TSV, TXT, XLSX, and XLS. The default local import limit is 200 MB (`RESEARCH_DRAW_MCP_MAX_IMPORT_MB`), the single-request upload limit is 32 MB (`RESEARCH_DRAW_MCP_MAX_UPLOAD_MB`), and the chunked upload total limit is 200 MB (`RESEARCH_DRAW_MCP_MAX_CHUNKED_UPLOAD_MB`). Each MCP session has a separate input/output namespace even when sessions select the same logical workspace.

## Examples

### Getting version
```text
→ get_version()
← "v0.1.5"
```

### Listing plot groups
```text
→ list_plot_groups()
← {
  "groups": [
    {"label": "统计二维", "plot_count": 10, ...},
    {"label": "学科二维", "plot_count": 29, ...},
    ...
  ]
}
```

### Getting plot recommendations and creating a chart

```text
→ suggest_plots(file_id: "a1b2c3d4e5f6_study.csv", goal: "比较不同处理组的指标分布")
← {
  "success": true,
  "analysis": {
    "numeric_columns": ["expression"],
    "categorical_columns": ["treatment"],
    "datetime_columns": []
  },
  "recommendations": [
    {
      "plot": "box",
      "display_name": "箱线图",
      "field_mapping": {"group_col": "treatment", "value_col": "expression"},
      "suggested_config": {"file": "a1b2c3d4e5f6_study.csv", "group_col": "treatment", "value_col": "expression"}
    }
  ]
}

→ create_plot(file_id: "a1b2c3d4e5f6_study.csv", goal: "比较不同处理组的指标分布")
← {"success": true, "plot_type": "box", "field_mapping": {...}, "image": ..., "path": ...}
```

`create_plot` automatically selects the highest-ranked compatible chart when `plot` is omitted. Provide `plot` to choose a chart explicitly, and use `config` to override inferred columns or style settings.

`suggest_plots` profiles up to 20 preview rows for numeric, categorical, date/time, identifier, and binary columns. It returns each recommendation's score, rationale, mapped columns, and a ready-to-use file-mode config. Name-based matches are heuristics; review the returned `analysis` and `field_mapping` before relying on an automatically selected specialist plot.

`get_plot_schema(plot)` includes a `parameters` array. Every parameter reports its type, meaning, applicable modes, required modes, example, default (`null` means none is defined), choices, and range (`null` means no range is declared). File-driven plots also return `file_input_columns`, `file_required_field_groups`, and `file_data_requirements`; a required field group means one of the listed alternatives is needed.

`validate_plot_config(mode, plot, config)` keeps the original `errors` and `warnings` and adds structured `diagnostics` plus an `auto_mapping` inferred from the inspected file. A diagnostic includes `severity`, `code`, `field`, `message`, and when available a repair suggestion or candidate columns. `suggested_config` is returned only when a correction is sufficiently unambiguous.

`create_plot` performs inspection, recommendation, column mapping, validation, and rendering in one call. Its response includes the rendered `image` and `path`, selected chart, `field_mapping`, data warnings, diagnostics, and analysis profile. If it cannot infer a required field, it returns `stage: "field_mapping"` with `missing_fields` so the caller can retry with explicit column names in `config`.

`create_plots(file_id, goal, plots, config, plot_configs)` inspects the file once, then validates and renders each requested chart. `config` applies shared style options; `plot_configs` maps chart names to per-chart overrides. The response contains one result per requested chart, including failures and warnings, and succeeds when at least one chart renders.

Each successful `render_plot`, `create_plot`, or `create_plots` result includes a `render_id`. `revise_plot(render_id, changes)` loads the saved render parameters and creates a new output after applying only the requested style changes. Supported keys are `title`, `palette`, `cmap`, `xlabel`, `ylabel`, and `zlabel`; the original result remains available. `list_render_outputs` also returns each output's `render_id` and whether its saved parameters can be revised. Render records larger than 2 MiB and outputs created before this feature may not have a saved revision record.

### Batch drawing and revising a result

```text
→ create_plots(
    file_id: "a1b2c3d4e5f6_study.csv",
    goal: "比较不同处理组的指标",
    plots: ["box", "violin", "column"],
    config: {"title": "Treatment comparison"},
    plot_configs: {"column": {"xlabel": "Treatment", "ylabel": "Mean value"}}
  )
← {"success": true, "success_count": 3, "results": [{"plot": "box", "render_id": "...", ...}, ...]}

→ revise_plot(render_id: "box_...", changes: {"title": "Revised title", "palette": "Set2", "ylabel": "Expression"})
← {"success": true, "source_render_id": "box_...", "render_id": "box_...", ...}
```

### Long-running plots and timeout recovery

Direct calls to `render_plot`, `create_plot`, `create_plots`, and `revise_plot` wait for rendering to finish, so use them for quick renders. Their rendering work is moved off the MCP event loop so other requests can still be served. Complex direct plots can outlast an agent's tool-call timeout; submit them through `start_render_job`, whose `mode`, `plot`, and `config` arguments are all required at the tool-schema level. File-based plots, batch requests, and revisions use `start_plot_job`. Both tools persist the request and return a job ID without waiting for rendering. For revisions pass `render_id` and `changes`:

```text
→ start_plot_job(
    operation: "create_plot",
    request_id: "analysis-2026-11-15-01",
    file_id: "a1b2c3d4e5f6_study.csv",
    goal: "比较不同处理组的指标分布"
  )
← {"success": true, "job_id": "<opaque-id>", "state": "queued", "poll_after_seconds": 3, ...}

→ get_plot_job_status(job_id: "<opaque-id>")
← {"success": true, "state": "running", "stage": "rendering", "poll_after_seconds": 3, ...}

→ get_plot_job_status(job_id: "<opaque-id>")
← {"success": true, "state": "succeeded", "result_summary": {"render_ids": ["..."]}, ...}

→ get_plot_job_result(job_id: "<opaque-id>")
← structured metadata: {"success": true, "state": "succeeded", "result": {"path": ..., ...}}
← image content block: <rendered chart>
```

For a direct render, submit the required arguments explicitly:

```text
→ start_render_job(
    request_id: "ocean-flow-2026-11-15-01",
    mode: "custom",
    plot: "quiver3d",
    config: {"x": [...], "y": [...], "z": [...], "u": [...], "v": [...], "w": [...], "fmt": "png"}
  )
← {"success": true, "job_id": "<opaque-id>", "state": "queued", "poll_after_seconds": 3, ...}
```

```text
→ start_plot_job(
    operation: "revise_plot",
    request_id: "revise-2026-11-15-01",
    render_id: "box_...",
    changes: {"title": "Updated comparison", "palette": "Set2"}
  )
← {"success": true, "job_id": "<opaque-id>", ...}
```

Retry `start_plot_job` with the same `request_id` and identical parameters if its response is lost; the server returns the original job instead of rendering a duplicate. A request ID must be 1–128 characters using letters, digits, `.`, `_`, `:`, or `-`; use a new ID for a genuinely new request. A request ID reused with different parameters is rejected. Job IDs are private, unguessable capabilities; treat them like access tokens and do not share them.

Job metadata is stored in the selected session workspace for seven days. At most eight jobs per session may be queued or running; this prevents an agent from creating an unbounded backlog. The process uses one render worker, so queued jobs can wait while another chart is rendering. Poll at the returned `poll_after_seconds` interval. If an explicit logical `workspace` was used on submission, pass the same name when checking status and fetching the result.

If the MCP server process stays alive during a client/network timeout, the render continues and can be recovered with the same request ID. After a server restart, queued jobs are resumed when queried. A job interrupted while running is marked `server_interrupted` because the server cannot know whether rendering finished just before it stopped. In that case inspect `list_render_outputs` before retrying with a new request ID; completed files remain in the workspace. A completed result can be fetched again if image transfer times out.

### Chunked upload

```text
→ begin_data_upload(filename: "large-study.csv", total_size: 73400320, chunk_size: 4194304)
← {"success": true, "upload_id": "...", "chunk_size": 4194304, "chunk_count": 18}

→ upload_data_chunk(upload_id: "...", chunk_index: 0, content_base64: "<Base64 of gzip-compressed first chunk>", content_encoding: "gzip")
← {"success": true, "chunk_index": 0, "received_bytes": 4194304, "content_encoding": "gzip", ...}
→ ... upload remaining chunk indexes ...
→ complete_data_upload(upload_id: "...")
← {"success": true, "file_id": "..._large-study.csv", "size": 73400320, ...}
```

Direct MCP SDK clients may use larger chunks as shown above. Model-facing clients should use the default 8 KiB chunk size; this bounds each Base64 argument even when the file is incompressible, at the cost of more tool calls. Gzip each chunk independently only when it reduces the payload, and set `content_encoding="gzip"`; `chunk_size` always describes the original bytes. Otherwise, omit `content_encoding` or use `"identity"`. The client must use the returned `chunk_size`, send each index once, and call `complete_data_upload` after all chunks have been acknowledged. Uploads are limited to 16,384 chunks. Pending uploads expire after 24 hours and are removed the next time an upload begins in that session.

### Validating a configuration

```text
→ validate_plot_config(mode: "file", plot: "box", config: {"file": "a1b2c3d4e5f6_study.csv", "group_col": "treatmnt", "value_col": "expression"})
← {
  "valid": false,
  "diagnostics": [{
    "severity": "error",
    "code": "unknown_column",
    "field": "group_col",
    "candidate_columns": ["treatment"],
    "suggestion": "将 group_col 改为“treatment”后再校验。"
  }],
  "suggested_config": {"file": "...", "group_col": "treatment", "value_col": "expression"}
}
```

### Importing and inspecting a data file

```text
→ list_workspaces()
← {"success": true, "workspaces": [{"name": "research", "is_default": true}, ...]}

→ import_data_file(source_path: "study.csv", workspace: "research")
← {"success": true, "file_id": "a1b2c3d4e5f6_study.csv", ...}

→ inspect_data_file(file_id: "a1b2c3d4e5f6_study.csv", workspace: "research")
← {"columns": [{"name": "group", "dtype": "object"}, ...], "preview_rows": [...], ...}
```

Use the returned `file_id` as `config.file` in `validate_plot_config` and `render_plot`. Data inputs and generated images are restricted to the configured workspace.

### Listing workspace files and renders

```text
→ list_workspace_files(limit: 50, offset: 0)
→ list_render_outputs(limit: 50, offset: 0)
```

`validate_plot_config` takes the same `mode`, `plot`, and `config` values as `render_plot`; it reports schema errors, missing files, and columns that do not exist without creating a figure.

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
  "path": "/path/to/research-draw-workspace/.mcp-sessions/<opaque-key>/outputs/mcp/test_box_<id>.png",
  "render_id": "test_box_<id>",
  "plot_type": "box",
  "mode": "demo"
}
```

### Rendering a basic 2D chart

```text
→ render_plot(mode: "demo", plot: "column", config: {"title": "Monthly values"})
← {"success": true, "plot_type": "column", ...}

→ render_plot(mode: "custom", plot: "line", config: {"x": [1, 2, 3], "y": [4, 6, 5], "marker": "s"})
← {"success": true, "plot_type": "line", ...}
```

## Requirements

- Python 3.13.15
- Research Draw dependencies (varies by plot type)
- MCP Python package (`mcp>=1.0`)

## Plot Types Supported

The server supports 57 plot types from Research Draw, organized into four groups:
- Statistics 2D (box, violin, scatter, bar, column, line, histogram, area, volcano, forest)
- Domain 2D (biomedical, clinical, materials, remote sensing, financial, psychological)
- 3D Plots (scatter3d, surface3d, wireframe3d, etc.)
- Maps (world, china, choropleth, raster, points)

## Notes

- The server forces headless mode (`MPLBACKEND=Agg`, `HEADLESS=1`) for compatibility with server environments
- Output files are saved to `<selected-workspace>/.mcp-sessions/<opaque-key>/outputs/mcp/`
- Imported tables are copied to `<selected-workspace>/.mcp-sessions/<opaque-key>/inputs/mcp/`
- Pending upload chunks are stored in the current session's private staging directory and are removed after completion or cancellation
- Stateful Streamable HTTP is enabled so one MCP client session maps consistently to one isolated file namespace
- Logical workspaces are resolved through the server allowlist; explicit paths remain restricted to the configured workspace boundary
- Some plot types require additional dependencies:
  - Maps: `maps` extra; raster file reading uses `rasterio`, included in base dependencies
  - 3D plots like `isosurface3d`: `ml` extra
  - File mode: pandas is included in the project's base dependencies
