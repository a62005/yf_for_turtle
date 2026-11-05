import json
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock
from src.scheduler import (
    get_bound_chat_leagues,
    trigger_daily_stats_push,
    _scheduler_loop,
    get_daily_schedule_state,
    clear_daily_schedule_state,
    TAIPEI_TZ,
)


def test_get_bound_chat_leagues_reads_mapping(tmp_path):
    sec_dir = tmp_path / "security"
    sec_dir.mkdir(parents=True)
    mapping_file = sec_dir / "chat_league_mapping.json"
    mapping_file.write_text(json.dumps({"C_group_1": "nba.l.49432"}), encoding="utf-8")

    with patch("src.scheduler.DATA_DIR", str(tmp_path)):
        result = get_bound_chat_leagues()
        assert result == {"C_group_1": "nba.l.49432"}


@patch("src.scheduler.subprocess.Popen")
def test_trigger_daily_stats_push_spawns_agent(mock_popen, tmp_path):
    sec_dir = tmp_path / "security"
    sec_dir.mkdir(parents=True)
    mapping_file = sec_dir / "chat_league_mapping.json"
    mapping_file.write_text(json.dumps({"C_group_1": "nba.l.49432"}), encoding="utf-8")

    with patch("src.scheduler.DATA_DIR", str(tmp_path)):
        count = trigger_daily_stats_push()
        assert count == 1
        mock_popen.assert_called_once()
        cmd = mock_popen.call_args[0][0]
        assert "--fetch-only" in cmd
        assert "nba.l.49432" in cmd
        assert "C_group_1" in cmd


@patch("src.scheduler.are_games_still_in_progress", return_value=False)
@patch("src.scheduler.trigger_daily_stats_push")
def test_scheduler_loop_triggers_at_14_00_once_per_day(mock_trigger, mock_in_progress, tmp_path):
    clear_daily_schedule_state()
    stop_event = threading.Event()
    fake_now = TAIPEI_TZ.localize(datetime(2026, 10, 20, 14, 0, 5))

    call_count = 0

    def fake_wait(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            stop_event.set()
            return True
        return False

    stop_event.wait = MagicMock(side_effect=fake_wait)

    with patch("src.scheduler.DATA_DIR", str(tmp_path)), \
         patch("src.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        _scheduler_loop(target_time="14:00", poll_interval=0.01, stop_event=stop_event)

    # 即使在 14:00 內輪詢兩次，同一天也只會觸發一次
    mock_trigger.assert_called_once()


@patch("src.scheduler.are_games_still_in_progress", return_value=False)
@patch("src.scheduler.trigger_daily_stats_push")
def test_scheduler_loop_triggers_at_13_55_default(mock_trigger, mock_in_progress, tmp_path):
    clear_daily_schedule_state()
    stop_event = threading.Event()
    fake_now = TAIPEI_TZ.localize(datetime(2026, 10, 20, 13, 55, 5))

    call_count = 0

    def fake_wait(timeout=None):
        nonlocal call_count
        call_count += 1
        if call_count >= 2:
            stop_event.set()
            return True
        return False

    stop_event.wait = MagicMock(side_effect=fake_wait)

    with patch("src.scheduler.DATA_DIR", str(tmp_path)), \
         patch("src.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        _scheduler_loop(poll_interval=0.01, stop_event=stop_event)

    mock_trigger.assert_called_once()


@patch("src.scheduler.trigger_daily_stats_push")
def test_scheduler_loop_postpones_by_30_mins_when_games_in_progress(mock_trigger, tmp_path):
    """
    測試：
    1. 13:55 仍有比賽 -> 不更新，延至 14:25 (開放查詢時間 14:30)
    2. 14:25 仍有比賽 -> 不更新，延至 14:55 (開放查詢時間 15:00)
    3. 14:55 比賽已結束 -> 執行更新，開放查詢時間維持 15:00
    """
    clear_daily_schedule_state()
    stop_event = threading.Event()

    times = [
        TAIPEI_TZ.localize(datetime(2026, 11, 5, 13, 55, 0)),
        TAIPEI_TZ.localize(datetime(2026, 11, 5, 14, 25, 0)),
        TAIPEI_TZ.localize(datetime(2026, 11, 5, 14, 55, 0)),
    ]
    game_states = [True, True, False]
    observed_states = []
    idx = 0

    def fake_now_fn(tz=None):
        return times[min(idx, len(times) - 1)]

    def fake_wait(timeout=None):
        nonlocal idx
        st = get_daily_schedule_state("2026-11-05")
        observed_states.append(dict(st) if st else None)
        idx += 1
        if idx >= len(times):
            stop_event.set()
            return True
        return False

    stop_event.wait = MagicMock(side_effect=fake_wait)

    with patch("src.scheduler.DATA_DIR", str(tmp_path)), \
         patch("src.scheduler.datetime") as mock_dt, \
         patch("src.scheduler.are_games_still_in_progress", side_effect=game_states):
        mock_dt.now.side_effect = fake_now_fn
        _scheduler_loop(target_time="13:55", poll_interval=0.01, stop_event=stop_event)

    # 13:55 後狀態：延至 14:25 更新，14:30 開放查詢
    assert observed_states[0]["next_update_time"] == "14:25"
    assert observed_states[0]["query_open_time"] == "14:30"
    assert observed_states[0]["games_in_progress"] is True

    # 14:25 後狀態：延至 14:55 更新，15:00 開放查詢
    assert observed_states[1]["next_update_time"] == "14:55"
    assert observed_states[1]["query_open_time"] == "15:00"
    assert observed_states[1]["games_in_progress"] is True

    # 14:55 比賽結束後狀態：觸發更新，開放時間 15:00，completed=True
    assert observed_states[2]["next_update_time"] == "14:55"
    assert observed_states[2]["query_open_time"] == "15:00"
    assert observed_states[2]["games_in_progress"] is False
    assert observed_states[2]["completed"] is True
    mock_trigger.assert_called_once_with("2026-11-05")
    clear_daily_schedule_state()
