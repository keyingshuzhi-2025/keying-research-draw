"""MCP Server for Research Draw.

This server exposes Research Draw's plotting capabilities as MCP tools,
allowing LLM clients to generate scientific visualizations.
"""

from __future__ import annotations

import asyncio
import os
import json
import re
import secrets
import threading
import time
import weakref
import base64
from difflib import SequenceMatcher, get_close_matches
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Literal, Optional

# The MCP process renders files in the background and has no GUI event loop.
# Select a non-interactive backend before importing the runner/plot modules;
# setting this only inside the runner is too late once pyplot was imported.
os.environ["MPLBACKEND"] = "Agg"
os.environ["PLOT_BACKEND"] = "Agg"
os.environ["HEADLESS"] = "1"

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolResult, ImageContent, TextContent

from src.cli.config_schema import validate_cli_config_payload
from src.cli.parser import build_parser
from src.mcp_server.runner import ResearchDrawMCPRunner
from src.mcp_server.http_auth import BearerTokenAuthMiddleware
from src.mcp_server.render_jobs import render_job_store, session_scope_from_job_id
from src.mcp_server.workspace import (
    ALLOWED_DATA_SUFFIXES,
    ALLOWED_RENDER_SUFFIXES,
    DEFAULT_MODEL_UPLOAD_CHUNK_BYTES,
    DEFAULT_WORKSPACE_ENV,
    list_configured_workspaces,
    resolve_workspace_selector,
    WorkspaceError,
)
from src.registry import (
    canonical_plots_by_group,
    group_metadata,
    plot_registry_payload,
    public_plot_name,
    required_fields_for_plot,
    default_args_for_plot,
    demo_data_path_for_plot,
)
from src.registry.plot_registry import (
    ALL_PUBLIC_PLOTS,
    PLOT_DESCRIPTIONS,
    PLOT_DISPLAY_NAMES,
    PLOT_DEPENDENCY_HINTS,
)


_COLUMN_CONFIG_KEYS = {
    "group_col", "value_col", "x_col", "y_col", "z_col", "z3d_col",
    "u_col", "v_col", "w_col", "scalar_col", "log2fc_col", "p_col",
    "label_col", "forest_label_col", "effect_col", "ci_low_col", "ci_high_col",
    "weight_col", "mean_col", "term_col", "count_col", "ratio_col", "hit_col",
    "score_col", "prob_col", "true_col", "pred_col", "time_col", "event_col",
    "class_col", "item_col", "response_col", "a_col", "b_col", "c_col",
    "factor_col", "loading_col", "date_col", "open_col", "high_col", "low_col",
    "close_col", "volume_col", "return_col", "price_col", "key_col", "lon_col",
    "lat_col", "size_col", "hue_col",
}
_BUNDLED_MAP_ONLY_PLOTS = {"world", "world_admin1", "china"}
_MODE_REQUIRED_PATH = {"raster": "raster_file"}
_CUSTOM_REQUIRED_FIELDS = {
    "box": ("group",),
    "violin": ("group",),
    "scatter": ("x", "y"),
    "bar": ("y",),
    "column": ("y",),
    "line": ("x", "y"),
    "histogram": ("y",),
    "area": ("x", "y"),
    "volcano": ("log2fc", "pvals"),
    "forest": ("forest_labels", "effects", "ci_low", "ci_high"),
    "scatter3d": ("x", "y", "z"),
    "surface3d": ("x", "y", "z"),
    "wireframe3d": ("x", "y", "z"),
    "contour3d": ("x", "y", "z"),
    "line3d": ("x", "y", "z"),
    "isosurface3d": ("x", "y", "z", "scalar"),
    "slice3d": ("x", "y", "z", "scalar"),
    "quiver3d": ("x", "y", "z", "u", "v", "w"),
    "waterfall3d": ("x", "y", "z"),
    "mesh3d": ("x", "y", "z"),
}
_PLOT_IMPORTS = {
    "data": ("pandas",),
    "maps": ("geopandas",),
    "raster": ("rasterio",),
}
_DATE_NAME_HINTS = ("date", "time", "timestamp", "year", "month", "日期", "时间", "年份", "月份")
_IDENTIFIER_NAME_HINTS = ("uuid", "sample_id", "subject_id", "record_id", "编号", "序号", "样本名")
_COLUMN_NAME_HINTS = {
    "group_col": ("group", "condition", "treatment", "class", "cohort", "组", "分组", "处理", "类别"),
    "value_col": ("value", "measurement", "score", "count", "abundance", "expression", "series", "ndvi", "数值", "浓度", "得分", "表达"),
    "x_col": ("date", "time", "year", "month", "rank", "position", "wavelength", "wavenumber", "theta", "strain", "x", "日期", "时间", "年份"),
    "y_col": ("running_es", "enrichment_score", "value", "measurement", "score", "result", "intensity", "stress", "reflectance", "y", "数值", "浓度", "得分", "表达"),
    "log2fc_col": ("log2fc", "log_fc", "fold_change", "foldchange", "fc", "差异倍数"),
    "p_col": ("pvalue", "p_value", "pval", "p_val", "fdr", "padj", "显著性"),
    "forest_label_col": ("study", "label", "term", "variable", "研究", "指标", "名称"),
    "effect_col": ("effect", "estimate", "odds_ratio", "hazard_ratio", "beta", "or", "hr", "rr", "效应", "估计"),
    "ci_low_col": ("ci_low", "lower_ci", "lower", "low", "lcl", "下限"),
    "ci_high_col": ("ci_high", "upper_ci", "upper", "high", "ucl", "上限"),
    "date_col": ("date", "datetime", "timestamp", "日期", "时间"),
    "time_col": ("survival_time", "duration", "time", "followup", "时间", "时长"),
    "event_col": ("event", "status", "censor", "发生", "结局"),
    "scalar_col": ("scalar", "intensity", "value", "volume", "强度", "数值"),
    "mean_col": ("mean", "average", "avg", "base_mean", "平均"),
    "term_col": ("term", "pathway", "description", "name", "通路", "条目"),
    "count_col": ("gene_count", "count", "n_genes", "number", "数量", "计数"),
    "ratio_col": ("ratio", "gene_ratio", "rich_factor", "比例"),
    "hit_col": ("hit", "hits", "位置", "命中"),
    "score_col": ("y_score", "score", "probability", "prob", "prediction", "得分", "概率"),
    "prob_col": ("y_prob", "probability", "prob", "score", "预测概率"),
    "true_col": ("y_true", "true", "actual", "outcome", "label", "target", "结局", "真实", "实际"),
    "pred_col": ("y_pred", "prediction", "predicted", "pred", "预测"),
    "class_col": ("class", "category", "label", "类别"),
    "item_col": ("item", "question", "variable", "题目", "题项"),
    "response_col": ("response", "rating", "score", "answer", "评分", "回答"),
    "a_col": ("discrimination", "disc", "slope", "a"),
    "b_col": ("difficulty", "diff", "threshold", "b"),
    "c_col": ("guessing", "guess", "c"),
    "factor_col": ("factor", "component", "因子"),
    "loading_col": ("loading", "载荷"),
    "open_col": ("open", "开盘"),
    "high_col": ("high", "最高"),
    "low_col": ("low", "最低"),
    "close_col": ("close", "收盘"),
    "volume_col": ("volume", "成交量"),
    "return_col": ("return", "returns", "ret", "收益"),
    "price_col": ("price", "close", "价格"),
    "lon_col": ("lon", "lng", "longitude", "经度"),
    "lat_col": ("lat", "latitude", "纬度"),
    "key_col": ("iso", "code", "region", "province", "name", "地区", "省份", "代码"),
    "label_col": ("label", "name", "gene", "sample", "标签", "名称"),
    "size_col": ("count", "value", "size", "数量"),
    "hue_col": ("class", "category", "group", "type", "类别"),
}
_FIELD_ROLE_BY_DEST = {
    "group_col": "categorical",
    "value_col": "numeric",
    "x_col": "numeric",
    "y_col": "numeric",
    "z_col": "numeric",
    "z3d_col": "numeric",
    "u_col": "numeric",
    "v_col": "numeric",
    "w_col": "numeric",
    "scalar_col": "numeric",
    "log2fc_col": "numeric",
    "p_col": "numeric",
    "forest_label_col": "categorical",
    "effect_col": "numeric",
    "ci_low_col": "numeric",
    "ci_high_col": "numeric",
    "weight_col": "numeric",
    "mean_col": "numeric",
    "term_col": "categorical",
    "count_col": "numeric",
    "ratio_col": "numeric",
    "hit_col": "numeric",
    "score_col": "numeric",
    "prob_col": "numeric",
    "true_col": "categorical",
    "pred_col": "categorical",
    "time_col": "datetime",
    "event_col": "numeric",
    "class_col": "categorical",
    "item_col": "categorical",
    "response_col": "categorical",
    "factor_col": "categorical",
    "loading_col": "numeric",
    "date_col": "datetime",
    "open_col": "numeric",
    "high_col": "numeric",
    "low_col": "numeric",
    "close_col": "numeric",
    "volume_col": "numeric",
    "return_col": "numeric",
    "price_col": "numeric",
    "key_col": "categorical",
    "lon_col": "numeric",
    "lat_col": "numeric",
    "label_col": "categorical",
    "size_col": "numeric",
    "hue_col": "categorical",
}

# File-mode columns used by specialist plots. Registry fields cover the common
# chart families; these mappings describe domain plots and optional enrichments.
_PLOT_FILE_FIELDS: dict[str, dict[str, str]] = {
    "box": {"group_col": "categorical", "value_col": "numeric"},
    "violin": {"group_col": "categorical", "value_col": "numeric"},
    "scatter": {"x_col": "numeric", "y_col": "numeric"},
    "bar": {"x_col": "categorical", "y_col": "numeric"},
    "column": {"x_col": "categorical", "y_col": "numeric"},
    "line": {"x_col": "datetime_or_categorical", "y_col": "numeric"},
    "histogram": {"value_col": "numeric"},
    "area": {"x_col": "datetime_or_categorical", "y_col": "numeric"},
    "volcano": {"log2fc_col": "numeric", "p_col": "numeric", "label_col": "categorical"},
    "forest": {"forest_label_col": "categorical", "effect_col": "numeric", "ci_low_col": "numeric", "ci_high_col": "numeric", "weight_col": "numeric"},
    "ma": {"mean_col": "numeric", "log2fc_col": "numeric", "p_col": "numeric"},
    "enrich_dot": {"term_col": "categorical", "p_col": "numeric", "count_col": "numeric", "ratio_col": "numeric"},
    "gsea": {"x_col": "numeric", "y_col": "numeric", "hit_col": "numeric"},
    "embedding": {"group_col": "categorical"},
    "upset": {"set_cols": "binary"},
    "km": {"time_col": "numeric", "event_col": "numeric", "group_col": "categorical"},
    "roc": {"true_col": "categorical", "score_col": "numeric"},
    "calibration": {"true_col": "categorical", "prob_col": "numeric"},
    "bland_altman": {"x_col": "numeric", "y_col": "numeric"},
    "dca": {"true_col": "categorical", "prob_col": "numeric"},
    "stress_strain": {"x_col": "numeric", "y_col": "numeric"},
    "xrd": {"x_col": "numeric", "y_col": "numeric", "group_col": "categorical"},
    "raman": {"x_col": "numeric", "y_col": "numeric", "group_col": "categorical"},
    "phase": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric"},
    "hysteresis": {"x_col": "numeric", "y_col": "numeric", "group_col": "categorical"},
    "spectral_signature": {"x_col": "numeric", "y_col": "numeric", "class_col": "categorical"},
    "index_ts": {"time_col": "datetime", "value_col": "numeric", "group_col": "categorical"},
    "confusion": {"true_col": "categorical", "pred_col": "categorical"},
    "class_dist": {"class_col": "categorical", "value_col": "numeric", "group_col": "categorical"},
    "candlestick": {"date_col": "datetime", "open_col": "numeric", "high_col": "numeric", "low_col": "numeric", "close_col": "numeric", "volume_col": "numeric"},
    "cum_return": {"date_col": "datetime", "return_col": "numeric", "price_col": "numeric"},
    "rolling_stats": {"date_col": "datetime", "return_col": "numeric"},
    "acf_pacf": {"value_col": "numeric"},
    "likert": {"item_col": "categorical", "response_col": "categorical", "count_col": "numeric"},
    "raincloud": {"group_col": "categorical", "value_col": "numeric"},
    "irt_icc": {"item_col": "categorical", "a_col": "numeric", "b_col": "numeric", "c_col": "numeric"},
    "factor_loadings": {"factor_col": "categorical", "item_col": "categorical", "loading_col": "numeric"},
    "interaction": {"x_col": "categorical", "group_col": "categorical", "value_col": "numeric"},
    "scatter3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric"},
    "surface3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric"},
    "wireframe3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric"},
    "contour3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric"},
    "line3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric"},
    "isosurface3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric", "scalar_col": "numeric"},
    "slice3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric", "scalar_col": "numeric"},
    "quiver3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric", "u_col": "numeric", "v_col": "numeric", "w_col": "numeric"},
    "waterfall3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric"},
    "embedding3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric"},
    "mesh3d": {"x_col": "numeric", "y_col": "numeric", "z_col": "numeric", "scalar_col": "numeric"},
    "choropleth_world": {"key_col": "categorical", "value_col": "numeric"},
    "choropleth_china": {"key_col": "categorical", "value_col": "numeric"},
    "points": {"lon_col": "numeric", "lat_col": "numeric", "label_col": "categorical", "size_col": "numeric", "hue_col": "categorical"},
}
_PLOT_REQUIRED_FIELD_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "ma": (("mean_col",), ("log2fc_col",)),
    "enrich_dot": (("term_col",), ("p_col",), ("count_col",)),
    "gsea": (("x_col",), ("y_col",)),
    "km": (("time_col",), ("event_col",)),
    "roc": (("true_col",), ("score_col", "prob_col")),
    "calibration": (("true_col",), ("prob_col",)),
    "bland_altman": (("x_col",), ("y_col",)),
    "dca": (("true_col",), ("prob_col",)),
    "stress_strain": (("x_col",), ("y_col",)),
    "xrd": (("x_col",), ("y_col",)),
    "raman": (("x_col",), ("y_col",)),
    "phase": (("x_col",), ("y_col",)),
    "hysteresis": (("x_col",), ("y_col",)),
    "spectral_signature": (("x_col",), ("y_col",)),
    "index_ts": (("time_col",), ("value_col",)),
    "confusion": (("true_col",), ("pred_col",)),
    "class_dist": (("class_col",),),
    "candlestick": (("date_col",), ("open_col",), ("high_col",), ("low_col",), ("close_col",)),
    "cum_return": (("date_col",), ("return_col", "price_col")),
    "rolling_stats": (("date_col",), ("return_col",)),
    "acf_pacf": (("value_col", "y_col"),),
    "likert": (("item_col",), ("response_col",)),
    "raincloud": (("group_col",), ("value_col",)),
    "irt_icc": (("item_col",), ("a_col",), ("b_col",)),
    "factor_loadings": (("factor_col",), ("item_col",), ("loading_col",)),
    "interaction": (("x_col",), ("group_col",), ("value_col",)),
    "isosurface3d": (("x_col",), ("y_col",), ("z_col",), ("scalar_col", "value_col")),
    "slice3d": (("x_col",), ("y_col",), ("z_col",), ("scalar_col", "value_col")),
}
_PLOT_COLUMN_ALIAS_GROUPS: dict[str, tuple[tuple[str, ...], ...]] = {
    "roc": (("score_col", "prob_col"),),
    "acf_pacf": (("value_col", "y_col"),),
    "isosurface3d": (("scalar_col", "value_col"),),
    "slice3d": (("scalar_col", "value_col"),),
    "mesh3d": (("scalar_col", "value_col"),),
}
for _plot_name in canonical_plots_by_group().get("plots_3d", []):
    _PLOT_COLUMN_ALIAS_GROUPS[_plot_name] = (
        *_PLOT_COLUMN_ALIAS_GROUPS.get(_plot_name, ()),
        ("z_col", "z3d_col"),
    )
_PLOT_SEMANTIC_REQUIRED_FIELDS: dict[str, tuple[str, ...]] = {
    "volcano": ("log2fc_col", "p_col"),
    "forest": ("effect_col", "ci_low_col", "ci_high_col"),
    "ma": ("mean_col", "log2fc_col"),
    "enrich_dot": ("term_col", "p_col", "count_col"),
    "gsea": ("x_col", "y_col"),
    "km": ("time_col", "event_col"),
    "roc": ("true_col", "score_col"),
    "calibration": ("true_col", "prob_col"),
    "dca": ("true_col", "prob_col"),
    "confusion": ("true_col", "pred_col"),
    "candlestick": ("date_col", "open_col", "high_col", "low_col", "close_col"),
    "points": ("lon_col", "lat_col"),
    "likert": ("item_col", "response_col"),
    "irt_icc": ("item_col", "a_col", "b_col"),
    "factor_loadings": ("factor_col", "item_col", "loading_col"),
}
_PLOT_EXTRA_SCHEMA_FIELDS: dict[str, tuple[str, ...]] = {
    "scatter": ("ci", "equal"),
    "bar": ("aggregation", "group_mode", "show_values", "tick_rotation"),
    "column": ("aggregation", "group_mode", "show_values", "tick_rotation"),
    "line": ("aggregation", "marker", "line_width"),
    "histogram": ("bins", "density", "hist_alpha"),
    "area": ("aggregation", "stacked", "area_alpha"),
    "volcano": ("fc_thresh", "p_thresh", "fdr", "top_n"),
    "forest": ("ref_line",),
    "enrich_dot": ("top_n",),
    "embedding": ("embed_method",),
    "upset": ("top_n",),
    "km": ("risk_table",),
    "roc": ("curve", "pos_label"),
    "calibration": ("n_bins", "calib_strategy"),
    "dca": ("thresholds",),
    "stress_strain": ("elastic_max", "yield_offset"),
    "irt_icc": ("theta_min", "theta_max"),
    "candlestick": ("date_col",),
    "rolling_stats": ("window", "risk_free"),
    "frontier": ("n_portfolios",),
    "acf_pacf": ("lags",),
    "surface3d": ("elev", "azim"),
    "wireframe3d": ("elev", "azim", "rstride", "cstride"),
    "contour3d": ("elev", "azim", "levels"),
    "line3d": ("elev", "azim"),
    "isosurface3d": ("elev", "azim", "iso_level"),
    "slice3d": ("elev", "azim", "slice_x", "slice_y", "slice_z"),
    "quiver3d": ("elev", "azim", "max_arrows", "length"),
    "waterfall3d": ("elev", "azim"),
    "mesh3d": ("elev", "azim"),
    "choropleth_world": ("scheme", "k", "on", "cmap", "label_top_n", "map_theme"),
    "choropleth_china": ("level", "scheme", "k", "on", "cmap", "label_top_n", "map_theme"),
    "raster": ("raster_file", "alpha", "basemap", "map_theme"),
    "points": ("basemap", "size_range", "map_theme"),
    "world": ("highlight", "label_names", "crs", "map_theme"),
    "world_admin1": ("countries", "label_names", "crs", "country_field", "case_sensitive", "map_theme"),
    "china": ("level", "highlight", "label_names", "crs", "map_theme"),
}
_SCHEMA_FIELD_EXAMPLES = {
    "file": "study.csv",
    "x": [1, 2, 3],
    "y": [4, 5, 6],
    "z": [7, 8, 9],
    "u": [0.1, 0.2, 0.3],
    "v": [0.2, 0.1, 0.0],
    "w": [0.0, 0.1, 0.2],
    "scalar": [0.3, 0.5, 0.8],
    "group": ["Control: 1,2,3", "Treatment: 2,3,4"],
    "log2fc": [1.2, -0.7, 2.1],
    "pvals": [0.01, 0.2, 0.003],
    "labels": ["Gene A", "Gene B", "Gene C"],
    "forest_labels": ["Study A", "Study B"],
    "effects": [0.4, 0.8],
    "ci_low": [0.2, 0.5],
    "ci_high": [0.6, 1.1],
    "weights": [0.4, 0.6],
    "group_col": "treatment",
    "value_col": "expression",
    "x_col": "time",
    "y_col": "value",
    "z_col": "depth",
    "log2fc_col": "log2FC",
    "p_col": "p_value",
    "mean_col": "mean_expression",
    "term_col": "pathway",
    "count_col": "gene_count",
    "ratio_col": "gene_ratio",
    "hit_col": "hit",
    "score_col": "predicted_score",
    "prob_col": "probability",
    "true_col": "actual_label",
    "pred_col": "predicted_label",
    "time_col": "survival_time",
    "event_col": "event",
    "class_col": "class",
    "item_col": "question",
    "response_col": "response",
    "a_col": "discrimination",
    "b_col": "difficulty",
    "c_col": "guessing",
    "factor_col": "factor",
    "loading_col": "loading",
    "date_col": "date",
    "open_col": "open",
    "high_col": "high",
    "low_col": "low",
    "close_col": "close",
    "volume_col": "volume",
    "return_col": "return",
    "price_col": "price",
    "key_col": "region_code",
    "lon_col": "longitude",
    "lat_col": "latitude",
    "label_col": "sample_name",
    "size_col": "count",
    "hue_col": "category",
    "set_cols": ["set_a", "set_b", "set_c"],
    "thresholds": [0.05, 0.10, 0.20],
    "countries": ["China", "Japan"],
    "highlight": ["北京", "上海"],
    "fmt": "png",
    "dpi": 300,
    "length": 8.0,
    "bins": 20,
    "palette": "tab10",
    "custom_json": "{\"x\": [1, 2], \"y\": [3, 4]}",
}
_SCHEMA_FIELD_DESCRIPTIONS = {
    "file": "工作区中的输入数据文件标识或相对路径。",
    "group_col": "用于区分实验组或类别的分组列。",
    "value_col": "用于绘图的连续数值列。",
    "x_col": "横轴数据列；折线图优先使用时间列，分类比较图使用类别列。",
    "y_col": "纵轴数值列。",
    "title": "图标题。",
    "xlabel": "X 轴标题。",
    "ylabel": "Y 轴标题。",
    "zlabel": "Z 轴标题。",
    "fmt": "导出文件格式。",
    "dpi": "栅格图导出分辨率。",
    "length": "3D 矢量箭头缩放因子；省略时根据点间距自动缩放，避免小向量几乎不可见。",
    "palette": "图形配色方案。",
    "grid": "是否显示基础二维图网格线。默认显示；设为 false 可关闭。",
    "bins": "直方图分箱数。",
    "z3d_col": "三维图 Z 轴数值列；优先级低于 z_col。",
    "scalar_col": "三维体数据中用于等值面或切片着色的标量列。",
    "log2fc_col": "差异分析中的 log2 倍数变化列。",
    "p_col": "显著性或 p 值列。",
    "forest_label_col": "森林图中每条研究或指标对应的标签列。",
    "effect_col": "森林图效应量列。",
    "ci_low_col": "效应量置信区间下限列。",
    "ci_high_col": "效应量置信区间上限列。",
    "weight_col": "森林图中用于控制研究权重的列。",
    "mean_col": "MA 图中表示平均表达量或基线均值的列。",
    "term_col": "富集结果中的通路或条目名称列。",
    "count_col": "条目计数列；富集图或 Likert 汇总表可使用。",
    "ratio_col": "富集结果比例列，用于气泡位置或辅助编码。",
    "hit_col": "GSEA 中标识命中位置的布尔或数值列。",
    "set_cols": "UpSet 图的集合列名，使用逗号分隔。",
    "score_col": "分类模型的预测分数列。",
    "prob_col": "模型预测概率列。",
    "true_col": "真实类别或结局列。",
    "pred_col": "模型预测类别列。",
    "time_col": "生存时长或时间序列横轴列。",
    "event_col": "生存事件指示列，通常为 0/1。",
    "class_col": "类别或分组标签列。",
    "item_col": "问卷题项或变量名称列。",
    "response_col": "问卷响应、评分或答案列。",
    "a_col": "IRT 项目区分度参数列。",
    "b_col": "IRT 项目难度参数列。",
    "c_col": "IRT 猜测参数列。",
    "factor_col": "因子载荷图中的因子名称列。",
    "loading_col": "因子载荷数值列。",
    "date_col": "金融或时间序列数据的日期列。",
    "open_col": "K 线图开盘价列。",
    "high_col": "K 线图最高价列。",
    "low_col": "K 线图最低价列。",
    "close_col": "K 线图收盘价列。",
    "volume_col": "K 线图成交量列（可选）。",
    "return_col": "收益率或收益变化列。",
    "price_col": "价格序列列；累计收益图可由价格计算收益。",
    "key_col": "用于关联地理区域的编码或名称列。",
    "lon_col": "经度列，使用十进制度。",
    "lat_col": "纬度列，使用十进制度。",
    "label_col": "可选的点位或观测对象标签列。",
    "size_col": "可选的点大小映射数值列。",
    "hue_col": "可选的点颜色映射类别或数值列。",
}
_SCHEMA_FIELD_CHOICES = {
    "embed_method": ["pca", "umap"],
    "curve": ["roc", "pr"],
    "normalize": ["none", "true", "pred", "all"],
    "calib_strategy": ["uniform", "quantile"],
    "aggregation": ["mean", "median", "sum"],
    "group_mode": ["grouped", "stacked"],
    "scheme": ["quantiles", "equal", "natural"],
    "on": ["iso_a3", "name", "NAME", "GID"],
    "map_theme": ["journal", "light", "dark"],
    "basemap": ["world_admin0", "china_l1", "none"],
    "fmt": ["png", "svg", "pdf"],
}
_ARRAY_SCHEMA_FIELDS = {
    "x", "y", "z", "u", "v", "w", "scalar", "group", "log2fc", "pvals",
    "labels", "forest_labels", "effects", "ci_low", "ci_high", "weights",
    "thresholds", "countries", "highlight", "set_cols",
}
_SCHEMA_FIELD_RANGES = {
    "ci": {"minimum": 0, "maximum": 1},
    "p_thresh": {"minimum": 0, "maximum": 1},
    "fdr": {"minimum": 0, "maximum": 1},
    "alpha": {"minimum": 0, "maximum": 1},
    "hist_alpha": {"minimum": 0, "maximum": 1},
    "area_alpha": {"minimum": 0, "maximum": 1},
    "bins": {"minimum": 1},
    "dpi": {"minimum": 72, "maximum": 1200},
    "k": {"minimum": 2, "maximum": 12},
    "fc_thresh": {"minimum": 0},
    "top_n": {"minimum": 0},
    "n_bins": {"minimum": 1},
    "window": {"minimum": 2},
    "lags": {"minimum": 1},
    "level": {"minimum": 0, "maximum": 3},
    "n_portfolios": {"minimum": 1},
    "max_arrows": {"minimum": 1},
    "levels": {"minimum": 1},
    "rstride": {"minimum": 1},
    "cstride": {"minimum": 1},
}


def _profile_columns(inspection: dict[str, Any]) -> dict[str, Any]:
    """Classify inspected table columns for chart recommendations."""
    preview_rows = inspection.get("preview_rows", [])
    columns: list[dict[str, Any]] = []
    for column in inspection.get("columns", []):
        name = str(column.get("name", ""))
        dtype = str(column.get("dtype", "")).lower()
        values = [row.get(name) for row in preview_rows if row.get(name) is not None]
        normalized_name = name.lower()
        is_identifier = (
            any(hint in normalized_name for hint in _IDENTIFIER_NAME_HINTS)
            or re.search(r"(^|[_\W])id($|[_\W])", normalized_name) is not None
        )
        role = "categorical"
        if is_identifier:
            role = "identifier"
        elif any(token in dtype for token in ("datetime", "date")):
            role = "datetime"
        elif any(token in dtype for token in ("int", "float", "double", "decimal", "number")) and "bool" not in dtype:
            role = "numeric"
        elif any(hint in normalized_name for hint in _DATE_NAME_HINTS) and values:
            role = "datetime"
        else:
            date_pattern_count = sum(
                isinstance(value, str)
                and re.search(r"\d{4}[-/.年]\d{1,2}|\d{1,2}[:：]\d{2}", value) is not None
                for value in values
            )
            if values and date_pattern_count / len(values) >= 0.7:
                role = "datetime"
            elif values:
                try:
                    import pandas as pd

                    parsed = pd.to_numeric(pd.Series(values), errors="coerce")
                    if int(parsed.notna().sum()) / len(values) >= 0.8:
                        role = "numeric"
                except ImportError:
                    pass
        normalized_values = {str(value).strip().lower() for value in values}
        is_binary = (
            "bool" in dtype
            or (
                bool(normalized_values)
                and len(normalized_values) <= 2
                and normalized_values.issubset({"0", "1", "true", "false", "yes", "no"})
            )
        )
        columns.append({
            "name": name,
            "dtype": column.get("dtype"),
            "role": role,
            "binary": is_binary,
            "example_values": values[:3],
            "missing_values": inspection.get("missing_values", {}).get(name, 0),
        })

    by_role = {
        role: [column["name"] for column in columns if column["role"] == role]
        for role in ("numeric", "categorical", "datetime", "identifier")
    }
    return {
        "row_count": inspection.get("row_count", 0),
        "column_count": inspection.get("column_count", len(columns)),
        "profiled_rows": len(preview_rows),
        "columns": columns,
        "numeric_columns": by_role["numeric"],
        "categorical_columns": by_role["categorical"],
        "datetime_columns": by_role["datetime"],
        "identifier_columns": by_role["identifier"],
    }


def _data_quality_warnings(
    profile: dict[str, Any],
    field_mapping: dict[str, str],
) -> list[str]:
    """Report relevant data quality issues for columns used by a plot."""
    warnings: list[str] = []
    columns = {column["name"]: column for column in profile.get("columns", [])}
    used_columns: list[str] = []
    for field, value in field_mapping.items():
        if field == "set_cols":
            used_columns.extend(part.strip() for part in value.split(",") if part.strip())
        else:
            used_columns.append(value)
    for name in dict.fromkeys(used_columns):
        missing = columns.get(name, {}).get("missing_values", 0)
        if missing:
            warnings.append(f"数据列“{name}”有 {missing} 个缺失值，绘图时可能会忽略这些记录。")
    if profile.get("row_count", 0) < 2:
        warnings.append("文件少于 2 行，图形可能无法显示有效的数据分布或趋势。")
    return warnings


def _column_mapping_for_plot(plot: str, profile: dict[str, Any]) -> dict[str, str]:
    """Suggest file-column mappings for a plot using types and column names."""
    columns = profile.get("columns", [])
    used: set[str] = set()
    mapping: dict[str, str] = {}

    def select(
        field: str,
        role: str,
        *,
        allow_numeric_fallback: bool = True,
        require_hint: bool = False,
    ) -> str | None:
        if role == "binary":
            pool = [column for column in columns if column.get("binary")]
        else:
            pool = [column for column in columns if column.get("role") == role]
        if role == "categorical" and allow_numeric_fallback and field in {
            "true_col", "pred_col", "group_col", "class_col", "response_col",
            "factor_col", "item_col", "key_col", "label_col", "x_col",
        }:
            pool += [
                column for column in columns
                if column.get("role") == "numeric" and column not in pool
            ]
        if role == "numeric" and field in {"event_col", "hit_col"}:
            pool += [
                column for column in columns
                if column.get("binary") and column not in pool
            ]
        if role == "datetime" and field in {"time_col", "date_col"} and not pool:
            hints = _COLUMN_NAME_HINTS.get(field, ())
            pool = [
                column for column in columns
                if column.get("role") == "numeric"
                and any(hint in column["name"].lower() for hint in hints if len(hint) > 2)
            ]
        hints = _COLUMN_NAME_HINTS.get(field, ())

        def hint_score(name: str) -> int:
            normalized = name.lower()
            score = 0
            for hint in hints:
                if len(hint) <= 2:
                    if normalized == hint or re.search(rf"(^|[^a-z0-9]){re.escape(hint)}([^a-z0-9]|$)", normalized):
                        score += 1
                elif hint in normalized:
                    score += 1
            return score

        pool.sort(
            key=lambda item: (
                -hint_score(item["name"]),
                item["name"].lower(),
            )
        )
        if require_hint:
            pool = [item for item in pool if hint_score(item["name"]) > 0]
        selected = next((item for item in pool if item["name"] not in used), None)
        if selected is None:
            return None
        used.add(selected["name"])
        return selected["name"]

    if plot in {"box", "violin"}:
        for field, role in (("group_col", "categorical"), ("value_col", "numeric")):
            value = select(field, role)
            if value:
                mapping[field] = value
    elif plot in {"bar", "column"}:
        for field, role in (("x_col", "categorical"), ("y_col", "numeric")):
            value = select(field, role)
            if value:
                mapping[field] = value
    elif plot in {"line", "area"}:
        x_value = select("x_col", "datetime") or select("x_col", "categorical")
        if x_value is None:
            x_value = select("x_col", "numeric")
        y_value = select("y_col", "numeric")
        if x_value:
            mapping["x_col"] = x_value
        if y_value:
            mapping["y_col"] = y_value
    elif plot == "scatter":
        for field in ("x_col", "y_col"):
            value = select(field, "numeric")
            if value:
                mapping[field] = value
    elif plot == "histogram":
        value = select("value_col", "numeric")
        if value:
            mapping["value_col"] = value
    elif (
        plot == "confusion"
        and profile.get("row_count", 0) > 0
        and profile.get("row_count") == profile.get("column_count")
        and len(profile.get("numeric_columns", [])) == profile.get("column_count")
    ):
        # A square numeric table is more likely to be a precomputed confusion matrix.
        pass
    else:
        field_roles = dict(_PLOT_FILE_FIELDS.get(plot, {}))
        for field in required_fields_for_plot(plot):
            field_roles.setdefault(field, _FIELD_ROLE_BY_DEST.get(field, "categorical"))
        required_single_fields = set(required_fields_for_plot(plot)) | {
            field
            for group in _PLOT_REQUIRED_FIELD_GROUPS.get(plot, ())
            if len(group) == 1
            for field in group
        }
        alternative_fields = {
            field
            for group in _PLOT_REQUIRED_FIELD_GROUPS.get(plot, ())
            if len(group) > 1
            for field in group
        }
        for field, role in field_roles.items():
            if field == "set_cols":
                set_columns = [
                    column["name"] for column in columns
                    if column.get("binary") and column["name"] not in used
                ]
                if len(set_columns) >= 2:
                    mapping[field] = ",".join(set_columns)
                    used.update(set_columns)
                continue
            value = select(
                field,
                role,
                allow_numeric_fallback=not (plot == "embedding" and field == "group_col"),
                require_hint=field not in required_single_fields or field in alternative_fields,
            )
            if value:
                mapping[field] = value
    return mapping


def _prune_inferred_aliases(
    plot: str,
    inferred_mapping: dict[str, str],
    explicit_config: dict[str, Any],
) -> dict[str, str]:
    """Keep an explicit alias from being shadowed by a different inferred column."""
    result = dict(inferred_mapping)
    for aliases in _PLOT_COLUMN_ALIAS_GROUPS.get(plot, ()):
        explicit_fields = [field for field in aliases if explicit_config.get(field)]
        if len(explicit_fields) == 1:
            explicit_field = explicit_fields[0]
            for field in aliases:
                if field != explicit_field:
                    result.pop(field, None)
    return result


def _plot_mapping_missing(
    plot: str,
    mapping: dict[str, str],
    profile: dict[str, Any],
    *,
    require_semantic_names: bool = False,
    inferred_fields: set[str] | None = None,
) -> list[str]:
    """Return required file fields that cannot be inferred from this table."""
    missing = [
        field for field in required_fields_for_plot(plot)
        if not mapping.get(field)
        and not (field == "z_col" and mapping.get("z3d_col"))
        and not any(
            field in aliases and any(mapping.get(alias) for alias in aliases if alias != field)
            for aliases in _PLOT_COLUMN_ALIAS_GROUPS.get(plot, ())
        )
    ]
    for alternatives in _PLOT_REQUIRED_FIELD_GROUPS.get(plot, ()):
        if not any(mapping.get(field) for field in alternatives):
            missing.append(" 或 ".join(alternatives))
    if plot == "upset" and len(mapping.get("set_cols", "").split(",")) < 2:
        missing.append("至少两个布尔/0-1 集合列")
    if plot in {"embedding", "frontier"} and len(profile.get("numeric_columns", [])) < 2:
        missing.append("至少两个数值特征列")
    square_numeric_matrix = (
        plot == "confusion"
        and profile.get("row_count", 0) > 0
        and profile.get("row_count") == profile.get("column_count")
        and len(profile.get("numeric_columns", [])) == profile.get("column_count")
    )
    if plot == "confusion" and square_numeric_matrix:
        missing = [field for field in missing if field not in {"true_col", "pred_col"}]
    if plot == "confusion" and not square_numeric_matrix and (
        not mapping.get("true_col") or not mapping.get("pred_col")
    ):
        missing.append("真实/预测列或方阵数据")
    if require_semantic_names:
        for field in _PLOT_SEMANTIC_REQUIRED_FIELDS.get(plot, ()):
            if inferred_fields is not None and field not in inferred_fields:
                continue
            value = mapping.get(field)
            hints = _COLUMN_NAME_HINTS.get(field, ())
            if value and hints and not any(hint in value.lower() for hint in hints if len(hint) > 2):
                missing.append(f"需要能识别 {field} 含义的列名")
    return list(dict.fromkeys(missing))


def _suggestions_for_profile(profile: dict[str, Any], goal: str) -> list[dict[str, Any]]:
    """Rank suitable general-purpose charts for a table and user goal."""
    numeric = profile.get("numeric_columns", [])
    categorical = profile.get("categorical_columns", [])
    dates = profile.get("datetime_columns", [])
    text = goal.lower()
    candidates: dict[str, tuple[float, str]] = {}

    def add(plot: str, score: float, reason: str) -> None:
        candidates[plot] = (score, reason)

    if numeric:
        add("histogram", 0.62, f"数值列“{numeric[0]}”可用于查看单变量分布。")
    if len(numeric) >= 2:
        add("scatter", 0.72, f"检测到多个数值列，可观察“{numeric[0]}”与“{numeric[1]}”之间的关系。")
    if categorical and numeric:
        add("bar", 0.68, f"分类列“{categorical[0]}”和数值列“{numeric[0]}”适合汇总比较。")
        add("column", 0.65, f"分类列“{categorical[0]}”和数值列“{numeric[0]}”适合按类别比较。")
        add("box", 0.70, f"分组列“{categorical[0]}”和数值列“{numeric[0]}”可比较组内分布。")
        add("violin", 0.60, f"分组列“{categorical[0]}”和数值列“{numeric[0]}”可比较分布形状。")
    if dates and numeric:
        add("line", 0.78, f"时间列“{dates[0]}”和数值列“{numeric[0]}”适合展示变化趋势。")
        add("area", 0.58, f"时间列“{dates[0]}”和数值列“{numeric[0]}”也可展示累计或连续变化。")

    specialist_goals = (
        (("火山图", "差异表达", "差异基因", "差异分析", "volcano"), "volcano", "检测到变化幅度与显著性字段，可用于差异分析。"),
        (("森林图", "荟萃", "meta分析", "置信区间", "forest"), "forest", "检测到效应量和置信区间字段，可汇总研究结果。"),
        (("ma图", "均值差异图", "ma plot"), "ma", "检测到平均表达量和倍数变化字段，可展示均值与差异关系。"),
        (("生存", "kaplan", "km曲线", "生存率"), "km", "检测到随访时间和结局字段，可绘制生存曲线。"),
        (("roc", "pr曲线", "分类模型评估", "模型评估"), "roc", "检测到真实标签和预测分数，可评估分类模型。"),
        (("校准", "概率校准", "calibration"), "calibration", "检测到真实标签和预测概率，可检查概率校准情况。"),
        (("混淆矩阵", "confusion"), "confusion", "检测到真实/预测标签或方阵数据，可查看分类结果。"),
        (("决策曲线", "临床净获益", "dca"), "dca", "检测到真实结局和预测概率，可比较决策阈值下的临床净获益。"),
        (("一致性", "bland-altman", "bland altman"), "bland_altman", "检测到两组数值测量，可评估方法间的一致性。"),
        (("富集", "通路", "enrichment"), "enrich_dot", "检测到通路、显著性和计数信息，可概览富集结果。"),
        (("k线", "蜡烛图", "candlestick"), "candlestick", "检测到日期及开高低收字段，可展示金融价格变化。"),
        (("地图点", "经纬度", "地理位置", "空间分布", "地图"), "points", "检测到经纬度列，可将观测位置绘制在地图上。"),
        (("集合交集", "集合关系", "upset"), "upset", "检测到多个二元集合列，可比较交集规模。"),
        (("gsea", "基因集富集", "运行富集分数"), "gsea", "检测到排序位置和运行富集分数字段，可绘制 GSEA 曲线。"),
        (("降维", "pca", "umap", "embedding"), "embedding", "检测到多列数值特征，可进行 PCA/UMAP 降维展示。"),
        (("光谱特征", "遥感光谱", "spectral signature"), "spectral_signature", "检测到波长和响应数值，可比较不同类别的光谱特征。"),
        (("ndvi时序", "遥感指数时序", "指数时序"), "index_ts", "检测到时间和指数数值，可展示遥感指数变化。"),
        (("地物类别", "类别分布", "class distribution"), "class_dist", "检测到类别字段，可比较类别样本量或面积。"),
        (("三维散点", "三维关系", "3d scatter"), "scatter3d", "检测到至少三个数值列，可在三维坐标中展示观测点。"),
        (("xrd", "衍射"), "xrd", "检测到连续数值字段，可展示 X 射线衍射曲线。"),
        (("拉曼", "raman", "红外"), "raman", "检测到连续数值字段，可展示光谱响应曲线。"),
        (("应力应变", "stress-strain"), "stress_strain", "检测到连续数值字段，可展示应力与应变关系。"),
        (("相图", "phase diagram"), "phase", "检测到成分和温度等数值字段，可展示材料相图。"),
        (("磁滞", "滞回", "hysteresis"), "hysteresis", "检测到两个连续测量变量，可展示加载与卸载的滞回关系。"),
        (("累计收益", "收益回撤", "drawdown"), "cum_return", "检测到日期和收益或价格列，可展示累计收益与回撤。"),
        (("滚动波动", "滚动统计", "rolling statistics"), "rolling_stats", "检测到日期与收益列，可展示滚动波动和风险指标。"),
        (("有效前沿", "投资组合", "portfolio frontier"), "frontier", "检测到多列数值收益，可估计风险收益有效前沿。"),
        (("自相关", "偏自相关", "acf", "pacf"), "acf_pacf", "检测到数值序列，可检查不同滞后阶数的相关性。"),
        (("likert", "李克特", "量表分布"), "likert", "检测到题项和响应字段，可比较量表选项分布。"),
        (("雨云图", "raincloud"), "raincloud", "检测到分组和连续数值，可比较分布与观测值。"),
        (("irt", "项目特征曲线"), "irt_icc", "检测到项目参数字段，可绘制 IRT 项目特征曲线。"),
        (("因子载荷", "factor loading"), "factor_loadings", "检测到因子、变量和载荷字段，可比较因子载荷。"),
        (("交互效应", "交互作用", "interaction effect"), "interaction", "检测到两个分类因素和结果数值，可展示交互效应。"),
        (("分级设色", "区域指标地图", "choropleth"), "choropleth_china", "检测到区域关联键和数值指标，可绘制分级设色地图。"),
    )
    for triggers, specialist, reason in specialist_goals:
        if any(trigger in text for trigger in triggers):
            add(specialist, 0.96, reason)

    preference_groups = [
        (("趋势", "时序", "时间变化", "随时间", "trend", "time series"), {"line": 0.28, "area": 0.16}),
        (("关系", "相关", "相关性", "关联", "relationship", "correlation"), {"scatter": 0.30}),
        (("分布", "频数", "密度", "distribution", "histogram"), {"histogram": 0.32, "violin": 0.14, "box": 0.10}),
        (("比较", "差异", "组间", "对比", "compare", "difference"), {"box": 0.24, "bar": 0.18, "column": 0.14, "violin": 0.10}),
        (("排名", "排行", "类别", "构成", "rank", "category"), {"bar": 0.24, "column": 0.18}),
    ]
    for triggers, boosts in preference_groups:
        if any(trigger in text for trigger in triggers):
            for plot, boost in boosts.items():
                if plot in candidates:
                    score, reason = candidates[plot]
                    candidates[plot] = (min(score + boost, 0.99), reason)

    explicit_names = {
        "折线": "line", "趋势线": "line", "散点": "scatter", "箱线": "box",
        "小提琴": "violin", "直方": "histogram", "条形": "bar", "柱状": "column",
        "面积": "area",
    }
    for keyword, plot in explicit_names.items():
        if keyword in text and plot in candidates:
            score, reason = candidates[plot]
            candidates[plot] = (min(score + 0.25, 0.99), reason)

    recommendations = []
    for plot, (score, reason) in sorted(candidates.items(), key=lambda item: (-item[1][0], item[0])):
        field_mapping = _column_mapping_for_plot(plot, profile)
        if _plot_mapping_missing(plot, field_mapping, profile, require_semantic_names=True):
            continue
        recommended_config = {"file": "<file_id>", **field_mapping}
        recommendations.append({
            "plot": plot,
            "display_name": PLOT_DISPLAY_NAMES.get(plot, plot),
            "score": round(score, 2),
            "reason": reason,
            "field_mapping": field_mapping,
            "suggested_config": recommended_config,
        })
        if len(recommendations) == 5:
            break
    return recommendations


def _plot_parameter_schema(plot: str) -> list[dict[str, Any]]:
    """Build a field-level schema from the CLI parser and plot registry."""
    parser = build_parser()
    action_map: dict[str, list[Any]] = {}
    for action in parser._actions:
        if action.dest != "help":
            action_map.setdefault(action.dest, []).append(action)

    defaults = default_args_for_plot(plot)
    required = set(required_fields_for_plot(plot))
    custom_required = set(_CUSTOM_REQUIRED_FIELDS.get(plot, ()))
    common = {"title", "save_name", "fmt", "dpi", "xlabel", "ylabel", "tight"}
    if plot in canonical_plots_by_group().get("plots_3d", []):
        common.update({"zlabel", "z3d_col"})
    if plot in {"isosurface3d", "slice3d", "mesh3d"}:
        common.add("value_col")
    if plot in canonical_plots_by_group().get("stats_2d", []):
        common.update({"palette", "grid"})
    file_column_fields = set(_PLOT_FILE_FIELDS.get(plot, {}))
    alias_fields = {
        field
        for group in _PLOT_COLUMN_ALIAS_GROUPS.get(plot, ())
        for field in group
    }
    fields = (
        required
        | custom_required
        | set(defaults)
        | common
        | file_column_fields
        | alias_fields
        | set(_PLOT_EXTRA_SCHEMA_FIELDS.get(plot, ()))
    )
    if plot == "raster":
        fields.add("raster_file")
    else:
        fields.add("file")

    parameters: list[dict[str, Any]] = []
    required_alias_fields = {
        field
        for group in _PLOT_COLUMN_ALIAS_GROUPS.get(plot, ())
        if len(group) > 1 and any(alias in required for alias in group)
        for field in group
    }
    for field in sorted(fields, key=lambda item: (item not in required, item)):
        actions = action_map.get(field, [])
        first = actions[0] if actions else None
        help_values = list(dict.fromkeys(
            str(action.help).strip() for action in actions if action.help
        ))
        if any(getattr(action, "nargs", None) == 0 for action in actions):
            field_type = "boolean"
        elif field in _ARRAY_SCHEMA_FIELDS:
            field_type = "array"
        elif first and first.type is int:
            field_type = "integer"
        elif first and first.type is float:
            field_type = "number"
        else:
            field_type = "string"

        if field in {"file", "raster_file", "set_cols"} or field in _COLUMN_CONFIG_KEYS:
            modes = ["file"]
        elif field in {"x", "y", "z", "u", "v", "w", "group", "scalar", "custom_json", "custom_json_file"}:
            modes = ["custom"]
        else:
            modes = ["demo", "custom", "file"]

        default = defaults.get(field, getattr(first, "default", None))
        required_modes = []
        alias_required = field in required_alias_fields
        if field in required and not alias_required:
            required_modes.append("file")
        if field in custom_required:
            required_modes.append("custom")
        if any(field in group and len(group) == 1 for group in _PLOT_REQUIRED_FIELD_GROUPS.get(plot, ())):
            required_modes.append("file")
        required_path = _MODE_REQUIRED_PATH.get(plot, "file")
        if (
            field == required_path
            and plot not in _BUNDLED_MAP_ONLY_PLOTS
        ):
            required_modes.append("file")
        parameter = {
            "name": field,
            "type": field_type,
            "description": _SCHEMA_FIELD_DESCRIPTIONS.get(
                field, "；".join(help_values) or f"{field} 参数。"
            ),
            "required": bool(required_modes),
            "required_modes": required_modes,
            "applicable_modes": modes,
            "default": default,
        }
        choices = getattr(first, "choices", None) if first else None
        if choices:
            parameter["choices"] = list(choices)
        elif field in _SCHEMA_FIELD_CHOICES:
            parameter["choices"] = _SCHEMA_FIELD_CHOICES[field]
        else:
            parameter["choices"] = []
        parameter["range"] = _SCHEMA_FIELD_RANGES.get(field)
        if field in _SCHEMA_FIELD_EXAMPLES:
            parameter["example"] = _SCHEMA_FIELD_EXAMPLES[field]
        elif field in _COLUMN_CONFIG_KEYS:
            parameter["example"] = "<数据列名>"
        elif field in required:
            parameter["example"] = f"<列名:{field}>"
        elif field_type == "boolean":
            parameter["example"] = True
        elif default is not None:
            parameter["example"] = default
        elif parameter["choices"]:
            parameter["example"] = parameter["choices"][0]
        elif field_type == "array":
            parameter["example"] = [1, 2, 3]
        elif field_type in {"integer", "number"}:
            parameter["example"] = 1
        else:
            parameter["example"] = f"<{field}>"
        if field in {"set_cols", "countries", "highlight", "thresholds"}:
            parameter["format"] = "逗号分隔的列名" if field == "set_cols" else "逗号分隔的值"
        parameters.append(parameter)

    return parameters


def _validation_diagnostics(
    errors: list[str],
    warnings: list[str],
    available_columns: set[str],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Turn human-readable validation messages into actionable diagnostics."""
    diagnostics: list[dict[str, Any]] = []
    suggested_config: dict[str, Any] | None = None

    def add_diagnostic(
        severity: str,
        code: str,
        message: str,
        *,
        field: str | None = None,
        suggestion: str | None = None,
        candidates: list[str] | None = None,
    ) -> None:
        item: dict[str, Any] = {
            "severity": severity,
            "code": code,
            "field": field,
            "message": message,
        }
        if suggestion:
            item["suggestion"] = suggestion
        if candidates:
            item["candidate_columns"] = candidates
        diagnostics.append(item)

    for message in errors:
        unmapped_match = re.search(r"无法从数据中自动识别必需字段：(.+?)。?$", message)
        if unmapped_match:
            field = unmapped_match.group(1).rstrip("。").strip()
            add_diagnostic(
                "error",
                "required_field_unmapped",
                message,
                field=field,
                suggestion="调用 inspect_data_file 查看可用列，再根据 get_plot_schema 的字段说明显式传入列名。",
                candidates=sorted(available_columns)[:30],
            )
            continue

        schema_match = re.search(
            r"\n\s*([a-zA-Z_][a-zA-Z0-9_]*)\n\s+(Extra inputs are not permitted|Input should be[^\n]*)",
            message,
        )
        if schema_match:
            field, detail = schema_match.groups()
            valid_fields = sorted({
                action.dest for action in build_parser()._actions if action.dest != "help"
            })
            candidates = get_close_matches(field, valid_fields, n=3, cutoff=0.5)
            is_unknown = "Extra inputs are not permitted" in detail
            add_diagnostic(
                "error",
                "unknown_parameter" if is_unknown else "invalid_parameter_type",
                message,
                field=field,
                suggestion=(
                    f"参数名可能应为 {candidates[0]}。"
                    if is_unknown and candidates else
                    "根据 get_plot_schema 返回的类型和示例调整该参数。"
                ),
                candidates=candidates if is_unknown else None,
            )
            if is_unknown and candidates:
                best = SequenceMatcher(None, field.lower(), candidates[0].lower()).ratio()
                second = SequenceMatcher(None, field.lower(), candidates[1].lower()).ratio() if len(candidates) > 1 else 0.0
                if best >= 0.88 and best - second >= 0.12 and field in (suggested_config or config):
                    suggested_config = dict(suggested_config or config)
                    suggested_config[candidates[0]] = suggested_config.pop(field)
            continue

        column_match = re.search(r"([a-zA-Z_][a-zA-Z0-9_]*) 指定的列“(.+?)”不在文件中", message)
        if column_match:
            field, invalid_column = column_match.groups()
            available = sorted(available_columns)
            candidates = get_close_matches(invalid_column, available, n=3, cutoff=0.45)
            candidate_columns = available[:30]
            if len(available) > len(candidate_columns):
                candidate_label = "、".join(candidate_columns) + " 等"
            else:
                candidate_label = "、".join(candidate_columns)
            add_diagnostic(
                "error",
                "unknown_column",
                message,
                field=field,
                suggestion=(
                    f"将 {field} 改为“{candidates[0]}”后再校验。"
                    if candidates else
                    f"文件可用列为：{candidate_label}。请从中选择。"
                    if candidate_columns else "请先检查数据文件中的列名。"
                ),
                candidates=candidate_columns,
            )
            if candidates:
                best = SequenceMatcher(None, invalid_column.lower(), candidates[0].lower()).ratio()
                second = (
                    SequenceMatcher(None, invalid_column.lower(), candidates[1].lower()).ratio()
                    if len(candidates) > 1 else 0.0
                )
                if best >= 0.88 and best - second >= 0.12:
                    suggested_config = dict(suggested_config or config)
                    suggested_config[field] = candidates[0]
            continue

        missing_custom = re.search(r"custom 模式缺少参数：(.+)", message)
        if missing_custom:
            for field in (value.strip() for value in missing_custom.group(1).split(",")):
                add_diagnostic(
                    "error", "missing_parameter", message, field=field,
                    suggestion=f"为 {field} 提供数据，或改用 file 模式读取表格列。",
                )
            continue

        missing_file = re.search(r"file 模式需要配置 ([a-zA-Z0-9_]+)", message)
        if missing_file:
            field = missing_file.group(1)
            add_diagnostic(
                "error", "missing_parameter", message, field=field,
                suggestion="在 config 中提供该字段；表格绘图通常使用 file 字段指定工作区文件。",
            )
        elif "未知图型" in message:
            add_diagnostic("error", "unknown_plot", message, field="plot", suggestion="先调用 list_plots 查询可用图型名称。")
        elif "mode 必须" in message:
            add_diagnostic("error", "invalid_mode", message, field="mode", suggestion="mode 使用 demo、custom 或 file。")
        elif "缺少依赖" in message:
            add_diagnostic("error", "missing_dependency", message, field="dependencies", suggestion="按提示安装对应 uv extra 后重试。")
        elif "workspace" in message or "工作区" in message:
            add_diagnostic("error", "workspace_error", message, field="workspace", suggestion="调用 list_workspaces 并选择已配置的逻辑工作区。")
        else:
            add_diagnostic("error", "invalid_config", message, suggestion="检查字段拼写、字段类型和当前图型的参数说明。")

    for message in warnings:
        missing_fields = re.search(r"未显式指定(?:领域)?字段：(.+?)(?:；|$)", message)
        if missing_fields:
            field_list = re.split(r"[,，]|\s+或\s+", missing_fields.group(1))
            for field in (value.strip() for value in field_list if value.strip()):
                add_diagnostic(
                    "warning", "field_not_mapped", message, field=field,
                    suggestion="确认自动识别的列符合预期；也可在 config 中显式指定对应列。",
                )
        else:
            add_diagnostic("warning", "validation_warning", message)

    return diagnostics, suggested_config


def _required_imports_for_plot(
    plot: str,
    mode: str,
    dependency_extra: str | None,
    config: dict[str, Any],
) -> tuple[str, ...]:
    modules = list(_PLOT_IMPORTS.get(dependency_extra or "", ()))
    if (
        (mode == "file" and plot not in _BUNDLED_MAP_ONLY_PLOTS and plot != "raster")
        or plot in canonical_plots_by_group().get("domain_2d", [])
        or plot == "embedding3d"
    ):
        modules.append("pandas")
    if plot in canonical_plots_by_group().get("maps", []):
        modules.append("geopandas")
    if plot == "upset":
        modules.append("upsetplot")
    elif plot == "isosurface3d":
        modules.append("skimage")
    elif plot in {"embedding", "embedding3d"} and str(config.get("embed_method", "pca")).lower() == "umap":
        modules.append("umap")
    return tuple(dict.fromkeys(modules))


# Initialize the FastMCP server
mcp = FastMCP(
    "research-draw",
    instructions=(
        "工作区工具可使用 workspace 逻辑名；省略工作区参数时使用服务端默认工作区。"
        "先调用 list_workspaces 查看允许的逻辑工作区。工作区选择器是顶层参数，不能放入 config。"
        "文件、待上传分块和绘图结果按 MCP 会话隔离；同一逻辑工作区中的其他会话不可见。"
        "文件绘图优先调用 suggest_plots 获取数据列角色和图型建议，再调用 create_plot 一次完成映射、校验和绘制。"
        "create_plots 可对同一文件批量绘制多种图；revise_plot 可基于 render_id 调整标题、配色和轴标签后重绘。"
        "若源文件已在所选逻辑工作区目录中，优先用 import_data_file 传相对路径，由服务器直接读取，避免模型搬运 Base64。"
        "远程客户端需要传输文件字节时，可使用 begin_data_upload、upload_data_chunk 和 complete_data_upload；"
        "模型客户端默认按 8 KiB 原始数据分块，避免高熵数据无法 gzip 压缩时单个 Base64 工具参数过大；"
        "如压缩有效，也可将每块独立 gzip 后设置 content_encoding='gzip'。"
        "chunk_size 与块索引始终按解压后的原始文件字节计算。"
        "直接绘图优先使用必填参数完整的 start_render_job；文件绘图、批量绘图或重绘使用 start_plot_job，避免 MCP 调用等待渲染而超时；"
        "随后用 get_plot_job_status 轮询，完成后用 get_plot_job_result 获取图片。"
        "网络超时后使用相同 request_id 重试提交以取回原任务，不要盲目重复绘图；同一 request_id 不可更换参数。"
        "get_plot_schema 返回字段类型、说明、默认值、示例、范围和模式要求；校验结果含 auto_mapping，失败时读取 diagnostics 与 suggested_config。"
    ),
)

_project_root: Optional[Path] = None
_PROCESS_SESSION_SCOPE = secrets.token_hex(16)
_SESSION_SCOPE_LOCK = threading.Lock()
_SESSION_SCOPES: dict[int, tuple[weakref.ReferenceType[Any], str]] = {}


def _forget_session_scope(
    object_id: int, reference: weakref.ReferenceType[Any]
) -> None:
    with _SESSION_SCOPE_LOCK:
        current = _SESSION_SCOPES.get(object_id)
        if current and current[0] is reference:
            _SESSION_SCOPES.pop(object_id, None)


def _session_scope_key(ctx: Context | None) -> str:
    """Derive an opaque, server-side workspace key from the MCP connection."""
    if ctx is None:
        if os.getenv("RESEARCH_DRAW_MCP_TRANSPORT", "stdio").strip().lower() == "streamable-http":
            raise WorkspaceError("HTTP MCP 请求缺少会话上下文，已拒绝共享工作区。")
        return _PROCESS_SESSION_SCOPE
    try:
        session = ctx.session
    except Exception as exc:
        if os.getenv("RESEARCH_DRAW_MCP_TRANSPORT", "stdio").strip().lower() == "streamable-http":
            raise WorkspaceError("无法读取 HTTP MCP 会话上下文，已拒绝共享工作区。") from exc
        session = None
    if session is None:
        if os.getenv("RESEARCH_DRAW_MCP_TRANSPORT", "stdio").strip().lower() == "streamable-http":
            raise WorkspaceError("HTTP MCP 会话标识为空，已拒绝共享工作区。")
        return _PROCESS_SESSION_SCOPE
    object_id = id(session)
    with _SESSION_SCOPE_LOCK:
        current = _SESSION_SCOPES.get(object_id)
        if current and current[0]() is session:
            return current[1]
        scope = secrets.token_hex(16)
        try:
            reference = weakref.ref(
                session,
                lambda ref, object_id=object_id: _forget_session_scope(object_id, ref),
            )
        except TypeError as exc:
            raise WorkspaceError("MCP SDK 会话对象无法安全绑定隔离工作区。") from exc
        _SESSION_SCOPES[object_id] = (reference, scope)
        return scope


def _get_runner(
    workspace: str | None = None,
    session_scope: str | None = None,
) -> ResearchDrawMCPRunner:
    """Get a runner scoped to one allowlisted workspace and MCP session."""
    global _project_root
    if workspace is not None:
        normalized_workspace = str(workspace).strip()
        if normalized_workspace.lower() in {"", "null", "none", "undefined"}:
            workspace = None
        else:
            workspace = normalized_workspace
    location = resolve_workspace_selector(workspace=workspace)
    scope = session_scope or _PROCESS_SESSION_SCOPE
    if not re.fullmatch(r"[0-9a-f]{32}", scope):
        raise WorkspaceError("MCP 会话工作区标识无效。")
    base = location.runtime_root.resolve(strict=True)
    sessions_root = base / ".mcp-sessions"
    sessions_root.mkdir(mode=0o700, exist_ok=True)
    sessions_root.chmod(0o700)
    resolved_sessions_root = sessions_root.resolve(strict=True)
    if not resolved_sessions_root.is_relative_to(base):
        raise WorkspaceError("会话工作区目录越出了逻辑工作区。")
    session_root = resolved_sessions_root / scope
    session_root.mkdir(mode=0o700, exist_ok=True)
    session_root.chmod(0o700)
    session_root = session_root.resolve(strict=True)
    if session_root.parent != resolved_sessions_root or not session_root.is_dir():
        raise WorkspaceError("MCP 会话工作区目录无效。")
    display_root = location.host_root / ".mcp-sessions" / scope
    if _project_root is None:
        _project_root = Path(__file__).resolve().parents[2]
    return ResearchDrawMCPRunner(
        _project_root,
        session_root,
        display_workspace_root=display_root,
        shared_workspace_root=base,
        display_shared_workspace_root=location.host_root,
    )


@mcp.tool()
def list_workspaces() -> dict:
    """List configured logical workspaces without returning filesystem paths."""
    try:
        return {"success": True, "workspaces": list_configured_workspaces()}
    except Exception as exc:
        return {"success": False, "message": str(exc), "workspaces": []}


@mcp.tool()
def get_version() -> str:
    """Get the version of Research Draw.
    
    Returns:
        Version string in the format "vX.Y.Z"
    """
    try:
        from src.version import __version__
        return f"v{__version__}"
    except Exception:
        # Fallback to reading VERSION file directly
        version_file = Path(__file__).resolve().parents[2] / "VERSION"
        if version_file.exists():
            return f"v{version_file.read_text().strip()}"
        return "v0.0.0"


@mcp.tool()
def list_plot_groups() -> dict:
    """List all available plot groups with metadata.
    
    Returns:
        Dictionary containing plot groups with their labels, descriptions, 
        order, scene description, and plot count.
    """
    groups = group_metadata()
    # Add plot count to each group
    plots_by_group = canonical_plots_by_group()
    for group_key, group_info in groups.items():
        group_info["plot_count"] = len(plots_by_group.get(group_key, []))
    return {"groups": groups}


@mcp.tool()
def list_plots(group: Optional[str] = None) -> dict:
    """List available plots, optionally filtered by group.
    
    Args:
        group: Optional group name to filter by (stats_2d, domain_2d, plots_3d, maps)
        
    Returns:
        Dictionary containing plots with their metadata including:
        - dispatch_key: Internal dispatcher key
        - group: Group the plot belongs to
        - required_fields: List of required parameter names
        - defaults: Default parameter values
        - dependency_extra: Required extra dependencies (if any)
        - demo_data: Path to demo data file (if applicable)
        - aliases: Alternative names/aliases for the plot
    """
    payload = plot_registry_payload()
    plots = payload["plots"]
    
    if group:
        # Filter plots by group
        filtered_plots = {
            name: info for name, info in plots.items() 
            if info["group"] == group
        }
        return {"plots": filtered_plots, "group": group}
    
    return {"plots": plots}


@mcp.tool()
def get_plot_schema(plot: str) -> dict:
    """Get detailed schema for a specific plot type.
    
    Args:
        plot: Plot type name (can be alias or canonical name)
        
    Returns:
        Dictionary containing detailed plot schema including:
        - name: Canonical plot name
        - group: Group the plot belongs to
        - required_fields: List of required parameter names
        - parameters: Field types, descriptions, examples, defaults, choices, ranges, and applicable modes
        - modes: Mode descriptions and mode-specific required fields
        - aliases: Alternative names for the plot
        - demo_info: Information about demo data (if available)
        - dependencies: Required extra dependencies
        - description: Human-readable description
    """
    # Normalize the plot name
    canonical_name = public_plot_name(plot)
    if not canonical_name:
        return {
            "error": f"Unknown plot type: {plot}",
            "available_plots": list(ALL_PUBLIC_PLOTS)[:20]  # Show first 20 as examples
        }
    
    # Get basic info
    registry_plot = plot_registry_payload().get("plots", {}).get(canonical_name, {})
    group = None
    for g, plots in canonical_plots_by_group().items():
        if canonical_name in plots:
            group = g
            break
    
    # Get dependencies
    dependency_extra = PLOT_DEPENDENCY_HINTS.get(canonical_name)
    
    # Get demo info
    demo_data_path = demo_data_path_for_plot(canonical_name, Path(__file__).resolve().parents[2])
    demo_info = None
    if demo_data_path and demo_data_path.exists():
        demo_info = {
            "path": str(demo_data_path),
            "exists": True
        }

    file_path_field = _MODE_REQUIRED_PATH.get(canonical_name, "file")
    file_required_fields = [] if canonical_name in _BUNDLED_MAP_ONLY_PLOTS else [file_path_field]
    required_names = set(required_fields_for_plot(canonical_name))
    required_alias_fields = {
        field
        for aliases in _PLOT_COLUMN_ALIAS_GROUPS.get(canonical_name, ())
        if any(alias in required_names for alias in aliases)
        for field in aliases
    }
    required_file_column_fields = [
        field for field in required_fields_for_plot(canonical_name)
        if field not in required_alias_fields
    ]
    required_file_groups = [
        list(group) for group in _PLOT_REQUIRED_FIELD_GROUPS.get(canonical_name, ())
    ]
    for aliases in _PLOT_COLUMN_ALIAS_GROUPS.get(canonical_name, ()):
        if any(alias in required_names for alias in aliases) and list(aliases) not in required_file_groups:
            required_file_groups.append(list(aliases))
    file_data_requirements: list[str] = []
    if canonical_name in {"embedding", "frontier"}:
        file_data_requirements.append("至少两列可用数值特征；embedding 可选 group_col 作为标签。")
    if canonical_name == "upset":
        file_data_requirements.append("至少两列布尔值或 0/1 集合列；可用 set_cols 显式指定。")
    if canonical_name == "confusion":
        file_data_requirements.append("提供 true_col 与 pred_col，或提供方形数值矩阵。")
    file_column_fields = dict(_PLOT_FILE_FIELDS.get(canonical_name, {}))
    for field in required_fields_for_plot(canonical_name):
        file_column_fields.setdefault(field, _FIELD_ROLE_BY_DEST.get(field, "categorical"))
    for aliases in _PLOT_COLUMN_ALIAS_GROUPS.get(canonical_name, ()):
        for field in aliases:
            file_column_fields.setdefault(field, _FIELD_ROLE_BY_DEST.get(field, "categorical"))
    if canonical_name in {"isosurface3d", "slice3d"}:
        file_column_fields.setdefault("value_col", "numeric")
    if canonical_name == "upset":
        file_column_fields.setdefault("set_cols", "binary")
    file_input_columns = [
        {
            "field": field,
            "role": role,
            "required": any(len(group) == 1 and group[0] == field for group in required_file_groups)
                or field in required_file_column_fields,
            "required_alternative_groups": [
                group for group in required_file_groups if len(group) > 1 and field in group
            ],
            "auto_detected": True,
        }
        for field, role in file_column_fields.items()
    ]
    parameters = _plot_parameter_schema(canonical_name)
    optional_fields = [parameter["name"] for parameter in parameters if not parameter["required"]]
    
    return {
        "name": canonical_name,
        "display_name": PLOT_DISPLAY_NAMES.get(canonical_name, canonical_name),
        "group": group,
        "required_fields": required_file_column_fields,
        "file_required_field_groups": required_file_groups,
        "file_data_requirements": file_data_requirements,
        "file_input_columns": file_input_columns,
        "custom_required_fields": list(_CUSTOM_REQUIRED_FIELDS.get(canonical_name, ())),
        "optional_fields": optional_fields,
        "parameters": parameters,
        "modes": [
            {"name": "demo", "description": "使用内置示例数据。"},
            {
                "name": "custom",
                "description": "使用调用方直接提供的数据参数。",
                "required_fields": list(_CUSTOM_REQUIRED_FIELDS.get(canonical_name, ())),
            },
            {
                "name": "file",
                "description": "使用工作区内的数据文件。",
                "required_fields": list(dict.fromkeys(
                    file_required_fields + required_file_column_fields
                )),
                "required_field_groups": required_file_groups,
                "data_requirements": file_data_requirements,
            },
        ],
        "aliases": list(registry_plot.get("aliases") or [canonical_name]),
        "demo_info": demo_info,
        "dependencies": dependency_extra,
        "description": PLOT_DESCRIPTIONS.get(canonical_name, f"{canonical_name} plot"),
        "demo_available": True,
    }


@mcp.tool()
def import_data_file(
    source_path: str,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Import a supported file from the session or shared logical workspace.

    Pass a short path relative to the logical workspace root when the client and
    MCP server share that filesystem. The server reads and copies the file
    directly, avoiding Base64 bytes in model-generated tool arguments. Paths
    remain restricted to the selected logical workspace and current session.
    workspace selects an allowlisted logical workspace; omitting it uses the configured default.
    """
    try:
        return _get_runner(workspace, _session_scope_key(ctx)).workspace.import_data_file(source_path)
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@mcp.tool()
def upload_data_file(
    filename: str,
    content_base64: str,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Upload a supported table into the selected workspace.

    workspace may be a configured logical name; omitting it selects the configured default.
    """
    try:
        runner = _get_runner(workspace, _session_scope_key(ctx))
        return runner.workspace.upload_data_file(filename, content_base64)
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@mcp.tool()
def begin_data_upload(
    filename: str,
    total_size: int,
    ctx: Context,
    chunk_size: int = DEFAULT_MODEL_UPLOAD_CHUNK_BYTES,
    workspace: Optional[str] = None,
) -> dict:
    """Start a chunked upload; the 8 KiB default keeps model tool arguments bounded."""
    try:
        return _get_runner(workspace, _session_scope_key(ctx)).workspace.begin_data_upload(
            filename, total_size, chunk_size
        )
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@mcp.tool()
def upload_data_chunk(
    upload_id: str,
    chunk_index: int,
    content_base64: str,
    ctx: Context,
    content_encoding: str = "identity",
    workspace: Optional[str] = None,
) -> dict:
    """Upload one Base64 chunk, optionally gzip-compressed, to a pending upload.

    `chunk_size` and chunk indexes count uncompressed file bytes. For model
    clients, the upload defaults to 8 KiB chunks because high-entropy data may
    not compress. Gzip each chunk independently when it reduces payload size.
    The default identity encoding remains available for existing clients.
    """
    try:
        return _get_runner(workspace, _session_scope_key(ctx)).workspace.upload_data_chunk(
            upload_id, chunk_index, content_base64, content_encoding
        )
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@mcp.tool()
def complete_data_upload(
    upload_id: str,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Assemble uploaded chunks and publish the table into the current session."""
    try:
        return _get_runner(workspace, _session_scope_key(ctx)).workspace.complete_data_upload(upload_id)
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@mcp.tool()
def cancel_data_upload(
    upload_id: str,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Discard a pending chunked upload in the current MCP session."""
    try:
        return _get_runner(workspace, _session_scope_key(ctx)).workspace.cancel_data_upload(upload_id)
    except Exception as exc:
        return {"success": False, "message": str(exc)}


@mcp.tool()
def list_workspace_files(
    ctx: Context,
    limit: int = 50,
    offset: int = 0,
    workspace: Optional[str] = None,
) -> dict:
    """List imported tabular files in the selected workspace."""
    try:
        return _get_runner(workspace, _session_scope_key(ctx)).workspace.list_data_files(limit=limit, offset=offset)
    except Exception as exc:
        return {"success": False, "message": str(exc), "items": []}


@mcp.tool()
def inspect_data_file(
    file_id: str,
    ctx: Context,
    preview_rows: int = 5,
    workspace: Optional[str] = None,
) -> dict:
    """Inspect a file_id within the selected workspace."""
    try:
        return _get_runner(workspace, _session_scope_key(ctx)).workspace.inspect_data_file(file_id, preview_rows)
    except Exception as exc:
        return {"success": False, "message": str(exc)}


def _suggest_plots_impl(
    file_id: str,
    goal: str,
    workspace: Optional[str] = None,
    session_scope: str | None = None,
) -> dict[str, Any]:
    runner = _get_runner(workspace, session_scope)
    inspection = runner.workspace.inspect_data_file(file_id, preview_rows=20)
    profile = _profile_columns(inspection)
    recommendations = _suggestions_for_profile(profile, goal)
    for recommendation in recommendations:
        recommendation["suggested_config"]["file"] = file_id

    result: dict[str, Any] = {
        "success": True,
        "file_id": file_id,
        "goal": goal,
        "analysis": profile,
        "recommendations": recommendations,
    }
    if not recommendations:
        result["message"] = "暂时无法从数据列中匹配通用图型；请指定图型，或检查文件是否包含可用的数值列。"
    return result


@mcp.tool()
def suggest_plots(
    file_id: str,
    goal: str,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Analyze a workspace table and recommend chart types and column mappings.

    Provide the user's analysis goal in Chinese or English. The response includes
    detected numeric, categorical, date, and identifier columns plus ranked chart
    recommendations with ready-to-use file-mode configs.
    """
    try:
        return _suggest_plots_impl(file_id, goal, workspace, _session_scope_key(ctx))
    except Exception as exc:
        return {"success": False, "message": str(exc), "file_id": file_id, "recommendations": []}


def _validate_plot_config_impl(
    mode: str,
    plot: str,
    config: dict,
    workspace: Optional[str] = None,
    *,
    session_scope: str | None = None,
    runner_override: ResearchDrawMCPRunner | None = None,
    inspection_override: dict[str, Any] | None = None,
) -> dict:
    """Preflight a plot request without rendering it."""
    errors: list[str] = []
    warnings: list[str] = []
    available_columns: set[str] = set()
    auto_mapping: dict[str, str] = {}
    if mode not in ("demo", "custom", "file"):
        errors.append("mode 必须是 demo、custom 或 file。")

    canonical_plot = public_plot_name(plot)
    if not canonical_plot or canonical_plot not in ALL_PUBLIC_PLOTS:
        errors.append(f"未知图型：{plot}。请先调用 list_plots。")
    if not isinstance(config, dict):
        errors.append("config 必须是键值对象。")
        config = {}

    normalized_config: dict[str, Any] = dict(config)
    if not errors:
        try:
            normalized_config = validate_cli_config_payload(build_parser(), normalized_config)
        except Exception as exc:
            errors.append(str(exc))

    runner: ResearchDrawMCPRunner | None = runner_override
    if not errors:
        try:
            runner = runner or _get_runner(workspace, session_scope)
            for path_key in ("file", "raster_file", "custom_json_file"):
                if normalized_config.get(path_key):
                    normalized_config[path_key] = str(
                        runner.workspace.resolve_workspace_file(str(normalized_config[path_key]))
                    )
            if normalized_config.get("basemap_root"):
                runner._resolve_config_paths({"basemap_root": normalized_config["basemap_root"]})
        except Exception as exc:
            errors.append(str(exc))

    if canonical_plot and canonical_plot in ALL_PUBLIC_PLOTS and mode in ("demo", "custom", "file"):
        if mode == "file":
            path_key = _MODE_REQUIRED_PATH.get(canonical_plot, "file")
            if canonical_plot in _BUNDLED_MAP_ONLY_PLOTS:
                path_key = ""
            if path_key and not normalized_config.get(path_key):
                errors.append(f"file 模式需要配置 {path_key}。")
            elif path_key and normalized_config.get(path_key) and runner:
                try:
                    input_path = Path(str(normalized_config[path_key]))
                    if input_path.suffix.lower() in ALLOWED_DATA_SUFFIXES:
                        inspection = inspection_override or runner.workspace.inspect_workspace_file(input_path)
                        available_columns = {column["name"] for column in inspection["columns"]}
                        for key in _COLUMN_CONFIG_KEYS:
                            value = normalized_config.get(key)
                            if isinstance(value, str) and value and value not in available_columns:
                                errors.append(f"{key} 指定的列“{value}”不在文件中。")
                        set_cols = normalized_config.get("set_cols")
                        if isinstance(set_cols, str) and set_cols:
                            for value in (part.strip() for part in set_cols.split(",") if part.strip()):
                                if value not in available_columns:
                                    errors.append(f"set_cols 指定的列“{value}”不在文件中。")
                        profile = _profile_columns(inspection)
                        auto_mapping = _column_mapping_for_plot(canonical_plot, profile)
                        auto_mapping = _prune_inferred_aliases(
                            canonical_plot, auto_mapping, normalized_config
                        )
                        explicit_field_keys = {
                            field for field in _COLUMN_CONFIG_KEYS.union({"set_cols"})
                            if normalized_config.get(field)
                        }
                        effective_mapping = {**auto_mapping, **{
                            field: str(normalized_config[field])
                            for field in explicit_field_keys
                        }}
                        inferred_fields = set(auto_mapping) - explicit_field_keys
                        missing_fields = _plot_mapping_missing(
                            canonical_plot,
                            effective_mapping,
                            profile,
                            require_semantic_names=True,
                            inferred_fields=inferred_fields,
                        )
                        for field in missing_fields:
                            errors.append(f"无法从数据中自动识别必需字段：{field}。")
                        inferred_for_review = {
                            field: value for field, value in auto_mapping.items()
                            if field not in explicit_field_keys
                        }
                        if inferred_for_review:
                            warnings.append(
                                "按列类型和列名推测字段映射："
                                + "; ".join(f"{field}={value}" for field, value in inferred_for_review.items())
                                + "。请确认映射符合分析意图。"
                            )
                except Exception as exc:
                    errors.append(str(exc))
        elif mode == "custom":
            required = _CUSTOM_REQUIRED_FIELDS.get(canonical_plot, ())
            missing = [field for field in required if not normalized_config.get(field)]
            if missing:
                errors.append("custom 模式缺少参数：" + ", ".join(missing))
            if canonical_plot in canonical_plots_by_group().get("domain_2d", []) or canonical_plot == "embedding3d":
                custom_data = normalized_config.get("custom_json")
                custom_file = normalized_config.get("custom_json_file")
                if not custom_data and not custom_file:
                    errors.append("该图型的 custom 模式需要 custom_json 或 custom_json_file。")
                elif custom_data:
                    try:
                        decoded = json.loads(custom_data)
                        if not isinstance(decoded, (list, dict)):
                            errors.append("custom_json 必须是对象或数组。")
                    except (TypeError, json.JSONDecodeError):
                        errors.append("custom_json 不是有效的 JSON。")
                elif custom_file:
                    try:
                        decoded = json.loads(Path(str(custom_file)).read_text(encoding="utf-8"))
                        if not isinstance(decoded, (list, dict)):
                            errors.append("custom_json_file 内容必须是对象或数组。")
                    except (OSError, json.JSONDecodeError):
                        errors.append("custom_json_file 不存在或不是有效的 JSON。")

    dependency_extra = PLOT_DEPENDENCY_HINTS.get(canonical_plot) if canonical_plot else None
    missing_modules = [
        module
        for module in _required_imports_for_plot(
            canonical_plot or "", mode, dependency_extra, normalized_config
        )
        if find_spec(module) is None
    ]
    if missing_modules:
        errors.append(
            f"缺少依赖 {', '.join(missing_modules)}；请安装 `uv sync --extra {dependency_extra}`。"
        )

    diagnostics, suggested_config = _validation_diagnostics(
        errors, warnings, available_columns, normalized_config
    )
    return {
        "valid": not errors,
        "plot": canonical_plot,
        "mode": mode,
        "errors": errors,
        "warnings": warnings,
        "diagnostics": diagnostics,
        "suggested_config": suggested_config,
        "auto_mapping": auto_mapping,
        "dependency_extra": dependency_extra,
        "normalized_config": normalized_config,
    }


@mcp.tool()
def validate_plot_config(
    mode: str,
    plot: str,
    config: dict,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Validate a plot request and return field-level errors and repair suggestions."""
    return _validate_plot_config_impl(
        mode, plot, config, workspace, session_scope=_session_scope_key(ctx)
    )


@mcp.tool()
def list_render_outputs(
    ctx: Context,
    limit: int = 50,
    offset: int = 0,
    workspace: Optional[str] = None,
) -> dict:
    """List recent rendered files in the selected workspace."""
    try:
        return _get_runner(workspace, _session_scope_key(ctx)).workspace.list_render_outputs(limit=limit, offset=offset)
    except Exception as exc:
        return {"success": False, "message": str(exc), "items": []}


def _render_plot_impl(
    mode: str,
    plot: str,
    config: dict,
    workspace: Optional[str] = None,
    session_scope: str | None = None,
    *,
    include_image: bool = True,
) -> dict:
    """Render a plot and return the result.
    
    Args:
        mode: Rendering mode - "demo" (built-in data), "custom" (parameters only), or "file" (from data file)
        plot: Plot type to render (e.g., "box", "scatter3d", "choropleth_world")
        config: Configuration parameters as key-value pairs. Keys should match CLI argument names.
               For example: {"title": "My Plot", "xlabel": "X Axis", "ylabel": "Y Axis"}
               For file mode: include "file" parameter with path to data file
               For custom mode: include data parameters like "group", "x", "y", etc.
        workspace: Optional configured logical workspace name.
                 Omit it to use the configured default. This selector is a top-level
                 argument, not a config key.
               
    Returns:
        Dictionary containing:
        - success: Boolean indicating if rendering succeeded
        - message: Status message
        - image: Base64-encoded PNG image data (if successful)
        - path: Filesystem path to the saved image (if successful)
        - plot_type: The plot type that was rendered
        - mode: The mode used for rendering
    """
    # Validate mode
    if mode not in ("demo", "custom", "file"):
        return {
            "success": False,
            "message": f"Invalid mode: {mode}. Must be 'demo', 'custom', or 'file'",
            "image": None,
            "path": None,
        }
    
    # Validate plot
    canonical_plot = public_plot_name(plot)
    if not canonical_plot or canonical_plot not in ALL_PUBLIC_PLOTS:
        return {
            "success": False,
            "message": f"Unknown plot type: {plot}. Use list_plots() to see available plots.",
            "image": None,
            "path": None,
        }

    if not isinstance(config, dict):
        return {
            "success": False,
            "message": "config 必须是键值对象。",
            "image": None,
            "path": None,
        }

    try:
        runner = _get_runner(workspace, session_scope)
    except Exception as exc:
        return {
            "success": False,
            "message": str(exc),
            "image": None,
            "path": None,
        }
    
    # Run the rendering
    success, message, output_path = runner.render_plot(mode, canonical_plot, config)
    
    if not success or output_path is None:
        return {
            "success": False,
            "message": message,
            "image": None,
            "path": None,
        }

    output_metadata = {
        "success": True,
        "message": message,
        "path": runner.workspace.public_path(output_path),
        "workspace_relative_path": runner.workspace.workspace_relative_path(output_path),
        "render_id": output_path.stem,
        "plot_type": canonical_plot,
        "mode": mode,
    }
    if not include_image:
        output_metadata["image_pending"] = True
        return output_metadata
    
    # Read the image file and return as base64
    try:
        import base64
        with open(output_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
        
        # Determine media type based on file extension
        ext = output_path.suffix.lower()
        if ext == ".png":
            media_type = "image/png"
        elif ext == ".jpg" or ext == ".jpeg":
            media_type = "image/jpeg"
        elif ext == ".svg":
            media_type = "image/svg+xml"
        elif ext == ".pdf":
            media_type = "application/pdf"
        else:
            media_type = "application/octet-stream"
        
        return {
            **output_metadata,
            "image": ImageContent(
                type="image",
                data=image_data,
                mimeType=media_type
            ),
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"Successfully rendered but failed to read output: {str(e)}",
            "image": None,
            "path": runner.workspace.public_path(output_path) if output_path else None,
        }


@mcp.tool()
async def render_plot(
    mode: str,
    plot: str,
    config: dict,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Render a plot directly for quick jobs; use start_plot_job for complex or slow renders to avoid client timeouts."""
    return await asyncio.to_thread(
        _render_plot_impl,
        mode,
        plot,
        config,
        workspace,
        _session_scope_key(ctx),
    )


@mcp.tool()
async def revise_plot(
    render_id: str,
    changes: dict,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Revise a prior render; use start_plot_job for complex or slow redraws to avoid client timeouts."""
    return await asyncio.to_thread(
        _revise_plot_impl,
        render_id,
        changes,
        workspace,
        _session_scope_key(ctx),
    )


def _revise_plot_impl(
    render_id: str,
    changes: dict,
    workspace: Optional[str],
    session_scope: str,
    *,
    include_image: bool = True,
) -> dict:
    allowed_changes = {"title", "palette", "cmap", "xlabel", "ylabel", "zlabel"}
    if not isinstance(changes, dict) or not changes:
        return {"success": False, "stage": "input", "message": "changes 必须是非空键值对象。"}
    unknown = sorted(set(changes) - allowed_changes)
    if unknown:
        return {
            "success": False,
            "stage": "input",
            "message": "目前只支持调整 title、palette、cmap、xlabel、ylabel 和 zlabel。",
            "invalid_fields": unknown,
        }
    try:
        runner = _get_runner(workspace, session_scope)
        manifest = runner.workspace.load_render_manifest(render_id)
    except Exception as exc:
        return {"success": False, "stage": "history_lookup", "message": str(exc)}

    revised_config = dict(manifest["config"])
    revised_config.update(changes)
    validation = _validate_plot_config_impl(
        manifest["mode"],
        manifest["plot"],
        revised_config,
        workspace,
        session_scope=session_scope,
        runner_override=runner,
    )
    if not validation["valid"]:
        return {
            "success": False,
            "stage": "validation",
            "source_render_id": render_id,
            "validation": validation,
        }
    result = _render_plot_impl(
        manifest["mode"],
        manifest["plot"],
        validation["normalized_config"],
        workspace,
        session_scope,
        include_image=include_image,
    )
    result["source_render_id"] = render_id
    result["applied_changes"] = changes
    if not result.get("success"):
        result["stage"] = "render"
    return result


def _create_plot_impl(
    file_id: str,
    goal: str,
    plot: Optional[str],
    config: Optional[dict],
    workspace: Optional[str],
    session_scope: str,
    *,
    include_image: bool = True,
) -> dict:
    """Recommend or use a plot, map file columns, validate, and render in one call.

    If plot is omitted, choose the highest-ranked compatible recommendation for goal.
    config can override automatically selected column names and visual parameters.
    """
    if config is None:
        config = {}
    if not isinstance(config, dict):
        return {"success": False, "stage": "input", "message": "config 必须是键值对象。"}
    forbidden = {"file", "mode", "plot", "workspace"}.intersection(config)
    if forbidden:
        return {
            "success": False,
            "stage": "input",
            "message": "file、mode、plot 和 workspace 由 create_plot 的顶层参数管理。",
            "invalid_fields": sorted(forbidden),
        }

    try:
        runner = _get_runner(workspace, session_scope)
        inspection = runner.workspace.inspect_data_file(file_id, preview_rows=20)
    except Exception as exc:
        return {"success": False, "stage": "data_inspection", "file_id": file_id, "message": str(exc)}

    profile = _profile_columns(inspection)
    recommendations = _suggestions_for_profile(profile, goal)
    for recommendation in recommendations:
        recommendation["suggested_config"]["file"] = file_id

    if plot:
        canonical_plot = public_plot_name(plot)
        if not canonical_plot or canonical_plot not in ALL_PUBLIC_PLOTS:
            return {
                "success": False,
                "stage": "plot_selection",
                "message": f"未知图型：{plot}。请先调用 list_plots。",
                "analysis": profile,
            }
    elif recommendations:
        canonical_plot = recommendations[0]["plot"]
    else:
        return {
            "success": False,
            "stage": "plot_selection",
            "message": "无法根据当前列自动选择通用图型；请指定 plot 和必要的列映射。",
            "analysis": profile,
            "recommendations": [],
        }

    field_mapping = _prune_inferred_aliases(
        canonical_plot,
        _column_mapping_for_plot(canonical_plot, profile),
        config,
    )
    plot_config = default_args_for_plot(canonical_plot)
    plot_config.update(field_mapping)
    plot_config.update(config)
    plot_config["file"] = file_id

    final_field_mapping = {
        field: str(value)
        for field, value in plot_config.items()
        if field in _COLUMN_CONFIG_KEYS.union({"set_cols"}) and value
    }
    missing_fields = _plot_mapping_missing(canonical_plot, final_field_mapping, profile)
    if missing_fields:
        diagnostics: list[dict[str, Any]] = []
        for missing in missing_fields:
            candidate_fields = [
                field.strip()
                for field in re.split(r"\s+或\s+", missing)
                if field.strip() in _COLUMN_CONFIG_KEYS
            ]
            candidate_columns: list[str] = []
            for field in candidate_fields:
                role = _PLOT_FILE_FIELDS.get(canonical_plot, {}).get(
                    field, _FIELD_ROLE_BY_DEST.get(field, "categorical")
                )
                if role == "datetime_or_categorical":
                    roles = {"datetime", "categorical", "numeric"}
                elif role == "binary":
                    candidate_columns.extend(
                        column["name"] for column in profile["columns"] if column.get("binary")
                    )
                    continue
                else:
                    roles = {role}
                candidate_columns.extend(
                    column["name"] for column in profile["columns"]
                    if column.get("role") in roles
                )
            if not candidate_columns and "数值" in missing:
                candidate_columns = list(profile.get("numeric_columns", []))
            if canonical_plot == "confusion" and not candidate_columns:
                candidate_columns = list(dict.fromkeys(
                    profile.get("categorical_columns", []) + profile.get("numeric_columns", [])
                ))
            diagnostics.append({
                "severity": "error",
                "code": "required_field_unmapped",
                "field": missing,
                "message": f"无法从当前数据中确定：{missing}。",
                "suggestion": "根据 get_plot_schema 的字段说明，在 config 中填写对应数据列名。",
                "candidate_columns": list(dict.fromkeys(candidate_columns)),
            })
        return {
            "success": False,
            "stage": "field_mapping",
            "plot": canonical_plot,
            "message": "无法从表格中确定所有必需字段；请提供缺少字段的列名。",
            "missing_fields": missing_fields,
            "field_mapping": final_field_mapping,
            "diagnostics": diagnostics,
            "suggested_config": {"file": file_id, **field_mapping, **config},
            "analysis": profile,
            "recommendations": recommendations,
        }

    validation = _validate_plot_config_impl(
        "file",
        canonical_plot,
        plot_config,
        workspace,
        session_scope=session_scope,
        runner_override=runner,
        inspection_override=inspection,
    )
    if not validation["valid"]:
        return {
            "success": False,
            "stage": "validation",
            "plot": canonical_plot,
            "field_mapping": field_mapping,
            "analysis": profile,
            "validation": validation,
            "recommendations": recommendations,
        }

    result = _render_plot_impl(
        "file",
        canonical_plot,
        validation["normalized_config"],
        workspace,
        session_scope,
        include_image=include_image,
    )
    data_warnings = _data_quality_warnings(profile, final_field_mapping)
    inferred_field_names = set(field_mapping) - set(config)
    if inferred_field_names:
        data_warnings.append("部分列映射由列名和数据类型推断，请核对返回的 field_mapping。")
    data_warnings.extend(validation["warnings"])
    result.update({
        "file_id": file_id,
        "goal": goal,
        "field_mapping": {
            field: validation["normalized_config"].get(field)
            for field in _COLUMN_CONFIG_KEYS.union({"set_cols"})
            if validation["normalized_config"].get(field)
        },
        "data_warnings": list(dict.fromkeys(data_warnings)),
        "diagnostics": validation["diagnostics"],
        "recommendations": recommendations,
        "analysis": profile,
    })
    if not result.get("success"):
        result["stage"] = "render"
    return result


@mcp.tool()
async def create_plot(
    file_id: str,
    goal: str,
    ctx: Context,
    plot: Optional[str] = None,
    config: Optional[dict] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Map, validate, and render one file plot; use start_plot_job for complex or slow plots to avoid client timeouts."""
    return await asyncio.to_thread(
        _create_plot_impl,
        file_id,
        goal,
        plot,
        config,
        workspace,
        _session_scope_key(ctx),
    )


def _create_plots_impl(
    file_id: str,
    goal: str,
    plots: list[str],
    config: Optional[dict],
    plot_configs: Optional[dict],
    workspace: Optional[str],
    session_scope: str,
    *,
    include_image: bool = True,
) -> dict:
    """Render several chart types from one data file after a single inspection.

    `plots` lists chart names. `config` supplies shared style overrides and
    `plot_configs` optionally maps a chart name to chart-specific overrides.
    """
    if not isinstance(plots, list) or not plots:
        return {"success": False, "stage": "input", "message": "plots 必须是非空图型名称列表。"}
    if len(plots) > 12:
        return {"success": False, "stage": "input", "message": "一次最多批量绘制 12 种图型。"}
    shared_config = {} if config is None else config
    per_plot_config = {} if plot_configs is None else plot_configs
    if not isinstance(shared_config, dict) or not isinstance(per_plot_config, dict):
        return {"success": False, "stage": "input", "message": "config 和 plot_configs 必须是键值对象。"}
    forbidden = {"file", "mode", "plot", "workspace"}.intersection(shared_config)
    if forbidden:
        return {
            "success": False,
            "stage": "input",
            "message": "file、mode、plot 和 workspace 由 create_plots 的顶层参数管理。",
            "invalid_fields": sorted(forbidden),
        }
    allowed_plot_config_keys = {
        str(requested) for requested in plots
    } | {
        canonical
        for requested in plots
        if (canonical := public_plot_name(str(requested)))
    }
    unknown_plot_config_keys = sorted(set(per_plot_config) - allowed_plot_config_keys)
    if unknown_plot_config_keys:
        return {
            "success": False,
            "stage": "input",
            "message": "plot_configs 中包含不在 plots 列表中的图型名称。",
            "invalid_plot_config_keys": unknown_plot_config_keys,
        }

    try:
        runner = _get_runner(workspace, session_scope)
        inspection = runner.workspace.inspect_data_file(file_id, preview_rows=20)
    except Exception as exc:
        return {"success": False, "stage": "data_inspection", "file_id": file_id, "message": str(exc)}

    profile = _profile_columns(inspection)
    recommendations = _suggestions_for_profile(profile, goal)
    recommendation_names = {item["plot"] for item in recommendations}
    results: list[dict[str, Any]] = []
    seen: set[str] = set()
    for requested_plot in plots:
        canonical_plot = public_plot_name(str(requested_plot))
        if not canonical_plot or canonical_plot not in ALL_PUBLIC_PLOTS:
            results.append({
                "success": False,
                "plot": requested_plot,
                "stage": "plot_selection",
                "message": f"未知图型：{requested_plot}。请先调用 list_plots。",
            })
            continue
        if canonical_plot in seen:
            results.append({
                "success": False,
                "plot": canonical_plot,
                "stage": "input",
                "message": "批量列表中存在重复图型。",
            })
            continue
        seen.add(canonical_plot)

        plot_override = per_plot_config.get(canonical_plot, per_plot_config.get(str(requested_plot), {}))
        if not isinstance(plot_override, dict):
            results.append({
                "success": False,
                "plot": canonical_plot,
                "stage": "input",
                "message": "该图型对应的 plot_configs 值必须是键值对象。",
            })
            continue
        forbidden_plot = {"file", "mode", "plot", "workspace"}.intersection(plot_override)
        if forbidden_plot:
            results.append({
                "success": False,
                "plot": canonical_plot,
                "stage": "input",
                "message": "plot_configs 中不能覆盖 file、mode、plot 或 workspace。",
                "invalid_fields": sorted(forbidden_plot),
            })
            continue

        overrides = {**shared_config, **plot_override}
        mapping = _prune_inferred_aliases(
            canonical_plot,
            _column_mapping_for_plot(canonical_plot, profile),
            overrides,
        )
        plot_config = default_args_for_plot(canonical_plot)
        plot_config.update(mapping)
        plot_config.update(overrides)
        plot_config["file"] = file_id
        validation = _validate_plot_config_impl(
            "file",
            canonical_plot,
            plot_config,
            workspace,
            session_scope=session_scope,
            runner_override=runner,
            inspection_override=inspection,
        )
        if not validation["valid"]:
            results.append({
                "success": False,
                "stage": "validation",
                "plot": canonical_plot,
                "display_name": PLOT_DISPLAY_NAMES.get(canonical_plot, canonical_plot),
                "field_mapping": mapping,
                "validation": validation,
            })
            continue

        rendered = _render_plot_impl(
            "file",
            canonical_plot,
            validation["normalized_config"],
            workspace,
            session_scope,
            include_image=include_image,
        )
        field_mapping = {
            field: validation["normalized_config"].get(field)
            for field in _COLUMN_CONFIG_KEYS.union({"set_cols"})
            if validation["normalized_config"].get(field)
        }
        warnings = _data_quality_warnings(profile, field_mapping)
        if set(mapping) - set(overrides):
            warnings.append("部分列映射由列名和数据类型推断，请核对返回的 field_mapping。")
        warnings.extend(validation["warnings"])
        rendered.update({
            "plot": canonical_plot,
            "display_name": PLOT_DISPLAY_NAMES.get(canonical_plot, canonical_plot),
            "field_mapping": field_mapping,
            "data_warnings": list(dict.fromkeys(warnings)),
            "diagnostics": validation["diagnostics"],
            "recommended_for_goal": canonical_plot in recommendation_names,
        })
        results.append(rendered)

    success_count = sum(bool(item.get("success")) for item in results)
    return {
        "success": success_count > 0,
        "partial_failure": 0 < success_count < len(results),
        "file_id": file_id,
        "goal": goal,
        "analysis": profile,
        "recommendations": recommendations,
        "result_count": len(results),
        "success_count": success_count,
        "results": results,
    }


@mcp.tool()
async def create_plots(
    file_id: str,
    goal: str,
    plots: list[str],
    ctx: Context,
    config: Optional[dict] = None,
    plot_configs: Optional[dict] = None,
    workspace: Optional[str] = None,
) -> dict:
    """Render several chart types; submit through start_plot_job for batch rendering to avoid client timeouts."""
    return await asyncio.to_thread(
        _create_plots_impl,
        file_id,
        goal,
        plots,
        config,
        plot_configs,
        workspace,
        _session_scope_key(ctx),
    )


def _plot_job_worker(
    operation: str,
    payload: dict[str, Any],
    session_scope: str,
) -> dict[str, Any]:
    workspace = payload.get("workspace")
    if operation == "render_plot":
        return _render_plot_impl(
            payload["mode"],
            payload["plot"],
            payload["config"],
            workspace,
            session_scope,
            include_image=False,
        )
    if operation == "create_plot":
        return _create_plot_impl(
            payload["file_id"],
            payload["goal"],
            payload.get("plot"),
            payload.get("config"),
            workspace,
            session_scope,
            include_image=False,
        )
    if operation == "create_plots":
        return _create_plots_impl(
            payload["file_id"],
            payload["goal"],
            payload["plots"],
            payload.get("config"),
            payload.get("plot_configs"),
            workspace,
            session_scope,
            include_image=False,
        )
    if operation == "revise_plot":
        return _revise_plot_impl(
            payload["render_id"],
            payload["changes"],
            workspace,
            session_scope,
            include_image=False,
        )
    return {
        "success": False,
        "stage": "input",
        "message": f"不支持的绘图任务类型：{operation}。",
    }


def _job_render_ids(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        render_id = value.get("render_id")
        if render_id and value.get("success"):
            found.append(str(render_id))
        for child in value.values():
            found.extend(_job_render_ids(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_job_render_ids(child))
    return list(dict.fromkeys(found))


def _restore_job_images(value: Any, runner: ResearchDrawMCPRunner) -> Any:
    if isinstance(value, list):
        return [_restore_job_images(item, runner) for item in value]
    if not isinstance(value, dict):
        return value

    restored = {
        key: _restore_job_images(child, runner)
        for key, child in value.items()
        if key != "image_pending"
    }
    if not value.get("image_pending"):
        return restored

    relative_path = value.get("workspace_relative_path")
    try:
        if not relative_path:
            raise WorkspaceError("任务结果缺少工作区相对路径。")
        image_path = runner.workspace.resolve_workspace_file(str(relative_path))
        if image_path.suffix.lower() not in ALLOWED_RENDER_SUFFIXES:
            raise WorkspaceError("任务结果文件格式无效。")
        media_type = {
            ".png": "image/png",
            ".svg": "image/svg+xml",
            ".pdf": "application/pdf",
        }[image_path.suffix.lower()]
        image_data = base64.b64encode(image_path.read_bytes()).decode("ascii")
        restored["image"] = ImageContent(
            type="image",
            data=image_data,
            mimeType=media_type,
        )
    except Exception as exc:
        restored["image_error"] = str(exc)
    return restored


def _separate_job_images(value: Any) -> tuple[Any, list[ImageContent]]:
    """Keep image bytes in MCP image blocks instead of JSON-encoding Base64."""
    images: list[ImageContent] = []

    def visit(item: Any) -> Any:
        if isinstance(item, list):
            return [visit(child) for child in item]
        if not isinstance(item, dict):
            return item

        metadata: dict[str, Any] = {}
        for key, child in item.items():
            if key == "image" and isinstance(child, ImageContent):
                images.append(child)
            else:
                metadata[key] = visit(child)
        return metadata

    return visit(value), images


def _job_result_response(
    response: dict[str, Any], images: Optional[list[ImageContent]] = None
) -> CallToolResult:
    """Return compact structured metadata and separately typed image blocks."""
    return CallToolResult(
        content=[
            TextContent(
                type="text",
                text=json.dumps(response, ensure_ascii=False, default=str),
            ),
            *(images or []),
        ],
        structuredContent=response,
    )


def _normalize_tool_choice(value: Optional[str]) -> Optional[str]:
    """Trim accidental quote wrappers emitted by some MCP clients/models."""
    if value is None:
        return None
    normalized = str(value).strip()
    # A malformed but observed call encoded enum values as the literal string
    # '"demo"'. Strip surrounding quote characters before validation.
    return normalized.strip("\"'` ").strip() or None


def _submit_plot_job(
    operation: str,
    request_id: str,
    request_payload: dict[str, Any],
    ctx: Context,
    workspace: Optional[str],
) -> dict:
    session_scope = _session_scope_key(ctx)
    normalized_workspace = (
        None if workspace is None or str(workspace).strip().lower() in {"", "null", "none", "undefined"}
        else str(workspace).strip()
    )
    selected_workspace = normalized_workspace or os.getenv(DEFAULT_WORKSPACE_ENV, "").strip() or None
    try:
        runner = _get_runner(selected_workspace, session_scope)
        request_payload["workspace"] = selected_workspace
        record, reused = render_job_store.submit(
            runner.workspace,
            session_scope,
            request_id,
            operation,
            request_payload,
            lambda: _plot_job_worker(operation, request_payload, session_scope),
        )
    except Exception as exc:
        return {"success": False, "stage": "submit", "message": str(exc)}

    return {
        "success": True,
        "job_id": record["job_id"],
        "request_id": record["request_id"],
        "operation": record["operation"],
        "state": record["state"],
        "reused": reused,
        "status_tool": "get_plot_job_status",
        "result_tool": "get_plot_job_result",
        "poll_after_seconds": 3,
    }


@mcp.tool()
def start_render_job(
    request_id: str,
    mode: Literal["demo", "custom", "file"],
    plot: str,
    config: dict,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Start an asynchronous direct render with all render arguments required.

    Use this for complex or slow plots to avoid client-side tool timeouts. Pass config
    as a top-level JSON object alongside mode and plot. Poll get_plot_job_status, then
    call get_plot_job_result to retrieve metadata and the typed image block. Reuse the
    same request_id and identical arguments after a transport timeout.
    """
    normalized_mode = _normalize_tool_choice(mode)
    normalized_plot = _normalize_tool_choice(plot)
    if normalized_mode not in {"demo", "custom", "file"}:
        return {
            "success": False,
            "stage": "input",
            "missing_fields": ["mode"],
            "message": "mode 必须是 demo、custom 或 file。",
        }
    if not normalized_plot:
        return {"success": False, "stage": "input", "missing_fields": ["plot"], "message": "plot 不能为空。"}
    if not isinstance(config, dict):
        return {"success": False, "stage": "input", "message": "config 必须是顶层键值对象。"}

    return _submit_plot_job(
        "render_plot",
        request_id,
        {"mode": normalized_mode, "plot": normalized_plot, "config": config},
        ctx,
        workspace,
    )


@mcp.tool()
def start_plot_job(
    operation: Literal["render_plot", "create_plot", "create_plots", "revise_plot"],
    request_id: str,
    ctx: Context,
    workspace: Optional[str] = None,
    mode: Optional[str] = None,
    plot: Optional[str] = None,
    config: Optional[dict] = None,
    file_id: Optional[str] = None,
    goal: Optional[str] = None,
    plots: Optional[list[str]] = None,
    plot_configs: Optional[dict] = None,
    render_id: Optional[str] = None,
    changes: Optional[dict] = None,
) -> dict:
    """Submit a render job and return quickly; use for complex, slow, or batch work to prevent MCP call timeouts.

    Poll get_plot_job_status, then fetch the completed image with get_plot_job_result.
    Reuse the exact request_id and parameters after a transport timeout to avoid duplicate renders.
    For operation=render_plot, pass mode, plot, and config as top-level arguments (not inside config).
    mode must be demo, custom, or file; pass mode and plot as plain strings without quote characters.
    create_plot needs file_id/goal; create_plots needs file_id/goal/plots; revise_plot needs render_id/changes.
    The selected workspace must be reused for later status/result calls.
    """
    if operation not in {"render_plot", "create_plot", "create_plots", "revise_plot"}:
        return {"success": False, "stage": "input", "message": "operation 无效。"}
    if operation == "render_plot":
        mode = _normalize_tool_choice(mode)
        plot = _normalize_tool_choice(plot)
        missing_fields = []
        if mode not in {"demo", "custom", "file"}:
            missing_fields.append("mode")
        if not plot:
            missing_fields.append("plot")
        if missing_fields:
            return {
                "success": False,
                "stage": "input",
                "missing_fields": missing_fields,
                "message": "render_plot 任务需要 mode（demo/custom/file）和 plot。",
            }
        if config is None or not isinstance(config, dict):
            return {"success": False, "stage": "input", "message": "render_plot 任务需要 config 键值对象。"}
        request_payload: dict[str, Any] = {
            "mode": mode,
            "plot": plot,
            "config": config,
        }
    elif operation == "create_plot":
        if not file_id or not goal:
            return {
                "success": False,
                "stage": "input",
                "message": "create_plot 任务需要 file_id 和 goal。",
            }
        if config is not None and not isinstance(config, dict):
            return {"success": False, "stage": "input", "message": "config 必须是键值对象。"}
        request_payload = {
            "file_id": file_id,
            "goal": goal,
            "plot": plot,
            "config": config or {},
        }
    elif operation == "create_plots":
        if not file_id or not goal or not isinstance(plots, list) or not plots:
            return {
                "success": False,
                "stage": "input",
                "message": "create_plots 任务需要 file_id、goal 和非空 plots 列表。",
            }
        if len(plots) > 12:
            return {"success": False, "stage": "input", "message": "一次最多批量绘制 12 种图型。"}
        if config is not None and not isinstance(config, dict):
            return {"success": False, "stage": "input", "message": "config 必须是键值对象。"}
        if plot_configs is not None and not isinstance(plot_configs, dict):
            return {"success": False, "stage": "input", "message": "plot_configs 必须是键值对象。"}
        request_payload = {
            "file_id": file_id,
            "goal": goal,
            "plots": plots,
            "config": config or {},
            "plot_configs": plot_configs or {},
        }
    else:
        if not render_id or not isinstance(changes, dict) or not changes:
            return {
                "success": False,
                "stage": "input",
                "message": "revise_plot 任务需要 render_id 和非空 changes 对象。",
            }
        request_payload = {"render_id": render_id, "changes": changes}

    return _submit_plot_job(operation, request_id, request_payload, ctx, workspace)


def _load_plot_job(job_id: str, workspace: Optional[str]) -> tuple[dict[str, Any], ResearchDrawMCPRunner]:
    session_scope = session_scope_from_job_id(job_id)
    runner = _get_runner(workspace, session_scope)
    record = render_job_store.load(runner.workspace, job_id)
    if record is None:
        raise WorkspaceError("绘图任务不存在，可能已超过 7 天保留期，或工作区选择错误。")
    if record["state"] == "queued":
        payload = record["payload"]
        render_job_store.schedule(
            runner.workspace,
            job_id,
            lambda: _plot_job_worker(record["operation"], payload, session_scope),
        )
        record = render_job_store.load(runner.workspace, job_id) or record
    return record, runner


@mcp.tool()
def get_plot_job_status(
    job_id: str,
    ctx: Context,
    workspace: Optional[str] = None,
) -> dict:
    """Return a small queued/running/completed status; poll again after poll_after_seconds while pending."""
    try:
        record, _ = _load_plot_job(job_id, workspace)
    except Exception as exc:
        return {"success": False, "stage": "job_lookup", "job_id": job_id, "message": str(exc)}

    now = record["finished_at"] or time.time()
    created = record["created_at"]
    response = {
        "success": True,
        "job_id": record["job_id"],
        "operation": record["operation"],
        "state": record["state"],
        "stage": record["stage"],
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
        "elapsed_seconds": round(max(0.0, now - created), 2),
        "error": record["error"],
    }
    if record["state"] in {"queued", "running"}:
        response["poll_after_seconds"] = 3
    result = record.get("result")
    if isinstance(result, dict):
        response["result_summary"] = {
            "success": bool(result.get("success")),
            "message": result.get("message"),
            "render_ids": _job_render_ids(result),
            "success_count": result.get("success_count"),
            "result_count": result.get("result_count"),
        }
    return response


@mcp.tool()
def get_plot_job_result(
    job_id: str,
    ctx: Context,
    workspace: Optional[str] = None,
) -> CallToolResult:
    """Fetch completed metadata and a typed MCP image block; safe to retry if image transfer times out."""
    try:
        record, runner = _load_plot_job(job_id, workspace)
    except Exception as exc:
        return _job_result_response(
            {"success": False, "stage": "job_lookup", "job_id": job_id, "message": str(exc)}
        )

    if record["state"] in {"queued", "running"}:
        return _job_result_response({
            "success": False,
            "stage": "job_not_complete",
            "job_id": job_id,
            "state": record["state"],
            "message": "绘图任务仍在运行；请稍后调用 get_plot_job_status。",
        })
    result = record.get("result")
    if not isinstance(result, dict):
        return _job_result_response(
            {"success": False, "stage": "job_result", "job_id": job_id, "message": "任务结果记录缺失。"}
        )
    if record["state"] == "succeeded":
        result = _restore_job_images(result, runner)
    response = {
        "success": bool(result.get("success")),
        "job_id": job_id,
        "state": record["state"],
        "result": result,
    }
    metadata, images = _separate_job_images(response)
    return _job_result_response(metadata, images)


# 为了向后兼容和直接运行的支持
def main():
    """Start local stdio mode or authenticated remote Streamable HTTP mode."""
    transport = os.getenv("RESEARCH_DRAW_MCP_TRANSPORT", "stdio").strip().lower()
    if transport == "stdio":
        mcp.run()
        return
    if transport != "streamable-http":
        raise SystemExit("RESEARCH_DRAW_MCP_TRANSPORT must be 'stdio' or 'streamable-http'.")

    token_path = os.getenv("RESEARCH_DRAW_MCP_TOKEN_FILE", "").strip()
    if not token_path:
        raise SystemExit("RESEARCH_DRAW_MCP_TOKEN_FILE is required for Streamable HTTP mode.")
    try:
        token = Path(token_path).read_bytes().strip()
    except OSError as exc:
        raise SystemExit(f"Cannot read MCP bearer token file: {token_path}") from exc
    if len(token) < 32 or any(byte < 33 or byte > 126 for byte in token):
        raise SystemExit("MCP bearer token must contain at least 32 visible ASCII characters.")

    def csv_setting(name: str, default: list[str]) -> list[str]:
        raw = os.getenv(name, "")
        values = [value.strip() for value in raw.split(",") if value.strip()]
        return values or default

    allowed_hosts = csv_setting(
        "RESEARCH_DRAW_MCP_ALLOWED_HOSTS", ["localhost:*", "127.0.0.1:*"]
    )
    allowed_origins = csv_setting("RESEARCH_DRAW_MCP_ALLOWED_ORIGINS", [])
    security = TransportSecuritySettings(
        allowed_hosts=allowed_hosts,
        allowed_origins=allowed_origins,
    )

    try:
        port = int(os.getenv("RESEARCH_DRAW_MCP_PORT", "8000"))
    except ValueError as exc:
        raise SystemExit("RESEARCH_DRAW_MCP_PORT must be an integer.") from exc
    if not 1 <= port <= 65535:
        raise SystemExit("RESEARCH_DRAW_MCP_PORT must be between 1 and 65535.")
    try:
        max_request_body_mb = max(
            1, min(256, int(os.getenv("RESEARCH_DRAW_MCP_MAX_REQUEST_BODY_MB", "48")))
        )
    except ValueError:
        max_request_body_mb = 48

    import uvicorn

    # FastMCP keeps HTTP transport options on its settings object; the pinned
    # SDK's streamable_http_app() factory does not accept keyword arguments.
    mcp.settings.host = "0.0.0.0"
    mcp.settings.port = port
    # Stateful HTTP sessions are required for per-MCP-session workspace isolation.
    mcp.settings.stateless_http = False
    mcp.settings.max_request_body_size = max_request_body_mb * 1024 * 1024
    mcp.settings.transport_security = security
    app = mcp.streamable_http_app()
    protected_app = BearerTokenAuthMiddleware(app, token)
    uvicorn.run(
        protected_app,
        host="0.0.0.0",
        port=port,
        log_level=os.getenv("RESEARCH_DRAW_MCP_LOG_LEVEL", "info"),
    )


if __name__ == "__main__":
    main()
