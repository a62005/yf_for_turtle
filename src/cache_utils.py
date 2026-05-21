import os
import json

CACHE_FILE = os.path.join("data", "empty_records.json")

def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}

def _save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    temp_file = CACHE_FILE + '.tmp'
    with open(temp_file, "w") as f:
        json.dump(data, f)
    os.replace(temp_file, CACHE_FILE)

def is_empty_data(key: str) -> bool:
    cache = _load_cache()
    return cache.get(key, False)

def mark_empty_data(key: str):
    cache = _load_cache()
    cache[key] = True
    _save_cache(cache)
