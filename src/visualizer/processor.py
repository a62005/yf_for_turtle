def process_stats_for_visual(data: dict) -> list:
    team_stats = data.get("team_stats", [])
    categories = [
        {"label": "FG", "sort_by": "FG%", "reverse": True},
        {"label": "FG%", "sort_by": "FG%", "reverse": True},
        {"label": "FT", "sort_by": "FT%", "reverse": True},
        {"label": "FT%", "sort_by": "FT%", "reverse": True},
        {"label": "3PTM", "sort_by": "3PTM", "reverse": True},
        {"label": "PTS", "sort_by": "PTS", "reverse": True},
        {"label": "REB", "sort_by": "REB", "reverse": True},
        {"label": "AST", "sort_by": "AST", "reverse": True},
        {"label": "ST", "sort_by": "ST", "reverse": True},
        {"label": "BLK", "sort_by": "BLK", "reverse": True},
        {"label": "TO", "sort_by": "TO", "reverse": False},
    ]
    
    result = []
    for cat in categories:
        # Sort teams by the specific logic
        sorted_teams = sorted(
            team_stats, 
            key=lambda x: x["stats"].get(cat["sort_by"], 0) if isinstance(x["stats"].get(cat["sort_by"]), (int, float)) else 0,
            reverse=cat["reverse"]
        )
        rows = []
        for t in sorted_teams:
            val = t["stats"].get(cat["label"], t["stats"].get(cat["sort_by"], "-"))
            rows.append({"name": t["name"], "value": val})
        result.append({"label": cat["label"], "rows": rows})
    return result
