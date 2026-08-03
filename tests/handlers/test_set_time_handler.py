from unittest.mock import MagicMock, patch
import pytest

def test_set_time_handler_can_handle():
    from src.handlers.set_time_handler import SetTimeHandler
    handler = SetTimeHandler()
    assert handler.can_handle("#設置選秀時間") is True
    assert handler.can_handle("#設置開季時間") is True
    assert handler.can_handle("設置選秀時間") is False
    assert handler.can_handle("設置開季時間") is False

def test_set_time_handler_no_league_id():
    from src.handlers.set_time_handler import SetTimeHandler
    handler = SetTimeHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置選秀時間"
    event.source.user_id = "user123"
    config = MagicMock()

    with patch("src.handlers.set_time_handler.load_config", return_value={"LEAGUE_ID": None}):
        handler.execute(event, config)
        handler.reply_text.assert_called_once()
        args, kwargs = handler.reply_text.call_args
        assert "聯賽 ID 尚未配置" in args[2]

def test_set_time_handler_success_draft():
    from src.handlers.set_time_handler import SetTimeHandler
    from src.utils.session_manager import DraftTimeSession
    handler = SetTimeHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置選秀時間"
    event.source.user_id = "user123"
    config = MagicMock()

    with patch("src.handlers.set_time_handler.load_config", return_value={"LEAGUE_ID": "12345"}):
        with patch("src.handlers.set_time_handler.register_session") as mock_register:
            handler.execute(event, config)
            mock_register.assert_called_once()
            args = mock_register.call_args[0]
            assert isinstance(args[0], DraftTimeSession)
            assert args[0].user_id == "user123"
            handler.reply_text.assert_called_once()
            args, kwargs = handler.reply_text.call_args
            assert "請在 60 秒內直接輸入新的選秀時間" in args[2]

def test_set_time_handler_success_season_start():
    from src.handlers.set_time_handler import SetTimeHandler
    from src.utils.session_manager import SeasonStartTimeSession
    handler = SetTimeHandler()
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置開季時間"
    event.source.user_id = "user123"
    config = MagicMock()

    with patch("src.handlers.set_time_handler.load_config", return_value={"LEAGUE_ID": "12345"}):
        with patch("src.handlers.set_time_handler.register_session") as mock_register:
            handler.execute(event, config)
            mock_register.assert_called_once()
            args = mock_register.call_args[0]
            assert isinstance(args[0], SeasonStartTimeSession)
            assert args[0].user_id == "user123"
            handler.reply_text.assert_called_once()
            args, kwargs = handler.reply_text.call_args
            assert "請在 60 秒內直接輸入開季時間" in args[2]
