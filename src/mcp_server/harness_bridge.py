
import json
import argparse
from pathlib import Path
from typing import Any, Dict

from src.registry import (
    plot_registry_payload,
    public_plot_name,
    required_fields_for_plot,
    default_args_for_plot,
)
from src.registry.plot_registry import PLOT_ALIASES
from src.mcp_server.runner import ResearchDrawMCPRunner

def list_plots(group: str = None):
    payload = plot_registry_payload()
    plots = payload["plots"]
    if group:
        plots = {k: v for k, v in plots.items() if v["group"] == group}
    return {"plots": plots}

def get_schema(plot: str):
    canonical = public_plot_name(plot)
    if not canonical:
        return {"error": f"Unknown plot type: {plot}"}
    
    return {
        "name": canonical,
        "required_fields": required_fields_for_plot(canonical),
        "optional_fields": list(default_args_for_plot(canonical).keys()),
        "aliases": PLOT_ALIASES.get(canonical, [canonical])
    }

def render_plot(mode: str, plot: str, config: Dict[str, Any]):
    try:
        runner = ResearchDrawMCPRunner()
        success, message, output_path = runner.render_plot(mode, plot, config)
        if not success or output_path is None:
            return {"success": False, "error": message}
        return {"success": True, "path": str(output_path), "message": message}
    except Exception as exc:
        return {"success": False, "error": str(exc)}

def main():
    parser = argparse.ArgumentParser(description="Research Draw Harness Bridge")
    subparsers = parser.add_subparsers(dest="command")

    # List plots
    list_parser = subparsers.add_parser("list")
    list_parser.add_argument("--group", type=str, help="Filter by group")

    # Get schema
    schema_parser = subparsers.add_parser("schema")
    schema_parser.add_argument("plot", type=str, help="Plot name")

    # Render plot
    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--mode", type=str, required=True, choices=["demo", "file", "custom"])
    render_parser.add_argument("--plot", type=str, required=True)
    render_parser.add_argument("--config", type=str, required=True, help="JSON string of config parameters")

    args = parser.parse_args()

    if args.command == "list":
        print(json.dumps(list_plots(args.group), ensure_ascii=False))
    elif args.command == "schema":
        print(json.dumps(get_schema(args.plot), ensure_ascii=False))
    elif args.command == "render":
        try:
            config = json.loads(args.config)
            print(json.dumps(render_plot(args.mode, args.plot, config), ensure_ascii=False))
        except json.JSONDecodeError:
            print(json.dumps({"success": False, "error": "Invalid JSON in --config"}))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
