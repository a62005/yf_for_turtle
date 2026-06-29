import os
from src.config import load_config

# 根目錄 C:\Users\HsiehLink\Python\yf_for_turtle
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

def get_league_id() -> str | None:
    """動態獲取當前配置的聯盟 ID，優先從 JSON 載入，否則從環境變數載入。"""
    return load_config().get("LEAGUE_ID")

def get_league_dir(league_id: str = None) -> str:
    lid = league_id or get_league_id() or "default"
    return os.path.join(BASE_DIR, "data", "league", str(lid))

def get_league_metadata_path(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "metadata.json")

def get_league_empty_records_path(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "empty_records.json")

def get_league_team_mapping_path(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "team_mapping.json")

def get_league_image_dir(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "image")

def get_league_daily_dir(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "daily")

def get_league_weekly_dir(league_id: str = None) -> str:
    return os.path.join(get_league_dir(league_id), "weekly")
