import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import pytz
from src.handlers.stats_handler import StatsHandler
from src.utils.time_utils import get_stats_rule_date
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ImageMessage, TextMessage


def test_stats_handler_can_handle_only_zhanji():
    handler = StatsHandler()
    assert handler.can_handle("#戰績") is True
    assert handler.can_handle("  #戰績  ") is True
    
    # 暫時移除其他特定天數查詢
    assert handler.can_handle("#戰績昨天") is False
    assert handler.can_handle("#戰績上週") is False
    assert handler.can_handle("#戰績W23") is False
    assert handler.can_handle("#戰績w23") is False
    assert handler.can_handle("#戰績20250101") is False
    assert handler.can_handle("#當天戰績") is False
    assert handler.can_handle("戰績") is False


def test_stats_handler_parse_command():
    handler = StatsHandler()
    assert handler.parse_command("#戰績") == ("combined", None)
    assert handler.parse_command("#戰績昨天") == (None, None)
    assert handler.parse_command("#無效") == (None, None)


def test_get_stats_rule_date():
    tw_tz = pytz.timezone("Asia/Taipei")
    
    # 10/27 10:30 (14:00 前) -> 10/26
    dt_before = tw_tz.localize(datetime(2026, 10, 27, 10, 30))
    assert get_stats_rule_date(dt_before) == "2026-10-26"

    # 10/27 13:59 (14:00 前) -> 10/26
    dt_just_before = tw_tz.localize(datetime(2026, 10, 27, 13, 59))
    assert get_stats_rule_date(dt_just_before) == "2026-10-26"

    # 10/27 14:00 (14:00 當刻) -> 10/27
    dt_exact = tw_tz.localize(datetime(2026, 10, 27, 14, 0))
    assert get_stats_rule_date(dt_exact) == "2026-10-27"

    # 10/27 14:01 (14:00 後) -> 10/27
    dt_after = tw_tz.localize(datetime(2026, 10, 27, 14, 1))
    assert get_stats_rule_date(dt_after) == "2026-10-27"


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("os.path.exists")
def test_stats_handler_nba_image_hit(mock_exists, mock_messaging_api, mock_api_client, mock_load_config, monkeypatch):
    handler = StatsHandler()
    mock_load_config.return_value = {
        "LEAGUE_ID": "nba.l.49432",
        "SERVER_URL": "http://localhost:5000"
    }
    monkeypatch.setenv("SERVER_URL", "http://localhost:5000")
    mock_exists.return_value = True

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"

    config = MagicMock(spec=Configuration)
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance

    with patch("src.handlers.stats_handler.get_stats_rule_date", return_value="2026-10-26"):
        handler.execute(event, config)

    assert mock_messaging_api.called
    call_args = mock_api_instance.reply_message.call_args
    assert call_args is not None
    reply_request = call_args[0][0]
    messages = reply_request.messages
    assert len(messages) == 2
    assert isinstance(messages[0], TextMessage)
    assert messages[0].text == "戰績數據日期：2026-10-26"
    assert isinstance(messages[1], ImageMessage)
    assert "2026-10-26_combined.png" in messages[1].original_content_url


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
@patch("os.path.exists")
def test_stats_handler_mlb_image_hit(mock_exists, mock_messaging_api, mock_api_client, mock_load_config, monkeypatch):
    handler = StatsHandler()
    mock_load_config.return_value = {
        "LEAGUE_ID": "mlb.l.62358",
        "SERVER_URL": "http://localhost:5000"
    }
    monkeypatch.setenv("SERVER_URL", "http://localhost:5000")
    mock_exists.return_value = True

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"

    config = MagicMock(spec=Configuration)
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance

    with patch("src.handlers.stats_handler.get_stats_rule_date", return_value="2026-10-26"):
        handler.execute(event, config)

    assert mock_messaging_api.called
    call_args = mock_api_instance.reply_message.call_args
    assert call_args is not None
    reply_request = call_args[0][0]
    messages = reply_request.messages
    assert len(messages) == 3
    assert isinstance(messages[0], TextMessage)
    assert messages[0].text == "戰績數據日期：2026-10-26"
    assert "2026-10-26_combined_hitter.png" in messages[1].original_content_url
    assert "2026-10-26_combined_pitcher.png" in messages[2].original_content_url


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
def test_stats_handler_postponed_blocks_query_and_prompts_next_open_time(
    mock_messaging_api, mock_api_client, mock_load_config, tmp_path
):
    """
    測試：
    1. 13:55 判定仍有比賽 -> 延後至 14:25 更新、14:30 開放查詢
    2. 13:58 查詢 #戰績 (14:00 前) -> 正常回傳前一天 (2026-11-04) 戰績
    3. 14:05 查詢 #戰績 -> 提示 "因仍有比賽正在進行，請於14:30後再次查詢"，且不回傳任何戰績
    4. 14:25 再次判定仍有比賽 -> 延後至 14:55 更新、15:00 開放查詢；14:35 查詢 -> 提示 "因仍有比賽正在進行，請於15:00後再次查詢"
    5. 14:55 更新完成 (completed=True, query_open_time=15:00)，14:57 查詢 -> 仍提示 "因仍有比賽正在進行，請於15:00後再次查詢"
    6. 15:00 查詢 -> 正常回傳當天 (2026-11-05) 戰績圖片
    """
    from src.scheduler import (
        postpone_daily_schedule,
        mark_daily_schedule_completed,
        clear_daily_schedule_state,
    )

    tw_tz = pytz.timezone("Asia/Taipei")
    handler = StatsHandler()
    mock_load_config.return_value = {
        "LEAGUE_ID": "nba.l.49432",
        "SERVER_URL": "https://example.ngrok.app"
    }

    img_dir = tmp_path / "league" / "nba" / "49432" / "image"
    img_dir.mkdir(parents=True)
    (img_dir / "2026-11-04_combined.png").write_bytes(b"yesterday_img")
    (img_dir / "2026-11-05_combined.png").write_bytes(b"today_img")

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"
    config = MagicMock(spec=Configuration)
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance

    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.scheduler.DATA_DIR", str(tmp_path)):
        clear_daily_schedule_state()

        # 1. 13:55 觸發延後 -> next_update=14:25, query_open=14:30
        postpone_daily_schedule("2026-11-05", current_hm="13:55")

        # 2. 13:58 查詢 (14:00 前) -> 回傳前一天 2026-11-04 戰績
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 13, 58))):
            handler.execute(event, config)
        msgs_1358 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1358) == 2
        assert msgs_1358[0].text == "戰績數據日期：2026-11-04"

        # 3. 14:05 查詢 -> 阻擋並提示 14:30 後再次查詢
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 14, 5))):
            handler.execute(event, config)
        msgs_1405 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1405) == 1
        assert msgs_1405[0].text == "因仍有比賽正在進行，請於14:30後再次查詢"

        # 4. 14:25 仍有比賽 -> 延後至 14:55 更新、15:00 開放查詢；14:35 查詢 -> 提示 15:00 後再次查詢
        postpone_daily_schedule("2026-11-05", current_hm="14:25")
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 14, 35))):
            handler.execute(event, config)
        msgs_1435 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1435) == 1
        assert msgs_1435[0].text == "因仍有比賽正在進行，請於15:00後再次查詢"

        # 5. 14:55 比賽結束並完成更新，但 14:57 查詢 (未滿 15:00) -> 仍提示 15:00 後再次查詢
        mark_daily_schedule_completed("2026-11-05", update_time="14:55")
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 14, 57))):
            handler.execute(event, config)
        msgs_1457 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1457) == 1
        assert msgs_1457[0].text == "因仍有比賽正在進行，請於15:00後再次查詢"

        # 6. 15:00 查詢 -> 正常回傳當天 2026-11-05 戰績圖片
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 15, 0))):
            handler.execute(event, config)
        msgs_1500 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1500) == 2
        assert msgs_1500[0].text == "戰績數據日期：2026-11-05"
        assert "2026-11-05_combined.png" in msgs_1500[1].original_content_url

        clear_daily_schedule_state()
