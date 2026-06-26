from unittest.mock import MagicMock, patch
from src.handlers.settings_handler import SettingsHandler

def test_settings_handler_can_handle():
    handler = SettingsHandler()
    assert handler.can_handle("#設置") is True
    assert handler.can_handle("設置") is False

def test_settings_handler_execute():
    handler = SettingsHandler()
    handler.reply_flex = MagicMock()

    event = MagicMock()
    config = MagicMock()

    with patch("src.handlers.settings_handler.load_config", return_value={"LEAGUE_ID": "12345"}):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        assert "設置選單" in args[2]
        
        # 驗證「設置玩家暱稱」已啟用，且對應指令為 #設置玩家暱稱
        flex_card = args[3]
        buttons_box = flex_card["body"]["contents"][1]
        btn_labels = [btn["action"]["label"] for btn in buttons_box["contents"] if btn["type"] == "button"]
        assert "設置玩家暱稱" in btn_labels
        assert "設置玩家暱稱 (即將推出)" not in btn_labels
        
        nickname_btn = [btn for btn in buttons_box["contents"] if btn["type"] == "button" and btn["action"]["label"] == "設置玩家暱稱"][0]
        assert nickname_btn["action"]["text"] == "#設置玩家暱稱"


