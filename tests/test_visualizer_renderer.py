import pytest
from src.visualizer.renderer import render_stats_html
import os

def test_render_stats_html_basic():
    daily_data = [{"label": "PTS", "rows": [{"name": "A", "value": "10"}]}]
    html = render_stats_html(daily_data)
    assert "PTS" in html
    assert "A" in html
    assert "10" in html
    assert '<div class="separator">' not in html

def test_render_stats_html_combined():
    daily_data = [{"label": "PTS", "rows": [{"name": "A", "value": "10"}]}]
    weekly_data = [{"label": "REB", "rows": [{"name": "B", "value": "20"}]}]
    html = render_stats_html(daily_data, weekly_data)
    assert "PTS" in html
    assert "REB" in html
    assert "separator" in html
    assert "==== 以上為日統計 / 以下為週統計 (格式相同) ====" in html

def test_template_loading():
    # Verify that the renderer can find the template even when called from different locations
    daily_data = [{"label": "PTS", "rows": [{"name": "A", "value": "10"}]}]
    html = render_stats_html(daily_data)
    assert "<!DOCTYPE html>" in html
