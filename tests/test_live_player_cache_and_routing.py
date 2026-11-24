import pytest
from unittest.mock import MagicMock
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration


def test_live_player_cache_case_insensitive_read_write(tmp_path):
    from src.utils.live_player_cache import (
        DEFAULT_LIVE_CACHE_PATH,
        get_cached_live_player,
        set_cached_live_player,
        load_live_player_cache,
        save_live_player_cache,
    )

    assert DEFAULT_LIVE_CACHE_PATH == "data/live_player_mapping_cache.json"

    cache_file = str(tmp_path / "live_player_mapping_cache.json")
    assert load_live_player_cache(cache_file) == {}
    assert get_cached_live_player("LBJ", cache_file) is None

    player_data = {
        "athlete_id": "1966",
        "english_name": "LeBron James",
        "chinese_name": "勒布朗·詹姆斯",
        "team_id": "13",
        "team_abbr": "LAL",
        "team": "Los Angeles Lakers",
        "jersey_number": "23",
        "position": "SF",
    }
    set_cached_live_player("  LBJ  ", player_data, cache_file)
    set_cached_live_player("老詹", player_data, cache_file)

    assert get_cached_live_player("lbj", cache_file) == player_data
    assert get_cached_live_player("LBJ", cache_file) == player_data
    assert get_cached_live_player(" 老詹 ", cache_file) == player_data

    # Also test direct save/load
    save_live_player_cache({"sga": {"english_name": "Shai Gilgeous-Alexander"}}, cache_file)
    assert get_cached_live_player("SGA", cache_file) == {"english_name": "Shai Gilgeous-Alexander"}


def test_live_player_handler_resolves_nickname_via_cache_llm_and_espn_calibration(mocker, tmp_path):
    from src.handlers.live_player_handler import LivePlayerHandler
    from src.utils.live_player_cache import get_cached_live_player

    cache_file = str(tmp_path / "live_player_mapping_cache.json")
    mocker.patch("src.utils.live_player_cache.DEFAULT_LIVE_CACHE_PATH", cache_file)
    mocker.patch("src.handlers.live_player_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.live_player_handler.load_league_metadata", return_value={"sport": "nba"})

    handler = LivePlayerHandler()
    mock_reply_text = mocker.patch.object(handler, "reply_text")
    mock_reply_flex = mocker.patch.object(handler, "reply_flex")

    # Simulate mid-season trade: LLM still thinks Luka Doncic is on Dallas Mavericks (#77),
    # while ESPN Search API returns his latest active NBA team (LAL, team_id=13, #77, PG).
    mock_llm_cls = mocker.patch("src.handlers.live_player_handler.LLMAgent")
    mock_llm_instance = mock_llm_cls.return_value
    mock_llm_instance.player_fuzzy_search.return_value = {
        "is_known_player": True,
        "english_name": "Luka Doncic",
        "chinese_name": "盧卡·唐西奇",
        "team": "Dallas Mavericks",
        "jersey_number": "77",
    }

    mock_search = mocker.patch.object(
        handler.fetcher,
        "search_player",
        return_value={
            "athlete_id": "3945274",
            "english_name": "Luka Doncic",
            "team_id": "13",
            "team_abbr": "LAL",
            "team_name": "Los Angeles Lakers",
            "jersey_number": "77",
            "position": "PG",
        },
    )
    mock_fetch_game = mocker.patch.object(
        handler.fetcher,
        "fetch_player_live_or_latest_game",
        return_value={
            "event_id": "401704999",
            "game_date": "2026-11-24",
            "game_state": "in",
            "status_label": "🔴 LIVE • Q4 02:10",
            "score_text": "LAL 110 : 104 DEN",
            "minutes": "36",
            "stats": {
                "MIN": "36",
                "FGM/A": "11/22",
                "FG%": "50.0%",
                "FTM/A": "6/7",
                "FT%": "85.7%",
                "3PT": "4",
                "PTS": "32",
                "REB": "9",
                "AST": "10",
                "ST": "2",
                "BLK": "0",
                "TO": "3",
            },
            "notice_banner": None,
        },
    )

    event = MagicMock(spec=MessageEvent)
    event.message = MagicMock()
    event.reply_token = "test_token"
    config = MagicMock(spec=Configuration)

    # 1. Cache Miss -> calls LLM fuzzy search + ESPN search calibration -> saves to cache
    event.message.text = "#球員 東77"
    handler.execute(event, config)

    mock_llm_instance.player_fuzzy_search.assert_called_once_with("東77", sport="nba")
    mock_search.assert_called_once_with("Luka Doncic")
    mock_reply_flex.assert_called_once()
    flex_bubble = mock_reply_flex.call_args[0][3]
    header_contents = flex_bubble["body"]["contents"][0]["contents"]
    assert header_contents[0]["text"] == "Luka Doncic"
    assert header_contents[1]["text"] == "盧卡·唐西奇 ｜ LAL #77 • PG"

    # Verify cache saved with calibrated team_abbr='LAL' and team_id='13'
    cached = get_cached_live_player("東77", cache_file)
    assert cached is not None
    assert cached["athlete_id"] == "3945274"
    assert cached["english_name"] == "Luka Doncic"
    assert cached["chinese_name"] == "盧卡·唐西奇"
    assert cached["team_id"] == "13"
    assert cached["team_abbr"] == "LAL"
    assert cached["team"] == "Los Angeles Lakers"
    assert cached["jersey_number"] == "77"
    assert cached["position"] == "PG"

    # 2. Cache Hit -> does NOT call LLM or ESPN search_player again
    mock_llm_instance.player_fuzzy_search.reset_mock()
    mock_search.reset_mock()
    mock_reply_flex.reset_mock()

    event.message.text = "#球員 東77"
    handler.execute(event, config)
    mock_llm_instance.player_fuzzy_search.assert_not_called()
    mock_search.assert_not_called()
    mock_reply_flex.assert_called_once()

    # 3. Unknown / retired player -> replies friendly error message
    mock_reply_text.reset_mock()
    mock_llm_instance.player_fuzzy_search.return_value = {
        "is_known_player": False,
        "english_name": None,
    }
    mock_search.return_value = None

    event.message.text = "#球員 櫻木花道"
    handler.execute(event, config)
    mock_reply_text.assert_called_once_with(
        event,
        config,
        "找不到現役 NBA 球員「櫻木花道」，請嘗試輸入更清晰的名字或別稱。",
    )


def test_prompts_and_intent_router_distinguish_league_manager_vs_real_player(mocker, tmp_path):
    from src.llm.prompts.intent_router_prompt import SYSTEM_PROMPT
    from src.llm.prompts.player_fuzzy_search import get_system_prompt
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.intent_router import IntentRouter
    from src.handlers.live_player_handler import LivePlayerHandler

    # 1. Verify intent_router_prompt explicitly distinguishes 聯賽玩家 vs 真實球員
    assert "聯賽玩家" in SYSTEM_PROMPT
    assert "真實球員" in SYSTEM_PROMPT
    assert "#球員" in SYSTEM_PROMPT
    assert "#球員昨晚" in SYSTEM_PROMPT

    # 2. Verify player_fuzzy_search prompt includes rich Taiwan/PTT NBA nickname mappings
    nba_prompt = get_system_prompt("nba")
    for nickname in [
        "老詹", "喇叭詹", "LBJ", "咖哩", "柯瑞", "斑馬", "Wemby",
        "小丑", "阿肥", "77", "東77", "SGA", "鴨梨", "蟻人", "AE",
        "書人", "字母哥", "KD", "死神", "AD", "濃眉", "大鬍子", "登哥",
        "龜龜", "威少", "吉巴", "士官長", "嘴綠", "胖虎", "照相機", "Toumani Camara",
    ]:
        assert nickname in nba_prompt, f"Missing nickname {nickname} in player_fuzzy_search prompt"

    # 3. Verify IntentRouter routes natural language real-world player query to LivePlayerHandler
    cache_file = str(tmp_path / "live_player_mapping_cache.json")
    mocker.patch("src.utils.live_player_cache.DEFAULT_LIVE_CACHE_PATH", cache_file)
    mocker.patch("src.config.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.intent_router.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.live_player_handler.load_config", return_value={"LEAGUE_ID": "nba.l.123"})
    mocker.patch("src.handlers.live_player_handler.load_league_metadata", return_value={"sport": "nba"})

    dispatcher = CommandDispatcher()
    live_handler = LivePlayerHandler()
    dispatcher.register(live_handler)
    router = IntentRouter(dispatcher)

    mocker.patch.object(
        router.llm_agent,
        "analyze_intent",
        return_value={"is_command": True, "command_text": "#球員 LeBron James", "reply_text": None},
    )
    mock_execute = mocker.patch.object(live_handler, "execute")

    event = MagicMock(spec=MessageEvent)
    event.reply_token = "tok_1"
    event.source = MagicMock()
    event.source.type = "user"
    event.source.user_id = "U123456"
    event.message = MagicMock()
    event.message.text = "老詹今天拿幾分"
    event.message.mention = None
    config = MagicMock(spec=Configuration)

    router.route(event, config)
    assert event.message.text == "#球員 LeBron James"
    mock_execute.assert_called_once_with(event, config)

    # 4. Fallback verification: when user inputs "泳池" and LLM mistakenly outputs "#玩家 泳池",
    # IntentRouter detects "泳池" is NOT in team_mapping ("喇叭", "小謝") and auto-converts it to "#球員 泳池"
    from src.handlers.local_user_stats_handler import LocalUserStatsHandler
    user_handler = LocalUserStatsHandler()
    dispatcher.register(user_handler)

    mocker.patch.object(router, "_load_team_mapping", return_value={"1": "喇叭", "2": "小謝"})
    mocker.patch.object(user_handler, "_load_team_mapping", return_value={"1": "喇叭", "2": "小謝"})
    mocker.patch.object(user_handler, "_load_default_local_daily_data", return_value=(None, None))
    mock_user_exec = mocker.patch.object(user_handler, "execute")
    mock_execute.reset_mock()

    mocker.patch.object(
        router.llm_agent,
        "analyze_intent",
        return_value={"is_command": True, "command_text": "#玩家 泳池", "reply_text": None},
    )
    event.message.text = "泳池"
    router.route(event, config)
    assert event.message.text == "#球員 泳池"
    mock_execute.assert_called_once_with(event, config)
    mock_user_exec.assert_not_called()

    # 5. Name collision verification: when user inputs "喇叭" (which exists in team_mapping AND is a player nickname),
    # league manager takes precedence -> stays "#玩家 喇叭" and dispatches to LocalUserStatsHandler
    mock_execute.reset_mock()
    mock_user_exec.reset_mock()
    mocker.patch.object(
        router.llm_agent,
        "analyze_intent",
        return_value={"is_command": True, "command_text": "#玩家 喇叭", "reply_text": None},
    )
    event.message.text = "喇叭"
    router.route(event, config)
    assert event.message.text == "#玩家 喇叭"
    mock_user_exec.assert_called_once_with(event, config)
    mock_execute.assert_not_called()


def test_help_menu_and_bot_registration_include_live_player_command(mocker):
    from src.handlers.dispatcher import CommandDispatcher
    from src.handlers.misc_handler import MiscHandler
    from src.handlers.local_user_stats_handler import LocalUserStatsHandler
    from src.handlers.local_matchup_handler import LocalMatchupHandler
    from src.handlers.local_score_handler import LocalScoreHandler
    from src.handlers.live_player_handler import LivePlayerHandler
    import bot

    # 1. Verify bot.dispatcher has LivePlayerHandler registered (and PlayerHandler not registered)
    assert bot.dispatcher.is_command_registered("#球員 老詹") is True
    assert any(isinstance(h, LivePlayerHandler) for h in bot.dispatcher._handlers)

    # 2. Verify MiscHandler dynamically includes '、#球員 [姓名]' when LivePlayerHandler is registered
    mocker.patch("src.handlers.misc_handler.load_config", return_value={"LEAGUE_ID": "nba.l.12345"})
    mocker.patch("src.handlers.misc_handler.load_league_metadata", return_value={"end_date": "2026-04-12"})
    mocker.patch("src.handlers.misc_handler.get_pacific_date", return_value="2026-05-29")
    mocker.patch("src.handlers.misc_handler.security_manager.is_whitelisted", return_value=False)

    dispatcher = CommandDispatcher()
    misc_handler = MiscHandler()
    dispatcher.register(misc_handler)
    dispatcher.register(LocalMatchupHandler())
    dispatcher.register(LocalScoreHandler())
    dispatcher.register(LocalUserStatsHandler())
    dispatcher.register(LivePlayerHandler())

    event = MagicMock(spec=MessageEvent)
    event.reply_token = "help_tok"
    event.source = MagicMock()
    event.source.user_id = "user_regular"
    event.message = MagicMock()
    event.message.text = "#幫助"
    config = MagicMock(spec=Configuration)

    mock_reply_flex = mocker.patch.object(misc_handler, "reply_flex")
    misc_handler.execute(event, config)

    mock_reply_flex.assert_called_once()
    carousel = mock_reply_flex.call_args[0][3]
    players_bubble = next(
        b for b in carousel["contents"]
        if "玩家與對戰" in str(b)
    )
    note_item = next(
        item for item in players_bubble["body"]["contents"]
        if item.get("type") == "text" and "支援點擊選單或輸入" in item.get("text", "")
    )
    assert note_item["text"] == "支援點擊選單或輸入 #對戰 [暱稱]、#比分 [暱稱]、#玩家 [暱稱]、#球員 [姓名]"


