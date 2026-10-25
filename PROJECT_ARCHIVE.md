# Research Draw 项目留档

> **项目名称**：Research Draw（科研绘图工具站）
> **版本**：v0.1.4
> **留档日期**：2026-10-25
> **留档性质**：项目全量架构与实现概览（静态快照）

---

## 一、项目概述

Research Draw 是一个面向科研场景的可视化工具站，提供从数据输入、字段映射、图型渲染到结果管理的完整流程。覆盖统计二维图、学科领域图、科研常用三维图、离线地图四大类共 50+ 种图表。

项目采用 **双端架构**：
- **Python CLI**：命令行工具，支持 demo / custom / file 三种模式
- **Web 端**：FastAPI 后端 + Vue3 前端，支持文件上传、异步渲染、历史管理
- **MCP 服务**：支持本地 stdio 和带 Bearer Token 的 Streamable HTTP；远程服务提供 amd64 Docker 镜像

---

## 二、技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.13.15 | 版本固定，由 `.python-version` 约束 |
| 包管理 | uv | `pyproject.toml` 声明依赖，`uv.lock` 锁定版本 |
| 绘图引擎 | Matplotlib | 3.7.x，支持 Agg / TkAgg 等后端 |
| Web 后端 | FastAPI | 异步任务队列 + 轮询状态模型 |
| Web 前端 | Vue3 + Vite | 组件化 SPA |
| 数据处理 | pandas / numpy | 文件模式读取 |
| 地理数据 | geopandas / shapely / mapclassify | 离线底图渲染 |
| 3D 渲染 | matplotlib 3D Axes | scatter3d / surface3d / wireframe3d 等 |
| 配置校验 | Pydantic | CLI 配置 schema 校验 + Web 请求模型 |
| 字体 | 中文字体自动适配 | macOS(STHeiti) / Windows(SimHei) / Linux(Arial) |
| 主题 | DEFAULT / NATURE / SCIENCE / IEEE | 期刊风格占位 |
| CI | GitHub Actions | ruff + mypy + pytest + 前端 lint/test/build |

---

## 三、目录结构

```
research-draw/
├── src/                          # Python 核心源码
│   ├── main.py                   # 入口（薄层，ResearchDrawApp 类）
│   ├── version.py                # 版本管理（读取 VERSION 文件）
│   ├── config.py                 # Matplotlib 渲染配置（.env 集成）
│   ├── cli/                      # CLI 参数解析与配置合并
│   │   ├── parser.py             # argparse 构建（350+ 行，全量参数）
│   │   └── config_schema.py      # Pydantic schema 校验
│   ├── dispatch/                 # 图型路由与执行
│   │   ├── executor.py           # PlotDispatchExecutor 分发执行器
│   │   ├── routes.py             # 归一化与副作用处理
│   │   └── handlers/             # 四大 Handler
│   │       ├── base.py           # HandlerContext / HandlerResult / PlotHandler
│   │       ├── static2d.py       # 统计二维图处理
│   │       ├── domain2d.py       # 学科领域图处理
│   │       ├── plot3d.py         # 三维图处理
│   │       └── map.py            # 地图图处理
│   ├── registry/                 # 图型注册中心
│   │   └── plot_registry.py      # 分组/别名/默认/依赖/demo 元数据
│   ├── plotters/                 # Plotter 类发现工厂
│   │   └── factory.py            # 动态导入 Static2D / Map / 3D Plotter
│   ├── loaders/                  # 数据加载
│   │   └── data_loader.py        # DataFrame 读取 / 列表解析 / 点位加载
│   ├── save/                     # 导出与保存
│   │   └── export.py             # autosave_name / outdir_override
│   ├── chart/
│   │   ├── plot_2d/              # 2D 图实现
│   │   │   ├── static_analysis.py  # 统计图（box/violin/scatter/volcano/forest）
│   │   │   ├── geo_atlas.py        # 地图底图（GeoAtlas）
│   │   │   └── plotters/
│   │   │       ├── geo/          # choropleth / overlays / views
│   │   │       └── static/       # 分学科 plotter（biomed/clinical/materials/remote/finance/psych）
│   │   └── plot_3d/              # 3D 图实现
│   │       └── scatter3d.py      # Scatter3DPlotter 及 3D 系列
│   ├── util/                     # 通用工具
│       ├── dependency_hints.py   # 依赖缺失提示
│       └── stats_utils.py        # 统计工具函数
│   └── mcp_server/               # MCP 工具、工作区管理与 HTTP 认证
│       ├── server.py
│       ├── runner.py
│       ├── workspace.py
│       └── http_auth.py
├── tests/                        # pytest 自动化测试（CI 主入口）
│   ├── conftest.py
│   ├── test_cli_parser.py
│   ├── test_dispatch_executor_demo.py
│   ├── test_dispatch_handler_registry.py
│   ├── test_dispatch_routes.py
│   ├── test_loaders.py
│   ├── test_plot_registry.py
│   ├── test_save_export.py
│   ├── test_smoke_app.py
│   ├── test_stats_utils.py
│   └── test_web_maintenance.py
├── scripts/                      # 运维与数据准备脚本
│   ├── README.md
│   ├── download_basemaps.py      # 下载离线底图（Natural Earth + GADM）
│   ├── generate_test_data.py     # 生成中英文统计图测试数据
│   ├── generate_domain_demo_data.py  # 生成领域 demo 数据
│   ├── generate_demo_rasters.py  # 生成 world/china 演示 GeoTIFF
│   ├── smoke_statics_en.py / cn.py   # 统计图手工 smoke
│   ├── smoke_maps_en.py / cn.py      # 地图功能手工 smoke
│   └── smoke_domain_plots.py         # 领域图手工 smoke
├── web/                          # Web 应用
│   ├── backend/
│   │   └── app.py                # FastAPI 主应用（1093 行）
│   ├── frontend/                 # Vue3 + Vite 前端
│   │   ├── src/
│   │   │   ├── App.vue           # 根组件（顶部菜单 + 左侧导航）
│   │   │   ├── main.js           # 入口
│   │   │   ├── style.css         # 全局样式
│   │   │   ├── components/
│   │   │   │   ├── TopBar.vue
│   │   │   │   ├── PlotSelector.vue
│   │   │   │   ├── DataInput.vue
│   │   │   │   ├── RenderPanel.vue
│   │   │   │   ├── ManualPage.vue
│   │   │   │   └── AboutPage.vue
│   │   │   └── composables/
│   │   │       ├── useResearchDrawState.js
│   │   │       └── useResearchDrawStore.js
│   │   ├── package.json / package-lock.json
│   │   ├── vite.config.js
│   │   ├── vitest.config.js
│   │   ├── index.html
│   │   └── scripts/sync-version.mjs
│   └── assets/                   # 关于页联系方式素材（二维码图片）
│       └── images/
│           ├── 小红书.png
│           ├── 微信公众号.png
│           ├── 微信服务号.png
│           └── 粉丝群.png
├── data/                         # demo 数据与离线底图
│   ├── *.csv / *.tif             # 通用 demo 数据
│   ├── biomed/                   # 生物领域数据（ma, enrich_dot, gsea, embedding, upset）
│   ├── clinical/                 # 临床领域数据（km, roc, calibration, bland_altman, dca）
│   ├── materials/                # 材料领域数据（stress_strain, xrd, raman, phase, hysteresis）
│   ├── remote/                   # 遥感领域数据（spectral_signature, index_ts, confusion, class_dist）
│   ├── finance/                  # 金融领域数据（candlestick, cum_return, rolling_stats, frontier, acf_pacf）
│   ├── psych/                    # 心理领域数据（likert, raincloud, irt_icc, factor_loadings, interaction）
│   └── geo/                      # 离线底图（Natural Earth + GADM + 港澳台区域）
│       ├── world/natural_earth/admin{0,1}
│       ├── world/regions/{hkg,mac}
│       ├── china/gadm/{gpkg,shp}
│       ├── china/regions/{hkg,mac}
│       └── taiwan/gadm/{gpkg,shp}
├── outputs/                      # 输出目录（figures + web）
├── web/README.md                 # Web 模块说明
├── scripts/README.md             # 脚本层说明
├── ResearchDrawApp_使用手册.md   # 用户手册（Web 端读取渲染）
├── pyproject.toml                # 依赖与打包配置
├── requirements.txt              # 依赖备选声明
├── uv.lock                       # 锁定依赖
├── .env                          # 运行时环境变量
├── .gitignore                    # Git 忽略规则
├── .python-version               # Python 版本锁定（3.13.15）
├── VERSION                       # 唯一版本源（0.1.4）
├── Dockerfile.mcp                # MCP-only amd64 镜像
├── compose.mcp.yaml              # MCP 部署示例（密钥与持久化卷运行时注入）
├── LICENSE                       # Apache License 2.0
├── .github/workflows/            # CI 与 tag 触发的 MCP 镜像发布
│   ├── ci.yml
│   └── publish-mcp-image.yml
└── research_draw.egg-info/       # 包元信息
```

---

## 四、核心模块详解

### 4.1 启动流程

```
CLI: uv run python -m src.main [args]
         ↓
src/main.py (ResearchDrawApp)
         ↓
src/cli/parser.py → parse_cli_args() → build_parser() + merge_args_with_config()
         ↓
src/main.py → PlotDispatchExecutor.__init__()
         ↓  获取三类 Plotter 类（static / map / 3d）
src/plotters/factory.py → get_static_plotter_cls() / get_map_plotter_cls() / get_3d_plotter_cls()
         ↓
src/dispatch/executor.py → run() → _handler_key_for_plot() → handler.render()
         ↓
src/save/export.py → finalize_plot_output() → save figure + plt.show/close
```

### 4.2 图型注册中心（`src/registry/plot_registry.py`）

**四大分组**：

| 分组键 | 中文名 | 顺序 | 包含图型数 |
|--------|--------|------|-----------|
| `stats_2d` | 统计二维 | 10 | 5 (box, violin, scatter, volcano, forest) |蛋 |
| `domain_2d` | 学科二维 | 20 | 28 |
| `plots_3d` | 三维图型 | 30 | 11 |
| `maps` | 地理地图 | 40 | 7 |

**别名系统**：`_ROUTE_ALIASES` 字典包含 100+ 个体别名映射，支持中英文别名（如"箱线图"→"box"、"火山图"→"volcano"）和多种拼写变体（如"scatter_3d"→"plot3d_scatter"）。

**依赖提示**：`PLOT_DEPENDENCY_HINTS` 标注各图型需要的 extra（如 domain_2d → "data"，isosurface3d / embedding → "ml"，maps → "maps"，raster → "raster"）。

### 4.3 分发执行器（`src/dispatch/executor.py`）

`PlotDispatchExecutor` 维护四个 Handler：
- `Static2DHandler` — 处理 stats_2d 分组图型
- `Domain2DHandler` — 处理 domain_2d 分组图型（学科领域）
- `Plot3DHandler` — 处理 plots_3d 分组图型
- `MapHandler` — 处理 maps 分组图型

`_handler_key_for_plot()` 按图名判断归属：
- 以 `map_` 开头 → `"map"`
- 以 `plot3d_` 开头 → `"plot3d"`
- 在 domain_2d 列表中 → `"domain2d"`
- 其余 → `"static2d"`

### 4.4 四大 Handler 架构

每个 Handler 实现 `PlotHandler` 协议（`base.py`），核心方法：
- `render(plot_key, mode)` → 返回 `HandlerResult(plot_key, title, plotter, rendered)`
- `plotter.save(name, fig, fmt, dpi, match_screen, tight)` → 保存文件

### 4.5 CLI 参数体系（`src/cli/parser.py`）

`build_parser()` 构建了极为全面的 argparse 参数，涵盖：

**全局参数**：`--mode` / `--plot` / `--title` / `--save-name` / `--fmt` / `--dpi` / `--match-screen` / `--tight` / `--no-show` / `--outdir` / `--config` / `--help-examples` / `--version`

**数据输入参数**：`--file` / `--sep` / `--group` / `--x` / `--y` / `--z` / `--u` / `--v` / `--w` / `--scalar` / `--custom-json` / `--custom-json-file`

**列映射参数**：`--x-col` / `--y-col` / `--z-col` / `--u-col` / `--v-col` / `--w-col` / `--scalar-col` / `--log2fc-col` / `--p-col` / `--class-col` / `--item-col` / `--response-col` / `--date-col` / `--open-col` / `--high-col` / `--low-col` / `--close-col` / `--volume-col` / `--return-col` / `--price-col` 等

**领域专用参数**：`--group-col` / `--value-col` / `--count-col` / `--term-col` / `--mean-col` / `--hit-col` / `--set-cols` / `--score-col` / `--prob-col` / `--true-col` / `--pred-col` / `--time-col` / `--event-col` / `--thresholds` / `--z-col` / `--invert-x` / `--factor-col` / `--loading-col` / `--a-col` / `--b-col` / `--c-col` / `--theta-min` / `--theta-max` / `--window` / `--risk-free` / `--n-portfolios` / `--lags` / `--elastic-max` / `--yield-offset`

**地图专用参数**：`--map-theme` / `--basemap-root` / `--include-taiwan` / `--include-hk-mo` / `--taiwan-name` / `--countries` / `--level` / `--highlight` / `--label-names` / `--crs` / `--country-field` / `--case-sensitive` / `--key-col` / `--on` / `--scheme` / `--k` / `--cmap` / `--label-top-n` / `--raster-file` / `--basemap` / `--alpha` / `--lon-col` / `--lat-col` / `--size-col` / `--hue-col` / `--size-range`

**3D 专用参数**：`--elev` / `--azim` / `--levels` / `--rstride` / `--cstride` / `--iso-level` / `--slice-x/y/z` / `--max-arrows` / `--ci` / `--equal`

### 4.6 Web 后端 API 体系（`web/backend/app.py`）

**FastAPI 应用**：`app = FastAPI(title="Research Draw Web API", version=APP_VERSION)`

**API 端点清单**：

| 方法 | 路径 | 功能 |
|------|------|------|
| GET | `/api/health` | 健康检查（含队列状态） |
| GET | `/api/version` | 版本信息 |
| GET | `/api/plots` | 图型分组列表 |
| GET | `/api/plot-registry` | 完整图型注册中心 |
| GET | `/api/contact-assets` | 联系方式素材 |
| GET | `/api/user-manual` | 用户手册 Markdown |
| POST | `/api/upload` | 文件上传 |
| GET | `/api/uploads` | 上传文件列表（分页） |
| GET | `/api/uploads/{file_id}/inspect` | 预览上传文件 |
| DELETE | `/api/uploads/{file_id}` | 删除上传文件 |
| DELETE | `/api/uploads` | 清空上传文件 |
| POST | `/api/tasks/render/submit` | 提交渲染任务（异步） |
| GET | `/api/tasks/{task_id}` | 查询任务状态 |
| POST | `/api/tasks/{task_id}/cancel` | 取消任务 |
| GET | `/api/tasks` | 任务列表 |
| GET | `/api/maintenance/cleanup` | 清理状态 |
| POST | `/api/render` | 同步渲染（兼容旧接口） |
| GET | `/api/renders` | 渲染文件列表 |
| DELETE | `/api/renders/{filename}` | 删除渲染文件 |
| DELETE | `/api/renders` | 清空渲染文件 |
| GET | `/api/files/{filename}` | 获取渲染文件 |
| GET | `/assets/...` | 静态资源 |

**异步任务模型**：
- `TASK_QUEUE: queue.Queue` — 任务队列（最大 128）
- `TASKS: dict` — 任务状态字典
- 工作线程池（默认 1 个 worker）+ 后台清理线程（默认 600s 间隔）
- 任务状态：`queued → running → success / failed / cancelled`
- 清理策略：按数量 + TTL + 目录总配额三重约束

**运行时配额（环境变量）**：
- `WEB_UPLOAD_MAX_FILE_MB`（默认 200）/ `WEB_UPLOAD_MAX_FILES`（默认 300）/ `WEB_UPLOAD_MAX_TOTAL_MB`（默认 2048）
- `WEB_RENDER_MAX_FILES`（默认 600）/ `WEB_RENDER_MAX_TOTAL_MB`（默认 4096）
- `WEB_UPLOAD_RETENTION_DAYS`（默认 14）/ `WEB_RENDER_RETENTION_DAYS`（默认 30）
- `WEB_CLEANUP_INTERVAL_SECONDS`（默认 600）

### 4.7 前端架构（`web/frontend/src/`）

**根组件** `App.vue`：顶部菜单栏（工作区/数据集/操作/关于/用户手册）+ 左侧导航 + 主内容区

**核心组件**：
- `TopBar.vue` — 顶部导航栏
- `PlotSelector.vue` — 图型分组选择器
- `DataInput.vue` — 文件上传 + 表格录入
- `RenderPanel.vue` — 渲染控制面板
- `ManualPage.vue` — 用户手册页（读取 `ResearchDrawApp_使用手册.md`）
- `AboutPage.vue` — 关于页（读取 `web/assets` 素材）

**状态管理**：
- `useResearchDrawState.js` — 响应式状态（composition API）
- `useResearchDrawStore.js` — 持久化存储

**启动流程**：
```
npm run sync:version → 同步 VERSION 到 package.json
npm run dev → Vite 启动（端口 5173）
```

### 4.8 配置系统（`src/config.py` + `.env`）

`PlotConfig` 数据类：
- **后端**：`PLOT_BACKEND`（默认 TkAgg）
- **字体**：按操作系统自动选择（Mac: STHeisi, Win: SimHei, Linux: Arial）
- **主题**：`PLOT_THEME`（DEFAULT / NATURE / SCIENCE / IEEE）
- **输出**：`PLOT_DPI=300`, `PLOT_FORMAT=PNG`, `PLOT_SAVE_DIR=outputs/figures`
- **负号修复**：`FIX_UNICODE_MINUS=True`

`.env` 文件被 `python-dotenv` 自动加载，`config.py` 在 import 时调用 `ensure_matplotlib_backend()`。

### 4.9 版本管理

单一版本源策略：
- `VERSION` 文件 → 唯一版本源（`0.1.4`）
- `src/version.py` → 自动读取 `VERSION` 文件，回退到 package metadata
- `web/frontend` → `npm run sync:version` 注入 `package.json`

---

## 五、数据资产

### 5.1 Demo 数据文件

| 路径 | 用途 |
|------|------|
| `data/demo_scatter.csv` | 散点图 demo |
| `data/demo_scatter3d.csv` | 3D 散点图 demo |
| `data/box_long.csv`, `data/wide_box.csv`, `data/violin_wide.csv` | 箱线图/小提琴图 |
| `data/volcano.csv`, `data/forest.csv` | 火山图/森林图 |
| `data/world_choropleth.csv` | 世界分级着色 |
| `data/china_values.csv` | 中国分级着色 |
| `data/points_cn.csv` | 中国点位 |
| `data/demo_world.tif`, `data/demo_china.tif` | 演示栅格 |
| `data/geo/` | 离线底图（Natural Earth + GADM + 港澳台） |

### 5.2 领域 Demo 数据

每个学科领域目录下有对应的 CSV 文件，与 `DOMAIN_DEMO_FILES` 映射一致：
- **生物**：`data/biomed/`（ma, enrich_dot, gsea, embedding, upset）
- **临床**：`data/clinical/`（km, roc, calibration, bland_altman, dca）
- **材料**：`data/materials/`（stress_strain, xrd, raman, phase, hysteresis）
- **遥感**：`data/remote/`（spectral_signature, index_ts, confusion, class_dist）
- **金融**：`data/finance/`（candlestick, cum_return, rolling_stats, frontier, acf_pacf）
- **心理**：`data/psych/`（likert, raincloud, irt_icc, factor_loadings, interaction）

---

## 六、测试体系

### 6.1 pytest 测试（`tests/`）

| 测试文件 | 覆盖范围 |
|----------|----------|
| `test_cli_parser.py` | CLI 参数解析与配置合并 |
| `test_dispatch_routes.py` | 分发路由归一化 |
| `test_dispatch_handler_registry.py` | Handler 注册与发现 |
| `test_dispatch_executor_demo.py` | 执行器 Demo 模式 |
| `test_loaders.py` | 数据加载器 |
| `test_plot_registry.py` | 图型注册中心 |
| `test_save_export.py` | 导出与保存 |
| `test_stats_utils.py` | 统计工具 |
| `test_smoke_app.py` | 应用 Smoke 测试 |
| `test_web_maintenance.py` | Web 清理策略 |

运行：`uv run pytest -q`（CI 中设置 `MPLBACKEND=Agg`, `HEADLESS=1`）

### 6.2 CI 流水线（`.github/workflows/ci.yml`）

三个并行 Job：
1. **backend-quality**：`uv sync --locked --extra test` → ruff + mypy + pytest
2. **frontend-quality**：`npm ci` → lint + test + build
3. **smoke-cli**：渲染一个 box 图验证 CLI 可用

---

## 七、运维与脚本

### 7.1 数据准备
```bash
uv run python scripts/download_basemaps.py --dir data/geo    # 下载离线底图
uv run python scripts/generate_test_data.py                  # 生成测试数据
uv run python scripts/generate_domain_demo_data.py           # 生成领域 demo
uv run python scripts/generate_demo_rasters.py --out-dir data # 生成演示栅格
```

### 7.2 手工 Smoke 验证
```bash
uv run python scripts/smoke_statics_en.py     # 统计图 smoke
uv run python scripts/smoke_statics_cn.py     # 统计图（中文字名列）smoke
uv run python scripts/smoke_maps_en.py        # 地图 smoke
uv run python scripts/smoke_maps_cn.py        # 地图（中文字名列）smoke
uv run python scripts/smoke_domain_plots.py   # 领域图 smoke
```

---

## 八、依赖矩阵

### 核心依赖（`[project] dependencies`）
- `numpy>=1.23,<3.0`
- `matplotlib>=3.7,<4.0`
- `python-dotenv>=1.0,<2.0`
- `pydantic>=2.8,<3.0`
- `PyYAML>=6.0,<7.0`

### 可选扩展（`[project.optional-dependencies]`）

| Extra | 用途 | 包含包 |
|-------|------|--------|
| `data` | 文件读取（CSV/Excel） | pandas, openpyxl |
| `stats` | 统计增强 | scipy |
| `ml` | 机器学习/高级图型 | scikit-learn, scikit-image, statsmodels, umap-learn, upsetplot |
| `maps` | 地图与空间分析 | geopandas, shapely, mapclassify, pyogrio, fiona |
| `raster` | 栅格数据 | rasterio |
| `web` | Web 后端 | fastapi, uvicorn, python-multipart |
| `test` | 测试与质量检查 | pytest, ruff, mypy, types-PyYAML, types-requests |
| `all` | 全量依赖 | 以上所有 |

---

## 九、Web 前端技术细节

- **框架**：Vue 3 + Composition API
- **构建工具**：Vite
- **测试**：Vitest
- **Lint**：ESLint
- **版本同步**：`scripts/sync-version.mjs` 读取根目录 `VERSION` 注入 `package.json`
- **API 通信**：Axios 或 fetch 调用 FastAPI REST 接口
- **CORS**：允许 `http://127.0.0.1:5173` 和 `http://localhost:5173`

---

## 十、许可与版权

- **许可证**：Apache License 2.0
- **版权方**：柯影数智（Keying Digital Intelligence）
- **联系信息**：`web/assets/` 目录下的二维码图片（小红书、微信公众号、微信服务号、粉丝群）

---

## 十一、已知约束与注意事项

1. **Python 版本严格锁定**：3.13.15，由 `.python-version` 和 `pyproject.toml` 的 `requires-python` 双重约束
2. **默认无头渲染**：Web 后端默认设置 `MPLBACKEND=Agg`，`HEADLESS=1`
3. **路径安全**：Web API 对文件路径做 `Path.resolve()` + `startswith(PROJECT_ROOT)` 校验，防止路径穿越
4. **别名覆盖**：`PLOT_ALIASES` 支持中英文别名和多种拼写变体，优先级高于默认名
5. **`--config` 校验**：JSON/YAML 配置文件经过 Pydantic schema 校验，未定义字段直接报错
6. **Geo 缓存**：地理数据读取启用进程级 LRU 缓存（默认 24 条）
7. **静态资源挂载**：`/assets` 路径映射到 `web/assets/` 目录

---

## 十二、文件清单（归档确认）

以下为项目根目录及关键子目录的文件/目录确认：

| 路径 | 状态 | 说明 |
|------|------|------|
| `VERSION` | ✅ 存在 | 版本源 `0.1.4` |
| `pyproject.toml` | ✅ 存在 | 依赖与打包配置 |
| `uv.lock` | ✅ 存在 | 锁定依赖 |
| `README.md` | ✅ 存在 | 项目说明 |
| `ResearchDrawApp_使用手册.md` | ✅ 存在 | 用户手册 |
| `web/README.md` | ✅ 存在 | Web 模块说明 |
| `scripts/README.md` | ✅ 存在 | 脚本层说明 |
| `src/` | ✅ 完整 | 核心源码（42 个 Python 文件） |
| `tests/` | ✅ 完整 | 11 个 pytest 测试文件 |
| `scripts/` | ✅ 完整 | 8 个运维脚本 |
| `web/backend/app.py` | ✅ 完整 | FastAPI 主应用 |
| `web/frontend/src/` | ✅ 完整 | Vue3 前端源码 |
| `data/` | ✅ 完整 | demo 数据 + 离线底图 |
| `outputs/` | ✅ 存在 | 输出目录 |
| `.github/workflows/ci.yml` | ✅ 存在 | CI 流水线 |
| `.env` | ✅ 存在 | 运行时环境变量 |
| `LICENSE` | ✅ 存在 | Apache 2.0 |
| `requirements.txt` | ✅ 存在 | 依赖备选声明 |

---

*本文档为 Research Draw v0.1.4 项目留档，用于项目交接、架构回顾与知识沉淀。*
