from pathlib import Path

from src.cli.parser import build_parser
from src.mcp_server.runner import _build_argv_from_config


def test_build_argv_attaches_negative_vector_values_to_options():
    argv = _build_argv_from_config(
        "custom",
        "quiver3d",
        {
            "x": [-1, 0, 1],
            "y": [0, 1, 2],
            "z": [0, 10, 20],
            "u": [-0.2, -0.1, 0.0],
            "v": [0.05, 0.1, 0.15],
            "w": [0, -0.01, -0.02],
            "xlabel": "经度",
        },
        Path("."),
    )

    parsed = build_parser().parse_args(argv)

    assert parsed.x == "-1,0,1"
    assert parsed.u == "-0.2,-0.1,0.0"
    assert parsed.w == "0,-0.01,-0.02"
    assert parsed.xlabel == "经度"


def test_build_argv_accepts_quiver_length_scale():
    argv = _build_argv_from_config("custom", "quiver3d", {"length": 8.0}, Path("."))

    assert "--length=8.0" in argv
