from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt

from src.chart.plot_2d.static_analysis import _apply_axes_text
from src.util.dependency_hints import format_missing_dependency

def kaplan_meier_plot(
    self,
    time: ArrayLike,
    event: ArrayLike,
    group: Optional[ArrayLike] = None,
    title: Optional[str] = None,
    risk_table: bool = True,
    figsize: Tuple[float, float] = (7.2, 5.8),
) -> Tuple[plt.Figure, plt.Axes]:
    t = np.asarray(time, dtype=float).ravel()
    e = np.asarray(event, dtype=float).ravel()
    n = min(t.size, e.size)
    t, e = t[:n], e[:n]
    mask = np.isfinite(t) & np.isfinite(e)
    t, e = t[mask], e[mask].astype(int)

    def _km(tt, ee):
        order = np.argsort(tt)
        tt, ee = tt[order], ee[order]
        uniq = np.unique(tt[ee == 1])
        surv = 1.0
        xs = [0.0]
        ys = [1.0]
        for u in uniq:
            d = np.sum((tt == u) & (ee == 1))
            n_at = np.sum(tt >= u)
            if n_at > 0:
                surv *= (1.0 - d / n_at)
                xs.append(u)
                ys.append(surv)
        return np.asarray(xs), np.asarray(ys)

    if group is None:
        fig, ax = self._new_subplots(figsize)
        xs, ys = _km(t, e)
        ax.step(xs, ys, where="post", lw=2.0, color="#2563EB", label="All")
    else:
        g = np.asarray(group)[mask]
        uniq = list(dict.fromkeys(g.tolist()))
        if risk_table:
            import matplotlib.gridspec as gridspec
            fig = plt.figure(figsize=figsize)
            gs = gridspec.GridSpec(2, 1, height_ratios=[3.5, 1.2], hspace=0.05)
            ax = fig.add_subplot(gs[0])
            ax_tbl = fig.add_subplot(gs[1])
        else:
            fig, ax = self._new_subplots(figsize)
            ax_tbl = None
        for u in uniq:
            m = g == u
            xs, ys = _km(t[m], e[m])
            ax.step(xs, ys, where="post", lw=2.0, label=str(u))

        if risk_table and ax_tbl is not None:
            ax_tbl.axis("off")
            t_min, t_max = float(np.min(t)), float(np.max(t))
            time_points = np.linspace(t_min, t_max, 5)
            cell_text = []
            for u in uniq:
                m = g == u
                counts = [int(np.sum(t[m] >= tp)) for tp in time_points]
                cell_text.append([str(c) for c in counts])
            ax_tbl.table(
                cellText=cell_text,
                rowLabels=[str(u) for u in uniq],
                colLabels=[f"{tp: .1f}" for tp in time_points],
                loc="center",
            )

    ax.set_xlabel("Time")
    ax.set_ylabel("Survival")
    if title:
        ax.set_title(title)
    ax.set_ylim(0, 1.02)
    ax.grid(alpha=0.25, linestyle=":")
    ax.legend(frameon=False, fontsize=9)
    return fig, ax

# -----------------------------
# 12) ROC / PR（临床）
# -----------------------------

def roc_pr_plot(
    self,
    y_true: ArrayLike,
    y_score: ArrayLike,
    curve: str = "roc",
    pos_label: Optional[str] = None,
    title: Optional[str] = None,
    figsize: Tuple[float, float] = (6.4, 5.0),
) -> Tuple[plt.Figure, plt.Axes, Dict[str, float]]:
    yt = np.asarray(y_true)
    ys = np.asarray(y_score, dtype=float).ravel()
    n = min(yt.size, ys.size)
    yt, ys = yt[:n], ys[:n]
    mask = np.isfinite(ys)
    yt, ys = yt[mask], ys[mask]

    if pos_label is None:
        if yt.dtype == bool:
            yb = yt.astype(int)
        else:
            uniq = np.unique(yt)
            if uniq.size == 2:
                yb = (yt == uniq[1]).astype(int)
            else:
                yb = (yt == 1).astype(int)
    else:
        yb = (yt == pos_label).astype(int)

    def _trapezoidal_area(y_values, x_values) -> float:
        y_array = np.asarray(y_values, dtype=float)
        x_array = np.asarray(x_values, dtype=float)
        if hasattr(np, "trapezoid"):
            return float(np.trapezoid(y_array, x_array))
        if x_array.size < 2:
            return 0.0
        return float(np.sum(np.diff(x_array) * (y_array[1:] + y_array[:-1]) * 0.5))

    curve = curve.lower()
    try:
        from sklearn import metrics  # type: ignore
        if curve == "roc":
            fpr, tpr, _ = metrics.roc_curve(yb, ys)
            auc = float(metrics.auc(fpr, tpr))
        else:
            tpr, fpr, _ = metrics.precision_recall_curve(yb, ys)
            auc = float(metrics.auc(fpr, tpr))
    except Exception:
        order = np.argsort(ys)[::-1]
        yb = yb[order]
        tps = np.cumsum(yb)
        fps = np.cumsum(1 - yb)
        if curve == "roc":
            tpr = tps / max(1, tps[-1])
            fpr = fps / max(1, fps[-1])
            auc = _trapezoidal_area(tpr, fpr)
        else:
            recall = tps / max(1, tps[-1])
            precision = tps / np.maximum(1, tps + fps)
            fpr, tpr = recall, precision
            auc = _trapezoidal_area(tpr, fpr)

    fig, ax = self._new_subplots(figsize)
    ax.plot(fpr, tpr, lw=2.0, color="#2563EB", label=f"AUC={auc:.3f}")
    if curve == "roc":
        ax.plot([0, 1], [0, 1], ls="--", lw=1.0, color="#9CA3AF")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
    else:
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1.02)
    if title:
        ax.set_title(title)
    ax.legend(frameon=False)
    ax.grid(alpha=0.2, linestyle=":")
    return fig, ax, {"auc": auc}

# -----------------------------
# 13) Calibration（临床）
# -----------------------------

def calibration_plot(
    self,
    y_true: ArrayLike,
    y_prob: ArrayLike,
    n_bins: int = 10,
    strategy: str = "uniform",
    title: Optional[str] = None,
    figsize: Tuple[float, float] = (6.0, 5.0),
) -> Tuple[plt.Figure, plt.Axes]:
    yt = np.asarray(y_true).astype(int).ravel()
    yp = np.asarray(y_prob, dtype=float).ravel()
    n = min(yt.size, yp.size)
    yt, yp = yt[:n], yp[:n]
    mask = np.isfinite(yp)
    yt, yp = yt[mask], yp[mask]

    try:
        from sklearn.calibration import calibration_curve  # type: ignore
        prob_true, prob_pred = calibration_curve(yt, yp, n_bins=n_bins, strategy=strategy)
    except Exception:
        order = np.argsort(yp)
        yp, yt = yp[order], yt[order]
        if strategy == "quantile":
            bins = np.array_split(np.arange(len(yp)), n_bins)
        else:
            bins = np.array_split(np.arange(len(yp)), n_bins)
        prob_true, prob_pred = [], []
        for b in bins:
            if b.size == 0:
                continue
            prob_pred.append(float(np.mean(yp[b])))
            prob_true.append(float(np.mean(yt[b])))
        prob_true = np.asarray(prob_true)
        prob_pred = np.asarray(prob_pred)

    fig, ax = self._new_subplots(figsize)
    ax.plot(prob_pred, prob_true, marker="o", color="#2563EB")
    ax.plot([0, 1], [0, 1], ls="--", color="#9CA3AF", lw=1.0)
    ax.set_xlabel("Predicted Probability")
    ax.set_ylabel("Observed Frequency")
    if title:
        ax.set_title(title)
    ax.grid(alpha=0.2, linestyle=":")
    return fig, ax

# -----------------------------
# 14) Bland-Altman（临床）
# -----------------------------

def bland_altman_plot(
    self,
    x: ArrayLike,
    y: ArrayLike,
    title: Optional[str] = None,
    xlabel: str = "Mean",
    ylabel: str = "Difference",
    figsize: Tuple[float, float] = (6.4, 5.0),
) -> Tuple[plt.Figure, plt.Axes]:
    x = np.asarray(x, dtype=float).ravel()
    y = np.asarray(y, dtype=float).ravel()
    n = min(x.size, y.size)
    x, y = x[:n], y[:n]
    mask = np.isfinite(x) & np.isfinite(y)
    x, y = x[mask], y[mask]
    m = (x + y) / 2.0
    d = x - y
    md = float(np.mean(d))
    sd = float(np.std(d, ddof=1))
    fig, ax = self._new_subplots(figsize)
    ax.scatter(m, d, s=18, alpha=0.75, color="#2563EB")
    ax.axhline(md, color="#111827", lw=1.2)
    ax.axhline(md + 1.96 * sd, color="#6B7280", ls="--", lw=1.0)
    ax.axhline(md - 1.96 * sd, color="#6B7280", ls="--", lw=1.0)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    if title:
        ax.set_title(title)
    ax.grid(alpha=0.2, linestyle=":")
    return fig, ax

# -----------------------------
# 15) Decision Curve（临床）
# -----------------------------

def decision_curve_plot(
    self,
    y_true: ArrayLike,
    y_prob: ArrayLike,
    thresholds: Optional[ArrayLike] = None,
    title: Optional[str] = None,
    figsize: Tuple[float, float] = (6.6, 5.0),
) -> Tuple[plt.Figure, plt.Axes]:
    yt = np.asarray(y_true).astype(int).ravel()
    yp = np.asarray(y_prob, dtype=float).ravel()
    n = min(yt.size, yp.size)
    yt, yp = yt[:n], yp[:n]
    mask = np.isfinite(yp)
    yt, yp = yt[mask], yp[mask]

    if thresholds is None:
        thr = np.linspace(0.01, 0.99, 50)
    else:
        thr = np.asarray(thresholds, dtype=float).ravel()
        thr = thr[(thr > 0) & (thr < 1)]
    net_benefit = []
    treat_all = []
    prevalence = float(np.mean(yt)) if yt.size else 0.0
    for t in thr:
        pred = yp >= t
        tp = np.sum(pred & (yt == 1))
        fp = np.sum(pred & (yt == 0))
        nb = tp / len(yt) - fp / len(yt) * (t / (1 - t))
        net_benefit.append(nb)
        treat_all.append(prevalence - (1 - prevalence) * (t / (1 - t)))

    fig, ax = self._new_subplots(figsize)
    ax.plot(thr, net_benefit, label="Model", color="#2563EB")
    ax.plot(thr, treat_all, label="Treat All", color="#9CA3AF", ls="--")
    ax.axhline(0, color="#111827", lw=1.0, alpha=0.5, label="Treat None")
    ax.set_xlabel("Threshold Probability")
    ax.set_ylabel("Net Benefit")
    if title:
        ax.set_title(title)
    ax.legend(frameon=False)
    ax.grid(alpha=0.2, linestyle=":")
    return fig, ax

# -----------------------------
# 16) Stress-Strain（材料）
# -----------------------------

