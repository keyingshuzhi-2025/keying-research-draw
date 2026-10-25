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

环境变量保留原配置，并新增工作区变量。工作区必须是已存在的目录，且不能是项目根目录或其子目录：

```text
PYTHONPATH=.
MPLBACKEND=Agg
PLOT_BACKEND=Agg
HEADLESS=1
RESEARCH_DRAW_MCP_WORKSPACE=/Volumes/柯影数智/研发部/mcp/mcp-keying-research-draw-workspace
```

先创建独立工作区目录：

```bash
mkdir -p "/Volumes/柯影数智/研发部/mcp/mcp-keying-research-draw-workspace"
```

```bash
cd "/Volumes/柯影数智/研发部/mcp/mcp-keying-research-draw"
RESEARCH_DRAW_MCP_WORKSPACE="/Volumes/柯影数智/研发部/mcp/mcp-keying-research-draw-workspace" /opt/homebrew/bin/uv run research-draw-mcp
```

工作区必须预先存在，不能是项目根目录或其子目录。服务不会把缺失的工作区配置回退到项目目录。

This will start the MCP server using stdio transport, ready to accept connections from MCP clients.

### 远程 Docker 部署（amd64）

仓库提供只包含 MCP 服务的 Linux `amd64` 镜像，不打包 Web 前端。镜像基于 Python 3.13.15，保留绘图源码和只读离线地图/示例数据；容器以非 root 用户运行，工作目录挂载为 Docker 持久卷。用户上传的数据和绘图结果、`.env` 运行配置及令牌文件均不进入镜像：持久化内容放在 Docker volume，运行配置由 Compose 注入，令牌由 Docker Secret 提供。`.dockerignore` 会排除 `.env*`、输出目录和本地密钥文件，Dockerfile 只复制明确列出的源码、依赖清单和静态数据目录。

服务通过 Streamable HTTP 提供于 `/mcp`。柯影智航连接例如 `https://mcp.example.com/mcp`，并设置请求头 `Authorization: Bearer <团队签发的令牌>`。团队管理员负责核实接入团队、签发和轮换令牌；团队共用令牌标识团队级访问，不能区分具体成员。

GitHub Actions 在推送与根目录 `VERSION` 相符的稳定版本 tag（例如 `v0.1.4`）时自动构建 `linux/amd64` 镜像并发布到 GHCR。成功后镜像地址为 `ghcr.io/keyingshuzhi/keying-research-draw-mcp`，并带有 `v0.1.4`、`0.1.4` 和 `latest` 标签。workflow 使用 `GITHUB_TOKEN` 发布并关联源仓库；GitHub 说明由工作流创建的 package 会继承该仓库的可见性和权限模型。当前源仓库为公开仓库，因此镜像预期可匿名拉取；package 可见性仍可单独管理，首次发布后可在 GitHub Packages 页面确认。详见 [GitHub Actions package 权限说明](https://docs.github.com/en/packages/managing-github-packages-using-github-actions-workflows/publishing-and-installing-a-package-with-github-actions)和 [GHCR 可见性说明](https://docs.github.com/en/packages/learn-github-packages/configuring-a-packages-access-control-and-visibility)。workflow 不使用仓库中的环境配置或密钥作为 build input。

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

把 `.env.mcp.example` 复制为 `.env`，将 `mcp.example.com` 改成实际域名，并选择要部署的镜像标签。然后在仓库目录拉取并启动：

```bash
cp .env.mcp.example .env
docker compose -f compose.mcp.yaml pull
docker compose -f compose.mcp.yaml up -d --no-build
```

Compose 会使用 `.env` 中的 `RESEARCH_DRAW_MCP_IMAGE`，并把令牌文件作为运行时 Docker Secret 挂载到 `/run/secrets/research_draw_mcp_token`。镜像、构建参数和代码库均不包含令牌值。HTTP 模式在令牌文件缺失或格式不符合要求时会拒绝启动；令牌在进程启动时读取，轮换后需重新创建容器：

```bash
docker compose -f compose.mcp.yaml up -d --force-recreate
```

容器端口默认只绑定服务器的 `127.0.0.1:8000`，由同机反向代理转发并终止 HTTPS。请配置代理速率限制和请求体限制，并通过 `.env` 中的 `RESEARCH_DRAW_MCP_ALLOWED_HOSTS` 设置实际域名；若客户端发送 `Origin`，还需设置 `RESEARCH_DRAW_MCP_ALLOWED_ORIGINS`。部署时不要将明文 HTTP 端口直接暴露到公网。镜像的 HTTP 请求体上限默认为 48 MiB；远程 `upload_data_file` 默认接受不超过 32 MiB 的表格。调整上传上限时，也要相应调高 `RESEARCH_DRAW_MCP_MAX_REQUEST_BODY_MB` 和反向代理请求体上限；HTTP 请求体配置最高为 256 MiB。更大的文件可由管理员放入容器工作区，再使用 `import_data_file`。

远程上传请调用 `upload_data_file(filename, content_base64)`，其中 `content_base64` 是文件原始字节的标准 Base64 编码。`import_data_file(source_path)` 仍用于 MCP 主机工作区中已有的文件。数据文件持久化在容器卷 `/workspace/inputs/mcp/`，图片保存在 `/workspace/outputs/mcp/`；渲染结果图片随 MCP 工具响应返回，容器内路径只供服务端管理使用。

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
- Output files are saved to `<RESEARCH_DRAW_MCP_WORKSPACE>/outputs/mcp/`
- Imported tables are copied to `<RESEARCH_DRAW_MCP_WORKSPACE>/inputs/mcp/`
- Workspace paths are resolved before file access; paths outside the workspace are rejected
- Some plot types require additional dependencies:
  - Maps: `maps`, `raster` extras
  - 3D plots like `isosurface3d`: `ml` extra
  - File mode: `data` extra (for pandas)
