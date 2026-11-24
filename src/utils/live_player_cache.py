import os
import json
import logging

DEFAULT_LIVE_CACHE_PATH = "data/live_player_mapping_cache.json"


def _normalize_key(nickname: str) -> str:
    return str(nickname or "").strip().lower()


def load_live_player_cache(cache_path: str | None = None) -> dict:
    cache_path = cache_path or DEFAULT_LIVE_CACHE_PATH
    if not os.path.exists(cache_path):
        return {}
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except Exception as e:
        logging.error(f"Failed to load live player cache from {cache_path}: {e}")
        return {}


def save_live_player_cache(cache: dict, cache_path: str | None = None) -> None:
    cache_path = cache_path or DEFAULT_LIVE_CACHE_PATH
    try:
        dir_name = os.path.dirname(cache_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Failed to save live player cache to {cache_path}: {e}")


def get_cached_live_player(nickname: str, cache_path: str | None = None) -> dict | None:
    cache_path = cache_path or DEFAULT_LIVE_CACHE_PATH
    key = _normalize_key(nickname)
    if not key:
        return None
    cache = load_live_player_cache(cache_path)
    if key in cache:
        return cache[key]
    for k, v in cache.items():
        if _normalize_key(k) == key:
            return v
    return None


def set_cached_live_player(
    nickname: str,
    player_data: dict,
    cache_path: str | None = None,
) -> None:
    cache_path = cache_path or DEFAULT_LIVE_CACHE_PATH
    key = _normalize_key(nickname)
    if not key:
        return
    cache = load_live_player_cache(cache_path)
    cache[key] = player_data
    save_live_player_cache(cache, cache_path)
