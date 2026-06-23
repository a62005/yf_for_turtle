import pytest
from unittest.mock import MagicMock, patch
from src.llm.prompts.world_cup_match_search import analyze_football_matchup, SYSTEM_PROMPT

@patch('src.llm.gemini.GeminiProvider.generate')
def test_analyze_football_matchup_success(mock_generate):
    mock_generate.return_value = "這是一段專業的足球對戰分析..."
    
    result = analyze_football_matchup("巴西", "德國", api_key="dummy_key", model_name="gemini-3.5-flash")
    assert "這是一段專業的足球對戰分析" in result
    mock_generate.assert_called_once_with(
        "請為以下兩支球隊進行對戰分析：巴西 vs 德國",
        system_instruction=SYSTEM_PROMPT
    )

@patch('src.llm.gemini.GeminiProvider.generate')
def test_analyze_football_matchup_env_fallback(mock_generate):
    mock_generate.return_value = "環境變數 fallback 分析結果"
    
    with patch.dict('os.environ', {'LLM_API_KEY': 'env_api_key', 'LLM_MODEL': 'env_model_name'}, clear=True):
        result = analyze_football_matchup("巴西", "德國")
        assert result == "環境變數 fallback 分析結果"
        mock_generate.assert_called_once_with(
            "請為以下兩支球隊進行對戰分析：巴西 vs 德國",
            system_instruction=SYSTEM_PROMPT
        )

def test_analyze_football_matchup_missing_api_key():
    with patch.dict('os.environ', {}, clear=True):
        result = analyze_football_matchup("巴西", "德國")
        assert "LLM API key 尚未設定" in result

@patch('requests.post')
def test_analyze_football_matchup_agnes_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Agnes AI 對戰分析結果：巴西 vs 德國"
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    result = analyze_football_matchup("巴西", "德國", api_key="agnes_key", model_name="agnes-2.0-flash")
    assert result == "Agnes AI 對戰分析結果：巴西 vs 德國"
    mock_post.assert_called_once()
