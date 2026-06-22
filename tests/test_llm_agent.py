import pytest
from unittest.mock import MagicMock, patch
from src.utils.llm_agent import LLMAgent

@patch('google.generativeai.GenerativeModel')
def test_llm_agent_gemini_command_intent(mock_model_cls):
    # Mock Response
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_command": true, "command_text": "#對戰 小謝", "reply_text": null}'
    mock_model.generate_content.return_value = mock_response
    mock_model_cls.return_value = mock_model

    with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}):
        agent = LLMAgent()
        result = agent.analyze_intent("幫我查小謝這週對戰", "指令清單")
        assert result["is_command"] is True
        assert result["command_text"] == "#對戰 小謝"

@patch('google.generativeai.GenerativeModel')
def test_llm_agent_gemini_chat_intent(mock_model_cls):
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_command": false, "command_text": null, "reply_text": "哈囉！"}'
    mock_model.generate_content.return_value = mock_response
    mock_model_cls.return_value = mock_model

    with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！"

@patch('requests.post')
def test_llm_agent_agnes_chat_intent(mock_post):
    # Mock Response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"is_command": false, "command_text": null, "reply_text": "哈囉！我是 Agnes AI。"}'
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    with patch.dict('os.environ', {'LLM_MODEL': 'agnes-2.0-flash', 'AGNES_API_KEY': 'agnes_key'}):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        
        # Verify result
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！我是 Agnes AI。"
        
        # Verify request routing
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        assert args[0] == "https://apihub.agnes-ai.com/v1/chat/completions"
        assert kwargs["json"]["model"] == "agnes-2.0-flash"
        assert kwargs["headers"]["Authorization"] == "Bearer agnes_key"
