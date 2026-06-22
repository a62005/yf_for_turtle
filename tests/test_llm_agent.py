import pytest
from unittest.mock import MagicMock, patch
from src.utils.llm_agent import LLMAgent

@patch('google.generativeai.GenerativeModel')
def test_llm_agent_command_intent(mock_model_cls):
    # Mock Response
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_command": true, "command_text": "#對戰 小謝", "reply_text": null}'
    mock_model.generate_content.return_value = mock_response
    mock_model_cls.return_value = mock_model

    # 必須設置臨時環境變數以供測試運行
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake_key'}):
        agent = LLMAgent()
        result = agent.analyze_intent("幫我查小謝這週對戰", "指令清單")
        assert result["is_command"] is True
        assert result["command_text"] == "#對戰 小謝"

@patch('google.generativeai.GenerativeModel')
def test_llm_agent_chat_intent(mock_model_cls):
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_command": false, "command_text": null, "reply_text": "哈囉！"}'
    mock_model.generate_content.return_value = mock_response
    mock_model_cls.return_value = mock_model

    with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake_key'}):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！"
