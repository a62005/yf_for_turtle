import os
import json
from unittest.mock import MagicMock, patch, mock_open
from src.handlers.set_nickname_handler import SetNicknameHandler
from src.utils.session_manager import get_active_session, NicknameSession

def test_set_nickname_handler_can_handle():
    handler = SetNicknameHandler()
    assert handler.can_handle("#設置玩家暱稱") is True
    assert handler.can_handle("#設置暱稱_隊伍 1") is True
    assert handler.can_handle("#設置") is False

def test_set_nickname_handler_menu_flow():
    handler = SetNicknameHandler()
    handler.reply_flex = MagicMock()
    
    event = MagicMock()
    event.message.text = "#設置玩家暱稱"
    config = MagicMock()
    
    mock_mapping = {"1": "小明", "2": "陳威"}
    
    with patch("src.handlers.set_nickname_handler.load_config", return_value={"LEAGUE_ID": "123"}), \
         patch("src.handlers.set_nickname_handler.os.path.exists", return_value=True), \
         patch("src.handlers.set_nickname_handler.open", mock_open(read_data=json.dumps(mock_mapping))):
        handler.execute(event, config)
        handler.reply_flex.assert_called_once()
        args, kwargs = handler.reply_flex.call_args
        assert "設定玩家暱稱" in args[2]
        flex_dict = args[3]
        buttons = flex_dict["body"]["contents"][1]["contents"]
        assert len(buttons) == 2
        assert buttons[0]["action"]["label"] == "小明"
        assert buttons[0]["action"]["text"] == "#設置暱稱_隊伍 1"

def test_set_nickname_handler_select_team_flow():
    handler = SetNicknameHandler()
    handler.reply_text = MagicMock()
    
    event = MagicMock()
    event.source.user_id = "user_abc"
    event.message.text = "#設置暱稱_隊伍 1"
    config = MagicMock()
    
    mock_mapping = {"1": "小明", "2": "陳威"}
    
    with patch("src.handlers.set_nickname_handler.load_config", return_value={"LEAGUE_ID": "123"}), \
         patch("src.handlers.set_nickname_handler.os.path.exists", return_value=True), \
         patch("src.handlers.set_nickname_handler.open", mock_open(read_data=json.dumps(mock_mapping))):
        handler.execute(event, config)
        handler.reply_text.assert_called_once_with(
            event, config, "👉 請在 60 秒內直接輸入 小明 的新暱稱："
        )
        session = get_active_session("user_abc")
        assert session is not None
        assert isinstance(session, NicknameSession)
        assert session.team_id == "1"
