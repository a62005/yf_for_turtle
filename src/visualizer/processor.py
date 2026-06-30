import os
import json
from src.config import load_config, current_chat_id
from src.utils.path_utils import get_league_dir

DISPLAY_ALIASES = {
    "FGM/FGA": "FG",
    "FTM/FTA": "FT",
    "3PTM": "3PT"
}

def process_stats_for_visual(data: dict) -> list:
    team_stats = data.get("team_stats", [])
    if not team_stats:
        return []

    # Get active league ID to read stats configuration
    config = load_config()
    league_id = config.get("LEAGUE_ID", "default")
    meta_path = os.path.join(get_league_dir(league_id), "metadata.json")
    
    stat_categories = []
    if os.path.exists(meta_path):
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
                stat_categories = meta.get("stat_categories", [])
        except Exception:
            pass

    # Build categories list dynamically
    categories = []
    
    # Check for Game Player data
    if any("GP_PLAYED" in t["stats"] for t in team_stats):
        for t in team_stats:
            played = t["stats"].get("GP_PLAYED", 0)
            total = t["stats"].get("GP_TOTAL", 0)
            t["stats"]["GP_SORT_KEY"] = (played * 1000) + total
            t["stats"]["Game Player"] = f"{played} / {total}"
        categories.append({"label": "Game Player", "data_key": "Game Player", "sort_key": "GP_SORT_KEY", "reverse": True})

    # Check for Today Player data
    if any("Today Player" in t["stats"] for t in team_stats):
        categories.append({"label": "Today Player", "data_key": "Today Player", "sort_key": "Today Player", "reverse": True})

    if not stat_categories:
        # Fallback to standard NBA categories if no categories found in metadata
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
    else:
        # Add dynamic stats categories from settings cache
        SORT_KEY_OVERRIDES = {
            "FG": "FG%",
            "FT": "FT%"
        }
        for cat in stat_categories:
            disp_name = cat["display_name"]
            label = DISPLAY_ALIASES.get(disp_name, disp_name)
            reverse_val = True if cat["sort_order"] == 1 else False
            sort_key_name = SORT_KEY_OVERRIDES.get(label, disp_name)
            
            categories.append({
                "label": label,
                "data_key": disp_name,
                "sort_key": sort_key_name,
                "reverse": reverse_val
            })

    # Formatting heuristics helper
    def format_val(label, val):
        if val is None or str(val).strip() in ("", "-"):
            return "-"
            
        # 1. Percentage (e.g. FG%)
        if "%" in label:
            try:
                num = float(val)
                if num == 0: return "-"
                return f"{num * 100:.1f}%"
            except (ValueError, TypeError):
                pass
                
        # 2. Baseball rate (AVG, OBP, SLG, OPS) -> 3 decimals (strip leading zero)
        if label in ["AVG", "OBP", "SLG", "OPS"]:
            try:
                num = float(val)
                formatted = f"{num:.3f}"
                if formatted.startswith("0."):
                    return formatted[1:]
                elif formatted.startswith("-0."):
                    return "-" + formatted[2:]
                return formatted
            except (ValueError, TypeError):
                pass
                
        # 3. Baseball pitching (ERA, WHIP) -> 2 decimals
        if label in ["ERA", "WHIP"]:
            try:
                num = float(val)
                return f"{num:.2f}"
            except (ValueError, TypeError):
                pass
                
        # 其餘直接輸出整數
        try:
            return int(round(float(val)))
        except (ValueError, TypeError):
            return val

    result = []
    for cat in categories:
        def sort_key_func(team):
            val = team["stats"].get(cat["sort_key"], 0)
            if isinstance(val, (int, float)):
                return val
            try: return float(str(val).strip('%'))
            except (ValueError, TypeError): return 0

        # Sort teams according to the category rule
        sorted_teams = sorted(team_stats, key=sort_key_func, reverse=cat["reverse"])
        
        rows = []
        for rank, team in enumerate(sorted_teams, 1):
            rows.append({
                "rank": rank,
                "name": team["name"],
                "value": format_val(cat["label"], team["stats"].get(cat["data_key"]))
            })
            
        result.append({
            "label": cat["label"],
            "rows": rows,
            "reverse": cat["reverse"]
        })
        
    return result

