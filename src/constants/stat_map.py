STAT_MAP = {
    "12": "PTS",
    "15": "REB",
    "16": "AST",
    "17": "ST",
    "18": "BLK",
    "19": "TO",
    "5": "FG%",
    "8": "FT%",
    "11": "3PT%",
    "9004003": "FGM/FGA",
    "9007006": "FTM/FTA"
}

def translate_stat_id(stat_id: str) -> str:
    """Translate a Yahoo stat ID to a standard abbreviation."""
    return STAT_MAP.get(str(stat_id), f"stat_{stat_id}")
