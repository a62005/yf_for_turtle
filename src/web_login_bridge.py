import os
import re
import time
import json
import queue
import base64
import logging
import threading
from flask import Blueprint, request, jsonify, Response
from playwright.sync_api import sync_playwright
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage

from src.config import load_config
from src.utils.path_utils import get_league_dir, parse_league_id
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


def is_page_authorized_for_league(page, league_id: str) -> tuple[bool, str]:
    """檢查當前 Playwright page 是否已登入且具備檢視指定聯盟的權限。"""
    current_url = page.url or ""
    if "login.yahoo.com" in current_url:
        return False, "尚在 Yahoo 登入頁面"

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
                    return { ok: false, reason: '無此聯盟檢視權限或尚未登入 (Error #152)' };
                }

                const teamRegex = new RegExp(`/${sportSlug}/${rawId}/(\\\\d+)$`);
                let teamCount = 0;
                for (const a of Array.from(document.querySelectorAll('a[href]'))) {
                    try {
                        const u = new URL(a.href, window.location.origin);
                        if (teamRegex.test(u.pathname) && !u.search) {
                            teamCount++;
                        }
                    } catch (e) {}
                }
                if (teamCount >= 2) {
                    return { ok: true, reason: `已成功讀取 ${teamCount} 支隊伍連結` };
                }
                return { ok: false, reason: '頁面上尚未偵測到聯盟隊伍資料' };
            }""",
            {"sportSlug": sport_slug, "rawId": raw_id}
        )
        return bool(check_result.get("ok")), str(check_result.get("reason", ""))
    except Exception as e:
        return False, f"頁面檢查異常: {e}"


def verify_league_web_access(league_id: str, headless: bool = True) -> bool:
    """使用已保存的 yahoo_web_state.json 測試是否能成功進入聯盟頁面並看到隊伍。"""
    state_path = get_league_storage_state_path(league_id)
    if not os.path.exists(state_path):
        return False

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
                ok, _ = is_page_authorized_for_league(page, league_id)
                if ok:
                    context.storage_state(path=state_path)
                return ok
            finally:
                browser.close()
    except Exception as e:
        logging.warning(f"[WEB_LOGIN] 驗證聯盟 {league_id} 網頁權限失敗: {e}")
        return False


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
                msg_text = f"✅ Yahoo 帳號網頁登入成功！已啟用此聊天室對聯賽 {self.league_id} 的每日 14:00 戰績自動抓取功能。"
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
                        # 逾時 10 分鐘自動關閉
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

                        # 檢查若已登入但不在聯盟頁，嘗試導向聯盟頁
                        cur_url = page.url or ""
                        if "login.yahoo.com" not in cur_url and self.league_id.split(".")[-1] not in cur_url:
                            try:
                                page.goto(target_url, wait_until="domcontentloaded", timeout=25000)
                                page.wait_for_timeout(1200)
                            except Exception:
                                pass

                        ok, reason = is_page_authorized_for_league(page, self.league_id)
                        self.status_msg = reason
                        if ok:
                            context.storage_state(path=state_path)
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
