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
                            if (name && !teams[tid]) {
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


def save_discovered_team_mapping(league_id: str, teams: dict[str, str]) -> None:
    """當從網頁擷取到官方隊伍名稱時，若 team_mapping.json 尚未建立或為空，則自動寫入以支援 #設置玩家暱稱。"""
    if not teams:
        return
    mapping_path = get_league_team_mapping_path(league_id)
    existing = {}
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except Exception:
            existing = {}

    if not existing:
        os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
        with open(mapping_path, "w", encoding="utf-8") as f:
            json.dump(teams, f, ensure_ascii=False, indent=2)


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
                    save_discovered_team_mapping(league_id, teams)
                return ok, teams
            finally:
                browser.close()
    except Exception as e:
        logging.warning(f"[WEB_LOGIN] 驗證聯盟 {league_id} 網頁權限失敗: {e}")
        return False, {}


def bind_web_login_to_set_league_handler(handler):
    """
    在不修改 src/handlers/set_league_id_handler.py 原始碼的前提下，
    將 bot.py 中註冊的 SetLeagueIdHandler 實例之 API 驗證替換為「網頁登入狀態驗證」，
    並於未登入時回覆手機端遠端網頁登入網址。
    """
    raw_execute = type(handler).execute.__get__(handler, type(handler))
    real_exists = os.path.exists

    def web_os_path_exists(path):
        p_str = str(path)
        if p_str.endswith(".yahoofantasy") or p_str.endswith("oauth2.json"):
            return False
        return real_exists(path)

    def web_wrapped_execute(event, configuration):
        user_id = getattr(event.source, "user_id", None)
        discovered_teams_holder = {}
        verified_state = {"target_id": None, "ok": False}

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

            res = verify_league_web_access(target_id)
            if isinstance(res, tuple):
                ok, teams = res
            else:
                ok, teams = bool(res), {}
            if not ok:
                raise LeaguePermissionError(f"Web login required for {target_id}")
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
                security_manager.set_league_authorized(verified_state["target_id"], True)
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


class RemoteLoginWorker:
    """在獨立執行緒中管理單一聯盟的遠端登入 Playwright 瀏覽器會話。"""

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

    def _run(self):
        _, _, target_url = build_league_web_url(self.league_id)
        state_path = get_league_storage_state_path(self.league_id)
        headless = os.getenv("HEADLESS_BROWSER", "true").lower() not in ("false", "0", "no")

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=headless)
                try:
                    ctx_kwargs = {"viewport": {"width": 1280, "height": 900}}
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
                            if action == "click":
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
                                page.wait_for_timeout(1200)
                            elif action == "key":
                                key_name = str(cmd.get("key", "Enter"))
                                page.keyboard.press(key_name)
                                page.wait_for_timeout(800)
                            elif action == "scroll":
                                dy = float(cmd.get("delta_y", 300))
                                page.mouse.wheel(0, dy)
                                page.wait_for_timeout(500)
                            elif action == "goto_league":
                                page.goto(target_url, wait_until="domcontentloaded", timeout=30000)
                                page.wait_for_timeout(1500)
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
                            save_discovered_team_mapping(self.league_id, teams)
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

                        png_bytes = page.screenshot(type="png")
                        b64_img = base64.b64encode(png_bytes).decode("ascii")
                        reply_q.put({
                            "authorized": False,
                            "url": page.url,
                            "status": reason,
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
<title>Yahoo Fantasy 網頁登入授權</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, "Microsoft JhengHei", sans-serif; margin: 0; background: #f4f6f8; color: #222; }
  .topbar { position: sticky; top: 0; z-index: 10; background: #fff; padding: 10px 12px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
  .title { font-size: 15px; font-weight: bold; margin-bottom: 6px; color: #400090; }
  .status { font-size: 12px; color: #666; margin-bottom: 8px; }
  .controls { display: flex; gap: 6px; flex-wrap: wrap; }
  .controls input { flex: 1; min-width: 160px; padding: 8px 10px; font-size: 15px; border: 1px solid #ccc; border-radius: 6px; }
  .controls button { padding: 8px 12px; font-size: 14px; font-weight: bold; border: none; border-radius: 6px; background: #6001d2; color: #fff; cursor: pointer; }
  .controls button.secondary { background: #e4e7eb; color: #333; }
  .viewer { padding: 10px; text-align: center; }
  #screen { width: 100%; max-width: 900px; border: 1px solid #ccc; border-radius: 8px; background: #fff; cursor: pointer; touch-action: manipulation; }
  .success-card { display: none; max-width: 400px; margin: 60px auto; background: #fff; padding: 32px; border-radius: 12px; text-align: center; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
  .success-card h2 { color: #2da44e; }
</style>
</head>
<body>
<div class="topbar" id="topbar">
  <div class="title">🔐 Yahoo Fantasy 聯盟授權登入 (__LEAGUE_ID__)</div>
  <div class="status" id="statusText">正在載入遠端登入畫面...（點擊下方畫面任意處可聚焦輸入框，再用上方欄位送出文字）</div>
  <div class="controls">
    <input type="text" id="textInput" placeholder="輸入帳號 / 密碼 / 驗證碼..." autocomplete="off">
    <button onclick="sendText(true)">輸入並送出</button>
    <button class="secondary" onclick="sendKey('Backspace')">退格</button>
    <button class="secondary" onclick="sendScroll(300)">往下滑</button>
  </div>
</div>

<div class="viewer" id="viewer">
  <img id="screen" alt="請稍候，正在載入 Yahoo 登入畫面..." onclick="handleTap(event)">
</div>

<div class="success-card" id="successCard">
  <h2>🎉 授權成功！</h2>
  <p>聊天室已順利取得聯賽 <b>__LEAGUE_ID__</b> 的網頁存取權限。</p>
  <p>現在您可以關閉此頁面並回到 LINE 聊天室！</p>
</div>

<script>
const leagueId = "__LEAGUE_ID__";
const chatId = "__CHAT_ID__";
const screenEl = document.getElementById("screen");
const statusEl = document.getElementById("statusText");
let busy = false;

async function postAction(payload) {
  if (busy && payload.action === "snapshot") return;
  busy = true;
  try {
    const resp = await fetch("/yahoo/web-login/action", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ league_id: leagueId, chat_id: chatId, ...payload })
    });
    const data = await resp.json();
    if (data.authorized) {
      document.getElementById("topbar").style.display = "none";
      document.getElementById("viewer").style.display = "none";
      document.getElementById("successCard").style.display = "block";
      return;
    }
    if (data.status) {
      statusEl.innerText = "狀態：" + data.status;
    }
    if (data.image_b64) {
      screenEl.src = "data:image/png;base64," + data.image_b64;
    }
  } catch (e) {
    statusEl.innerText = "連線更新中...";
  } finally {
    busy = false;
  }
}

function handleTap(e) {
  const rect = screenEl.getBoundingClientRect();
  if (!rect.width || !rect.height) return;
  const x = ((e.clientX - rect.left) / rect.width) * 1280;
  const y = ((e.clientY - rect.top) / rect.height) * 900;
  statusEl.innerText = "已點擊畫面，處理中...";
  postAction({ action: "click", x, y });
}

function sendText(pressEnter) {
  const input = document.getElementById("textInput");
  const val = input.value;
  input.value = "";
  statusEl.innerText = "正在送出輸入內容...";
  postAction({ action: "type", text: val, press_enter: pressEnter });
}

function sendKey(keyName) {
  postAction({ action: "key", key: keyName });
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
