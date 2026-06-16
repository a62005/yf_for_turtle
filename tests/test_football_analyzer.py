import pytest
from unittest.mock import MagicMock
from src.utils.football_analyzer import analyze_football_matchup, SYSTEM_PROMPT

def test_analyze_football_matchup_success(mocker):
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "這是一段專業的足球對戰分析，字數大約兩百字左右..."
    mock_model.generate_content.return_value = mock_response
    
    mock_genai = mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    mock_configure = mocker.patch("google.generativeai.configure")
    
    team_a = "巴西"
    team_b = "德國"
    result = analyze_football_matchup(team_a, team_b, api_key="dummy_key")
    
    assert "這是一段專業的足球對戰分析" in result
    mock_configure.assert_called_once_with(api_key="dummy_key")
    
    # 驗證 SYSTEM_PROMPT 包含爆冷分析規定與投注下注推薦規定
    assert "爆冷機率" in SYSTEM_PROMPT
    assert "爆冷推薦" in SYSTEM_PROMPT
    assert "讓分" in SYSTEM_PROMPT
    assert "正確比分" in SYSTEM_PROMPT

    mock_genai.assert_called_once_with(
        model_name="gemini-3.5-flash",
        system_instruction=SYSTEM_PROMPT
    )
    mock_model.generate_content.assert_called_once_with(
        "請為以下兩支球隊進行對戰分析：巴西 vs 德國"
    )

def test_analyze_football_matchup_custom_model(mocker):
    # 測試傳入自訂 model_name 參數
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "自訂模型分析結果"
    mock_model.generate_content.return_value = mock_response
    
    mock_genai = mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    mocker.patch("google.generativeai.configure")
    
    analyze_football_matchup("巴西", "德國", api_key="dummy_key", model_name="my-custom-model")
    mock_genai.assert_called_once_with(
        model_name="my-custom-model",
        system_instruction=SYSTEM_PROMPT
    )

def test_analyze_football_matchup_env_fallback(mocker, monkeypatch):
    # 測試不傳入 api_key 與 model_name 時，正確從環境變數 fallback 讀取
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "環境變數 fallback 分析結果"
    mock_model.generate_content.return_value = mock_response
    
    mock_genai = mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    mock_configure = mocker.patch("google.generativeai.configure")
    
    monkeypatch.setenv("GEMINI_API_KEY", "env_api_key")
    monkeypatch.setenv("GEMINI_MODEL", "env_model_name")
    
    result = analyze_football_matchup("巴西", "德國")
    
    assert result == "環境變數 fallback 分析結果"
    mock_configure.assert_called_once_with(api_key="env_api_key")
    mock_genai.assert_called_once_with(
        model_name="env_model_name",
        system_instruction=SYSTEM_PROMPT
    )

def test_analyze_football_matchup_exception(mocker):
    # 測試 API 呼叫拋出異常時，回傳友好的錯誤訊息
    mock_model = MagicMock()
    mock_model.generate_content.side_effect = RuntimeError("API error")
    
    mocker.patch("google.generativeai.GenerativeModel", return_value=mock_model)
    mocker.patch("google.generativeai.configure")
    
    result = analyze_football_matchup("巴西", "德國", api_key="dummy_key")
    assert result == "系統繁忙，目前無法取得對戰分析，請稍後再試。"

def test_analyze_football_matchup_missing_api_key(monkeypatch):
    # 測試當沒有 API Key 時，回傳友好的錯誤提示字串
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    result = analyze_football_matchup("巴西", "德國")
    assert result == "Gemini API key 尚未設定，無法進行對戰分析。"
