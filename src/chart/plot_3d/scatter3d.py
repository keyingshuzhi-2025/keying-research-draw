from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence, Tuple

import numpy as np

from src.config import PlotConfig, ensure_matplotlib_backend
from src.util.dependency_hints import format_missing_dependency
from src.util.stats_utils import save_figure

ensure_matplotlib_backend()

import matplotlib.pyplot as plt
import matplotlib.tri as mtri
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401


def _as_1d_float(arr) -> np.ndarray:
    return np.asarray(arr, dtype=float).reshape(-1)


def _finite_n(*arrs) -> Tuple[list[np.ndarray], np.ndarray]:
    vecs = [_as_1d_float(v) for v in arrs]
    sizes = {v.size for v in vecs}
    if len(sizes) != 1:
        raise ValueError("输入数组长度需一致")
    mask = np.ones(vecs[0].shape, dtype=bool)
    for v in vecs:
        mask &= np.isfinite(v)
    filtered = [v[mask] for v in vecs]
    if filtered[0].size < 3:
        raise ValueError("3D 图至少需要 3 个有效点")
    return filtered, mask


def _finite_xyz(x, y, z) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    (x_arr, y_arr, z_arr), _ = _finite_n(x, y, z)
    return x_arr, y_arr, z_arr


def _grid_from_xyz(x, y, z) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    x_arr, y_arr, z_arr = _finite_xyz(x, y, z)
    x_u = np.unique(x_arr)
    y_u = np.unique(y_arr)
    if x_u.size * y_u.size != x_arr.size:
        raise ValueError("当前 x/y/z 不是规则网格数据（wireframe3d/contour3d 需要网格；可改用 surface3d）")

    x_index = {float(v): i for i, v in enumerate(x_u)}
    y_index = {float(v): i for i, v in enumerate(y_u)}
    z_grid = np.full((y_u.size, x_u.size), np.nan, dtype=float)
    for xv, yv, zv in zip(x_arr, y_arr, z_arr):
        i = y_index[float(yv)]
        j = x_index[float(xv)]
        if np.isnan(z_grid[i, j]):
            z_grid[i, j] = float(zv)
        else:
            z_grid[i, j] = (z_grid[i, j] + float(zv)) / 2.0
    if np.isnan(z_grid).any():
        raise ValueError("规则网格数据存在缺口，无法绘制 wireframe3d/contour3d")
    x_grid, y_grid = np.meshgrid(x_u, y_u)
    return x_grid, y_grid, z_grid


def _spacing(values: np.ndarray) -> float:
    if values.size < 2:
        return 1.0
    diffs = np.diff(np.sort(values))
    finite = diffs[np.isfinite(diffs) & (diffs > 0)]
    if finite.size == 0:
        return 1.0
    return float(np.median(finite))


def _auto_quiver_length(x: np.ndarray, y: np.ndarray, z: np.ndarray, magnitude: np.ndarray) -> float:
    """Scale vectors so the largest arrow uses 35% of typical point spacing."""
    max_magnitude = float(np.max(magnitude)) if magnitude.size else 0.0
    if not np.isfinite(max_magnitude) or max_magnitude <= 0:
        return 1.0

    positions = np.column_stack((x, y, z))
    spacing = 0.0
    if len(positions) > 1:
        delta = positions[:, None, :] - positions[None, :, :]
        distances = np.sqrt(np.sum(delta * delta, axis=2))
        np.fill_diagonal(distances, np.inf)
        nearest = np.min(distances, axis=1)
        nearest = nearest[np.isfinite(nearest) & (nearest > 0)]
        if nearest.size:
            spacing = float(np.median(nearest))

    if not np.isfinite(spacing) or spacing <= 0:
        coordinate_span = max(
            float(np.ptp(x)),
            float(np.ptp(y)),
            float(np.ptp(z)),
        )
        spacing = coordinate_span if coordinate_span > 0 else 1.0

    return 0.35 * spacing / max_magnitude


def _volume_from_xyzc(x, y, z, c) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    (x_arr, y_arr, z_arr, c_arr), _ = _finite_n(x, y, z, c)
    x_u = np.unique(x_arr)
    y_u = np.unique(y_arr)
    z_u = np.unique(z_arr)
    if x_u.size * y_u.size * z_u.size != x_arr.size:
        raise ValueError("isosurface3d/slice3d 需要规则体网格数据（x,y,z 组合完整）")

    x_index = {float(v): i for i, v in enumerate(x_u)}
    y_index = {float(v): i for i, v in enumerate(y_u)}
    z_index = {float(v): i for i, v in enumerate(z_u)}
    vol = np.full((z_u.size, y_u.size, x_u.size), np.nan, dtype=float)
    cnt = np.zeros_like(vol, dtype=float)
    for xv, yv, zv, cv in zip(x_arr, y_arr, z_arr, c_arr):
        i = z_index[float(zv)]
        j = y_index[float(yv)]
        k = x_index[float(xv)]
        if np.isnan(vol[i, j, k]):
            vol[i, j, k] = float(cv)
        else:
            vol[i, j, k] += float(cv)
        cnt[i, j, k] += 1.0

    mask = cnt > 0
    vol[mask] = vol[mask] / cnt[mask]
    if np.isnan(vol).any():
        raise ValueError("体网格存在缺口，无法绘制 isosurface3d/slice3d")
    return x_u, y_u, z_u, vol


@dataclass
class Scatter3DPlotter:
    cfg: Optional[PlotConfig] = None

    def __post_init__(self) -> None:
        if self.cfg is None:
            self.cfg = PlotConfig.from_env()
        self.cfg.apply()

    def save(
        self,
        name: Optional[str] = None,
        fig: Optional[plt.Figure] = None,
        fmt: Optional[str] = None,
        dpi: Optional[int] = None,
        match_screen: bool = True,
        tight: bool = False,
    ) -> str:
        return save_figure(
            outpath_func=self.cfg.outpath,
            name=name,
            fig=fig,
            fmt=fmt,
            dpi=dpi,
            match_screen=match_screen,
            tight=tight,
        )

    @staticmethod
    def _apply_axes(ax, title: str, xlabel: str, ylabel: str, zlabel: str, elev: float, azim: float) -> None:
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_zlabel(zlabel)
        ax.view_init(elev=float(elev), azim=float(azim))

    def scatter3d(
        self,
        x,
        y,
        z,
        title: str = "3D Scatter",
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        s: float = 28.0,
        alpha: float = 0.9,
        elev: float = 24.0,
        azim: float = 38.0,
        cmap: str = "viridis",
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        x_arr, y_arr, z_arr = _finite_xyz(x, y, z)
        fig = plt.figure(figsize=(7.6, 6.2), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        sc = ax.scatter(
            x_arr,
            y_arr,
            z_arr,
            c=z_arr,
            cmap=cmap,
            s=float(s),
            alpha=float(alpha),
            depthshade=True,
            edgecolors="white",
            linewidths=0.25,
        )
        cb = fig.colorbar(sc, ax=ax, fraction=0.045, pad=0.06)
        cb.set_label(zlabel)
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {"n": int(x_arr.size)}
        return fig, ax, extras

    def surface3d(
        self,
        x,
        y,
        z,
        title: str = "3D Surface",
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        elev: float = 24.0,
        azim: float = 38.0,
        cmap: str = "viridis",
        alpha: float = 0.95,
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        x_arr, y_arr, z_arr = _finite_xyz(x, y, z)
        fig = plt.figure(figsize=(7.8, 6.2), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")

        mode = "trisurf"
        try:
            xg, yg, zg = _grid_from_xyz(x_arr, y_arr, z_arr)
            surf = ax.plot_surface(
                xg,
                yg,
                zg,
                cmap=cmap,
                linewidth=0.0,
                antialiased=True,
                alpha=float(alpha),
            )
            mode = "surface"
        except Exception:
            surf = ax.plot_trisurf(
                x_arr,
                y_arr,
                z_arr,
                cmap=cmap,
                linewidth=0.08,
                antialiased=True,
                alpha=float(alpha),
            )

        cb = fig.colorbar(surf, ax=ax, fraction=0.045, pad=0.06)
        cb.set_label(zlabel)
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {"n": int(x_arr.size), "mode": mode}
        return fig, ax, extras

    def wireframe3d(
        self,
        x,
        y,
        z,
        title: str = "3D Wireframe",
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        elev: float = 24.0,
        azim: float = 38.0,
        color: str = "#1f77b4",
        rstride: int = 2,
        cstride: int = 2,
        linewidth: float = 0.8,
        alpha: float = 0.9,
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        xg, yg, zg = _grid_from_xyz(x, y, z)
        fig = plt.figure(figsize=(7.8, 6.2), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        ax.plot_wireframe(
            xg,
            yg,
            zg,
            rstride=max(int(rstride), 1),
            cstride=max(int(cstride), 1),
            color=color,
            linewidth=float(linewidth),
            alpha=float(alpha),
        )
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {"shape": (int(zg.shape[0]), int(zg.shape[1]))}
        return fig, ax, extras

    def contour3d(
        self,
        x,
        y,
        z,
        title: str = "3D Contour",
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        elev: float = 30.0,
        azim: float = 42.0,
        cmap: str = "viridis",
        levels: int = 18,
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        xg, yg, zg = _grid_from_xyz(x, y, z)
        fig = plt.figure(figsize=(7.8, 6.2), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        ct = ax.contour3D(xg, yg, zg, levels=max(int(levels), 3), cmap=cmap, linewidths=1.0)
        cb = fig.colorbar(ct, ax=ax, fraction=0.045, pad=0.06)
        cb.set_label(zlabel)
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {"shape": (int(zg.shape[0]), int(zg.shape[1])), "levels": max(int(levels), 3)}
        return fig, ax, extras

    def line3d(
        self,
        x,
        y,
        z,
        title: str = "3D Line",
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        elev: float = 24.0,
        azim: float = 38.0,
        color: str = "#d62728",
        linewidth: float = 2.0,
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        x_arr, y_arr, z_arr = _finite_xyz(x, y, z)
        fig = plt.figure(figsize=(7.6, 6.2), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        ax.plot(x_arr, y_arr, z_arr, color=color, linewidth=float(linewidth))
        ax.scatter(x_arr[0], y_arr[0], z_arr[0], s=28, color="#2ca02c", label="start")
        ax.scatter(x_arr[-1], y_arr[-1], z_arr[-1], s=32, color="#111827", label="end")
        ax.legend(frameon=False, loc="upper left")
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {"n": int(x_arr.size)}
        return fig, ax, extras

    def quiver3d(
        self,
        x,
        y,
        z,
        u,
        v,
        w,
        title: str = "3D Vector Field",
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        elev: float = 24.0,
        azim: float = 38.0,
        cmap: str = "viridis",
        length: Optional[float] = None,
        normalize: bool = False,
        max_arrows: int = 600,
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        (x_arr, y_arr, z_arr, u_arr, v_arr, w_arr), _ = _finite_n(x, y, z, u, v, w)
        n = int(x_arr.size)
        if max_arrows > 0 and n > max_arrows:
            step = int(np.ceil(n / max_arrows))
            x_arr = x_arr[::step]
            y_arr = y_arr[::step]
            z_arr = z_arr[::step]
            u_arr = u_arr[::step]
            v_arr = v_arr[::step]
            w_arr = w_arr[::step]
        mag = np.sqrt(u_arr ** 2 + v_arr ** 2 + w_arr ** 2)
        quiver_length = _auto_quiver_length(x_arr, y_arr, z_arr, mag) if length is None else float(length)
        if not np.isfinite(quiver_length) or quiver_length <= 0:
            raise ValueError("quiver3d 的 length 必须是大于 0 的有限数值")
        norm = plt.Normalize(vmin=float(np.min(mag)), vmax=float(np.max(mag) + 1e-12))
        colors = plt.get_cmap(cmap)(norm(mag))

        fig = plt.figure(figsize=(7.8, 6.3), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        ax.quiver(
            x_arr,
            y_arr,
            z_arr,
            u_arr,
            v_arr,
            w_arr,
            length=quiver_length,
            normalize=bool(normalize),
            colors=colors,
            linewidth=0.8,
        )
        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array(mag)
        cb = fig.colorbar(sm, ax=ax, fraction=0.045, pad=0.06)
        cb.set_label("Vector Magnitude")
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {"n": int(x_arr.size)}
        return fig, ax, extras

    def waterfall3d(
        self,
        x,
        y,
        z,
        title: str = "3D Waterfall",
        xlabel: str = "X",
        ylabel: str = "Series",
        zlabel: str = "Intensity",
        elev: float = 24.0,
        azim: float = -62.0,
        cmap: str = "viridis",
        linewidth: float = 1.35,
        alpha: float = 0.92,
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        x_arr, y_arr, z_arr = _finite_xyz(x, y, z)
        y_unique = np.unique(y_arr)
        if y_unique.size < 2:
            raise ValueError("waterfall3d 需要至少两条曲线（y 方向至少两个组）")

        fig = plt.figure(figsize=(8.2, 6.0), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        norm = plt.Normalize(vmin=float(np.min(y_unique)), vmax=float(np.max(y_unique)))
        cmap_obj = plt.get_cmap(cmap)
        for yv in y_unique:
            m = y_arr == yv
            xs = x_arr[m]
            zs = z_arr[m]
            order = np.argsort(xs)
            xs = xs[order]
            zs = zs[order]
            ys = np.full_like(xs, yv)
            ax.plot(xs, ys, zs, color=cmap_obj(norm(float(yv))), linewidth=float(linewidth), alpha=float(alpha))

        sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
        sm.set_array(y_unique)
        cb = fig.colorbar(sm, ax=ax, fraction=0.045, pad=0.06)
        cb.set_label(ylabel)
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {"n_curves": int(y_unique.size), "n_points": int(x_arr.size)}
        return fig, ax, extras

    def embedding3d(
        self,
        features,
        labels: Optional[Sequence] = None,
        method: str = "pca",
        title: str = "3D Embedding",
        elev: float = 24.0,
        azim: float = 38.0,
        cmap: str = "viridis",
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        X = np.asarray(features, dtype=float)
        if X.ndim != 2 or X.shape[1] < 2:
            raise ValueError("embedding3d 需要二维特征矩阵，且特征数至少 2")
        finite_mask = np.isfinite(X).all(axis=1)
        X = X[finite_mask]
        if X.shape[0] < 3:
            raise ValueError("embedding3d 样本量不足")

        y = None
        if labels is not None:
            y = np.asarray(labels).reshape(-1)
            if y.size != finite_mask.size:
                raise ValueError("labels 长度需与样本数一致")
            y = y[finite_mask]

        method_l = str(method or "pca").lower()
        if method_l == "umap":
            try:
                import umap  # type: ignore
            except Exception as e:
                raise RuntimeError(
                    format_missing_dependency(
                        package="umap-learn",
                        feature="embedding3d 的 UMAP 降维",
                        recommended_extra="ml",
                        fallback_pip="uv add umap-learn scikit-learn",
                    )
                ) from e
            emb = umap.UMAP(n_components=3, random_state=42).fit_transform(X)
            axis_name = ("UMAP-1", "UMAP-2", "UMAP-3")
        else:
            try:
                from sklearn.decomposition import PCA  # type: ignore

                emb = PCA(n_components=3, random_state=42).fit_transform(X)
            except Exception:
                X0 = X - np.mean(X, axis=0, keepdims=True)
                _u, _s, vt = np.linalg.svd(X0, full_matrices=False)
                emb = X0 @ vt[:3].T
            axis_name = ("PC1", "PC2", "PC3")

        fig = plt.figure(figsize=(7.8, 6.3), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")

        if y is None:
            sc = ax.scatter(emb[:, 0], emb[:, 1], emb[:, 2], c=emb[:, 2], cmap=cmap, s=24, alpha=0.9)
            cb = fig.colorbar(sc, ax=ax, fraction=0.045, pad=0.06)
            cb.set_label(axis_name[2])
        else:
            y_num = None
            try:
                y_num = y.astype(float)
            except Exception:
                y_num = None

            if y_num is not None and np.unique(y_num).size > 12:
                sc = ax.scatter(emb[:, 0], emb[:, 1], emb[:, 2], c=y_num, cmap=cmap, s=24, alpha=0.9)
                cb = fig.colorbar(sc, ax=ax, fraction=0.045, pad=0.06)
                cb.set_label("Label")
            else:
                cats = np.unique(y.astype(str))
                colors = plt.get_cmap("tab20")(np.linspace(0, 1, max(cats.size, 1)))
                for i, cat in enumerate(cats):
                    m = y.astype(str) == cat
                    ax.scatter(
                        emb[m, 0],
                        emb[m, 1],
                        emb[m, 2],
                        s=24,
                        alpha=0.9,
                        color=colors[i],
                        label=str(cat),
                    )
                ax.legend(frameon=False, loc="best")

        self._apply_axes(ax, title, axis_name[0], axis_name[1], axis_name[2], elev, azim)
        extras = {"method": method_l, "n_samples": int(X.shape[0]), "n_features": int(X.shape[1])}
        return fig, ax, extras

    def mesh3d(
        self,
        x,
        y,
        z,
        values=None,
        title: str = "3D Mesh",
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        elev: float = 24.0,
        azim: float = 38.0,
        cmap: str = "viridis",
        alpha: float = 0.95,
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        if values is None:
            x_arr, y_arr, z_arr = _finite_xyz(x, y, z)
            c_arr = z_arr
        else:
            (x_arr, y_arr, z_arr, c_arr), _ = _finite_n(x, y, z, values)

        tri = mtri.Triangulation(x_arr, y_arr)
        fig = plt.figure(figsize=(7.8, 6.2), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        surf = ax.plot_trisurf(
            x_arr,
            y_arr,
            z_arr,
            triangles=tri.triangles,
            cmap=cmap,
            linewidth=0.12,
            antialiased=True,
            alpha=float(alpha),
        )
        surf.set_array(np.asarray(c_arr, dtype=float))
        surf.autoscale()
        cb = fig.colorbar(surf, ax=ax, fraction=0.045, pad=0.06)
        cb.set_label("Value")
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {"n_points": int(x_arr.size), "n_faces": int(tri.triangles.shape[0])}
        return fig, ax, extras

    def isosurface3d(
        self,
        x,
        y,
        z,
        values,
        iso_level: Optional[float] = None,
        title: str = "3D Isosurface",
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        elev: float = 26.0,
        azim: float = 38.0,
        cmap: str = "viridis",
        alpha: float = 0.88,
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        try:
            from skimage import measure  # type: ignore
        except Exception as e:
            raise RuntimeError(
                format_missing_dependency(
                    package="scikit-image",
                    feature="isosurface3d（Marching Cubes）",
                    recommended_extra="ml",
                        fallback_pip="uv add scikit-image",
                )
            ) from e

        x_u, y_u, z_u, vol = _volume_from_xyzc(x, y, z, values)
        vmin = float(np.min(vol))
        vmax = float(np.max(vol))
        level = float(iso_level) if iso_level is not None else float(np.percentile(vol, 70))
        if not (vmin < level < vmax):
            raise ValueError(f"iso-level 需位于数据范围内 ({vmin:.4g}, {vmax:.4g})")

        dx = _spacing(x_u)
        dy = _spacing(y_u)
        dz = _spacing(z_u)
        verts, faces, _normals, _vals = measure.marching_cubes(vol, level=level, spacing=(dz, dy, dx))

        vz = verts[:, 0] + float(np.min(z_u))
        vy = verts[:, 1] + float(np.min(y_u))
        vx = verts[:, 2] + float(np.min(x_u))

        fig = plt.figure(figsize=(7.9, 6.4), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        surf = ax.plot_trisurf(vx, vy, vz, triangles=faces, cmap=cmap, linewidth=0.08, alpha=float(alpha))
        surf.set_array(vz)
        surf.autoscale()
        cb = fig.colorbar(surf, ax=ax, fraction=0.045, pad=0.06)
        cb.set_label(zlabel)
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {"iso_level": level, "n_vertices": int(vx.size), "n_faces": int(faces.shape[0])}
        return fig, ax, extras

    def slice3d(
        self,
        x,
        y,
        z,
        values,
        slice_x: Optional[float] = None,
        slice_y: Optional[float] = None,
        slice_z: Optional[float] = None,
        title: str = "3D Orthogonal Slices",
        xlabel: str = "X",
        ylabel: str = "Y",
        zlabel: str = "Z",
        elev: float = 24.0,
        azim: float = 38.0,
        cmap: str = "viridis",
    ) -> Tuple[plt.Figure, plt.Axes, dict]:
        (x_arr, y_arr, z_arr, c_arr), _ = _finite_n(x, y, z, values)
        sx = float(slice_x) if slice_x is not None else float(np.median(x_arr))
        sy = float(slice_y) if slice_y is not None else float(np.median(y_arr))
        sz = float(slice_z) if slice_z is not None else float(np.median(z_arr))
        tx = max((float(np.max(x_arr)) - float(np.min(x_arr))) / 42.0, 1e-12)
        ty = max((float(np.max(y_arr)) - float(np.min(y_arr))) / 42.0, 1e-12)
        tz = max((float(np.max(z_arr)) - float(np.min(z_arr))) / 42.0, 1e-12)

        def _mask_near(arr: np.ndarray, center: float, tol: float) -> np.ndarray:
            m = np.abs(arr - center) <= tol
            if m.any():
                return m
            take = max(1, int(np.ceil(arr.size * 0.05)))
            idx = np.argsort(np.abs(arr - center))[:take]
            out = np.zeros(arr.shape, dtype=bool)
            out[idx] = True
            return out

        mx = _mask_near(x_arr, sx, tx)
        my = _mask_near(y_arr, sy, ty)
        mz = _mask_near(z_arr, sz, tz)

        fig = plt.figure(figsize=(7.9, 6.4), constrained_layout=True)
        ax = fig.add_subplot(111, projection="3d")
        scx = ax.scatter(
            x_arr[mx],
            y_arr[mx],
            z_arr[mx],
            c=c_arr[mx],
            cmap=cmap,
            s=16,
            alpha=0.88,
            marker="o",
            label=f"x={sx:.3g}",
        )
        ax.scatter(
            x_arr[my],
            y_arr[my],
            z_arr[my],
            c=c_arr[my],
            cmap=cmap,
            s=14,
            alpha=0.82,
            marker="^",
            label=f"y={sy:.3g}",
        )
        ax.scatter(
            x_arr[mz],
            y_arr[mz],
            z_arr[mz],
            c=c_arr[mz],
            cmap=cmap,
            s=14,
            alpha=0.82,
            marker="s",
            label=f"z={sz:.3g}",
        )
        cb = fig.colorbar(scx, ax=ax, fraction=0.045, pad=0.06)
        cb.set_label("Scalar")
        ax.legend(frameon=False, loc="best")
        self._apply_axes(ax, title, xlabel, ylabel, zlabel, elev, azim)
        extras = {
            "slice_x": sx,
            "slice_y": sy,
            "slice_z": sz,
            "n_x": int(np.sum(mx)),
            "n_y": int(np.sum(my)),
            "n_z": int(np.sum(mz)),
        }
        return fig, ax, extras


_default_plotter: Optional[Scatter3DPlotter] = None


def _get_default_plotter() -> Scatter3DPlotter:
    global _default_plotter
    if _default_plotter is None:
        _default_plotter = Scatter3DPlotter()
    return _default_plotter


def scatter3d(*args, **kwargs):
    return _get_default_plotter().scatter3d(*args, **kwargs)


def surface3d(*args, **kwargs):
    return _get_default_plotter().surface3d(*args, **kwargs)


def wireframe3d(*args, **kwargs):
    return _get_default_plotter().wireframe3d(*args, **kwargs)


def contour3d(*args, **kwargs):
    return _get_default_plotter().contour3d(*args, **kwargs)


def line3d(*args, **kwargs):
    return _get_default_plotter().line3d(*args, **kwargs)


def quiver3d(*args, **kwargs):
    return _get_default_plotter().quiver3d(*args, **kwargs)


def waterfall3d(*args, **kwargs):
    return _get_default_plotter().waterfall3d(*args, **kwargs)


def embedding3d(*args, **kwargs):
    return _get_default_plotter().embedding3d(*args, **kwargs)


def mesh3d(*args, **kwargs):
    return _get_default_plotter().mesh3d(*args, **kwargs)


def isosurface3d(*args, **kwargs):
    return _get_default_plotter().isosurface3d(*args, **kwargs)


def slice3d(*args, **kwargs):
    return _get_default_plotter().slice3d(*args, **kwargs)
