# Research Draw（科研绘图）

Research Draw 是一个面向科研场景的可视化工具站，提供从数据输入、字段映射、图型渲染到结果管理的完整流程。

包含：

- Python CLI（`uv run python -m src.main` / `uv run research-draw`）
- Web 端（FastAPI + Vue3）

> 当前开发版本：`v0.1.5`（项目整体尚未发行；MCP v0.1.5 Docker 镜像已单独发布，部署方式见 [MCP_DEPLOYMENT_GUIDE.md](MCP_DEPLOYMENT_GUIDE.md)）。

项目环境已统一使用 `uv` 管理，Python 版本固定为 `3.13.15`。依赖声明以 `pyproject.toml` 为准，解析结果锁定在 `uv.lock`。

当前版本覆盖统计二维图、领域二维图、科研常用三维图、离线地图绘图，并支持文件上传、页面表格录入、历史记录与本地渲染文件管理。

版本管理已统一到单一来源：

- 根目录 `VERSION` 为唯一版本源（当前 `0.1.5`）
- CLI / Web 后端通过 `src/version.py` 自动读取
- 前端 `package.json` / `package-lock.json` 在 `npm` 脚本前自动执行 `sync:version` 注入

## 开源许可

项目软件源码与文档采用 MIT 许可证，详见 [LICENSE](LICENSE)。该许可不覆盖 `web/assets/Keying-Atlas-Brand-Kit-v1/` 中的品牌素材，也不授予「柯影智绘 Atlas」名称及品牌标识的商标使用权；仓库中的地图、示例数据和第三方素材仍按各自来源的许可使用。

## 核心能力

- 统计二维：`box` / `violin` / `scatter` / `bar` / `column` / `line` / `histogram` / `area` / `volcano` / `forest`
- 领域二维：
  - 生物：`ma` / `enrich_dot` / `gsea` / `embedding` / `upset`
  - 临床：`km` / `roc` / `calibration` / `bland_altman` / `dca`
  - 材料：`stress_strain` / `xrd` / `raman` / `phase` / `hysteresis`
  - 遥感：`spectral_signature` / `index_ts` / `confusion` / `class_dist`
  - 金融：`candlestick` / `cum_return` / `rolling_stats` / `frontier` / `acf_pacf`
  - 心理：`likert` / `raincloud` / `irt_icc` / `factor_loadings` / `interaction`
- 三维图：`scatter3d` / `surface3d` / `wireframe3d` / `contour3d` / `line3d` / `isosurface3d` / `slice3d` / `quiver3d` / `waterfall3d` / `embedding3d` / `mesh3d`
- 地图：`world` / `world_admin1` / `china` / `choropleth_world` / `choropleth_china` / `raster` / `points`

## 环境与安装

项目固定使用 Python `3.13.15`，推荐先安装 [uv](https://docs.astral.sh/uv/)。项目根目录的 `.python-version` 会被 uv 自动识别。

CSV/Excel 文件读取依赖（`pandas`、`openpyxl`）和栅格读取依赖（`rasterio`）已包含在基础依赖中；地图、机器学习图型和 Web 服务分别通过对应 extra 安装。

同步基础环境：

```bash
uv sync
```

按需安装扩展：

```bash
# 统计增强
uv sync --extra stats

# 机器学习/高级图型（含 isosurface3d 依赖 scikit-image）
uv sync --extra ml

# 地图（栅格读取依赖 rasterio，已包含在基础依赖中）
uv sync --extra maps

# Web 后端
uv sync --extra web

# 全量依赖
uv sync --extra all
```

`uv.lock` 是可复现安装的锁定文件；日常运行、测试和质量检查统一通过 `uv run` 执行。

## CLI 快速开始

建议使用 `uv run python -m src.main` 或 `uv run research-draw` 启动，不使用脚本路径启动方式。

```bash
# 查看帮助与示例
uv run python -m src.main -h
uv run python -m src.main --help-examples

# Demo
uv run python -m src.main --mode demo --plot box --title "箱线图演示"
uv run python -m src.main --mode demo --plot scatter3d --title "3D Scatter"
uv run python -m src.main --mode demo --plot confusion --title "Confusion Matrix"

# 文件模式
uv run python -m src.main --mode file --plot scatter --file data/demo_scatter.csv --x-col x --y-col y
uv run python -m src.main --mode file --plot scatter3d --file data/demo_scatter3d.csv --x-col x --y-col y --z-col z

# 常用统计二维图
uv run python -m src.main --mode demo --plot column --show-values
uv run python -m src.main --mode custom --plot bar --labels "A,B,C" --y "12,18,9" --show-values
uv run python -m src.main --mode file --plot line --file data/measurements.csv --x-col date --y-col value --group-col group
uv run python -m src.main --mode file --plot histogram --file data/measurements.csv --value-col value --group-col group --bins 30

# 地图
uv run python -m src.main --plot choropleth_world --file data/world_choropleth.csv --key-col ISO_A3 --value-col value --on iso_a3
uv run python -m src.main --plot points --basemap china_l1 --file data/points_cn.csv --lon-col lon --lat-col lat
```

也可通过入口命令运行：

```bash
research-draw --help
```

`uv run python -m src.main --help-examples` 按分组列出全部已注册图型的内置 Demo 命令。

## MCP Server

MCP 服务提供图型发现、数据分析与推荐、参数校验、数据导入、绘图和结果管理。当前 MCP 代码版本为 `v0.1.5`；已发布的 Docker 镜像为 `ghcr.io/keyingshuzhi-2025/keying-research-draw-mcp:v0.1.5`。本机 stdio、本机 Docker 和阿里云 ECS（Alibaba Cloud Linux 3）部署教程见 [MCP_DEPLOYMENT_GUIDE.md](MCP_DEPLOYMENT_GUIDE.md)。工作区由服务端配置为逻辑名称，工具调用可省略工作区参数使用默认值，也可传逻辑名称：

```bash
uv sync --extra mcp
RESEARCH_DRAW_MCP_DEFAULT_WORKSPACE="research" \
RESEARCH_DRAW_MCP_WORKSPACES='{"research":"/path/to/research-draw-workspace"}' \
uv run --extra mcp research-draw-mcp
```

每个 MCP 会话在逻辑工作区下使用独立目录：`<工作区>/.mcp-sessions/<会话标识>/`。输入副本位于该目录的 `inputs/mcp/`，绘图结果位于 `outputs/mcp/`，分块上传暂存数据会在完成、取消或过期清理时移除。MCP 工具包括：

- 发现与说明：`get_version`、`list_workspaces`、`list_plot_groups`、`list_plots`、`get_plot_schema`
- 分析与绘图：`suggest_plots`、`create_plot`、`create_plots`、`render_plot`、`revise_plot`
- 长任务与超时恢复：`start_render_job`、`start_plot_job`、`get_plot_job_status`、`get_plot_job_result`
- 数据管理：`import_data_file`、`upload_data_file`、`begin_data_upload`、`upload_data_chunk`、`complete_data_upload`、`cancel_data_upload`、`list_workspace_files`、`inspect_data_file`
- 校验与结果：`validate_plot_config`、`list_render_outputs`

`suggest_plots` 会根据表格字段与分析目标推荐图型；`create_plot` 可一站完成字段匹配、校验和渲染；`create_plots` 可基于同一份数据批量比较多种图型；`revise_plot` 可基于已有结果调整标题、配色或轴标签后重绘。文件已在 MCP 共享工作区时，可直接按相对路径导入，避免模型传输 Base64 文件内容；无法共享文件系统时仍可使用分块上传。图型 schema 提供参数说明，校验结果包含可供模型读取的错误诊断和安全修复建议。

复杂、耗时的直接绘图请使用 `start_render_job`（`mode`、`plot`、`config` 均为必填顶层参数）；文件绘图、批量绘图或复杂图重绘使用 `start_plot_job`。工具会先返回任务 ID，再轮询 `get_plot_job_status`，完成后调用 `get_plot_job_result` 获取结果和图像内容。客户端或网络超时后，用相同的 `request_id` 和参数重试提交即可复用原任务，避免重复绘制。

详细配置和调用示例见 [MCP_SERVER_README.md](MCP_SERVER_README.md)。

## Web 快速开始

首次运行前，安装 Python 和前端依赖：

```bash
uv sync --extra web --extra ml --extra maps
npm --prefix web/frontend install
```

以后在项目根目录用一条命令同时启动前后端：

```bash
uv run --extra web --extra ml --extra maps python scripts/dev_web.py
```

按 `Ctrl+C` 会同时停止两端服务。

默认地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

Web 端已支持：

- 左侧主导航、首页介绍、可折叠和调整宽度的导航栏
- 绘图工作区内独立滚动的步骤一至三区域与结果预览区域
- 文件上传与表格录入
- 图标题与 `xlabel/ylabel/zlabel` 与数据分离
- 资产管理弹窗（渲染历史与本地渲染文件）
- 设置弹窗（基础设置、关于、用户手册）；后端连接位于“设置 → 基础设置”
- 关于页展示版本、项目介绍、57 种图型目录与联系方式

Web 页面结构与操作细节见 [用户手册](ResearchDrawApp_使用手册.md) 和 [Web 模块说明](web/README.md)。

## 工程质量检查

```bash
uv sync --extra test
uv run ruff check src/main.py src/cli/parser.py src/cli/config_schema.py src/version.py web/backend/app.py tests/test_cli_parser.py tests/test_loaders.py tests/test_smoke_app.py
uv run mypy
uv run pytest -q

cd web/frontend
npm install
npm run lint
npm run test
npm run build
```

说明：

- `tests/`：标准 pytest 自动化测试（CI 主入口）
- `scripts/`：运维与数据准备脚本（底图下载、demo 数据生成、手工 smoke）
- `.github/workflows/ci.yml`：后端 lint/type/test + 前端 lint/test/build + CLI smoke

## 配置

`PlotConfig` 支持 `.env`/环境变量，例如：

```bash
PLOT_BACKEND=TkAgg
PLOT_THEME=DEFAULT
PLOT_DPI=300
PLOT_FORMAT=PNG
PLOT_SAVE_DIR=outputs/figures
MAP_BASEMAP_ROOT=./data/geo
```

运行时可覆盖：

- `--outdir`：覆盖当前运行输出目录
- `--basemap-root`：覆盖离线底图目录
- `--config`：读取 JSON/YAML 配置（命令行参数优先级更高）

`--config` 配置文件会经过统一 schema 校验（Pydantic）：

- 未定义字段会直接报错（防止 silent ignore）
- 基础类型会自动校验（如 `dpi`、`alpha`、`k` 等）
- `group` 这类 append 参数会统一标准化为列表

Geo 数据读取默认启用进程级 LRU 缓存（用于离线底图/GADM 反复读盘场景）：

- `GEO_READ_CACHE_MAX_ITEMS`：缓存条目上限（默认 `24`）

Web 端运行时配额/清理策略可通过环境变量配置：

- `WEB_UPLOAD_MAX_FILE_MB` / `WEB_UPLOAD_MAX_FILES` / `WEB_UPLOAD_MAX_TOTAL_MB`
- `WEB_RENDER_MAX_FILES` / `WEB_RENDER_MAX_TOTAL_MB`
- `WEB_UPLOAD_RETENTION_DAYS` / `WEB_RENDER_RETENTION_DAYS`
- `WEB_CLEANUP_INTERVAL_SECONDS`

## 文档

- CLI/Web 详细手册：`ResearchDrawApp_使用手册.md`
- Web 模块说明：`web/README.md`
- 脚本层说明：`scripts/README.md`

## 项目结构

```text
research-draw/
├── src/
│   ├── main.py              # 入口（薄层）
│   ├── cli/                 # 参数解析与配置合并
│   ├── dispatch/            # 图型路由与执行
│   ├── registry/            # 图型注册中心（分组/别名/默认/依赖/demo）
│   ├── loaders/             # 文件/表格/JSON 数据读取
│   ├── plotters/            # Plotter 类发现
│   ├── save/                # 导出与保存
│   ├── chart/
│   │   ├── plot_2d/         # 2D 图（统计 + 地图）
│   │   └── plot_3d/         # 3D 图
│   └── util/                # 通用工具（含依赖提示、统计工具）
├── tests/                   # pytest 自动化测试
├── scripts/                 # 数据准备/底图下载/手工 smoke 脚本
├── web/                     # FastAPI + Vue3
├── data/                    # demo 数据与离线底图
├── outputs/                 # 输出目录
└── pyproject.toml           # 依赖与打包配置
```
