"""Runner for Research Draw MCP server.

Handles the conversion from MCP tool parameters to CLI arguments
and execution of the Research Draw application.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from src.main import ResearchDrawApp


def _dest_to_arg_flag(dest: str) -> str:
    """Convert a destination name (e.g., 'save_name') to CLI argument flag (e.g., '--save-name').
    
    Args:
        dest: Destination name from argparse (underscores)
        
    Returns:
        CLI argument flag with hyphens
    """
    return f"--{dest.replace('_', '-')}"


def _build_argv_from_config(
    mode: str, plot: str, config: Dict[str, Any], project_root: Path
) -> list[str]:
    """Build CLI argument list from MCP tool parameters.

    Args:
        mode: One of "demo", "custom", or "file"
        plot: Plot type name (e.g., "box", "scatter3d")
        config: Configuration dictionary mapping CLI argument names to values
        project_root: Project root directory

    Returns:
        List of command-line arguments suitable for passing to ResearchDrawApp
    """
    argv = ["--mode", mode, "--plot", plot]

    # Handle special cases first
    if mode == "file" and config.get("file"):
        argv.extend(["--file", str(config["file"])])

    # Add all other config parameters
    for key, value in config.items():
        # Skip already handled parameters
        if key in ("mode", "plot", "file"):
            continue

        # Handle None values (skip unless it's a flag that should be False)
        if value is None:
            continue

        # Handle boolean flags
        if isinstance(value, bool):
            if value:
                argv.extend([_dest_to_arg_flag(key)])
            # If False, we don't add the flag (default behavior)
            continue

        # Handle list-like parameters (e.g., --group can be repeated)
        if isinstance(value, (list, tuple)):
            for item in value:
                argv.extend([_dest_to_arg_flag(key), str(item)])
            continue

        # Handle all other parameter types
        argv.extend([_dest_to_arg_flag(key), str(value)])

    return argv


class ResearchDrawMCPRunner:
    """Runner that executes Research Draw and captures results."""

    def __init__(self, project_root: Optional[Path] = None):
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self._ensure_output_dir()

    def _ensure_output_dir(self) -> None:
        """Ensure the MCP output directory exists."""
        self.output_dir = self.project_root / "outputs" / "mcp"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _prepare_environment(self) -> Dict[str, str]:
        """Prepare environment variables for headless execution."""
        env = os.environ.copy()
        # Force headless/backend settings
        env["MPLBACKEND"] = "Agg"
        env["PLOT_BACKEND"] = "Agg"
        env["HEADLESS"] = "1"
        # Set output directory override
        env["PLOT_OUTDIR_OVERRIDE"] = str(self.output_dir)
        return env

    def render_plot(
        self, mode: str, plot: str, config: Dict[str, Any]
    ) -> Tuple[bool, str, Optional[Path]]:
        """Render a plot and return the result.

        Args:
            mode: Rendering mode ("demo", "custom", or "file")
            plot: Plot type to render
            config: Configuration parameters for the plot

        Returns:
            Tuple of (success, message, output_path)
            If success is False, output_path is None
            If success is True, output_path is the path to the saved image
        """
        # Ensure output directory exists
        self._ensure_output_dir()

        # Prepare environment
        env = self._prepare_environment()

        # Build argv
        argv = _build_argv_from_config(mode, plot, config, self.project_root)

        # Save original environment and argv
        old_env = dict(os.environ)
        old_argv = sys.argv.copy()

        try:
            # Set environment
            os.environ.update(env)
            sys.argv = ["research-draw"] + argv

            # Create and run the application
            app = ResearchDrawApp(argv=argv)
            app.run()

            # If we get here, execution succeeded
            # Determine the output file path
            # We need to figure out what filename was generated
            save_name = config.get("save_name")
            fmt = config.get("fmt", "PNG").lower()

            if save_name:
                # User provided save name
                filename = f"{save_name}.{fmt}"
            else:
                # Need to determine auto-generated name
                # This is tricky - we'll look for the most recent file in output dir
                # as a fallback, but ideally we'd capture it from the app
                filename = None

            output_path = self.output_dir / filename if filename else None

            if filename and output_path.exists():
                return True, f"Successfully rendered {plot}", output_path
            else:
                # Try to find the most recent image file in the output directory
                image_files = list(self.output_dir.glob("*.png")) + list(
                    self.output_dir.glob("*.svg")
                ) + list(self.output_dir.glob("*.pdf"))
                if image_files:
                    # Return the most recently modified file
                    latest_file = max(image_files, key=lambda p: p.stat().st_mtime)
                    return (
                        True,
                        f"Successfully rendered {plot} (auto-named)",
                        latest_file,
                    )
                else:
                    return (
                        False,
                        "Render completed but no output file found",
                        None,
                    )

        except Exception as e:
            return False, f"Error rendering plot: {str(e)}", None
        finally:
            # Restore environment
            os.environ.clear()
            os.environ.update(old_env)
            sys.argv = old_argv