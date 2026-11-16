from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import List, Optional


def _try_import(modpath: str, attr: str):
    try:
        mod = __import__(modpath, fromlist=[attr])
        return getattr(mod, attr)
    except Exception:
        return None


def _load_from_candidates(candidates: List[Path], mod_name: str, attr: str):
    for path in candidates:
        if not path.exists():
            continue
        spec = importlib.util.spec_from_file_location(mod_name, path)
        if spec and spec.loader:
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            return getattr(mod, attr)
    raise ImportError(f"未找到 {attr}，候选路径：\n" + "\n".join(str(x) for x in candidates))


def _unavailable_map_plotter_cls(error: Exception):
    class UnavailableMapPlotter:
        def __init__(self, *args, **kwargs):
            raise RuntimeError(f"地图绘图模块加载失败：{error}") from error

    return UnavailableMapPlotter


def get_static_plotter_cls(src_dir: Path):
    cls = _try_import("src.chart.plot_2d.static_analysis", "StaticAnalysisPlotter")
    if cls is not None:
        return cls
    candidates = [
        src_dir / "chart" / "plot_2d" / "static_analysis.py",
        src_dir / "chart" / "plot-2d" / "static_analysis.py",
        src_dir / "chart" / "2D" / "static_analysis.py",
    ]
    return _load_from_candidates(candidates, "src.chart.plot_2d.static_analysis_dyn", "StaticAnalysisPlotter")


def get_map_plotter_cls(src_dir: Path):
    candidates_mod_cls = [
        ("src.chart.plot_2d.geo_atlas", "GeoAtlas"),
        ("src.chart.plot_2d.geo_atlas", "GeoAtlasPlotter"),
        ("src.chart.plot_2d.geo_atlas", "AtlasMapPlotter"),
        ("src.chart.plot_2d.geo_atlas", "MapPlotter"),
        ("src.chart.plot_2d.geo_atlas", "DomainMapPlotter"),
        ("src.chart.plot_2d.cartography", "CartographyPlotter"),
        ("src.chart.plot_2d.cartography", "DomainMapPlotter"),
        ("src.chart.plot_2d.geo_thematic", "GeoThematicPlotter"),
        ("src.chart.plot_2d.geo_thematic", "DomainMapPlotter"),
        ("src.chart.plot_2d.domain_analysis", "DomainMapPlotter"),
    ]
    module_paths = {
        "src.chart.plot_2d.geo_atlas": src_dir / "chart" / "plot_2d" / "geo_atlas.py",
        "src.chart.plot_2d.cartography": src_dir / "chart" / "plot_2d" / "cartography.py",
        "src.chart.plot_2d.geo_thematic": src_dir / "chart" / "plot_2d" / "geo_thematic.py",
        "src.chart.plot_2d.domain_analysis": src_dir / "chart" / "plot_2d" / "domain_analysis.py",
    }
    load_error: Optional[Exception] = None
    for mod, cls_name in candidates_mod_cls:
        try:
            module = __import__(mod, fromlist=[cls_name])
        except Exception as exc:
            module_path = module_paths.get(mod)
            if module_path is not None and module_path.is_file() and load_error is None:
                load_error = exc
            continue
        cls = getattr(module, cls_name, None)
        if cls is not None:
            return cls

    file_attr_pairs = [
        (src_dir / "chart" / "plot_2d" / "geo_atlas.py", "GeoAtlas"),
        (src_dir / "chart" / "plot_2d" / "geo_atlas.py", "GeoAtlasPlotter"),
        (src_dir / "chart" / "plot_2d" / "geo_atlas.py", "AtlasMapPlotter"),
        (src_dir / "chart" / "plot_2d" / "geo_atlas.py", "MapPlotter"),
        (src_dir / "chart" / "plot_2d" / "geo_atlas.py", "DomainMapPlotter"),
        (src_dir / "chart" / "plot_2d" / "cartography.py", "CartographyPlotter"),
        (src_dir / "chart" / "plot_2d" / "cartography.py", "DomainMapPlotter"),
        (src_dir / "chart" / "plot_2d" / "geo_thematic.py", "GeoThematicPlotter"),
        (src_dir / "chart" / "plot_2d" / "geo_thematic.py", "DomainMapPlotter"),
        (src_dir / "chart" / "plot_2d" / "domain_analysis.py", "DomainMapPlotter"),
    ]
    for path, attr in file_attr_pairs:
        if not path.is_file():
            continue
        try:
            return _load_from_candidates([path], f"{path.stem}_dyn", attr)
        except Exception as e:
            if load_error is None:
                load_error = e
    if load_error is not None:
        return _unavailable_map_plotter_cls(load_error)
    return None


def get_3d_plotter_cls(src_dir: Path):
    cls = _try_import("src.chart.plot_3d.scatter3d", "Scatter3DPlotter")
    if cls is not None:
        return cls
    candidates = [
        src_dir / "chart" / "plot_3d" / "scatter3d.py",
        src_dir / "chart" / "plot-3d" / "scatter3d.py",
        src_dir / "chart" / "3D" / "scatter3d.py",
    ]
    try:
        return _load_from_candidates(candidates, "src.chart.plot_3d.scatter3d_dyn", "Scatter3DPlotter")
    except Exception:
        return None
