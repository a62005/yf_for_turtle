import os
import json
from src.config import load_config, current_chat_id
from src.utils.path_utils import get_league_dir

DISPLAY_ALIASES = {
    "FGM/FGA": "FGM/A",
    "FTM/FTA": "FTM/A",
    "3PTM": "3PT",
    "AST/TO": "A/T",
    "A/TO": "A/T",
    "STL": "ST"
}

def is_mlb_pitcher_stat(stat_id: str, display_name: str) -> bool:
    pitcher_ids = {
        "26", "27", "28", "29", "30", "31", "32", "37", "38", "39",
        "41", "42", "48", "50", "81", "82", "83", "89", "121", "122"
    }
    if stat_id in pitcher_ids:
        return True
    
    pitcher_names = {
        "IP", "ERA", "WHIP", "QS", "SV+H", "SV", "HLD", "K", "W", "L", 
        "CG", "SHO", "OUT", "K/9", "BB/9", "K/BB", "SV+HLD"
    }
    if display_name in pitcher_names:
        if display_name in ("BB", "H"):
            return False
        return True
    return False

def process_stats_for_visual(data: dict, league_id: str = None) -> list:
    team_stats = data.get("team_stats", [])
    if not team_stats:
        return []

    # Get active league ID to read stats configuration
    lid = league_id or data.get("league_id")
    if not lid:
        config = load_config()
        lid = config.get("LEAGUE_ID", "default")
    meta_path = os.path.join(get_league_dir(lid), "metadata.json")
    
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
    
    # 1. Today Player (最左側第一欄)
    if any("Today Player" in t.get("stats", {}) for t in team_stats):
        categories.append({
            "label": "Today Player",
            "data_key": "Today Player",
            "sort_key": "Today Player",
            "reverse": True,
            "is_pitcher": False,
            "is_common": True
        })

    # 2. Game Player (最左側第二欄)
    if any("GP_PLAYED" in t.get("stats", {}) or "Game Player" in t.get("stats", {}) for t in team_stats):
        for t in team_stats:
            stats = t.setdefault("stats", {})
            if "GP_PLAYED" in stats:
                played = stats.get("GP_PLAYED", 0)
                total = stats.get("GP_TOTAL", 0)
                stats["GP_SORT_KEY"] = (played * 1000) + total
                stats["Game Player"] = f"{played} / {total}"
            elif "Game Player" in stats:
                gp_val = stats.get("Game Player", "-")
                stats["Game Player"] = gp_val
                try:
                    p_num = int(str(gp_val).split("/")[0].strip())
                    stats["GP_SORT_KEY"] = p_num
                except Exception:
                    stats["GP_SORT_KEY"] = 0
            else:
                stats["Game Player"] = "-"
                stats["GP_SORT_KEY"] = 0
        categories.append({
            "label": "Game Player",
            "data_key": "Game Player",
            "sort_key": "GP_SORT_KEY",
            "reverse": True,
            "is_pitcher": False,
            "is_common": True
        })

    SORT_KEY_OVERRIDES = {
        "FGM/A": "FG%",
        "FGM/FGA": "FG%",
        "FTM/A": "FT%",
        "FTM/FTA": "FT%",
        "FG": "FG%",
        "FT": "FT%"
    }
    added_labels = set()
    added_keys = set()

    if stat_categories:
        for cat in stat_categories:
            disp_name = cat["display_name"]
            label = DISPLAY_ALIASES.get(disp_name, disp_name)
            reverse_val = True if cat.get("sort_order", 1) == 1 else False
            sort_key_name = SORT_KEY_OVERRIDES.get(label, disp_name)
            
            categories.append({
                "label": label,
                "data_key": disp_name,
                "sort_key": sort_key_name,
                "reverse": reverse_val,
                "is_pitcher": is_mlb_pitcher_stat(cat.get("stat_id", ""), disp_name),
                "is_common": False
            })
            added_labels.add(label)
            added_keys.add(disp_name)

    # 滾動探索所有出現在 team_stats 中的自訂比分項目（如 DD, A/T 等，不侷限於 9-CAT）
    KNOWN_ORDER = [
        "FGM/A", "FGM/FGA", "FG%", "FTM/A", "FTM/FTA", "FT%", "3PT", "3PTM", "3PT%",
        "PTS", "REB", "OREB", "DREB", "AST", "ST", "STL", "BLK", "TO",
        "DD", "TD", "A/T", "AST/TO", "A/TO",
        # MLB hitting
        "H/AB", "R", "H", "HR", "RBI", "SB", "BB", "AVG", "OBP", "SLG", "OPS",
        # MLB pitching
        "IP", "W", "K", "ERA", "WHIP", "QS", "SV", "HLD", "SV+H", "SV+HLD", "L"
    ]

    all_team_keys = set()
    for t in team_stats:
        all_team_keys.update(t.get("stats", {}).keys())

    ignored_keys = {
        "Today Player", "Game Player", "GP_PLAYED", "GP_TOTAL", "GP_SORT_KEY",
        "FG", "FT", "FGM", "FGA", "FTM", "FTA"
    }

    if not stat_categories:
        # 依照原本 NBA 標準排序：FGM/A, FG%, FTM/A, FT%, 3PT, PTS, REB, AST, ST, BLK, TO
        has_fgm = any(k in all_team_keys for k in ("FGM/A", "FGM/FGA"))
        if has_fgm and "FGM/A" not in added_labels:
            fg_key = "FGM/A" if "FGM/A" in all_team_keys else "FGM/FGA"
            categories.append({
                "label": "FGM/A", "data_key": fg_key, "sort_key": "FG%",
                "reverse": True, "is_pitcher": False, "is_common": False
            })
            added_labels.update(["FGM/A", "FG"])
            added_keys.update(["FGM/A", "FGM/FGA", "FG"])

        if "FG%" in all_team_keys and "FG%" not in added_labels:
            categories.append({
                "label": "FG%", "data_key": "FG%", "sort_key": "FG%",
                "reverse": True, "is_pitcher": False, "is_common": False
            })
            added_labels.add("FG%")
            added_keys.add("FG%")

        has_ftm = any(k in all_team_keys for k in ("FTM/A", "FTM/FTA"))
        if has_ftm and "FTM/A" not in added_labels:
            ft_key = "FTM/A" if "FTM/A" in all_team_keys else "FTM/FTA"
            categories.append({
                "label": "FTM/A", "data_key": ft_key, "sort_key": "FT%",
                "reverse": True, "is_pitcher": False, "is_common": False
            })
            added_labels.update(["FTM/A", "FT"])
            added_keys.update(["FTM/A", "FTM/FTA", "FT"])

        if "FT%" in all_team_keys and "FT%" not in added_labels:
            categories.append({
                "label": "FT%", "data_key": "FT%", "sort_key": "FT%",
                "reverse": True, "is_pitcher": False, "is_common": False
            })
            added_labels.add("FT%")
            added_keys.add("FT%")

        has_3pt = any(k in all_team_keys for k in ("3PT", "3PTM"))
        if has_3pt and "3PT" not in added_labels and "3PTM" not in added_labels:
            t3_key = "3PT" if "3PT" in all_team_keys else "3PTM"
            categories.append({
                "label": "3PT", "data_key": t3_key, "sort_key": t3_key,
                "reverse": True, "is_pitcher": False, "is_common": False
            })
            added_labels.update(["3PT", "3PTM"])
            added_keys.update(["3PT", "3PTM"])

        for std_key, rev in [("PTS", True), ("REB", True), ("AST", True), ("ST", True), ("BLK", True), ("TO", False)]:
            actual_key = std_key
            if std_key == "ST" and "ST" not in all_team_keys and "STL" in all_team_keys:
                actual_key = "STL"
            if (std_key in all_team_keys or actual_key in all_team_keys) and std_key not in added_labels:
                categories.append({
                    "label": std_key, "data_key": actual_key, "sort_key": actual_key,
                    "reverse": rev, "is_pitcher": False, "is_common": False
                })
                added_labels.add(std_key)
                added_keys.update([std_key, actual_key])

    remaining_keys = [k for k in all_team_keys if k not in ignored_keys and k not in added_keys and DISPLAY_ALIASES.get(k, k) not in added_labels]

    def key_sort_order(k):
        try:
            return (0, KNOWN_ORDER.index(k))
        except ValueError:
            return (1, k)

    for k in sorted(remaining_keys, key=key_sort_order):
        label = DISPLAY_ALIASES.get(k, k)
        if label in added_labels:
            continue
        reverse_val = False if k.upper() in ["TO", "ERA", "WHIP", "L"] else True
        categories.append({
            "label": label,
            "data_key": k,
            "sort_key": k,
            "reverse": reverse_val,
            "is_pitcher": is_mlb_pitcher_stat("", k),
            "is_common": False
        })
        added_labels.add(label)
        added_keys.add(k)

    # Formatting heuristics helper
    def format_val(label, val):
        if label in ["Today Player", "Game Player"]:
            if val is None or str(val).strip() in ("", "-"):
                return "-" if label == "Game Player" else 0
            return val

        if val is None or str(val).strip() in ("", "-"):
            val = 0
            
        # 1. Percentage (e.g. FG%)
        if "%" in label:
            try:
                num = float(val)
                return f"{num * 100:.1f}%"
            except (ValueError, TypeError):
                return "0.0%"
                
        # 2. Ratios (A/T, AST/TO) -> 2 decimals
        if label in ["A/T", "AST/TO"]:
            try:
                return f"{float(val):.2f}"
            except (ValueError, TypeError):
                return "0.00"

        # 3. Baseball rate (AVG, OBP, SLG, OPS) -> 3 decimals (strip leading zero)
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
                return ".000"
                
        # 4. Baseball pitching (ERA, WHIP) -> 2 decimals
        if label in ["ERA", "WHIP"]:
            try:
                num = float(val)
                return f"{num:.2f}"
            except (ValueError, TypeError):
                return "0.00"
                
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

        # Sort teams: first by team_id ascending (as fallback for ties)
        def get_team_id_key(team):
            tid = team.get("team_id", "")
            try:
                return int(tid)
            except (ValueError, TypeError):
                return 999999
        
        sorted_by_id = sorted(team_stats, key=get_team_id_key)
        
        # Then sort by the stats category value (stable sort preserves team_id order)
        sorted_teams = sorted(sorted_by_id, key=sort_key_func, reverse=cat["reverse"])
        
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
            "reverse": cat["reverse"],
            "is_pitcher": cat.get("is_pitcher", False),
            "is_common": cat.get("is_common", False)
        })
        
    return result
