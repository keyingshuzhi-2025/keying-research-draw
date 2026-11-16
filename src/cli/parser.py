from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.cli.config_schema import validate_cli_config_payload
from src.registry.plot_registry import GROUP_META, PLOT_DISPLAY_NAMES, PLOT_GROUPS
from src.util.dependency_hints import format_missing_dependency
from src.version import CLI_VERSION


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "科研绘图：统计图 + 地图（离线底图）\n"
            "Static (box/violin/scatter/bar/column/line/histogram/area/volcano/forest) + "
            "3D (scatter3d/surface3d/wireframe3d/contour3d/line3d/isosurface3d/slice3d/quiver3d/waterfall3d/embedding3d/mesh3d) + "
            "Maps (world/china/choropleth/raster/points)"
        ),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--mode", default="demo", help="模式 mode: demo/演示 | custom/自定义 | file/文件（从CSV/TSV/Excel导入）")
    p.add_argument(
        "--plot",
        default="box",
        help=(
            "图类型 plot:\n"
            "  统计: box/violin/scatter/bar/column/line/histogram/area/volcano/forest\n"
            "  3D: scatter3d/surface3d/wireframe3d/contour3d/line3d/"
            "isosurface3d/slice3d/quiver3d/waterfall3d/embedding3d/mesh3d\n"
            "  生物: ma/enrich_dot/gsea/embedding(pca|umap)/upset\n"
            "  临床: km/roc/pr/calibration/bland_altman/dca\n"
            "  材料: stress_strain/xrd/raman/ftir/phase/hysteresis\n"
            "  遥感: spectral_signature/index_ts/confusion/class_dist/roc/pr\n"
            "  金融: candlestick/cum_return/rolling_stats/frontier/acf_pacf\n"
            "  心理: likert/raincloud/irt_icc/factor_loadings/interaction\n"
            "  地图: world/world_admin1/china/choropleth_world/choropleth_china/raster/points"
        ),
    )
    p.add_argument("--title", type=str, default=None, help="自定义标题 / Custom title")
    p.add_argument("--save-name", type=str, default=None, help="保存文件名（不含扩展名）/ filename without suffix")
    p.add_argument("--fmt", dest="fmt", type=str, default=None, help="导出格式：png/pdf/svg 等")
    p.add_argument("--dpi", type=int, default=None, help="导出 DPI")
    p.add_argument("--match-screen", action="store_true", help="保存与 show() 完全一致（WYSIWYG）")
    p.add_argument("--no-match-screen", action="store_true", help="关闭 WYSIWYG（使用指定/默认 DPI）")
    p.add_argument("--tight", action="store_true", help="期刊导出紧裁剪（bbox_inches='tight')")
    p.add_argument("--xlabel", type=str, default=None, help="x 轴标题 / x-axis label")
    p.add_argument("--ylabel", type=str, default=None, help="y 轴标题 / y-axis label")
    p.add_argument("--no-show", action="store_true", help="不显示窗口，仅保存 / save only, do not show window")
    p.add_argument("--outdir", type=str, default=None, help="（可选）覆盖 PlotConfig 输出目录")
    p.add_argument("--seed", type=int, default=42, help="随机种子（demo 用）")
    p.add_argument("--version", action="store_true", help="显示版本并退出")

    p.add_argument("--group", action="append", help="重复使用：组数据，如 'Ctrl: 1,2,3'；repeat for multiple groups")
    p.add_argument("--x", type=str, help="X数组，如 '1,2,3'、'A,B,C' 或 '[1,2,3]' / x values")
    p.add_argument("--y", type=str, help="Y数值数组，如 '4,5,6' 或 '[4,5,6]' / y values")
    p.add_argument("--aggregation", choices=("mean", "median", "sum"), default="mean", help="重复类别/时间点的汇总方式")
    p.add_argument("--group-mode", choices=("grouped", "stacked"), default="grouped", help="条形图/柱状图分组展示方式")
    p.add_argument("--show-values", action="store_true", help="在条形图/柱状图上显示数值")
    p.add_argument("--tick-rotation", type=float, default=0, help="分类刻度标签旋转角度")
    p.add_argument("--palette", type=str, default="tab10", help="Matplotlib 配色方案名称")
    p.add_argument("--marker", type=str, default="o", help="折线图数据点标记；空字符串表示不显示标记")
    p.add_argument("--line-width", type=float, default=2.0, help="折线图线宽")
    p.add_argument("--bins", type=int, default=20, help="直方图分箱数")
    p.add_argument("--density", action="store_true", help="直方图纵轴使用概率密度")
    p.add_argument("--hist-alpha", type=float, default=0.68, help="直方图填充透明度")
    p.add_argument("--area-alpha", type=float, default=0.28, help="面积图填充透明度")
    p.add_argument("--stacked", action="store_true", help="面积图使用堆叠模式")
    p.add_argument("--grid", dest="grid", action="store_true", help="显示基础二维图网格线")
    p.add_argument("--no-grid", dest="grid", action="store_false", help="关闭基础二维图网格线")
    p.set_defaults(grid=True)
    p.add_argument("--z", type=str, help="3D散点Z数组，如 '7,8,9' 或 '[7,8,9]' / z values")
    p.add_argument("--u", type=str, help="3D 向量 U 数组 / 3D vector U values")
    p.add_argument("--v", type=str, help="3D 向量 V 数组 / 3D vector V values")
    p.add_argument("--w", type=str, help="3D 向量 W 数组 / 3D vector W values")
    p.add_argument("--scalar", type=str, help="3D 体数据标量数组 / scalar values")
    p.add_argument("--zlabel", type=str, default=None, help="z 轴标题 / z-axis label")
    p.add_argument("--elev", type=float, default=None, help="3D 视角仰角 / elevation angle")
    p.add_argument("--azim", type=float, default=None, help="3D 视角方位角 / azimuth angle")
    p.add_argument("--levels", type=int, default=18, help="3D 等高线层数 / contour levels")
    p.add_argument("--rstride", type=int, default=2, help="3D 线框图行步长 / wireframe row stride")
    p.add_argument("--cstride", type=int, default=2, help="3D 线框图列步长 / wireframe column stride")
    p.add_argument("--iso-level", type=float, default=None, help="3D 等值面阈值 / isosurface level")
    p.add_argument("--slice-x", type=float, default=None, help="3D 切片 x 位置")
    p.add_argument("--slice-y", type=float, default=None, help="3D 切片 y 位置")
    p.add_argument("--slice-z", type=float, default=None, help="3D 切片 z 位置")
    p.add_argument("--max-arrows", type=int, default=600, help="3D 矢量图最多箭头数量")
    p.add_argument("--length", type=float, default=None, help="3D 矢量图箭头缩放因子；默认按点间距自动缩放")
    p.add_argument("--ci", type=float, default=0.95, help="散点回归线置信水平（0~1；0 关闭置信带）")
    p.add_argument("--equal", action="store_true", help="散点图使用等比例坐标")
    p.add_argument("--log2fc", type=str, help="火山图log2FC数组 / log2FC array")
    p.add_argument("--pvals", type=str, help="火山图p值数组 / p-values array")
    p.add_argument("--labels", type=str, help="点标签数组（可选）/ optional point labels")
    p.add_argument("--fc-thresh", type=float, default=1.0, help="|log2FC| 阈值")
    p.add_argument("--p-thresh", type=float, default=0.05, help="p 阈值")
    p.add_argument("--fdr", type=float, default=None, help="火山图 FDR 阈值（BH）")
    p.add_argument("--top-n", type=int, default=0, help="标注 -log10(p) TopN 个点 / annotate top-N")
    p.add_argument("--forest-labels", type=str, help="森林图标签数组 / labels for forest")
    p.add_argument("--effects", type=str, help="效应量数组 / effects")
    p.add_argument("--ci-low", type=str, help="CI低数组 / CI low")
    p.add_argument("--ci-high", type=str, help="CI高数组 / CI high")
    p.add_argument("--weights", type=str, help="权重数组（可选）/ optional weights")
    p.add_argument("--ref-line", type=float, default=0.0, help="参考线（默认0.0）/ reference line")

    p.add_argument("--file", type=str, help="CSV/TSV/Excel/GeoJSON/GPKG/SHP 文件路径")
    p.add_argument("--sep", type=str, default=None, help="分隔符（默认按后缀推断）")
    p.add_argument("--group-col", type=str, help="长表：组名列 / long format: group column")
    p.add_argument("--value-col", type=str, help="长表或分级着色：数值列 / numeric value column")
    p.add_argument("--x-col", type=str, help="散点X列 / x column")
    p.add_argument("--y-col", type=str, help="散点Y列 / y column")
    p.add_argument("--z3d-col", type=str, default=None, help="3D Z 列（别名，优先级低于 --z-col）")
    p.add_argument("--u-col", type=str, help="3D 向量 U 列")
    p.add_argument("--v-col", type=str, help="3D 向量 V 列")
    p.add_argument("--w-col", type=str, help="3D 向量 W 列")
    p.add_argument("--scalar-col", type=str, help="3D 标量列（isosurface/slice/mesh）")
    p.add_argument("--log2fc-col", type=str, help="log2FC 列 / log2FC column")
    p.add_argument("--p-col", type=str, help="p 值列 / p-value column")
    p.add_argument("--label-col", type=str, help="标签列（可选）/ optional label column")
    p.add_argument("--forest-label-col", type=str, help="森林图标签列 / label column")
    p.add_argument("--effect-col", type=str, help="效应量列 / effect column")
    p.add_argument("--ci-low-col", type=str, help="CI 低列 / CI low column")
    p.add_argument("--ci-high-col", type=str, help="CI 高列 / CI high column")
    p.add_argument("--weight-col", type=str, help="权重列（可选）/ weight column")

    p.add_argument("--mean-col", type=str, help="MA 图均值列 / mean column")
    p.add_argument("--term-col", type=str, help="富集图术语列 / term column")
    p.add_argument("--count-col", type=str, help="计数列 / count column (enrichment/confusion/likert)")
    p.add_argument("--ratio-col", type=str, help="比例列 / ratio column (enrichment)")
    p.add_argument("--hit-col", type=str, help="GSEA 命中列 / hit column (bool/int)")
    p.add_argument("--set-cols", type=str, help="UpSet 集合列（逗号分隔）/ set columns")
    p.add_argument("--embed-method", type=str, default=None, help="embedding 方法: pca/umap")
    p.add_argument("--curve", type=str, default=None, help="ROC/PR 曲线类型: roc/pr")
    p.add_argument("--pos-label", type=str, default=None, help="正类标签（ROC/PR）")
    p.add_argument("--score-col", type=str, help="预测得分列 / score column")
    p.add_argument("--prob-col", type=str, help="预测概率列 / probability column")
    p.add_argument("--true-col", type=str, help="真实标签列 / true label column")
    p.add_argument("--pred-col", type=str, help="预测标签列 / predicted label column")
    p.add_argument("--normalize", type=str, default=None, help="confusion normalize: none/true/pred/all")
    p.add_argument("--n-bins", type=int, default=10, help="校准曲线分箱数 / calibration bins")
    p.add_argument("--calib-strategy", type=str, default="uniform", help="校准分箱策略: uniform/quantile")
    p.add_argument("--time-col", type=str, help="时间列 / time column")
    p.add_argument("--event-col", type=str, help="事件列（0/1）/ event column")
    p.add_argument("--risk-table", dest="risk_table", action="store_true", help="显示 KM 风险表")
    p.add_argument("--no-risk-table", dest="risk_table", action="store_false", help="关闭 KM 风险表")
    p.set_defaults(risk_table=True)
    p.add_argument("--thresholds", type=str, default=None, help="阈值列表（逗号）/ thresholds")
    p.add_argument("--z-col", type=str, help="Z 数值列 / z column (phase)")
    p.add_argument("--invert-x", action="store_true", help="反转 X 轴（如 FTIR）")
    p.add_argument("--class-col", type=str, help="类别列 / class column")
    p.add_argument("--item-col", type=str, help="题项列 / item column")
    p.add_argument("--response-col", type=str, help="量表响应列 / response column")
    p.add_argument("--a-col", type=str, help="IRT a 参数列")
    p.add_argument("--b-col", type=str, help="IRT b 参数列")
    p.add_argument("--c-col", type=str, help="IRT c 参数列")
    p.add_argument("--theta-min", type=float, default=-4.0, help="IRT theta 最小值")
    p.add_argument("--theta-max", type=float, default=4.0, help="IRT theta 最大值")
    p.add_argument("--factor-col", type=str, help="因子列 / factor column")
    p.add_argument("--loading-col", type=str, help="载荷列 / loading column")
    p.add_argument("--date-col", type=str, help="日期列 / date column")
    p.add_argument("--open-col", type=str, help="开盘列 / open column")
    p.add_argument("--high-col", type=str, help="最高列 / high column")
    p.add_argument("--low-col", type=str, help="最低列 / low column")
    p.add_argument("--close-col", type=str, help="收盘列 / close column")
    p.add_argument("--volume-col", type=str, help="成交量列 / volume column")
    p.add_argument("--return-col", type=str, help="收益列 / return column")
    p.add_argument("--price-col", type=str, help="价格列 / price column")
    p.add_argument("--window", type=int, default=20, help="滚动窗口 / rolling window")
    p.add_argument("--risk-free", type=float, default=0.0, help="无风险利率 / risk-free rate")
    p.add_argument("--n-portfolios", type=int, default=4000, help="随机组合数量 / portfolios")
    p.add_argument("--lags", type=int, default=40, help="ACF/PACF 滞后阶数 / lags")
    p.add_argument("--elastic-max", type=float, default=None, help="应力应变线性区间上限")
    p.add_argument("--yield-offset", type=float, default=None, help="屈服偏移（如 0.002）")
    p.add_argument("--custom-json", type=str, default=None, help="自定义 JSON 数据字符串")
    p.add_argument("--custom-json-file", type=str, default=None, help="自定义 JSON 文件路径")

    p.add_argument("--map-theme", type=str, default="journal", help="地图主题：journal/light/dark")
    p.add_argument("--basemap-root", type=str, default=None, help="离线底图根目录（覆盖 MAP_BASEMAP_ROOT）")
    p.add_argument("--include-taiwan", dest="include_taiwan", action="store_true", help="中国底图包含台湾（默认开）")
    p.add_argument("--no-include-taiwan", dest="include_taiwan", action="store_false", help="中国底图不包含台湾")
    p.set_defaults(include_taiwan=True)
    p.add_argument("--include-hk-mo", dest="include_hk_mo", action="store_true", help="中国底图包含港澳（默认开）")
    p.add_argument("--no-include-hk-mo", dest="include_hk_mo", action="store_false", help="中国底图不包含港澳")
    p.set_defaults(include_hk_mo=True)
    p.add_argument("--taiwan-name", type=str, default=None, help="L1 union 后台湾显示名称（默认：台湾省）")

    p.add_argument("--countries", type=str, help="admin1 仅绘制指定国家，逗号分隔")
    p.add_argument("--level", type=int, default=1, help="中国层级：0国/1省/2市/3县")
    p.add_argument("--highlight", type=str, help="高亮名称（world用国家名；china用NAME_i/GID_i），逗号分隔")
    p.add_argument("--label-names", action="store_true", help="给区域名称标注")
    p.add_argument("--crs", type=str, default=None, help="目标投影（如 EPSG:4326, ESRI:54030 等）")
    p.add_argument("--country-field", type=str, default=None, help="admin1 底图中的国别字段名（如 adm0_name 或 admin），用于 --countries 筛选")
    p.add_argument("--case-sensitive", action="store_true", help="国家名筛选大小写敏感（默认大小写不敏感）")

    p.add_argument("--key-col", type=str, help="分级/关联键列名")
    p.add_argument("--on", type=str, default=None, help="对齐字段（world: iso_a3|name；china: NAME|GID）")
    p.add_argument("--scheme", type=str, default="quantiles", help="分级方案：quantiles/equal/natural")
    p.add_argument("--k", type=int, default=5, help="分级数")
    p.add_argument("--cmap", type=str, default=None, help="配色方案（如 Blues/YlOrRd/journal 等）")
    p.add_argument("--label-top-n", type=int, default=0, help="按值标注前N个区域")

    p.add_argument("--raster-file", type=str, help="GeoTIFF 等栅格路径")
    p.add_argument("--basemap", type=str, default="world_admin0", help="叠加时底图：world_admin0|china_l1|none")
    p.add_argument("--alpha", type=float, default=0.65, help="栅格透明度 [0,1]")

    p.add_argument("--lon-col", type=str, help="点经度列（CSV/TSV/Excel）")
    p.add_argument("--lat-col", type=str, help="点纬度列（CSV/TSV/Excel）")
    p.add_argument("--size-col", type=str, help="点大小字段")
    p.add_argument("--hue-col", type=str, help="点颜色字段（连续/分类均可）")
    p.add_argument("--size-range", type=str, default=None, help="点大小范围，如 '24,160'")

    p.add_argument("--config", type=str, default=None, help="从 JSON/YAML 配置读取参数，命令行优先覆盖")
    p.add_argument("--help-examples", action="store_true", help="显示示例命令")
    return p


def _load_config(path: Path) -> Dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yml", ".yaml"}:
        try:
            import yaml
        except Exception as e:
            raise RuntimeError(
                format_missing_dependency(
                    package="PyYAML",
                    feature="YAML 配置文件解析",
                    recommended_extra="all",
                    fallback_pip="uv add PyYAML",
                )
            ) from e
        return yaml.safe_load(text) or {}
    try:
        return json.loads(text)
    except Exception as e:
        raise RuntimeError("读取 JSON 失败，请检查配置格式") from e


def _provided_destinations(parser: argparse.ArgumentParser, argv: Optional[List[str]]) -> set[str]:
    if not argv:
        return set()
    option_to_dest: Dict[str, str] = {}
    for action in parser._actions:
        for opt in action.option_strings:
            option_to_dest[opt] = action.dest

    provided: set[str] = set()
    for token in argv:
        if not token.startswith("--"):
            continue
        key = token.split("=", 1)[0]
        dest = option_to_dest.get(key)
        if dest:
            provided.add(dest)
    return provided


def merge_args_with_config(
    parser: argparse.ArgumentParser,
    args: argparse.Namespace,
    argv: Optional[List[str]] = None,
) -> argparse.Namespace:
    cfg_path = getattr(args, "config", None)
    if not cfg_path:
        return args

    cfg_p = Path(cfg_path).expanduser().resolve()
    if not cfg_p.exists():
        raise FileNotFoundError(f"配置文件不存在：{cfg_p}")
    cfg = _load_config(cfg_p)
    if not isinstance(cfg, dict):
        raise ValueError("配置文件需为对象（key-value）")
    cfg = validate_cli_config_payload(parser, cfg)

    defaults = parser.parse_args([])
    explicit_dests = _provided_destinations(parser, argv)
    merged = vars(args)
    for key, value in cfg.items():
        if key not in merged:
            continue
        if key in explicit_dests:
            continue
        current = merged[key]
        default = getattr(defaults, key)
        if isinstance(default, bool):
            if current == default:
                merged[key] = value
            continue
        if current == default or current is None:
            merged[key] = value
    return argparse.Namespace(**merged)


def print_examples_and_exit() -> None:
    print(
        r"""
Examples
========
# 1) 演示：箱线图 / 小提琴图 / 散点拟合 / 火山图 / 森林图
uv run python -m src.main --mode demo --plot box --title "箱线图演示"
uv run python -m src.main --mode demo --plot violin
uv run python -m src.main --mode demo --plot scatter --xlabel X --ylabel Y --ci 0.95 --equal
uv run python -m src.main --mode demo --plot volcano --top-n 10 --fdr 0.1
uv run python -m src.main --mode demo --plot forest --ref-line 0

# 2) 自定义：箱线图
uv run python -m src.main --mode custom --plot box \
  --group "Ctrl: 1,2,3,4" --group "A: 1.2,2.3,1.8" --group "B: 0.7,0.8,1.0"

# 3) 文件模式：散点
data/demo.csv: 列 x,y
uv run python -m src.main --mode file --plot scatter --file data/demo.csv --x-col x --y-col y --ci 0.9

# 3.1) 3D 散点
uv run python -m src.main --mode demo --plot scatter3d --title "3D Scatter"
uv run python -m src.main --mode file --plot scatter3d --file data/demo_scatter3d.csv --x-col x --y-col y --z-col z
uv run python -m src.main --mode demo --plot surface3d --title "3D Surface"
uv run python -m src.main --mode demo --plot wireframe3d --title "3D Wireframe"
uv run python -m src.main --mode demo --plot contour3d --title "3D Contour"
uv run python -m src.main --mode demo --plot line3d --title "3D Trajectory"
uv run python -m src.main --mode demo --plot quiver3d --title "3D Vector Field"
uv run python -m src.main --mode demo --plot waterfall3d --title "3D Waterfall"
uv run python -m src.main --mode demo --plot embedding3d --embed-method pca --title "3D Embedding"
uv run python -m src.main --mode demo --plot mesh3d --title "3D Mesh"
uv run python -m src.main --mode demo --plot slice3d --title "3D Slices"
uv run python -m src.main --mode demo --plot isosurface3d --iso-level 0.3 --title "3D Isosurface"

# 4) 世界底图 + 高亮 + 标注
uv run python -m src.main --plot world --title "World" --highlight "China,United States of America" --label-names

# 5) 中国分级着色（省级）
uv run python -m src.main --plot choropleth_china --file data/china_values.csv --level 1 \
  --key-col NAME_1 --value-col value --on NAME --k 6 --cmap Reds --label-top-n 5

# 6) 栅格叠加（世界底图）
uv run python -m src.main --plot raster --raster-file data/geo/demo_world.tif --alpha 0.6 --basemap world_admin0

# 7) 点位叠加（中国）
uv run python -m src.main --plot points --basemap china_l1 --file data/points_cn.csv \
  --lon-col lon --lat-col lat --hue-col category --size-col value --size-range 24,180

# 8) 完整性控制（中国地图）
uv run python -m src.main --plot china --no-include-hk-mo --taiwan-name 台湾

# 9) 领域图示例
uv run python -m src.main --mode file --plot ma --file data/biomed/ma.csv --title "MA Plot"
uv run python -m src.main --mode file --plot km --file data/clinical/km.csv --title "Kaplan-Meier"
uv run python -m src.main --mode file --plot xrd --file data/materials/xrd.csv --title "XRD"
uv run python -m src.main --mode file --plot spectral_signature --file data/remote/spectral_signature.csv --title "Spectral"
uv run python -m src.main --mode file --plot candlestick --file data/finance/candlestick.csv --title "Candlestick"
uv run python -m src.main --mode file --plot likert --file data/psych/likert.csv --title "Likert"
"""
    )
    print("\n# 每种图型的内置 Demo（按图型分组）")
    for group_key, plot_names in PLOT_GROUPS.items():
        print(f"\n## {GROUP_META[group_key]['label']}")
        for plot_name in plot_names:
            label = PLOT_DISPLAY_NAMES.get(plot_name, plot_name)
            print(
                f'uv run python -m src.main --mode demo --plot {plot_name} '
                f'--title "{label}示例"'
            )
    sys.exit(0)


def handle_early_exit(args: argparse.Namespace) -> None:
    if getattr(args, "version", False):
        print(CLI_VERSION)
        sys.exit(0)
    if getattr(args, "help_examples", False):
        print_examples_and_exit()


def parse_cli_args(argv: Optional[List[str]] = None) -> Tuple[argparse.ArgumentParser, argparse.Namespace]:
    parser = build_parser()
    args = parser.parse_args(argv)
    handle_early_exit(args)
    args = merge_args_with_config(parser, args, argv=argv)
    return parser, args
