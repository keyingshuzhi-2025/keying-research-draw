from __future__ import annotations

from pathlib import Path

import numpy as np

from src.dispatch.handlers.base import HandlerContext, HandlerResult
from src.loaders.data_loader import (
    parse_group_arg,
    parse_label_list,
    parse_numeric_list,
    read_dataframe,
    auto_sep,
)


class Static2DHandler:
    key = "static2d"

    def __init__(self, ctx: HandlerContext) -> None:
        self.ctx = ctx
        self.args = ctx.args

    def render(self, plot_key: str, mode: str) -> HandlerResult:
        if self.ctx.static_plotter_cls is None:
            raise ImportError("二维统计绘图模块未找到。")

        plotter = self.ctx.static_plotter_cls()
        if mode == "demo":
            rendered = self._render_demo(plotter, plot_key)
        elif mode == "custom":
            rendered = self._render_custom(plotter, plot_key)
        elif mode == "file":
            rendered = self._render_file(plotter, plot_key)
        else:
            raise ValueError(f"未知模式 / Unknown mode: {self.args.mode}")
        return HandlerResult(plotter=plotter, rendered=rendered, plot_key=plot_key, title=self.args.title)

    def _basic_style(self):
        return {
            "aggregation": self.args.aggregation,
            "palette": self.args.palette,
            "grid": self.args.grid,
        }

    @staticmethod
    def _parse_basic_x(raw: str):
        try:
            return parse_numeric_list(raw)
        except (TypeError, ValueError):
            return parse_label_list(raw)

    def _render_basic_chart(self, plotter, plot_key: str, x, y, groups=None, xlabel=None, ylabel=None):
        style = self._basic_style()
        title = self.args.title
        xlabel = xlabel or self.args.xlabel
        ylabel = ylabel or self.args.ylabel
        if plot_key in {"bar", "column"}:
            chart = plotter.bar_plot if plot_key == "bar" else plotter.column_plot
            return chart(
                x,
                y,
                groups=groups,
                title=title or ("条形图" if plot_key == "bar" else "柱状图"),
                xlabel=xlabel,
                ylabel=ylabel,
                group_mode=self.args.group_mode,
                show_values=self.args.show_values,
                tick_rotation=self.args.tick_rotation,
                **style,
            )
        if plot_key == "line":
            return plotter.line_plot(
                x,
                y,
                groups=groups,
                title=title or "折线图",
                xlabel=xlabel,
                ylabel=ylabel,
                marker=self.args.marker,
                line_width=self.args.line_width,
                **style,
            )
        if plot_key == "area":
            return plotter.area_plot(
                x,
                y,
                groups=groups,
                title=title or "面积图",
                xlabel=xlabel,
                ylabel=ylabel,
                stacked=self.args.stacked,
                alpha=self.args.area_alpha,
                **style,
            )
        if plot_key == "histogram":
            values = [y]
            series_labels = None
            if groups is not None:
                group_values = np.asarray(groups, dtype=object)
                group_names = list(
                    dict.fromkeys(
                        str(value)
                        for value in group_values
                        if value is not None
                        and not (isinstance(value, (float, np.floating)) and not np.isfinite(value))
                    )
                )
                values = [
                    np.asarray(y, dtype=float)[np.asarray([str(value) == name for value in group_values])]
                    for name in group_names
                ]
                series_labels = group_names
            return plotter.histogram_plot(
                values,
                labels=series_labels,
                title=title or "直方图",
                xlabel=xlabel or "Value",
                ylabel=ylabel,
                bins=self.args.bins,
                density=self.args.density,
                alpha=self.args.hist_alpha,
                palette=self.args.palette,
                grid=self.args.grid,
            )
        raise ValueError(f"未知基础二维图类型：{plot_key}")

    def _render_demo(self, plotter, plot_key: str):
        rng = np.random.default_rng(int(self.args.seed or 42))
        title = self.args.title
        if plot_key in {"bar", "column", "line", "histogram", "area"}:
            if plot_key in {"bar", "column"}:
                categories = np.asarray(["春", "夏", "秋", "冬"] * 2)
                groups = np.asarray(["实验组"] * 4 + ["对照组"] * 4)
                y = np.asarray([18, 26, 21, 30, 15, 22, 19, 25], dtype=float)
                return self._render_basic_chart(plotter, plot_key, categories, y, groups=groups)
            if plot_key in {"line", "area"}:
                x = np.tile(np.arange(1, 13), 2)
                groups = np.asarray(["实验组"] * 12 + ["对照组"] * 12)
                trend = np.asarray([12, 15, 13, 18, 22, 20, 24, 23, 28, 26, 31, 35], dtype=float)
                y = np.concatenate((trend, trend * 0.78 + rng.normal(0, 1.2, trend.size)))
                return self._render_basic_chart(plotter, plot_key, x, y, groups=groups)
            x = None
            y = np.concatenate((rng.normal(0, 1, 180), rng.normal(1.1, 1.2, 180)))
            groups = np.asarray(["对照组"] * 180 + ["实验组"] * 180)
            return self._render_basic_chart(plotter, plot_key, x, y, groups=groups)
        if plot_key in {"box", "violin"}:
            groups = {
                "Ctrl": rng.normal(0, 1, 80),
                "TreatA": rng.normal(0.4, 1.1, 90),
                "TreatB": rng.normal(-0.2, 0.9, 85),
            }
            if plot_key == "box":
                return plotter.boxplot(groups, title=title or "箱线图演示", ylabel=self.args.ylabel or "Value", xlabel=self.args.xlabel)
            return plotter.violin_plot(groups, title=title or "小提琴图演示", ylabel=self.args.ylabel or "Value", xlabel=self.args.xlabel)

        if plot_key == "scatter":
            x = rng.normal(0, 1, 120)
            y = 1.5 * x + 0.6 + rng.normal(0, 0.8, 120)
            return plotter.scatter_with_fit(
                x,
                y,
                title=title or "散点 + 拟合",
                xlabel=self.args.xlabel or "X",
                ylabel=self.args.ylabel or "Y",
                ci=float(self.args.ci or 0.95),
                equal=bool(self.args.equal),
            )

        if plot_key == "volcano":
            log2fc = rng.normal(0, 1, 400)
            pvals = rng.uniform(0, 1, 400) ** 3
            genes = [f"G{i}" for i in range(400)]
            return plotter.volcano_plot(
                log2fc,
                pvals,
                title=title or "火山图演示",
                fc_thresh=self.args.fc_thresh,
                p_thresh=self.args.p_thresh,
                annotate_top_n=self.args.top_n,
                gene_labels=genes,
                fdr=self.args.fdr,
            )

        if plot_key == "forest":
            k = 8
            eff = rng.normal(0.1, 0.25, k)
            ci_w = rng.uniform(0.15, 0.45, k)
            lo = eff - ci_w
            hi = eff + ci_w
            labs = [f"Study {i + 1}" for i in range(k)]
            return plotter.forest_plot(
                labs,
                eff,
                lo,
                hi,
                title=title or "森林图演示",
                xlabel=self.args.xlabel or "Effect (95% CI)",
                ref_line=self.args.ref_line,
            )
        raise ValueError(f"未知图类型 / Unknown plot: {self.args.plot}")

    def _render_custom(self, plotter, plot_key: str):
        title = self.args.title
        if plot_key in {"bar", "column"}:
            if not self.args.y:
                raise ValueError(f"自定义{('条形图' if plot_key == 'bar' else '柱状图')}需要 --y；可用 --labels 指定类别名称")
            y = parse_numeric_list(self.args.y)
            labels = parse_label_list(self.args.labels) if self.args.labels else [f"类别 {i + 1}" for i in range(len(y))]
            if len(labels) != len(y):
                raise ValueError("--labels 与 --y 的项目数必须一致。")
            return self._render_basic_chart(plotter, plot_key, labels, y)
        if plot_key in {"line", "area"}:
            if not (self.args.x and self.args.y):
                raise ValueError(f"自定义{('折线图' if plot_key == 'line' else '面积图')}需要 --x 与 --y")
            x = self._parse_basic_x(self.args.x)
            y = parse_numeric_list(self.args.y)
            return self._render_basic_chart(plotter, plot_key, x, y)
        if plot_key == "histogram":
            if not self.args.y:
                raise ValueError("自定义直方图需要 --y 提供数值数组。")
            y = parse_numeric_list(self.args.y)
            return self._render_basic_chart(plotter, plot_key, None, y)
        if plot_key in {"box", "violin"}:
            if not self.args.group:
                raise ValueError("自定义箱线图/小提琴图需要至少一个 --group 'Label: 1,2,3'")
            groups = {}
            for g in self.args.group:
                label, arr = parse_group_arg(g)
                groups[label] = arr
            if plot_key == "box":
                return plotter.boxplot(groups, title=title or "箱线图", ylabel=self.args.ylabel, xlabel=self.args.xlabel)
            return plotter.violin_plot(groups, title=title or "小提琴图", ylabel=self.args.ylabel, xlabel=self.args.xlabel)

        if plot_key == "scatter":
            if not (self.args.x and self.args.y):
                raise ValueError("自定义散点图需要 --x 与 --y")
            x = parse_numeric_list(self.args.x)
            y = parse_numeric_list(self.args.y)
            return plotter.scatter_with_fit(
                x,
                y,
                title=title or "散点图",
                xlabel=self.args.xlabel or "X",
                ylabel=self.args.ylabel or "Y",
                ci=float(self.args.ci or 0.95),
                equal=bool(self.args.equal),
            )

        if plot_key == "volcano":
            if not (self.args.log2fc and self.args.pvals):
                raise ValueError("自定义火山图需要 --log2fc 与 --pvals")
            x = parse_numeric_list(self.args.log2fc)
            pv = parse_numeric_list(self.args.pvals)
            labels = parse_label_list(self.args.labels) if self.args.labels else None
            return plotter.volcano_plot(
                x,
                pv,
                title=title or "火山图",
                fc_thresh=self.args.fc_thresh,
                p_thresh=self.args.p_thresh,
                annotate_top_n=self.args.top_n,
                gene_labels=labels,
                fdr=self.args.fdr,
            )

        if plot_key == "forest":
            required = (self.args.forest_labels, self.args.effects, self.args.ci_low, self.args.ci_high)
            if not all(required):
                raise ValueError("自定义森林图需要 --forest-labels --effects --ci-low --ci-high")
            labels = parse_label_list(self.args.forest_labels)
            eff = parse_numeric_list(self.args.effects)
            lo = parse_numeric_list(self.args.ci_low)
            hi = parse_numeric_list(self.args.ci_high)
            w = parse_numeric_list(self.args.weights) if self.args.weights else None
            return plotter.forest_plot(
                labels,
                eff,
                lo,
                hi,
                title=title or "森林图",
                xlabel=self.args.xlabel or "Effect (95% CI)",
                ref_line=self.args.ref_line,
                weights=w,
            )
        raise ValueError(f"未知图类型 / Unknown plot: {self.args.plot}")

    def _render_file(self, plotter, plot_key: str):
        if not self.args.file:
            raise ValueError("--mode file 需要提供 --file")
        path = Path(self.args.file).expanduser().resolve()
        sep = auto_sep(path, self.args.sep)
        df = read_dataframe(path, sep)
        title = self.args.title

        if plot_key in {"bar", "column", "line", "area"}:
            if not (self.args.x_col and self.args.y_col):
                raise ValueError(f"文件模式{plot_key}图需要 --x-col 与 --y-col")
            groups = df[self.args.group_col].values if self.args.group_col else None
            xlabel = self.args.xlabel or (
                self.args.y_col if plot_key == "bar" else self.args.x_col
            )
            ylabel = self.args.ylabel or (
                self.args.x_col if plot_key == "bar" else self.args.y_col
            )
            return self._render_basic_chart(
                plotter,
                plot_key,
                df[self.args.x_col].values,
                df[self.args.y_col].values,
                groups=groups,
                xlabel=xlabel,
                ylabel=ylabel,
            )

        if plot_key == "histogram":
            if not self.args.value_col:
                raise ValueError("文件模式直方图需要 --value-col 指定数值列。")
            groups = df[self.args.group_col].values if self.args.group_col else None
            return self._render_basic_chart(
                plotter,
                plot_key,
                None,
                df[self.args.value_col].values,
                groups=groups,
                xlabel=self.args.value_col,
            )

        if plot_key in {"box", "violin"}:
            if self.args.group_col and self.args.value_col:
                groups = {
                    g: df[df[self.args.group_col] == g][self.args.value_col].dropna().values
                    for g in df[self.args.group_col].dropna().unique()
                }
            else:
                numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
                if not numeric_cols:
                    raise ValueError("未检测到数值列，请提供 --group-col 与 --value-col")
                groups = {col: df[col].dropna().values for col in numeric_cols}
            if plot_key == "box":
                return plotter.boxplot(groups, title=title or "箱线图", ylabel=self.args.ylabel, xlabel=self.args.xlabel)
            return plotter.violin_plot(groups, title=title or "小提琴图", ylabel=self.args.ylabel, xlabel=self.args.xlabel)

        if plot_key == "scatter":
            if not (self.args.x_col and self.args.y_col):
                raise ValueError("文件模式散点图需要 --x-col 与 --y-col")
            return plotter.scatter_with_fit(
                df[self.args.x_col].values,
                df[self.args.y_col].values,
                title=title or "散点图",
                xlabel=self.args.xlabel or self.args.x_col,
                ylabel=self.args.ylabel or self.args.y_col,
                ci=float(self.args.ci or 0.95),
                equal=bool(self.args.equal),
            )

        if plot_key == "volcano":
            if not (self.args.log2fc_col and self.args.p_col):
                raise ValueError("文件模式火山图需要 --log2fc-col 与 --p-col")
            labels = df[self.args.label_col].astype(str).values if self.args.label_col and self.args.label_col in df.columns else None
            return plotter.volcano_plot(
                df[self.args.log2fc_col].values,
                df[self.args.p_col].values,
                title=title or "火山图",
                fc_thresh=self.args.fc_thresh,
                p_thresh=self.args.p_thresh,
                annotate_top_n=self.args.top_n,
                gene_labels=labels,
                fdr=self.args.fdr,
            )

        if plot_key == "forest":
            for col in (self.args.forest_label_col, self.args.effect_col, self.args.ci_low_col, self.args.ci_high_col):
                if not col:
                    raise ValueError("文件模式森林图需要 --forest-label-col --effect-col --ci-low-col --ci-high-col")
            weights = df[self.args.weight_col].values if self.args.weight_col and self.args.weight_col in df.columns else None
            return plotter.forest_plot(
                df[self.args.forest_label_col].astype(str).values,
                df[self.args.effect_col].values,
                df[self.args.ci_low_col].values,
                df[self.args.ci_high_col].values,
                title=title or "森林图",
                xlabel=self.args.xlabel or "Effect (95% CI)",
                ref_line=self.args.ref_line,
                weights=weights,
            )
        raise ValueError(f"未知图类型 / Unknown plot: {self.args.plot}")
