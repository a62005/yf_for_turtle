from unittest.mock import MagicMock, patch
from src.handlers.settings_handler import SettingsHandler

def test_settings_handler_can_handle():
    handler = SettingsHandler()
    assert handler.can_handle("#設置") is True
    assert handler.can_handle("設置") is False

def test_settings_handler_execute_offseason():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()

    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
         patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
         patch("src.utils.time_utils.get_pacific_date", return_value="2026-05-29"):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        assert "設置選單" in args[2]
        
        # 驗證「設置玩家暱稱」已啟用，且對應指令為 #設置玩家暱稱
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        assert "設置玩家暱稱" in btn_labels
        
        nickname_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置玩家暱稱"][0]
        assert nickname_btn["action"]["text"] == "#設置玩家暱稱"

        # 驗證在休賽季「設置選秀時間」啟用
        assert "設置選秀時間" in btn_labels
        draft_time_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置選秀時間"][0]
        assert draft_time_btn["action"]["text"] == "#設置選秀時間"

def test_settings_handler_execute_inseason():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()

    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
         patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
         patch("src.utils.time_utils.get_pacific_date", return_value="2026-04-10"):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        
        # 驗證在季中「設置選秀時間 (限休賽季)」反灰不可點擊
        assert "設置選秀時間" not in btn_labels
        assert "設置選秀時間 (限休賽季)" in btn_labels
        draft_time_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置選秀時間 (限休賽季)"][0]
        assert draft_time_btn["action"]["type"] == "postback"
        assert draft_time_btn["action"]["data"] == "action=ignore"


def test_settings_handler_contains_remove_league_button():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()
    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}), \
         patch("src.utils.cache_utils.load_league_metadata", return_value={"end_date": "2026-04-12"}), \
         patch("src.utils.time_utils.get_pacific_date", return_value="2026-04-10"):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args = handler.reply_flex.call_args[0]
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        remove_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and (btn["action"]["label"] == "移除聯盟ID (即將推出)" or btn["action"]["label"] == "移除聯盟ID")][0]
        assert remove_btn["action"]["text"] == "#移除聯盟ID"




