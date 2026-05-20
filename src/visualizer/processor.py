def process_stats_for_visual(data: dict) -> list:
    team_stats = data.get("team_stats", [])
    if not team_stats:
        return []

    # Prepare categories list
    categories = []
    
    # Check for Game Player data
    if any("GP_PLAYED" in t["stats"] for t in team_stats):
        # Add composite sort key: Played * 1000 + Total
        for t in team_stats:
            played = t["stats"].get("GP_PLAYED", 0)
            total = t["stats"].get("GP_TOTAL", 0)
            t["stats"]["GP_SORT_KEY"] = (played * 1000) + total
            t["stats"]["Game Player"] = f"{played} / {total}"
        
        categories.append({"label": "Game Player", "data_key": "Game Player", "sort_key": "GP_SORT_KEY", "reverse": True})

    # Check for Today Player data
    if any("Today Player" in t["stats"] for t in team_stats):
        categories.append({"label": "Today Player", "data_key": "Today Player", "sort_key": "Today Player", "reverse": True})

    # Standard categories
    categories += [
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
            if isinstance(val, (int, float)):
                return val
            # Handle percentage strings if necessary
            try: return float(str(val).strip('%'))
            except (ValueError, TypeError): return 0

        sorted_teams = sorted(team_stats, key=sort_key_func, reverse=cat["reverse"])
        
        rows = []
        for t in sorted_teams:
            rows.append({
                "name": t["name"],
                "value": t["stats"].get(cat["data_key"], "-")
            })
        result.append({"label": cat["label"], "rows": rows})
    return result
