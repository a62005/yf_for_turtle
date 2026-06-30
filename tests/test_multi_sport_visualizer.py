import json
import pytest
from src.visualizer.processor import process_stats_for_visual

def test_process_stats_for_visual_nba(mocker):
    # Mock metadata file read
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps({
        "stat_categories": [
            {"stat_id": "12", "display_name": "PTS", "sort_order": 1},
            {"stat_id": "19", "display_name": "TO", "sort_order": 0},
            {"stat_id": "5", "display_name": "FG%", "sort_order": 1},
            {"stat_id": "9004003", "display_name": "FGM/FGA", "sort_order": 1}
        ]
    })))
    mocker.patch("os.path.exists", return_value=True)
    mock_chat_id = mocker.patch("src.visualizer.processor.current_chat_id")
    mock_chat_id.get.return_value = "chat1"
    mocker.patch("src.visualizer.processor.load_config", return_value={"LEAGUE_ID": "nba.l.18457"})
    
    sample_data = {
        "team_stats": [
            {"team_id": "1", "name": "Team A", "stats": {"PTS": "105", "TO": "12", "FG%": "0.485", "FGM/FGA": "45/90"}}
        ]
    }
    
    result = process_stats_for_visual(sample_data)
    assert len(result) > 0
    
    # Check FGM/FGA display name replaced by alias 'FG'
    fg_cat = next(c for c in result if c["label"] == "FG")
    assert fg_cat["rows"][0]["value"] == "45/90"
    
    # Check percentage formatted
    fg_pct = next(c for c in result if c["label"] == "FG%")
    assert fg_pct["rows"][0]["value"] == "48.5%"
    
    # Check sort order reverse matches settings
    to_cat = next(c for c in result if c["label"] == "TO")
    assert to_cat["reverse"] is False # Low better

def test_process_stats_for_visual_mlb(mocker):
    mocker.patch("builtins.open", mocker.mock_open(read_data=json.dumps({
        "stat_categories": [
            {"stat_id": "1", "display_name": "AVG", "sort_order": 1},
            {"stat_id": "2", "display_name": "ERA", "sort_order": 0},
            {"stat_id": "3", "display_name": "WHIP", "sort_order": 0}
        ]
    })))
    mocker.patch("os.path.exists", return_value=True)
    mock_chat_id = mocker.patch("src.visualizer.processor.current_chat_id")
    mock_chat_id.get.return_value = "chat1"
    mocker.patch("src.visualizer.processor.load_config", return_value={"LEAGUE_ID": "mlb.l.12345"})
    
    sample_data = {
        "team_stats": [
            {"team_id": "1", "name": "Team A", "stats": {"AVG": "0.2854", "ERA": "3.456", "WHIP": "1.123"}}
        ]
    }
    
    result = process_stats_for_visual(sample_data)
    
    # Check AVG formatted to 3 decimals with leading zero stripped
    avg_cat = next(c for c in result if c["label"] == "AVG")
    assert avg_cat["rows"][0]["value"] == ".285"
    
    # Check ERA formatted to 2 decimals
    era_cat = next(c for c in result if c["label"] == "ERA")
    assert era_cat["rows"][0]["value"] == "3.46"
