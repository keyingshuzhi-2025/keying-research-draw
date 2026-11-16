# -*- coding: utf-8 -*-
# @Time: 2025/10/23 上午10:12  → 2025/11/12 修复与增强（稳定版）
# @Author: 柯影数智
# @File: static_analysis.py
# @Email: 1090461393@qq.com
# @SoftWare: PyCharm

"""
static_analysis — 顶刊常用科研图 · OOP 版（稳定修复）
支持：箱线图 / 小提琴图 / 散点+拟合 / 条形图 / 柱状图 / 折线图 / 直方图 / 面积图 / 火山图 / 森林图
扩展：MA / GSEA / 富集 Dotplot / Embedding(PCA/UMAP) / UpSet / KM / ROC-PR / Calibration /
      Bland-Altman / DCA / Stress-Strain / XRD / Raman(FTIR) / Phase / Hysteresis /
      Spectral / Index TS / Confusion / Class Dist / Candlestick / CumReturn+DD /
      Rolling Stats / Frontier / ACF-PACF / Likert / Raincloud / IRT-ICC / Loadings / Interaction

本版修复与增强（2025-11-12）：
- ✅ 修复森林图 xerr 维度不匹配（单样本时报错）与数组被误取首元素的问题
- ✅ 火山图 Top-N 标注与 gene_labels 对齐，允许长度不一致/标量
- ✅ 小提琴图 widths=None 时不传参，兼容 Matplotlib 3.9+
- ✅ 散点图视觉优化：置信带置底、1:1 参考线、等比例选项、返回统计信息（斜率/截距/r/p/R²）
- ✅ 统一保存：PlotConfig.apply() + util.save_figure（WYSIWYG / tight）

依赖：numpy、matplotlib；可选 SciPy（t 分布临界值）
局部依赖：src.config.PlotConfig、src.util.stats_utils
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple, Dict, List, Any

import numpy as np
import matplotlib

from src.config import PlotConfig, ensure_matplotlib_backend

ensure_matplotlib_backend()

import matplotlib.pyplot as plt
from src.util.stats_utils import (
    StatsUtils,
    ArrayLike,
    save_figure,  # 统一保存逻辑（标题即文件名 + WYSIWYG）
)
from src.util.dependency_hints import format_missing_dependency

__all__ = [
    "StaticAnalysisPlotter",
    "boxplot",
    "violin_plot",
    "scatter_with_fit",
    "volcano_plot",
    "forest_plot",
    "bar_plot",
    "column_plot",
    "line_plot",
    "histogram_plot",
    "area_plot",
    "ma_plot",
    "enrichment_dotplot",
    "gsea_running_plot",
    "embedding_plot",
    "upset_plot",
    "kaplan_meier_plot",
    "roc_pr_plot",
    "calibration_plot",
    "bland_altman_plot",
    "decision_curve_plot",
    "stress_strain_plot",
    "xrd_plot",
    "raman_plot",
    "phase_plot",
    "hysteresis_plot",
    "spectral_signature_plot",
    "index_time_series_plot",
    "confusion_matrix_plot",
    "class_distribution_plot",
    "candlestick_plot",
    "cum_return_drawdown_plot",
    "rolling_stats_plot",
    "efficient_frontier_plot",
    "acf_pacf_plot",
    "likert_plot",
    "raincloud_plot",
    "irt_icc_plot",
    "factor_loadings_plot",
    "interaction_plot",
]

# 版本检测：mpl >= 3.7 支持 layout="constrained"
try:
    _MPL_GE_37 = tuple(int(x) for x in matplotlib.__version__.split(".")[:2]) >= (3, 7)
except Exception:
    _MPL_GE_37 = False


# -----------------------------
# 小工具
# -----------------------------

def _finite_1d(a: ArrayLike) -> np.ndarray:
    """扁平化为 1D 并仅保留有限数（去 NaN/Inf）；返回 float64。"""
    x = StatsUtils.ensure_1d(a).astype(float)
    return x[np.isfinite(x)]


def _pairwise_finite(x: ArrayLike, y: ArrayLike) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """对 (x, y) 做**成对**去 NaN/Inf，保持索引对齐。返回 (xx, yy, mask)。"""
    xx = StatsUtils.ensure_1d(x).astype(float)
    yy = StatsUtils.ensure_1d(y).astype(float)
    if xx.size != yy.size:
        raise ValueError("x 与 y 长度需一致")
    mask = np.isfinite(xx) & np.isfinite(yy)
    return xx[mask], yy[mask], mask


def _multi_finite(*arrs: ArrayLike) -> Tuple[List[np.ndarray], np.ndarray]:
    """对多列做**共用掩码**的去 NaN/Inf，保持多列与 labels 对齐。"""
    vecs = [StatsUtils.ensure_1d(a).astype(float) for a in arrs]
    n = {v.size for v in vecs}
    if len(n) != 1:
        raise ValueError("输入列长度需一致")
    mask = np.ones(vecs[0].shape, dtype=bool)
    for v in vecs:
        mask &= np.isfinite(v)
    return [v[mask] for v in vecs], mask


def _apply_axes_text(ax: plt.Axes, title: Optional[str], xlabel: Optional[str], ylabel: Optional[str]) -> None:
    if title:
        ax.set_title(title)
    if xlabel:
        ax.set_xlabel(xlabel)
    if ylabel:
        ax.set_ylabel(ylabel)


from src.chart.plot_2d.plotters.static import biomed as _biomed
from src.chart.plot_2d.plotters.static import basic as _basic
from src.chart.plot_2d.plotters.static import clinical as _clinical
from src.chart.plot_2d.plotters.static import finance as _finance
from src.chart.plot_2d.plotters.static import materials as _materials
from src.chart.plot_2d.plotters.static import psych as _psych
from src.chart.plot_2d.plotters.static import remote as _remote


@dataclass
class StaticAnalysisPlotter:
    """科研绘图统一入口（面向对象）。

    所有方法均返回 (fig, ax, *extras)；导出统一走 self.save()。
    """

    cfg: Optional[PlotConfig] = None

    def __post_init__(self):
        if self.cfg is None:
            self.cfg = PlotConfig.from_env()
        # 应用全局渲染与主题（字体、后端、DPI、导出格式等）
        self.cfg.apply()

    # -----------------------------
    # 内部：统一创建 Figure/Axes（启用受约束布局）
    # -----------------------------
    def _new_subplots(self, figsize: Tuple[float, float]) -> Tuple[plt.Figure, plt.Axes]:
        """创建带受约束布局的 Figure/Axes，自动兼容不同 Matplotlib 版本。"""
        if _MPL_GE_37:
            return plt.subplots(figsize=figsize, layout="constrained")
        else:
            return plt.subplots(figsize=figsize, constrained_layout=True)

    # -----------------------------
    # 导出工具（WYSIWYG + 标题即文件名）
    # -----------------------------
    def save(
        self,
        name: Optional[str] = None,
        fig: Optional[plt.Figure] = None,
        fmt: Optional[str] = None,
        dpi: Optional[int] = None,
        match_screen: bool = True,
        tight: bool = False,
    ) -> str:
        """
        保存图像（委托 util.save_figure）：
        - 不传 name → 自动从 suptitle/axes.title 生成文件名（安全化）
        - match_screen=True：保存与屏幕显示一致（DPI='figure' 且不 tight 裁剪）
        - tight=True：期刊导出时使用 bbox_inches='tight'（与 match_screen 不建议同开）
        """
        return save_figure(
            outpath_func=self.cfg.outpath,
            name=name,
            fig=fig,
            fmt=fmt,
            dpi=dpi,
            match_screen=match_screen,
            tight=tight,
        )

    # -----------------------------
    # 1) 箱线图
    # -----------------------------
    def boxplot(
        self,
        groups: Dict[str, ArrayLike],
        title: Optional[str] = None,
        ylabel: Optional[str] = None,
        xlabel: Optional[str] = None,
        showfliers: bool = True,
        notch: bool = False,
        vert: bool = True,
        whis: Any = 1.5,
        widths: Optional[float] = None,
        figsize: Tuple[float, float] = (6.0, 4.0),
    ) -> Tuple[plt.Figure, plt.Axes]:
        """箱线图：labels 从 dict 顺序读取；自动去 NaN/Inf。"""
        if not groups:
            raise ValueError("groups 为空")
        labels = list(groups.keys())
        data = [_finite_1d(v) for v in groups.values()]
        if any(len(d) == 0 for d in data):
            raise ValueError("存在空数据组（去除 NaN/Inf 后），请检查输入")

        fig, ax = self._new_subplots(figsize)
        try:
            ax.boxplot(
                data,
                tick_labels=labels,  # mpl 3.7+
                showfliers=showfliers,
                notch=notch,
                vert=vert,
                whis=whis,
                widths=widths,
            )
        except TypeError:
            # 兼容旧版参数名：labels
            ax.boxplot(
                data,
                labels=labels,
                showfliers=showfliers,
                notch=notch,
                vert=vert,
                whis=whis,
                widths=widths,
            )
        _apply_axes_text(ax, title, xlabel, ylabel)
        ax.grid(True, axis="y" if vert else "x", linestyle="--", alpha=0.3)
        ax.margins(x=0.05, y=0.10)
        return fig, ax

    # -----------------------------
    # 2) 小提琴图
    # -----------------------------
    def violin_plot(
        self,
        groups: Dict[str, ArrayLike],
        title: Optional[str] = None,
        ylabel: Optional[str] = None,
        xlabel: Optional[str] = None,
        showmedians: bool = True,
        vert: bool = True,
        figsize: Tuple[float, float] = (6.0, 4.0),
        width: Optional[float] = None,  # 新增：可选宽度；None 时不传给 mpl
    ) -> Tuple[plt.Figure, plt.Axes]:
        """
        稳健版小提琴图（兼容 matplotlib 3.9+）：
        - 当 width 为 None 时，不向 ax.violinplot 传 widths 参数（避免 len(None) 报错）
        - 当 width 为标量或序列时再传递给 widths
        - 组内先做去 NaN/Inf，避免形状异常
        """
        if not groups:
            raise ValueError("groups 为空")
        labels = list(groups.keys())
        data = [_finite_1d(v) for v in groups.values()]
        if any(len(d) == 0 for d in data):
            raise ValueError("存在空数据组（去除 NaN/Inf 后），请检查输入")
        n = len(data)

        fig, ax = self._new_subplots(figsize)

        # 组装 kwargs，避免将 None 传入 widths
        vp_kwargs = dict(showmeans=False, showmedians=showmedians, vert=vert)
        if width is not None:
            vp_kwargs["widths"] = width

        ax.violinplot(data, **vp_kwargs)

        # 位置与坐标刻度
        pos = np.arange(1, n + 1)
        if vert:
            ax.set_xticks(pos)
            ax.set_xticklabels(labels, rotation=0)
            if ylabel:
                ax.set_ylabel(ylabel)
            if xlabel:
                ax.set_xlabel(xlabel)
        else:
            ax.set_yticks(pos)
            ax.set_yticklabels(labels, rotation=0)
            if ylabel:
                ax.set_xlabel(ylabel)
            if xlabel:
                ax.set_ylabel(xlabel)

        if title:
            ax.set_title(title)

        # 样式与边距
        ax.grid(True, axis=("y" if vert else "x"), linestyle="--", alpha=0.3)
        ax.margins(x=0.05, y=0.10)

        return fig, ax

    # -----------------------------
    # 3) 散点 + 拟合
    # -----------------------------
    def scatter_with_fit(
        self,
        x,
        y,
        title: str = "散点 + 拟合",
        xlabel: str = "X",
        ylabel: str = "Y",
        ci: float = 0.95,
        equal: bool = False,
        s: float = 32,  # 点大小
        alpha: float = 0.85,  # 点透明度
        line_lw: float = 2.0,  # 回归线宽
    ) -> Tuple[plt.Figure, plt.Axes, Dict[str, float]]:
        """一元 OLS + Pearson 统计；返回 (fig, ax, stats)。"""
        x = np.asarray(x, dtype=float).ravel()
        y = np.asarray(y, dtype=float).ravel()
        msk = np.isfinite(x) & np.isfinite(y)
        x, y = x[msk], y[msk]
        n = x.size
        if n < 3:
            raise ValueError("样本量过小，至少需要 3 个点")

        # --- OLS ---
        X = np.c_[np.ones_like(x), x]
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        b0, b1 = float(beta[0]), float(beta[1])
        y_hat = b0 + b1 * x
        resid = y - y_hat
        s_err = float(np.sqrt(np.sum(resid ** 2) / max(n - 2, 1)))
        xbar = float(np.mean(x))
        Sxx = float(np.sum((x - xbar) ** 2))

        # Pearson r / p-value（无 SciPy 时 p 近似）
        r = float(np.corrcoef(x, y)[0, 1])
        try:
            from scipy import stats  # type: ignore
            r_p = float(stats.pearsonr(x, y).pvalue)
            t_quant = float(stats.t.ppf(0.5 + ci / 2, n - 2))
        except Exception:
            t_val = r * np.sqrt(max(n - 2, 1) / (1 - r ** 2 + 1e-12))
            from math import erf, sqrt
            r_p = float(2 * (1 - 0.5 * (1 + erf(abs(t_val) / np.sqrt(2)))))
            t_quant = 1.96 if ci >= 0.95 else 1.64

        # --- 平滑绘制用网格 & 置信带（均值预测区间） ---
        xg = np.linspace(x.min(), x.max(), 200)
        yg = b0 + b1 * xg
        se_mean = s_err * np.sqrt(1.0 / n + (xg - xbar) ** 2 / (Sxx + 1e-12))
        ci_lo, ci_hi = yg - t_quant * se_mean, yg + t_quant * se_mean

        # --- 图形 ---
        fig, ax = plt.subplots(figsize=(7.5, 6.5), constrained_layout=True)
        ax.grid(True, linewidth=0.6, alpha=0.35)
        ax.set_axisbelow(True)

        # 置信带先画（在回归线下层）
        if ci and ci > 0:
            ax.fill_between(xg, ci_lo, ci_hi, alpha=0.22)

        # 回归线
        ax.plot(xg, yg, linewidth=line_lw)

        # 点
        ax.scatter(x, y, s=s, alpha=alpha, edgecolors="#1f2937", linewidths=0.4)

        # 等轴 & 1:1 参考线（仅当量纲一致时更直观）
        if equal:
            xmin = min(x.min(), y.min())
            xmax = max(x.max(), y.max())
            span = xmax - xmin
            pad = 0.05 * span
            ax.set_xlim(xmin - pad, xmax + pad)
            ax.set_ylim(xmin - pad, xmax + pad)
            ax.set_aspect("equal", adjustable="box")
            ax.plot([xmin - pad, xmax + pad], [xmin - pad, xmax + pad], linestyle="--", linewidth=1.0, alpha=0.6)

        # 文本信息放在坐标系内左上角，带半透明底
        r2 = r * r
        ax.text(
            0.02,
            0.98,
            f"Pearson r={r: .3f}   R²={r2: .3f}   p={r_p:.2e}",
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=11,
            bbox=dict(facecolor="white", alpha=0.7, edgecolor="none", pad=3.5),
        )

        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)

        stats = {"slope": b1, "intercept": b0, "r": r, "r2": r2, "p": r_p, "n": n}
        return fig, ax, stats

    # -----------------------------
    # 4) 火山图（Robust）
    # -----------------------------
    def volcano_plot(
        self,
        log2fc,
        pvals,
        title: str = "火山图",
        fc_thresh: float = 1.0,
        p_thresh: float = 0.05,
        annotate_top_n: int = 0,
        gene_labels=None,
        fdr: float | None = None,
        ax: Optional[plt.Axes] = None,
    ) -> Tuple[plt.Figure, plt.Axes, Dict[str, Any]]:
        import numpy as np
        import matplotlib.pyplot as plt

        # ---- 统一为 1D ndarray 且长度一致 ----
        x = np.asarray(log2fc, dtype=float).reshape(-1)
        pv = np.asarray(pvals, dtype=float).reshape(-1)
        n = min(x.size, pv.size)
        x, pv = x[:n], pv[:n]

        # 去 NaN
        mask_valid = np.isfinite(x) & np.isfinite(pv)
        x, pv = x[mask_valid], pv[mask_valid]

        # clip，避免 log10(0)
        tiny = np.finfo(float).tiny
        pv = np.clip(pv, tiny, 1.0)

        # 计算 -log10(p)
        neglogp = -np.log10(pv)

        # ---- 计算显著性阈值（优先 FDR-BH） ----
        p_cut_from_fdr = None
        if fdr is not None:
            try:
                order = np.argsort(pv)
                ranks = np.arange(1, pv.size + 1, dtype=float)
                bh_line = (ranks / pv.size) * float(fdr)
                ok = pv[order] <= bh_line
                if np.any(ok):
                    p_cut_from_fdr = float(pv[order][ok].max())
            except Exception:
                p_cut_from_fdr = None

        p_cut = float(p_cut_from_fdr) if p_cut_from_fdr is not None else float(p_thresh)
        neglogp_cut = -np.log10(np.clip(p_cut, tiny, 1.0))

        # ---- 分类着色：上调/下调/非显著 ----
        sig = pv <= p_cut
        up = (x >= fc_thresh) & sig
        dn = (x <= -fc_thresh) & sig
        ns = ~(up | dn)

        # ---- 作图 ----
        if ax is None:
            fig, ax = plt.subplots(figsize=(6.8, 5.2), layout="constrained")
        else:
            fig = ax.figure

        ax.scatter(x[ns], neglogp[ns], s=14, alpha=0.75, color="#9AA3AF", edgecolors="none")
        ax.scatter(x[dn], neglogp[dn], s=18, alpha=0.85, color="#2563EB", edgecolors="none", label="Down")
        ax.scatter(x[up], neglogp[up], s=18, alpha=0.85, color="#DC2626", edgecolors="none", label="Up")

        # 阈值线
        ax.axvline(+fc_thresh, ls="--", lw=1.0, color="#6B7280")
        ax.axvline(-fc_thresh, ls="--", lw=1.0, color="#6B7280")
        ax.axhline(neglogp_cut, ls="--", lw=1.0, color="#6B7280")

        # 轴 & 标题
        ax.set_xlabel("log2 Fold Change")
        ax.set_ylabel("-log10(p)")
        ax.set_title(title or "Volcano Plot")
        ax.legend(frameon=False, loc="upper right")

        # ---- Top-N 标注（按 -log10(p) 从高到低）----
        labels = None
        if gene_labels is not None:
            labels = np.asarray(gene_labels, dtype=object)
            if labels.ndim == 0:
                labels = np.repeat(str(labels), neglogp.size)
            elif labels.size != neglogp.size:
                tmp = np.array([""] * neglogp.size, dtype=object)
                tmp[: min(tmp.size, labels.size)] = labels[: min(tmp.size, labels.size)]
                labels = tmp
        else:
            labels = np.array([f"ID{i}" for i in range(neglogp.size)], dtype=object)

        if annotate_top_n and annotate_top_n > 0:
            idx_sort = np.argsort(neglogp)[::-1]
            k = int(min(annotate_top_n, idx_sort.size))
            for i in idx_sort[:k]:
                ax.text(x[i], neglogp[i], str(labels[i]), fontsize=8, ha="left", va="bottom")

        ax.grid(alpha=0.25, linestyle=":", linewidth=0.8)
        extras = {
            "p_cut": p_cut,
            "neglogp_cut": float(neglogp_cut),
            "n_total": int(neglogp.size),
            "n_up": int(np.sum(up)),
            "n_down": int(np.sum(dn)),
            "n_ns": int(np.sum(ns)),
        }
        return fig, ax, extras

    # -----------------------------
    # 5) 森林图（稳定版）
    # -----------------------------
    def forest_plot(
        self,
        labels: Sequence[str],
        effects: ArrayLike,
        ci_low: ArrayLike,
        ci_high: ArrayLike,
        title: Optional[str] = None,
        xlabel: Optional[str] = None,
        ref_line: float = 0.0,
        weights: Optional[ArrayLike] = None,
        annotate_values: bool = False,
        figsize: Tuple[float, float] = (6.6, 5.0),
    ) -> Tuple[plt.Figure, plt.Axes]:
        """森林图：效应量点 + 95%CI；支持按权重调整点大小。"""
        if weights is None:
            (e, lo, hi), mask = _multi_finite(effects, ci_low, ci_high)
            w = None
        else:
            (e, lo, hi, w), mask = _multi_finite(effects, ci_low, ci_high, weights)

        # e/lo/hi 均为 ndarray；不要再取 [0]
        # 同步过滤 labels
        idx = np.nonzero(mask)[0]
        if len(labels) != mask.size:
            raise ValueError("labels 长度需与数据列一致")
        labels_f = [labels[i] for i in idx]

        n = e.size
        if n == 0:
            raise ValueError("有效数据为空")
        y = np.arange(n)[::-1]

        fig, ax = self._new_subplots(figsize)
        err_left = e - lo
        err_right = hi - e
        # 只画误差棒，不重复画点
        ax.errorbar(e, y, xerr=np.vstack([err_left, err_right]), fmt="none", capsize=3, elinewidth=1.2)
        ax.axvline(ref_line, linestyle="--", alpha=0.5)

        # 权重（点大小）
        if w is not None:
            w_min = float(np.min(w))
            w_range = float(np.ptp(w))  # NumPy 2.0 兼容
            if not np.isfinite(w_min) or w_range <= 1e-12:
                sizes = np.full_like(e, 36 * 0.8, dtype=float)
            else:
                w_norm = (w - w_min) / (w_range + 1e-12)
                sizes = 36 * (0.4 + 0.8 * w_norm)
        else:
            sizes = np.full_like(e, 36.0, dtype=float)
        ax.scatter(e, y, s=sizes, zorder=3)

        if annotate_values:
            for yi, ei, li, hi_ in zip(y, e, lo, hi):
                ax.text(ei, yi, f" {ei:.3g}  [{li:.3g}, {hi_:.3g}]", va="center", ha="left", fontsize=9)

        ax.set_yticks(y)
        ax.set_yticklabels(labels_f)
        _apply_axes_text(ax, title, xlabel or "Effect (95% CI)", None)
        ax.grid(True, axis="x", linestyle=":", alpha=0.25)
        ax.margins(x=0.08, y=0.05)  # 给左右 CI 留余量
        return fig, ax

    # -----------------------------
    # General-purpose 2D charts
    # -----------------------------
    def bar_plot(self, *args, **kwargs):
        return _basic.bar_chart(self, *args, horizontal=True, **kwargs)

    def column_plot(self, *args, **kwargs):
        return _basic.bar_chart(self, *args, horizontal=False, **kwargs)

    def line_plot(self, *args, **kwargs):
        return _basic.line_chart(self, *args, **kwargs)

    def histogram_plot(self, *args, **kwargs):
        return _basic.histogram_chart(self, *args, **kwargs)

    def area_plot(self, *args, **kwargs):
        return _basic.area_chart(self, *args, **kwargs)

    # -----------------------------
    # 6) MA Plot（生物）
    # -----------------------------
    def ma_plot(self, *args, **kwargs):
        return _biomed.ma_plot(self, *args, **kwargs)

    def enrichment_dotplot(self, *args, **kwargs):
        return _biomed.enrichment_dotplot(self, *args, **kwargs)

    def gsea_running_plot(self, *args, **kwargs):
        return _biomed.gsea_running_plot(self, *args, **kwargs)

    def embedding_plot(self, *args, **kwargs):
        return _biomed.embedding_plot(self, *args, **kwargs)

    def upset_plot(self, *args, **kwargs):
        return _biomed.upset_plot(self, *args, **kwargs)

    def kaplan_meier_plot(self, *args, **kwargs):
        return _clinical.kaplan_meier_plot(self, *args, **kwargs)

    def roc_pr_plot(self, *args, **kwargs):
        return _clinical.roc_pr_plot(self, *args, **kwargs)

    def calibration_plot(self, *args, **kwargs):
        return _clinical.calibration_plot(self, *args, **kwargs)

    def bland_altman_plot(self, *args, **kwargs):
        return _clinical.bland_altman_plot(self, *args, **kwargs)

    def decision_curve_plot(self, *args, **kwargs):
        return _clinical.decision_curve_plot(self, *args, **kwargs)

    def stress_strain_plot(self, *args, **kwargs):
        return _materials.stress_strain_plot(self, *args, **kwargs)

    def xrd_plot(self, *args, **kwargs):
        return _materials.xrd_plot(self, *args, **kwargs)

    def raman_plot(self, *args, **kwargs):
        return _materials.raman_plot(self, *args, **kwargs)

    def phase_plot(self, *args, **kwargs):
        return _materials.phase_plot(self, *args, **kwargs)

    def hysteresis_plot(self, *args, **kwargs):
        return _materials.hysteresis_plot(self, *args, **kwargs)

    def spectral_signature_plot(self, *args, **kwargs):
        return _remote.spectral_signature_plot(self, *args, **kwargs)

    def index_time_series_plot(self, *args, **kwargs):
        return _remote.index_time_series_plot(self, *args, **kwargs)

    def confusion_matrix_plot(self, *args, **kwargs):
        return _remote.confusion_matrix_plot(self, *args, **kwargs)

    def class_distribution_plot(self, *args, **kwargs):
        return _remote.class_distribution_plot(self, *args, **kwargs)

    def candlestick_plot(self, *args, **kwargs):
        return _finance.candlestick_plot(self, *args, **kwargs)

    def cum_return_drawdown_plot(self, *args, **kwargs):
        return _finance.cum_return_drawdown_plot(self, *args, **kwargs)

    def rolling_stats_plot(self, *args, **kwargs):
        return _finance.rolling_stats_plot(self, *args, **kwargs)

    def efficient_frontier_plot(self, *args, **kwargs):
        return _finance.efficient_frontier_plot(self, *args, **kwargs)

    def acf_pacf_plot(self, *args, **kwargs):
        return _finance.acf_pacf_plot(self, *args, **kwargs)

    def likert_plot(self, *args, **kwargs):
        return _psych.likert_plot(self, *args, **kwargs)

    def raincloud_plot(self, *args, **kwargs):
        return _psych.raincloud_plot(self, *args, **kwargs)

    def irt_icc_plot(self, *args, **kwargs):
        return _psych.irt_icc_plot(self, *args, **kwargs)

    def factor_loadings_plot(self, *args, **kwargs):
        return _psych.factor_loadings_plot(self, *args, **kwargs)

    def interaction_plot(self, *args, **kwargs):
        return _psych.interaction_plot(self, *args, **kwargs)

# -----------------------------
# 函数式 API（向后兼容）
# -----------------------------
_default_plotter: Optional[StaticAnalysisPlotter] = None


def _get_default_plotter() -> StaticAnalysisPlotter:
    global _default_plotter
    if _default_plotter is None:
        _default_plotter = StaticAnalysisPlotter()
    return _default_plotter


def boxplot(*args, **kwargs):
    return _get_default_plotter().boxplot(*args, **kwargs)


def violin_plot(*args, **kwargs):
    return _get_default_plotter().violin_plot(*args, **kwargs)


def scatter_with_fit(*args, **kwargs):
    return _get_default_plotter().scatter_with_fit(*args, **kwargs)


def volcano_plot(*args, **kwargs):
    return _get_default_plotter().volcano_plot(*args, **kwargs)


def forest_plot(*args, **kwargs):
    return _get_default_plotter().forest_plot(*args, **kwargs)


def bar_plot(*args, **kwargs):
    return _get_default_plotter().bar_plot(*args, **kwargs)


def column_plot(*args, **kwargs):
    return _get_default_plotter().column_plot(*args, **kwargs)


def line_plot(*args, **kwargs):
    return _get_default_plotter().line_plot(*args, **kwargs)


def histogram_plot(*args, **kwargs):
    return _get_default_plotter().histogram_plot(*args, **kwargs)


def area_plot(*args, **kwargs):
    return _get_default_plotter().area_plot(*args, **kwargs)


def ma_plot(*args, **kwargs):
    return _get_default_plotter().ma_plot(*args, **kwargs)


def enrichment_dotplot(*args, **kwargs):
    return _get_default_plotter().enrichment_dotplot(*args, **kwargs)


def gsea_running_plot(*args, **kwargs):
    return _get_default_plotter().gsea_running_plot(*args, **kwargs)


def embedding_plot(*args, **kwargs):
    return _get_default_plotter().embedding_plot(*args, **kwargs)


def upset_plot(*args, **kwargs):
    return _get_default_plotter().upset_plot(*args, **kwargs)


def kaplan_meier_plot(*args, **kwargs):
    return _get_default_plotter().kaplan_meier_plot(*args, **kwargs)


def roc_pr_plot(*args, **kwargs):
    return _get_default_plotter().roc_pr_plot(*args, **kwargs)


def calibration_plot(*args, **kwargs):
    return _get_default_plotter().calibration_plot(*args, **kwargs)


def bland_altman_plot(*args, **kwargs):
    return _get_default_plotter().bland_altman_plot(*args, **kwargs)


def decision_curve_plot(*args, **kwargs):
    return _get_default_plotter().decision_curve_plot(*args, **kwargs)


def stress_strain_plot(*args, **kwargs):
    return _get_default_plotter().stress_strain_plot(*args, **kwargs)


def xrd_plot(*args, **kwargs):
    return _get_default_plotter().xrd_plot(*args, **kwargs)


def raman_plot(*args, **kwargs):
    return _get_default_plotter().raman_plot(*args, **kwargs)


def phase_plot(*args, **kwargs):
    return _get_default_plotter().phase_plot(*args, **kwargs)


def hysteresis_plot(*args, **kwargs):
    return _get_default_plotter().hysteresis_plot(*args, **kwargs)


def spectral_signature_plot(*args, **kwargs):
    return _get_default_plotter().spectral_signature_plot(*args, **kwargs)


def index_time_series_plot(*args, **kwargs):
    return _get_default_plotter().index_time_series_plot(*args, **kwargs)


def confusion_matrix_plot(*args, **kwargs):
    return _get_default_plotter().confusion_matrix_plot(*args, **kwargs)


def class_distribution_plot(*args, **kwargs):
    return _get_default_plotter().class_distribution_plot(*args, **kwargs)


def candlestick_plot(*args, **kwargs):
    return _get_default_plotter().candlestick_plot(*args, **kwargs)


def cum_return_drawdown_plot(*args, **kwargs):
    return _get_default_plotter().cum_return_drawdown_plot(*args, **kwargs)


def rolling_stats_plot(*args, **kwargs):
    return _get_default_plotter().rolling_stats_plot(*args, **kwargs)


def efficient_frontier_plot(*args, **kwargs):
    return _get_default_plotter().efficient_frontier_plot(*args, **kwargs)


def acf_pacf_plot(*args, **kwargs):
    return _get_default_plotter().acf_pacf_plot(*args, **kwargs)


def likert_plot(*args, **kwargs):
    return _get_default_plotter().likert_plot(*args, **kwargs)


def raincloud_plot(*args, **kwargs):
    return _get_default_plotter().raincloud_plot(*args, **kwargs)


def irt_icc_plot(*args, **kwargs):
    return _get_default_plotter().irt_icc_plot(*args, **kwargs)


def factor_loadings_plot(*args, **kwargs):
    return _get_default_plotter().factor_loadings_plot(*args, **kwargs)


def interaction_plot(*args, **kwargs):
    return _get_default_plotter().interaction_plot(*args, **kwargs)


# -----------------------------
# Demo（仅用于快速自测）
# -----------------------------
if __name__ == "__main__":
    rng = np.random.default_rng(42)
    p = StaticAnalysisPlotter()  # 从 .env 加载并应用 PlotConfig

    # 1) Boxplot
    box_data = {
        "Ctrl": rng.normal(0, 1, 80),
        "TreatA": rng.normal(0.4, 1.1, 90),
        "TreatB": rng.normal(-0.2, 0.9, 85),
    }
    fig1, ax1 = p.boxplot(box_data, title="箱线图演示", ylabel="Value")
    p.save(fig=fig1)

    # 2) Violin
    fig2, ax2 = p.violin_plot(box_data, title="Violin Demo", ylabel="Value")
    p.save(fig=fig2)

    # 3) Scatter + Fit
    x = rng.normal(0, 1, 120)
    y = 1.5 * x + 0.6 + rng.normal(0, 0.8, 120)
    fig3, ax3, stats = p.scatter_with_fit(x, y, title="Scatter + Fit", xlabel="X", ylabel="Y", ci=0.95)
    print("Scatter stats:", stats)
    p.save(fig=fig3)

    # 4) Volcano
    log2fc = rng.normal(0, 1, 400)
    pvals = rng.uniform(0, 1, 400) ** 3
    genes = [f"G{i}" for i in range(400)]
    fig4, ax4, extra = p.volcano_plot(log2fc, pvals, title="Volcano Demo", annotate_top_n=8, gene_labels=genes, fdr=0.1)
    print("Volcano info:", extra)
    p.save(fig=fig4)

    # 5) Forest
    k = 8
    eff = rng.normal(0.1, 0.25, k)
    ci_w = rng.uniform(0.15, 0.45, k)
    lo = eff - ci_w
    hi = eff + ci_w
    labs = [f"Study {i + 1}" for i in range(k)]
    fig5, ax5 = p.forest_plot(labs, eff, lo, hi, title="Forest Demo", xlabel="Effect (95% CI)", ref_line=0.0, annotate_values=True)
    p.save(fig=fig5)

    plt.show()
