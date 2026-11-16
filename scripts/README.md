# Scripts Guide

`scripts/` 是项目的“工具脚本层”，和 `tests/`（pytest 自动化测试）完全分离。

适用版本：`v0.1.5`（当前开发版本，尚未发布）；Python 版本为 `3.13.15`，通过 `uv` 管理。

## 目录定位

- `tests/`：CI/回归自动化测试（由 `pytest` 统一执行）
- `scripts/`：运维、数据准备、手工 smoke 验证脚本

## 常用脚本

- `dev_web.py`
  - 从项目根目录一条命令启动 Web 前端和后端：
  - `uv run --extra web --extra ml --extra maps python scripts/dev_web.py`
  - 按 `Ctrl+C` 会同时停止前后端服务。

- `download_basemaps.py`
  - 下载离线底图（Natural Earth + GADM）并可选提取港澳区域
  - 示例：`uv run python scripts/download_basemaps.py --dir data/geo`

- `generate_test_data.py`
  - 生成中英文统计图测试数据与领域数据
  - 示例：`uv run python scripts/generate_test_data.py`

- `generate_domain_demo_data.py`
  - 轻量生成领域 demo 数据
  - 示例：`uv run python scripts/generate_domain_demo_data.py`

- `generate_demo_rasters.py`
  - 生成 world/china 演示 GeoTIFF 栅格
  - 示例：`uv run python scripts/generate_demo_rasters.py --out-dir data`

- `smoke_statics_en.py` / `smoke_statics_cn.py`
  - 统计图手工 smoke（英文/中文列名）

- `smoke_maps_en.py` / `smoke_maps_cn.py`
  - 地图功能手工 smoke（底图/分级/点叠加/栅格）

- `smoke_domain_plots.py`
  - 领域图手工 smoke（生物/临床/材料/遥感/金融/心理）

## 使用建议

- 先运行 `generate_test_data.py` 和 `download_basemaps.py`，再跑 smoke 脚本。
- 这些脚本用于开发调试和人工验收，不纳入 pytest 收敛路径。
