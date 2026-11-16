"""General-purpose 2D charts shared by the CLI, Web UI, and MCP server."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable, Sequence

import numpy as np


_DEFAULT_PALETTE = "tab10"


def _is_missing(value: Any) -> bool:
    if value is None:
        return True
    try:
        return bool(np.isscalar(value) and np.isnan(value))
    except (TypeError, ValueError):
        return False


def _clean_vectors(x: Sequence[Any], y: Sequence[Any], groups: Sequence[Any] | None = None):
    x_values = np.asarray(x, dtype=object).reshape(-1)
    y_values = np.asarray(y, dtype=object).reshape(-1)
    if x_values.size != y_values.size:
        raise ValueError("X 与 Y 数据长度必须一致。")
    group_values = None if groups is None else np.asarray(groups, dtype=object).reshape(-1)
    if group_values is not None and group_values.size != x_values.size:
        raise ValueError("分组列与 X/Y 数据长度必须一致。")

    clean_x: list[Any] = []
    clean_y: list[float] = []
    clean_groups: list[str | None] = []
    for index, (x_value, y_value) in enumerate(zip(x_values, y_values)):
        if _is_missing(x_value):
            continue
        try:
            numeric_y = float(y_value)
        except (TypeError, ValueError):
            continue
        if not np.isfinite(numeric_y):
            continue
        group_value = None if group_values is None else group_values[index]
        if group_values is not None and _is_missing(group_value):
            continue
        clean_x.append(x_value)
        clean_y.append(numeric_y)
        clean_groups.append(None if group_value is None else str(group_value))
    if not clean_x:
        raise ValueError("没有可绘制的有效数值。")
    return clean_x, np.asarray(clean_y, dtype=float), clean_groups


def _ordered_categories(values: Iterable[Any]) -> list[Any]:
    categories = list(dict.fromkeys(values))
    try:
        return sorted(categories, key=lambda value: float(value))
    except (TypeError, ValueError):
        pass
    try:
        parsed = [(datetime.fromisoformat(str(value).replace("Z", "+00:00")), value) for value in categories]
        return [value for _, value in sorted(parsed, key=lambda item: item[0])]
    except (TypeError, ValueError):
        return categories


def _aggregate(
    x: Sequence[Any],
    y: Sequence[Any],
    groups: Sequence[Any] | None,
    aggregation: str,
):
    clean_x, clean_y, clean_groups = _clean_vectors(x, y, groups)
    method = str(aggregation or "mean").lower()
    if method not in {"mean", "median", "sum"}:
        raise ValueError("aggregation 仅支持 mean、median 或 sum。")

    categories = _ordered_categories(clean_x)
    series = list(dict.fromkeys(clean_groups))
    values: dict[tuple[Any, str | None], list[float]] = {}
    for x_value, y_value, group_value in zip(clean_x, clean_y, clean_groups):
        values.setdefault((x_value, group_value), []).append(float(y_value))

    def reduce(items: list[float]) -> float:
        if method == "sum":
            return float(np.sum(items))
        if method == "median":
            return float(np.median(items))
        return float(np.mean(items))

    matrix = {
        group: np.asarray(
            [reduce(values[(category, group)]) if (category, group) in values else np.nan for category in categories],
            dtype=float,
        )
        for group in series
    }
    return categories, series, matrix


def _colors(palette: str | None, count: int) -> list[Any]:
    import matplotlib.pyplot as plt

    name = str(palette or _DEFAULT_PALETTE)
    try:
        cmap = plt.get_cmap(name)
    except ValueError as exc:
        raise ValueError(f"未知配色方案：{name}。") from exc
    if count <= 0:
        return []
    if getattr(cmap, "N", 0) <= 10 and count <= cmap.N:
        return [cmap(index) for index in range(count)]
    return [cmap(value) for value in np.linspace(0.05, 0.95, count)]


def _style_axes(ax, grid: bool, grid_axis: str) -> None:
    ax.set_axisbelow(True)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.tick_params(direction="out", length=3.5, width=0.8)
    if grid:
        ax.grid(True, axis=grid_axis, linestyle="--", linewidth=0.65, alpha=0.28)


def _annotate_bars(ax, bars, horizontal: bool) -> None:
    for bar in bars:
        value = bar.get_width() if horizontal else bar.get_height()
        if not np.isfinite(value):
            continue
        if horizontal:
            endpoint = bar.get_x() + bar.get_width()
            ax.annotate(
                f"{value:g}",
                (endpoint, bar.get_y() + bar.get_height() / 2),
                xytext=(4 if value >= 0 else -4, 0),
                textcoords="offset points",
                va="center",
                ha="left" if value >= 0 else "right",
                fontsize=8,
            )
        else:
            endpoint = bar.get_y() + bar.get_height()
            ax.annotate(
                f"{value:g}",
                (bar.get_x() + bar.get_width() / 2, endpoint),
                xytext=(0, 3 if value >= 0 else -3),
                textcoords="offset points",
                va="bottom" if value >= 0 else "top",
                ha="center",
                fontsize=8,
            )


def bar_chart(
    plotter,
    x: Sequence[Any],
    y: Sequence[Any],
    groups: Sequence[Any] | None = None,
    *,
    horizontal: bool = False,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    aggregation: str = "mean",
    group_mode: str = "grouped",
    show_values: bool = False,
    tick_rotation: float = 0,
    palette: str = _DEFAULT_PALETTE,
    grid: bool = True,
    figsize: tuple[float, float] = (7.2, 4.8),
):
    import matplotlib.pyplot as plt

    categories, series, matrix = _aggregate(x, y, groups, aggregation)
    mode = str(group_mode or "grouped").lower()
    if mode not in {"grouped", "stacked"}:
        raise ValueError("group_mode 仅支持 grouped 或 stacked。")
    if groups is None:
        mode = "grouped"
    labels = [str(category) for category in categories]
    positions = np.arange(len(categories), dtype=float)
    colors = _colors(palette, len(series))
    fig, ax = plotter._new_subplots(figsize)
    width = 0.8 / max(len(series), 1) if mode == "grouped" else 0.8

    positive_bottom = np.zeros(len(categories), dtype=float)
    negative_bottom = np.zeros(len(categories), dtype=float)
    for index, group in enumerate(series):
        values = matrix[group]
        safe_values = np.nan_to_num(values, nan=0.0)
        bar_containers = []
        if mode == "grouped":
            offset = (index - (len(series) - 1) / 2) * width
            bar_positions = positions + offset
            if horizontal:
                bars = ax.barh(bar_positions, safe_values, height=width, color=colors[index], label=group)
            else:
                bars = ax.bar(bar_positions, safe_values, width=width, color=colors[index], label=group)
            bar_containers.append(bars)
        else:
            positive = np.maximum(safe_values, 0)
            negative = np.minimum(safe_values, 0)
            if horizontal:
                positive_bars = ax.barh(positions, positive, left=positive_bottom, height=width, color=colors[index], label=group)
                negative_bars = ax.barh(positions, negative, left=negative_bottom, height=width, color=colors[index])
            else:
                positive_bars = ax.bar(positions, positive, bottom=positive_bottom, width=width, color=colors[index], label=group)
                negative_bars = ax.bar(positions, negative, bottom=negative_bottom, width=width, color=colors[index])
            positive_bottom += positive
            negative_bottom += negative
            bar_containers.extend((positive_bars, negative_bars))
        if show_values:
            for bars in bar_containers:
                _annotate_bars(ax, bars, horizontal)

    if horizontal:
        ax.set_yticks(positions, labels)
        ax.set_xlabel(xlabel or "Value")
        ax.set_ylabel(ylabel or "Category")
        _style_axes(ax, grid, "x")
    else:
        ax.set_xticks(positions, labels, rotation=float(tick_rotation), ha="right" if tick_rotation else "center")
        ax.set_xlabel(xlabel or "Category")
        ax.set_ylabel(ylabel or "Value")
        _style_axes(ax, grid, "y")
    if len(series) > 1:
        ax.legend(frameon=False)
    if title:
        ax.set_title(title, pad=10)
    ax.margins(x=0.08 if horizontal else 0.04, y=0.08 if not horizontal else 0.04)
    return fig, ax


def _line_coordinates(categories: list[Any]):
    try:
        values = np.asarray([float(value) for value in categories], dtype=float)
        order = np.argsort(values, kind="stable")
        return values[order], order, None
    except (TypeError, ValueError):
        pass

    try:
        from matplotlib import dates as mdates

        dates = [datetime.fromisoformat(str(value).replace("Z", "+00:00")) for value in categories]
        order = np.argsort(mdates.date2num(dates), kind="stable")
        coordinates = mdates.date2num([dates[index] for index in order])
        return coordinates, order, mdates
    except (TypeError, ValueError, OverflowError):
        order = np.arange(len(categories))
        return order, order, "categorical"


def _series_plot_data(x, y, groups, aggregation):
    categories, series, matrix = _aggregate(x, y, groups, aggregation)
    coordinates, order, date_formatter = _line_coordinates(categories)
    sorted_categories = [categories[index] for index in order]
    matrix = {name: values[order] for name, values in matrix.items()}
    return sorted_categories, coordinates, series, matrix, date_formatter


def line_chart(
    plotter,
    x: Sequence[Any],
    y: Sequence[Any],
    groups: Sequence[Any] | None = None,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    aggregation: str = "mean",
    marker: str = "o",
    line_width: float = 2.0,
    palette: str = _DEFAULT_PALETTE,
    grid: bool = True,
    figsize: tuple[float, float] = (7.2, 4.8),
):
    from matplotlib import dates as mdates

    categories, coordinates, series, matrix, date_formatter = _series_plot_data(x, y, groups, aggregation)
    line_width = float(line_width)
    if not np.isfinite(line_width) or line_width <= 0:
        raise ValueError("line_width 必须是大于 0 的有限数值。")
    colors = _colors(palette, len(series))
    fig, ax = plotter._new_subplots(figsize)
    for index, group in enumerate(series):
        values = matrix[group]
        ax.plot(
            np.asarray(coordinates),
            values,
            color=colors[index],
            marker=marker or None,
            linewidth=line_width,
            markersize=5,
            label=group,
        )
    if date_formatter == "categorical":
        ax.set_xticks(coordinates, [str(value) for value in categories])
    elif date_formatter is not None:
        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        fig.autofmt_xdate()
    _style_axes(ax, grid, "both")
    ax.set_xlabel(xlabel or "X")
    ax.set_ylabel(ylabel or "Value")
    if title:
        ax.set_title(title, pad=10)
    if len(series) > 1:
        ax.legend(frameon=False)
    ax.margins(x=0.04, y=0.08)
    return fig, ax


def histogram_chart(
    plotter,
    values: Sequence[Any] | Sequence[Sequence[Any]],
    labels: Sequence[str] | None = None,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    bins: int = 20,
    density: bool = False,
    alpha: float = 0.68,
    palette: str = _DEFAULT_PALETTE,
    grid: bool = True,
    figsize: tuple[float, float] = (7.2, 4.8),
):
    try:
        bins = int(bins)
    except (TypeError, ValueError) as exc:
        raise ValueError("bins 必须是正整数。") from exc
    if bins < 1:
        raise ValueError("bins 必须是正整数。")
    raw_values = list(values) if not isinstance(values, np.ndarray) else values.tolist()
    raw_series = (
        raw_values
        if raw_values and isinstance(raw_values[0], (list, tuple, np.ndarray))
        else [raw_values]
    )
    data: list[np.ndarray] = []
    for series in raw_series:
        numeric = np.asarray(series, dtype=float).reshape(-1)
        numeric = numeric[np.isfinite(numeric)]
        if numeric.size:
            data.append(numeric)
    if not data:
        raise ValueError("直方图没有可绘制的有效数值。")
    alpha = float(alpha)
    if not np.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("直方图 alpha 必须在 0 到 1 之间。")
    names = list(labels) if labels is not None else []
    if len(data) > 1 and len(names) != len(data):
        names = [f"Series {index + 1}" for index in range(len(data))]
    colors = _colors(palette, len(data))
    fig, ax = plotter._new_subplots(figsize)
    ax.hist(
        data,
        bins=bins,
        density=bool(density),
        alpha=alpha,
        color=colors,
        label=names if len(data) > 1 else None,
        edgecolor="white",
        linewidth=0.65,
    )
    _style_axes(ax, grid, "y")
    ax.set_xlabel(xlabel or "Value")
    ax.set_ylabel(ylabel or ("Density" if density else "Count"))
    if title:
        ax.set_title(title, pad=10)
    if len(data) > 1:
        ax.legend(frameon=False)
    ax.margins(x=0.04, y=0.08)
    return fig, ax


def area_chart(
    plotter,
    x: Sequence[Any],
    y: Sequence[Any],
    groups: Sequence[Any] | None = None,
    *,
    title: str | None = None,
    xlabel: str | None = None,
    ylabel: str | None = None,
    aggregation: str = "mean",
    stacked: bool = False,
    alpha: float = 0.28,
    palette: str = _DEFAULT_PALETTE,
    grid: bool = True,
    figsize: tuple[float, float] = (7.2, 4.8),
):
    categories, coordinates, series, matrix, date_formatter = _series_plot_data(x, y, groups, aggregation)
    from matplotlib import dates as mdates

    alpha = float(alpha)
    if not np.isfinite(alpha) or not 0 <= alpha <= 1:
        raise ValueError("面积图 alpha 必须在 0 到 1 之间。")
    colors = _colors(palette, len(series))
    x_values = np.asarray(coordinates, dtype=float)
    fig, ax = plotter._new_subplots(figsize)
    if stacked:
        data = [np.nan_to_num(matrix[group], nan=0.0) for group in series]
        if any(np.any(item < 0) for item in data):
            raise ValueError("stacked 面积图暂不支持负数。")
        ax.stackplot(x_values, *data, labels=[str(group) for group in series], colors=colors, alpha=float(alpha))
    else:
        for index, group in enumerate(series):
            values = matrix[group]
            mask = np.isfinite(values)
            ax.fill_between(
                x_values,
                values,
                where=mask,
                color=colors[index],
                alpha=alpha,
                label=group,
                linewidth=1.4,
            )
            ax.plot(x_values, values, color=colors[index], linewidth=1.6)
    if date_formatter == "categorical":
        ax.set_xticks(coordinates, [str(value) for value in categories])
    elif date_formatter is not None:
        locator = mdates.AutoDateLocator()
        ax.xaxis.set_major_locator(locator)
        ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(locator))
        fig.autofmt_xdate()
    _style_axes(ax, grid, "both")
    ax.set_xlabel(xlabel or "X")
    ax.set_ylabel(ylabel or "Value")
    if title:
        ax.set_title(title, pad=10)
    if len(series) > 1:
        ax.legend(frameon=False)
    ax.margins(x=0.04, y=0.08)
    return fig, ax
