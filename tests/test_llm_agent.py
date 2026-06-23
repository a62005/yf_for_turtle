import pytest
from unittest.mock import MagicMock, patch
from src.llm.llm_agent import LLMAgent

@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_command_intent(mock_generate_json):
    # Stage 1: intent classifier returns "league_query"
    # Stage 2: league intent parsing returns the command structure
    mock_generate_json.side_effect = [
        {"category": "league_query"},
        {
            "is_command": True,
            "command_text": "#對戰 小謝",
            "reply_text": None
        }
    ]

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("幫我查小謝這週對戰", "指令清單")
        assert result["is_command"] is True
        assert result["command_text"] == "#對戰 小謝"
        assert mock_generate_json.call_count == 2


@patch('src.llm.gemini.GeminiProvider.generate')
@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_chat_intent(mock_generate_json, mock_generate):
    # Stage 1: intent classifier returns "casual_chat"
    mock_generate_json.return_value = {"category": "casual_chat"}
    # Stage 2: chat generator returns text response
    mock_generate.return_value = "哈囉！"

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！"
        mock_generate_json.assert_called_once()
        mock_generate.assert_called_once()


@patch('requests.post')
def test_llm_agent_agnes_chat_intent(mock_post):
    # Stage 1: Agnes response for intent classifier
    mock_resp_1 = MagicMock()
    mock_resp_1.status_code = 200
    mock_resp_1.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"category": "casual_chat"}'
                }
            }
        ]
    }
    
    # Stage 2: Agnes response for casual chat generation
    mock_resp_2 = MagicMock()
    mock_resp_2.status_code = 200
    mock_resp_2.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "哈囉！我是 Agnes AI。"
                }
            }
        ]
    }
    mock_post.side_effect = [mock_resp_1, mock_resp_2]

    with patch.dict('os.environ', {'LLM_MODEL': 'agnes-2.0-flash', 'LLM_API_KEY': 'agnes_key'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！我是 Agnes AI。"
        assert mock_post.call_count == 2


def test_llm_agent_missing_api_key():
    with patch.dict('os.environ', {}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result.get("error") is True
        assert "未配置" in result["reply_text"]


@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_exception(mock_generate_json):
    # Simulate exception on classification stage
    mock_generate_json.side_effect = Exception("API connection refused")

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result.get("error") is True
        assert "大腦暫時離線" in result["reply_text"]
