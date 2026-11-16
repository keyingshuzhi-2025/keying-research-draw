from __future__ import annotations

from pathlib import Path

import numpy as np

from src.dispatch.handlers.base import HandlerContext, HandlerResult
from src.loaders.data_loader import (
    auto_sep,
    df_from_custom_data,
    load_custom_json,
    parse_numeric_list,
    pick_col,
    read_dataframe,
)


class Plot3DHandler:
    key = "plot3d"

    def __init__(self, ctx: HandlerContext) -> None:
        self.ctx = ctx
        self.args = ctx.args

    def render(self, plot_key: str, mode: str) -> HandlerResult:
        if self.ctx.plot3d_plotter_cls is None:
            raise ImportError("3D 模块未找到：请确认存在 src/chart/plot_3d/scatter3d.py")

        p = self.ctx.plot3d_plotter_cls()
        title = self.args.title

        plot_titles = {
            "plot3d_scatter": "3D Scatter",
            "plot3d_surface": "3D Surface",
            "plot3d_wireframe": "3D Wireframe",
            "plot3d_contour": "3D Contour",
            "plot3d_line": "3D Trajectory",
            "plot3d_isosurface": "3D Isosurface",
            "plot3d_slice": "3D Orthogonal Slices",
            "plot3d_quiver": "3D Vector Field",
            "plot3d_waterfall": "3D Waterfall",
            "plot3d_embedding": "3D Embedding",
            "plot3d_mesh": "3D Mesh",
        }
        if plot_key not in plot_titles:
            raise ValueError(f"未知 3D 图类型 / Unknown 3D plot: {self.args.plot}")

        if mode not in {"demo", "custom", "file"}:
            raise ValueError(f"未知模式 / Unknown mode: {self.args.mode}")

        z_col_name = self.args.z_col or self.args.z3d_col
        xlabel = self.args.xlabel or (self.args.x_col if mode == "file" and self.args.x_col else "X")
        ylabel = self.args.ylabel or (self.args.y_col if mode == "file" and self.args.y_col else "Y")
        zlabel = self.args.zlabel or (z_col_name if mode == "file" and z_col_name else "Z")
        elev = float(self.args.elev) if self.args.elev is not None else 24.0
        azim = float(self.args.azim) if self.args.azim is not None else 38.0
        cmap = self.args.cmap or "viridis"
        rng = np.random.default_rng(int(self.args.seed or 42))

        def _read_file_df():
            if not self.args.file:
                raise ValueError("--mode file 需要提供 --file")
            path = Path(self.args.file).expanduser().resolve()
            sep = auto_sep(path, self.args.sep)
            return read_dataframe(path, sep)

        ret = None

        if plot_key == "plot3d_embedding":
            method = (self.args.embed_method or "pca").lower()
            if mode == "demo":
                n = 260
                y_cls = rng.integers(0, 4, size=n)
                X = rng.normal(0, 0.8, size=(n, 6))
                for k in range(4):
                    X[y_cls == k, :3] += np.array([k * 1.6, (k % 2) * 1.4, (-1) ** k * 0.9])
                ret = p.embedding3d(
                    X,
                    labels=y_cls,
                    method=method,
                    title=title or "3D Embedding (Demo)",
                    elev=elev,
                    azim=azim,
                    cmap=cmap,
                )
            else:
                if mode == "custom":
                    data = load_custom_json(self.args)
                    if data is None:
                        raise ValueError("embedding3d 自定义模式需要 --custom-json 或 --custom-json-file")
                    df = df_from_custom_data(data)
                else:
                    df = _read_file_df()
                group_col = self.args.group_col if self.args.group_col and self.args.group_col in df.columns else None
                labels = df[group_col].values if group_col else None
                feat_df = df.drop(columns=[group_col]) if group_col else df
                numeric = feat_df.select_dtypes(include=["number"])
                if numeric.shape[1] < 2:
                    raise ValueError("embedding3d 需要至少两列数值特征")
                ret = p.embedding3d(
                    numeric.values,
                    labels=labels,
                    method=method,
                    title=title or "3D Embedding",
                    elev=elev,
                    azim=azim,
                    cmap=cmap,
                )
        elif plot_key in {"plot3d_isosurface", "plot3d_slice"}:
            if mode == "demo":
                axis = np.linspace(-2.2, 2.2, 22)
                xg, yg, zg = np.meshgrid(axis, axis, axis, indexing="xy")
                scalar = np.exp(-(xg ** 2 + yg ** 2 + zg ** 2) / 3.0) + 0.28 * np.sin(2.1 * xg) * np.cos(1.8 * yg)
                x = xg.reshape(-1)
                y = yg.reshape(-1)
                z = zg.reshape(-1)
                s = scalar.reshape(-1)
            elif mode == "custom":
                if not (self.args.x and self.args.y and self.args.z and self.args.scalar):
                    raise ValueError("isosurface3d/slice3d 自定义模式需要 --x --y --z --scalar")
                x = parse_numeric_list(self.args.x)
                y = parse_numeric_list(self.args.y)
                z = parse_numeric_list(self.args.z)
                s = parse_numeric_list(self.args.scalar)
            else:
                if not (self.args.x_col and self.args.y_col and z_col_name):
                    raise ValueError("3D 文件模式需要 --x-col --y-col --z-col（或 --z3d-col）")
                df = _read_file_df()
                scalar_col = self.args.scalar_col or self.args.value_col
                if not scalar_col:
                    scalar_col = pick_col(df, ["value", "scalar", "intensity", "val"])
                if scalar_col not in df.columns:
                    raise ValueError(f"未找到标量列：{scalar_col}")
                x = df[self.args.x_col].values
                y = df[self.args.y_col].values
                z = df[z_col_name].values
                s = df[scalar_col].values

            if plot_key == "plot3d_isosurface":
                ret = p.isosurface3d(
                    x,
                    y,
                    z,
                    s,
                    iso_level=self.args.iso_level,
                    title=title or ("3D Isosurface (Demo)" if mode == "demo" else "3D Isosurface"),
                    xlabel=xlabel,
                    ylabel=ylabel,
                    zlabel=zlabel,
                    elev=elev,
                    azim=azim,
                    cmap=cmap,
                )
            else:
                ret = p.slice3d(
                    x,
                    y,
                    z,
                    s,
                    slice_x=self.args.slice_x,
                    slice_y=self.args.slice_y,
                    slice_z=self.args.slice_z,
                    title=title or ("3D Orthogonal Slices (Demo)" if mode == "demo" else "3D Orthogonal Slices"),
                    xlabel=xlabel,
                    ylabel=ylabel,
                    zlabel=zlabel,
                    elev=elev,
                    azim=azim,
                    cmap=cmap,
                )
        elif plot_key == "plot3d_quiver":
            if mode == "demo":
                axis = np.linspace(-1.2, 1.2, 9)
                xg, yg, zg = np.meshgrid(axis, axis, axis[::2], indexing="xy")
                x = xg.reshape(-1)
                y = yg.reshape(-1)
                z = zg.reshape(-1)
                u = -y
                v = x
                w = 0.8 * np.sin(np.pi * z)
            elif mode == "custom":
                if not (self.args.x and self.args.y and self.args.z and self.args.u and self.args.v and self.args.w):
                    raise ValueError("quiver3d 自定义模式需要 --x --y --z --u --v --w")
                x = parse_numeric_list(self.args.x)
                y = parse_numeric_list(self.args.y)
                z = parse_numeric_list(self.args.z)
                u = parse_numeric_list(self.args.u)
                v = parse_numeric_list(self.args.v)
                w = parse_numeric_list(self.args.w)
            else:
                if not (self.args.x_col and self.args.y_col and z_col_name):
                    raise ValueError("3D 文件模式需要 --x-col --y-col --z-col（或 --z3d-col）")
                df = _read_file_df()
                u_col = self.args.u_col or pick_col(df, ["u", "ux", "vx", "dx"])
                v_col = self.args.v_col or pick_col(df, ["v", "uy", "vy", "dy"])
                w_col = self.args.w_col or pick_col(df, ["w", "uz", "vz", "dz"])
                x = df[self.args.x_col].values
                y = df[self.args.y_col].values
                z = df[z_col_name].values
                u = df[u_col].values
                v = df[v_col].values
                w = df[w_col].values
            ret = p.quiver3d(
                x,
                y,
                z,
                u,
                v,
                w,
                title=title or ("3D Vector Field (Demo)" if mode == "demo" else "3D Vector Field"),
                xlabel=xlabel,
                ylabel=ylabel,
                zlabel=zlabel,
                elev=elev,
                azim=azim,
                cmap=cmap,
                length=self.args.length,
                max_arrows=max(int(self.args.max_arrows or 600), 50),
            )
        else:
            if mode == "demo":
                if plot_key == "plot3d_scatter":
                    x = rng.normal(0.0, 1.0, 160)
                    y = 0.9 * x + rng.normal(0.0, 0.55, 160)
                    z = 1.2 * x - 0.4 * y + rng.normal(0.0, 0.35, 160)
                elif plot_key == "plot3d_line":
                    t = np.linspace(0.0, 10.0 * np.pi, 420)
                    x = np.cos(t)
                    y = np.sin(t)
                    z = t / (2.0 * np.pi)
                elif plot_key == "plot3d_waterfall":
                    x_base = np.linspace(0.0, 10.0, 180)
                    curves = 8
                    xs, ys, zs = [], [], []
                    for i in range(curves):
                        y0 = float(i)
                        z0 = np.sin(x_base * (0.9 + 0.08 * i)) * np.exp(-x_base / (10.0 + i)) + 0.12 * i
                        xs.append(x_base)
                        ys.append(np.full_like(x_base, y0))
                        zs.append(z0)
                    x = np.concatenate(xs)
                    y = np.concatenate(ys)
                    z = np.concatenate(zs)
                elif plot_key == "plot3d_mesh":
                    x = rng.uniform(-3.0, 3.0, 1300)
                    y = rng.uniform(-3.0, 3.0, 1300)
                    r = np.sqrt(x ** 2 + y ** 2) + 1e-9
                    z = np.sin(r) / r + 0.06 * rng.normal(size=r.size)
                else:
                    gx = np.linspace(-3.2, 3.2, 70)
                    gy = np.linspace(-3.2, 3.2, 70)
                    xg, yg = np.meshgrid(gx, gy)
                    r = np.sqrt(xg ** 2 + yg ** 2) + 1e-9
                    zg = np.sin(r) / r
                    x = xg.reshape(-1)
                    y = yg.reshape(-1)
                    z = zg.reshape(-1)
            elif mode == "custom":
                if not (self.args.x and self.args.y and self.args.z):
                    raise ValueError("3D 自定义模式需要 --x --y --z")
                x = parse_numeric_list(self.args.x)
                y = parse_numeric_list(self.args.y)
                z = parse_numeric_list(self.args.z)
            else:
                if not (self.args.x_col and self.args.y_col and z_col_name):
                    raise ValueError("3D 文件模式需要 --x-col --y-col --z-col（或 --z3d-col）")
                df = _read_file_df()
                x = df[self.args.x_col].values
                y = df[self.args.y_col].values
                z = df[z_col_name].values

            if plot_key == "plot3d_scatter":
                ret = p.scatter3d(
                    x,
                    y,
                    z,
                    title=title or ("3D Scatter (Demo)" if mode == "demo" else "3D Scatter"),
                    xlabel=xlabel,
                    ylabel=ylabel,
                    zlabel=zlabel,
                    elev=elev,
                    azim=azim,
                    cmap=cmap,
                )
            elif plot_key == "plot3d_surface":
                ret = p.surface3d(
                    x,
                    y,
                    z,
                    title=title or ("3D Surface (Demo)" if mode == "demo" else "3D Surface"),
                    xlabel=xlabel,
                    ylabel=ylabel,
                    zlabel=zlabel,
                    elev=elev,
                    azim=azim,
                    cmap=cmap,
                )
            elif plot_key == "plot3d_wireframe":
                ret = p.wireframe3d(
                    x,
                    y,
                    z,
                    title=title or ("3D Wireframe (Demo)" if mode == "demo" else "3D Wireframe"),
                    xlabel=xlabel,
                    ylabel=ylabel,
                    zlabel=zlabel,
                    elev=elev,
                    azim=azim,
                    rstride=max(int(self.args.rstride or 2), 1),
                    cstride=max(int(self.args.cstride or 2), 1),
                )
            elif plot_key == "plot3d_contour":
                contour_elev = float(self.args.elev) if self.args.elev is not None else 30.0
                contour_azim = float(self.args.azim) if self.args.azim is not None else 42.0
                ret = p.contour3d(
                    x,
                    y,
                    z,
                    title=title or ("3D Contour (Demo)" if mode == "demo" else "3D Contour"),
                    xlabel=xlabel,
                    ylabel=ylabel,
                    zlabel=zlabel,
                    elev=contour_elev,
                    azim=contour_azim,
                    cmap=cmap,
                    levels=max(int(self.args.levels or 18), 3),
                )
            elif plot_key == "plot3d_line":
                ret = p.line3d(
                    x,
                    y,
                    z,
                    title=title or ("3D Trajectory (Demo)" if mode == "demo" else "3D Trajectory"),
                    xlabel=xlabel,
                    ylabel=ylabel,
                    zlabel=zlabel,
                    elev=elev,
                    azim=azim,
                )
            elif plot_key == "plot3d_waterfall":
                ret = p.waterfall3d(
                    x,
                    y,
                    z,
                    title=title or ("3D Waterfall (Demo)" if mode == "demo" else "3D Waterfall"),
                    xlabel=xlabel,
                    ylabel=ylabel,
                    zlabel=zlabel,
                    elev=elev,
                    azim=float(self.args.azim) if self.args.azim is not None else -62.0,
                    cmap=cmap,
                )
            else:
                values = None
                if mode == "custom" and self.args.scalar:
                    values = parse_numeric_list(self.args.scalar)
                elif mode == "file":
                    scalar_col = self.args.scalar_col or self.args.value_col
                    if scalar_col and scalar_col in df.columns:
                        values = df[scalar_col].values
                ret = p.mesh3d(
                    x,
                    y,
                    z,
                    values=values,
                    title=title or ("3D Mesh (Demo)" if mode == "demo" else "3D Mesh"),
                    xlabel=xlabel,
                    ylabel=ylabel,
                    zlabel=zlabel,
                    elev=elev,
                    azim=azim,
                    cmap=cmap,
                )

        if ret is None:
            raise RuntimeError(f"3D 分发失败：{plot_key}")

        return HandlerResult(plotter=p, rendered=ret, plot_key=plot_key, title=title)
