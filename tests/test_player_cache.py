import os
import json
import pytest
from src.utils.player_cache import load_cache, save_cache, get_cached_player, set_cached_player

TEST_CACHE_PATH = "data/test_player_cache.json"

@pytest.fixture(autouse=True)
def cleanup():
    if os.path.exists(TEST_CACHE_PATH):
        os.remove(TEST_CACHE_PATH)
    yield
    if os.path.exists(TEST_CACHE_PATH):
        os.remove(TEST_CACHE_PATH)

def test_cache_operations():
    cache = load_cache(TEST_CACHE_PATH)
    assert cache == {}
    
    player_data = {
        "english_name": "LeBron James",
        "chinese_name": "勒布朗·詹姆斯",
        "team": "Los Angeles Lakers",
        "jersey_number": "23",
        "player_key": "nba.p.3704"
    }
    
    set_cached_player("喇叭", player_data, TEST_CACHE_PATH)
    
    loaded = get_cached_player("喇叭", TEST_CACHE_PATH)
    assert loaded is not None
    assert loaded["english_name"] == "LeBron James"
    assert loaded["player_key"] == "nba.p.3704"
