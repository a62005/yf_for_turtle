import os
import json
import logging
from src.utils import path_utils

_SENTINEL_DEFAULT_CACHE_PATH = "data/live_player_mapping_cache.json"
DEFAULT_LIVE_CACHE_PATH = _SENTINEL_DEFAULT_CACHE_PATH


def _resolve_cache_path(cache_path: str | None = None) -> str:
    if cache_path:
        return cache_path
    if DEFAULT_LIVE_CACHE_PATH != _SENTINEL_DEFAULT_CACHE_PATH:
        return DEFAULT_LIVE_CACHE_PATH
    return os.path.join(path_utils.DATA_DIR, "live_player_mapping_cache.json")


def _normalize_key(nickname: str) -> str:
    return str(nickname or "").strip().lower()


def load_live_player_cache(cache_path: str | None = None) -> dict:
    cache_path = _resolve_cache_path(cache_path)
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
    cache_path = _resolve_cache_path(cache_path)
    try:
        dir_name = os.path.dirname(cache_path)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logging.error(f"Failed to save live player cache to {cache_path}: {e}")


def get_cached_live_player(nickname: str, cache_path: str | None = None) -> dict | None:
    cache_path = _resolve_cache_path(cache_path)
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
    cache_path = _resolve_cache_path(cache_path)
    key = _normalize_key(nickname)
    if not key:
        return
    cache = load_live_player_cache(cache_path)
    cache[key] = player_data
    save_live_player_cache(cache, cache_path)
