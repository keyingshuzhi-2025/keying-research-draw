from pathlib import Path

import pytest

from src.plotters import factory


def test_map_plotter_keeps_optional_dependency_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_dir = tmp_path / "src"
    geo_dir = source_dir / "chart" / "plot_2d"
    geo_dir.mkdir(parents=True)
    (geo_dir / "geo_atlas.py").write_text("# optional map module", encoding="utf-8")

    def missing_map_import(module: str, fromlist: list[str]):
        if module == "src.chart.plot_2d.geo_atlas":
            raise RuntimeError("GeoAtlas 地图功能需要依赖 `geopandas`。建议安装：uv sync --extra maps")
        raise ModuleNotFoundError(module)

    def missing_map_file(candidates: list[Path], module_name: str, attribute: str):
        raise RuntimeError("GeoAtlas 地图功能需要依赖 `geopandas`。建议安装：uv sync --extra maps")

    monkeypatch.setattr(factory, "__import__", missing_map_import, raising=False)
    monkeypatch.setattr(factory, "_load_from_candidates", missing_map_file)

    map_plotter_cls = factory.get_map_plotter_cls(source_dir)

    assert map_plotter_cls is not None
    with pytest.raises(RuntimeError, match="geopandas.*uv sync --extra maps"):
        map_plotter_cls()
