# 柯影智绘 Atlas（Research Draw Web）

> 柯影数智团队开发
>
> 当前版本：`v0.1.4`

Web 模块基于 CLI 能力封装，提供面向终端用户的一体化科研绘图流程。
建议统一使用 `uv run` 启动（`uv run python -m src.main`、`uv run uvicorn web.backend.app:app`），避免运行时路径和依赖环境差异。

版本统一策略：

- 统一版本源：项目根目录 `VERSION`
- 后端版本：`src/version.py` 自动注入到 FastAPI
- 前端版本：`npm` 脚本前自动执行 `sync:version`，同步 `package.json` 与 `package-lock.json`

## 模块结构

- `web/backend/app.py`：FastAPI API 服务（上传、渲染、文件管理、手册/联系方式接口）
- `web/frontend/`：Vue3 + Vite 前端
- `web/assets/`：关于页联系方式素材目录（二维码/图片）

## 当前前端能力

- 顶部菜单栏：
  - 工作区 / 数据集 / 操作
  - 关于页面
  - 用户手册页面
- 左侧导航：
  - 工作区模式下显示流程导航
  - 关于/手册模式下显示页面导航
- 数据输入：
  - 上传文件（CSV/TSV/TXT/XLSX/XLS）
  - 页面表格录入并保存为数据集
  - 数据预览（列名 + 前几行）
- 渲染控制：
  - 图型分组选择
  - 图标题、`xlabel/ylabel/zlabel` 与数据集输入解耦
  - 顶部主按钮一键渲染
- 文件与历史管理：
  - 上传文件列表（使用/删除/清空）
  - 渲染历史（复用配置/打开结果/删除记录+文件）
  - 本地渲染文件列表（打开/删除/清空）
- 信息页：
  - 关于页面读取 `web/assets` 联系方式素材
  - 用户手册页面读取 `ResearchDrawApp_使用手册.md`，前端按 Markdown 渲染

## 启动方式

### 1) 启动后端

在项目根目录执行：

```bash
uv sync --extra web --extra data --extra ml --extra maps --extra raster
uv run uvicorn web.backend.app:app --reload --host 127.0.0.1 --port 8000
```

### 2) 启动前端

```bash
cd web/frontend
npm install
npm run sync:version
npm run dev
```

前端质量检查：

```bash
cd web/frontend
npm run lint
npm run test
npm run build
```

默认地址：

- 前端：`http://127.0.0.1:5173`
- 后端：`http://127.0.0.1:8000`

前端可在“后端连接（高级设置）”中修改 API 地址。

## 后端 API

- `GET /api/health`
- `GET /api/version`
- `GET /api/plots`
- `GET /api/plot-registry`：图型注册中心（分组/别名/必需字段/默认参数/依赖提示/demo 信息）
- `GET /api/contact-assets`：读取 `web/assets` 下可展示图片
- `GET /api/user-manual`：读取项目手册 Markdown 文本
- `POST /api/upload`
- `GET /api/uploads`（支持 `page` / `page_size` 分页；返回 `usage_bytes` / `quota_bytes`）
- `GET /api/uploads/{file_id}/inspect`
- `DELETE /api/uploads/{file_id}`
- `DELETE /api/uploads`
- `POST /api/tasks/render/submit`：提交渲染任务（异步）
- `GET /api/tasks/{task_id}`：查询任务状态
- `POST /api/tasks/{task_id}/cancel`：取消任务
- `GET /api/tasks`：任务列表（支持 `limit/status`）
- `GET /api/maintenance/cleanup`：后台清理状态（含文件/字节清理统计与当前占用）
- `POST /api/render`：同步渲染（兼容旧接口，不建议前端直连）
- `GET /api/renders`（支持 `page` / `page_size` 分页；返回 `usage_bytes` / `quota_bytes`）
- `DELETE /api/renders/{filename}`
- `DELETE /api/renders`
- `GET /api/files/{filename}`
- `GET /assets/...`：静态资源映射（默认映射 `web/assets`）

## 运行时配额与清理参数（环境变量）

- `WEB_UPLOAD_MAX_FILE_MB`：单个上传文件大小上限（默认 `200`）
- `WEB_UPLOAD_MAX_FILES`：上传目录文件数上限（默认 `300`）
- `WEB_UPLOAD_MAX_TOTAL_MB`：上传目录总大小上限（默认 `2048`）
- `WEB_UPLOAD_RETENTION_DAYS`：上传文件保留天数（默认 `14`）
- `WEB_RENDER_MAX_FILES`：渲染目录文件数上限（默认 `600`）
- `WEB_RENDER_MAX_TOTAL_MB`：渲染目录总大小上限（默认 `4096`）
- `WEB_RENDER_RETENTION_DAYS`：渲染文件保留天数（默认 `30`）
- `WEB_CLEANUP_INTERVAL_SECONDS`：后台周期清理间隔秒数（默认 `600`）

## 约束与说明

- 后端默认使用无 GUI 渲染（`Agg`）。
- Web 端默认走“异步任务队列 + 轮询状态”模型，避免重图渲染阻塞请求线程。
- 后端包含后台清理策略（按数量 + TTL + 目录总配额清理上传文件/渲染文件，并清理过期任务记录）。
- Web 渲染时，`mode=file` 优先使用上传文件；也兼容在 `args.file` 传入项目内路径。
- `isosurface3d` 依赖 `scikit-image`（已在 `.[ml]` / `.[all]`）。
