from src.visualizer.processor import process_stats_for_visual

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
