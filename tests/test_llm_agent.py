import pytest
from unittest.mock import MagicMock, patch
from src.llm.llm_agent import LLMAgent

@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_command_intent(mock_generate_json):
    mock_generate_json.return_value = {
        "is_command": True,
        "command_text": "#對戰 小謝",
        "reply_text": None
    }

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("幫我查小謝這週對戰", "指令清單")
        assert result["is_command"] is True
        assert result["command_text"] == "#對戰 小謝"

@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_chat_intent(mock_generate_json):
    mock_generate_json.return_value = {
        "is_command": False,
        "command_text": None,
        "reply_text": "哈囉！"
    }

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！"

@patch('requests.post')
def test_llm_agent_agnes_chat_intent(mock_post):
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

    with patch.dict('os.environ', {'LLM_MODEL': 'agnes-2.0-flash', 'LLM_API_KEY': 'agnes_key'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！我是 Agnes AI。"
        mock_post.assert_called_once()

def test_llm_agent_missing_api_key():
    with patch.dict('os.environ', {}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result.get("error") is True
        assert "未配置" in result["reply_text"]

@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_exception(mock_generate_json):
    mock_generate_json.side_effect = Exception("API connection refused")

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result.get("error") is True
        assert "大腦暫時離線" in result["reply_text"]
