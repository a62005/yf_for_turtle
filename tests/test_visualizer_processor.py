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
