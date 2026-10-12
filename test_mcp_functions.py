#!/usr/bin/env python3
"""Test MCP server functions without triggering server initialization."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_mcp_functions():
    """Test MCP server functions directly."""
    print("Testing Research Draw MCP Server Functions...")
    
    # Test version by importing version module directly
    from src.version import __version__
    version = f"v{__version__}"
    print(f"✓ Version: {version}")
    assert version.startswith("v"), f"Version should start with 'v': {version}"
    
    # Test list plot groups by importing registry functions directly
    from src.registry import group_metadata, canonical_plots_by_group
    groups = group_metadata()
    plots_by_group = canonical_plots_by_group()
    assert len(groups) == 4, f"Expected 4 groups, got {len(groups)}"
    for group_key, group_info in groups.items():
        expected_count = len(plots_by_group.get(group_key, []))
        actual_count = group_info.get("plot_count", 0)  # We'll add this in our function
        # For now just check that we have the basic structure
        assert "label" in group_info
        assert "description" in group_info
    print(f"✓ Plot groups: {len(groups)} groups found")
    
    # Test list plots by importing registry functions directly
    from src.registry import plot_registry_payload, public_plot_name
    payload = plot_registry_payload()
    assert "plots" in payload, "Should contain 'plots' key"
    plots = payload["plots"]
    assert len(plots) > 40, f"Expected >40 plots, got {len(plots)}"
    print(f"✓ Available plots: {len(plots)} plots found")
    
    # Test get plot schema by importing registry functions directly
    from src.registry import (
        get_plot_schema as registry_get_plot_schema,
        required_fields_for_plot,
        default_args_for_plot,
        public_plot_name
    )
    plot_name = "box"
    canonical_name = public_plot_name(plot_name)
    assert canonical_name == "box", f"Expected canonical name 'box', got {canonical_name}"
    
    required = required_fields_for_plot(plot_name)
    assert isinstance(required, list), "Required fields should be a list"
    assert "group_col" in required, "Box plot should require 'group_col'"
    assert "value_col" in required, "Box plot should require 'value_col'"
    
    defaults = default_args_for_plot(plot_name)
    assert isinstance(defaults, dict), "Default args should be a dict"
    print("✓ Plot schema: Box plot schema valid")
    
    # Test the runner function directly
    from mcp_server.runner import ResearchDrawMCPRunner, _build_argv_from_config
    from pathlib import Path
    
    # Test argv building
    project_root = Path('.').resolve()
    argv = _build_argv_from_config('demo', 'box', {'title': 'Test Box Plot', 'save_name': 'test_box'}, project_root)
    expected_argv = ['--mode', 'demo', '--plot', 'box', '--title', 'Test Box Plot', '--save-name', 'test_box']
    assert argv == expected_argv, f"Expected {expected_argv}, got {argv}"
    print("✓ argv building: Correctly converts config to CLI arguments")
    
    # Test runner instantiation
    runner = ResearchDrawMCPRunner(project_root)
    assert runner.project_root == project_root
    assert runner.output_dir == project_root / "outputs" / "mcp"
    print("✓ Runner: Instantiated correctly")
    
    print("\n🎉 All function tests passed! MCP server components are working correctly.")
    return True

if __name__ == "__main__":
    try:
        test_mcp_functions()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)