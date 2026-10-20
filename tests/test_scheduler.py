import json
import threading
from datetime import datetime
from unittest.mock import patch, MagicMock
from src.scheduler import (
    get_bound_chat_leagues,
    trigger_daily_stats_push,
    _scheduler_loop,
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
        assert "--push" in cmd
        assert "nba.l.49432" in cmd
        assert "C_group_1" in cmd


@patch("src.scheduler.trigger_daily_stats_push")
def test_scheduler_loop_triggers_at_14_00_once_per_day(mock_trigger):
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

    with patch("src.scheduler.datetime") as mock_dt:
        mock_dt.now.return_value = fake_now
        _scheduler_loop(target_time="14:00", poll_interval=0.01, stop_event=stop_event)

    # 即使在 14:00 內輪詢兩次，同一天也只會觸發一次
    mock_trigger.assert_called_once()
