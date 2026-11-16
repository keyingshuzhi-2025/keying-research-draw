from types import SimpleNamespace

import pytest

from src.dispatch.handlers import static2d
from src.dispatch.handlers.static2d import Static2DHandler


class _Series:
    def __init__(self, values):
        self.values = values


class _Frame:
    def __getitem__(self, column):
        return _Series(["Control", "Treatment"] if column == "group" else [1, 3])


class _Plotter:
    def bar_plot(self, *args, **kwargs):
        self.kwargs = kwargs
        return kwargs

    def column_plot(self, *args, **kwargs):
        self.kwargs = kwargs
        return kwargs


@pytest.mark.parametrize(
    ("plot", "explicit_xlabel", "explicit_ylabel", "expected_xlabel", "expected_ylabel"),
    [
        ("bar", None, None, "value", "group"),
        ("column", None, None, "group", "value"),
        ("bar", "Measurement", "Treatment group", "Measurement", "Treatment group"),
    ],
)
def test_file_axis_labels_match_rendered_orientation(
    monkeypatch,
    tmp_path,
    plot,
    explicit_xlabel,
    explicit_ylabel,
    expected_xlabel,
    expected_ylabel,
):
    monkeypatch.setattr(static2d, "auto_sep", lambda _path, _sep: ",")
    monkeypatch.setattr(static2d, "read_dataframe", lambda _path, _sep: _Frame())
    args = SimpleNamespace(
        file=str(tmp_path / "data.csv"),
        sep=None,
        x_col="group",
        y_col="value",
        group_col=None,
        xlabel=explicit_xlabel,
        ylabel=explicit_ylabel,
        title="E2E",
        aggregation="mean",
        palette="tab10",
        grid=True,
        group_mode="grouped",
        show_values=False,
        tick_rotation=0,
    )
    handler = Static2DHandler(SimpleNamespace(args=args))
    plotter = _Plotter()

    handler._render_file(plotter, plot)

    assert plotter.kwargs["xlabel"] == expected_xlabel
    assert plotter.kwargs["ylabel"] == expected_ylabel
