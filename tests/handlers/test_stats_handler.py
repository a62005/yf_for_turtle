import pytest
from src.handlers.stats_handler import StatsHandler

def test_stats_handler_can_handle():
    handler = StatsHandler()
    assert handler.can_handle("#戰績") is True
    assert handler.can_handle("#當天戰績") is True
    assert handler.can_handle("#當週戰績") is True
    assert handler.can_handle("#戰績W23") is True
    assert handler.can_handle("#戰績w23") is True
    assert handler.can_handle("#戰績20250101") is True
    
    assert handler.can_handle("#獎金") is False
    assert handler.can_handle("戰績") is False

def test_stats_handler_parse_command():
    handler = StatsHandler()
    assert handler.parse_command("#戰績") == ("combined", None)
    assert handler.parse_command("#當天戰績") == ("daily", None)
    assert handler.parse_command("#當週戰績") == ("weekly", None)
    assert handler.parse_command("#戰績W23") == ("specific_week", 23)
    assert handler.parse_command("#戰績w23") == ("specific_week", 23)
    assert handler.parse_command("#戰績20250101") == ("specific_date", "2025-01-01")
    assert handler.parse_command("#無效") == (None, None)
