# ResearchDrawApp 使用手册（v0.1.4）

本手册覆盖当前项目的 CLI 与 Web 端能力，内容与仓库最新代码同步。

版本治理（v0.1.4）：

- 单一版本源：项目根目录 `VERSION`
- CLI / Web 后端：通过 `src/version.py` 自动读取并注入
- 前端 package 版本：通过 `web/frontend/scripts/sync-version.mjs` 自动同步到 `package.json` 与 `package-lock.json`

环境治理：

- Python 固定为 `3.13.15`
- 使用 `uv` 管理虚拟环境、依赖和锁文件
- `.python-version` 固定解释器版本，`uv.lock` 固定依赖解析结果

## 1. 工具概览

- CLI 入口：`uv run python -m src.main` 或 `uv run research-draw`
- Web 入口：`web/backend/app.py` + `web/frontend/`
- 支持图型：
  - 统计二维：`box` / `violin` / `scatter` / `volcano` / `forest`
  - 领域二维：`ma` / `enrich_dot` / `gsea` / `embedding` / `upset` / `km` / `roc` / `calibration` / `bland_altman` / `dca` / `stress_strain` / `xrd` / `raman` / `phase` / `hysteresis` / `spectral_signature` / `index_ts` / `confusion` / `class_dist` / `candlestick` / `cum_return` / `rolling_stats` / `frontier` / `acf_pacf` / `likert` / `raincloud` / `irt_icc` / `factor_loadings` / `interaction`
  - 三维：`scatter3d` / `surface3d` / `wireframe3d` / `contour3d` / `line3d` / `isosurface3d` / `slice3d` / `quiver3d` / `waterfall3d` / `embedding3d` / `mesh3d`
  - 地图：`world` / `world_admin1` / `china` / `choropleth_world` / `choropleth_china` / `raster` / `points`

## 2. 安装

推荐 Python `3.10+`。

```bash
# 安装/同步基础环境
uv sync

# 常用组合（Web + 数据 + ML + 地图）
uv sync --extra web --extra data --extra ml --extra maps --extra raster
```

说明：

- YAML 配置解析依赖 `PyYAML`，已在基础依赖中声明。
- `isosurface3d` 依赖 `scikit-image`（在 `.[ml]` / `.[all]` 中）。

## 3. CLI 快速使用

### 3.1 查看帮助

```bash
uv run python -m src.main -h
uv run python -m src.main --help-examples
```

### 3.2 Demo 示例

```bash
uv run python -m src.main --mode demo --plot box --title "箱线图演示"
uv run python -m src.main --mode demo --plot confusion --title "Confusion Demo"
uv run python -m src.main --mode demo --plot scatter3d --title "3D Scatter"
uv run python -m src.main --mode demo --plot quiver3d --title "3D Vector Field"
uv run python -m src.main --mode demo --plot choropleth_world --title "World Choropleth"
```

### 3.3 文件模式示例

```bash
uv run python -m src.main --mode file --plot scatter --file data/demo_scatter.csv --x-col x --y-col y
uv run python -m src.main --mode file --plot scatter3d --file data/demo_scatter3d.csv --x-col x --y-col y --z-col z
uv run python -m src.main --mode file --plot upset --file data/biomed/upset.csv
uv run python -m src.main --mode file --plot confusion --file data/remote/confusion.csv
uv run python -m src.main --mode file --plot choropleth_china --file data/china_values.csv --level 1 --key-col NAME_1 --value-col value
```

### 3.4 自定义模式示例

```bash
uv run python -m src.main --mode custom --plot box --group "Ctrl:1,2,3" --group "A:2,3,4"
uv run python -m src.main --mode custom --plot scatter --x "1,2,3,4" --y "1.1,2.4,2.8,4.2" --ci 0.95
uv run python -m src.main --mode custom --plot volcano --log2fc "0.5,1.2,-1.1" --pvals "0.05,0.01,0.2"
```

## 4. Web 端使用

### 4.1 启动

```bash
# 后端（项目根目录）
uv run uvicorn web.backend.app:app --reload --host 127.0.0.1 --port 8000

# 前端
cd web/frontend
npm install
npm run sync:version
npm run dev
```

### 4.2 页面结构

- 顶部菜单栏：
  - `工作区`、`数据集`、`操作`
  - `关于页面`
  - `用户手册页面`
- 左侧导航栏：
  - 工作区模式：流程导航
  - 信息页模式：页面导航
- 主面板：
  - 工作区（数据输入、图型选择、图形设置、渲染结果）
  - 关于页面（展示 `web/assets` 联系方式）
  - 用户手册页面（读取并渲染本手册 Markdown）

### 4.3 用户手册页面说明

- 后端接口：`GET /api/user-manual`
- 返回内容：手册 Markdown 文本
- 前端渲染：按 Markdown 语义展示（标题、段落、列表、代码块、引用、链接）

## 5. 数据格式要求

### 5.1 通用文件格式

- 支持：`.csv` / `.tsv` / `.txt` / `.xlsx` / `.xls`
- 文件建议 UTF-8 编码；分隔符可自动推断，也可通过 `--sep` 指定

### 5.2 常用二维图

- `scatter`：至少 `x_col` + `y_col`
- `box` / `violin`：
  - 长表：`group_col` + `value_col`
  - 宽表：自动读取所有数值列
- `volcano`：`log2fc_col` + `p_col`，可选 `label_col`
- `forest`：`forest_label_col` + `effect_col` + `ci_low_col` + `ci_high_col`

### 5.3 常用三维图

- `scatter3d` / `line3d` / `surface3d` / `wireframe3d` / `contour3d` / `waterfall3d` / `mesh3d`：
  - `x_col` + `y_col` + `z_col`
- `quiver3d`：
  - `x_col` + `y_col` + `z_col` + `u_col` + `v_col` + `w_col`
- `isosurface3d` / `slice3d`：
  - 体素坐标和标量（常用 `x_col` + `y_col` + `z_col` + `scalar_col`）

### 5.4 地图相关

- `choropleth_world` / `choropleth_china`：
  - `key_col` + `value_col`
- `points`：
  - `lon_col` + `lat_col`
  - 可选：`hue_col` / `size_col` / `label_col`
- `raster`：
  - 需提供 `--raster-file`（GeoTIFF 等）

## 6. 配置文件（JSON/YAML）

可通过 `--config` 读取配置：

```bash
uv run python -m src.main --config path/to/config.yaml
```

规则：

- 配置中的键名与 CLI 参数对应（下划线形式）
- 命令行显式传入的参数优先级高于配置文件
- 配置文件会经过统一 schema 校验（Pydantic）：
  - 未定义字段报错
  - 基础类型自动校验
  - `group` 等 append 参数自动归一为列表

地图相关补充：

- Geo 数据读取默认启用进程级 LRU 缓存（减少重复读盘）
- 可通过 `GEO_READ_CACHE_MAX_ITEMS` 调整缓存条目上限（默认 `24`）

## 7. Web API 概览

- 健康检查：`GET /api/health`
- 版本信息：`GET /api/version`
- 图型与注册中心：`GET /api/plots` / `GET /api/plot-registry`
- 上传文件：`POST /api/upload`
- 上传文件管理：`GET /api/uploads` / `GET /api/uploads/{file_id}/inspect` / `DELETE /api/uploads/{file_id}` / `DELETE /api/uploads`
- `GET /api/uploads` 支持 `page`、`page_size` 分页参数，并返回 `usage_bytes`、`quota_bytes`
- 异步渲染任务：`POST /api/tasks/render/submit` / `GET /api/tasks/{task_id}` / `POST /api/tasks/{task_id}/cancel` / `GET /api/tasks`
- 清理状态：`GET /api/maintenance/cleanup`（含文件数/字节清理统计与当前占用）
- 同步渲染（兼容旧接口）：`POST /api/render`
- 渲染文件管理：`GET /api/renders` / `DELETE /api/renders/{filename}` / `DELETE /api/renders`
- `GET /api/renders` 支持 `page`、`page_size` 分页参数，并返回 `usage_bytes`、`quota_bytes`
- 文件访问：`GET /api/files/{filename}`
- 联系方式素材：`GET /api/contact-assets`
- 用户手册：`GET /api/user-manual`
- 静态素材：`GET /assets/...`

### 7.1 Web 清理策略与配额参数

- 上传文件单文件上限：`WEB_UPLOAD_MAX_FILE_MB`（默认 `200`）
- 上传目录文件数上限：`WEB_UPLOAD_MAX_FILES`（默认 `300`）
- 上传目录总大小上限：`WEB_UPLOAD_MAX_TOTAL_MB`（默认 `2048`）
- 上传目录 TTL（天）：`WEB_UPLOAD_RETENTION_DAYS`（默认 `14`）
- 渲染目录文件数上限：`WEB_RENDER_MAX_FILES`（默认 `600`）
- 渲染目录总大小上限：`WEB_RENDER_MAX_TOTAL_MB`（默认 `4096`）
- 渲染目录 TTL（天）：`WEB_RENDER_RETENTION_DAYS`（默认 `30`）
- 周期清理间隔（秒）：`WEB_CLEANUP_INTERVAL_SECONDS`（默认 `600`）

## 8. 工程质量基线（ruff + mypy + pytest + frontend lint/test + CI）

### 8.1 后端质量检查

```bash
uv sync --extra test
uv run ruff check src/main.py src/cli/parser.py src/cli/config_schema.py src/version.py web/backend/app.py tests/test_cli_parser.py tests/test_loaders.py tests/test_smoke_app.py
uv run mypy
MPLBACKEND=Agg PLOT_BACKEND=Agg HEADLESS=1 uv run pytest -q
```

说明：

- `ruff`：代码风格与静态问题检查（当前基线检查核心入口与关键测试文件）
- `mypy`：类型检查（按 `pyproject.toml` 中基线范围执行）
- `pytest`：自动化单测 + smoke（无 GUI，Agg 后端）

### 8.2 前端质量检查

```bash
cd web/frontend
npm install
npm run lint
npm run test
npm run build
```

说明：

- `lint`：ESLint（Vue3 代码检查）
- `test`：Vitest（当前已包含基础状态层单测）
- `build`：Vite 生产构建检查

### 8.3 CI（GitHub Actions）

- 工作流文件：`.github/workflows/ci.yml`
- 覆盖项：
  - 后端：`ruff` + `mypy` + `pytest`
  - 前端：`lint` + `test` + `build`
  - 关键 smoke：CLI 渲染 `demo box` 并校验输出文件存在

### 8.4 本地一键回归建议

```bash
uv sync --extra test
uv run ruff check src/main.py src/cli/parser.py src/cli/config_schema.py src/version.py web/backend/app.py tests/test_cli_parser.py tests/test_loaders.py tests/test_smoke_app.py
uv run mypy
MPLBACKEND=Agg PLOT_BACKEND=Agg HEADLESS=1 uv run pytest -q
cd web/frontend && npm run lint && npm run test && npm run build
```

## 9. 常见问题

- 提示缺少可选依赖：
  - 请按报错提示安装对应 extras，例如 `.[ml]`、`.[maps]`、`.[raster]`
- 地图底图缺失：
  - 检查 `MAP_BASEMAP_ROOT` 或 `--basemap-root`
- Web 端无法连接后端：
  - 在左侧“后端连接（高级设置）”中确认 API 地址
- 用户手册页面为空：
  - 检查项目根目录是否存在 `ResearchDrawApp_使用手册.md`

## 10. 建议实践

- 产出论文图建议使用：`--fmt pdf --dpi 300 --tight`
- 对复杂流程优先用 YAML 配置固定参数，命令行只覆盖少量差异参数
- 在 CI 中至少保留一个 smoke 渲染流程，尽早发现依赖与回归问题
