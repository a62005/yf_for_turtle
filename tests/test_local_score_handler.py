import json
from datetime import datetime
import pytz
import pytest
from unittest.mock import MagicMock
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

from src.handlers.local_score_handler import LocalScoreHandler


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


def test_local_score_handler_can_handle_current_week_and_menu(mocker, tmp_path):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_score_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch.object(
        LocalScoreHandler,
        "_load_team_mapping",
        return_value={"1": "小謝", "2": "韋哥", "3": "Covi"},
    )

    handler = LocalScoreHandler()
    assert handler.can_handle("#比分") is True
    assert handler.can_handle("#比分 ") is True
    assert handler.can_handle("#比分 小謝") is True
    assert handler.can_handle("#比分 韋哥") is True
    assert handler.can_handle("#比分 路人甲") is False
    assert handler.can_handle("#對戰 小謝") is False


def test_local_score_no_nickname_shows_player_list(mocker, mock_event, mock_config):
    mocker.patch.object(
        LocalScoreHandler,
        "_load_team_mapping",
        return_value={"1": "小謝", "2": "韋哥"},
    )
    handler = LocalScoreHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_event.message.text = "#比分"

    handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    alt_text = mock_reply_flex.call_args[0][2]
    flex_dict = mock_reply_flex.call_args[0][3]
    assert "全聯盟比分查詢" in alt_text
    flex_str = json.dumps(flex_dict, ensure_ascii=False)
    assert "📊 全聯盟比分查詢" in flex_str
    assert "#比分 小謝" in flex_str
    assert "#比分 韋哥" in flex_str


def test_local_score_missing_local_data_replies_not_found(mocker, tmp_path, mock_event, mock_config):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_score_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.local_score_handler.load_league_metadata", return_value=None)
    mocker.patch.object(LocalScoreHandler, "_load_team_mapping", return_value={"1": "小謝"})

    handler = LocalScoreHandler()
    mock_reply_text = mocker.patch.object(handler, "reply_text")
    mock_event.message.text = "#比分 小謝"

    handler.execute(mock_event, mock_config)

    mock_reply_text.assert_called_once_with(mock_event, mock_config, "查無當週對戰數據")


def test_local_score_current_week_groups_sorts_hides_empty_and_marks_actual_opponent(
    mocker, tmp_path, mock_event, mock_config
):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_score_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.local_score_handler.load_league_metadata", return_value=None)
    mocker.patch.object(
        LocalScoreHandler,
        "_load_team_mapping",
        return_value={"10": "小謝", "6": "Andy", "7": "Covi", "5": "Joseph", "3": "Jerry"},
    )
    tw_tz = pytz.timezone("Asia/Taipei")
    mocker.patch(
        "src.handlers.local_score_handler._get_now_tw",
        return_value=tw_tz.localize(datetime(2026, 11, 23, 15, 0, 0)),
    )

    weekly_dir = tmp_path / "league" / "nba" / "123" / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_payload = {
        "league_id": "nba.l.123",
        "date": "2026-11-22",
        "week": 5,
        "matchups": [
            {"team1_id": "10", "team2_id": "6"},
            {"team1_id": "7", "team2_id": "5"},
        ],
        "team_stats": [
            {
                "team_id": "10",
                "name": "小謝",
                "official_name": "姆主席萬歲",
                "stats": {
                    "FGM/FGA": "215/462",
                    "FG%": 0.465,
                    "FTM/FTA": "80/98",
                    "FT%": 0.816,
                    "3PTM": 62,
                    "PTS": 574,
                    "REB": 189,
                    "AST": 127,
                    "ST": 36,
                    "BLK": 18,
                    "TO": 65,
                },
            },
            {
                "team_id": "7",
                "name": "Covi",
                "official_name": "艾七俱樂部",
                "stats": {
                    "FGM/FGA": "204/446",
                    "FG%": 0.457,
                    "FTM/FTA": "87/109",
                    "FT%": 0.798,
                    "3PTM": 68,
                    "PTS": 563,
                    "REB": 189,
                    "AST": 147,
                    "ST": 44,
                    "BLK": 16,
                    "TO": 91,
                },
            },
            {
                "team_id": "5",
                "name": "Joseph",
                "official_name": "中和賈奈特",
                "stats": {
                    "FGM/FGA": "246/474",
                    "FG%": 0.519,
                    "FTM/FTA": "81/110",
                    "FT%": 0.736,
                    "3PTM": 76,
                    "PTS": 649,
                    "REB": 172,
                    "AST": 126,
                    "ST": 26,
                    "BLK": 21,
                    "TO": 67,
                },
            },
            {
                "team_id": "3",
                "name": "Jerry",
                "official_name": "Jerry 傑瑞",
                "stats": {
                    "FGM/FGA": "213/456",
                    "FG%": 0.467,
                    "FTM/FTA": "104/135",
                    "FT%": 0.77,
                    "3PTM": 57,
                    "PTS": 587,
                    "REB": 233,
                    "AST": 164,
                    "ST": 48,
                    "BLK": 25,
                    "TO": 94,
                },
            },
            {
                "team_id": "6",
                "name": "Andy",
                "official_name": "來囉來囉",
                "stats": {
                    "FGM/FGA": "246/504",
                    "FG%": 0.488,
                    "FTM/FTA": "120/150",
                    "FT%": 0.8,
                    "3PTM": 59,
                    "PTS": 671,
                    "REB": 234,
                    "AST": 177,
                    "ST": 34,
                    "BLK": 28,
                    "TO": 61,
                },
            },
        ],
    }
    (weekly_dir / "date_2026-11-22_weekly.json").write_text(
        json.dumps(weekly_payload, ensure_ascii=False), encoding="utf-8"
    )

    handler = LocalScoreHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_event.message.text = "#比分 小謝"

    handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    alt_text = mock_reply_flex.call_args[0][2]
    bubble = mock_reply_flex.call_args[0][3]
    assert alt_text == "WEEK 5 ALL-PLAY - 小謝"
    assert bubble["type"] == "bubble"

    flex_str = json.dumps(bubble, ensure_ascii=False)
    assert "WEEK 5 ALL-PLAY" in flex_str
    assert "小謝" in flex_str
    assert "姆主席萬歲" in flex_str
    # 不含全聯盟模擬戰績灰底框
    assert "全聯盟模擬戰績" not in flex_str
    # 有勝場與敗場，且無平手時自動隱藏平手分組
    assert "🟢 勝場 (2)" in flex_str
    assert "🔴 敗場 (2)" in flex_str
    assert "⚪ 平手" not in flex_str

    # 檢查有平手比項顯示 5 : 3 : 1，無平手顯示 5 : 4 與 3 : 6
    assert "5 : 3 : 1" in flex_str
    assert "5 : 4" in flex_str
    assert "3 : 6" in flex_str

    # 檢查當週對手標記與同分優先排序（Andy 與 Jerry 皆為 3:6，Andy 為當週對手應排在 Jerry 前面）
    assert "⚔️ Andy" in flex_str
    assert "當週對手" in flex_str
    assert flex_str.index("⚔️ Andy") < flex_str.index("Jerry")
    # Covi (5:3:1, 淨勝 +2) 應排在 Joseph (5:4, 淨勝 +1) 前面
    assert flex_str.index("Covi") < flex_str.index("Joseph")


def test_local_score_handler_can_handle_historical_week_variants(mocker, tmp_path):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_score_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch.object(
        LocalScoreHandler,
        "_load_team_mapping",
        return_value={"10": "小謝", "1": "韋哥"},
    )

    handler = LocalScoreHandler()
    assert handler.can_handle("#比分 W3") is True
    assert handler.can_handle("#比分W3") is True
    assert handler.can_handle("#比分 上週") is True
    assert handler.can_handle("#比分上週") is True
    assert handler.can_handle("#比分 小謝 W4") is True
    assert handler.can_handle("#比分 小謝W4") is True
    assert handler.can_handle("#比分W4 小謝") is True
    assert handler.can_handle("#比分 w4 小謝") is True
    assert handler.can_handle("#比分 小謝 上週") is True
    assert handler.can_handle("#比分上週 小謝") is True
    assert handler.can_handle("#比分 路人甲 W4") is False


def test_local_score_menu_with_week_suffix_populates_buttons(mocker, mock_event, mock_config):
    mocker.patch.object(
        LocalScoreHandler,
        "_load_team_mapping",
        return_value={"10": "小謝", "1": "韋哥"},
    )
    handler = LocalScoreHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")

    mock_event.message.text = "#比分 W3"
    handler.execute(mock_event, mock_config)
    mock_reply_flex.assert_called_once()
    flex_str = json.dumps(mock_reply_flex.call_args[0][3], ensure_ascii=False)
    assert "#比分 小謝 W3" in flex_str
    assert "#比分 韋哥 W3" in flex_str

    mock_reply_flex.reset_mock()
    mock_event.message.text = "#比分 上週"
    handler.execute(mock_event, mock_config)
    mock_reply_flex.assert_called_once()
    flex_str_lw = json.dumps(mock_reply_flex.call_args[0][3], ensure_ascii=False)
    assert "#比分 小謝 上週" in flex_str_lw


def test_local_score_historical_week_and_last_week_uses_final_day_and_silently_ignores_missing(
    mocker, tmp_path, mock_event, mock_config
):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch(
        "src.handlers.local_score_handler.load_config",
        return_value={
            "LEAGUE_ID": "nba.l.123",
            "NEXT_SEASON_START_DATE": "2026-10-20 08:00:00",
        },
    )
    mocker.patch(
        "src.handlers.local_score_handler.load_league_metadata",
        return_value={"start_date": "2025-10-21", "end_date": "2026-04-05", "end_week": 23},
    )
    mocker.patch.object(
        LocalScoreHandler,
        "_load_team_mapping",
        return_value={"10": "小謝", "5": "Joseph", "7": "Covi"},
    )
    tw_tz = pytz.timezone("Asia/Taipei")
    # 當前時間為 2026-11-23 (屬於 W5，因此上週為 W4)
    mocker.patch(
        "src.handlers.local_score_handler._get_now_tw",
        return_value=tw_tz.localize(datetime(2026, 11, 23, 15, 0, 0)),
    )

    weekly_dir = tmp_path / "league" / "nba" / "123" / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)

    # W4 中間日 2026-11-12 (PTS=300) 與 W4 結算日 2026-11-15 (PTS=605，且含 tie 對手 Covi)
    w4_mid = {
        "league_id": "nba.l.123",
        "date": "2026-11-12",
        "week": 4,
        "team_stats": [
            {"team_id": "10", "name": "小謝", "official_name": "姆主席萬歲", "stats": {"PTS": 300}},
            {"team_id": "5", "name": "Joseph", "official_name": "中和賈奈特", "stats": {"PTS": 200}},
        ],
    }
    w4_final = {
        "league_id": "nba.l.123",
        "date": "2026-11-15",
        "week": 4,
        "matchups": [{"team1_id": "10", "team2_id": "5"}],
        "team_stats": [
            {
                "team_id": "10",
                "name": "小謝",
                "official_name": "姆主席萬歲",
                "stats": {
                    "FG%": 0.43,
                    "FT%": 0.787,
                    "3PTM": 62,
                    "PTS": 605,
                    "REB": 209,
                    "AST": 166,
                    "ST": 39,
                    "BLK": 22,
                    "TO": 78,
                },
            },
            {
                "team_id": "7",
                "name": "Covi",
                "official_name": "艾七俱樂部",
                "stats": {
                    "FG%": 0.451,
                    "FT%": 0.793,
                    "3PTM": 77,
                    "PTS": 556,
                    "REB": 202,
                    "AST": 135,
                    "ST": 39,
                    "BLK": 21,
                    "TO": 67,
                },
            },
            {
                "team_id": "5",
                "name": "Joseph",
                "official_name": "中和賈奈特",
                "stats": {
                    "FG%": 0.48,
                    "FT%": 0.82,
                    "3PTM": 75,
                    "PTS": 680,
                    "REB": 230,
                    "AST": 140,
                    "ST": 45,
                    "BLK": 30,
                    "TO": 85,
                },
            },
        ],
    }
    # W5 當週檔案 2026-11-22
    w5_live = {
        "league_id": "nba.l.123",
        "date": "2026-11-22",
        "week": 5,
        "team_stats": [
            {"team_id": "10", "name": "小謝", "official_name": "姆主席萬歲", "stats": {"PTS": 574}},
            {"team_id": "5", "name": "Joseph", "official_name": "中和賈奈特", "stats": {"PTS": 500}},
        ],
    }

    (weekly_dir / "date_2026-11-12_weekly.json").write_text(json.dumps(w4_mid), encoding="utf-8")
    (weekly_dir / "date_2026-11-15_weekly.json").write_text(json.dumps(w4_final), encoding="utf-8")
    (weekly_dir / "date_2026-11-22_weekly.json").write_text(json.dumps(w5_live), encoding="utf-8")

    handler = LocalScoreHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_reply_text = mocker.patch.object(handler, "reply_text")

    # 1. #比分 小謝 W4 -> 應選取 W4 最後一天 2026-11-15，顯示 WEEK 4 ALL-PLAY、平手 Covi 4:4:1、敗場 Joseph 2:7 (當週對手)
    mock_event.message.text = "#比分 小謝 W4"
    handler.execute(mock_event, mock_config)
    mock_reply_flex.assert_called_once()
    assert mock_reply_flex.call_args[0][2] == "WEEK 4 ALL-PLAY - 小謝"
    flex_w4_str = json.dumps(mock_reply_flex.call_args[0][3], ensure_ascii=False)
    assert "WEEK 4 ALL-PLAY" in flex_w4_str
    assert "⚪ 平手 (1)" in flex_w4_str
    assert "4 : 4 : 1" in flex_w4_str
    assert "⚔️ Joseph" in flex_w4_str
    assert "2 : 7" in flex_w4_str

    # 2. #比分 小謝 上週 -> 當前 W5，上週為 W4，結果相同
    mock_reply_flex.reset_mock()
    mock_event.message.text = "#比分 小謝 上週"
    handler.execute(mock_event, mock_config)
    mock_reply_flex.assert_called_once()
    assert mock_reply_flex.call_args[0][2] == "WEEK 4 ALL-PLAY - 小謝"

    # 3. #比分W5 小謝 -> 指定當前週次 W5，讀取當週最新數據
    mock_reply_flex.reset_mock()
    mock_event.message.text = "#比分W5 小謝"
    handler.execute(mock_event, mock_config)
    mock_reply_flex.assert_called_once()
    assert mock_reply_flex.call_args[0][2] == "WEEK 5 ALL-PLAY - 小謝"

    # 4. #比分 小謝 W9 -> 本地無 W9 數據，應靜默不回應
    mock_reply_flex.reset_mock()
    mock_reply_text.reset_mock()
    mock_event.message.text = "#比分 小謝 W9"
    handler.execute(mock_event, mock_config)
    mock_reply_flex.assert_not_called()
    mock_reply_text.assert_not_called()


def test_help_menu_displays_local_score_button_and_note(mocker, mock_event, mock_config):
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.stats_handler import StatsHandler
    from src.handlers.local_user_stats_handler import LocalUserStatsHandler
    from src.handlers.local_matchup_handler import LocalMatchupHandler
    from src.handlers.misc_handler import MiscHandler

    mocker.patch("src.handlers.misc_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.misc_handler.security_manager.is_whitelisted", return_value=False)

    dispatcher = CommandDispatcher()
    dispatcher.register(StatsHandler())
    dispatcher.register(LocalUserStatsHandler())
    dispatcher.register(LocalMatchupHandler())
    dispatcher.register(LocalScoreHandler())
    misc_handler = MiscHandler(dispatcher=dispatcher)
    dispatcher.register(misc_handler)

    mock_reply_flex = mocker.patch.object(misc_handler, "reply_flex")
    mock_event.message.text = "#幫助"

    misc_handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    flex_dict = mock_reply_flex.call_args[0][3]
    flex_str = json.dumps(flex_dict, ensure_ascii=False)
    assert "全聯盟比分" in flex_str
    assert "#比分" in flex_str
    assert "#比分 [暱稱]" in flex_str


def test_intent_router_semantic_mention_triggers_local_score_and_prompt_includes_rules(
    mocker, tmp_path, mock_event, mock_config
):
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.llm.prompts.intent_router_prompt import SYSTEM_PROMPT

    assert "#比分" in SYSTEM_PROMPT
    assert "會輸給哪些人" in SYSTEM_PROMPT or "全聯盟" in SYSTEM_PROMPT

    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.local_score_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch.object(LocalScoreHandler, "_load_team_mapping", return_value={"10": "小謝", "1": "韋哥"})

    dispatcher = CommandDispatcher()
    score_handler = LocalScoreHandler()
    dispatcher.register(score_handler)

    router = IntentRouter(dispatcher)
    mock_score_exec = mocker.patch.object(score_handler, "execute")

    mock_event.source = MagicMock()
    mock_event.source.type = "group"
    mock_event.source.user_id = "U_test"

    # @bot 告訴我第5週，小謝的對戰數據，會輸給哪些人 -> LLM 解析為 #比分 小謝 W5 -> 觸發 LocalScoreHandler
    mocker.patch.object(
        router.llm_agent,
        "analyze_intent",
        return_value={"is_command": True, "command_text": "#比分 小謝 W5", "reply_text": None},
    )
    mock_event.message.text = "@bot 告訴我第5週，小謝的對戰數據，會輸給哪些人"
    router.route(mock_event, mock_config)

    mock_score_exec.assert_called_once()
    assert mock_event.message.text == "#比分 小謝 W5"


def test_local_score_11_cat_and_mlb_custom_stat_categories(mocker, tmp_path, mock_event, mock_config):
    mocker.patch("src.utils.path_utils.DATA_DIR", str(tmp_path))
    mocker.patch("src.handlers.local_score_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    # 模擬 11-cat metadata（含 FGM/A、FTM/A 輔助項，以及 A/T、DD 自訂比項）
    mocker.patch(
        "src.handlers.local_score_handler.load_league_metadata",
        return_value={
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
                {"stat_id": "20", "display_name": "A/T", "sort_order": 1},
                {"stat_id": "27", "display_name": "DD", "sort_order": 1},
            ]
        },
    )
    mocker.patch.object(
        LocalScoreHandler,
        "_load_team_mapping",
        return_value={"11": "小謝", "7": "Covi", "2": "Andy"},
    )
    tw_tz = pytz.timezone("Asia/Taipei")
    mocker.patch(
        "src.handlers.local_score_handler._get_now_tw",
        return_value=tw_tz.localize(datetime(2026, 11, 23, 15, 0, 0)),
    )

    weekly_dir = tmp_path / "league" / "nba" / "123" / "weekly"
    weekly_dir.mkdir(parents=True, exist_ok=True)
    weekly_payload = {
        "league_id": "nba.l.123",
        "date": "2026-11-22",
        "week": 5,
        "matchups": [{"team1_id": "11", "team2_id": "7"}],
        "team_stats": [
            {
                "team_id": "11",
                "name": "小謝",
                "official_name": "你真的頂不住了",
                "stats": {
                    "FGM/A": "229/460",
                    "FG%": 0.498,
                    "FTM/A": "83/116",
                    "FT%": 0.716,
                    "3PTM": 63,
                    "PTS": 604,
                    "REB": 228,
                    "AST": 136,
                    "ST": 33,
                    "BLK": 31,
                    "TO": 77,
                    "A/T": 1.766,
                    "DD": 6,
                },
            },
            {
                "team_id": "7",
                "name": "Covi",
                "official_name": "字七欺人會贏喔",
                "stats": {
                    "FGM/A": "233/522",
                    "FG%": 0.446,
                    "FTM/A": "91/118",
                    "FT%": 0.771,
                    "3PTM": 66,
                    "PTS": 623,
                    "REB": 207,
                    "AST": 153,
                    "ST": 42,
                    "BLK": 24,
                    "TO": 80,
                    "A/T": 1.913,
                    "DD": 4,
                },
            },
            {
                "team_id": "2",
                "name": "Andy",
                "official_name": "Andy Team",
                "stats": {
                    "FGM/A": "286/582",
                    "FG%": 0.491,
                    "FTM/A": "131/168",
                    "FT%": 0.78,
                    "3PTM": 85,
                    "PTS": 788,
                    "REB": 213,
                    "AST": 160,
                    "ST": 51,
                    "BLK": 25,
                    "TO": 99,
                    "A/T": 1.616,
                    "DD": 4,
                },
            },
        ],
    }
    (weekly_dir / "date_2026-11-22_weekly.json").write_text(
        json.dumps(weekly_payload, ensure_ascii=False), encoding="utf-8"
    )

    handler = LocalScoreHandler()
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")
    mock_event.message.text = "#比分 小謝"

    handler.execute(mock_event, mock_config)

    mock_reply_flex.assert_called_once()
    flex_str = json.dumps(mock_reply_flex.call_args[0][3], ensure_ascii=False)
    # 11-cat 下：小謝 vs Andy 為 6 : 5 (勝)，小謝 vs Covi 為 5 : 6 (敗，當週對手)
    assert "🟢 勝場 (1)" in flex_str
    assert "6 : 5" in flex_str
    assert "🔴 敗場 (1)" in flex_str
    assert "⚔️ Covi" in flex_str
    assert "5 : 6" in flex_str



