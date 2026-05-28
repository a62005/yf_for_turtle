import pytest
from unittest.mock import MagicMock
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
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_known_player": false, "english_name": null, "chinese_name": null, "team": null, "jersey_number": null, "confidence": 0.0, "reason": "test"}'
    mock_model.generate_content.return_value = mock_response
    
    mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    
    res = parse_player_nickname("哈囉", api_key="dummy_key")
    assert res["is_known_player"] is False

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
