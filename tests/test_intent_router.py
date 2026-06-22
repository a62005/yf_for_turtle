import pytest
from unittest.mock import MagicMock, patch
from src.handlers.intent_router import IntentRouter
from linebot.v3.messaging import Configuration

def create_mock_event(text, chat_type="user", mentionees=None):
    event = MagicMock()
    event.reply_token = "dummy_reply_token"
    
    # Message Mock
    message = MagicMock()
    message.text = text
    
    if mentionees is not None:
        mention = MagicMock()
        m_list = []
        for m_data in mentionees:
            m = MagicMock()
            m.type = m_data.get("type", "user")
            m.user_id = m_data.get("user_id", None)
            m_list.append(m)
        mention.mentionees = m_list
        message.mention = mention
    else:
        message.mention = None
        
    event.message = message
    
    # Source Mock
    source = MagicMock()
    source.type = chat_type
    event.source = source
    return event

@patch('src.handlers.intent_router.IntentRouter._get_bot_user_id', return_value='bot_user_id_123')
@patch('src.utils.llm_agent.LLMAgent.analyze_intent')
def test_router_skips_unmentioned_group_chat(mock_analyze, mock_get_bot_id):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組普通閒聊且無 mention
    event = create_mock_event("哈囉", chat_type="group")
    router.route(event, MagicMock())
    
    mock_analyze.assert_not_called()
    dispatcher.handle.assert_not_called()

@patch('src.handlers.intent_router.IntentRouter._get_bot_user_id', return_value='bot_user_id_123')
@patch('src.utils.llm_agent.LLMAgent.analyze_intent')
def test_router_handles_mentioned_group_chat(mock_analyze, mock_get_bot_id):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組中 @提及 機器人本身
    event = create_mock_event("哈囉", chat_type="group", mentionees=[{"type": "user", "user_id": "bot_user_id_123"}])
    mock_analyze.return_value = {"is_command": False, "command_text": None, "reply_text": "你好"}
    
    config = Configuration()
    config.access_token = "dummy_access_token"
    
    with patch('linebot.v3.messaging.MessagingApi.reply_message') as mock_reply:
        router.route(event, config)
        mock_analyze.assert_called_once()
        mock_reply.assert_called_once()

@patch('src.handlers.intent_router.IntentRouter._get_bot_user_id', return_value='bot_user_id_123')
@patch('src.utils.llm_agent.LLMAgent.analyze_intent')
def test_router_skips_mentioned_others_group_chat(mock_analyze, mock_get_bot_id):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組中 @提及 其他人 (user_id 不一致)
    event = create_mock_event("哈囉", chat_type="group", mentionees=[{"type": "user", "user_id": "other_user_id"}])
    router.route(event, MagicMock())
    
    mock_analyze.assert_not_called()
    dispatcher.handle.assert_not_called()

@patch('src.handlers.intent_router.IntentRouter._get_bot_user_id', return_value='bot_user_id_123')
@patch('src.utils.llm_agent.LLMAgent.analyze_intent')
def test_router_skips_all_mention_group_chat(mock_analyze, mock_get_bot_id):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組中 @ALL 
    event = create_mock_event("哈囉", chat_type="group", mentionees=[{"type": "all", "user_id": None}])
    router.route(event, MagicMock())
    
    mock_analyze.assert_not_called()
    dispatcher.handle.assert_not_called()

@patch('src.utils.llm_agent.LLMAgent.analyze_intent')
def test_router_converts_command_and_dispatches(mock_analyze):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 單聊
    event = create_mock_event("幫我查 Curry", chat_type="user")
    mock_analyze.return_value = {"is_command": True, "command_text": "#球員 Stephen Curry", "reply_text": None}
    
    config = MagicMock()
    dispatcher._handlers = config
    
    router.route(event, config)
    
    assert event.message.text == "#球員 Stephen Curry"
    dispatcher.handle.assert_called_once_with(event, router.dispatcher._handlers if hasattr(router.dispatcher, '_handlers') else MagicMock())
