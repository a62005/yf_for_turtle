import pytest
from unittest.mock import MagicMock, patch
from src.utils.gemini_parser import parse_player_nickname

def test_parse_player_nickname_success(mocker):
    # Mock google.generativeai 的 model.generate_content
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_known_player": true, "english_name": "LeBron James", "chinese_name": "勒布朗·詹姆斯", "team": "Los Angeles Lakers", "jersey_number": "23", "confidence": 1.0, "reason": "test"}'
    mock_model.generate_content.return_value = mock_response
    
    mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    
    res = parse_player_nickname("喇叭", api_key="dummy_key")
    assert res["is_known_player"] is True
    assert res["english_name"] == "LeBron James"
    assert res["jersey_number"] == "23"

def test_parse_player_nickname_unknown(mocker):
    # 測試第一次與第二次皆解析失敗
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_known_player": false, "english_name": null, "chinese_name": null, "team": null, "jersey_number": null, "confidence": 0.0, "reason": "test"}'
    mock_model.generate_content.return_value = mock_response
    
    mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    # mock 搜尋以免測試時發送真實請求
    mock_search = mocker.patch("src.utils.gemini_parser._search_duckduckgo", return_value=["NBA 測試結果"])
    
    res = parse_player_nickname("哈囉", api_key="dummy_key")
    assert res["is_known_player"] is False
    assert mock_search.call_count == 1
    assert mock_model.generate_content.call_count == 2

def test_parse_player_nickname_with_search_success(mocker):
    # 測試第一次解析失敗，但經過網路搜尋後第二次解析成功
    mock_model = MagicMock()
    
    # 設定 side_effect 來為兩次 generate_content 提供不同 response
    mock_response1 = MagicMock()
    mock_response1.text = '{"is_known_player": false}'
    
    mock_response2 = MagicMock()
    mock_response2.text = '{"is_known_player": true, "english_name": "Luka Doncic", "chinese_name": "盧卡·東契奇", "team": "Dallas Mavericks", "jersey_number": "77"}'
    
    mock_model.generate_content.side_effect = [mock_response1, mock_response2]
    
    mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    
    # 模擬搜尋回傳
    mock_search = mocker.patch(
        "src.utils.gemini_parser._search_duckduckgo", 
        return_value=["標題: Luka Doncic wears 77\n摘要: Luka Doncic wears number 77 for Dallas Mavericks"]
    )
    
    res = parse_player_nickname("77", api_key="dummy_key")
    
    assert res["is_known_player"] is True
    assert res["english_name"] == "Luka Doncic"
    assert res["jersey_number"] == "77"
    mock_search.assert_called_once_with('NBA "77"')
    assert mock_model.generate_content.call_count == 2

def test_parse_player_nickname_search_empty_fallback(mocker):
    # 測試第一次解析失敗，且搜尋結果為空時，不進行第二次解析，直接 fallback 回傳第一次的結果
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_known_player": false, "reason": "first_fail"}'
    mock_model.generate_content.return_value = mock_response
    
    mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    
    # 模擬搜尋結果為空
    mock_search = mocker.patch("src.utils.gemini_parser._search_duckduckgo", return_value=[])
    
    res = parse_player_nickname("哈囉", api_key="dummy_key")
    
    assert res["is_known_player"] is False
    assert res["reason"] == "first_fail"
    mock_search.assert_called_once_with('NBA "哈囉"')
    assert mock_model.generate_content.call_count == 1

def test_parse_player_nickname_custom_model(mocker):
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_known_player": true, "english_name": "LeBron James", "chinese_name": "勒布朗·詹姆斯", "team": "Los Angeles Lakers", "jersey_number": "23", "confidence": 1.0, "reason": "test"}'
    mock_model.generate_content.return_value = mock_response
    
    mock_generative_model = mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    
    # 1. 測試顯式傳入 model_name 參數
    parse_player_nickname("喇叭", api_key="dummy_key", model_name="my-custom-model")
    mock_generative_model.assert_called_with(
        model_name="my-custom-model",
        system_instruction=mocker.ANY
    )
    
    # 2. 測試從環境變數 GEMINI_MODEL 讀取
    mocker.patch.dict("os.environ", {"GEMINI_MODEL": "env-custom-model"})
    parse_player_nickname("喇叭", api_key="dummy_key")
    mock_generative_model.assert_called_with(
        model_name="env-custom-model",
        system_instruction=mocker.ANY
    )

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

    # mock 搜尋以免測試時發送真實請求
    mock_search = mocker.patch("src.utils.gemini_parser._search_duckduckgo")

    res = parse_player_nickname("咖哩", api_key="agnes_key", model_name="agnes-2.0-flash")
    
    assert res["is_known_player"] is True
    assert res["english_name"] == "Stephen Curry"
    mock_search.assert_not_called()
    mock_post.assert_called_once()
    args, kwargs = mock_post.call_args
    assert args[0] == "https://apihub.agnes-ai.com/v1/chat/completions"
    assert kwargs["json"]["model"] == "agnes-2.0-flash"
    assert kwargs["headers"]["Authorization"] == "Bearer agnes_key"
