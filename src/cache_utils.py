import os
import json
from datetime import datetime
from filelock import FileLock

CACHE_FILE = os.path.join("data", "empty_records.json")
LOCK_FILE = CACHE_FILE + ".lock"
METADATA_FILE = os.path.join("data", "league_metadata.json")
METADATA_LOCK = METADATA_FILE + ".lock"

def _load_cache(file_path=CACHE_FILE):
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

def _save_cache(data, file_path=CACHE_FILE):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    temp_file = file_path + '.tmp'
    with open(temp_file, "w") as f:
        json.dump(data, f)
    os.replace(temp_file, file_path)

def is_empty_data(key: str) -> bool:
    cache = _load_cache()
    return cache.get(key, False)

def mark_empty_data(key: str):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with FileLock(LOCK_FILE):
        cache = _load_cache()
        cache[key] = True
        _save_cache(cache)

def save_league_metadata(data: dict):
    """Save league metadata with a timestamp."""
    os.makedirs(os.path.dirname(METADATA_FILE), exist_ok=True)
    with FileLock(METADATA_LOCK):
        data["last_updated"] = datetime.now().isoformat()
        _save_cache(data, METADATA_FILE)

def load_league_metadata() -> dict:
    """Load league metadata from cache."""
    return _load_cache(METADATA_FILE)
