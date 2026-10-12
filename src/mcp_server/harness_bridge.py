
import sys
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
from src.main import ResearchDrawApp

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
    # The ResearchDrawApp.run() method processes sys.argv.
    # We simulate the CLI call by constructing argv.
    argv = ["--mode", mode, "--plot", plot]
    
    for key, value in config.items():
        if key in ("mode", "plot"):
            continue
        
        flag = f"--{key.replace('_', '-')}"
        if isinstance(value, bool):
            if value:
                argv.append(flag)
        elif isinstance(value, (list, tuple)):
            for item in value:
                argv.extend([flag, str(item)])
        else:
            argv.extend([flag, str(value)])
            
    try:
        # Note: ResearchDrawApp handles its own output directory via environment variables 
        # or config. We assume it uses the default outputs/figures or outputs/mcp.
        app = ResearchDrawApp(argv=argv)
        app.run()
        
        # To find the output file, we look for the most recent image in the output directory
        output_dirs = [Path("outputs/figures"), Path("outputs/mcp")]
        latest_file = None
        max_mtime = 0
        
        for d in output_dirs:
            if d.exists():
                for f in d.glob("*.*"):
                    if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".pdf", ".svg"):
                        mtime = f.stat().st_mtime
                        if mtime > max_mtime:
                            max_mtime = mtime
                            latest_file = f
                            
        if latest_file:
            return {
                "success": True,
                "path": str(latest_file.absolute()),
                "message": f"Successfully rendered {plot}"
            }
        else:
            return {"success": False, "error": "Render completed but output file not found."}
            
    except Exception as e:
        return {"success": False, "error": str(e)}

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
