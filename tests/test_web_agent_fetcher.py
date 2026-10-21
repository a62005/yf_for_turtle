import os
import json
import pytest
from unittest.mock import MagicMock, patch
from src.web_agent_fetcher import (
    WebAgentFetcher,
    LeagueWebAuthError,
    build_league_url,
    clean_old_images,
    run_web_agent_push,
)
from src.handlers.set_league_id_handler import SetLeagueIdHandler
from src.web_login_bridge import bind_web_login_to_set_league_handler
from src.config import current_chat_id


def test_build_league_url_nba_and_mlb():
    sport, raw_id, url = build_league_url("nba.l.49432")
    assert sport == "nba"
    assert raw_id == "49432"
    assert url == "https://basketball.fantasysports.yahoo.com/nba/49432"

    sport_m, raw_id_m, url_m = build_league_url("mlb.l.62358")
    assert sport_m == "mlb"
    assert raw_id_m == "62358"
    assert url_m == "https://baseball.fantasysports.yahoo.com/b1/62358"


def test_normalize_team_list_maps_names_and_strips_participation_and_normalizes_pct():
    fetcher = WebAgentFetcher(
        team_mapping={"1": "自訂隊名A"},
        league_id="nba.l.49432",
        api_key="dummy_key"
    )
    raw_list = [
        {
            "team_id": "1",
            "name": "Original A",
            "stats": {
                "FGM/FGA": "40/80",
                "FG%": "50.0%",
                "FTM/FTA": "15/20",
                "FT%": 75.0,
                "3PTM": 10,
                "PTS": 105,
                "REB": 42,
                "AST": 25,
                "STL": 8,
                "BLK": 4,
                "TO": 12,
                "Today Player": 5,
                "GP_PLAYED": 20,
                "GP_TOTAL": 40
            }
        }
    ]
    normalized = fetcher._normalize_team_list(raw_list, is_daily=True)
    assert len(normalized) == 1
    team = normalized[0]
    assert team["name"] == "自訂隊名A"
    assert team["stats"]["FGM/A"] == "40/80"
    assert team["stats"]["FTM/A"] == "15/20"
    assert team["stats"]["3PT"] == 10
    assert team["stats"]["ST"] == 8
    assert team["stats"]["FG%"] == pytest.approx(0.50)
    assert team["stats"]["FT%"] == pytest.approx(0.75)
    assert team["stats"]["Today Player"] == 5
    assert "Game Player" not in team["stats"]
    assert "GP_PLAYED" not in team["stats"]

    # 驗證 is_daily=False (當週戰績) 僅包含 Game Player，不包含 Today Player
    weekly_raw = [
        {
            "team_id": "1",
            "name": "Original A",
            "stats": {
                "PTS": 500,
                "Today Player": 5,
                "Game Player": "20 / 40"
            }
        }
    ]
    weekly_normalized = fetcher._normalize_team_list(weekly_raw, is_daily=False)
    w_team = weekly_normalized[0]
    assert "Today Player" not in w_team["stats"]
    assert w_team["stats"]["Game Player"] == "20 / 40"


def test_clean_old_images_removes_only_png(tmp_path):
    old_png = tmp_path / "2026-10-19_combined.png"
    old_png.write_bytes(b"fake_png")
    other_file = tmp_path / "keep.txt"
    other_file.write_text("keep")

    clean_old_images(str(tmp_path))

    assert not old_png.exists()
    assert other_file.exists()


@patch("src.web_agent_fetcher.capture_html_to_png")
@patch("src.web_agent_fetcher.render_stats_html", return_value="<html></html>")
@patch("src.web_agent_fetcher.process_stats_for_visual", return_value=[{"label": "PTS", "rows": []}])
@patch("src.web_agent_fetcher.WebAgentFetcher.fetch_daily_and_weekly_stats")
@patch("linebot.v3.messaging.ApiClient")
@patch("linebot.v3.messaging.MessagingApi")
def test_run_web_agent_push_no_json_saved_and_pushes_image(
    mock_messaging_api,
    mock_api_client,
    mock_fetch,
    mock_process,
    mock_render,
    mock_capture,
    tmp_path
):
    mock_fetch.return_value = (
        {"team_stats": [{"team_id": "1", "name": "Team 1", "stats": {"PTS": 100}}]},
        {"team_stats": [{"team_id": "1", "name": "Team 1", "stats": {"PTS": 500}}]}
    )
    img_dir = tmp_path / "league" / "nba" / "12345" / "image"
    img_dir.mkdir(parents=True)
    stale_img = img_dir / "2026-10-01_combined.png"
    stale_img.write_bytes(b"old")

    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.web_agent_fetcher.load_config", return_value={
             "LEAGUE_ID": "nba.l.12345",
             "LINE_CHANNEL_ACCESS_TOKEN": "token_123",
             "SERVER_URL": "https://example.ngrok.app",
             "LLM_API_KEY": "key_123",
             "LLM_MODEL": "gemini-2.5-flash"
         }):
        run_web_agent_push(league_id="nba.l.12345", reply_to="C_group_1", target_date="2026-10-20")

    assert not stale_img.exists()
    mock_capture.assert_called_once()
    captured_path = mock_capture.call_args[0][1]
    assert captured_path.endswith("2026-10-20_combined.png")
    assert not (tmp_path / "league" / "nba" / "12345" / "daily").exists()
    assert not (tmp_path / "league" / "nba" / "12345" / "weekly").exists()

    mock_messaging_api.return_value.push_message.assert_called_once()
    push_req = mock_messaging_api.return_value.push_message.call_args[0][0]
    assert push_req.to == "C_group_1"
    assert push_req.messages[0].original_content_url == "https://example.ngrok.app/images/nba/12345/2026-10-20_combined.png"


@patch("src.web_agent_fetcher.capture_html_to_png")
@patch("src.web_agent_fetcher.WebAgentFetcher.fetch_daily_and_weekly_stats")
@patch("linebot.v3.messaging.ApiClient")
@patch("linebot.v3.messaging.MessagingApi")
def test_run_web_agent_push_unauthenticated_sends_login_url_without_fake_image(
    mock_messaging_api,
    mock_api_client,
    mock_fetch,
    mock_capture,
    tmp_path
):
    mock_fetch.side_effect = LeagueWebAuthError("尚未登入或無檢視權限")

    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.web_agent_fetcher.load_config", return_value={
             "LEAGUE_ID": "nba.l.49432",
             "LINE_CHANNEL_ACCESS_TOKEN": "token_123",
             "SERVER_URL": "https://example.ngrok.app",
             "LLM_API_KEY": "key_123"
         }), \
         patch("src.web_login_bridge.load_config", return_value={
             "SERVER_URL": "https://example.ngrok.app"
         }):
        run_web_agent_push(league_id="nba.l.49432", reply_to="C_group_49432", target_date="2026-10-20")

    # 絕不生成假圖片
    mock_capture.assert_not_called()
    # 改推播手機登入網址給群組
    mock_messaging_api.return_value.push_message.assert_called_once()
    push_req = mock_messaging_api.return_value.push_message.call_args[0][0]
    assert push_req.to == "C_group_49432"
    assert "https://example.ngrok.app/yahoo/web-login?league_id=nba.l.49432&chat_id=C_group_49432" in push_req.messages[0].text


def test_set_league_id_handler_with_web_login_provides_login_url_when_not_logged_in(tmp_path):
    handler = bind_web_login_to_set_league_handler(SetLeagueIdHandler())
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置聯盟ID 49432"
    event.source.user_id = "U_manager_1"
    config = MagicMock()

    token = current_chat_id.set("C_group_test")
    try:
        with patch("src.web_login_bridge.DATA_DIR", str(tmp_path)), \
             patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
             patch("src.web_login_bridge.verify_league_web_access", return_value=(False, {})), \
             patch("src.web_login_bridge.load_config", return_value={"SERVER_URL": "https://my-bot.ngrok.app"}), \
             patch("src.utils.security.security_manager._load_json", return_value={}), \
             patch("src.utils.security.security_manager.set_league_owner"), \
             patch("src.utils.security.security_manager.set_league_authorized"):
            handler.execute(event, config)

        handler.reply_text.assert_called_once()
        reply_msg = handler.reply_text.call_args[0][2]
        assert "nba.l.49432" in reply_msg
        assert "https://my-bot.ngrok.app/yahoo/web-login?league_id=nba.l.49432&chat_id=C_group_test" in reply_msg
    finally:
        current_chat_id.reset(token)


def test_set_league_id_handler_with_web_login_binds_immediately_when_already_logged_in(tmp_path):
    handler = bind_web_login_to_set_league_handler(SetLeagueIdHandler())
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置聯盟ID 49432"
    event.source.user_id = "U_manager_1"
    config = MagicMock()

    token = current_chat_id.set("C_group_test")
    try:
        with patch("src.web_login_bridge.DATA_DIR", str(tmp_path)), \
             patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
             patch("src.web_login_bridge.verify_league_web_access", return_value=(True, {"1": "Team Alpha", "2": "Team Beta"})), \
             patch("src.utils.security.security_manager._load_json", return_value={}), \
             patch("src.utils.security.security_manager.set_league_owner"), \
             patch("src.utils.security.security_manager.set_league_authorized") as mock_auth:
            handler.execute(event, config)

        mock_auth.assert_called_with("nba.l.49432", True)
        handler.reply_text.assert_called_once_with(
            event, config, "✅ 成功將此聊天室綁定至聯賽 ID：nba.l.49432"
        )
    finally:
        current_chat_id.reset(token)


def test_web_login_blueprint_routes():
    import bot
    client = bot.app.test_client()

    with patch("src.web_login_bridge.get_or_create_login_worker") as mock_get_worker:
        mock_worker = MagicMock()
        mock_worker.execute_action.return_value = {
            "authorized": False,
            "url": "https://login.yahoo.com",
            "status": "尚在 Yahoo 登入頁面",
            "image_b64": "ZmFrZQ=="
        }
        mock_get_worker.return_value = mock_worker

        resp = client.get("/yahoo/web-login?league_id=nba.l.49432&chat_id=C_group_1")
        assert resp.status_code == 200
        assert "nba.l.49432" in resp.get_data(as_text=True)

        act_resp = client.post(
            "/yahoo/web-login/action",
            json={"league_id": "nba.l.49432", "chat_id": "C_group_1", "action": "snapshot"}
        )
        assert act_resp.status_code == 200
        assert act_resp.get_json()["authorized"] is False


def test_inspect_yahoo_login_stage_detects_username_password_and_otp():
    from playwright.sync_api import sync_playwright
    from src.web_login_bridge import inspect_yahoo_login_stage

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        try:
            page = browser.new_page()

            # 1. Username step
            page.set_content('<html><body><input id="login-username" type="text" style="width:200px;height:40px;" /></body></html>')
            s1 = inspect_yahoo_login_stage(page)
            assert s1["stage"] == "username"

            # 2. Password step (even when hidden username input still exists in DOM)
            page.set_content(
                '<html><body>'
                '<input id="login-username" type="text" style="display:none;" />'
                '<input id="login-passwd" type="password" style="width:200px;height:40px;" />'
                '</body></html>'
            )
            s2 = inspect_yahoo_login_stage(page)
            assert s2["stage"] == "password"
            assert s2["input_type"] == "password"

            # 3. OTP step
            page.set_content(
                '<html><body>'
                '<div class="challenge-desc" style="width:200px;height:30px;">已傳送驗證碼至 0912***</div>'
                '<input id="verification-code-field" type="text" style="width:200px;height:40px;" />'
                '</body></html>'
            )
            s3 = inspect_yahoo_login_stage(page)
            assert s3["stage"] == "otp"
        finally:
            browser.close()


def test_default_agent_model_is_gemini_3_5_flash():
    from src.web_agent_fetcher import DEFAULT_AGENT_MODEL
    fetcher = WebAgentFetcher(league_id="nba.l.49432", api_key="dummy")
    assert DEFAULT_AGENT_MODEL == "gemini-3.5-flash"
    assert fetcher.model_name == "gemini-3.5-flash"


def test_already_set_league_id_skips_relogin_when_state_and_mapping_exist(tmp_path):
    league_dir = tmp_path / "league" / "nba" / "49432"
    league_dir.mkdir(parents=True)
    (league_dir / "yahoo_web_state.json").write_text('{"cookies": []}', encoding="utf-8")
    (league_dir / "team_mapping.json").write_text(
        json.dumps({"1": "隊伍一", "2": "隊伍二"}, ensure_ascii=False),
        encoding="utf-8"
    )

    handler = bind_web_login_to_set_league_handler(SetLeagueIdHandler())
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置聯盟ID 49432"
    event.source.user_id = "U_manager_1"
    config = MagicMock()

    token = current_chat_id.set("C_group_test")
    try:
        with patch("src.web_login_bridge.DATA_DIR", str(tmp_path)), \
             patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
             patch("src.web_login_bridge.verify_league_web_access") as mock_verify, \
             patch("src.utils.security.security_manager._load_json", return_value={}), \
             patch("src.utils.security.security_manager.set_league_owner"), \
             patch("src.utils.security.security_manager.set_league_authorized"):
            handler.execute(event, config)

        # 已設置過且已有 yahoo_web_state.json 與 team_mapping.json，不需再次觸發瀏覽器登入驗證
        mock_verify.assert_not_called()
        handler.reply_text.assert_called_once_with(
            event, config, "✅ 成功將此聊天室綁定至聯賽 ID：nba.l.49432"
        )
    finally:
        current_chat_id.reset(token)


def test_set_league_id_without_mapping_uses_agent_to_populate_team_mapping(tmp_path):
    from src.web_login_bridge import save_discovered_team_mapping

    with patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
         patch("src.web_agent_fetcher.WebAgentFetcher.fetch_team_mapping_via_agent", return_value={"1": "AI擷取隊伍A", "2": "AI擷取隊伍B"}):
        result = save_discovered_team_mapping("nba.l.49432")

    assert result == {"1": "AI擷取隊伍A", "2": "AI擷取隊伍B"}
    mapping_file = tmp_path / "league" / "nba" / "49432" / "team_mapping.json"
    assert mapping_file.exists()
    saved = json.loads(mapping_file.read_text(encoding="utf-8"))
    assert saved["1"] == "AI擷取隊伍A"


def test_set_league_id_when_login_expired_prompts_user_to_relogin(tmp_path):
    league_dir = tmp_path / "league" / "nba" / "49432"
    league_dir.mkdir(parents=True)
    # 有舊的登入檔，但沒有 team_mapping 且登入已失效
    (league_dir / "yahoo_web_state.json").write_text('{"cookies": []}', encoding="utf-8")

    handler = bind_web_login_to_set_league_handler(SetLeagueIdHandler())
    handler.reply_text = MagicMock()

    event = MagicMock()
    event.message.text = "#設置聯盟ID 49432"
    event.source.user_id = "U_manager_1"
    config = MagicMock()

    token = current_chat_id.set("C_group_test")
    try:
        with patch("src.web_login_bridge.DATA_DIR", str(tmp_path)), \
             patch("src.utils.path_utils.DATA_DIR", str(tmp_path)), \
             patch("src.web_login_bridge.verify_league_web_access", return_value=(False, {})), \
             patch("src.web_login_bridge.load_config", return_value={"SERVER_URL": "https://my-bot.ngrok.app"}), \
             patch("src.utils.security.security_manager._load_json", return_value={}), \
             patch("src.utils.security.security_manager.set_league_owner"), \
             patch("src.utils.security.security_manager.set_league_authorized"):
            handler.execute(event, config)

        handler.reply_text.assert_called_once()
        reply_msg = handler.reply_text.call_args[0][2]
        assert "登入狀態已失效" in reply_msg
        assert "重新登入" in reply_msg
        assert "https://my-bot.ngrok.app/yahoo/web-login?league_id=nba.l.49432&chat_id=C_group_test" in reply_msg
    finally:
        current_chat_id.reset(token)
