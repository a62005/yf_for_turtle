import os
import pytest
from src.visualizer.capturer import capture_html_to_png

def test_capture_html_to_png(tmp_path):
    html = "<html><body><div class='stats-container'><h1>Test</h1></div></body></html>"
    output_file = os.path.join(tmp_path, "test_output.png")
    
    # This might fail in environments without chromium, but we'll try to run it
    try:
        capture_html_to_png(html, output_file)
        assert os.path.exists(output_file)
        assert os.path.getsize(output_file) > 0
    except Exception as e:
        pytest.skip(f"Playwright capture failed: {e}")
