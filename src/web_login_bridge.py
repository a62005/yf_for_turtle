import os
import time
import json
import queue
import shutil
import base64
import logging
import threading
from unittest.mock import patch, MagicMock
from urllib.parse import quote
from flask import Blueprint, request, jsonify, Response
from playwright.sync_api import sync_playwright
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage

from src.config import load_config, current_chat_id
from src.fetcher import LeaguePermissionError
from src.utils.path_utils import DATA_DIR, get_league_dir, get_league_team_mapping_path, parse_league_id
from src.utils.security import security_manager

web_login_bp = Blueprint("web_login_bp", __name__)


def get_league_storage_state_path(league_id: str) -> str:
    """回傳該聯盟專屬的 Playwright 網頁登入狀態檔路徑 (含 yahoo 字樣以相容清理保留規則)。"""
    league_dir = get_league_dir(league_id)
    os.makedirs(league_dir, exist_ok=True)
    return os.path.join(league_dir, "yahoo_web_state.json")


def build_league_web_url(league_id: str) -> tuple[str, str, str]:
    """根據 league_id 回傳 (sport, raw_id, url)。"""
    sport, raw_id = parse_league_id(league_id)
    if sport == "mlb":
        return "mlb", raw_id, f"https://baseball.fantasysports.yahoo.com/b1/{raw_id}"
    return "nba", raw_id, f"https://basketball.fantasysports.yahoo.com/nba/{raw_id}"


def build_mobile_web_login_url(league_id: str, chat_id: str = None) -> str:
    """組合供手機端開啟的遠端 Yahoo 網頁登入網址。"""
    config = load_config()
    server_url = os.environ.get("SERVER_URL") or config.get("SERVER_URL") or "http://localhost:5001"
    https_url = server_url.replace("http://", "https://").rstrip("/")
    if not https_url.startswith("https://"):
        https_url = f"https://{https_url.lstrip('https://')}"
    cid = chat_id or current_chat_id.get() or "default"
    return f"{https_url}/yahoo/web-login?league_id={quote(str(league_id))}&chat_id={quote(str(cid))}"


def extract_teams_and_check_auth(page, league_id: str) -> tuple[bool, str, dict[str, str]]:
    """檢查當前 Playwright page 是否已登入且具備檢視指定聯盟的權限，同時擷取隊伍 ID 與名稱對照表。"""
    current_url = page.url or ""
    if "login.yahoo.com" in current_url:
        return False, "尚在 Yahoo 登入頁面", {}

    sport, raw_id, _ = build_league_web_url(league_id)
    sport_slug = "b1" if sport == "mlb" else "nba"

    try:
        check_result = page.evaluate(
            """({ sportSlug, rawId }) => {
                const bodyText = (document.body && document.body.innerText) ? document.body.innerText : '';
                if (
                    bodyText.includes('You are not allowed to view this page') ||
                    bodyText.includes('you are not in this league') ||
                    bodyText.includes('Error #152') ||
                    bodyText.includes('Please sign in')
                ) {
                    return { ok: false, reason: '無此聯盟檢視權限或尚未登入 (Error #152)', teams: {} };
                }

                const teamRegex = new RegExp(`/${sportSlug}/${rawId}/(\\\\d+)$`);
                const teams = {};
                for (const a of Array.from(document.querySelectorAll('a[href]'))) {
                    try {
                        const u = new URL(a.href, window.location.origin);
                        const m = u.pathname.match(teamRegex);
                        if (m && !u.search) {
                            const tid = m[1];
                            const name = a.innerText.trim();
                            if (name && name.toLowerCase() !== 'my team' && !teams[tid]) {
                                teams[tid] = name;
                            }
                        }
                    } catch (e) {}
                }
                const count = Object.keys(teams).length;
                if (count >= 2) {
                    return { ok: true, reason: `已成功讀取 ${count} 支隊伍連結`, teams };
                }
                return { ok: false, reason: '頁面上尚未偵測到聯盟隊伍資料', teams: {} };
            }""",
            {"sportSlug": sport_slug, "rawId": raw_id}
        )
        return (
            bool(check_result.get("ok")),
            str(check_result.get("reason", "")),
            dict(check_result.get("teams") or {})
        )
    except Exception as e:
        return False, f"頁面檢查異常: {e}", {}


def is_page_authorized_for_league(page, league_id: str) -> tuple[bool, str]:
    """檢查當前 Playwright page 是否已登入且具備檢視指定聯盟的權限。"""
    ok, reason, _ = extract_teams_and_check_auth(page, league_id)
    return ok, reason


def save_discovered_team_mapping(league_id: str, teams: dict[str, str] = None, page=None) -> dict[str, str]:
    """若該聯盟尚未有 team_mapping.json 或內容為空，則優先使用 AI Agent 瀏覽網頁獲取隊伍清單並更新 team_mapping.json。"""
    mapping_path = get_league_team_mapping_path(league_id)
    existing = {}
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    if existing and isinstance(existing, dict) and len(existing) >= 2:
        return existing

    # 使用 AI Agent 瀏覽網頁並解析更新 team_mapping.json
    try:
        from src.web_agent_fetcher import WebAgentFetcher
        fetcher = WebAgentFetcher(league_id=league_id)
        agent_teams = fetcher.ensure_team_mapping_via_agent(league_id=league_id, page=page)
        if agent_teams and len(agent_teams) >= 2:
            return agent_teams
    except Exception as e:
        logging.warning(f"[WEB_LOGIN] AI Agent 自動獲取 team_mapping 失敗，改用備援隊伍清單: {e}")

    if teams:
        os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(teams, f, ensure_ascii=False, indent=2)
        return teams
    return {}


def verify_league_web_access(league_id: str, headless: bool = True) -> tuple[bool, dict[str, str]]:
    """使用已保存的 yahoo_web_state.json 測試是否能成功進入聯盟頁面並看到隊伍，回傳 (ok, teams_dict)。"""
    state_path = get_league_storage_state_path(league_id)
    if not os.path.exists(state_path):
        return False, {}

    _, _, target_url = build_league_web_url(league_id)
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=headless)
            try:
                context = browser.new_context(
                    storage_state=state_path,
                    viewport={"width": 1280, "height": 900}
                )
                page = context.new_page()
                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                page.wait_for_timeout(1500)
                ok, _, teams = extract_teams_and_check_auth(page, league_id)
                if ok:
                    context.storage_state(path=state_path)
                    final_teams = save_discovered_team_mapping(league_id, teams, page=page)
                    return True, final_teams or teams
                return False, {}
            finally:
                browser.close()
    except Exception as e:
        logging.warning(f"[WEB_LOGIN] 驗證聯盟 {league_id} 網頁權限失敗: {e}")
        return False, {}


def bind_web_login_to_set_league_handler(handler):
    """
    在不修改 src/handlers/set_league_id_handler.py 原始碼的前提下，
    將 bot.py 中註冊的 SetLeagueIdHandler 實例之 API 驗證替換為「網頁登入狀態驗證」：
    1. 已設置過且已有 yahoo_web_state.json 的聯盟 ID 不需再次登入。
    2. 若無 team_mapping.json (或為空)，自動透過 AI Agent 瀏覽網頁獲取並更新 team_mapping.json。
    3. 若尚未登入或登入已失效導致獲取資料失敗，主動提示使用者點擊連結重新登入。
    """
    raw_execute = type(handler).execute.__get__(handler, type(handler))
    real_exists = os.path.exists

    def web_os_path_exists(path):
        p_str = str(path)
        if p_str.endswith(".yahoofantasy") or p_str.endswith("oauth2.json"):
            return False
        return real_exists(path)

    def _load_existing_mapping(lid: str) -> dict:
        m_path = get_league_team_mapping_path(lid)
        if real_exists(m_path):
            try:
                with open(m_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        return {}

    def web_wrapped_execute(event, configuration):
        user_id = getattr(event.source, "user_id", None)
        discovered_teams_holder = {}
        verified_state = {"target_id": None, "ok": False, "had_state": False}

        def web_sync_season_metadata(_fetcher, target_id):
            verified_state["target_id"] = target_id
            state_path = get_league_storage_state_path(target_id)
            if user_id and not real_exists(state_path):
                roles = security_manager._load_json(security_manager.league_roles_path, {})
                for prev_lid, ldata in roles.items():
                    if isinstance(ldata, dict) and ldata.get("manager") == user_id and prev_lid != target_id:
                        prev_state = get_league_storage_state_path(prev_lid)
                        if real_exists(prev_state):
                            try:
                                shutil.copy2(prev_state, state_path)
                                break
                            except Exception:
                                pass

            has_state = real_exists(state_path)
            verified_state["had_state"] = has_state
            existing_map = _load_existing_mapping(target_id)

            # 已設置過且已有登入狀態與 team_mapping 的聯盟 ID，直接免除二次驗證與登入
            if has_state and len(existing_map) >= 2:
                verified_state["ok"] = True
                discovered_teams_holder.update(existing_map)
                return

            res = verify_league_web_access(target_id)
            if isinstance(res, tuple):
                ok, teams = res
            else:
                ok, teams = bool(res), {}
            if not ok:
                raise LeaguePermissionError(f"Web login required or expired for {target_id}")
            verified_state["ok"] = True
            if teams:
                discovered_teams_holder.update(teams)

        def fake_league_factory(_ctx, _norm_id):
            mock_league = MagicMock()
            team_objs = []
            for tid, tname in discovered_teams_holder.items():
                t = MagicMock()
                t.team_id = tid
                t.name = tname
                team_objs.append(t)
            mock_league.teams.return_value = team_objs
            return mock_league

        try:
            with patch("src.handlers.set_league_id_handler.os.path.exists", side_effect=web_os_path_exists), \
                 patch("src.handlers.set_league_id_handler.YahooFantasyFetcher") as mock_fetcher_cls, \
                 patch("src.handlers.set_league_id_handler.sync_season_metadata", side_effect=web_sync_season_metadata), \
                 patch("yahoofantasy.League", side_effect=fake_league_factory):
                mock_fetcher_cls.return_value._normalize_league_id.side_effect = lambda x: x
                raw_execute(event, configuration)
            if verified_state["ok"] and verified_state["target_id"]:
                tid = verified_state["target_id"]
                security_manager.set_league_authorized(tid, True)
                # 確保設置完聯盟 ID 後，若 team_mapping 仍為空，使用 AI Agent 或已探索之隊伍寫入 team_mapping.json
                cur_map = _load_existing_mapping(tid)
                if len(cur_map) < 2:
                    save_discovered_team_mapping(tid, discovered_teams_holder)
        except Exception as e:
            if isinstance(e, LeaguePermissionError) or e.__class__.__name__ == "LeaguePermissionError":
                chat_id = current_chat_id.get() or "default"
                bound_league_id = verified_state["target_id"]
                if not bound_league_id:
                    mapping_path = os.path.join(DATA_DIR, "security", "chat_league_mapping.json")
                    if real_exists(mapping_path):
                        try:
                            with open(mapping_path, "r", encoding="utf-8") as f:
                                mapping = json.load(f)
                                bound_league_id = mapping.get(str(chat_id))
                        except Exception:
                            pass
                if bound_league_id:
                    security_manager.set_league_authorized(bound_league_id, False)
                login_url = build_mobile_web_login_url(bound_league_id or "", chat_id)
                if verified_state.get("had_state"):
                    msg = (
                        "⚠️ 獲取聯盟資料失敗：Yahoo 網頁登入狀態已失效或無存取權限。\n"
                        "請點擊以下連結於手機重新登入 Yahoo 帳號：\n"
                        f"👉 {login_url}"
                    )
                else:
                    msg = (
                        "⚠️ 機器人目前尚未具備此聯盟的網頁存取權限。\n"
                        "請點擊以下連結於手機登入 Yahoo 帳號以啟用此聯賽：\n"
                        f"👉 {login_url}"
                    )
                handler.reply_text(event, configuration, msg)
            else:
                raise

    handler.execute = web_wrapped_execute
    return handler


def inspect_yahoo_login_stage(page) -> dict:
    """自動偵測當前 Yahoo 登入頁面的所在步驟，讓前端每次只顯示該步驟對應的輸入欄位或按鈕。"""
    try:
        return page.evaluate(
            """() => {
                const isVisible = (el) => {
                    if (!el) return false;
                    const style = window.getComputedStyle(el);
                    if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
                    const r = el.getBoundingClientRect();
                    return r.width > 5 && r.height > 5;
                };

                const findVisible = (selector) => {
                    try {
                        for (const el of Array.from(document.querySelectorAll(selector))) {
                            if (isVisible(el)) return el;
                        }
                    } catch (e) {}
                    return null;
                };

                // 擷取頁面上的錯誤訊息
                let errorMsg = '';
                const errEl = findVisible('#username-error, #password-error, .error-msg, p.error, [data-error]');
                if (errEl && errEl.innerText.trim()) {
                    errorMsg = errEl.innerText.trim();
                }

                // 擷取提示說明文字
                let hintMsg = '';
                const descEl = findVisible('.challenge-desc, .txt-align-center, h2.challenge-heading, .challenge-heading');
                if (descEl && descEl.innerText.trim()) {
                    hintMsg = descEl.innerText.trim();
                }

                const href = (window.location && window.location.href) ? window.location.href : '';
                const bodyText = (document.body && document.body.innerText) ? document.body.innerText : '';

                const pwInput = findVisible('#login-passwd, input[name="password"], input[type="password"], input[autocomplete="current-password"]');
                if (
                    pwInput ||
                    href.includes('/challenge/password') ||
                    bodyText.includes('請輸入密碼') ||
                    bodyText.includes('輸入您的密碼') ||
                    bodyText.includes('Enter password')
                ) {
                    return {
                        stage: 'password',
                        step_title: '步驟 2：輸入 Yahoo 密碼',
                        hint: hintMsg || '帳號已確認，請輸入您的 Yahoo 登入密碼',
                        placeholder: '請輸入密碼',
                        input_type: 'password',
                        button_label: '登入',
                        error: errorMsg,
                        options: []
                    };
                }

                const otpInput = findVisible('#verification-code-field, input[name="code"], input[name="otpCode"], input[autocomplete="one-time-code"], input[type="tel"]');
                if (
                    otpInput ||
                    href.includes('/challenge/phone-verify') ||
                    href.includes('/challenge/email-verify') ||
                    bodyText.includes('輸入驗證碼') ||
                    bodyText.includes('Enter verification code')
                ) {
                    return {
                        stage: 'otp',
                        step_title: '步驟 2：輸入驗證碼',
                        hint: hintMsg || 'Yahoo 已發送驗證碼至您的手機或信箱，請收到後輸入',
                        placeholder: '請輸入收到的驗證碼',
                        input_type: 'text',
                        button_label: '驗證並登入',
                        error: errorMsg,
                        options: []
                    };
                }

                const userInput = findVisible('#login-username, input[name="username"], input[name="identifier"]');
                if (userInput && !href.includes('/challenge/')) {
                    return {
                        stage: 'username',
                        step_title: '步驟 1：輸入 Yahoo 帳號',
                        hint: '請先輸入您的 Yahoo 帳號或 Email，按下一步後才會要求密碼或發送驗證碼',
                        placeholder: '請輸入 Yahoo 帳號或 Email',
                        input_type: 'email',
                        button_label: '下一步',
                        error: errorMsg,
                        options: []
                    };
                }

                // 若無標準輸入框，收集畫面上可見的驗證方式按鈕（例如：選擇寄送簡訊、使用 Yahoo App 推播、使用密碼等）
                const btns = [];
                try {
                    const candidates = document.querySelectorAll('button, input[type="submit"], a.pure-button, .challenge-selector li button');
                    candidates.forEach((btn) => {
                        if (isVisible(btn)) {
                            const txt = (btn.innerText || btn.value || '').trim().replace(/\\s+/g, ' ');
                            if (txt && txt.length <= 40 && !btns.includes(txt)) {
                                btns.push(txt);
                            }
                        }
                    });
                } catch (e) {}

                return {
                    stage: 'challenge_select',
                    step_title: '步驟 2：完成雙重驗證或選擇登入方式',
                    hint: hintMsg || '請點擊下方按鈕選擇驗證方式，或直接點擊下方即時網頁畫面操作',
                    placeholder: '若畫面要求輸入文字可在此輸入...',
                    input_type: 'text',
                    button_label: '送出',
                    error: errorMsg,
                    options: btns.slice(0, 6)
                };
            }"""
        )
    except Exception as e:
        logging.warning(f"[WEB_LOGIN] inspect_yahoo_login_stage 異常: {e}")
        return {
            "stage": "username",
            "step_title": "步驟 1：輸入 Yahoo 帳號",
            "hint": "請先輸入您的 Yahoo 帳號或 Email",
            "placeholder": "請輸入 Yahoo 帳號或 Email",
            "input_type": "email",
            "button_label": "下一步",
            "error": "",
            "options": []
        }


class RemoteLoginWorker:
    """在獨立執行緒中管理單一聯盟的遠端登入 Playwright 瀏覽器會話。"""

    VIEWPORT_W = 414
    VIEWPORT_H = 720

    def __init__(self, league_id: str, chat_id: str):
        self.league_id = league_id
        self.chat_id = chat_id
        self.cmd_queue: queue.Queue = queue.Queue()
        self.authorized = False
        self.status_msg = "正在啟動遠端瀏覽器..."
        self.last_active = time.time()
        self.closed = False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def execute_action(self, payload: dict, timeout: float = 15.0) -> dict:
        self.last_active = time.time()
        if self.closed:
            return {"authorized": self.authorized, "closed": True, "status": self.status_msg}
        reply_q: queue.Queue = queue.Queue()
        self.cmd_queue.put((payload, reply_q))
        try:
            return reply_q.get(timeout=timeout)
        except queue.Empty:
            return {"authorized": self.authorized, "error": "操作逾時，請稍後重試", "status": self.status_msg}

    def _notify_line_success(self):
        if not self.chat_id:
            return
        try:
            config = load_config()
            token = config.get("LINE_CHANNEL_ACCESS_TOKEN") or os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
            if not token:
                return
            line_config = Configuration(access_token=token)
            with ApiClient(line_config) as api_client:
                line_bot_api = MessagingApi(api_client)
                msg_text = f"✅ Yahoo 帳號網頁登入成功！已成功啟用此聊天室對聯賽 {self.league_id} 的資料存取功能。"
                line_bot_api.push_message(
                    PushMessageRequest(
                        to=self.chat_id,
                        messages=[TextMessage(text=msg_text)]
                    )
                )
        except Exception as e:
            logging.error(f"[WEB_LOGIN] 推送 LINE 登入成功通知失敗: {e}")

    def _submit_step_input(self, page, stage: str, text: str):
        """根據當前頁面上實際可見的 Yahoo 輸入框自動填入並送出。"""
        if not text:
            return
        candidate_selectors = [
            "#login-passwd",
            'input[name="password"]',
            'input[type="password"]',
            'input[autocomplete="current-password"]',
            "#verification-code-field",
            'input[name="code"]',
            'input[name="otpCode"]',
            'input[autocomplete="one-time-code"]',
            "#login-username",
            'input[name="username"]',
            'input[name="identifier"]',
            'input[type="tel"]',
            'input[type="email"]',
            'input[type="text"]',
        ]
        filled = False
        for sel in candidate_selectors:
            try:
                loc = page.locator(sel)
                count = loc.count()
                for idx in range(count):
                    item = loc.nth(idx)
                    if item.is_visible(timeout=300):
                        item.click()
                        item.fill(text)
                        filled = True
                        break
                if filled:
                    break
            except Exception:
                continue

        if not filled:
            page.keyboard.type(text)

        submit_selectors = [
            "#login-signin",
            "#verify-code-button",
            'button[type="submit"]',
            'input[type="submit"]',
        ]
        submitted = False
        for sub_sel in submit_selectors:
            try:
                btn = page.locator(sub_sel).first
                if btn.is_visible(timeout=500):
                    btn.click()
                    submitted = True
                    break
            except Exception:
                continue

        if not submitted:
            page.keyboard.press("Enter")

        page.wait_for_timeout(2500)

    def _run(self):
        _, _, target_url = build_league_web_url(self.league_id)
        state_path = get_league_storage_state_path(self.league_id)
        headless = os.getenv("HEADLESS_BROWSER", "true").lower() not in ("false", "0", "no")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                try:
                    ctx_kwargs = {
                        "viewport": {"width": self.VIEWPORT_W, "height": self.VIEWPORT_H},
                    }
                    if os.path.exists(state_path):
                        ctx_kwargs["storage_state"] = state_path
                    context = browser.new_context(**ctx_kwargs)
                    page = context.new_page()

                    login_entry = f"https://login.yahoo.com/?.done={target_url}"
                    page.goto(login_entry, wait_until="domcontentloaded", timeout=45000)
                    page.wait_for_timeout(1000)

                    while not self.closed:
                        if time.time() - self.last_active > 600:
                            self.status_msg = "登入會話逾時已關閉"
                            break

                        try:
                            cmd, reply_q = self.cmd_queue.get(timeout=1.0)
                        except queue.Empty:
                            continue

                        action = cmd.get("action", "snapshot")
                        try:
                            if action == "submit_step":
                                stage = str(cmd.get("stage", "username"))
                                text = str(cmd.get("text", "")).strip()
                                self._submit_step_input(page, stage, text)
                            elif action == "click_option":
                                label = str(cmd.get("label", "")).strip()
                                if label:
                                    page.get_by_text(label, exact=False).first.click(timeout=3000)
                                    page.wait_for_timeout(1500)
                            elif action == "click":
                                x = float(cmd.get("x", 0))
                                y = float(cmd.get("y", 0))
                                page.mouse.click(x, y)
                                page.wait_for_timeout(800)
                            elif action == "type":
                                text = str(cmd.get("text", ""))
                                press_enter = bool(cmd.get("press_enter", True))
                                if text:
                                    page.keyboard.type(text)
                                if press_enter:
                                    page.keyboard.press("Enter")
                                page.wait_for_timeout(1500)
                            elif action == "key":
                                key_name = str(cmd.get("key", "Enter"))
                                page.keyboard.press(key_name)
                                page.wait_for_timeout(800)
                            elif action == "scroll":
                                dy = float(cmd.get("delta_y", 250))
                                page.mouse.wheel(0, dy)
                                page.wait_for_timeout(400)
                        except Exception as act_err:
                            logging.warning(f"[WEB_LOGIN] 執行動作 {action} 異常: {act_err}")

                        cur_url = page.url or ""
                        if "login.yahoo.com" not in cur_url and self.league_id.split(".")[-1] not in cur_url:
                            try:
                                page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
                                page.wait_for_timeout(1200)
                            except Exception:
                                pass

                        ok, reason, teams = extract_teams_and_check_auth(page, self.league_id)
                        self.status_msg = reason
                        if ok:
                            context.storage_state(path=state_path)
                            save_discovered_team_mapping(self.league_id, teams, page=page)
                            security_manager.set_league_authorized(self.league_id, True)
                            self.authorized = True
                            self.closed = True
                            reply_q.put({
                                "authorized": True,
                                "url": page.url,
                                "status": reason
                            })
                            self._notify_line_success()
                            break

                        stage_info = inspect_yahoo_login_stage(page)
                        png_bytes = page.screenshot(type="png")
                        b64_img = base64.b64encode(png_bytes).decode("ascii")
                        reply_q.put({
                            "authorized": False,
                            "url": page.url,
                            "status": reason,
                            "stage_info": stage_info,
                            "viewport_w": self.VIEWPORT_W,
                            "viewport_h": self.VIEWPORT_H,
                            "image_b64": b64_img
                        })
                finally:
                    browser.close()
        except Exception as e:
            logging.error(f"[WEB_LOGIN] 遠端登入執行緒錯誤: {e}")
            self.status_msg = f"瀏覽器啟動失敗: {e}"
        finally:
            self.closed = True


_ACTIVE_WORKERS: dict[str, RemoteLoginWorker] = {}
_WORKERS_LOCK = threading.Lock()


def get_or_create_login_worker(league_id: str, chat_id: str) -> RemoteLoginWorker:
    key = f"{chat_id}:{league_id}"
    with _WORKERS_LOCK:
        worker = _ACTIVE_WORKERS.get(key)
        if worker is None or worker.closed:
            worker = RemoteLoginWorker(league_id=league_id, chat_id=chat_id)
            _ACTIVE_WORKERS[key] = worker
        return worker


REMOTE_LOGIN_HTML = """<!DOCTYPE html>
<html lang="zh-Hant">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>Yahoo Fantasy 聯盟登入授權</title>
<style>
  * { box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, "Microsoft JhengHei", sans-serif; margin: 0; background: #f4f6f9; color: #1d2228; }
  .container { max-width: 440px; margin: 0 auto; padding: 14px; }
  .card { background: #fff; border-radius: 14px; padding: 18px 16px; box-shadow: 0 4px 16px rgba(0,0,0,0.08); margin-bottom: 14px; }
  .brand { font-size: 13px; font-weight: 700; color: #6001d2; letter-spacing: 0.3px; margin-bottom: 4px; }
  .step-title { font-size: 19px; font-weight: 700; margin: 0 0 6px 0; color: #1d2228; }
  .hint { font-size: 13px; color: #5b636a; margin-bottom: 12px; line-height: 1.45; }
  .error-box { display: none; background: #fff1f0; border: 1px solid #ffa39e; color: #cf1322; font-size: 13px; padding: 8px 10px; border-radius: 8px; margin-bottom: 12px; }
  .form-row { display: flex; flex-direction: column; gap: 10px; }
  .form-row input { width: 100%; padding: 12px 14px; font-size: 16px; border: 1.5px solid #cbd2d9; border-radius: 10px; outline: none; transition: border-color 0.2s; }
  .form-row input:focus { border-color: #6001d2; }
  .primary-btn { width: 100%; padding: 12px; font-size: 16px; font-weight: 700; border: none; border-radius: 24px; background: #6001d2; color: #fff; cursor: pointer; }
  .primary-btn:disabled { opacity: 0.6; cursor: wait; }
  .options-list { display: none; flex-direction: column; gap: 8px; margin-bottom: 10px; }
  .opt-btn { width: 100%; padding: 10px 12px; font-size: 14px; font-weight: 600; border: 1px solid #d0d7de; border-radius: 10px; background: #f8f9fa; color: #222; cursor: pointer; text-align: left; }
  .preview-header { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: #666; margin-bottom: 6px; padding: 0 4px; }
  .viewer { text-align: center; background: #fff; border-radius: 12px; padding: 6px; box-shadow: 0 2px 10px rgba(0,0,0,0.05); }
  #screen { width: 100%; border-radius: 8px; display: block; cursor: pointer; touch-action: manipulation; }
  .success-card { display: none; max-width: 400px; margin: 50px auto; background: #fff; padding: 32px 20px; border-radius: 14px; text-align: center; box-shadow: 0 4px 16px rgba(0,0,0,0.1); }
  .success-card h2 { color: #1a7f37; margin-top: 0; }
</style>
</head>
<body>
<div class="container" id="mainContainer">
  <div class="card">
    <div class="brand">Yahoo Fantasy 聯盟授權 (__LEAGUE_ID__)</div>
    <h1 class="step-title" id="stepTitle">正在連線至 Yahoo 登入頁...</h1>
    <div class="hint" id="stepHint">系統會根據 Yahoo 驗證流程逐步引導您輸入帳號、密碼或驗證碼。</div>
    <div class="error-box" id="errorBox"></div>
    <div class="options-list" id="optionsList"></div>
    <form class="form-row" id="stepForm" onsubmit="handleStepSubmit(event)">
      <input type="email" id="stepInput" placeholder="請輸入 Yahoo 帳號或 Email" autocomplete="off" required>
      <button type="submit" class="primary-btn" id="submitBtn">下一步</button>
    </form>
  </div>

  <div class="preview-header">
    <span id="statusText">即時 Yahoo 網頁畫面（亦可直接點擊畫面互動）</span>
    <span onclick="sendScroll(240)" style="color:#6001d2;cursor:pointer;font-weight:600;">往下捲動 ▾</span>
  </div>
  <div class="viewer">
    <img id="screen" alt="正在載入 Yahoo 登入畫面..." onclick="handleTap(event)">
  </div>
</div>

<div class="success-card" id="successCard">
  <h2>🎉 授權成功！</h2>
  <p>聊天室已順利取得聯賽 <b>__LEAGUE_ID__</b> 的網頁存取權限。</p>
  <p>現在您可以直接關閉此網頁並回到 LINE 聊天室！</p>
</div>

<script>
const leagueId = "__LEAGUE_ID__";
const chatId = "__CHAT_ID__";
const screenEl = document.getElementById("screen");
const statusEl = document.getElementById("statusText");
const stepTitleEl = document.getElementById("stepTitle");
const stepHintEl = document.getElementById("stepHint");
const stepInputEl = document.getElementById("stepInput");
const submitBtnEl = document.getElementById("submitBtn");
const errorBoxEl = document.getElementById("errorBox");
const optionsListEl = document.getElementById("optionsList");

let currentStage = "username";
let viewportW = 414;
let viewportH = 720;
let busy = false;

function updateStageUI(stageInfo) {
  if (!stageInfo) return;
  const newStage = stageInfo.stage || "username";
  stepTitleEl.innerText = stageInfo.step_title || "Yahoo 帳號登入";
  stepHintEl.innerText = stageInfo.hint || "";
  submitBtnEl.innerText = stageInfo.button_label || "下一步";

  if (stageInfo.error) {
    errorBoxEl.style.display = "block";
    errorBoxEl.innerText = "⚠️ " + stageInfo.error;
  } else {
    errorBoxEl.style.display = "none";
  }

  if (newStage !== currentStage) {
    currentStage = newStage;
    stepInputEl.value = "";
    stepInputEl.type = stageInfo.input_type || "text";
    stepInputEl.placeholder = stageInfo.placeholder || "";
    stepInputEl.focus();
  } else {
    stepInputEl.type = stageInfo.input_type || "text";
    stepInputEl.placeholder = stageInfo.placeholder || "";
  }

  const opts = stageInfo.options || [];
  if (opts.length > 0 && newStage === "challenge_select") {
    optionsListEl.style.display = "flex";
    optionsListEl.innerHTML = "";
    opts.forEach((optText) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "opt-btn";
      b.innerText = "👉 " + optText;
      b.onclick = () => clickOption(optText);
      optionsListEl.appendChild(b);
    });
  } else {
    optionsListEl.style.display = "none";
  }
}

async function postAction(payload) {
  if (busy && payload.action === "snapshot") return;
  busy = true;
  if (payload.action !== "snapshot") {
    submitBtnEl.disabled = true;
  }
  try {
    const resp = await fetch("/yahoo/web-login/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ league_id: leagueId, chat_id: chatId, ...payload })
    });
    const data = await resp.json();
    if (data.authorized) {
      document.getElementById("mainContainer").style.display = "none";
      document.getElementById("successCard").style.display = "block";
      return;
    }
    if (data.viewport_w && data.viewport_h) {
      viewportW = data.viewport_w;
      viewportH = data.viewport_h;
    }
    if (data.stage_info) {
      updateStageUI(data.stage_info);
    }
    if (data.status) {
      statusEl.innerText = data.status;
    }
    if (data.image_b64) {
      screenEl.src = "data:image/png;base64," + data.image_b64;
    }
  } catch (e) {
    statusEl.innerText = "正在同步畫面...";
  } finally {
    busy = false;
    submitBtnEl.disabled = false;
  }
}

function handleStepSubmit(e) {
  e.preventDefault();
  const val = stepInputEl.value.trim();
  if (!val) return;
  stepInputEl.value = "";
  statusEl.innerText = "正在送出至 Yahoo 驗證...";
  postAction({ action: "submit_step", stage: currentStage, text: val });
}

function clickOption(label) {
  statusEl.innerText = "正在點擊選項：" + label;
  postAction({ action: "click_option", label });
}

function handleTap(e) {
  const rect = screenEl.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const x = ((e.clientX - rect.left) / rect.width) * viewportW;
  const y = ((e.clientY - rect.top) / rect.height) * viewportH;
  statusEl.innerText = "已點擊畫面，處理中...";
  postAction({ action: "click", x, y });
}

function sendScroll(dy) {
  postAction({ action: "scroll", delta_y: dy });
}

setInterval(() => postAction({ action: "snapshot" }), 2500);
postAction({ action: "snapshot" });
</script>
</body>
</html>
"""


@web_login_bp.route("/yahoo/web-login", methods=["GET"])
def yahoo_web_login_page():
    league_id = request.args.get("league_id", "").strip()
    chat_id = request.args.get("chat_id", "").strip()
    if not league_id:
        return "⚠️ 缺少參數 league_id", 400

    get_or_create_login_worker(league_id=league_id, chat_id=chat_id)
    html = (
        REMOTE_LOGIN_HTML
        .replace("__LEAGUE_ID__", league_id)
        .replace("__CHAT_ID__", chat_id)
    )
    return Response(html, mimetype="text/html")


@web_login_bp.route("/yahoo/web-login/action", methods=["POST"])
def yahoo_web_login_action():
    data = request.get_json(silent=True) or {}
    league_id = str(data.get("league_id", "")).strip()
    chat_id = str(data.get("chat_id", "")).strip()
    if not league_id:
        return jsonify({"error": "missing league_id"}), 400

    worker = get_or_create_login_worker(league_id=league_id, chat_id=chat_id)
    result = worker.execute_action(data)
    return jsonify(result)
