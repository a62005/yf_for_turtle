import os
import json

CACHE_FILE = os.path.join("data", "empty_records.json")

def _load_cache():
    if not os.path.exists(CACHE_FILE):
        return {}
    try:
        with open(CACHE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, "w") as f:
        json.dump(data, f)

def is_empty_data(key: str) -> bool:
    cache = _load_cache()
    return cache.get(key, False)

def mark_empty_data(key: str):
    cache = _load_cache()
    cache[key] = True
    _save_cache(cache)
