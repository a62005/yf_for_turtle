import pytest
from unittest.mock import MagicMock, patch
from src.llm.llm_agent import LLMAgent

@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_command_intent(mock_generate_json):
    # Single-stage intent parsing returns the command structure directly
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
        assert mock_generate_json.call_count == 1


@patch('src.llm.gemini.GeminiProvider.generate')
@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_chat_intent(mock_generate_json, mock_generate):
    # Single-stage intent parsing returns non-command for casual chat
    mock_generate_json.return_value = {
        "is_command": False,
        "command_text": None,
        "reply_text": None
    }

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result["command_text"] is None
        assert result["reply_text"] is None
        mock_generate_json.assert_called_once()
        mock_generate.assert_not_called()


@patch('requests.post')
def test_llm_agent_agnes_chat_intent(mock_post):
    # Single-stage Agnes response for intent parsing
    mock_resp_1 = MagicMock()
    mock_resp_1.status_code = 200
    mock_resp_1.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"is_command": false, "command_text": null, "reply_text": null}'
                }
            }
        ]
    }
    mock_post.side_effect = [mock_resp_1]

    with patch.dict('os.environ', {'LLM_MODEL': 'agnes-2.0-flash', 'LLM_API_KEY': 'agnes_key'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        
        assert result["is_command"] is False
        assert result["command_text"] is None
        assert result["reply_text"] is None
        assert mock_post.call_count == 1


def test_llm_agent_missing_api_key():
    with patch.dict('os.environ', {}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result.get("error") is True
        assert "未配置" in result["reply_text"]


@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_exception(mock_generate_json):
    # Simulate exception on intent analysis
    mock_generate_json.side_effect = Exception("API connection refused")

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result.get("error") is True
        assert "大腦暫時離線" in result["reply_text"]


@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_parse_draft_date_success(mock_generate_json):
    mock_generate_json.return_value = {
        "success": True,
        "date": "2026-10-15 20:30"
    }

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.parse_draft_date("10月15號晚上8點30分")
        assert result["success"] is True
        assert result["date"] == "2026-10-15 20:30"
        mock_generate_json.assert_called_once()
        args, kwargs = mock_generate_json.call_args
        assert "10月15號晚上8點30分" in args[0]


@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_dynamic_context_loading(mock_generate_json):
    mock_generate_json.return_value = {
        "is_command": True,
        "command_text": "#戰績",
        "reply_text": None
    }

    # Setup dispatcher mock
    mock_dispatcher = MagicMock()
    mock_dispatcher.get_all_instruction_descs.return_value = "mocked_commands_desc"

    # Setup team mapping mock
    mock_mapping = {"team_1": "韋哥", "team_2": "小明"}

    # Setup metadata mock
    mock_meta = {
        "end_week": 21,
        "date_to_week": {
            "2026-10-15": 2
        }
    }

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True), \
         patch("src.llm.llm_agent.LLMAgent._load_team_mapping", return_value=mock_mapping), \
         patch("src.utils.cache_utils.load_league_metadata", return_value=mock_meta), \
         patch("src.utils.time_utils.get_pacific_date", return_value="2026-10-15"), \
         patch("src.config.load_config", return_value={"LEAGUE_ID": "nba.l.123"}):
         
        agent = LLMAgent()
        # Call with only text and dispatcher (other contexts are None)
        result = agent.analyze_intent("幫我查戰績", dispatcher=mock_dispatcher)
        
        assert result["is_command"] is True
        assert result["command_text"] == "#戰績"
        assert mock_generate_json.call_count == 1
        
        # Verify the context values resolved dynamically and were passed to generate_json
        args, kwargs = mock_generate_json.call_args
        system_prompt = kwargs.get("system_instruction")
        
        assert "mocked_commands_desc" in system_prompt
        assert "韋哥, 小明" in system_prompt
        assert "今天的太平洋時間日期為：2026-10-15。" in system_prompt
        assert "目前聯賽進行到第 2 週。" in system_prompt
        assert "聯賽的最後一週（例行賽結束週）為第 21 週。" in system_prompt


@patch('src.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_intent_cache_hit(mock_generate_json):
    mock_generate_json.return_value = {
        "is_command": True,
        "command_text": "#對戰 小謝",
        "reply_text": None
    }

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-3.5-flash'}, clear=True):
        agent = LLMAgent()
        res1 = agent.analyze_intent("幫我查小謝這週對戰", "指令清單", "小謝", "今天日期")
        res2 = agent.analyze_intent("幫我查小謝這週對戰", "指令清單", "小謝", "今天日期")
        assert res1 == res2
        # 第二次查詢相同內容與上下文應命中快取，不重複呼叫 LLM API
        assert mock_generate_json.call_count == 1
