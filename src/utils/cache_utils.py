import os
import json
from datetime import datetime
from filelock import FileLock
from src.utils.path_utils import get_league_metadata_path, get_league_empty_records_path

def _load_cache(file_path):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

def _save_cache(data, file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    temp_file = file_path + '.tmp'
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    os.replace(temp_file, file_path)

def is_empty_data(key: str) -> bool:
    path = get_league_empty_records_path()
    cache = _load_cache(path)
    return cache.get(key, False)

def mark_empty_data(key: str):
    path = get_league_empty_records_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path + ".lock"):
        cache = _load_cache(path)
        cache[key] = True
        _save_cache(cache, path)

def save_league_metadata(data: dict, league_id: str = None):
    """Save league metadata with a timestamp."""
    path = get_league_metadata_path(league_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with FileLock(path + ".lock"):
        data["last_updated"] = datetime.now().isoformat()
        _save_cache(data, path)

def load_league_metadata(league_id: str = None) -> dict:
    """Load league metadata from cache."""
    return _load_cache(get_league_metadata_path(league_id))
