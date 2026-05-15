def process_stats_for_visual(data: dict) -> list:
    team_stats = data.get("team_stats", [])
    if not team_stats:
        return []

    # Map display labels to (data_key, sort_key, reverse_sort)
    categories = [
        {"label": "FG", "data_key": "FGM/FGA", "sort_key": "FG%", "reverse": True},
        {"label": "FG%", "data_key": "FG%", "sort_key": "FG%", "reverse": True},
        {"label": "FT", "data_key": "FTM/FTA", "sort_key": "FT%", "reverse": True},
        {"label": "FT%", "data_key": "FT%", "sort_key": "FT%", "reverse": True},
        {"label": "3PT", "data_key": "3PTM", "sort_key": "3PTM", "reverse": True},
        {"label": "PTS", "data_key": "PTS", "sort_key": "PTS", "reverse": True},
        {"label": "REB", "data_key": "REB", "sort_key": "REB", "reverse": True},
        {"label": "AST", "data_key": "AST", "sort_key": "AST", "reverse": True},
        {"label": "ST", "data_key": "ST", "sort_key": "ST", "reverse": True},
        {"label": "BLK", "data_key": "BLK", "sort_key": "BLK", "reverse": True},
        {"label": "TO", "data_key": "TO", "sort_key": "TO", "reverse": False},
    ]

    result = []
    for cat in categories:
        def sort_key_func(team):
            val = team["stats"].get(cat["sort_key"], 0)
            return val if isinstance(val, (int, float)) else 0

        sorted_teams = sorted(team_stats, key=sort_key_func, reverse=cat["reverse"])
        
        rows = []
        for t in sorted_teams:
            rows.append({
                "name": t["name"],
                "value": t["stats"].get(cat["data_key"], "-")
            })
        result.append({"label": cat["label"], "rows": rows})
    return result
