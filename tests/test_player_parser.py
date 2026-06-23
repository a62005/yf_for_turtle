import pytest
from unittest.mock import MagicMock, patch
from src.utils.player_parser import parse_player_nickname

@patch('src.utils.llm.gemini.GeminiProvider.generate_json')
def test_parse_player_nickname_success(mock_generate_json):
    mock_generate_json.return_value = {
        "is_known_player": True,
        "english_name": "LeBron James",
        "chinese_name": "勒布朗·詹姆斯",
        "team": "Los Angeles Lakers",
        "jersey_number": "23"
    }
    
    res = parse_player_nickname("喇叭", api_key="dummy_key", model_name="gemini-2.5-flash")
    assert res["is_known_player"] is True
    assert res["english_name"] == "LeBron James"
    assert res["jersey_number"] == "23"

@patch('src.utils.llm.gemini.GeminiProvider.generate_json')
def test_parse_player_nickname_unknown(mock_generate_json, mocker):
    mock_generate_json.return_value = {
        "is_known_player": False,
        "english_name": None,
        "chinese_name": None,
        "team": None,
        "jersey_number": None
    }
    mock_search = mocker.patch("src.utils.player_parser._search_duckduckgo", return_value=["NBA 測試結果"])
    
    res = parse_player_nickname("哈囉", api_key="dummy_key", model_name="gemini-2.5-flash")
    assert res["is_known_player"] is False
    assert mock_search.call_count == 1
    assert mock_generate_json.call_count == 2

@patch('requests.post')
def test_parse_player_nickname_agnes_success(mock_post, mocker):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"is_known_player": true, "english_name": "Stephen Curry", "chinese_name": "史蒂芬·柯瑞", "team": "Golden State Warriors", "jersey_number": "30"}'
                }
            }
        ]
    }
    mock_post.return_value = mock_response
    mock_search = mocker.patch("src.utils.player_parser._search_duckduckgo")

    res = parse_player_nickname("咖哩", api_key="agnes_key", model_name="agnes-2.0-flash")
    
    assert res["is_known_player"] is True
    assert res["english_name"] == "Stephen Curry"
    mock_search.assert_not_called()
    mock_post.assert_called_once()
