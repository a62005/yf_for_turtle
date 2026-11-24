import json
from datetime import datetime
import pytz
import pytest
from unittest.mock import MagicMock
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

from src.handlers.local_matchup_handler import LocalMatchupHandler
from src.handlers.local_user_stats_handler import LocalUserStatsHandler
from src.handlers.misc_handler import MiscHandler
from src.handlers.dispatcher import CommandDispatcher
from src.handlers.stats_handler import StatsHandler


@pytest.fixture
def mock_event():
    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.source = MagicMock()
    event.source.user_id = "test_user"
    event.reply_token = "dummy_reply_token"
    return event


@pytest.fixture
def mock_config():
    return MagicMock(spec=Configuration)


def test_local_matchup_handler_can_handle(mocker, tmp_path):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_matchup_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch.object(LocalMatchupHandler, "_load_team_mapping", return_value={"1": "韋哥", "2": "Jerry"})

    handler = LocalMatchupHandler()
    assert handler.can_handle("#對戰") is True
    assert handler.can_handle("#對戰 ") is True
    assert handler.can_handle("#對戰 韋哥") is True
    assert handler.can_handle("#對戰 Jerry") is True
    assert handler.can_handle("#對戰 詹姆斯") is False
    assert handler.can_handle("#戰績") is False


def test_local_matchup_no_nickname_shows_player_list(mocker, mock_event, mock_config):
    handler = LocalMatchupHandler()
    mock_event.message.text = "#對戰"
    mock_reply_list = mocker.patch.object(handler, "reply_player_list")

    handler.execute(mock_event, mock_config)
    mock_reply_list.assert_called_once_with(mock_event, mock_config, is_matchup=True)


def test_local_matchup_execute_with_explicit_matchups(mocker, tmp_path, mock_event, mock_config):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_matchup_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.local_matchup_handler.load_league_metadata", return_value=None)
    mocker.patch.object(
        LocalMatchupHandler,
        "_load_team_mapping",
        return_value={"1": "韋哥", "2": "Jerry", "3": "陳威", "4": "阿明"},
    )
    tw_tz = pytz.timezone("Asia/Taipei")
    mocker.patch(
        "src.handlers.local_matchup_handler._get_now_tw",
        return_value=tw_tz.localize(datetime(2026, 4, 5, 15, 0, 0)),
    )

    weekly_dir = tmp_path / "league" / "nba" / "123" / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_payload = {
        "league_id": "nba.l.123",
        "date": "2026-04-04",
        "week": 23,
        "matchups": [
            {"team1_id": "1", "team2_id": "4"},
            {"team1_id": "2", "team2_id": "3"},
        ],
        "team_stats": [
            {
                "team_id": "1",
                "name": "韋哥",
                "official_name": "Vigo Official",
                "stats": {
                    "FGM/A": "180/350",
                    "FG%": 0.514,
                    "FTM/A": "0/0",
                    "FT%": 0.0,
                    "3PT": 35,
                    "PTS": 450,
                    "REB": 110,
                    "AST": 95,
                    "ST": 25,
                    "BLK": 12,
                    "TO": 32,
                },
            },
            {
                "team_id": "2",
                "name": "Jerry",
                "official_name": "Jerry Official",
                "stats": {"PTS": 100},
            },
            {
                "team_id": "3",
                "name": "陳威",
                "official_name": "Chen Official",
                "stats": {"PTS": 120},
            },
            {
                "team_id": "4",
                "name": "阿明",
                "official_name": "Ming Official",
                "stats": {
                    "FGM/A": "165/340",
                    "FG%": 0.485,
                    "FTM/A": "15/20",
                    "FT%": 0.750,
                    "3PT": 42,
                    "PTS": 410,
                    "REB": 125,
                    "AST": 80,
                    "ST": 20,
                    "BLK": 18,
                    "TO": 38,
                },
            },
        ],
    }
    (weekly_dir / "date_2026-04-04_weekly.json").write_text(
        json.dumps(weekly_payload, ensure_ascii=False), encoding="utf-8"
    )

    handler = LocalMatchupHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_event.message.text = "#對戰 韋哥"

    handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    call_args = mock_reply_flex.call_args[0]
    assert call_args[2] == "WEEK 23 MATCHUP - 韋哥 vs 阿明"
    bubble = call_args[3]
    assert bubble["type"] == "bubble"
    body = bubble["body"]["contents"]
    assert body[0]["text"] == "WEEK 23 MATCHUP"
    assert body[1]["contents"][0]["text"] == "韋哥"
    assert body[1]["contents"][2]["text"] == "阿明"
    assert body[2]["contents"][0]["text"] == "Vigo Official"
    assert body[2]["contents"][2]["text"] == "Ming Official"
    assert body[3]["contents"][0]["text"] == "5"
    assert body[3]["contents"][2]["text"] == "4"


def test_local_matchup_fallback_to_latest_file_and_adjacent_pairs(mocker, tmp_path, mock_event, mock_config):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_matchup_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch(
        "src.handlers.local_matchup_handler.load_league_metadata",
        return_value={
            "start_date": "2025-10-20",
            "end_date": "2026-04-12",
            "end_week": 24,
            "stat_categories": [
                {"stat_id": "9004003", "display_name": "FGM/A", "sort_order": 1},
                {"stat_id": "5", "display_name": "FG%", "sort_order": 1},
                {"stat_id": "9007006", "display_name": "FTM/A", "sort_order": 1},
                {"stat_id": "8", "display_name": "FT%", "sort_order": 1},
                {"stat_id": "10", "display_name": "3PTM", "sort_order": 1},
                {"stat_id": "12", "display_name": "PTS", "sort_order": 1},
                {"stat_id": "15", "display_name": "REB", "sort_order": 1},
                {"stat_id": "16", "display_name": "AST", "sort_order": 1},
                {"stat_id": "17", "display_name": "ST", "sort_order": 1},
                {"stat_id": "18", "display_name": "BLK", "sort_order": 1},
                {"stat_id": "19", "display_name": "TO", "sort_order": 0},
            ],
        },
    )
    mocker.patch.object(
        LocalMatchupHandler,
        "_load_team_mapping",
        return_value={"1": "韋哥", "2": "Jerry"},
    )
    # 模擬今天時間是 2026-04-06，但本地只有 2026-04-04 的舊格式 weekly 檔案（無 matchups 欄位）
    tw_tz = pytz.timezone("Asia/Taipei")
    mocker.patch(
        "src.handlers.local_matchup_handler._get_now_tw",
        return_value=tw_tz.localize(datetime(2026, 4, 6, 15, 0, 0)),
    )

    weekly_dir = tmp_path / "league" / "nba" / "123" / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_payload = {
        "league_id": "nba.l.123",
        "date": "2026-04-04",
        "team_stats": [
            {
                "team_id": "1",
                "name": "韋哥",
                "stats": {
                    "FGM/A": "180/350",
                    "FG%": 0.514,
                    "FTM/A": "20/25",
                    "FT%": 0.800,
                    "3PT": 35,
                    "PTS": 450,
                    "REB": 110,
                    "AST": 95,
                    "ST": 25,
                    "BLK": 12,
                    "TO": 32,
                },
            },
            {
                "team_id": "2",
                "name": "Jerry",
                "stats": {
                    "FGM/A": "165/340",
                    "FG%": 0.485,
                    "FTM/A": "15/20",
                    "FT%": 0.750,
                    "3PT": 42,
                    "PTS": 410,
                    "REB": 125,
                    "AST": 80,
                    "ST": 20,
                    "BLK": 18,
                    "TO": 38,
                },
            },
        ],
    }
    (weekly_dir / "date_2026-04-04_weekly.json").write_text(
        json.dumps(weekly_payload, ensure_ascii=False), encoding="utf-8"
    )

    handler = LocalMatchupHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_event.message.text = "#對戰 Jerry"

    handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    call_args = mock_reply_flex.call_args[0]
    assert "Jerry vs 韋哥" in call_args[2]
    bubble = call_args[3]
    body = bubble["body"]["contents"]
    # Jerry 贏 3PTM, REB, BLK (3 項)，韋哥贏 FG%, FT%, PTS, AST, ST, TO (6 項)，FGM/A 與 FTM/A 為輔助行不計入勝負
    assert body[3]["contents"][0]["text"] == "3"
    assert body[3]["contents"][2]["text"] == "6"


def test_help_menu_displays_local_matchup_and_local_user_stats(mocker, mock_event, mock_config):
    mocker.patch("src.handlers.misc_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.misc_handler.security_manager.is_whitelisted", return_value=False)

    dispatcher = CommandDispatcher()
    dispatcher.register(StatsHandler())
    dispatcher.register(LocalUserStatsHandler())
    dispatcher.register(LocalMatchupHandler())
    misc_handler = MiscHandler()
    dispatcher.register(misc_handler)

    mock_reply_flex = mocker.patch.object(misc_handler, "reply_flex")
    mock_event.message.text = "#幫助"

    misc_handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    flex_dict = mock_reply_flex.call_args[0][3]
    flex_str = json.dumps(flex_dict, ensure_ascii=False)
    assert "即時對決" in flex_str
    assert "#對戰" in flex_str
    assert "玩家數據" in flex_str
    assert "#玩家" in flex_str


def test_local_matchup_historical_query_case_insensitive(mocker, tmp_path, mock_event, mock_config):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_matchup_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.local_matchup_handler.load_league_metadata", return_value=None)
    mocker.patch.object(
        LocalMatchupHandler,
        "_load_team_mapping",
        return_value={"6": "胡哲", "7": "Covi", "11": "小謝", "1": "韋哥"},
    )
    tw_tz = pytz.timezone("Asia/Taipei")
    # Current time in Week 2
    mocker.patch(
        "src.handlers.local_matchup_handler._get_now_tw",
        return_value=tw_tz.localize(datetime(2026, 11, 1, 15, 0, 0)),
    )

    weekly_dir = tmp_path / "league" / "nba" / "123" / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    w1_payload = {
        "league_id": "nba.l.123",
        "date": "2026-10-25",
        "week": 1,
        "matchups": [
            {"team1_id": "6", "team2_id": "7"},
            {"team1_id": "11", "team2_id": "1"},
        ],
        "team_stats": [
            {"team_id": "6", "name": "胡哲", "stats": {"PTS": 300, "REB": 100, "AST": 50}},
            {"team_id": "7", "name": "Covi", "stats": {"PTS": 350, "REB": 90, "AST": 60}},
            {"team_id": "11", "name": "小謝", "stats": {"PTS": 280, "REB": 110, "AST": 40}},
            {"team_id": "1", "name": "韋哥", "stats": {"PTS": 310, "REB": 80, "AST": 70}},
        ],
    }
    (weekly_dir / "date_2026-10-25_weekly.json").write_text(
        json.dumps(w1_payload, ensure_ascii=False), encoding="utf-8"
    )

    handler = LocalMatchupHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")

    # 1. Test #對戰 COVI W1 (Uppercase nickname + specific week)
    mock_event.message.text = "#對戰 COVI W1"
    handler.execute(mock_event, mock_config)
    mock_reply_flex.assert_called_once()
    alt_text = mock_reply_flex.call_args[0][2]
    assert "WEEK 1 MATCHUP - Covi vs 胡哲" in alt_text

    # 2. Test #對戰 covi 上週 (Lowercase nickname + last week)
    mock_reply_flex.reset_mock()
    mock_event.message.text = "#對戰 covi 上週"
    handler.execute(mock_event, mock_config)
    mock_reply_flex.assert_called_once()
    alt_text2 = mock_reply_flex.call_args[0][2]
    assert "WEEK 1 MATCHUP - Covi vs 胡哲" in alt_text2


def test_fantasy_stat_toolkit_and_comparator_and_matchup_flex_renderer():
    from src.services.fantasy_stat_toolkit import FantasyStatToolkit, FantasyStatComparator
    from src.visualizer.matchup_flex_renderer import MatchupFlexRenderer

    # 1. FantasyStatToolkit alias lookup & fallback
    stats_fallback = {
        "stat_4": 15,
        "stat_3": 30,
        "stat_7": 0,
        "stat_6": 0,
        "3PM": 4,
        "STL": 3,
        "AST/TO": 2.5,
        "DD": 1,
        "OREB": 5,
    }
    assert FantasyStatToolkit.get_stat_raw(stats_fallback, "FGM/A") == "15/30"
    assert FantasyStatToolkit.get_stat_raw(stats_fallback, "FGM/FGA") == "15/30"
    assert FantasyStatToolkit.get_stat_raw(stats_fallback, "FTM/A") == "0/0"
    assert FantasyStatToolkit.get_stat_raw(stats_fallback, "3PTM") == 4
    assert FantasyStatToolkit.get_stat_raw(stats_fallback, "3PT") == 4
    assert FantasyStatToolkit.get_stat_raw(stats_fallback, "ST") == 3
    assert FantasyStatToolkit.get_stat_raw(stats_fallback, "A/T") == 2.5

    # 2. extract_extra_custom_keys ordered by EXTRA_NBA_ORDER
    extra_keys = FantasyStatToolkit.extract_extra_custom_keys(stats_fallback, {"TD": 1, "3PT%": 0.4})
    assert extra_keys == ["3PT%", "OREB", "A/T", "DD", "TD"]

    # 3. Formatting helpers
    assert FantasyStatToolkit.to_percent_str(0.514) == "51.4%"
    assert FantasyStatToolkit.to_percent_str(0.0) == "-"
    assert FantasyStatToolkit.to_val_str("180/350") == "180/350"
    assert FantasyStatToolkit.to_val_str(12.0) == "12"
    assert FantasyStatToolkit.to_val_str(0.0) == "0"
    assert FantasyStatToolkit.to_val_str(None) == "-"
    assert FantasyStatToolkit.format_stat_value("AVG", 0.312) == ".312"
    assert FantasyStatToolkit.format_stat_value("ERA", 3.456) == "3.46"
    assert FantasyStatToolkit.format_stat_value("A/T", 2.0, integer_at_ratio_as_int=True) == "2"
    assert FantasyStatToolkit.format_stat_value("A/T", 2.0, integer_at_ratio_as_int=False) == "2.00"
    assert FantasyStatToolkit.is_auxiliary_category({"stat_id": "9004003", "display_name": "FGM/A", "sort_order": 1}) is True
    assert FantasyStatToolkit.is_auxiliary_category({"stat_id": "12", "display_name": "PTS", "sort_order": 1}) is False

    # 4. FantasyStatComparator compare_stats & MatchupFlexRenderer render_matchup_card
    comparator = FantasyStatComparator()
    my_stats = {
        "FGM/A": "180/350", "FG%": 0.514, "FTM/A": "20/25", "FT%": 0.800,
        "3PTM": 35, "PTS": 450, "REB": 110, "AST": 95, "ST": 25, "BLK": 12, "TO": 32,
    }
    opp_stats = {
        "FGM/A": "165/340", "FG%": 0.485, "FTM/A": "15/20", "FT%": 0.750,
        "3PTM": 42, "PTS": 410, "REB": 110, "AST": 80, "ST": 20, "BLK": 18, "TO": 38,
    }
    comp_res = comparator.compare_stats(my_stats, opp_stats)
    assert comp_res["wins"] == 6
    assert comp_res["losses"] == 2
    assert comp_res["ties"] == 1
    assert comp_res["details"]["TO"]["status"] == "my_win"
    assert comp_res["details"]["REB"]["status"] == "tie"

    renderer = MatchupFlexRenderer()
    player_info = {
        "my_nickname": "韋哥",
        "my_official": "Vigo Official",
        "opp_nickname": "阿明",
        "opp_official": "Ming Official",
    }
    bubble = renderer.render_matchup_card(player_info, comp_res, "23")
    assert bubble["type"] == "bubble"
    assert bubble["body"]["contents"][0]["text"] == "WEEK 23 MATCHUP"
    assert bubble["body"]["contents"][3]["contents"][0]["text"] == "6"
    assert bubble["body"]["contents"][3]["contents"][2]["text"] == "2"


def test_local_league_data_repository_and_decoupled_handlers(mocker, tmp_path):
    from src.repositories.local_league_data_repository import LocalLeagueDataRepository, WeeklyFileEntry
    from src.handlers.local_score_handler import LocalScoreHandler

    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))

    repo = LocalLeagueDataRepository()
    tw_tz = pytz.timezone("Asia/Taipei")
    now_tw = tw_tz.localize(datetime(2026, 11, 23, 15, 0, 0))

    league_id = "nba.l.123"
    league_dir = tmp_path / "league" / "nba" / "123"
    daily_dir = league_dir / "daily"
    weekly_dir = league_dir / "weekly"
    daily_dir.mkdir(parents=True, exist_ok=True)
    weekly_dir.mkdir(parents=True, exist_ok=True)

    # Stale metadata from previous season + new season config
    stale_meta = {"start_date": "2025-10-21", "end_date": "2026-04-05", "end_week": 23}
    config = {"NEXT_SEASON_START_DATE": "2026-10-20 08:00:00"}

    start_y, end_y, end_w, is_stale = repo.get_current_season_bounds(league_id, config, stale_meta, now_tw)
    assert is_stale is True
    assert start_y == "2026-10-19"
    assert end_y is None
    assert end_w is None

    assert repo.is_tw_date_in_current_season("2026-11-10", now_tw, start_y, end_y) is True
    assert repo.is_tw_date_in_current_season("2026-01-01", now_tw, start_y, end_y) is False
    assert repo.is_tw_date_in_current_season("2026-11-30", now_tw, start_y, end_y) is False

    # Daily data: all zero vs valid
    zero_daily = {
        "date": "2026-11-22",
        "week": 5,
        "team_stats": [{"team_id": "1", "name": "韋哥", "stats": {"Today Player": 0, "PTS": 0}}],
    }
    valid_daily = {
        "date": "2026-11-21",
        "week": 5,
        "team_stats": [{"team_id": "1", "name": "韋哥", "official_name": "Vigo", "stats": {"Today Player": 5, "PTS": 95}}],
    }
    assert repo.is_daily_payload_all_zero(zero_daily) is True
    assert repo.is_daily_payload_all_zero(valid_daily) is False

    (daily_dir / "date_2026-11-22.json").write_text(json.dumps(zero_daily), encoding="utf-8")
    (daily_dir / "date_2026-11-21.json").write_text(json.dumps(valid_daily), encoding="utf-8")

    loaded_daily, disp_date = repo.load_default_local_daily_data(league_id, now_tw=now_tw)
    assert loaded_daily is not None
    assert loaded_daily["date"] == "2026-11-21"
    assert disp_date == "2026-11-22"

    found_team = repo.find_team_entry(loaded_daily, "1", "韋哥", {"1": "韋哥"})
    assert found_team is not None
    assert found_team["official_name"] == "Vigo"

    # Weekly data & matchups
    w4_final = {
        "date": "2026-11-15",
        "week": 4,
        "matchups": [{"team1_id": "1", "team2_id": "2"}],
        "team_stats": [
            {"team_id": "1", "name": "韋哥", "stats": {"PTS": 500}},
            {"team_id": "2", "name": "Jerry", "stats": {"PTS": 450}},
        ],
    }
    w5_live = {
        "date": "2026-11-22",
        "week": 5,
        "matchups": [{"team1_id": "1", "team2_id": "2"}],
        "team_stats": [
            {"team_id": "1", "name": "韋哥", "stats": {"PTS": 300}},
            {"team_id": "2", "name": "Jerry", "stats": {"PTS": 320}},
        ],
    }
    (weekly_dir / "date_2026-11-15_weekly.json").write_text(json.dumps(w4_final), encoding="utf-8")
    (weekly_dir / "date_2026-11-22_weekly.json").write_text(json.dumps(w5_live), encoding="utf-8")

    q_data, q_week, q_miss = repo.load_weekly_data_for_query(
        league_id, config, now_tw, week_mode="last_week", week_num=None, meta=stale_meta
    )
    assert q_miss is False
    assert q_week == 4
    assert q_data["date"] == "2026-11-15"

    matchups = repo.build_matchups_from_weekly_data(q_data, {"1": "韋哥", "2": "Jerry"})
    assert len(matchups) == 1
    assert matchups[0]["team1"]["name"] == "韋哥"
    assert matchups[0]["team2"]["name"] == "Jerry"

    # Verify handlers no longer have cross-handler helper attributes
    m_handler = LocalMatchupHandler(repository=repo)
    s_handler = LocalScoreHandler(repository=repo)
    st_handler = StatsHandler(repository=repo)
    u_handler = LocalUserStatsHandler(repository=repo)

    assert not hasattr(m_handler, "_stats_helper")
    assert not hasattr(s_handler, "_matchup_helper")
    assert not hasattr(s_handler, "_stats_helper")
    assert m_handler.repository is repo
    assert s_handler.repository is repo
    assert st_handler.repository is repo
    assert u_handler.repository is repo



