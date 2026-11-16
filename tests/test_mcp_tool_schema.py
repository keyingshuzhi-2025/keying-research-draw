from src.mcp_server.server import _validation_diagnostics, get_plot_schema
from src.registry import plot_registry_payload


def test_plot_schema_aliases_match_plot_catalog():
    schema = get_plot_schema("bar")
    catalog_aliases = plot_registry_payload()["plots"]["bar"]["aliases"]

    assert isinstance(schema["aliases"], list)
    assert schema["aliases"] == catalog_aliases
    assert {"bar", "barplot", "horizontal_bar", "条形图"}.issubset(schema["aliases"])


def test_plot_schema_grid_description_is_unambiguous():
    schema = get_plot_schema("bar")
    grid = next(parameter for parameter in schema["parameters"] if parameter["name"] == "grid")

    assert grid["type"] == "boolean"
    assert "默认显示" in grid["description"]
    assert "设为 false 可关闭" in grid["description"]
    assert "关闭基础二维图网格线" not in grid["description"]


def test_quiver3d_schema_describes_automatic_arrow_scaling():
    schema = get_plot_schema("quiver3d")
    length = next(parameter for parameter in schema["parameters"] if parameter["name"] == "length")

    assert length["type"] == "number"
    assert "根据点间距自动缩放" in length["description"]


def test_unknown_column_diagnostic_lists_available_columns():
    diagnostics, suggested_config = _validation_diagnostics(
        errors=["x_col 指定的列“not_a_column”不在文件中。"],
        warnings=[],
        available_columns={"group", "value", "date"},
        config={"x_col": "not_a_column", "y_col": "value"},
    )

    assert diagnostics[0]["code"] == "unknown_column"
    assert diagnostics[0]["field"] == "x_col"
    assert diagnostics[0]["candidate_columns"] == ["date", "group", "value"]
    assert "date、group、value" in diagnostics[0]["suggestion"]
    assert suggested_config is None
