from __future__ import annotations

import json

import pytest

from src.cli.parser import build_parser, merge_args_with_config, print_examples_and_exit
from src.registry.plot_registry import ALL_PUBLIC_PLOTS


def test_parser_basic_args():
    parser = build_parser()
    args = parser.parse_args(["--mode", "file", "--plot", "scatter", "--x-col", "x", "--y-col", "y"])
    assert args.mode == "file"
    assert args.plot == "scatter"
    assert args.x_col == "x"
    assert args.y_col == "y"


def test_parser_3d_args():
    parser = build_parser()
    args = parser.parse_args(
        [
            "--mode",
            "file",
            "--plot",
            "isosurface3d",
            "--x-col",
            "x",
            "--y-col",
            "y",
            "--z-col",
            "z",
            "--scalar-col",
            "density",
            "--z",
            "1,2,3",
            "--u-col",
            "u",
            "--v-col",
            "v",
            "--w-col",
            "w",
            "--zlabel",
            "Intensity",
            "--elev",
            "35",
            "--azim",
            "40",
            "--levels",
            "20",
            "--rstride",
            "3",
            "--cstride",
            "4",
            "--iso-level",
            "0.32",
            "--slice-x",
            "0.1",
            "--slice-y",
            "0.2",
            "--slice-z",
            "0.3",
            "--max-arrows",
            "900",
        ]
    )
    assert args.plot == "isosurface3d"
    assert args.x_col == "x"
    assert args.y_col == "y"
    assert args.z_col == "z"
    assert args.scalar_col == "density"
    assert args.u_col == "u"
    assert args.v_col == "v"
    assert args.w_col == "w"
    assert args.z == "1,2,3"
    assert args.zlabel == "Intensity"
    assert args.elev == 35.0
    assert args.azim == 40.0
    assert args.levels == 20
    assert args.rstride == 3
    assert args.cstride == 4
    assert args.iso_level == 0.32
    assert args.slice_x == 0.1
    assert args.slice_y == 0.2
    assert args.slice_z == 0.3
    assert args.max_arrows == 900


def test_config_merge_keeps_cli_priority(tmp_path):
    parser = build_parser()
    cfg = {"plot": "volcano", "mode": "custom", "dpi": 150, "no_show": True}
    cfg_path = tmp_path / "cfg.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    argv = ["--config", str(cfg_path), "--plot", "box"]
    args = parser.parse_args(argv)
    merged = merge_args_with_config(parser, args, argv=argv)
    assert merged.plot == "box"
    assert merged.mode == "custom"
    assert merged.dpi == 150
    assert merged.no_show is True


def test_config_schema_rejects_unknown_key(tmp_path):
    parser = build_parser()
    cfg = {"plot": "box", "unknown_option": 1}
    cfg_path = tmp_path / "bad_cfg.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    argv = ["--config", str(cfg_path)]
    args = parser.parse_args(argv)
    with pytest.raises(ValueError):
        merge_args_with_config(parser, args, argv=argv)


def test_help_examples_contains_a_demo_command_for_every_plot(capsys):
    with pytest.raises(SystemExit) as exit_info:
        print_examples_and_exit()

    assert exit_info.value.code == 0
    output = capsys.readouterr().out
    for plot_name in ALL_PUBLIC_PLOTS:
        assert f"--mode demo --plot {plot_name} " in output
