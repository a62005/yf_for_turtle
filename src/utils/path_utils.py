import os
import logging
import json
from src.config import load_config

# 根目錄 C:\Users\HsiehLink\Python\yf_for_turtle
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")

def get_league_id() -> str | None:
    """動態獲取當前配置的聯盟 ID，優先從 JSON 載入，否則從環境變數載入。"""
    return load_config().get("LEAGUE_ID")

def get_league_dir(league_id: str = None) -> str:
    lid = league_id or get_league_id()
    if not lid:
        return os.path.join(DATA_DIR, "league", "default")
    
    # Normalize key to full league key (e.g. nba.l.18457)
    lid_str = str(lid).strip()
    if not lid_str.startswith("nba.l.") and not lid_str.startswith("mlb.l."):
        # Check if there's any prefix
        if "." in lid_str:
            normalized_id = lid_str
        else:
            normalized_id = f"nba.l.{lid_str}"
    else:
        normalized_id = lid_str
        
    return os.path.join(DATA_DIR, "league", normalized_id)

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

def migrate_old_league_directories():
    league_base = os.path.join(DATA_DIR, "league")
    if not os.path.exists(league_base):
        return
        
    # Rename folder from raw numeric to nba.l.<number>
    for name in os.listdir(league_base):
        full_path = os.path.join(league_base, name)
        if os.path.isdir(full_path) and name.isdigit():
            new_name = f"nba.l.{name}"
            new_path = os.path.join(league_base, new_name)
            if not os.path.exists(new_path):
                try:
                    os.rename(full_path, new_path)
                    logging.info(f"[SYSTEM] 已將歷史目錄 {name} 重新命名為 {new_name}")
                except Exception as e:
                    logging.error(f"重命名目錄失敗: {e}")
                    
    # Upgrade chat_league_mapping.json keys
    mapping_file = os.path.join(DATA_DIR, "security", "chat_league_mapping.json")
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            updated = False
            for k, v in list(mapping.items()):
                v_str = str(v).strip()
                if v_str.isdigit():
                    mapping[k] = f"nba.l.{v_str}"
                    updated = True
            if updated:
                with open(mapping_file, "w", encoding="utf-8") as f:
                    json.dump(mapping, f, ensure_ascii=False, indent=2)
                logging.info("[SYSTEM] 已成功升級對照表中的舊型聯賽 ID 格式")
        except Exception as e:
            logging.error(f"升級對照表失敗: {e}")
