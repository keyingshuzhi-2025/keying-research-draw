from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Optional


GROUP_META: Dict[str, Dict[str, Any]] = {
    "stats_2d": {
        "label": "统计二维",
        "order": 10,
        "description": "通用统计分析图型，适用于实验比较与相关分析。",
        "scene": "实验组比较、差异分析、相关性分析",
    },
    "domain_2d": {
        "label": "学科二维",
        "order": 20,
        "description": "生物、临床、材料、遥感、金融、心理等领域科研图型。",
        "scene": "生信分析、临床评估、材料表征、遥感与金融时序",
    },
    "plots_3d": {
        "label": "三维图型",
        "order": 30,
        "description": "科研常用三维可视化图型，支持轨迹、曲面、向量场等。",
        "scene": "三维结构展示、体数据分析、向量场分析",
    },
    "maps": {
        "label": "地理地图",
        "order": 40,
        "description": "离线地图绘图，支持底图、分级着色、栅格与点位叠加。",
        "scene": "全球/中国空间分布、区域分级、点位与栅格叠加",
    },
}


PLOT_GROUPS: Dict[str, List[str]] = {
    "stats_2d": [
        "box",
        "violin",
        "scatter",
        "bar",
        "column",
        "line",
        "histogram",
        "area",
        "volcano",
        "forest",
    ],
    "domain_2d": [
        "ma",
        "enrich_dot",
        "gsea",
        "embedding",
        "upset",
        "km",
        "roc",
        "calibration",
        "bland_altman",
        "dca",
        "stress_strain",
        "xrd",
        "raman",
        "phase",
        "hysteresis",
        "spectral_signature",
        "index_ts",
        "confusion",
        "class_dist",
        "candlestick",
        "cum_return",
        "rolling_stats",
        "frontier",
        "acf_pacf",
        "likert",
        "raincloud",
        "irt_icc",
        "factor_loadings",
        "interaction",
    ],
    "plots_3d": [
        "scatter3d",
        "surface3d",
        "wireframe3d",
        "contour3d",
        "line3d",
        "isosurface3d",
        "slice3d",
        "quiver3d",
        "waterfall3d",
        "embedding3d",
        "mesh3d",
    ],
    "maps": ["world", "world_admin1", "china", "choropleth_world", "choropleth_china", "raster", "points"],
}


PLOT_DISPLAY_NAMES: Dict[str, str] = {
    "box": "箱线图",
    "violin": "小提琴图",
    "scatter": "散点回归图",
    "bar": "横向条形图",
    "column": "纵向柱状图",
    "line": "折线图",
    "histogram": "直方图",
    "area": "面积图",
    "volcano": "火山图",
    "forest": "森林图",
    "ma": "MA 均值-差异图",
    "enrich_dot": "富集气泡图",
    "gsea": "GSEA 富集曲线",
    "embedding": "降维散点图（PCA/UMAP）",
    "upset": "UpSet 集合交集图",
    "km": "Kaplan–Meier 生存曲线",
    "roc": "ROC/PR 评估曲线",
    "calibration": "概率校准曲线",
    "bland_altman": "Bland–Altman 一致性图",
    "dca": "决策曲线分析图",
    "stress_strain": "应力-应变曲线",
    "xrd": "X 射线衍射图（XRD）",
    "raman": "拉曼/红外光谱图",
    "phase": "材料相图",
    "hysteresis": "磁滞/滞回曲线",
    "spectral_signature": "遥感光谱特征曲线",
    "index_ts": "遥感指数时序图",
    "confusion": "分类混淆矩阵",
    "class_dist": "地物类别分布图",
    "candlestick": "金融 K 线图",
    "cum_return": "累计收益与回撤图",
    "rolling_stats": "滚动统计图",
    "frontier": "投资组合有效前沿图",
    "acf_pacf": "自相关/偏自相关图",
    "likert": "Likert 量表分布图",
    "raincloud": "雨云分布图",
    "irt_icc": "IRT 项目特征曲线（ICC）",
    "factor_loadings": "因子载荷图",
    "interaction": "交互效应图",
    "scatter3d": "三维散点图",
    "surface3d": "三维曲面图",
    "wireframe3d": "三维线框图",
    "contour3d": "三维等高线图",
    "line3d": "三维轨迹图",
    "isosurface3d": "三维等值面图",
    "slice3d": "三维正交切片图",
    "quiver3d": "三维矢量场图",
    "waterfall3d": "三维瀑布图",
    "embedding3d": "三维降维图",
    "mesh3d": "三维网格图",
    "world": "世界底图",
    "world_admin1": "世界一级行政区图",
    "china": "中国行政区底图",
    "choropleth_world": "世界分级设色地图",
    "choropleth_china": "中国分级设色地图",
    "raster": "栅格影像叠加图",
    "points": "地图点位分布图",
}

PLOT_DESCRIPTIONS: Dict[str, str] = {
    "box": "比较多组数据的中位数、四分位范围和离群点。",
    "violin": "比较多组数据的分布形状与概率密度。",
    "scatter": "查看两个数值变量的关系，并显示线性拟合。",
    "bar": "横向比较分类数值，适合类别名称较长的情况。",
    "column": "纵向比较不同类别或分组的数值。",
    "line": "展示数值随时间、顺序或类别的变化趋势。",
    "histogram": "查看连续数值的频数或概率密度分布。",
    "area": "突出展示数值随时间或顺序的变化，可堆叠分组。",
    "volcano": "同时展示变化幅度与显著性，常用于差异分析。",
    "forest": "汇总多个研究或指标的效应量及置信区间。",
    "ma": "展示平均表达量与倍数变化的关系。",
    "enrich_dot": "用气泡大小和颜色概览通路富集结果。",
    "gsea": "展示排序列表上的运行富集分数和命中位置。",
    "embedding": "将高维样本投影到二维空间并按类别着色。",
    "upset": "展示多个集合的交集及其规模。",
    "km": "展示生存概率随时间变化及组间差异。",
    "roc": "评估分类模型的 ROC 或精确率-召回率表现。",
    "calibration": "比较预测概率与实际发生率的一致程度。",
    "bland_altman": "评估两种测量方法之间的一致性和偏差。",
    "dca": "比较不同阈值下模型或策略的临床净获益。",
    "stress_strain": "展示材料应力与应变关系及关键力学区间。",
    "xrd": "展示衍射角与强度，用于材料物相分析。",
    "raman": "展示波数或波长与光谱强度。",
    "phase": "展示材料状态随温度、成分等变量的变化。",
    "hysteresis": "展示加载与卸载过程形成的滞回关系。",
    "spectral_signature": "比较不同地物类别的光谱响应特征。",
    "index_ts": "展示 NDVI 等遥感指数的时间变化。",
    "confusion": "展示分类预测与真实类别的对应数量或比例。",
    "class_dist": "比较不同地物类别的样本量或面积。",
    "candlestick": "展示金融资产开盘、收盘、最高和最低价格。",
    "cum_return": "展示累计收益及回撤变化。",
    "rolling_stats": "展示收益序列的滚动均值和波动情况。",
    "frontier": "展示风险与预期收益之间的投资组合前沿。",
    "acf_pacf": "检查时间序列在不同滞后阶数上的相关性。",
    "likert": "比较量表各选项在不同题目或组别中的占比。",
    "raincloud": "同时展示分布密度、散点和统计摘要。",
    "irt_icc": "展示项目反应理论中能力值与作答概率的关系。",
    "factor_loadings": "展示变量在潜在因子上的载荷大小和方向。",
    "interaction": "展示两个预测变量对结果的联合影响。",
    "scatter3d": "在三维坐标中展示观测点的位置。",
    "surface3d": "展示两个自变量与连续响应值构成的曲面。",
    "wireframe3d": "以网格线呈现三维曲面结构。",
    "contour3d": "在三维坐标中展示连续变量的等值线。",
    "line3d": "展示三维空间中的轨迹或路径。",
    "isosurface3d": "从体数据中提取指定数值的三维等值面。",
    "slice3d": "查看三维体数据在多个正交切面上的分布。",
    "quiver3d": "展示三维空间中的向量方向和大小。",
    "waterfall3d": "沿一个维度排列多条三维曲线以比较变化。",
    "embedding3d": "将高维样本投影到三维空间并按类别着色。",
    "mesh3d": "展示三维表面或体数据的网格结构。",
    "world": "显示世界行政区底图，可叠加高亮和名称。",
    "world_admin1": "显示世界各国一级行政区边界。",
    "china": "显示中国行政区底图并按层级绘制。",
    "choropleth_world": "按指标数值对世界区域进行分级着色。",
    "choropleth_china": "按指标数值对中国省级区域进行分级着色。",
    "raster": "将栅格影像与离线行政区底图叠加显示。",
    "points": "在离线底图上展示经纬度点位及其属性。",
}


PUBLIC_TO_DISPATCH: Dict[str, str] = {
    "scatter3d": "plot3d_scatter",
    "surface3d": "plot3d_surface",
    "wireframe3d": "plot3d_wireframe",
    "contour3d": "plot3d_contour",
    "line3d": "plot3d_line",
    "isosurface3d": "plot3d_isosurface",
    "slice3d": "plot3d_slice",
    "quiver3d": "plot3d_quiver",
    "waterfall3d": "plot3d_waterfall",
    "embedding3d": "plot3d_embedding",
    "mesh3d": "plot3d_mesh",
    "world": "map_world",
    "world_admin1": "map_world_admin1",
    "china": "map_china",
    "choropleth_world": "map_choropleth_world",
    "choropleth_china": "map_choropleth_china",
    "raster": "map_raster",
    "points": "map_points",
}


ALL_PUBLIC_PLOTS: List[str] = [name for group in PLOT_GROUPS.values() for name in group]
for _plot in ALL_PUBLIC_PLOTS:
    PUBLIC_TO_DISPATCH.setdefault(_plot, _plot)

DISPATCH_TO_PUBLIC: Dict[str, str] = {dispatch: public for public, dispatch in PUBLIC_TO_DISPATCH.items()}


_ROUTE_ALIASES: Dict[str, str] = {
    "box": "box",
    "boxplot": "box",
    "箱线图": "box",
    "箱形图": "box",
    "violin": "violin",
    "violinplot": "violin",
    "小提琴图": "violin",
    "scatter": "scatter",
    "bar": "bar",
    "barplot": "bar",
    "horizontal_bar": "bar",
    "条形图": "bar",
    "column": "column",
    "column_chart": "column",
    "柱状图": "column",
    "line": "line",
    "lineplot": "line",
    "折线图": "line",
    "histogram": "histogram",
    "hist": "histogram",
    "直方图": "histogram",
    "area": "area",
    "area_chart": "area",
    "面积图": "area",
    "scatter3d": "plot3d_scatter",
    "scatter_3d": "plot3d_scatter",
    "3d_scatter": "plot3d_scatter",
    "plot3d_scatter": "plot3d_scatter",
    "surface3d": "plot3d_surface",
    "surface_3d": "plot3d_surface",
    "3d_surface": "plot3d_surface",
    "plot3d_surface": "plot3d_surface",
    "trisurf": "plot3d_surface",
    "wireframe3d": "plot3d_wireframe",
    "wireframe_3d": "plot3d_wireframe",
    "3d_wireframe": "plot3d_wireframe",
    "plot3d_wireframe": "plot3d_wireframe",
    "mesh_wireframe3d": "plot3d_wireframe",
    "contour3d": "plot3d_contour",
    "contour_3d": "plot3d_contour",
    "3d_contour": "plot3d_contour",
    "plot3d_contour": "plot3d_contour",
    "line3d": "plot3d_line",
    "line_3d": "plot3d_line",
    "trajectory3d": "plot3d_line",
    "3d_line": "plot3d_line",
    "plot3d_line": "plot3d_line",
    "isosurface3d": "plot3d_isosurface",
    "isosurface_3d": "plot3d_isosurface",
    "3d_isosurface": "plot3d_isosurface",
    "plot3d_isosurface": "plot3d_isosurface",
    "slice3d": "plot3d_slice",
    "slice_3d": "plot3d_slice",
    "3d_slice": "plot3d_slice",
    "plot3d_slice": "plot3d_slice",
    "quiver3d": "plot3d_quiver",
    "quiver_3d": "plot3d_quiver",
    "vector3d": "plot3d_quiver",
    "plot3d_quiver": "plot3d_quiver",
    "waterfall3d": "plot3d_waterfall",
    "waterfall_3d": "plot3d_waterfall",
    "plot3d_waterfall": "plot3d_waterfall",
    "embedding3d": "plot3d_embedding",
    "embed3d": "plot3d_embedding",
    "plot3d_embedding": "plot3d_embedding",
    "mesh3d": "plot3d_mesh",
    "plot3d_mesh": "plot3d_mesh",
    "3d": "plot3d_scatter",
    "3d散点": "plot3d_scatter",
    "三维散点": "plot3d_scatter",
    "散点图": "scatter",
    "散点": "scatter",
    "volcano": "volcano",
    "火山图": "volcano",
    "forest": "forest",
    "森林图": "forest",
    "森林": "forest",
    "ma": "ma",
    "ma图": "ma",
    "enrich_dot": "enrich_dot",
    "enrich": "enrich_dot",
    "dotplot": "enrich_dot",
    "富集": "enrich_dot",
    "gsea": "gsea",
    "embedding": "embedding",
    "pca": "embedding",
    "umap": "embedding",
    "upset": "upset",
    "venn": "upset",
    "km": "km",
    "kaplan": "km",
    "kaplan_meier": "km",
    "生存": "km",
    "roc": "roc",
    "pr": "roc",
    "calibration": "calibration",
    "校准": "calibration",
    "bland_altman": "bland_altman",
    "bland": "bland_altman",
    "dca": "dca",
    "decision_curve": "dca",
    "决策曲线": "dca",
    "stress_strain": "stress_strain",
    "stress": "stress_strain",
    "应力应变": "stress_strain",
    "xrd": "xrd",
    "raman": "raman",
    "ftir": "raman",
    "phase": "phase",
    "相图": "phase",
    "hysteresis": "hysteresis",
    "磁滞": "hysteresis",
    "滞回": "hysteresis",
    "spectral_signature": "spectral_signature",
    "spectral": "spectral_signature",
    "index_ts": "index_ts",
    "ndvi": "index_ts",
    "time_series": "index_ts",
    "confusion": "confusion",
    "confusion_matrix": "confusion",
    "class_dist": "class_dist",
    "landcover": "class_dist",
    "candlestick": "candlestick",
    "kline": "candlestick",
    "k线": "candlestick",
    "cum_return": "cum_return",
    "drawdown": "cum_return",
    "rolling_stats": "rolling_stats",
    "rolling": "rolling_stats",
    "frontier": "frontier",
    "efficient_frontier": "frontier",
    "acf_pacf": "acf_pacf",
    "acf": "acf_pacf",
    "pacf": "acf_pacf",
    "likert": "likert",
    "raincloud": "raincloud",
    "irt_icc": "irt_icc",
    "icc": "irt_icc",
    "factor_loadings": "factor_loadings",
    "loading": "factor_loadings",
    "interaction": "interaction",
    "交互": "interaction",
    "world": "map_world",
    "world_admin0": "map_world",
    "world_admin1": "map_world_admin1",
    "china": "map_china",
    "china_l1": "map_china",
    "choropleth_world": "map_choropleth_world",
    "choropleth_china": "map_choropleth_china",
    "raster": "map_raster",
    "points": "map_points",
    "map_points": "map_points",
}


PLOT_ALIASES: Dict[str, str] = dict(_ROUTE_ALIASES)
for _public, _dispatch in PUBLIC_TO_DISPATCH.items():
    PLOT_ALIASES.setdefault(_public.lower(), _dispatch)
    PLOT_ALIASES.setdefault(_dispatch.lower(), _dispatch)


MODE_ALIASES = {
    "demo": "demo",
    "演示": "demo",
    "custom": "custom",
    "自定义": "custom",
    "file": "file",
    "数据": "file",
    "文件": "file",
}


PLOT_REQUIRED_FIELDS: Dict[str, List[str]] = {
    "box": ["group_col", "value_col"],
    "violin": ["group_col", "value_col"],
    "scatter": ["x_col", "y_col"],
    "bar": ["x_col", "y_col"],
    "column": ["x_col", "y_col"],
    "line": ["x_col", "y_col"],
    "histogram": ["value_col"],
    "area": ["x_col", "y_col"],
    "volcano": ["log2fc_col", "p_col"],
    "forest": ["forest_label_col", "effect_col", "ci_low_col", "ci_high_col"],
    "scatter3d": ["x_col", "y_col", "z_col"],
    "line3d": ["x_col", "y_col", "z_col"],
    "surface3d": ["x_col", "y_col", "z_col"],
    "wireframe3d": ["x_col", "y_col", "z_col"],
    "contour3d": ["x_col", "y_col", "z_col"],
    "quiver3d": ["x_col", "y_col", "z_col", "u_col", "v_col", "w_col"],
    "isosurface3d": ["scalar_col"],
    "slice3d": ["scalar_col"],
    "waterfall3d": ["x_col", "y_col", "z_col"],
    "embedding3d": ["x_col", "y_col", "z_col"],
    "mesh3d": ["x_col", "y_col", "z_col"],
    "choropleth_world": ["key_col", "value_col"],
    "choropleth_china": ["key_col", "value_col"],
    "points": ["lon_col", "lat_col"],
}


PLOT_DEFAULT_ARGS: Dict[str, Dict[str, Any]] = {
    "scatter": {"ci": 0.95, "equal": False},
    "bar": {
        "aggregation": "mean",
        "group_mode": "grouped",
        "show_values": False,
        "tick_rotation": 0,
        "palette": "tab10",
        "grid": True,
    },
    "column": {
        "aggregation": "mean",
        "group_mode": "grouped",
        "show_values": False,
        "tick_rotation": 0,
        "palette": "tab10",
        "grid": True,
    },
    "line": {"aggregation": "mean", "marker": "o", "line_width": 2.0, "palette": "tab10", "grid": True},
    "histogram": {"bins": 20, "density": False, "hist_alpha": 0.68, "palette": "tab10", "grid": True},
    "area": {"aggregation": "mean", "stacked": False, "area_alpha": 0.28, "palette": "tab10", "grid": True},
    "volcano": {"fc_thresh": 1.0, "p_thresh": 0.05, "top_n": 10},
    "forest": {"ref_line": 0.0},
    "surface3d": {"elev": None, "azim": None},
    "wireframe3d": {"rstride": 2, "cstride": 2, "elev": None, "azim": None},
    "contour3d": {"levels": 18, "elev": None, "azim": None},
    "line3d": {"elev": None, "azim": None},
    "quiver3d": {"max_arrows": 600, "elev": None, "azim": None, "length": None},
    "isosurface3d": {"iso_level": None},
    "slice3d": {"slice_x": None, "slice_y": None, "slice_z": None},
    "choropleth_world": {"scheme": "quantiles", "k": 5},
    "choropleth_china": {"scheme": "quantiles", "k": 5},
    "raster": {"alpha": 0.65},
    "calibration": {"n_bins": 10, "calib_strategy": "uniform"},
    "rolling_stats": {"window": 20},
    "acf_pacf": {"lags": 40},
}


DOMAIN_DEMO_FILES: Dict[str, str] = {
    "ma": "data/biomed/ma.csv",
    "enrich_dot": "data/biomed/enrich_dot.csv",
    "gsea": "data/biomed/gsea.csv",
    "embedding": "data/biomed/embedding.csv",
    "upset": "data/biomed/upset.csv",
    "km": "data/clinical/km.csv",
    "roc": "data/clinical/roc.csv",
    "calibration": "data/clinical/calibration.csv",
    "bland_altman": "data/clinical/bland_altman.csv",
    "dca": "data/clinical/dca.csv",
    "stress_strain": "data/materials/stress_strain.csv",
    "xrd": "data/materials/xrd.csv",
    "raman": "data/materials/raman.csv",
    "phase": "data/materials/phase.csv",
    "hysteresis": "data/materials/hysteresis.csv",
    "spectral_signature": "data/remote/spectral_signature.csv",
    "index_ts": "data/remote/index_ts.csv",
    "confusion": "data/remote/confusion.csv",
    "class_dist": "data/remote/class_dist.csv",
    "candlestick": "data/finance/candlestick.csv",
    "cum_return": "data/finance/returns.csv",
    "rolling_stats": "data/finance/returns.csv",
    "frontier": "data/finance/frontier.csv",
    "acf_pacf": "data/finance/series.csv",
    "likert": "data/psych/likert.csv",
    "raincloud": "data/psych/raincloud.csv",
    "irt_icc": "data/psych/irt_icc.csv",
    "factor_loadings": "data/psych/factor_loadings.csv",
    "interaction": "data/psych/interaction.csv",
}


MAP_DEMO_DEFAULTS: Dict[str, Dict[str, Any]] = {
    "choropleth_world": {"key_col": "ISO_A3", "value_col": "value", "on": "iso_a3", "scheme": "natural", "k": 6},
    "choropleth_china": {"level": 1, "key_col": "NAME_1", "value_col": "value", "on": "NAME", "scheme": "quantiles", "k": 5, "cmap": "Reds"},
    "raster": {"alpha": 0.60},
    "points": {"lon_col": "lon", "lat_col": "lat", "label_col": "name", "hue_col": "category", "size_col": "value", "size_range": "24,180", "basemap": "china_l1"},
}


MAP_DEMO_FILES: Dict[str, str] = {
    "choropleth_world": "data/world_choropleth.csv",
    "choropleth_china": "data/china_values.csv",
    "points": "data/points_cn.csv",
}

MAP_DEMO_RASTER_CANDIDATES: List[str] = ["data/demo_world.tif", "data/demo_china.tif"]


PLOT_DEPENDENCY_HINTS: Dict[str, Optional[str]] = {}
for _plot in PLOT_GROUPS["stats_2d"]:
    PLOT_DEPENDENCY_HINTS[_plot] = None
for _plot in PLOT_GROUPS["domain_2d"]:
    PLOT_DEPENDENCY_HINTS[_plot] = "data"
for _plot in PLOT_GROUPS["plots_3d"]:
    PLOT_DEPENDENCY_HINTS[_plot] = None
for _plot in PLOT_GROUPS["maps"]:
    PLOT_DEPENDENCY_HINTS[_plot] = "maps"
PLOT_DEPENDENCY_HINTS["raster"] = "raster"
for _plot in {"embedding", "upset", "roc", "calibration", "dca", "frontier", "acf_pacf", "irt_icc", "isosurface3d"}:
    PLOT_DEPENDENCY_HINTS[_plot] = "ml"


def normalize_plot_name(name: str) -> str:
    key = str(name or "").strip().lower()
    if not key:
        return key
    dispatch = PLOT_ALIASES.get(key)
    if dispatch:
        return dispatch
    return PUBLIC_TO_DISPATCH.get(key, key)


def normalize_mode(name: str) -> str:
    return MODE_ALIASES.get(str(name or "").strip().lower(), str(name or "").strip().lower())


def public_plot_name(name: str) -> str:
    dispatch = normalize_plot_name(name)
    return DISPATCH_TO_PUBLIC.get(dispatch, dispatch)


def dispatch_key_for_public_plot(plot_name: str) -> str:
    return PUBLIC_TO_DISPATCH.get(str(plot_name or "").strip().lower(), str(plot_name or "").strip().lower())


def is_map_dispatch_key(plot_dispatch_key: str) -> bool:
    return str(plot_dispatch_key).startswith("map_")


def is_3d_dispatch_key(plot_dispatch_key: str) -> bool:
    return str(plot_dispatch_key).startswith("plot3d_")


def is_extended_plot_key(plot_name_or_dispatch_key: str) -> bool:
    return public_plot_name(plot_name_or_dispatch_key) in set(PLOT_GROUPS["domain_2d"])


def required_fields_for_plot(plot_name_or_alias: str) -> List[str]:
    return list(PLOT_REQUIRED_FIELDS.get(public_plot_name(plot_name_or_alias), []))


def default_args_for_plot(plot_name_or_alias: str) -> Dict[str, Any]:
    return deepcopy(PLOT_DEFAULT_ARGS.get(public_plot_name(plot_name_or_alias), {}))


def demo_data_path_for_plot(plot_name_or_alias: str, project_root: Path) -> Optional[Path]:
    rel = DOMAIN_DEMO_FILES.get(public_plot_name(plot_name_or_alias))
    if not rel:
        rel = MAP_DEMO_FILES.get(public_plot_name(plot_name_or_alias))
    if not rel:
        return None
    return project_root / rel


def demo_defaults_for_map_plot(plot_name_or_dispatch_key: str, project_root: Path) -> Dict[str, Any]:
    public_name = public_plot_name(plot_name_or_dispatch_key)
    defaults = deepcopy(MAP_DEMO_DEFAULTS.get(public_name, {}))
    if not defaults:
        return {}

    if public_name in MAP_DEMO_FILES:
        fp = project_root / MAP_DEMO_FILES[public_name]
        if not fp.exists():
            raise FileNotFoundError(f"未找到 {public_name} demo 数据：{fp}")
        defaults["file"] = str(fp)
        return defaults

    if public_name == "raster":
        selected: Optional[Path] = None
        for rel in MAP_DEMO_RASTER_CANDIDATES:
            fp = project_root / rel
            if fp.exists():
                selected = fp
                break
        if selected is None:
            joined = " 或 ".join(str(project_root / rel) for rel in MAP_DEMO_RASTER_CANDIDATES)
            raise FileNotFoundError(f"未找到 raster demo 数据：{joined}")
        defaults["raster_file"] = str(selected)
        defaults.setdefault("basemap", "china_l1" if "china" in selected.name.lower() else "world_admin0")
        return defaults

    return defaults


def canonical_plots_by_group() -> Dict[str, List[str]]:
    return {k: list(v) for k, v in PLOT_GROUPS.items()}


def group_metadata() -> Dict[str, Dict[str, Any]]:
    return deepcopy(GROUP_META)


def _group_for_plot(public_name: str) -> str:
    for group_key, plots in PLOT_GROUPS.items():
        if public_name in plots:
            return group_key
    return "unknown"


def _aliases_for_public_plot(public_name: str) -> List[str]:
    dispatch_key = dispatch_key_for_public_plot(public_name)
    aliases = [alias for alias, dispatch in PLOT_ALIASES.items() if dispatch == dispatch_key]
    aliases.extend([public_name, dispatch_key])
    return sorted(set(aliases))


def plot_registry_payload() -> Dict[str, Any]:
    groups = []
    for group_key, meta in sorted(GROUP_META.items(), key=lambda kv: int(kv[1].get("order", 999))):
        groups.append(
            {
                "key": group_key,
                "label": meta["label"],
                "order": meta["order"],
                "description": meta["description"],
                "scene": meta["scene"],
                "count": len(PLOT_GROUPS.get(group_key, [])),
            }
        )

    plots: Dict[str, Dict[str, Any]] = {}
    for public_name in ALL_PUBLIC_PLOTS:
        plots[public_name] = {
            "display_name": PLOT_DISPLAY_NAMES.get(public_name, public_name),
            "description": PLOT_DESCRIPTIONS.get(public_name, "科研数据可视化图型。"),
            "demo_available": True,
            "dispatch_key": dispatch_key_for_public_plot(public_name),
            "group": _group_for_plot(public_name),
            "required_fields": required_fields_for_plot(public_name),
            "defaults": default_args_for_plot(public_name),
            "dependency_extra": PLOT_DEPENDENCY_HINTS.get(public_name),
            "demo_data": DOMAIN_DEMO_FILES.get(public_name) or MAP_DEMO_FILES.get(public_name),
            "aliases": _aliases_for_public_plot(public_name),
        }

    return {
        "groups": groups,
        "plots_by_group": canonical_plots_by_group(),
        "plots": plots,
    }

