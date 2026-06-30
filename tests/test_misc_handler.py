import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime
import pytz
import os

from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, TextMessage, ImageMessage

# Import the handler (this will fail initially because the file doesn't exist yet, or we'll create the empty file/class to allow import but fail the assertions)
from src.handlers.misc_handler import MiscHandler

@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.reply_token = "dummy_reply_token"
    event.message = MagicMock()
    return event

@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)

def test_misc_handler_can_handle():
    handler = MiscHandler()
    assert handler.can_handle("#開季") is True
    assert handler.can_handle("#選秀") is True
    assert handler.can_handle("#獎金") is True
    assert handler.can_handle("#幫助") is True
    assert handler.can_handle("#help") is True
    assert handler.can_handle("#Help") is True
    assert handler.can_handle("#HELP") is True
    assert handler.can_handle("  #help  ") is True
    
    assert handler.can_handle("#開季啦") is False
    assert handler.can_handle("#開季 ") is True # Since we strip the user text, this should be True
    assert handler.can_handle("#其他") is False
    assert handler.can_handle("開季") is False

def test_calculate_countdown():
    handler = MiscHandler()
    
    # Let's mock datetime now inside _calculate_countdown or patch datetime in pytz/datetime
    # Target time in the future
    # Let's mock datetime.now to return a fixed Taipei time: 2026-05-29 08:00:00
    taipei_tz = pytz.timezone("Asia/Taipei")
    fixed_now = taipei_tz.localize(datetime(2026, 5, 29, 8, 0, 0))
    
    with patch("src.handlers.misc_handler.datetime") as mock_datetime:
        # Mock datetime.now(taipei_tz)
        mock_datetime.now.return_value = fixed_now
        # Also need strptime to work normally
        mock_datetime.strptime = datetime.strptime
        
        # Test countdown to future
        res = handler._calculate_countdown("2026-05-30 09:30:00")
        assert res == "1 天 1 小時 30 分鐘"
        
        # Test target time reached
        res_reached = handler._calculate_countdown("2026-05-29 07:00:00")
        assert res_reached == "已經到達！"

@patch("src.handlers.misc_handler.save_league_metadata")
@patch("src.handlers.misc_handler.LLMAgent")
@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_season_start(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_llm_agent_class, mock_save_meta, mock_event, mock_config):
    handler = MiscHandler()
    mock_event.message.text = "#開季"
    mock_get_pacific.return_value = "2026-05-29"

    # 1. 優先檢查快取中是否有 next_season_start_date (且為休賽季)
    mock_load_meta.return_value = {"next_season_start_date": "2026-10-20 08:00:00", "end_date": "2026-04-12"}
    with patch.object(handler, "_calculate_countdown", return_value="140 天 5 小時 20 分鐘") as mock_calc:
        handler.execute(mock_event, mock_config)
        mock_calc.assert_called_with("2026-10-20 08:00:00")
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.reply_token == "dummy_reply_token"
        assert reply_req.messages[0].text == "🏀 新賽季即將開始以下時間開打：\n👉 2026年10月20日\n🏀 距離新賽季開季還有：\n👉 140 天 5 小時 20 分鐘"

    # 重設 mock 以供下一階段測試
    mock_messaging_api.reset_mock()
    mock_api_client.reset_mock()

    # 2. 快取中無 next_season_start_date，但 start_date 在未來
    mock_load_meta.return_value = {"start_date": "2026-10-25", "end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    with patch.object(handler, "_calculate_countdown", return_value="145 天 5 小時 20 分鐘") as mock_calc:
        handler.execute(mock_event, mock_config)
        mock_calc.assert_called_with("2026-10-25 08:00:00")
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.messages[0].text == "🏀 新賽季即將開始以下時間開打：\n👉 2026年10月25日\n🏀 距離新賽季開季還有：\n👉 145 天 5 小時 20 分鐘"

    mock_messaging_api.reset_mock()
    mock_api_client.reset_mock()

    # 3. 快取中皆無，使用 LLMAgent 搜尋成功
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_agent_instance = mock_llm_agent_class.return_value
    mock_agent_instance.search_nba_season_start.return_value = {"success": True, "start_date": "2026-10-22 08:00:00"}

    with patch.object(handler, "_calculate_countdown", return_value="142 天 5 小時 20 分鐘") as mock_calc, \
         patch.object(handler, "_update_settings_file") as mock_update:
        handler.execute(mock_event, mock_config)
        mock_calc.assert_called_with("2026-10-22 08:00:00")
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.messages[0].text == "🏀 新賽季即將開始以下時間開打：\n👉 2026年10月22日\n🏀 距離新賽季開季還有：\n👉 142 天 5 小時 20 分鐘"
        mock_update.assert_called_with({"next_season_start_date": "2026-10-22 08:00:00"})

    mock_messaging_api.reset_mock()
    mock_api_client.reset_mock()
    mock_save_meta.reset_mock()

    # 4. LLMAgent 搜尋失敗
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_agent_instance.search_nba_season_start.return_value = {"success": False}
    handler.execute(mock_event, mock_config)
    reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
    assert reply_req.messages[0].text == "🏀 無法獲取新賽季開季時間"

    mock_messaging_api.reset_mock()
    mock_api_client.reset_mock()

    # 5. 非休賽季 (in-season) -> 保持靜默不回覆
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-04-10"
    handler.execute(mock_event, mock_config)
    mock_api_client.assert_not_called()

@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_draft(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    
    # 1. Not offseason -> silently ignore
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-04-10"
    mock_event.message.text = "#選秀"
    
    handler.execute(mock_event, mock_config)
    mock_api_client.assert_not_called()
    
    # 2. Offseason, and DRAFT_DATE set -> reply countdown
    mock_get_pacific.return_value = "2026-05-29"
    mock_load_config.return_value = {"LEAGUE_ID": "nba.l.12345", "DRAFT_DATE": "2026-10-15 10:00"}
    
    with patch.object(handler, "_calculate_countdown", return_value="135 天 7 小時 0 分鐘") as mock_calc:
        handler.execute(mock_event, mock_config)
        mock_calc.assert_called_with("2026-10-15 10:00")
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        expected_reply = (
            "⚔️ 聯盟選秀即將開始以下時間舉行：\n"
            "👉 2026年10月15日 10:00\n"
            "⚔️ 距離聯盟選秀還有：\n"
            "👉 135 天 7 小時 0 分鐘"
        )
        assert reply_req.messages[0].text == expected_reply

@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_prize(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    mock_event.message.text = "#獎金"
    mock_get_pacific.return_value = "2026-05-29"
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    
    # 情境 1: 沒有綁定 league_id -> 靜默 return
    mock_load_config.return_value = {"LEAGUE_ID": None, "SERVER_URL": "http://localhost:5000"}
    handler.execute(mock_event, mock_config)
    mock_api_client.assert_not_called()
    
    # 情境 2: 已綁定，但找不到獎金圖片 -> 回覆 "尚未設置獎金"
    mock_api_client.reset_mock()
    mock_load_config.return_value = {"LEAGUE_ID": "mlb.l.62358", "SERVER_URL": "http://localhost:5000"}
    with patch("src.utils.path_utils.parse_league_id", return_value=("mlb", "62358")), \
         patch("os.path.exists", return_value=True), \
         patch("os.listdir", return_value=[]):  # 目錄為空
        handler.execute(mock_event, mock_config)
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.messages[0].text == "尚未設置獎金"
        
    # 情境 3: 已綁定，且有獎金圖片 (如 bouns.png) -> 回覆 ImageMessage
    mock_api_client.reset_mock()
    with patch("src.utils.path_utils.parse_league_id", return_value=("mlb", "62358")), \
         patch("os.path.exists", return_value=True), \
         patch("os.path.getmtime", return_value=12345.0), \
         patch("os.listdir", return_value=["bouns.png"]):
        handler.execute(mock_event, mock_config)
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert isinstance(reply_req.messages[0], ImageMessage)
        assert reply_req.messages[0].original_content_url == "https://localhost:5000/images/mlb/62358/bouns.png"

@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_help_success(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    mock_event.message.text = "#幫助"
    
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    
    # Mock builtins.open to return custom help content successfully
    import builtins
    mock_open_helper = MagicMock()
    mock_open_helper.return_value.__enter__.return_value.read.return_value = "Custom Help Document"
    
    with patch("builtins.open", mock_open_helper):
        handler.execute(mock_event, mock_config)
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.reply_token == "dummy_reply_token"
        assert reply_req.messages[0].text == "Custom Help Document"


@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_help_fallback(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_event, mock_config):
    handler = MiscHandler()
    mock_event.message.text = "#help"
    
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    
    # Mock builtins.open to raise FileNotFoundError to simulate missing file
    with patch("builtins.open", side_effect=FileNotFoundError("help.txt not found")):
        handler.execute(mock_event, mock_config)
        
        reply_req = mock_messaging_api.return_value.reply_message.call_args[0][0]
        assert reply_req.reply_token == "dummy_reply_token"
        assert "歡迎使用聯賽數據助手" in reply_req.messages[0].text
