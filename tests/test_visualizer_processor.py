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
