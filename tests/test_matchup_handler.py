import pytest
from unittest.mock import MagicMock, patch
from src.handlers.matchup_handler import MatchupHandler
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from datetime import datetime
import pytz

def test_matchup_handler_can_handle(mocker):
    mocker.patch("src.handlers.matchup_handler.load_config", return_value={"TEAM_MAPPING_FILE": "team_mapping.json"})
    mocker.patch.object(MatchupHandler, "_load_team_mapping", return_value={"1": "韋哥", "2": "Jerry"})
    
    handler = MatchupHandler()
    assert handler.can_handle("#對戰 韋哥") is True
    assert handler.can_handle("#對戰 Jerry") is True
    assert handler.can_handle("#對戰 詹姆斯") is False # 沒登錄 -> 略過
    assert handler.can_handle("#對戰") is False

def test_matchup_compare_logic():
    handler = MatchupHandler()
    
    # 測試 TO 越小越好，其餘越大越好，零值轉 "-"
    my_stats = {
        "FG%": "0.514", "FGM/FGA": "180/350", "FT%": "0.0", "FTM/FTA": "0/0",
        "3PTM": "35", "PTS": "450", "REB": "110", "AST": "95", "ST": "25", "BLK": "12", "TO": "32"
    }
    opp_stats = {
        "FG%": "0.485", "FGM/FGA": "165/340", "FT%": "0.750", "FTM/FTA": "15/20",
        "3PTM": "42", "PTS": "410", "REB": "125", "AST": "80", "ST": "20", "BLK": "18", "TO": "38"
    }
    
    comp_res = handler.compare_stats(my_stats, opp_stats)
    
    # 驗證 9-Cat 勝負 (韋哥贏：FG%, PTS, AST, ST, TO；落後：FT%, 3PTM, REB, BLK -> 比分 5:4)
    assert comp_res["wins"] == 5
    assert comp_res["losses"] == 4
    assert comp_res["ties"] == 0
    
    # 驗證單一指標的勝負標記
    # FG%: 我方贏 (51.4% > 48.5%)
    assert comp_res["details"]["FG%"]["status"] == "my_win"
    assert comp_res["details"]["FG%"]["my_val"] == "51.4%"
    assert comp_res["details"]["FG%"]["opp_val"] == "48.5%"
    
    # FT%: 我方為 0 顯示為 "-"，落後
    assert comp_res["details"]["FT%"]["status"] == "opp_win"
    assert comp_res["details"]["FT%"]["my_val"] == "-"
    assert comp_res["details"]["FT%"]["opp_val"] == "75.0%"
    
    # TO: 我方 32 < 38 贏
    assert comp_res["details"]["TO"]["status"] == "my_win"
    
    # FGM/A: 輔助行，不用標註較優方，無 status
    assert "status" not in comp_res["details"]["FGM/A"]
    assert comp_res["details"]["FGM/A"]["my_val"] == "180/350"

def test_matchup_compare_logic_edge_cases():
    handler = MatchupHandler()
    
    # 測試含有無效字串 (如 "N/A"、"abc") 或缺失鍵時的安全降級
    # 以及累計指標 "0" 顯示為 "0" (而非 "-")，而百分比 "0.0" 仍顯示為 "-"
    my_stats = {
        "FG%": "0.0", "FGM/FGA": "0/0", "FT%": "abc", "FTM/FTA": "0/0",
        "3PTM": "0", "PTS": "N/A", "REB": "10", "AST": None, "ST": "0.0", "BLK": "5", "TO": "0"
    }
    opp_stats = {
        "FG%": "0.450", "FGM/FGA": "90/200", "FT%": "0.800", "FTM/FTA": "8/10",
        "3PTM": "5", "PTS": "100", "REB": "abc", "AST": "2", "ST": "1", "BLK": None, "TO": "0"
    }
    
    comp_res = handler.compare_stats(my_stats, opp_stats)
    
    # 1. 驗證累計數值為 "0" 或 "0.0" 時，to_val_str 應保持 "0"
    # ST: my_stats 是 "0.0" -> my_val 應為 "0"，opp_stats 是 "1" -> opp_val 應為 "1"
    # 由於 0.0 < 1，ST 判定為 opp_win
    assert comp_res["details"]["ST"]["my_val"] == "0"
    assert comp_res["details"]["ST"]["opp_val"] == "1"
    assert comp_res["details"]["ST"]["status"] == "opp_win"
    
    # 3PTM: my_stats 是 "0" -> my_val 應為 "0"，opp_val 應為 "5"，opp_win
    assert comp_res["details"]["3PTM"]["my_val"] == "0"
    assert comp_res["details"]["3PTM"]["status"] == "opp_win"

    # TO: my_val = "0", opp_val = "0", my_num = 0.0, opp_num = 0.0 -> tie
    assert comp_res["details"]["TO"]["my_val"] == "0"
    assert comp_res["details"]["TO"]["opp_val"] == "0"
    assert comp_res["details"]["TO"]["status"] == "tie"
    
    # 2. 驗證百分比 "0.0" 依然為 "-"
    assert comp_res["details"]["FG%"]["my_val"] == "-"
    assert comp_res["details"]["FG%"]["opp_val"] == "45.0%"
    assert comp_res["details"]["FG%"]["status"] == "opp_win"

    # 3. 驗證無效字串 ("abc", "N/A") 或 None 轉換為 "-" 且安全降級為數值 0.0
    # FT%: my_stats 是 "abc" 轉換成 my_val_str = "-" 且 my_num = 0.0
    # opp_stats 是 "0.800" 轉換成 80.0%，判定為 opp_win
    assert comp_res["details"]["FT%"]["my_val"] == "-"
    assert comp_res["details"]["FT%"]["opp_val"] == "80.0%"
    assert comp_res["details"]["FT%"]["status"] == "opp_win"

    # PTS: my_stats 是 "N/A" 轉換成 my_val_str = "-" 且 my_num = 0.0
    # opp_stats 是 "100" 轉換成 "100"，判定為 opp_win
    assert comp_res["details"]["PTS"]["my_val"] == "-"
    assert comp_res["details"]["PTS"]["opp_val"] == "100"
    assert comp_res["details"]["PTS"]["status"] == "opp_win"

    # REB: my_stats 是 "10"，opp_stats 是 "abc" -> opp_val_str = "-" 且 opp_num = 0.0
    # 10 > 0.0，判定為 my_win
    assert comp_res["details"]["REB"]["my_val"] == "10"
    assert comp_res["details"]["REB"]["opp_val"] == "-"
    assert comp_res["details"]["REB"]["status"] == "my_win"

    # AST: my_stats 是 None -> my_val_str = "-" 且 my_num = 0.0
    # opp_stats 是 "2" -> opp_val_str = "2"，判定為 opp_win
    assert comp_res["details"]["AST"]["my_val"] == "-"
    assert comp_res["details"]["AST"]["opp_val"] == "2"
    assert comp_res["details"]["AST"]["status"] == "opp_win"

    # BLK: my_stats 是 "5"，opp_stats 是 None -> opp_val_str = "-" 且 opp_num = 0.0
    # 5 > 0.0，判定為 my_win
    assert comp_res["details"]["BLK"]["my_val"] == "5"
    assert comp_res["details"]["BLK"]["opp_val"] == "-"
    assert comp_res["details"]["BLK"]["status"] == "my_win"


def test_format_matchup_stats():
    handler = MatchupHandler()
    
    player_info = {
        "my_nickname": "韋哥",
        "my_official": "Vigo's Superteam",
        "opp_nickname": "Jerry",
        "opp_official": "Jerry's Awesome"
    }
    
    comp_res = {
        "wins": 5, "losses": 4, "ties": 0,
        "details": {
            "FGM/A": {"my_val": "180/350", "opp_val": "165/340"},
            "FTM/A": {"my_val": "-", "opp_val": "15/20"},
            "FG%": {"status": "my_win", "my_val": "51.4%", "opp_val": "48.5%"},
            "FT%": {"status": "opp_win", "my_val": "-", "opp_val": "75.0%"},
            "3PTM": {"status": "opp_win", "my_val": "35", "opp_val": "42"},
            "PTS": {"status": "my_win", "my_val": "450", "opp_val": "410"},
            "REB": {"status": "opp_win", "my_val": "110", "opp_val": "125"},
            "AST": {"status": "my_win", "my_val": "95", "opp_val": "80"},
            "ST": {"status": "my_win", "my_val": "25", "opp_val": "20"},
            "BLK": {"status": "opp_win", "my_val": "12", "opp_val": "18"},
            "TO": {"status": "my_win", "my_val": "32", "opp_val": "38"}
        }
    }
    
    bubble = handler.format_matchup_stats(player_info, comp_res, "24")
    
    assert isinstance(bubble, dict)
    assert bubble["type"] == "bubble"
    
    body = bubble["body"]["contents"]
    
    # 驗證 Header 第一層：中文暱稱 (韋哥 VS Jerry)
    header_box = body[1]
    assert header_box["contents"][0]["text"] == "韋哥"
    assert header_box["contents"][0]["weight"] == "bold"
    assert header_box["contents"][0]["size"] == "xl"
    assert header_box["contents"][0]["color"] == "#111111"
    
    assert header_box["contents"][1]["text"] == "VS"
    assert header_box["contents"][1]["weight"] == "bold"
    assert header_box["contents"][1]["size"] == "sm"
    assert header_box["contents"][1]["color"] == "#aaaaaa"
    
    assert header_box["contents"][2]["text"] == "Jerry"
    assert header_box["contents"][2]["weight"] == "bold"
    assert header_box["contents"][2]["size"] == "xl"
    assert header_box["contents"][2]["color"] == "#111111"
    
    # 驗證 Header 第二層：官方隊名
    team_name_box = body[2]
    assert team_name_box["contents"][0]["text"] == "Vigo's Superteam"
    assert team_name_box["contents"][0]["size"] == "xxs"
    assert team_name_box["contents"][0]["color"] == "#999999"
    
    assert team_name_box["contents"][2]["text"] == "Jerry's Awesome"
    assert team_name_box["contents"][2]["size"] == "xxs"
    assert team_name_box["contents"][2]["color"] == "#999999"
    
    # 驗證 Header 第三層：比分對決 (5:4，我方領先大黑 20px/bold/#111111，落後小灰 18px/regular/#aaaaaa)
    score_box = body[3]
    assert score_box["contents"][0]["text"] == "5"
    assert score_box["contents"][0]["size"] == "20px"
    assert score_box["contents"][0]["weight"] == "bold"
    assert score_box["contents"][0]["color"] == "#111111"
    
    assert score_box["contents"][2]["text"] == "4"
    assert score_box["contents"][2]["size"] == "18px"
    assert score_box["contents"][2]["weight"] == "regular"
    assert score_box["contents"][2]["color"] == "#aaaaaa"
    
    # 驗證 Body 11 行指標 (如 FG%，我方贏 -> 我方大黑，對手小灰)
    fg_row = body[5]["contents"][1] # index 5 is the box containing rows, index 1 is FG% row
    assert fg_row["contents"][0]["text"] == "51.4%"
    assert fg_row["contents"][0]["weight"] == "bold"
    assert fg_row["contents"][0]["size"] == "16px"
    assert fg_row["contents"][0]["color"] == "#111111"
    
    assert fg_row["contents"][1]["text"] == "FG%"
    
    assert fg_row["contents"][2]["text"] == "48.5%"
    assert fg_row["contents"][2]["weight"] == "regular"
    assert fg_row["contents"][2]["size"] == "14px"
    assert fg_row["contents"][2]["color"] == "#aaaaaa"


@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.reply_token = "dummy_reply_token"
    return event

@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)

@patch("src.handlers.matchup_handler.load_config", return_value={"LEAGUE_ID": "123456", "TEAM_MAPPING_FILE": "team_mapping.json"})
@patch("src.handlers.matchup_handler.get_pacific_datetime")
@patch("src.handlers.matchup_handler.YahooFantasyFetcher")
@patch("src.handlers.matchup_handler.MatchupHandler.reply_flex")
def test_matchup_handler_execute_flow(mock_reply_flex, mock_fetcher_cls, mock_get_pacific, mock_load_config, mock_event, mock_config):
    # 1. 設置模擬時間在賽季中 (2025-11-15 12:00:00)
    pacific_tz = pytz.timezone("US/Pacific")
    mock_now = pacific_tz.localize(datetime(2025, 11, 15, 12, 0, 0))
    mock_get_pacific.return_value = mock_now

    # 2. 設置模擬聯盟 Meta
    mock_fetcher = mock_fetcher_cls.return_value
    mock_fetcher.fetch_league_metadata.return_value = {
        "league_id": "nba.l.123456",
        "name": "My NBA League",
        "season": "2025",
        "start_date": "2025-10-20",
        "end_date": "2026-04-12",
        "end_week": 24
    }

    # 3. 設置模擬對戰列表
    mock_fetcher.fetch_matchups.return_value = [
        {
            "team1": {
                "team_id": "1",
                "name": "韋哥",
                "official_name": "Vigo's Superteam",
                "stats": {
                    "FG%": "0.514", "FGM/FGA": "180/350", "FT%": "0.750", "FTM/FTA": "15/20",
                    "3PTM": "35", "PTS": "450", "REB": "110", "AST": "95", "ST": "25", "BLK": "12", "TO": "32"
                }
            },
            "team2": {
                "team_id": "2",
                "name": "Jerry",
                "official_name": "Jerry's Awesome",
                "stats": {
                    "FG%": "0.485", "FGM/FGA": "165/340", "FT%": "0.750", "FTM/FTA": "15/20",
                    "3PTM": "42", "PTS": "410", "REB": "125", "AST": "80", "ST": "20", "BLK": "18", "TO": "38"
                }
            }
        }
    ]

    handler = MatchupHandler()
    # Mock 暱稱對應
    handler._load_team_mapping = MagicMock(return_value={"1": "韋哥", "2": "Jerry"})

    mock_event.message.text = "#對戰 韋哥"

    # 4. 執行
    handler.execute(mock_event, mock_config)

    # 5. 驗證
    # 驗證 fetch_league_metadata 被呼叫
    mock_fetcher.fetch_league_metadata.assert_called_once_with("123456")
    
    # 驗證計算出的週數 (2025-10-20 到 2025-11-15 -> 第 4 週)
    # 2025-10-20 (星期一) -> Monday of start week.
    # 2025-11-15 差 26 天. 26 // 7 = 3 -> 3+1 = 4.
    mock_fetcher.fetch_matchups.assert_called_once_with("123456", 4)

    # 驗證 reply_flex 有被呼叫，且回傳的 Flex 參數是正確的
    mock_reply_flex.assert_called_once()
    call_args = mock_reply_flex.call_args[0]
    # call_args[0]: event, call_args[1]: configuration, call_args[2]: alt_text, call_args[3]: flex_dict
    assert call_args[0] == mock_event
    assert call_args[1] == mock_config
    assert call_args[2] == "WEEK 4 MATCHUP - 韋哥 vs Jerry"
    assert isinstance(call_args[3], dict)


@patch("src.handlers.matchup_handler.load_config", return_value={"LEAGUE_ID": "123456", "TEAM_MAPPING_FILE": "team_mapping.json"})
@patch("src.handlers.matchup_handler.get_pacific_datetime")
@patch("src.handlers.matchup_handler.YahooFantasyFetcher")
@patch("src.handlers.matchup_handler.MatchupHandler.reply_flex")
def test_matchup_handler_execute_offseason(mock_reply_flex, mock_fetcher_cls, mock_get_pacific, mock_load_config, mock_event, mock_config):
    # 1. 設置模擬時間在 offseason (2026-05-01 12:00:00)
    pacific_tz = pytz.timezone("US/Pacific")
    mock_now = pacific_tz.localize(datetime(2026, 5, 1, 12, 0, 0))
    mock_get_pacific.return_value = mock_now

    # 2. 設置模擬聯盟 Meta
    mock_fetcher = mock_fetcher_cls.return_value
    mock_fetcher.fetch_league_metadata.return_value = {
        "league_id": "nba.l.123456",
        "name": "My NBA League",
        "season": "2025",
        "start_date": "2025-10-20",
        "end_date": "2026-04-12",
        "end_week": 24
    }

    # 3. 設置模擬對戰列表 (offseason fallback to end_week = 24)
    mock_fetcher.fetch_matchups.return_value = [
        {
            "team1": {
                "team_id": "1",
                "name": "韋哥",
                "official_name": "Vigo's Superteam",
                "stats": {
                    "FG%": "0.514", "FGM/FGA": "180/350", "FT%": "0.750", "FTM/FTA": "15/20",
                    "3PTM": "35", "PTS": "450", "REB": "110", "AST": "95", "ST": "25", "BLK": "12", "TO": "32"
                }
            },
            "team2": {
                "team_id": "2",
                "name": "Jerry",
                "official_name": "Jerry's Awesome",
                "stats": {
                    "FG%": "0.485", "FGM/FGA": "165/340", "FT%": "0.750", "FTM/FTA": "15/20",
                    "3PTM": "42", "PTS": "410", "REB": "125", "AST": "80", "ST": "20", "BLK": "18", "TO": "38"
                }
            }
        }
    ]

    handler = MatchupHandler()
    handler._load_team_mapping = MagicMock(return_value={"1": "韋哥", "2": "Jerry"})

    mock_event.message.text = "#對戰 韋哥"

    # 4. 執行
    handler.execute(mock_event, mock_config)

    # 5. 驗證: 應該使用 end_week 24 查詢 fetch_matchups
    mock_fetcher.fetch_matchups.assert_called_once_with("123456", 24)

    # 驗證 reply_flex 有被呼叫，且為 WEEK 24
    mock_reply_flex.assert_called_once()
    call_args = mock_reply_flex.call_args[0]
    assert call_args[2] == "WEEK 24 MATCHUP - 韋哥 vs Jerry"


@patch("src.handlers.matchup_handler.load_config")
@patch("src.handlers.matchup_handler.YahooFantasyFetcher")
@patch("src.handlers.matchup_handler.MatchupHandler.reply_flex")
def test_matchup_handler_execute_error_handling(mock_reply_flex, mock_fetcher_cls, mock_load_config, mock_event, mock_config):
    # 測試 1: config 缺少 LEAGUE_ID
    mock_load_config.return_value = {} # empty config
    
    handler = MatchupHandler()
    handler._load_team_mapping = MagicMock(return_value={"1": "韋哥"})
    mock_event.message.text = "#對戰 韋哥"

    # 執行不應該拋出任何例外
    try:
        handler.execute(mock_event, mock_config)
    except Exception as e:
        pytest.fail(f"Execute threw exception when config was empty: {e}")

    # reply_flex 應該不會被呼叫 (quiet exit)
    mock_reply_flex.assert_not_called()

    # 測試 2: API 發生異常
    mock_load_config.return_value = {"LEAGUE_ID": "123456"}
    mock_fetcher_cls.return_value.fetch_league_metadata.side_effect = Exception("Network connection lost")

    # 執行不應該拋出例外 (quiet exit)
    try:
        handler.execute(mock_event, mock_config)
    except Exception as e:
        pytest.fail(f"Execute threw exception when Yahoo fetcher raised error: {e}")

    # reply_flex 應該不會被呼叫 (quiet exit)
    mock_reply_flex.assert_not_called()



