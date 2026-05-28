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
    daily_stats = {
        "stat_4": "14", "stat_3": "24", "FG%": "0.583", "stat_7": "3", "stat_6": "4", "FT%": "0.750",
        "3PTM": "4", "PTS": "35", "REB": "9", "AST": "12", "ST": "2", "BLK": "1", "TO": "3"
    }
    weekly_stats = {
        "stat_4": "80", "stat_3": "150", "FG%": "0.533", "stat_7": "20", "stat_6": "25", "FT%": "0.800",
        "3PTM": "18", "PTS": "210", "REB": "55", "AST": "62", "ST": "12", "BLK": "8", "TO": "15"
    }
    
    formatted = handler.format_user_stats(player_info, daily_stats, weekly_stats, "2026-05-28", "24")
    
    # 斷言回傳必須是字典格式 (Flex Message Bubble)
    assert isinstance(formatted, dict)
    assert formatted["type"] == "bubble"
    
    # 驗證 Header 部分的玩家暱稱與官方名稱
    header_box = formatted["header"]["contents"]
    assert header_box[0]["text"] == "韋哥"
    assert header_box[1]["text"] == "Vigo's Superteam"
    assert header_box[2]["text"] == "2026-05-28"
    
    # 驗證 Body 部分的雙層對比格線 (當日 + 分割線 + 當週標頭 + 當週)
    body_contents = formatted["body"]["contents"]
    
    # 1. 當日數據
    daily_box = body_contents[0]["contents"]
    assert daily_box[0]["contents"][0]["text"] == "FGM/A"
    assert daily_box[0]["contents"][1]["text"] == "14/24"
    assert daily_box[5]["contents"][0]["text"] == "PTS"
    assert daily_box[5]["contents"][1]["text"] == "35"
    
    # 2. 分割線
    assert body_contents[1]["type"] == "separator"
    
    # 3. 當週標頭
    assert body_contents[2]["text"] == "W24"
    
    # 4. 當週數據
    weekly_box = body_contents[3]["contents"]
    assert weekly_box[0]["contents"][0]["text"] == "FGM/A"
    assert weekly_box[0]["contents"][1]["text"] == "80/150"
    assert weekly_box[5]["contents"][0]["text"] == "PTS"
    assert weekly_box[5]["contents"][1]["text"] == "210"
