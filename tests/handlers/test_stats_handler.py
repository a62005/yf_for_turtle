import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime
import pytz
from src.handlers.stats_handler import StatsHandler
from src.utils.time_utils import get_stats_rule_date
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ImageMessage, TextMessage


def test_stats_handler_can_handle_all_commands():
    handler = StatsHandler()
    assert handler.can_handle("#戰績") is True
    assert handler.can_handle("  #戰績  ") is True
    assert handler.can_handle("#戰績昨天") is True
    assert handler.can_handle("#戰績 昨天") is True
    assert handler.can_handle("#戰績上週") is True
    assert handler.can_handle("#戰績 上週") is True
    assert handler.can_handle("#戰績W2") is True
    assert handler.can_handle("#戰績 W2") is True
    assert handler.can_handle("#戰績w23") is True
    assert handler.can_handle("#戰績 w23") is True
    assert handler.can_handle("#戰績20261120") is True
    assert handler.can_handle("#戰績 20261120") is True
    assert handler.can_handle("#戰績 2026-11-20") is True

    # 無效指令與非法日期
    assert handler.can_handle("#戰績 20261399") is False
    assert handler.can_handle("#當天戰績") is False
    assert handler.can_handle("戰績") is False


def test_stats_handler_parse_command():
    handler = StatsHandler()
    assert handler.parse_command("#戰績") == ("combined", None)
    assert handler.parse_command("#戰績昨天") == ("yesterday", None)
    assert handler.parse_command("#戰績 昨天") == ("yesterday", None)
    assert handler.parse_command("#戰績上週") == ("last_week", None)
    assert handler.can_handle("#戰績 上週") is True
    assert handler.parse_command("#戰績W5") == ("specific_week", 5)
    assert handler.parse_command("#戰績 w5") == ("specific_week", 5)
    assert handler.parse_command("#戰績20261120") == ("specific_date", "2026-11-20")
    assert handler.parse_command("#戰績 20261120") == ("specific_date", "2026-11-20")
    assert handler.parse_command("#戰績 2026-11-20") == ("specific_date", "2026-11-20")
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

    with patch("src.handlers.stats_handler.get_stats_rule_date", return_value="2026-10-26"), \
         patch("src.scheduler.fetch_daily_game_times_tw", return_value=None):
        from src.scheduler import clear_daily_schedule_state
        clear_daily_schedule_state()
        handler.execute(event, config)
        clear_daily_schedule_state()

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

    with patch("src.handlers.stats_handler.get_stats_rule_date", return_value="2026-10-26"), \
         patch("src.scheduler.fetch_daily_game_times_tw", return_value=None):
        from src.scheduler import clear_daily_schedule_state
        clear_daily_schedule_state()
        handler.execute(event, config)
        clear_daily_schedule_state()

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
def test_stats_handler_postponed_prompts_next_open_time_and_returns_yesterday_stats(
    mock_messaging_api, mock_api_client, mock_load_config, tmp_path
):
    """
    測試（降級 14:00 規則或延後開放時）：
    1. 13:55 判定仍有比賽 -> 延後至 14:25 更新、14:30 開放查詢
    2. 13:58 查詢 #戰績 (14:00 前) -> 正常回傳前一天 (2026-11-04) 戰績
    3. 14:05 查詢 #戰績 -> 提示 "因稍早或當前仍有比賽正在進行，請於14:30後再次查詢\n戰績數據日期：2026-11-04"，並附上 2026-11-04 戰績圖片
    4. 14:25 再次判定仍有比賽 -> 延後至 14:55 更新、15:00 開放查詢；14:35 查詢 -> 提示 "因稍早或當前仍有比賽正在進行，請於15:00後再次查詢\n戰績數據日期：2026-11-04"，並附上 2026-11-04 戰績圖片
    5. 14:55 更新完成 (completed=True, query_open_time=15:00)，14:57 查詢 -> 仍提示 "因稍早或當前仍有比賽正在進行，請於15:00後再次查詢\n戰績數據日期：2026-11-04" 與前一天圖片
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
         patch("src.scheduler.DATA_DIR", str(tmp_path)), \
         patch("src.scheduler.fetch_daily_game_times_tw", return_value=None):
        clear_daily_schedule_state()

        # 1. 13:55 觸發延後 -> next_update=14:25, query_open=14:30
        postpone_daily_schedule("2026-11-05", current_hm="13:55")

        # 2. 13:58 查詢 (14:00 前) -> 回傳前一天 2026-11-04 戰績
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 13, 58))):
            handler.execute(event, config)
        msgs_1358 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1358) == 2
        assert msgs_1358[0].text == "戰績數據日期：2026-11-04"

        # 3. 14:05 查詢 -> 提示 14:30 後再次查詢，並回傳前一天戰績
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 14, 5))):
            handler.execute(event, config)
        msgs_1405 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1405) == 2
        assert msgs_1405[0].text == "因稍早或當前仍有比賽正在進行，請於14:30後再次查詢\n戰績數據日期：2026-11-04"
        assert "2026-11-04_combined.png" in msgs_1405[1].original_content_url

        # 4. 14:25 仍有比賽 -> 延後至 14:55 更新、15:00 開放查詢；14:35 查詢 -> 提示 15:00 後再次查詢，並回傳前一天戰績
        postpone_daily_schedule("2026-11-05", current_hm="14:25")
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 14, 35))):
            handler.execute(event, config)
        msgs_1435 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1435) == 2
        assert msgs_1435[0].text == "因稍早或當前仍有比賽正在進行，請於15:00後再次查詢\n戰績數據日期：2026-11-04"
        assert "2026-11-04_combined.png" in msgs_1435[1].original_content_url

        # 5. 14:55 比賽結束並完成更新，但 14:57 查詢 (未滿 15:00) -> 仍提示 15:00 後再次查詢，並回傳前一天戰績
        mark_daily_schedule_completed("2026-11-05", update_time="14:55")
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 14, 57))):
            handler.execute(event, config)
        msgs_1457 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1457) == 2
        assert msgs_1457[0].text == "因稍早或當前仍有比賽正在進行，請於15:00後再次查詢\n戰績數據日期：2026-11-04"
        assert "2026-11-04_combined.png" in msgs_1457[1].original_content_url

        # 6. 15:00 查詢 -> 正常回傳當天 2026-11-05 戰績圖片
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 15, 0))):
            handler.execute(event, config)
        msgs_1500 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1500) == 2
        assert msgs_1500[0].text == "戰績數據日期：2026-11-05"
        assert "2026-11-05_combined.png" in msgs_1500[1].original_content_url

        clear_daily_schedule_state()


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
def test_stats_handler_dynamic_game_times_flow(
    mock_messaging_api, mock_api_client, mock_load_config, tmp_path
):
    """
    測試依據當日第一場與最後一場比賽時間的完整流程 (設第一場 07:30、最後一場 11:00 -> 12:55 更新 / 13:00 開放)：
    1. 06:00 (第一場比賽開始前)：直接回傳前一天 (2026-11-04) 戰績，無額外提示
    2. 09:00 (第一場 07:30 與最後一場 11:00 之間)：提示「今日比賽尚未完全結束\n戰績數據日期：2026-11-04」，並回傳前一天戰績圖片
    3. 11:30 (最後一場 11:00 開始後 ～ 13:00 前)：提示「因稍早或當前仍有比賽正在進行，請於13:00後再次查詢\n戰績數據日期：2026-11-04」，並回傳前一天戰績圖片
    4. 13:05 (已過 13:00，但當日最後一場比賽仍在打且尚未有當日圖檔)：順延至 13:30 開放，提示「因稍早或當前仍有比賽正在進行，請於13:30後再次查詢\n戰績數據日期：2026-11-04」，並回傳前一天戰績圖片
    5. 13:30 (比賽已結束且有當日圖檔)：回傳當天 (2026-11-05) 戰績圖片
    """
    from src.scheduler import (
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

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"
    config = MagicMock(spec=Configuration)
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance

    fake_game_times = {
        "date": "2026-11-05",
        "yahoo_date": "2026-11-04",
        "has_games": True,
        "first_game_time": "07:30",
        "last_game_time": "11:00",
        "base_update_time": "12:55",
        "query_open_time": "13:00",
    }

    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.scheduler.DATA_DIR", str(tmp_path)), \
         patch("src.scheduler.fetch_daily_game_times_tw", return_value=fake_game_times):
        clear_daily_schedule_state()

        # 1. 06:00 (第一場比賽前) -> 直接回傳前一天戰績
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 6, 0))):
            handler.execute(event, config)
        msgs_0600 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_0600) == 2
        assert msgs_0600[0].text == "戰績數據日期：2026-11-04"
        assert "2026-11-04_combined.png" in msgs_0600[1].original_content_url

        # 2. 09:00 (第一場與最後一場之間) -> 告知今日比賽尚未完全結束，並回傳前一天戰績
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 9, 0))):
            handler.execute(event, config)
        msgs_0900 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_0900) == 2
        assert msgs_0900[0].text == "今日比賽尚未完全結束\n戰績數據日期：2026-11-04"
        assert "2026-11-04_combined.png" in msgs_0900[1].original_content_url

        # 3. 11:30 (最後一場開始後，未達 13:00) -> 告知稍早或當前仍有比賽，請於 13:00 後再次查詢，並回傳前一天戰績
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 11, 30))):
            handler.execute(event, config)
        msgs_1130 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1130) == 2
        assert msgs_1130[0].text == "因稍早或當前仍有比賽正在進行，請於13:00後再次查詢\n戰績數據日期：2026-11-04"
        assert "2026-11-04_combined.png" in msgs_1130[1].original_content_url

        # 4. 13:05 (已過 13:00，但當日尚無圖檔且比賽仍在進行) -> 自動延至 13:30 開放並回傳前一天戰績
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 13, 5))), \
             patch("src.handlers.stats_handler.are_games_still_in_progress", return_value=True):
            handler.execute(event, config)
        msgs_1305 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1305) == 2
        assert msgs_1305[0].text == "因稍早或當前仍有比賽正在進行，請於13:30後再次查詢\n戰績數據日期：2026-11-04"
        assert "2026-11-04_combined.png" in msgs_1305[1].original_content_url

        # 5. 13:25 比賽結束並產生當日圖檔，13:30 查詢 -> 回傳當天 (2026-11-05) 戰績
        (img_dir / "2026-11-05_combined.png").write_bytes(b"today_img")
        mark_daily_schedule_completed("2026-11-05", update_time="13:25")
        mock_api_instance.reset_mock()
        with patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 13, 30))):
            handler.execute(event, config)
        msgs_1330 = mock_api_instance.reply_message.call_args[0][0].messages
        assert len(msgs_1330) == 2
        assert msgs_1330[0].text == "戰績數據日期：2026-11-05"
        assert "2026-11-05_combined.png" in msgs_1330[1].original_content_url

        clear_daily_schedule_state()


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
def test_stats_handler_historical_date_and_yesterday_current_season_only(
    mock_messaging_api, mock_api_client, mock_load_config, tmp_path
):
    """
    測試：
    1. #戰績 20260101（非當季，例如當季 2026-10-20 開季）-> 完全不回應（靜默忽略）
    2. #戰績 20261130（未來日期或本地無檔案）-> 完全不回應（靜默忽略）
    3. #戰績 20261110（當季且本地有圖片）-> 回傳 2026-11-10 戰績圖
    4. #戰績昨天（當季且本地有昨日圖片）-> 回傳昨日戰績圖；若無圖片亦不回應
    """
    tw_tz = pytz.timezone("Asia/Taipei")
    handler = StatsHandler()
    mock_load_config.return_value = {
        "LEAGUE_ID": "nba.l.49432",
        "SERVER_URL": "https://example.ngrok.app",
        "NEXT_SEASON_START_DATE": "2026-10-20 08:00:00",
    }

    league_dir = tmp_path / "league" / "nba" / "49432"
    img_dir = league_dir / "image"
    img_dir.mkdir(parents=True)
    # 模擬過期的上一季 metadata (2025-10-21 ~ 2026-04-05) 以及上一季殘留圖檔 2026-01-01
    (league_dir / "metadata.json").write_text(
        json.dumps({"start_date": "2025-10-21", "end_date": "2026-04-05", "end_week": 23}),
        encoding="utf-8",
    )
    (img_dir / "2026-01-01_combined.png").write_bytes(b"old_season_img")
    (img_dir / "2026-11-10_combined.png").write_bytes(b"nov10_img")
    (img_dir / "2026-11-22_combined.png").write_bytes(b"nov22_img")

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.reply_token = "dummy_token"
    config = MagicMock(spec=Configuration)
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance

    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 23, 15, 0))):

        # 1. #戰績 20260101 -> 屬於上一季（早於 2026-10 開季），即使有舊圖檔也不回應
        event.message.text = "#戰績 20260101"
        handler.execute(event, config)
        mock_api_instance.reply_message.assert_not_called()

        # 2. #戰績 20261115 -> 當季但本地無現有數據，靜默不回應
        event.message.text = "#戰績 20261115"
        handler.execute(event, config)
        mock_api_instance.reply_message.assert_not_called()

        # 3. #戰績 20261130 -> 未來日期，靜默不回應
        event.message.text = "#戰績 20261130"
        handler.execute(event, config)
        mock_api_instance.reply_message.assert_not_called()

        # 4. #戰績 20261110 -> 當季且有現有數據，正常回傳
        event.message.text = "#戰績 20261110"
        handler.execute(event, config)
        mock_api_instance.reply_message.assert_called_once()
        msgs_1110 = mock_api_instance.reply_message.call_args[0][0].messages
        assert msgs_1110[0].text == "戰績數據日期：2026-11-10"
        assert "2026-11-10_combined.png" in msgs_1110[1].original_content_url

        # 5. #戰績昨天 -> 11/23 15:00 的規則基準日為 11/23，昨天為 2026-11-22
        mock_api_instance.reset_mock()
        event.message.text = "#戰績昨天"
        handler.execute(event, config)
        mock_api_instance.reply_message.assert_called_once()
        msgs_yest = mock_api_instance.reply_message.call_args[0][0].messages
        assert msgs_yest[0].text == "戰績數據日期：2026-11-22"
        assert "2026-11-22_combined.png" in msgs_yest[1].original_content_url


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
def test_stats_handler_specific_week_and_last_week_from_local_data_and_json_render(
    mock_messaging_api, mock_api_client, mock_load_config, tmp_path
):
    """
    測試：
    1. #戰績 W2 -> 從本地當季資料找出屬於 W2 的最後一天 (最新日期) 回傳
    2. 若該日尚無 .png 但有本地 daily + weekly JSON，直接以本地 JSON 渲染生成圖片（不啟動爬蟲）
    3. #戰績上週 -> 自動計算當前週次 - 1，回傳上週最新一天的戰績
    4. #戰績 W9 -> 找不到 W9 現有數據時，靜默不回應
    """
    tw_tz = pytz.timezone("Asia/Taipei")
    handler = StatsHandler()
    mock_load_config.return_value = {
        "LEAGUE_ID": "nba.l.49432",
        "SERVER_URL": "https://example.ngrok.app",
        "NEXT_SEASON_START_DATE": "2026-10-20 08:00:00",
    }

    league_dir = tmp_path / "league" / "nba" / "49432"
    img_dir = league_dir / "image"
    daily_dir = league_dir / "daily"
    weekly_dir = league_dir / "weekly"
    img_dir.mkdir(parents=True)
    daily_dir.mkdir(parents=True)
    weekly_dir.mkdir(parents=True)

    # W1 (美西 10/19~10/25 -> 台灣 10/20~10/26)
    (img_dir / "2026-10-26_combined.png").write_bytes(b"w1_last_day")

    # W2 (美西 10/26~11/01 -> 台灣 10/27~11/02)
    # 台灣 10/30 有圖，台灣 11/02 (美西 11/01) 只有本地 JSON 無圖
    (img_dir / "2026-10-30_combined.png").write_bytes(b"w2_mid_day")
    sample_stats = {
        "league_id": "nba.l.49432",
        "date": "2026-11-01",
        "week": 2,
        "team_stats": [
            {"team_id": "1", "name": "韋哥", "stats": {"PTS": 120, "REB": 40, "AST": 25}}
        ],
    }
    (daily_dir / "date_2026-11-01.json").write_text(json.dumps(sample_stats), encoding="utf-8")
    (weekly_dir / "date_2026-11-01_weekly.json").write_text(json.dumps(sample_stats), encoding="utf-8")

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.reply_token = "dummy_token"
    config = MagicMock(spec=Configuration)
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance

    def fake_capture(html_str, out_path):
        with open(out_path, "wb") as f:
            f.write(b"rendered_from_local_json")

    # 設定當前時間為 2026-11-05 (屬於 W3，因此上週為 W2)
    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 5, 15, 0))), \
         patch("src.visualizer.capturer.capture_html_to_png", side_effect=fake_capture) as mock_capture, \
         patch("src.web_agent_fetcher.WebAgentFetcher") as mock_fetcher:

        # 1. #戰績 W2 -> 應選中 W2 最新一天 2026-11-02 (由美西 2026-11-01 JSON 渲染)
        event.message.text = "#戰績 W2"
        handler.execute(event, config)
        mock_fetcher.assert_not_called()
        assert mock_capture.called
        mock_api_instance.reply_message.assert_called_once()
        msgs_w2 = mock_api_instance.reply_message.call_args[0][0].messages
        assert msgs_w2[0].text == "戰績數據日期：2026-11-02"
        assert "2026-11-02_combined.png" in msgs_w2[1].original_content_url

        # 2. #戰績上週 -> 當前為 W3，上週為 W2 -> 回傳 2026-11-02
        mock_api_instance.reset_mock()
        event.message.text = "#戰績上週"
        handler.execute(event, config)
        mock_api_instance.reply_message.assert_called_once()
        msgs_lw = mock_api_instance.reply_message.call_args[0][0].messages
        assert msgs_lw[0].text == "戰績數據日期：2026-11-02"
        assert "2026-11-02_combined.png" in msgs_lw[1].original_content_url

        # 3. #戰績 W9 -> 找不到當季 W9 數據，靜默不回應
        mock_api_instance.reset_mock()
        event.message.text = "#戰績 W9"
        handler.execute(event, config)
        mock_api_instance.reply_message.assert_not_called()


@patch("src.handlers.stats_handler.load_config")
@patch("src.handlers.stats_handler.ApiClient")
@patch("src.handlers.stats_handler.MessagingApi")
def test_stats_handler_no_game_day_returns_latest_active_game_date(
    mock_messaging_api, mock_api_client, mock_load_config, tmp_path
):
    """
    測試當今天 (2026-11-28) 與昨天 (2026-11-27) 連續兩天皆無比賽時，
    查詢 #戰績 應自動回退至最後一天有比賽數據的日期 (2026-11-26)，絕不回傳全為 0 的無比賽日戰績。
    """
    from src.scheduler import clear_daily_schedule_state

    tw_tz = pytz.timezone("Asia/Taipei")
    handler = StatsHandler()
    mock_load_config.return_value = {
        "LEAGUE_ID": "nba.l.49432",
        "SERVER_URL": "https://example.ngrok.app",
    }

    img_dir = tmp_path / "league" / "nba" / "49432" / "image"
    img_dir.mkdir(parents=True)
    # 最後一天有比賽的戰績圖為 2026-11-26
    (img_dir / "2026-11-26_combined.png").write_bytes(b"last_active_day_img")

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.message.text = "#戰績"
    event.reply_token = "dummy_token"
    config = MagicMock(spec=Configuration)
    mock_api_instance = MagicMock()
    mock_messaging_api.return_value = mock_api_instance

    def fake_fetch_times(sport, tw_date_str):
        if tw_date_str in ("2026-11-28", "2026-11-27"):
            return {"date": tw_date_str, "has_games": False}
        return {"date": tw_date_str, "has_games": True}

    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.scheduler.DATA_DIR", str(tmp_path)), \
         patch("src.scheduler.fetch_daily_game_times_tw", side_effect=fake_fetch_times), \
         patch("src.utils.time_utils.fetch_daily_game_times_tw", side_effect=fake_fetch_times), \
         patch("src.handlers.stats_handler._get_now_tw", return_value=tw_tz.localize(datetime(2026, 11, 28, 15, 0))):
        clear_daily_schedule_state()
        handler.execute(event, config)
        clear_daily_schedule_state()

    mock_api_instance.reply_message.assert_called_once()
    msgs = mock_api_instance.reply_message.call_args[0][0].messages
    assert len(msgs) == 2
    assert msgs[0].text == "戰績數據日期：2026-11-26"
    assert "2026-11-26_combined.png" in msgs[1].original_content_url

