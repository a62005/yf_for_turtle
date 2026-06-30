from src.visualizer.processor import process_stats_for_visual, is_mlb_pitcher_stat

def test_process_stats_sorting():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"PTS": 100, "FG%": 0.45, "FGM/FGA": "45/100"}},
            {"name": "Team B", "stats": {"PTS": 200, "FG%": 0.55, "FGM/FGA": "55/100"}}
        ]
    }
    processed = process_stats_for_visual(raw_data)
    # Check PTS sorting (descending)
    pts_column = next(c for c in processed if c['label'] == 'PTS')
    assert pts_column['rows'][0]['name'] == 'Team B'

def test_process_stats_to_ascending():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"TO": 15}},
            {"name": "Team B", "stats": {"TO": 10}}
        ]
    }
    processed = process_stats_for_visual(raw_data)
    to_column = next(c for c in processed if c['label'] == 'TO')
    # TO should be ascending (lower is better)
    assert to_column['rows'][0]['name'] == 'Team B'
    assert to_column['rows'][0]['value'] == 10

def test_process_stats_fg_mapping_and_sorting():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"FG%": 0.40, "FGM/FGA": "40/100"}},
            {"name": "Team B", "stats": {"FG%": 0.50, "FGM/FGA": "25/50"}}
        ]
    }
    processed = process_stats_for_visual(raw_data)
    fg_column = next(c for c in processed if c['label'] == 'FG')
    # Should sort by FG% (Team B > Team A) but show FGM/FGA
    assert fg_column['rows'][0]['name'] == 'Team B'
    assert fg_column['rows'][0]['value'] == "25/50"
    assert fg_column['rows'][1]['name'] == 'Team A'
    assert fg_column['rows'][1]['value'] == "40/100"

def test_process_stats_missing_fallback():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"PTS": 100}},
            {"name": "Team B", "stats": {}}
        ]
    }
    processed = process_stats_for_visual(raw_data)
    pts_column = next(c for c in processed if c['label'] == 'PTS')
    assert pts_column['rows'][0]['name'] == 'Team A'
    assert pts_column['rows'][1]['name'] == 'Team B'
    assert pts_column['rows'][1]['value'] == "-"

def test_process_stats_empty():
    assert process_stats_for_visual({}) == []
    assert process_stats_for_visual({"team_stats": []}) == []

def test_process_stats_today_player():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"Today Player": 5}},
            {"name": "Team B", "stats": {"Today Player": 8}}
        ]
    }
    processed = process_stats_for_visual(raw_data)
    today_column = next(c for c in processed if c['label'] == 'Today Player')
    assert today_column['rows'][0]['name'] == 'Team B'
    assert today_column['rows'][0]['value'] == 8
    assert today_column['rows'][1]['name'] == 'Team A'
    assert today_column['rows'][1]['value'] == 5

def test_process_stats_game_player():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"GP_PLAYED": 10, "GP_TOTAL": 40}},
            {"name": "Team B", "stats": {"GP_PLAYED": 12, "GP_TOTAL": 42}},
            {"name": "Team C", "stats": {"GP_PLAYED": 10, "GP_TOTAL": 45}}
        ]
    }
    processed = process_stats_for_visual(raw_data)
    gp_column = next(c for c in processed if c['label'] == 'Game Player')
    
    # Sorting logic: (played * 1000) + total, descending
    # Team A: 10 * 1000 + 40 = 10040
    # Team B: 12 * 1000 + 42 = 12042
    # Team C: 10 * 1000 + 45 = 10045
    # Order: Team B (12042), Team C (10045), Team A (10040)
    
    assert gp_column['rows'][0]['name'] == 'Team B'
    assert gp_column['rows'][0]['value'] == "12 / 42"
    assert gp_column['rows'][1]['name'] == 'Team C'
    assert gp_column['rows'][1]['value'] == "10 / 45"
    assert gp_column['rows'][2]['name'] == 'Team A'
    assert gp_column['rows'][2]['value'] == "10 / 40"

def test_process_stats_percentage_formatting():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"FG%": 0.1234, "FT%": 0.8}},
            {"name": "Team B", "stats": {"FG%": 0, "FT%": None}},
            {"name": "Team C", "stats": {"FG%": 0.5, "FT%": 0.00}}
        ]
    }
    processed = process_stats_for_visual(raw_data)
    
    fg_pct_column = next(c for c in processed if c['label'] == 'FG%')
    ft_pct_column = next(c for c in processed if c['label'] == 'FT%')
    
    # Team A: 0.1234 -> 12.3%, 0.8 -> 80.0%
    assert any(r['name'] == 'Team A' and r['value'] == '12.3%' for r in fg_pct_column['rows'])
    assert any(r['name'] == 'Team A' and r['value'] == '80.0%' for r in ft_pct_column['rows'])
    
    # Team B: 0 -> "-", None -> "-"
    assert any(r['name'] == 'Team B' and r['value'] == '-' for r in fg_pct_column['rows'])
    assert any(r['name'] == 'Team B' and r['value'] == '-' for r in ft_pct_column['rows'])
    
    # Team C: 0.5 -> 50.0%, 0.00 -> "-"
    assert any(r['name'] == 'Team C' and r['value'] == '50.0%' for r in fg_pct_column['rows'])
    assert any(r['name'] == 'Team C' and r['value'] == '-' for r in ft_pct_column['rows'])


def test_is_mlb_pitcher_stat():
    assert is_mlb_pitcher_stat("26", "ERA") is True
    assert is_mlb_pitcher_stat("50", "IP") is True
    assert is_mlb_pitcher_stat("3", "AVG") is False
    assert is_mlb_pitcher_stat("18", "BB") is False  # 野手 BB
    assert is_mlb_pitcher_stat("39", "BB") is True   # 投手 BB


def test_process_stats_mlb_pitcher_marking():
    raw_data = {
        "team_stats": [
            {"name": "Team A", "stats": {"AVG": 0.280, "ERA": 3.50, "Today Player": 5}}
        ]
    }
    # 透過 patch mock config 與 metadata.json
    import unittest.mock as mock
    with mock.patch("src.visualizer.processor.load_config") as mock_config, \
         mock.patch("os.path.exists", return_value=True), \
         mock.patch("builtins.open", mock.mock_open(read_data='{"stat_categories": [{"stat_id": "3", "display_name": "AVG", "sort_order": 1}, {"stat_id": "26", "display_name": "ERA", "sort_order": 0}]}')):
        mock_config.return_value = {"LEAGUE_ID": "mlb.l.62358"}
        processed = process_stats_for_visual(raw_data)
        
    avg_col = next(c for c in processed if c['label'] == 'AVG')
    era_col = next(c for c in processed if c['label'] == 'ERA')
    today_col = next(c for c in processed if c['label'] == 'Today Player')
    
    assert avg_col.get("is_pitcher") is False
    assert era_col.get("is_pitcher") is True
    assert today_col.get("is_common") is True
