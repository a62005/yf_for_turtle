from src.constants.stat_map import translate_stat_id

def test_translate_stat_id_known():
    assert translate_stat_id("12") == "PTS"
    assert translate_stat_id("15") == "REB"

def test_translate_stat_id_unknown():
    assert translate_stat_id("999") == "stat_999"
