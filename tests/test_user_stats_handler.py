import pytest
from unittest.mock import MagicMock
from src.handlers.user_stats_handler import UserStatsHandler

def test_user_stats_handler_can_handle(mocker):
    # Mock load_config 以提供 team_mapping 檔案配置
    mocker.patch("src.handlers.user_stats_handler.load_config", return_value={"TEAM_MAPPING_FILE": "team_mapping.json"})
    
    # Mock 讀取 team_mapping.json 的回傳內容 (模擬有 韋哥，但沒有 詹姆斯)
    mock_mapping = {"1": "韋哥", "2": "Jerry"}
    mocker.patch("src.handlers.user_stats_handler.UserStatsHandler._load_team_mapping", return_value=mock_mapping)
    
    handler = UserStatsHandler()
    
    # 測試比對
    assert handler.can_handle("#玩家 韋哥") is True
    assert handler.can_handle("#玩家 Jerry") is True
    assert handler.can_handle("#玩家 詹姆斯") is False  # 沒登錄 -> 略過
    assert handler.can_handle("#玩家") is False
    assert handler.can_handle("#球員 韋哥") is False

def test_format_user_stats():
    handler = UserStatsHandler()
    player_info = {
        "manager_name": "韋哥",
        "official_name": "Vigo's Superteam"
    }
    
    # 模擬當日數據
    daily_stats = {
        "stat_4": "14",
        "stat_3": "24",
        "FG%": "0.583",
        "stat_7": "3",
        "stat_6": "4",
        "FT%": "0.750",
        "3PTM": "4",
        "PTS": "35",
        "REB": "9",
        "AST": "12",
        "ST": "2",
        "BLK": "1",
        "TO": "3"
    }
    
    # 模擬當週累積數據
    weekly_stats = {
        "stat_4": "80",
        "stat_3": "150",
        "FG%": "0.533",
        "stat_7": "20",
        "stat_6": "25",
        "FT%": "0.800",
        "3PTM": "18",
        "PTS": "210",
        "REB": "55",
        "AST": "62",
        "ST": "12",
        "BLK": "8",
        "TO": "15"
    }
    
    formatted = handler.format_user_stats(player_info, daily_stats, weekly_stats, "2026-05-28", "24")
    
    expected = (
        "韋哥\n"
        "Vigo's Superteam\n"
        "2026-05-28\n"
        "```\n"
        "FGM/A :           14/24\n"
        "FG% :             58.3%\n"
        "FTM/A :             3/4\n"
        "FT% :             75.0%\n"
        "3PM :                 4\n"
        "PTS :                35\n"
        "REB :                 9\n"
        "AST :                12\n"
        "STL :                 2\n"
        "BLK :                 1\n"
        "TO :                  3\n"
        "```\n"
        "W24\n"
        "```\n"
        "FGM/A :          80/150\n"
        "FG% :             53.3%\n"
        "FTM/A :           20/25\n"
        "FT% :             80.0%\n"
        "3PM :                18\n"
        "PTS :               210\n"
        "REB :                55\n"
        "AST :                62\n"
        "STL :                12\n"
        "BLK :                 8\n"
        "TO :                 15\n"
        "```"
    )
    assert formatted.strip() == expected.strip()
