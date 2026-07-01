import pytest
from unittest.mock import MagicMock, patch, mock_open
from src.handlers.settings_handler import SettingsHandler
from src.handlers.set_league_id_handler import SetLeagueIdHandler

def test_settings_handler_shows_flex_menu():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()
    
    event = MagicMock()
    config = MagicMock()
    
    # 測試 A: 當 LEAGUE_ID 未設定時，回傳僅含「設置聯盟ID」的選單
    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": None}):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        assert "設置選單" in args[2]

def test_set_league_id_handler_success():
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#設置聯盟ID 12345"
    config = MagicMock()
    
    mock_team = MagicMock()
    mock_team.team_id = "1"
    mock_team.name = "官方測試隊伍"
    
    mock_league = MagicMock()
    mock_league.teams.return_value = [mock_team]
    
    with patch("src.handlers.set_league_id_handler.sync_season_metadata") as mock_sync, \
         patch("src.handlers.set_league_id_handler.open", mock_open()) as mock_file, \
         patch("src.handlers.set_league_id_handler.os.path.exists", return_value=False), \
         patch("yahoofantasy.League", return_value=mock_league) as mock_league_cls:
        handler.execute(event, config)
        
        mock_sync.assert_called_once()
        mock_league_cls.assert_called_once()
        handler.reply_text.assert_called_once_with(
            event, 
            config, 
            "✅ 成功將此聊天室綁定至聯賽 ID：nba.l.12345"
        )


def test_set_league_id_handler_multi_league_binding():
    from src.config import current_chat_id
    import json
    
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#設置聯盟ID 99999"
    config = MagicMock()
    
    mock_team = MagicMock()
    mock_team.team_id = "1"
    mock_team.name = "官方測試隊伍"
    
    mock_league = MagicMock()
    mock_league.teams.return_value = [mock_team]
    
    # 紀錄 open 寫入的資料
    written_data = {}
    
    import builtins
    import io
    original_open = builtins.open
    
    class MockFile(io.StringIO):
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            val = self.getvalue()
            if val:
                try:
                    nonlocal written_data
                    written_data = json.loads(val)
                except Exception:
                    pass
        def close(self):
            val = self.getvalue()
            if val:
                try:
                    nonlocal written_data
                    written_data = json.loads(val)
                except Exception:
                    pass
            super().close()

    def custom_open(path, mode="r", *args, **kwargs):
        if "chat_league_mapping.json" in str(path).replace("\\", "/"):
            if "r" in mode:
                return MockFile("{}")
            return MockFile()
        return original_open(path, mode, *args, **kwargs)
        
    token = current_chat_id.set("group_abc")
    try:
        with patch("src.handlers.set_league_id_handler.sync_season_metadata") as mock_sync, \
             patch("src.handlers.set_league_id_handler.open", side_effect=custom_open), \
             patch("src.handlers.set_league_id_handler.os.path.exists", return_value=False), \
             patch("yahoofantasy.League", return_value=mock_league) as mock_league_cls:
             
            handler.execute(event, config)
            
            mock_sync.assert_called_once()
            assert written_data.get("group_abc") == "nba.l.99999"
            handler.reply_text.assert_called_once_with(
                event, 
                config, 
                "✅ 成功將此聊天室綁定至聯賽 ID：nba.l.99999"
            )
    finally:
        current_chat_id.reset(token)


def test_set_league_id_handler_interactive_flow(mocker):
    from src.handlers.set_league_id_handler import SetLeagueIdHandler
    from src.utils import session_manager
    
    handler = SetLeagueIdHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_reply_text = mocker.patch.object(handler, "reply_text")
    
    # 測試 1: 傳送 "#設置聯盟ID" (無參數)
    event1 = MagicMock()
    event1.message.text = "#設置聯盟ID"
    event1.source.user_id = "user_test_123"
    
    handler.execute(event1, MagicMock())
    
    # 驗證是否回覆 Flex Message
    mock_reply_flex.assert_called_once()
    flex_msg = mock_reply_flex.call_args[0][3]
    assert flex_msg is not None
    
    # 測試 2: 選擇運動 "#設置聯盟ID nba"
    event2 = MagicMock()
    event2.message.text = "#設置聯盟ID nba"
    event2.source.user_id = "user_test_123"
    
    mock_reply_flex.reset_mock()
    
    handler.execute(event2, MagicMock())
    
    # 驗證是否設定了對話會話 (session_manager)
    session = session_manager.get_session("user_test_123", "set_league_id")
    assert session is not None
    assert session.get("sport") == "nba"
    
    # 驗證回覆了引導提示文字
    mock_reply_text.assert_called_once()
    assert "請在 60 秒內輸入您的聯盟 ID" in mock_reply_text.call_args[0][2]


def test_set_league_id_handler_interactive_session_digit(mocker):
    from src.handlers.set_league_id_handler import SetLeagueIdHandler
    from src.utils import session_manager
    
    handler = SetLeagueIdHandler()
    mock_reply_text = mocker.patch.object(handler, "reply_text")
    
    # 設定一個 active session，使用者已選擇 nba
    session_manager.set_session("user_test_456", "set_league_id", {"sport": "nba"}, duration_sec=60)
    
    # 模擬 IntentRouter 攔截純數字後轉發的事件，也就是 text 變成 "#設置聯盟ID 18457"
    event3 = MagicMock()
    event3.message.text = "#設置聯盟ID 18457"
    event3.source.user_id = "user_test_456"
    
    # Mock sync_season_metadata 與 yahoofantasy
    mock_sync = mocker.patch("src.handlers.set_league_id_handler.sync_season_metadata")
    mock_league = MagicMock()
    mocker.patch("yahoofantasy.League", return_value=mock_league)
    mocker.patch("src.handlers.set_league_id_handler.open", mocker.mock_open())
    mocker.patch("src.handlers.set_league_id_handler.os.path.exists", return_value=True)
    mock_update = mocker.patch.object(handler, "_update_league_id")
    
    handler.execute(event3, MagicMock())
    
    # 驗證 session 是否被清除
    assert session_manager.get_session("user_test_456", "set_league_id") is None
    
    # 驗證傳給 _update_league_id 的 league_id 是 "nba.l.18457"
    mock_update.assert_called_once_with("nba.l.18457")


def test_set_league_id_handler_permission_denied_pre_saves_mapping(mocker):
    from src.handlers.set_league_id_handler import SetLeagueIdHandler
    from src.fetcher import LeaguePermissionError
    from src.config import current_chat_id
    
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.message.text = "#設置聯盟ID 12345"
    config = MagicMock()
    
    # Mock sync_season_metadata to raise LeaguePermissionError
    mocker.patch("src.handlers.set_league_id_handler.sync_season_metadata", side_effect=LeaguePermissionError("Permission Denied"))
    mock_update = mocker.patch.object(handler, "_update_league_id")
    
    token = current_chat_id.set("group_xyz")
    try:
        handler.execute(event, config)
            
        # Verify that _update_league_id was called with "nba.l.12345" even though it raised LeaguePermissionError
        mock_update.assert_called_once_with("nba.l.12345")
    finally:
        current_chat_id.reset(token)


def test_set_league_id_handler_shows_remove_confirm_card():
    from src.config import current_chat_id
    handler = SetLeagueIdHandler()
    handler.reply_flex = MagicMock()
    event = MagicMock()
    event.message.text = "#移除聯盟ID"
    config = MagicMock()

    token = current_chat_id.set("group_test_confirm")
    try:
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args = handler.reply_flex.call_args[0]
        title = args[2]
        flex_card = args[3]
        
        assert "請選擇" in title or "確認" in title
        # 檢查選單內有「確定移除」與「取消」按鈕
        buttons_box = flex_card["body"]["contents"][1]
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        assert "確定移除" in btn_labels
        assert "取消" in btn_labels
        
        confirm_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "確定移除"][0]
        assert confirm_btn["action"]["text"] == "#確定移除聯盟ID"
    finally:
        current_chat_id.reset(token)


def test_set_league_id_handler_remove_success_with_others():
    from src.config import current_chat_id
    from src.utils.session_manager import set_session
    import json
    
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    set_session("user_test_remove_1", "remove_league_id", {"active": True}, duration_sec=60)
    
    event = MagicMock()
    event.message.text = "#確定移除聯盟ID"
    event.source.user_id = "user_test_remove_1"
    config = MagicMock()
    
    written_data = {}
    def mock_mapping_io(path, mode="r", *args, **kwargs):
        import io
        class MockFile(io.StringIO):
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
            def close(self):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
                super().close()
                
        if "chat_league_mapping.json" in str(path).replace("\\", "/"):
            if "r" in mode:
                # 兩個群組都綁定同一聯賽 nba.l.11111
                return MockFile('{"group_1": "nba.l.11111", "group_2": "nba.l.11111"}')
            return MockFile()
        return open(path, mode, *args, **kwargs)

    token = current_chat_id.set("group_1")
    try:
        with patch("src.handlers.set_league_id_handler.open", side_effect=mock_mapping_io), \
             patch("src.handlers.set_league_id_handler.os.path.exists", return_value=True), \
             patch("src.handlers.set_league_id_handler.get_league_dir") as mock_get_dir, \
             patch("shutil.rmtree") as mock_rmtree:
             
            handler.execute(event, config)
            
            # 驗證 mapping 中 group_1 已被移除，但 group_2 仍保留
            assert "group_1" not in written_data
            assert written_data.get("group_2") == "nba.l.11111"
            # 驗證並未執行刪除資料夾（因為還有 group_2 綁定）
            mock_rmtree.assert_not_called()
            handler.reply_text.assert_called_once_with(event, config, "✅ 已成功解除此群組的聯盟綁定。")
    finally:
        current_chat_id.reset(token)

def test_set_league_id_handler_remove_success_and_delete_directory():
    from src.config import current_chat_id
    from src.utils.session_manager import set_session
    import json
    import os
    
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    set_session("user_test_remove_2", "remove_league_id", {"active": True}, duration_sec=60)
    
    event = MagicMock()
    event.message.text = "#確定移除聯盟ID"
    event.source.user_id = "user_test_remove_2"
    config = MagicMock()
    
    written_data = {}
    def mock_mapping_io(path, mode="r", *args, **kwargs):
        import io
        class MockFile(io.StringIO):
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
            def close(self):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
                super().close()
                
        if "chat_league_mapping.json" in str(path).replace("\\", "/"):
            if "r" in mode:
                # 只有 group_1 綁定 nba.l.22222
                return MockFile('{"group_1": "nba.l.22222"}')
            return MockFile()
        return open(path, mode, *args, **kwargs)

    token = current_chat_id.set("group_1")
    try:
        with patch("src.handlers.set_league_id_handler.open", side_effect=mock_mapping_io), \
             patch("src.handlers.set_league_id_handler.os.path.exists", return_value=True), \
             patch("src.handlers.set_league_id_handler.get_league_dir", return_value="mock_dir/nba/22222"), \
             patch("os.listdir", return_value=["metadata.json"]) as mock_listdir, \
             patch("os.path.isdir", side_effect=lambda p: "security" in p), \
             patch("os.remove") as mock_remove, \
             patch("shutil.rmtree") as mock_rmtree:
             
            handler.execute(event, config)
            
            assert "group_1" not in written_data
            mock_remove.assert_called_once_with(os.path.join("mock_dir/nba/22222", "metadata.json"))
            mock_rmtree.assert_not_called()
            handler.reply_text.assert_called_once_with(event, config, "✅ 已成功解除此群組的聯盟綁定。")
    finally:
        current_chat_id.reset(token)

def test_set_league_id_handler_remove_success_preserves_auth():
    from src.config import current_chat_id
    from src.utils.session_manager import set_session
    import json
    import os
    
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    set_session("user_test_remove_3", "remove_league_id", {"active": True}, duration_sec=60)
    
    event = MagicMock()
    event.message.text = "#確定移除聯盟ID"
    event.source.user_id = "user_test_remove_3"
    config = MagicMock()
    
    written_data = {}
    def mock_mapping_io(path, mode="r", *args, **kwargs):
        import io
        class MockFile(io.StringIO):
            def __enter__(self): return self
            def __exit__(self, exc_type, exc_val, exc_tb):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
            def close(self):
                nonlocal written_data
                val = self.getvalue()
                if val: written_data = json.loads(val)
                super().close()
                
        if "chat_league_mapping.json" in str(path).replace("\\", "/"):
            if "r" in mode:
                # 只有 group_1 綁定 nba.l.22222
                return MockFile('{"group_1": "nba.l.22222"}')
            return MockFile()
        return open(path, mode, *args, **kwargs)

    token = current_chat_id.set("group_1")
    try:
        with patch("src.handlers.set_league_id_handler.open", side_effect=mock_mapping_io), \
             patch("src.handlers.set_league_id_handler.os.path.exists", return_value=True), \
             patch("src.handlers.set_league_id_handler.get_league_dir", return_value="mock_dir/nba/22222"), \
             patch("os.listdir", return_value=[".yahoofantasy", "oauth2.json", "metadata.json", "daily", "some_oauth.json.tmp"]) as mock_listdir, \
             patch("os.path.isdir", side_effect=lambda p: "daily" in p or "security" in p) as mock_isdir, \
             patch("os.remove") as mock_remove, \
             patch("shutil.rmtree") as mock_rmtree:
             
            handler.execute(event, config)
            
            assert "group_1" not in written_data
            mock_listdir.assert_called_once_with("mock_dir/nba/22222")
            mock_remove.assert_any_call(os.path.join("mock_dir/nba/22222", "metadata.json"))
            
            # 確保 .yahoofantasy, oauth2.json 及包含 oauth 的項目皆未被刪除
            for call_args in mock_remove.call_args_list:
                assert ".yahoofantasy" not in call_args[0][0]
                assert "oauth2.json" not in call_args[0][0]
                assert "some_oauth.json.tmp" not in call_args[0][0]
            for call_args in mock_rmtree.call_args_list:
                assert ".yahoofantasy" not in call_args[0][0]
                assert "oauth2.json" not in call_args[0][0]
                
            mock_rmtree.assert_any_call(os.path.join("mock_dir/nba/22222", "daily"))
            handler.reply_text.assert_called_once_with(event, config, "✅ 已成功解除此群組的聯盟綁定。")
    finally:
        current_chat_id.reset(token)

def test_set_league_id_handler_remove_direct_call_without_session_fails():
    from src.utils.session_manager import clear_remove_league_session
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    # 確保沒有 remove_league_id 的 session
    clear_remove_league_session("user_no_session")
    
    event = MagicMock()
    event.message.text = "#確定移除聯盟ID"
    event.source.user_id = "user_no_session"
    config = MagicMock()
    
    handler.execute(event, config)
    
    # 根本不存在應直接無視，不作 any response
    handler.reply_text.assert_not_called()

def test_set_league_id_handler_remove_expired_session_fails():
    from src.utils.session_manager import set_remove_league_session
    handler = SetLeagueIdHandler()
    handler.reply_text = MagicMock()
    
    # 模擬已過期的 session
    set_remove_league_session("user_expired", duration_sec=-10)
    
    event = MagicMock()
    event.message.text = "#確定移除聯盟ID"
    event.source.user_id = "user_expired"
    config = MagicMock()
    
    handler.execute(event, config)
    
    handler.reply_text.assert_called_once_with(
        event,
        config,
        "⚠️ 移除請求已過期或未發起，請重新輸入 #移除聯盟ID。"
    )

def test_settings_handler_aliases():
    handler = SettingsHandler()
    assert handler.can_handle("#設定") is True
    assert handler.can_handle("#Setting") is True
    assert handler.can_handle("#setting") is True
    assert handler.can_handle("#設置") is True
    assert handler.can_handle("#其他") is False
