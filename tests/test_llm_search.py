import pytest
from unittest.mock import MagicMock, patch
from src.llm.gemini import GeminiProvider

def test_gemini_provider_generate_json_with_search():
    provider = GeminiProvider(api_key="dummy_key", model_name="gemini-3.5-flash")
    
    # Mock Client
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"success": true, "start_date": "2026-10-20 08:00:00"}'
    mock_client.models.generate_content.return_value = mock_response
    
    with patch.object(provider, "_get_client", return_value=mock_client):
        res = provider.generate_json_with_search("test prompt")
        assert res == {"success": True, "start_date": "2026-10-20 08:00:00"}
        
        # 驗證是否有傳入 google_search 工具設定
        args, kwargs = mock_client.models.generate_content.call_args
        assert "tools" in kwargs["config"]
        assert kwargs["config"]["tools"] == [{"google_search": {}}]
