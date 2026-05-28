import pytest
from src.handlers.matchup_handler import MatchupHandler

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
    
    # 驗證 Header 第三層：比分對決 (5:4，我方領先大黑 24px/bold/#111111，落後小灰 16px/regular/#aaaaaa)
    score_box = body[3]
    assert score_box["contents"][0]["text"] == "5"
    assert score_box["contents"][0]["size"] == "xl" # 24px對應 xl
    assert score_box["contents"][0]["weight"] == "bold"
    assert score_box["contents"][0]["color"] == "#111111"
    
    assert score_box["contents"][2]["text"] == "4"
    assert score_box["contents"][2]["size"] == "md" # 16px對應 md
    assert score_box["contents"][2]["weight"] == "regular"
    assert score_box["contents"][2]["color"] == "#aaaaaa"
    
    # 驗證 Body 11 行指標 (如 FG%，我方贏 -> 我方大黑，對手小灰)
    fg_row = body[5]["contents"][1] # index 5 is the box containing rows, index 1 is FG% row
    assert fg_row["contents"][0]["text"] == "51.4%"
    assert fg_row["contents"][0]["weight"] == "bold"
    assert fg_row["contents"][0]["size"] == "md"
    assert fg_row["contents"][0]["color"] == "#111111"
    
    assert fg_row["contents"][1]["text"] == "FG%"
    
    assert fg_row["contents"][2]["text"] == "48.5%"
    assert fg_row["contents"][2]["weight"] == "regular"
    assert fg_row["contents"][2]["size"] == "xs"
    assert fg_row["contents"][2]["color"] == "#aaaaaa"


