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
        "3PTM": "35", "PTS": "450", "REB": "110", "AST": "95", "STL": "25", "BLK": "12", "TO": "32"
    }
    opp_stats = {
        "FG%": "0.485", "FGM/FGA": "165/340", "FT%": "0.750", "FTM/FTA": "15/20",
        "3PTM": "42", "PTS": "410", "REB": "125", "AST": "80", "STL": "20", "BLK": "18", "TO": "38"
    }
    
    comp_res = handler.compare_stats(my_stats, opp_stats)
    
    # 驗證 9-Cat 勝負 (韋哥贏：FG%, PTS, AST, STL, TO；落後：FT%, 3PTM, REB, BLK -> 比分 5:4)
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
