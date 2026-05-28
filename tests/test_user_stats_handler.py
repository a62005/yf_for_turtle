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
    assert handler.can_handle("#玩家") is True
    assert handler.can_handle("#玩家  ") is True
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
    
    # 驗證 Body 部分的雙層對比格線 (玩家資訊標頭 + 日期標頭 + 當日 + 分割線 + 當週標頭 + 當週)
    body_contents = formatted["body"]["contents"]
    
    # 1. 玩家資訊標頭
    assert body_contents[0]["contents"][0]["text"] == "韋哥"
    assert body_contents[0]["contents"][1]["text"] == "Vigo's Superteam"
    
    # 2. 日期標頭
    assert body_contents[1]["text"] == "2026-05-28"
    
    # 3. 當日數據
    daily_box = body_contents[2]["contents"]
    assert daily_box[0]["contents"][0]["text"] == "FGM/A"
    assert daily_box[0]["contents"][1]["text"] == "14/24"
    assert daily_box[5]["contents"][0]["text"] == "PTS"
    assert daily_box[5]["contents"][1]["text"] == "35"
    
    # 4. 分割線
    assert body_contents[3]["type"] == "separator"
    
    # 5. 當週標頭
    assert body_contents[4]["text"] == "W24"
    
    # 6. 當週數據
    weekly_box = body_contents[5]["contents"]
    assert weekly_box[0]["contents"][0]["text"] == "FGM/A"
    assert weekly_box[0]["contents"][1]["text"] == "80/150"
    assert weekly_box[5]["contents"][0]["text"] == "PTS"
    assert weekly_box[5]["contents"][1]["text"] == "210"


def test_format_user_stats_with_composite_keys():
    handler = UserStatsHandler()
    player_info = {
        "manager_name": "肥儒",
        "official_name": "Feiru's Superteam"
    }
    
    # 模擬真實的 composite keys {"FGM/FGA": "5/10", "FTM/FTA": "3/4"} 傳入
    daily_stats = {
        "FGM/FGA": "5/10", "FG%": "0.500", "FTM/FTA": "3/4", "FT%": "0.750",
        "3PTM": "2", "PTS": "15", "REB": "5", "AST": "6", "ST": "1", "BLK": "0", "TO": "2"
    }
    weekly_stats = {
        "FGM/FGA": "35/70", "FG%": "0.500", "FTM/FTA": "21/28", "FT%": "0.750",
        "3PTM": "14", "PTS": "105", "REB": "35", "AST": "42", "ST": "7", "BLK": "2", "TO": "14"
    }
    
    formatted = handler.format_user_stats(player_info, daily_stats, weekly_stats, "2026-05-28", "24")
    
    assert isinstance(formatted, dict)
    body_contents = formatted["body"]["contents"]
    
    # 驗證玩家資訊標頭
    assert body_contents[0]["contents"][0]["text"] == "肥儒"
    assert body_contents[0]["contents"][1]["text"] == "Feiru's Superteam"
    
    # 驗證日期標頭
    assert body_contents[1]["text"] == "2026-05-28"
    
    # 驗證當日數據
    daily_box = body_contents[2]["contents"]
    assert daily_box[0]["contents"][0]["text"] == "FGM/A"
    assert daily_box[0]["contents"][1]["text"] == "5/10"
    assert daily_box[1]["contents"][0]["text"] == "FG%"
    assert daily_box[1]["contents"][1]["text"] == "50.0%"
    assert daily_box[2]["contents"][0]["text"] == "FTM/A"
    assert daily_box[2]["contents"][1]["text"] == "3/4"
    assert daily_box[3]["contents"][0]["text"] == "FT%"
    assert daily_box[3]["contents"][1]["text"] == "75.0%"
    
    # 驗證當週數據
    weekly_box = body_contents[5]["contents"]
    assert weekly_box[0]["contents"][0]["text"] == "FGM/A"
    assert weekly_box[0]["contents"][1]["text"] == "35/70"
    assert weekly_box[2]["contents"][0]["text"] == "FTM/A"
    assert weekly_box[2]["contents"][1]["text"] == "21/28"


def test_execute_user_stats_no_nickname(mocker):
    handler = UserStatsHandler()
    
    # Mock message event text
    mock_event = MagicMock()
    mock_event.message.text = "#玩家"
    
    mock_config = MagicMock()
    
    # Spy / Mock BaseHandler's reply_player_list method
    mock_reply_player_list = mocker.patch.object(handler, "reply_player_list")
    
    handler.execute(mock_event, mock_config)
    
    mock_reply_player_list.assert_called_once_with(mock_event, mock_config, is_matchup=False)


