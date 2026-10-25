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

本地运行前，需要配置独立于项目目录的工作区。数据副本放在工作区的 `inputs/mcp/`，绘图结果保存在 `outputs/mcp/`。

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
     research-draw-mcp
     ```

   - 工作目录：`/Volumes/柯影数智/研发部/mcp/mcp-keying-research-draw`

   工作目录请填写柯影智航本机安装的项目根目录绝对路径。

环境变量保留原配置。工作区类 MCP 工具会要求调用方在每次请求中提供当前会话工作区的绝对路径；如需限制本地 stdio 服务可访问的会话范围，可设置共同根目录：

```text
PYTHONPATH=.
MPLBACKEND=Agg
PLOT_BACKEND=Agg
HEADLESS=1
RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT=/Volumes/柯影数智/研发部/实验
```

共同根目录需已存在，且应尽可能窄。柯影智航每次调用文件工具时都要传入当前会话的绝对 `workspace_path`；导入和绘图分别写入该目录下的 `inputs/mcp/` 与 `outputs/mcp/`。不配置共同根目录时，本地 stdio 服务仍要求绝对会话路径，但不会额外限制其父目录。

```bash
mkdir -p "/Volumes/柯影数智/研发部/实验"
```

```bash
cd "/Volumes/柯影数智/研发部/mcp/mcp-keying-research-draw"
RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT="/Volumes/柯影数智/研发部/实验" /opt/homebrew/bin/uv run research-draw-mcp
```

`RESEARCH_DRAW_MCP_WORKSPACE` 仅供兼容桥接入口使用；主 MCP 工具以每次调用传入的 `workspace_path` 为准，不会回退到单一默认会话目录。

This will start the MCP server using stdio transport, ready to accept connections from MCP clients.

### 远程 Docker 部署（amd64）

仓库提供只包含 MCP 服务的 Linux `amd64` 镜像，不打包 Web 前端。镜像基于 Python 3.13.15，保留绘图源码和只读离线地图/示例数据；容器以非 root 用户运行。容器只 bind mount `RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT` 指定的共同宿主机目录到 `/host-workspaces`，不把数据持久化在容器层或 Docker volume 中。每次文件相关工具调用都必须提供 `workspace_path`，指定当前柯影智航会话的绝对工作区路径；服务将它限制在共同根目录之内，并分别读写该会话下的 `inputs/mcp/` 和 `outputs/mcp/`。`.env` 运行配置及令牌文件均不进入镜像，运行配置由 Compose 注入，令牌由 Docker Secret 提供。`.dockerignore` 会排除 `.env*`、输出目录和本地密钥文件，Dockerfile 只复制明确列出的源码、依赖清单和静态数据目录。

一个 HTTP MCP 实例可服务多个会话，因为每次工作区工具调用都携带当前会话的 `workspace_path`。客户端/助手必须在每次调用 `import_data_file`、`upload_data_file`、`inspect_data_file`、`list_workspace_files`、`validate_plot_config`、`render_plot` 或 `list_render_outputs` 时传入当前会话工作区绝对路径；不能复用上一个会话的路径。服务端只接受位于 `RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT` 之下、且容器挂载中实际存在的目录。请将共同根目录设为覆盖目标会话的最窄父目录；例如仅覆盖实验会话时，可设置为 `/Volumes/柯影数智/研发部/实验`。这会把该共同根目录以读写方式提供给容器，因此不要选择比实际需要更宽的目录。容器以非 root 用户运行：Linux 通常使用 UID/GID `10001:10001`，macOS 应将 `RESEARCH_DRAW_MCP_UID` 和 `RESEARCH_DRAW_MCP_GID` 设为工作区所属账号 ID；容器仍会以附加组 `10001` 读取 Docker Secret。

`RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT` 是部署时可配置的存储边界，不是固定会话目录。柯影智航当前会话选中目录 A 时，每次工具调用传目录 A；切换到目录 B 后传目录 B，输入和输出分别落在 A、B 自己的 `inputs/mcp/`、`outputs/mcp/` 下。本机 Docker 测试可以把 `/Volumes/柯影数智/研发部/实验` 作为共同根目录；部署到阿里云时，应把它改成阿里云服务器上实际的数据盘或共享存储路径（例如 `/srv/koying/workspaces`），并确保所有会话工作区都位于该目录中。MCP 收到的绝对路径必须是 Docker 宿主机可见的路径；不能把柯影智航客户端 Mac 上、阿里云服务器不可见的本地路径直接发给远程服务。若会话工作区位于各用户自己的电脑上，需要柯影智航客户端增加文件上传/下载桥接，由客户端把结果写回当前会话目录。

`workspace_path` 是工具的顶层参数，须使用柯影智航当前选中目录的完整绝对路径；`render_plot` 也不能把它放入 `config`。服务兼容某些客户端误删路径首个 `/` 的情况：仅当补回 `/` 后路径严格位于已挂载的共同根目录内，才会按该会话目录处理；其他相对路径仍会被拒绝。

服务通过 Streamable HTTP 提供于 `/mcp`。柯影智航连接例如 `https://mcp.example.com/mcp`，并设置请求头 `Authorization: Bearer <团队签发的令牌>`。团队管理员负责核实接入团队、签发和轮换令牌；团队共用令牌标识团队级访问，不能区分具体成员。

GitHub Actions 在推送与根目录 `VERSION` 相符的稳定版本 tag（例如 `v0.1.4`）时自动构建 `linux/amd64` 镜像并发布到 GHCR。成功后镜像地址为 `ghcr.io/keyingshuzhi-2025/keying-research-draw-mcp`，并带有 `v0.1.4`、`0.1.4` 和 `latest` 标签。管理员也可从 Actions 手动运行此 workflow 并填写已有稳定版本 tag，以重试镜像发布。workflow 使用 `GITHUB_TOKEN` 发布并关联源仓库；GitHub 说明由工作流创建的 package 会继承该仓库的可见性和权限模型。当前源仓库为公开仓库，因此镜像预期可匿名拉取；package 可见性仍可单独管理，首次发布后可在 GitHub Packages 页面确认。详见 [GitHub Actions package 权限说明](https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions)和 [GHCR 可见性说明](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility)。workflow 不使用仓库中的环境配置或密钥作为 build input。

建议在仓库 Rulesets 中限制 `v*` release tag 的创建和更新权限，只允许发布管理员操作；workflow 本身会拒绝非稳定版本号以及与 `VERSION` 不一致的 tag。

推送 tag 的示例：

```bash
git tag v0.1.4
git push origin v0.1.4
```

在部署服务器上创建令牌文件，令牌至少 32 个可见 ASCII 字符：

```bash
sudo install -d -m 700 /etc/research-draw
sudo install -o root -g 10001 -m 440 /dev/null /etc/research-draw/mcp-token
openssl rand -hex 32 | sudo tee /etc/research-draw/mcp-token >/dev/null
```

令牌文件的组 ID `10001` 对应容器内的 MCP 用户组，使非 root 容器进程可以读取 Secret。若服务器使用 rootless Docker 或 user-namespace remapping，需按主机映射后的 UID/GID 调整文件属主和权限。

把 `.env.mcp.example` 复制为 `.env`，设置实际域名、镜像标签、Docker Secret 文件路径，以及包含所有目标会话工作区的共同宿主机根目录。macOS 还需把 UID/GID 设为工作区所属账号的 `id -u` 与 `id -g` 输出。共同根目录和目标会话工作区必须预先存在，再在仓库目录拉取并启动：

```bash
cp .env.mcp.example .env
# Edit .env: set RESEARCH_DRAW_MCP_HOST_WORKSPACES_ROOT and, on macOS, the owning account's UID/GID.
docker compose -f compose.mcp.yaml pull
docker compose -f compose.mcp.yaml up -d --no-build
```

Compose 使用禁用自动建目录的 bind mount；共同根目录不存在时启动会失败，避免 Docker 自动创建错误路径。

Compose 会使用 `.env` 中的 `RESEARCH_DRAW_MCP_IMAGE`，并把令牌文件作为运行时 Docker Secret 挂载到 `/run/secrets/research_draw_mcp_token`。镜像、构建参数和代码库均不包含令牌值。HTTP 模式在令牌文件缺失或格式不符合要求时会拒绝启动；令牌在进程启动时读取，轮换后需重新创建容器：

```bash
docker compose -f compose.mcp.yaml up -d --force-recreate
```

容器端口默认只绑定服务器的 `127.0.0.1:8000`，由同机反向代理转发并终止 HTTPS。请配置代理速率限制和请求体限制，并通过 `.env` 中的 `RESEARCH_DRAW_MCP_ALLOWED_HOSTS` 设置实际域名；若客户端发送 `Origin`，还需设置 `RESEARCH_DRAW_MCP_ALLOWED_ORIGINS`。部署时不要将明文 HTTP 端口直接暴露到公网。镜像的 HTTP 请求体上限默认为 48 MiB；远程 `upload_data_file` 默认接受不超过 32 MiB 的表格。调整上传上限时，也要相应调高 `RESEARCH_DRAW_MCP_MAX_REQUEST_BODY_MB` 和反向代理请求体上限；HTTP 请求体配置最高为 256 MiB。更大的文件可由管理员放入容器工作区，再使用 `import_data_file`。

远程上传请调用 `upload_data_file(filename, content_base64, workspace_path)`，其中 `content_base64` 是文件原始字节的标准 Base64 编码，`workspace_path` 是当前会话工作区绝对路径。所有文件工具都需带上 `workspace_path`，这样切换会话后工具就会操作新会话对应的宿主机目录。`import_data_file(source_path, workspace_path)` 可从当前工作区内已有的文件导入。工具返回的 `path` 是宿主机文件路径，`workspace_relative_path` 是相对当前会话工作区的路径；文件分别写入该工作区的 `inputs/mcp/` 和 `outputs/mcp/`。渲染结果图片也会随 MCP 工具响应返回。

令牌文件通过 Compose Secret 注入；Docker 官方资料说明了 [Compose Secret 的文件挂载方式](https://docs.docker.com/compose/how-tos/use-secrets/)以及 [构建阶段不应通过 `ARG`/`ENV` 传递密钥](https://docs.docker.com/reference/build-checks/secrets-used-in-arg-or-env/)。

```text
→ upload_data_file(filename: "study.csv", content_base64: "<standard-base64-file-bytes>")
← {"success": true, "file_id": "a1b2c3d4e5f6_study.csv", "size": 12345, ...}
```

Use the returned `file_id` in `validate_plot_config` and `render_plot`.

### Available Tools

The server exposes the following tools:

1. `get_version` - Get the version of Research Draw
2. `list_plot_groups` - List all available plot groups with metadata
3. `list_plots` - List available plots, optionally filtered by group
4. `get_plot_schema` - Get detailed schema for a specific plot type
5. `import_data_file` - Copy a supported local table into the managed workspace input folder
6. `upload_data_file` - Receive a base64-encoded table from a remote MCP client (32 MB default limit)
7. `list_workspace_files` - List imported data files
8. `inspect_data_file` - Inspect columns, data types, missing values, and a short preview
9. `validate_plot_config` - Check plot parameters and workspace file paths before rendering
10. `render_plot` - Render a plot and return the result (supports demo, custom, and file modes)
11. `list_render_outputs` - List recent images in the workspace output folder

`import_data_file` accepts a source path inside the configured workspace. `upload_data_file` accepts raw file bytes encoded as standard Base64 for remote clients. Both support CSV, TSV, TXT, XLSX, and XLS. The default local import limit is 200 MB (`RESEARCH_DRAW_MCP_MAX_IMPORT_MB`); the default remote upload limit is 32 MB (`RESEARCH_DRAW_MCP_MAX_UPLOAD_MB`).

## Examples

### Getting version
```text
→ get_version()
← "v0.1.4"
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

### Importing and inspecting a data file

```text
→ import_data_file(source_path: "/path/to/research-draw-workspace/study.csv")
← {"success": true, "file_id": "a1b2c3d4e5f6_study.csv", ...}

→ inspect_data_file(file_id: "a1b2c3d4e5f6_study.csv")
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
  "path": "/path/to/research-draw-workspace/outputs/mcp/test_box_<id>.png",
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
- Output files are saved to `<workspace_path>/outputs/mcp/`
- Imported tables are copied to `<workspace_path>/inputs/mcp/`
- Workspace paths are resolved before file access; paths outside the workspace are rejected
- Some plot types require additional dependencies:
  - Maps: `maps`, `raster` extras
  - 3D plots like `isosurface3d`: `ml` extra
  - File mode: `data` extra (for pandas)
