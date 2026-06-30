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
@patch('src.llm.llm_agent.LLMAgent.analyze_intent')
def test_router_skips_unmentioned_group_chat(mock_analyze, mock_get_bot_id):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組普通閒聊且無 mention
    event = create_mock_event("哈囉", chat_type="group")
    router.route(event, MagicMock())
    
    mock_analyze.assert_not_called()
    dispatcher.handle.assert_not_called()

@patch('src.handlers.intent_router.IntentRouter._get_bot_user_id', return_value='bot_user_id_123')
@patch('src.llm.llm_agent.LLMAgent.analyze_intent')
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
@patch('src.llm.llm_agent.LLMAgent.analyze_intent')
def test_router_skips_mentioned_others_group_chat(mock_analyze, mock_get_bot_id):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組中 @提及 其他人 (user_id 不一致)
    event = create_mock_event("哈囉", chat_type="group", mentionees=[{"type": "user", "user_id": "other_user_id"}])
    router.route(event, MagicMock())
    
    mock_analyze.assert_not_called()
    dispatcher.handle.assert_not_called()

@patch('src.handlers.intent_router.IntentRouter._get_bot_user_id', return_value='bot_user_id_123')
@patch('src.llm.llm_agent.LLMAgent.analyze_intent')
def test_router_skips_all_mention_group_chat(mock_analyze, mock_get_bot_id):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組中 @ALL 
    event = create_mock_event("哈囉", chat_type="group", mentionees=[{"type": "all", "user_id": None}])
    router.route(event, MagicMock())
    
    mock_analyze.assert_not_called()
    dispatcher.handle.assert_not_called()

@patch('src.llm.llm_agent.LLMAgent.analyze_intent')
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

@patch('src.handlers.intent_router.IntentRouter._get_bot_user_id', return_value='bot_user_id_123')
@patch('src.llm.llm_agent.LLMAgent.analyze_intent')
def test_router_mentioned_group_chat_llm_error_no_reply(mock_analyze, mock_get_bot_id):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組中 @提及 機器人本身，且 LLM 未啟用/出錯
    event = create_mock_event("哈囉", chat_type="group", mentionees=[{"type": "user", "user_id": "bot_user_id_123"}])
    mock_analyze.return_value = {"is_command": False, "command_text": None, "reply_text": "未配置金鑰", "error": True}
    
    config = Configuration()
    config.access_token = "dummy_access_token"
    with patch('linebot.v3.messaging.MessagingApi.reply_message') as mock_reply:
        router.route(event, config)
        mock_analyze.assert_called_once()
        mock_reply.assert_not_called()  # 應該完全不回覆！

@patch('src.llm.llm_agent.LLMAgent.analyze_intent')
def test_router_private_chat_llm_error_still_replies(mock_analyze):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 單聊，且 LLM 未啟用/出錯
    event = create_mock_event("哈囉", chat_type="user")
    mock_analyze.return_value = {"is_command": False, "command_text": None, "reply_text": "未配置金鑰", "error": True}
    
    config = Configuration()
    config.access_token = "dummy_access_token"
    with patch('linebot.v3.messaging.MessagingApi.reply_message') as mock_reply:
        router.route(event, config)
        mock_analyze.assert_called_once()
        mock_reply.assert_called_once()  # 單聊依然要回覆錯誤訊息給使用者

@patch('src.handlers.intent_router.IntentRouter._get_bot_user_id', return_value='bot_user_id_123')
def test_should_process_logic(mock_get_bot_id):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    config = MagicMock()
    
    # 1. 標準指令 -> True
    event_cmd = create_mock_event("#戰績", chat_type="group")
    assert router.should_process(event_cmd, config) is True
    
    # 2. 單聊 -> True
    event_private = create_mock_event("嗨哈囉", chat_type="user")
    assert router.should_process(event_private, config) is True
    
    # 3. 群聊中 @提及 機器人 -> True
    event_group_mentioned = create_mock_event("哈囉", chat_type="group", mentionees=[{"type": "user", "user_id": "bot_user_id_123"}])
    assert router.should_process(event_group_mentioned, config) is True
    
    # 4. 群聊中包含 @bot 文字 -> True
    event_group_text_mention = create_mock_event("哈囉 @bot", chat_type="group")
    assert router.should_process(event_group_text_mention, config) is True
    
    # 5. 群聊普通閒聊 (無 mention、無 #) -> False
    event_group_chat = create_mock_event("我不行了", chat_type="group")
    assert router.should_process(event_group_chat, config) is False

    # 6. 群聊無 mention 但該用戶有活動中的選秀/暱稱會話 -> True
    event_group_session = create_mock_event("2026-10-15 20:00", chat_type="group")
    event_group_session.source.user_id = "U12345_session"
    
    with patch("src.handlers.intent_router.get_draft_time_session", return_value={"type": "draft_time"}), \
         patch("src.handlers.intent_router.get_nickname_session", return_value=None):
        assert router.should_process(event_group_session, config) is True
        
    with patch("src.handlers.intent_router.get_draft_time_session", return_value=None), \
         patch("src.handlers.intent_router.get_nickname_session", return_value={"type": "nickname"}):
        assert router.should_process(event_group_session, config) is True


@patch('src.llm.llm_agent.LLMAgent.analyze_intent')
def test_router_converts_injury_command_and_dispatches(mock_analyze):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 模擬使用者發問：看韋哥傷兵
    event = create_mock_event("幫我看一下韋哥有誰受傷", chat_type="user")
    mock_analyze.return_value = {"is_command": True, "command_text": "#傷兵 韋哥", "reply_text": None}
    
    config = Configuration()
    config.access_token = "dummy_access_token"
    
    router.route(event, config)
    mock_analyze.assert_called_once()
    # 確保成功轉交 dispatcher 處理，且其內容被置換為 "#傷兵 韋哥"
    dispatcher.handle.assert_called_once_with(event, config)
    assert event.message.text == "#傷兵 韋哥"


def test_intent_router_nickname_session_interception():
    import json
    from unittest.mock import mock_open
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_nickname_session, get_nickname_session
    
    dispatcher = CommandDispatcher()
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_test_intercept"
    event.source.type = "user"
    event.message.text = "韋哥的新暱稱"
    config = MagicMock()
    
    # 設置 60 秒的有效會話
    set_nickname_session("user_test_intercept", "1", duration_sec=60)
    
    mock_mapping = {"1": "小明"}
    
    with patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "123"}), \
         patch("src.handlers.intent_router.get_league_team_mapping_path", return_value="dummy_dir/team_mapping.json"), \
         patch("src.handlers.intent_router.os.path.exists", return_value=True), \
         patch("src.handlers.intent_router.os.makedirs") as mock_makedirs, \
         patch("src.handlers.intent_router.open", mock_open(read_data=json.dumps(mock_mapping))) as m_file, \
         patch.object(router, "reply_text") as mock_reply:
        
        router.route(event, config)
        
        # 驗證會話被清空
        assert get_nickname_session("user_test_intercept") is None
        # 驗證寫入新暱稱
        assert m_file().write.called
        # 驗證回覆
        mock_reply.assert_called_once_with(event, config, "✅ 成功將暱稱修改為：韋哥的新暱稱")

def test_intent_router_nickname_session_reset_by_command():
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_nickname_session, get_nickname_session
    
    dispatcher = CommandDispatcher()
    dispatcher.handle = MagicMock()
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_test_reset"
    event.message.text = "#對戰"
    config = MagicMock()
    
    set_nickname_session("user_test_reset", "1", duration_sec=60)
    
    with patch.object(router, "should_process", return_value=True):
        router.route(event, config)
        # 標準指令將會話清除
        assert get_nickname_session("user_test_reset") is None
        # 正常分發指令
        dispatcher.handle.assert_called_once()

def test_intent_router_intercept_draft_session_success():
    import json
    from unittest.mock import mock_open
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_draft_time_session, get_draft_time_session
    from linebot.v3.messaging import Configuration
    
    dispatcher = CommandDispatcher()
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_test_draft"
    event.source.type = "user"
    event.message.text = "10月15號晚上8點"
    
    config = Configuration()
    config.access_token = "dummy_access_token"
    
    # 設置 60 秒的有效會話 (draft_time session)
    set_draft_time_session("user_test_draft", True, duration_sec=60)
    
    mock_settings = {"DRAFT_DATE": "2025-01-01"}
    
    # Mock LLMAgent.parse_draft_date 讓它成功解析出時間
    with patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "123"}), \
         patch("src.handlers.intent_router.os.path.exists", return_value=True), \
         patch("src.handlers.intent_router.os.makedirs") as mock_makedirs, \
         patch("src.handlers.intent_router.open", mock_open(read_data=json.dumps(mock_settings))) as m_file, \
         patch.object(router.llm_agent, "parse_draft_date", return_value={"success": True, "date": "2026-10-15 20:00"}), \
         patch.object(router, "reply_text") as mock_reply:
         
        router.route(event, config)
        
        # 驗證會話被清空
        assert get_draft_time_session("user_test_draft") is None
        # 驗證寫入新設定到 settings.json
        assert m_file().write.called
        # 驗證回覆包含標準成功字串
        mock_reply.assert_called_once_with(event, config, "✅ 成功將選秀時間修改為：2026-10-15 20:00")

def test_intent_router_intercept_draft_session_failure():
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_draft_time_session, get_draft_time_session
    from linebot.v3.messaging import Configuration
    
    dispatcher = CommandDispatcher()
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_test_draft_fail"
    event.source.type = "user"
    event.message.text = "忘記了"
    
    config = Configuration()
    config.access_token = "dummy_access_token"
    
    set_draft_time_session("user_test_draft_fail", True, duration_sec=60)
    
    with patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "123"}), \
         patch.object(router.llm_agent, "parse_draft_date", return_value={"success": False, "date": None}), \
         patch.object(router, "reply_text") as mock_reply:
         
        router.route(event, config)
        
        # 驗證會話依然存在 (解析失敗不清除會話)
        assert get_draft_time_session("user_test_draft_fail") is not None
        # 驗證回覆警告字串
        mock_reply.assert_called_once()
        args, kwargs = mock_reply.call_args
        assert "無法解析" in args[2] or "格式" in args[2] or "請重新輸入" in args[2]


def test_intent_router_prize_session_text_interception():
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_prize_session, get_prize_session
    
    dispatcher = CommandDispatcher()
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_prize_text"
    event.source.type = "user"
    event.message.text = "普通文字訊息"
    config = MagicMock()
    
    set_prize_session("user_prize_text", duration_sec=60)
    
    with patch.object(router, "reply_text") as mock_reply:
        router.route(event, config)
        assert get_prize_session("user_prize_text") is not None
        mock_reply.assert_called_once_with(
            event, config, "⚠️ 設置獎金模式中，請傳送獎金圖片，或輸入 # 取消設定。"
        )
        
    event.message.text = "#"
    with patch.object(router, "reply_text") as mock_reply:
        router.route(event, config)
        assert get_prize_session("user_prize_text") is None
        mock_reply.assert_called_once_with(event, config, "已取消設定。")

def test_intent_router_route_image():
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.utils.session_manager import set_prize_session, clear_prize_session
    from src.handlers.set_prize_handler import SetPrizeHandler
    
    dispatcher = CommandDispatcher()
    mock_handler = MagicMock(spec=SetPrizeHandler)
    dispatcher.register(mock_handler)
    
    router = IntentRouter(dispatcher)
    
    event = MagicMock()
    event.source.user_id = "user_prize_image"
    event.message.id = "image_msg_123"
    config = MagicMock()
    
    set_prize_session("user_prize_image", duration_sec=60)
    
    with patch("src.handlers.intent_router.ApiClient"), \
         patch("linebot.v3.messaging.MessagingApiBlob") as mock_blob_class:
        
        mock_blob = MagicMock()
        mock_blob.get_message_content.return_value = b"image_data"
        mock_blob_class.return_value = mock_blob
        
        router.route_image(event, config)
        
        mock_blob.get_message_content.assert_called_once_with("image_msg_123")
        mock_handler.handle_image.assert_called_once_with(event, config, b"image_data")
        
    clear_prize_session("user_prize_image")


