#!/usr/bin/env python3
"""Basic test for Research Draw MCP server functionality."""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_mcp_server_basic():
    """Test basic MCP server functionality."""
    print("Testing Research Draw MCP Server...")
    
    # Test version
    from mcp_server.server import get_version
    version = get_version()
    print(f"✓ Version: {version}")
    assert version.startswith("v"), f"Version should start with 'v': {version}"
    
    # Test list plot groups
    from mcp_server.server import list_plot_groups
    groups_result = list_plot_groups()
    assert "groups" in groups_result, "Should contain 'groups' key"
    groups = groups_result["groups"]
    assert len(groups) == 4, f"Expected 4 groups, got {len(groups)}"
    print(f"✓ Plot groups: {len(groups)} groups found")
    
    # Test list plots
    from mcp_server.server import list_plots
    plots_result = list_plots()
    assert "plots" in plots_result, "Should contain 'plots' key"
    plots = plots_result["plots"]
    assert len(plots) > 40, f"Expected >40 plots, got {len(plots)}"
    print(f"✓ Available plots: {len(plots)} plots found")
    
    # Test get plot schema
    from mcp_server.server import get_plot_schema
    schema = get_plot_schema("box")
    assert "name" in schema, "Schema should contain 'name' key"
    assert schema["name"] == "box", f"Expected name 'box', got {schema['name']}"
    assert "required_fields" in schema, "Schema should contain 'required_fields' key"
    required = schema["required_fields"]
    assert "group_col" in required, "Box plot should require 'group_col'"
    assert "value_col" in required, "Box plot should require 'value_col'"
    print("✓ Plot schema: Box plot schema valid")
    
    # Test render plot (demo mode)
    from mcp_server.server import render_plot
    render_result = render_plot(
        mode="demo",
        plot="box",
        config={
            "title": "Test Box Plot",
            "save_name": "test_mcp_box"
        }
    )
    assert render_result.get("success") == True, f"Render should succeed: {render_result.get('message')}"
    assert "image" in render_result, "Result should contain 'image' field"
    assert render_result.get("path") is not None, "Result should contain path"
    assert "box" in render_result.get("path", ""), "Path should contain plot type"
    print("✓ Render plot: Demo box plot rendered successfully")
    
    # Verify image data is present
    image = render_result.get("image")
    assert image is not None, "Image should not be None"
    # ImageContent object should have data and mimeType attributes
    assert hasattr(image, "data"), "Image should have data attribute"
    assert hasattr(image, "mimeType"), "Image should have mimeType attribute"
    assert len(image.data) > 0, "Image data should not be empty"
    assert image.mimeType == "image/png", f"Expected PNG mime type, got {image.mimeType}"
    print(f"✓ Image data: {len(image.data)} bytes, {image.mimeType}")
    
    print("\n🎉 All tests passed! MCP server is working correctly.")
    return True

if __name__ == "__main__":
    try:
        test_mcp_server_basic()
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)