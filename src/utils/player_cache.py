import os
import json
import logging

DEFAULT_CACHE_PATH = "data/player_mapping_cache.json"

def load_cache(cache_path: str = DEFAULT_CACHE_PATH) -> dict:
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load player cache from {cache_path}: {e}")
        return {}

def save_cache(cache: dict, cache_path: str = DEFAULT_CACHE_PATH) -> None:
    try:
        os.makedirs(os.path.dirname(cache_path), exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Failed to save player cache to {cache_path}: {e}")

def get_cached_player(nickname: str, cache_path: str = DEFAULT_CACHE_PATH) -> dict | None:
    cache = load_cache(cache_path)
    return cache.get(nickname.strip())

def set_cached_player(nickname: str, player_data: dict, cache_path: str = DEFAULT_CACHE_PATH) -> None:
    cache = load_cache(cache_path)
    cache[nickname.strip()] = player_data
    save_cache(cache, cache_path)
