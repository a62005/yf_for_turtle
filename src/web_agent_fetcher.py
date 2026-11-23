import os
import sys

# 確保專案根目錄在 sys.path 中，避免以腳本直接執行時找不到 src 模組
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

import json
import time
import logging
import argparse
from playwright.sync_api import sync_playwright
from src.config import load_config
from src.utils.path_utils import (
    BASE_DIR,
    DATA_DIR,
    parse_league_id,
    get_league_dir,
    get_league_image_dir,
    get_league_daily_dir,
    get_league_weekly_dir,
    get_league_team_mapping_path,
)
from src.utils.time_utils import (
    get_pacific_date,
    get_today_tw_date,
    tw_date_to_yahoo_date,
    yahoo_date_to_tw_date,
    has_games_on_yahoo_date,
    resolve_latest_active_tw_date,
)
from src.llm.gemini import GeminiProvider
from src.visualizer.processor import process_stats_for_visual
from src.visualizer.renderer import render_stats_html
from src.visualizer.capturer import capture_html_to_png
from src.web_login_bridge import (
    get_league_storage_state_path,
    is_page_authorized_for_league,
    build_mobile_web_login_url,
    save_and_sync_league_storage_state,
)


DEFAULT_AGENT_MODEL = "gemini-3.5-flash"
FALLBACK_AGENT_MODEL = "gemini-3-flash-preview"


class LeagueWebAuthError(RuntimeError):
    """當瀏覽器未登入 Yahoo 或登入帳號無該聯盟檢視權限時拋出。"""
    pass


class GamesInProgressError(RuntimeError):
    """當網頁或賽事計分板顯示當日仍有比賽正在進行中時拋出。"""
    pass


class NoGamesScheduledError(RuntimeError):
    """當目標日期無任何賽事排程，或擷取結果顯示全聯盟當日皆無出賽且計數全為 0 時拋出。"""
    pass


class StatsDataValidationError(RuntimeError):
    """當擷取或解析出的戰績數據未通過完整性與合理性驗證（如漏抓對戰頁面、週數據小於日數據、整組歸零）時拋出。"""
    pass


def has_ongoing_games_in_scraped_data(scraped_data: dict, sport: str = "nba") -> bool:
    """
    從擷取的 Yahoo Fantasy 每日頁面表格資料中檢測是否仍有比賽正在進行中。
    當發現明確的比賽進行中標記（如 Q1~Q4 節數時間、Halftime、OT、In Progress、Top/Bot 局數）時回傳 True。
    """
    import re

    if not isinstance(scraped_data, dict):
        return False
    if scraped_data.get("games_in_progress") is True:
        return True

    live_pattern = re.compile(
        r"\b(?:"
        r"Q[1-4](?:\s+\d{1,2}:\d{2})?|"
        r"[1-4](?:st|nd|rd|th)\s+\d{1,2}:\d{2}|"
        r"[1-4]?OT(?:\s+\d{1,2}:\d{2})?|"
        r"Halftime|In\s+Progress|"
        r"(?:Top|Bot|Mid|End)\s+(?:1st|2nd|3rd|[4-9]th|1\dth)|"
        r"End\s+Q[1-4]"
        r")\b",
        re.IGNORECASE
    )

    for dp in scraped_data.get("daily_pages") or []:
        if not isinstance(dp, dict):
            continue
        for table_text in dp.get("tables") or []:
            if not isinstance(table_text, str):
                continue
            for row in table_text.splitlines():
                if live_pattern.search(row):
                    return True
    return False


def get_browser_profile_dir() -> str:
    """回傳本地 Playwright 持久化瀏覽器設定檔目錄 (位於 credentials/browser_profile)。"""
    profile_dir = os.path.join(BASE_DIR, "credentials", "browser_profile")
    os.makedirs(profile_dir, exist_ok=True)
    return profile_dir


def build_league_url(league_id: str) -> tuple[str, str, str]:
    """根據 league_id 推導運動項目、純數字 ID 與 Yahoo Fantasy 聯盟網址。"""
    sport, raw_id = parse_league_id(league_id)
    if sport == "mlb":
        return "mlb", raw_id, f"https://baseball.fantasysports.yahoo.com/b1/{raw_id}"
    return "nba", raw_id, f"https://basketball.fantasysports.yahoo.com/nba/{raw_id}"


def login_interactively(league_id: str = None) -> None:
    """開啟本機有頭瀏覽器視窗供使用者登入 Yahoo Fantasy，並同時寫入聯盟專屬 yahoo_web_state.json。"""
    if not league_id:
        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            mapping_file = os.path.join(DATA_DIR, "security", "chat_league_mapping.json")
            if os.path.exists(mapping_file):
                try:
                    with open(mapping_file, "r", encoding="utf-8") as f:
                        mapping = json.load(f)
                        if mapping:
                            league_id = next(iter(mapping.values()))
                except Exception:
                    pass

    target_url = "https://basketball.fantasysports.yahoo.com"
    if league_id and str(league_id) != "default":
        _, _, target_url = build_league_url(league_id)

    profile_dir = get_browser_profile_dir()
    logging.info(f"[LOGIN] 正在啟動本地瀏覽器，設定檔路徑: {profile_dir}")
    logging.info(f"[LOGIN] 前往網址: {target_url}")
    logging.info("[LOGIN] 請在開啟的瀏覽器視窗中完成 Yahoo 帳號登入，確認可看到聯盟畫面後，直接關閉瀏覽器視窗即可。")

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            headless=False,
            viewport={"width": 1280, "height": 900}
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(target_url)
        try:
            page.wait_for_event("close", timeout=0)
        except Exception:
            pass
        finally:
            if league_id and str(league_id) != "default":
                try:
                    state_path = get_league_storage_state_path(league_id)
                    context.storage_state(path=state_path)
                    logging.info(f"[LOGIN] 已同步儲存聯盟網頁憑證至: {state_path}")
                except Exception:
                    pass
            try:
                context.close()
            except Exception:
                pass
    logging.info("[LOGIN] 瀏覽器已關閉，登入狀態已成功保存！")


class WebAgentFetcher:
    """使用已授權的聯盟網頁登入狀態 (yahoo_web_state.json) 與 Gemini AI 從 Yahoo 網站擷取當日與當週戰績。"""

    def __init__(
        self,
        team_mapping: dict = None,
        league_id: str = None,
        api_key: str = None,
        model_name: str = None,
        headless: bool = None
    ):
        config = load_config()
        self.league_id = league_id or config.get("LEAGUE_ID")
        self.team_mapping = team_mapping or {}
        self.api_key = api_key or config.get("LLM_API_KEY") or os.getenv("LLM_API_KEY")
        self.model_name = model_name or DEFAULT_AGENT_MODEL

        if headless is None:
            env_headless = os.getenv("HEADLESS_BROWSER", "true").lower()
            self.headless = env_headless not in ("false", "0", "no")
        else:
            self.headless = headless

    def _call_gemini_json(self, prompt: str, system_instruction: str) -> dict:
        """使用最新可用之 Gemini 模型 (預設 gemini-3-flash-preview) 解析 JSON，若遇配額限制自動降級至備援模型。"""
        if not self.api_key:
            raise RuntimeError("未設定 LLM_API_KEY，無法啟動 Gemini AI Agent。")

        models_to_try = [self.model_name]
        for backup in ["gemini-3.5-flash-lite", FALLBACK_AGENT_MODEL, "gemini-3.6-flash"]:
            if backup not in models_to_try:
                models_to_try.append(backup)

        last_err = None
        for m_name in models_to_try:
            try:
                provider = GeminiProvider(api_key=self.api_key, model_name=m_name)
                res = provider.generate_json(prompt=prompt, system_instruction=system_instruction, temperature=0.0)
                if res:
                    return res
            except Exception as e:
                last_err = e
                logging.warning(f"[WEB_AGENT] 模型 {m_name} 呼叫失敗，嘗試備援模型: {e}")
        if last_err:
            raise last_err
        return {}

    def fetch_team_mapping_via_agent(self, league_id: str = None, page=None) -> dict[str, str]:
        """透過 AI Agent 瀏覽聯盟首頁擷取所有隊伍 ID 與名稱，回傳 {team_id: team_name}。若登入失效則拋出 LeagueWebAuthError。"""
        lid = league_id or self.league_id
        if not lid:
            raise ValueError("LEAGUE_ID 未設定，無法透過 AI Agent 獲取隊伍清單。")

        sport, raw_id, base_url = build_league_url(lid)
        sport_slug = "b1" if sport == "mlb" else "nba"

        def _extract_raw_from_page(active_page) -> dict:
            ok, reason = is_page_authorized_for_league(active_page, lid)
            if not ok:
                raise LeagueWebAuthError(
                    f"無法存取聯盟 {lid} 網頁 ({reason})，Yahoo 登入狀態已失效或尚未登入。"
                )
            return active_page.evaluate(
                """({ sportSlug, rawId }) => {
                    const teamRegex = new RegExp(`/${sportSlug}/${rawId}/(\\\\d+)$`);
                    const links = [];
                    for (const a of Array.from(document.querySelectorAll('a[href]'))) {
                        try {
                            const u = new URL(a.href, window.location.origin);
                            const m = u.pathname.match(teamRegex);
                            if (m && !u.search) {
                                const text = a.innerText.trim();
                                if (text) {
                                    links.push({ team_id: m[1], text });
                                }
                            }
                        } catch (e) {}
                    }
                    const tables = Array.from(document.querySelectorAll('table')).map(
                        t => t.innerText.replace(/\\s+/g, ' ').trim()
                    ).filter(Boolean);
                    return { links, tables };
                }""",
                {"sportSlug": sport_slug, "rawId": raw_id}
            )

        if page is not None:
            raw_page_data = _extract_raw_from_page(page)
        else:
            state_path = get_league_storage_state_path(lid)
            if not os.path.exists(state_path):
                raise LeagueWebAuthError(f"聯盟 {lid} 尚未有登入狀態檔，請重新登入 Yahoo 帳號。")
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=self.headless)
                try:
                    context = browser.new_context(
                        storage_state=state_path,
                        viewport={"width": 1280, "height": 900}
                    )
                    new_page = context.new_page()
                    new_page.goto(base_url, wait_until="domcontentloaded", timeout=45000)
                    new_page.wait_for_timeout(1500)
                    raw_page_data = _extract_raw_from_page(new_page)
                    save_and_sync_league_storage_state(context, lid)
                finally:
                    browser.close()

        fallback_map = {}
        for item in raw_page_data.get("links", []):
            tid = str(item.get("team_id", "")).strip()
            txt = str(item.get("text", "")).strip()
            if tid and txt and txt.lower() != "my team" and tid not in fallback_map:
                fallback_map[tid] = txt

        if self.api_key:
            sys_inst = (
                "你是 Yahoo Fantasy 聯盟網頁解析 AI Agent。\n"
                "請根據提供的聯盟網頁隊伍連結與戰績表文字，提取該聯盟所有隊伍的編號 (team_id，純數字字串如 '1', '2'...) 與對應的真實隊伍名稱。\n"
                "注意：忽略導覽列上的 'My Team' 字樣，必須使用該隊伍真正的名稱。\n"
                '請嚴格輸出 JSON 格式：{"teams": {"1": "隊伍名稱1", "2": "隊伍名稱2"}}'
            )
            prompt = f"聯盟 ID: {lid}\n網頁擷取資料:\n{json.dumps(raw_page_data, ensure_ascii=False)}"
            try:
                logging.info(f"[WEB_AGENT] 正在使用 Gemini AI Agent ({self.model_name}) 解析聯盟 {lid} 的隊伍清單...")
                parsed = self._call_gemini_json(prompt=prompt, system_instruction=sys_inst)
                ai_teams = parsed.get("teams") if isinstance(parsed, dict) else None
                if isinstance(ai_teams, dict) and len(ai_teams) >= 2:
                    cleaned = {
                        str(k).strip(): str(v).strip()
                        for k, v in ai_teams.items()
                        if str(k).strip() and str(v).strip() and str(v).strip().lower() != "my team"
                    }
                    if len(cleaned) >= 2:
                        return dict(sorted(cleaned.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999))
            except Exception as e:
                logging.warning(f"[WEB_AGENT] Gemini 解析 team_mapping 失敗，改用網頁連結解析結果: {e}")

        if len(fallback_map) < 2:
            raise LeagueWebAuthError(f"無法從聯盟 {lid} 網頁擷取到隊伍清單，登入狀態可能已失效。")
        return dict(sorted(fallback_map.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 999))

    def ensure_team_mapping_via_agent(self, league_id: str = None, page=None) -> dict[str, str]:
        """檢查聯盟是否有 team_mapping.json；若無或為空，則透過 AI Agent 瀏覽網頁獲取並寫入 team_mapping.json。"""
        lid = league_id or self.league_id
        mapping_path = get_league_team_mapping_path(lid)
        existing = {}
        if os.path.exists(mapping_path):
            try:
                with open(mapping_path, "r", encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                existing = {}

        if existing and isinstance(existing, dict) and len(existing) >= 2:
            return existing

        teams = self.fetch_team_mapping_via_agent(league_id=lid, page=page)
        if teams:
            os.makedirs(os.path.dirname(mapping_path), exist_ok=True)
            with open(mapping_path, "w", encoding="utf-8") as f:
                json.dump(teams, f, ensure_ascii=False, indent=2)
            logging.info(f"[WEB_AGENT] 已透過 AI Agent 自動更新聯盟 {lid} 的 team_mapping.json (共 {len(teams)} 隊)")
        return teams

    def _scrape_league_pages(self, league_id: str, target_date: str) -> dict:
        """透過已登入的 Playwright 瀏覽器開啟聯盟頁面，驗證權限後擷取當週對戰表與各隊當日數據表格內容。"""
        sport, raw_id, base_url = build_league_url(league_id)
        sport_slug = "b1" if sport == "mlb" else "nba"
        state_path = get_league_storage_state_path(league_id)

        logging.info(f"[WEB_AGENT] 啟動瀏覽器前往聯盟首頁: {base_url} (日期: {target_date})")
        with sync_playwright() as p:
            browser = None
            context = None
            try:
                if os.path.exists(state_path):
                    browser = p.chromium.launch(headless=self.headless)
                    context = browser.new_context(
                        storage_state=state_path,
                        viewport={"width": 1280, "height": 900}
                    )
                else:
                    profile_dir = get_browser_profile_dir()
                    context = p.chromium.launch_persistent_context(
                        user_data_dir=profile_dir,
                        headless=self.headless,
                        viewport={"width": 1280, "height": 900}
                    )

                page = context.pages[0] if context.pages else context.new_page()
                page.goto(base_url, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2000)

                ok, reason = is_page_authorized_for_league(page, league_id)
                if not ok:
                    raise LeagueWebAuthError(
                        f"無法存取聯盟 {league_id} 網頁 ({reason})，請透過手機登入網址完成 Yahoo 帳號授權。"
                    )

                # 智慧週數定位：從 Yahoo Matchup 官方日期導覽直接判定目標日期所屬週數
                # 徹底防禦明星賽週 (All-Star Week 跨兩週 14 天) 或長短週合併造成的日曆除法偏差
                smart_week_info = page.evaluate("""async (baseUrl) => {
                    let navDoc = document;
                    try {
                        const mResp = await fetch(`${baseUrl}/matchup`, { credentials: 'include' });
                        if (mResp.ok) {
                            const html = await mResp.text();
                            const parser = new DOMParser();
                            navDoc = parser.parseFromString(html, 'text/html');
                        }
                    } catch (e) {}

                    const text = navDoc.body.innerText;
                    const wm = text.match(/Week\\s*(\\d+)/i);
                    const currWeek = wm ? parseInt(wm[1], 10) : 1;

                    const dates = [];
                    for (const a of Array.from(navDoc.querySelectorAll('a[href*="date="]'))) {
                        try {
                            const u = new URL(a.href, window.location.origin);
                            const d = u.searchParams.get('date');
                            if (d && /^\\d{4}-\\d{2}-\\d{2}$/.test(d)) {
                                dates.push(d);
                            }
                        } catch (e) {}
                    }
                    const uniqueDates = Array.from(new Set(dates)).sort();

                    let prevWeek = null;
                    let nextWeek = null;
                    for (const a of Array.from(navDoc.querySelectorAll('a[href*="week="]'))) {
                        try {
                            const u = new URL(a.href, window.location.origin);
                            const w = parseInt(u.searchParams.get('week'), 10);
                            if (w < currWeek) prevWeek = w;
                            if (w > currWeek && nextWeek === null) nextWeek = w;
                        } catch (e) {}
                    }
                    return { currWeek, dates: uniqueDates, prevWeek, nextWeek };
                }""", base_url)

                curr_week_val = smart_week_info.get("currWeek") or 1
                week_dates = smart_week_info.get("dates") or []
                prev_week_val = smart_week_info.get("prevWeek") or max(1, curr_week_val - 1)
                next_week_val = smart_week_info.get("nextWeek") or (curr_week_val + 1)

                if week_dates and target_date in week_dates:
                    target_week = curr_week_val
                    logging.info(f"[WEB_AGENT] 目標日期 {target_date} 命中當前 Matchup 日期列表，判定為 Week {target_week}")
                elif week_dates and target_date < week_dates[0]:
                    target_week = prev_week_val
                    logging.info(f"[WEB_AGENT] 目標日期 {target_date} 早於當前週起始 ({week_dates[0]})，依 Yahoo 導航判定為上一週 Week {target_week}")
                elif week_dates and target_date > week_dates[-1]:
                    target_week = next_week_val
                    logging.info(f"[WEB_AGENT] 目標日期 {target_date} 晚於當前週結束 ({week_dates[-1]})，依 Yahoo 導航判定為下一週 Week {target_week}")
                else:
                    target_week = curr_week_val
                    logging.info(f"[WEB_AGENT] 目標日期 {target_date} 預設對齊當前聯賽週數 Week {target_week}")

                scraped = page.evaluate(
                    """async ({ baseUrl, sportSlug, rawId, targetDate, targetWeek, currWeek }) => {
                        const teamRegex = new RegExp(`/${sportSlug}/${rawId}/(\\\\d+)$`);
                        const extractTablesText = (rootDoc) => {
                            const tables = Array.from(rootDoc.querySelectorAll('table'));
                            return tables.map(t => {
                                const rows = Array.from(t.querySelectorAll('tr'));
                                return rows.map(r => {
                                    const expandedCells = [];
                                    for (const c of Array.from(r.querySelectorAll('th, td'))) {
                                        const span = parseInt(c.getAttribute('colspan') || '1', 10) || 1;
                                        let cellText = c.innerText.replace(/\\s+/g, ' ').trim();
                                        const link = c.querySelector('a[href]');
                                        if (link) {
                                            try {
                                                const u = new URL(link.href, window.location.origin);
                                                const m = u.pathname.match(teamRegex);
                                                if (m) {
                                                    cellText = `${c.innerText.trim()} (team_id: ${m[1]})`;
                                                }
                                            } catch (e) {}
                                        }
                                        expandedCells.push(cellText);
                                        for (let i = 1; i < span; i++) {
                                            expandedCells.push('');
                                        }
                                    }
                                    return expandedCells.join(' | ');
                                }).filter(Boolean).join('\\n');
                            }).filter(Boolean);
                        };

                        // 1. 探索聯盟中所有真實隊伍 (team_id 與名稱)
                        const teamMap = new Map();
                        for (const a of Array.from(document.querySelectorAll('a[href]'))) {
                            try {
                                const u = new URL(a.href, window.location.origin);
                                const m = u.pathname.match(teamRegex);
                                if (m && !u.search) {
                                    const tid = m[1];
                                    const name = a.innerText.trim();
                                    if (name && name.toLowerCase() !== 'my team') {
                                        if (!teamMap.has(tid) || teamMap.get(tid).toLowerCase() === 'my team') {
                                            teamMap.set(tid, name);
                                        }
                                    }
                                }
                            } catch (e) {}
                        }

                        // 2. 探索目標週數的所有 Matchup 連結 (動態鎖定 targetWeek，若目標週非首頁當前週，主動抓取 targetWeek 的 matchups 模組)
                        let matchupSourceDoc = document;
                        if (Number(targetWeek) !== Number(currWeek)) {
                            try {
                                const mwResp = await fetch(`${baseUrl}?matchup_week=${targetWeek}&module=matchups&lhst=matchups`, { credentials: 'include' });
                                if (mwResp.ok) {
                                    const mwHtml = await mwResp.text();
                                    const mwParser = new DOMParser();
                                    matchupSourceDoc = mwParser.parseFromString(mwHtml, 'text/html');
                                }
                            } catch (e) {}
                        }

                        const matchupUrls = new Set();
                        for (const a of Array.from(matchupSourceDoc.querySelectorAll('a[href*="matchup"]'))) {
                            try {
                                const u = new URL(a.href, window.location.origin);
                                if (u.pathname.includes(`/${sportSlug}/${rawId}/matchup`) && u.searchParams.has('mid1') && u.searchParams.has('mid2')) {
                                    const m1 = Number(u.searchParams.get('mid1'));
                                    const m2 = Number(u.searchParams.get('mid2'));
                                    matchupUrls.add(`${baseUrl}/matchup?week=${targetWeek}&mid1=${Math.min(m1, m2)}&mid2=${Math.max(m1, m2)}`);
                                }
                            } catch (e) {}
                        }

                        const matchupList = Array.from(matchupUrls);
                        if (matchupList.length === 0) {
                            const tids = Array.from(teamMap.keys()).sort((a, b) => Number(a) - Number(b));
                            for (let i = 0; i < tids.length; i += 2) {
                                if (i + 1 < tids.length) {
                                    matchupList.push(`${baseUrl}/matchup?week=${targetWeek}&mid1=${tids[i]}&mid2=${tids[i+1]}`);
                                }
                            }
                        }

                        const countTodayActivePlayers = (rootDoc) => {
                            const nonStarting = new Set(['BN', 'IL', 'IL+', 'NA', 'DL', 'DL+']);
                            let activeCount = 0;
                            for (const t of Array.from(rootDoc.querySelectorAll('table'))) {
                                const headerRow = Array.from(t.querySelectorAll('thead tr, tr')).find(r =>
                                    Array.from(r.querySelectorAll('th')).some(th => th.innerText.trim() === 'Pos') &&
                                    Array.from(r.querySelectorAll('th')).some(th => th.innerText.trim() === 'Opp')
                                );
                                if (!headerRow) continue;
                                const headers = [];
                                for (const th of Array.from(headerRow.querySelectorAll('th'))) {
                                    const span = parseInt(th.getAttribute('colspan') || '1', 10) || 1;
                                    const txt = th.innerText.trim();
                                    for (let i = 0; i < span; i++) headers.push(txt);
                                }
                                const oppIdx = headers.indexOf('Opp');
                                const rows = Array.from(t.querySelectorAll('tbody tr'));
                                for (const r of rows) {
                                    const posCell = r.querySelector('td.pos') || r.querySelector('td:first-child');
                                    const playerCell = r.querySelector('td.player');
                                    if (!posCell || !playerCell) continue;
                                    const pos = posCell.innerText.trim();
                                    if (!pos || pos === 'Pos' || pos.includes('Total') || nonStarting.has(pos.toUpperCase())) continue;
                                    const playerText = playerCell.innerText.replace(/\\s+/g, ' ').trim();
                                    if (!playerText || /^\\(Empty\\)$/i.test(playerText)) continue;
                                    const allTds = Array.from(r.querySelectorAll('td'));
                                    const oppText = (oppIdx >= 0 && oppIdx < allTds.length) ? allTds[oppIdx].innerText.trim() : '';
                                    if (oppText && oppText !== '-') {
                                        activeCount++;
                                    }
                                }
                            }
                            return activeCount;
                        };

                        const fetchDocTables = async (url) => {
                            let lastErr = '';
                            for (let attempt = 1; attempt <= 3; attempt++) {
                                try {
                                    const resp = await fetch(url, { credentials: 'include' });
                                    if (!resp.ok) {
                                        lastErr = `HTTP ${resp.status}`;
                                        await new Promise(r => setTimeout(r, 600 * attempt));
                                        continue;
                                    }
                                    const html = await resp.text();
                                    const parser = new DOMParser();
                                    const doc = parser.parseFromString(html, 'text/html');
                                    const tables = extractTablesText(doc);
                                    if (tables.length === 0 && attempt < 3) {
                                        await new Promise(r => setTimeout(r, 600 * attempt));
                                        continue;
                                    }
                                    const titleEl = doc.querySelector('title');
                                    return {
                                        url,
                                        title: titleEl ? titleEl.innerText.trim() : '',
                                        tables,
                                        today_active_players: countTodayActivePlayers(doc)
                                    };
                                } catch (e) {
                                    lastErr = String(e);
                                    if (attempt < 3) {
                                        await new Promise(r => setTimeout(r, 600 * attempt));
                                    }
                                }
                            }
                            return { url, tables: [], today_active_players: null, error: lastErr };
                        };

                        const teamEntries = Array.from(teamMap.entries());
                        const dailyResults = await Promise.all(teamEntries.map(async ([tid, tname]) => {
                            const dailyUrl = `${baseUrl}/${tid}?date=${targetDate}`;
                            const res = await fetchDocTables(dailyUrl);
                            return {
                                team_id: tid,
                                team_name: tname,
                                url: dailyUrl,
                                today_active_players: res.today_active_players,
                                tables: res.tables
                            };
                        }));

                        return {
                            discovered_teams: teamEntries.map(([team_id, name]) => ({ team_id, name })),
                            home_tables: extractTablesText(document),
                            matchup_urls: matchupList,
                            daily_pages: dailyResults
                        };
                    }""",
                    {
                        "baseUrl": base_url,
                        "sportSlug": sport_slug,
                        "rawId": raw_id,
                        "targetDate": target_date,
                        "targetWeek": target_week,
                        "currWeek": curr_week_val,
                    }
                )

                if not scraped.get("discovered_teams"):
                    raise LeagueWebAuthError(f"聯盟 {league_id} 頁面未找到任何隊伍資料，可能尚未登入或無檢視權限。")

                scraped["week"] = target_week
                weekly_pages = []
                for m_url in scraped.get("matchup_urls", []):
                    loaded_m_data = None
                    for attempt in range(1, 4):
                        try:
                            page.goto(m_url, wait_until="domcontentloaded", timeout=35000)
                            page.wait_for_timeout(1000 + (attempt - 1) * 500)
                            m_data = page.evaluate("""({sportSlug, rawId}) => {
                                const teamRegex = new RegExp(`/${sportSlug}/${rawId}/(\\\\d+)$`);
                                const extractTablesText = (rootDoc) => {
                                    const tables = Array.from(rootDoc.querySelectorAll('table'));
                                    return tables.map(t => {
                                        const rows = Array.from(t.querySelectorAll('tr'));
                                        return rows.map(r => {
                                            const cells = Array.from(r.querySelectorAll('th, td'));
                                            return cells.map(c => {
                                                const link = c.querySelector('a[href]');
                                                if (link) {
                                                    try {
                                                        const u = new URL(link.href, window.location.origin);
                                                        const m = u.pathname.match(teamRegex);
                                                        if (m) {
                                                            return `${c.innerText.trim()} (team_id: ${m[1]})`;
                                                        }
                                                    } catch (e) {}
                                                }
                                                return c.innerText.replace(/\\s+/g, ' ').trim();
                                            }).join(' | ');
                                        }).filter(Boolean).join('\\n');
                                    }).filter(Boolean);
                                };
                                // 優先從 #remaining-games 區塊精確擷取，避免受到前綴 "20 Remaining 20/40" 貪婪正則截斷成 "0/40"
                                const rgEl = document.getElementById('remaining-games');
                                const gpSourceText = rgEl ? rgEl.innerText : document.body.innerText;
                                const gpMatch = gpSourceText.match(/(?:^|\\D)(\\d+\\/\\d+)\\s*Games Played\\s*(\\d+\\/\\d+)(?:\\D|$)/i);

                                // 精確提取對戰雙方各自的 team_id 與對應出賽人次 (games_played_map)
                                // 注意：必須從對戰統計表格 (table) 內部提取對戰雙方的連結，不可從整個 document 抓，否則第一個連結永遠是頂部導覽列的 "My Team"
                                const gpMap = {};
                                let matchedTeamIds = [];
                                try {
                                    for (const t of Array.from(document.querySelectorAll('table'))) {
                                        const tidsInTable = [];
                                        for (const a of Array.from(t.querySelectorAll('a[href]'))) {
                                            try {
                                                const u = new URL(a.href, window.location.origin);
                                                const m = u.pathname.match(teamRegex);
                                                if (m && !u.search && !tidsInTable.includes(m[1])) {
                                                    tidsInTable.push(m[1]);
                                                }
                                            } catch (e) {}
                                        }
                                        if (tidsInTable.length === 2) {
                                            matchedTeamIds = tidsInTable;
                                            break;
                                        }
                                    }
                                    if (gpMatch && matchedTeamIds.length === 2) {
                                        // 對戰表格第一列/左側隊伍對應左側出賽人次，第二列/右側隊伍對應右側出賽人次
                                        gpMap[matchedTeamIds[0]] = gpMatch[1];
                                        gpMap[matchedTeamIds[1]] = gpMatch[2];
                                    }
                                } catch (e) {}

                                return {
                                    url: window.location.href,
                                    title: document.title,
                                    tables: extractTablesText(document),
                                    games_played_banner: gpMatch ? `${gpMatch[1]} Games Played ${gpMatch[2]}` : '',
                                    games_played_map: gpMap,
                                    matched_team_ids: matchedTeamIds
                                };
                            }""", {"sportSlug": sport_slug, "rawId": raw_id})
                            if (
                                isinstance(m_data, dict)
                                and len(m_data.get("matched_team_ids") or []) == 2
                                and m_data.get("tables")
                            ):
                                loaded_m_data = m_data
                                break
                            logging.warning(
                                f"[WEB_AGENT] 對戰頁面 {m_url} 內容不完整 (第 {attempt}/3 次嘗試)，準備重試..."
                            )
                        except Exception as me:
                            logging.warning(f"[WEB_AGENT] 載入對戰頁面 {m_url} 失敗 (第 {attempt}/3 次嘗試): {me}")
                        if attempt < 3:
                            time.sleep(1.5 * attempt)

                    if loaded_m_data is not None:
                        weekly_pages.append(loaded_m_data)
                    else:
                        logging.error(f"[WEB_AGENT] 對戰頁面 {m_url} 重試 3 次後仍無法完整載入！")
                scraped["weekly_pages"] = weekly_pages

                # 在成功擷取所有頁面後，將更新後的 Session / Cookie 狀態回寫至檔案並同步給同管理員聯盟，達到自動滑動展延的效果
                if state_path and context:
                    try:
                        save_and_sync_league_storage_state(context, league_id)
                        logging.info(f"[WEB_AGENT] 戰績抓取成功，已自動展延聯盟 {league_id} 及其關聯聯盟之網頁 Session")
                    except Exception as refresh_err:
                        logging.warning(f"[WEB_AGENT] 自動展延 Session 失敗: {refresh_err}")

                return scraped
            finally:
                try:
                    if context:
                        context.close()
                except Exception:
                    pass
                try:
                    if browser:
                        browser.close()
                except Exception:
                    pass

    def _parse_with_gemini(self, scraped_data: dict, sport: str, target_date: str) -> dict:
        """將擷取到的網頁表格文字交由 Gemini AI 解析為結構化當日與當週戰績 JSON。"""
        if sport == "mlb":
            categories_hint = (
                'MLB 統計項目鍵名請提取網頁表格中出現的所有項目，如: "H/AB", "R", "H", "HR", "RBI", "SB", "BB", "AVG", "OPS", '
                '"IP", "W", "K", "ERA", "WHIP", "QS", "SV+H" 等'
            )
        else:
            categories_hint = (
                'NBA 統計項目鍵名請嚴格根據網頁表格標題列 (Table Header) 中**實際存在**的欄位動態提取，例如常規 9-CAT '
                '("FGM/FGA", "FG%", "FTM/FTA", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO")；'
                '若該聯盟表格標題列有自訂擴展項目（如 "DD", "A/T" 等）也請一併提取。\n'
                '重要規則：\n'
                '- 若網頁表格標題列有 DD, A/T (或 AST/TO) 等自訂項目，請務必萃取，切勿遺漏！\n'
                '- 【絕對禁止腦補欄位】若網頁表格標題列**沒有** A/T (或 AST/TO) 或 DD（例如標準 9-CAT 聯盟），**嚴禁自行用 AST 除以 TO 計算 A/T 或捏造任何表格標題不存在的欄位**！daily_stats 與 weekly_stats 的比分項目欄位必須與網頁表格標題完全一致。\n'
                '- FG% 與 FT% 請輸出 0~1 的小數（例如 0.485 代表 48.5%）。\n'
                '- 僅在網頁表格標題確實存在 A/T (或 AST/TO) 時，才輸出該數值比率（例如 2.45）。\n'
                '- "Today Player"：僅用於 daily_stats，請統計該隊當天排在先發名單（排除 BN 板凳、IL/IL+/NA 傷兵欄位，NBA 先發最多 10 人）且當天有比賽安排（Opp 欄位非空白）的球員人數（整數，如 5，無比賽填 0）。若 daily_pages 已提供 today_active_players 數值，請直接使用該數值。\n'
                '- "Game Player"：僅用於 weekly_stats，請提取對戰中的出賽人次（例如 "8/40" 或 "9/34"）。若網頁提供 games_played_map (例如 {"1": "8/40", "8": "9/34"})，請務必嚴格依據 team_id 填入對應隊伍的 "Game Player"；若未提供 games_played_map 但有 games_played_banner 如 "8/40 Games Played 9/34"，左側隊伍填 "8/40"，右側隊伍填 "9/34"；若無則填 "-"。'
            )

        system_instruction = f"""
你是一個精準的 Yahoo Fantasy 運動數據萃取 AI Agent。
請根據提供的已登入 Yahoo Fantasy 聯盟網頁表格內容，解析出全聯盟每一支隊伍的：
1. `daily_stats`（{target_date} 當日各隊總計數據，通常位於各隊頁面表格底部的 Total 列）
2. `weekly_stats`（本週 Matchup 對戰表中各隊的當週累計數據）

規則：
- {categories_hint}
- 【極重要】網頁對戰表 (Matchup) 與表格各行隊名皆已明確註明 "(team_id: X)"。在解析 `weekly_stats` 時，每一隊的數據必須嚴格對應其該行所標註的 `team_id`，絕不可將對戰雙方的數據反過來填寫！
- 若某隊當日沒有比賽或 Total 為 `-` / `0`，數值項目請填 `0`，命中率請填 `0.0`，投籃/打數請填 `"0/0"`。
- 請注意欄位劃分：`daily_stats` 僅包含 "Today Player"（不可包含 "Game Player"）；`weekly_stats` 僅包含 "Game Player"（不可包含 "Today Player"）。
- 若 `daily_pages` 表格中顯示 {target_date} 當天仍有任何一場比賽正在進行中（例如狀態顯示 Q1~Q4、Halftime、OT、Top/Bot 局數、In Progress 等尚未結束的狀態），請將 `"games_in_progress"` 設為 `true`，否則設為 `false`。
- 嚴格輸出以下 JSON 結構：
{{
  "games_in_progress": false,
  "daily_stats": {{
    "team_stats": [
      {{
        "team_id": "1",
        "name": "隊伍名稱",
        "stats": {{ ... }}
      }}
    ]
  }},
  "weekly_stats": {{
    "team_stats": [
      {{
        "team_id": "1",
        "name": "隊伍名稱",
        "stats": {{ ... }}
      }}
    ]
  }}
}}
"""
        discovered = scraped_data.get("discovered_teams", [])
        prompt = (
            f"目標日期: {target_date}\n"
            f"聯盟隊伍清單 (包含真實隊名與 team_id): {json.dumps(discovered, ensure_ascii=False)}\n"
            f"已知隊伍對應表 (team_mapping): {json.dumps(self.team_mapping, ensure_ascii=False)}\n"
            f"網頁擷取內容:\n{json.dumps(scraped_data, ensure_ascii=False)}"
        )

        logging.info(f"[WEB_AGENT] 正在呼叫 Gemini AI ({self.model_name}) 解析當日與當週戰績數據...")
        return self._call_gemini_json(prompt=prompt, system_instruction=system_instruction)

    def _normalize_team_list(self, team_stats: list, is_daily: bool = False, official_names: dict = None) -> list:
        """標準化各隊名稱對應、百分比格式與欄位別名，保留出賽人次並完全相容 process_stats_for_visual。"""
        normalized = []
        for idx, item in enumerate(team_stats or [], 1):
            tid = str(item.get("team_id") or idx)
            raw_name = item.get("name") or f"Team {tid}"
            official_name = str((official_names or {}).get(tid) or item.get("official_name") or raw_name)
            name = self.team_mapping.get(tid, raw_name)
            raw_stats = dict(item.get("stats") or {})

            # 確保 Today Player 與 Game Player 嚴格隔離：
            # 當日戰績 (is_daily=True) 僅保留 "Today Player"，絕不包含 "Game Player"
            # 當週戰績 (is_daily=False) 僅保留 "Game Player"，絕不包含 "Today Player"
            if is_daily:
                raw_stats.pop("Game Player", None)
                raw_stats.pop("GP_PLAYED", None)
                raw_stats.pop("GP_TOTAL", None)
                raw_stats.pop("GP_SORT_KEY", None)
                if "Today Player" not in raw_stats:
                    raw_stats["Today Player"] = 0
                else:
                    try:
                        raw_stats["Today Player"] = int(float(str(raw_stats["Today Player"]).strip()))
                    except (ValueError, TypeError):
                        raw_stats["Today Player"] = 0
            else:
                raw_stats.pop("Today Player", None)
                if "Game Player" not in raw_stats:
                    raw_stats["Game Player"] = "-"
                else:
                    raw_stats["Game Player"] = str(raw_stats["Game Player"]).strip()

            # 徹底剔除多餘的 FG, FT 鍵名與任何尾端星號 (如 FGM/A*, FTM/A*)，保留標準 FGM/A, FTM/A
            for k in list(raw_stats.keys()):
                if isinstance(k, str) and "*" in k:
                    clean_k = k.replace("*", "").strip()
                    val_k = raw_stats.pop(k)
                    if clean_k and clean_k not in raw_stats:
                        raw_stats[clean_k] = val_k

            raw_stats.pop("FG", None)
            raw_stats.pop("FT", None)

            if "FGM/FGA" in raw_stats and "FGM/A" not in raw_stats:
                raw_stats["FGM/A"] = raw_stats["FGM/FGA"]
            elif "FGM/A" in raw_stats and "FGM/FGA" not in raw_stats:
                raw_stats["FGM/FGA"] = raw_stats["FGM/A"]

            if "FTM/FTA" in raw_stats and "FTM/A" not in raw_stats:
                raw_stats["FTM/A"] = raw_stats["FTM/FTA"]
            elif "FTM/A" in raw_stats and "FTM/FTA" not in raw_stats:
                raw_stats["FTM/FTA"] = raw_stats["FTM/A"]

            if "3PTM" in raw_stats and "3PT" not in raw_stats:
                raw_stats["3PT"] = raw_stats["3PTM"]
            elif "3PT" in raw_stats and "3PTM" not in raw_stats:
                raw_stats["3PTM"] = raw_stats["3PT"]

            if "STL" in raw_stats and "ST" not in raw_stats:
                raw_stats["ST"] = raw_stats["STL"]

            if "AST/TO" in raw_stats and "A/T" not in raw_stats:
                raw_stats["A/T"] = raw_stats["AST/TO"]
            elif "A/TO" in raw_stats and "A/T" not in raw_stats:
                raw_stats["A/T"] = raw_stats["A/TO"]

            for pct_key in ("FG%", "FT%", "3PT%"):
                if pct_key in raw_stats:
                    val = raw_stats[pct_key]
                    if isinstance(val, str):
                        val_clean = val.strip()
                        if val_clean.endswith("%"):
                            try:
                                raw_stats[pct_key] = float(val_clean[:-1].strip()) / 100.0
                                continue
                            except ValueError:
                                raw_stats[pct_key] = 0.0
                                continue
                    try:
                        f_val = float(val)
                        if f_val > 1.0:
                            f_val = f_val / 100.0
                        raw_stats[pct_key] = f_val
                    except (ValueError, TypeError):
                        raw_stats[pct_key] = 0.0

            normalized.append({
                "team_id": tid,
                "name": name,
                "official_name": official_name,
                "stats": raw_stats
            })
        return normalized

    @staticmethod
    def _extract_week_and_matchups(scraped_data: dict) -> tuple[int | None, list[dict]]:
        """從網頁擷取結構中萃取週次 (week) 與對戰組合配對 (matchups)。"""
        from urllib.parse import urlparse, parse_qs

        if not isinstance(scraped_data, dict):
            return None, []

        week_num = scraped_data.get("week")
        try:
            week_num = int(week_num) if week_num is not None else None
        except (ValueError, TypeError):
            week_num = None

        matchups = []
        seen_pairs = set()

        def add_pair(t1, t2):
            s1, s2 = str(t1 or "").strip(), str(t2 or "").strip()
            if not s1 or not s2 or s1 == s2:
                return
            pair_key = tuple(sorted([s1, s2]))
            if pair_key not in seen_pairs:
                seen_pairs.add(pair_key)
                matchups.append({"team1_id": s1, "team2_id": s2})

        def parse_url_meta(url_str: str):
            nonlocal week_num
            if not url_str:
                return
            try:
                qs = parse_qs(urlparse(str(url_str)).query)
                if week_num is None and "week" in qs and qs["week"]:
                    week_num = int(qs["week"][0])
                if "mid1" in qs and "mid2" in qs and qs["mid1"] and qs["mid2"]:
                    add_pair(qs["mid1"][0], qs["mid2"][0])
            except Exception:
                pass

        for wp in scraped_data.get("weekly_pages", []) or []:
            if not isinstance(wp, dict):
                continue
            m_ids = wp.get("matched_team_ids")
            if isinstance(m_ids, list) and len(m_ids) == 2:
                add_pair(m_ids[0], m_ids[1])
            else:
                gp_map = wp.get("games_played_map")
                if isinstance(gp_map, dict) and len(gp_map) == 2:
                    keys = list(gp_map.keys())
                    add_pair(keys[0], keys[1])
            parse_url_meta(wp.get("url", ""))

        for m_url in scraped_data.get("matchup_urls", []) or []:
            parse_url_meta(m_url)

        return week_num, matchups

    @staticmethod
    def _normalize_stat_header(raw_header: str) -> str:
        """將網頁表格標題欄位名稱標準化（去除尾端星號並對齊系統標準鍵名）。"""
        h = str(raw_header or "").strip().rstrip("*").strip()
        upper = h.upper()
        alias_map = {
            "FGM/A": "FGM/FGA",
            "FGM/FGA": "FGM/FGA",
            "FTM/A": "FTM/FTA",
            "FTM/FTA": "FTM/FTA",
            "3PT": "3PTM",
            "3PTM": "3PTM",
            "STL": "ST",
            "ST": "ST",
            "AST/TO": "A/T",
            "A/TO": "A/T",
            "A/T": "A/T",
        }
        return alias_map.get(upper, h)

    @staticmethod
    def _parse_stat_cell(stat_key: str, raw_val: str):
        """將單一表格儲存格文字依欄位型別轉為標準數值或分數字串，杜絕 AI 幻覺。"""
        val = str(raw_val or "").strip().rstrip("*").strip()
        key_upper = str(stat_key or "").strip().upper()

        # 1. 投籃/打擊分母複合字串 (如 "15/27")
        if key_upper in ("FGM/FGA", "FGM/A", "FTM/FTA", "FTM/A", "H/AB"):
            if not val or val in ("-", "-/-", "--", "0"):
                return "0/0"
            return val

        # 2. 百分比欄位 (如 ".556" 或 "55.6%" -> 0.556)
        if "%" in key_upper:
            if not val or val in ("-", "-/-", "--"):
                return 0.0
            try:
                num = float(val.rstrip("%").strip())
                if num > 1.0:
                    num = num / 100.0
                return round(num, 4)
            except (ValueError, TypeError):
                return 0.0

        # 3. 浮點數比率欄位 (A/T, ERA, WHIP, AVG, OPS, IP 等)
        if key_upper in ("A/T", "AST/TO", "A/TO", "AVG", "OBP", "SLG", "OPS", "ERA", "WHIP", "IP", "K/9", "BB/9", "K/BB"):
            if not val or val in ("-", "-/-", "--") or "INF" in val.upper():
                return 0.0
            try:
                return round(float(val), 3)
            except (ValueError, TypeError):
                return 0.0

        # 4. 整數計數欄位 (PTS, REB, AST, ST, BLK, TO, 3PTM, DD, TD, R, HR, RBI, SB, W, K, QS, SV+H 等)
        if not val or val in ("-", "-/-", "--"):
            return 0
        try:
            return int(round(float(val)))
        except (ValueError, TypeError):
            return 0

    @classmethod
    def _extract_stats_from_scraped_tables(cls, scraped_data: dict) -> tuple[list[dict], list[dict]]:
        """
        直接從擷取的 Yahoo 網頁 DOM 表格文字中確定性解析各隊當日 (Starting Lineup Totals) 與當週 (Matchup Breakdown) 數據。
        不經過 LLM 猜測，100% 忠於網頁原始表格與 team_id 綁定。
        """
        import re

        if not isinstance(scraped_data, dict):
            return [], []

        non_stat_headers = {
            "", "TEAM", "POS", "PLAYERS", "PLAYER", "BATTERS", "PITCHERS",
            "OPP", "OPPONENT", "STATUS", "SCORE", "PRE-SEASON", "CURRENT",
            "% START", "% ROS", "% OWN", "OWN%", "ACTION", "MIN", "GP", "GS",
            "RANK", "FANTASY", "TIME", "TOTAL", "TOTALS", "STARTING LINEUP TOTALS",
            "CATEGORY", "WHAT IT MEANS", "WHO IS ELIGIBLE", "LEVEL", "RATING", "PERCENTILES"
        }

        team_row_re = re.compile(r"^(.*?)\s*\(team_id:\s*(\d+)\)\s*$")
        official_names = {}
        discovered_order = []
        for dt in scraped_data.get("discovered_teams") or []:
            if isinstance(dt, dict) and dt.get("team_id"):
                tid_str = str(dt["team_id"]).strip()
                tname_str = str(dt.get("name") or f"Team {tid_str}").strip()
                official_names[tid_str] = tname_str
                if tid_str not in discovered_order:
                    discovered_order.append(tid_str)

        # 1. 解析當週 Matchup 對戰表 (weekly_pages)
        weekly_by_tid: dict[str, dict] = {}
        weekly_order: list[str] = []
        for wp in scraped_data.get("weekly_pages") or []:
            if not isinstance(wp, dict):
                continue
            gp_map = wp.get("games_played_map") or {}
            for tbl in wp.get("tables") or []:
                lines = [ln.strip() for ln in str(tbl).splitlines() if ln.strip()]
                if len(lines) < 2:
                    continue
                stat_cols = []
                header_line_idx = -1
                for idx_ln, ln in enumerate(lines):
                    cells = [c.strip().rstrip("*").strip() for c in ln.split("|")]
                    if len(cells) >= 4 and cells[0].upper() == "TEAM":
                        upper_rest = {c.upper() for c in cells[1:] if c}
                        if upper_rest and not (upper_rest <= {"CATEGORY", "WHAT IT MEANS"}):
                            for col_i in range(1, len(cells)):
                                raw_h = cells[col_i]
                                if not raw_h or raw_h.upper() in non_stat_headers:
                                    continue
                                stat_cols.append((col_i, cls._normalize_stat_header(raw_h)))
                            if stat_cols:
                                header_line_idx = idx_ln
                                break
                if header_line_idx < 0 or not stat_cols:
                    continue

                for ln in lines[header_line_idx + 1:]:
                    row_cells = [c.strip() for c in ln.split("|")]
                    if not row_cells:
                        continue
                    m = team_row_re.match(row_cells[0])
                    if not m:
                        continue
                    raw_tname = m.group(1).strip()
                    tid = m.group(2).strip()
                    st_dict = {}
                    if tid in gp_map and gp_map[tid]:
                        st_dict["Game Player"] = gp_map[tid]
                    for col_i, st_key in stat_cols:
                        cell_val = row_cells[col_i] if col_i < len(row_cells) else ""
                        st_dict[st_key] = cls._parse_stat_cell(st_key, cell_val)
                    if st_dict:
                        weekly_by_tid[tid] = {
                            "team_id": tid,
                            "name": official_names.get(tid, raw_tname or f"Team {tid}"),
                            "stats": st_dict,
                        }
                        if tid not in weekly_order:
                            weekly_order.append(tid)

        # 2. 解析當日各隊數據表 (daily_pages -> Starting Lineup Totals)
        daily_by_tid: dict[str, dict] = {}
        daily_order: list[str] = []
        for dp in scraped_data.get("daily_pages") or []:
            if not isinstance(dp, dict):
                continue
            tid = str(dp.get("team_id") or "").strip()
            if not tid:
                continue
            tname = str(dp.get("team_name") or official_names.get(tid) or f"Team {tid}").strip()
            merged_daily_stats: dict = {}
            found_roster_table = False

            for tbl in dp.get("tables") or []:
                lines = [ln for ln in str(tbl).splitlines() if ln.strip()]
                if len(lines) < 2:
                    continue
                stat_cols = []
                header_line_idx = -1
                for idx_ln, ln in enumerate(lines):
                    cells = [c.strip().rstrip("*").strip() for c in ln.split("|")]
                    if (
                        len(cells) >= 6
                        and cells[0].upper() == "POS"
                        and any(h.upper() in ("PLAYERS", "PLAYER", "BATTERS", "PITCHERS") for h in cells[1:4])
                    ):
                        start_col = 2
                        for idx_h in range(1, min(4, len(cells))):
                            if cells[idx_h].upper() in ("PLAYERS", "PLAYER", "BATTERS", "PITCHERS"):
                                start_col = idx_h + 1
                                break
                        for col_i in range(start_col, len(cells)):
                            raw_h = cells[col_i]
                            if not raw_h or raw_h.upper() in non_stat_headers:
                                continue
                            stat_cols.append((col_i, cls._normalize_stat_header(raw_h)))
                        if stat_cols:
                            header_line_idx = idx_ln
                            header_cells_len = len(cells)
                            break
                if header_line_idx < 0 or not stat_cols:
                    continue

                found_roster_table = True
                total_row_cells = None
                for ln in reversed(lines[header_line_idx + 1:]):
                    rc = [c.strip() for c in ln.split("|")]
                    head_tokens = " ".join(rc[:4]).upper()
                    if "STARTING LINEUP TOTALS" in head_tokens or "TOTALS" in head_tokens or "TOTAL" in head_tokens:
                        total_row_cells = rc
                        break

                col_offset = (len(total_row_cells) - header_cells_len) if total_row_cells is not None else 0
                for col_i, st_key in stat_cols:
                    target_idx = col_i + col_offset
                    if total_row_cells is not None and 0 <= target_idx < len(total_row_cells):
                        merged_daily_stats[st_key] = cls._parse_stat_cell(st_key, total_row_cells[target_idx])
                    else:
                        merged_daily_stats.setdefault(st_key, cls._parse_stat_cell(st_key, "-"))

            if found_roster_table and merged_daily_stats:
                active_val = dp.get("today_active_players")
                merged_daily_stats["Today Player"] = active_val if (isinstance(active_val, int) and active_val >= 0) else 0
                daily_by_tid[tid] = {
                    "team_id": tid,
                    "name": tname,
                    "stats": merged_daily_stats,
                }
                if tid not in daily_order:
                    daily_order.append(tid)

        final_daily = [daily_by_tid[tid] for tid in (discovered_order or daily_order) if tid in daily_by_tid]
        final_weekly = [weekly_by_tid[tid] for tid in weekly_order if tid in weekly_by_tid]
        for tid in discovered_order:
            if tid in weekly_by_tid and tid not in weekly_order:
                final_weekly.append(weekly_by_tid[tid])

        return final_daily, final_weekly

    @staticmethod
    def _sanitize_stat_categories(league_id: str, scraped_data: dict, daily_raw: list, weekly_raw: list) -> None:
        """根據網頁表格實際標題與聯賽 metadata.json 雙重校驗，剔除 AI 自行腦補計算的擴展統計欄位（如在 9-CAT 聯賽誤生出 A/T）。"""
        custom_groups = [
            {"A/T", "AST/TO", "A/TO"},
            {"DD"},
            {"TD"},
            {"3PT%"},
            {"OREB"},
            {"DREB"},
        ]

        # 1. 讀取 metadata.json 的白名單（若有）
        meta_allowed = set()
        if league_id:
            try:
                meta_path = os.path.join(get_league_dir(league_id), "metadata.json")
                if os.path.exists(meta_path):
                    with open(meta_path, "r", encoding="utf-8") as f:
                        meta = json.load(f)
                    for cat in (meta.get("stat_categories") or []):
                        disp = str(cat.get("display_name") or "").strip().upper()
                        if disp:
                            meta_allowed.add(disp)
            except Exception:
                pass

        # 2. 僅從數據表格標題列（Pos | Player... 或 Team | ...）提取欄位 Token，避開底部 Abbreviation 說明表誤導
        table_tokens = set()
        if isinstance(scraped_data, dict):
            all_tables = []
            all_tables.extend(scraped_data.get("home_tables") or [])
            for dp in (scraped_data.get("daily_pages") or []):
                if isinstance(dp, dict):
                    all_tables.extend(dp.get("tables") or [])
            for wp in (scraped_data.get("weekly_pages") or []):
                if isinstance(wp, dict):
                    all_tables.extend(wp.get("tables") or [])
            for tbl in all_tables:
                lines = [ln.strip() for ln in str(tbl).splitlines() if ln.strip()]
                if lines and lines[0].upper().startswith("ABBREVIATION"):
                    continue
                for line in lines:
                    cells = [c.strip().rstrip("*").strip().upper() for c in line.split("|")]
                    if not cells:
                        continue
                    # 僅採計表格標題列或單行測試表格
                    if len(lines) == 1 or cells[0] in ("POS", "TEAM"):
                        for tok in cells:
                            if tok:
                                table_tokens.add(tok)

        daily_keys = {
            str(k).strip().upper()
            for t in (daily_raw or [])
            if isinstance(t, dict)
            for k in (t.get("stats") or {}).keys()
        }
        weekly_keys = {
            str(k).strip().upper()
            for t in (weekly_raw or [])
            if isinstance(t, dict)
            for k in (t.get("stats") or {}).keys()
        }

        for grp in custom_groups:
            grp_upper = {g.upper() for g in grp}
            should_strip = False

            # 若 metadata.json 已明確定義該聯賽的 stat_categories，且不包含此擴展欄位 -> 剔除
            if meta_allowed and not (grp_upper & meta_allowed):
                should_strip = True
            # 若網頁擷取表格非空，且表格標題中完全沒有出現此擴展欄位 -> 剔除
            elif table_tokens and not (grp_upper & table_tokens):
                should_strip = True
            # 若無表格與 metadata，但該擴展欄位僅單邊出現（例如 daily 沒有 A/T，weekly 卻被 AI 算出 A/T） -> 剔除
            elif daily_keys and weekly_keys and bool(grp_upper & daily_keys) != bool(grp_upper & weekly_keys):
                should_strip = True

            if should_strip:
                for team_list in (daily_raw or [], weekly_raw or []):
                    for t in team_list:
                        if not isinstance(t, dict) or not isinstance(t.get("stats"), dict):
                            continue
                        stats_dict = t["stats"]
                        for k in list(stats_dict.keys()):
                            if str(k).strip().upper() in grp_upper:
                                stats_dict.pop(k, None)

    @staticmethod
    def _validate_stats_integrity(
        league_id: str,
        date_str: str,
        scraped_data: dict,
        daily_list: list[dict],
        weekly_list: list[dict],
        week_num: int | None = None
    ) -> None:
        """
        數據合理性守門員 (Data Sanity Validator)：
        在寫入 JSON 與生成圖片前執行嚴格驗證，若發現漏抓對戰頁面、隊伍缺失、當週數據小於當日數據或整組歸零，
        立即拋出 StatsDataValidationError 阻斷存檔與推播。
        """
        counting_keys = (
            "PTS", "REB", "AST", "ST", "BLK", "TO", "3PTM", "DD", "TD",
            "R", "H", "HR", "RBI", "SB", "BB", "W", "K", "QS"
        )

        if isinstance(scraped_data, dict):
            matchup_urls = scraped_data.get("matchup_urls") or []
            weekly_pages = scraped_data.get("weekly_pages") or []
            if matchup_urls and len(weekly_pages) < len(matchup_urls):
                raise StatsDataValidationError(
                    f"聯賽 {league_id} 當週對戰頁面抓取不完整：預期 {len(matchup_urls)} 組對戰，僅載入 {len(weekly_pages)} 組。"
                )

            discovered_ids = {
                str(t.get("team_id")).strip()
                for t in (scraped_data.get("discovered_teams") or [])
                if isinstance(t, dict) and t.get("team_id")
            }
            if discovered_ids:
                daily_ids = {str(t.get("team_id")).strip() for t in (daily_list or []) if t.get("team_id")}
                weekly_ids = {str(t.get("team_id")).strip() for t in (weekly_list or []) if t.get("team_id")}
                missing_d = discovered_ids - daily_ids
                missing_w = discovered_ids - weekly_ids
                if missing_d or missing_w:
                    raise StatsDataValidationError(
                        f"聯賽 {league_id} 隊伍數據缺失：daily 缺少 {sorted(missing_d)}，weekly 缺少 {sorted(missing_w)}。"
                    )

        daily_by_id = {str(t.get("team_id")): t for t in (daily_list or []) if isinstance(t, dict) and t.get("team_id")}
        weekly_by_id = {str(t.get("team_id")): t for t in (weekly_list or []) if isinstance(t, dict) and t.get("team_id")}

        # 1. 日/週交叉校驗 (Daily <= Weekly 鐵律) 與 日/週欄位對稱校驗：
        #    - 當週累計計數項目絕不可能小於當日單日數據
        #    - 若當日數據已包含 FGM/FGA 或 FTM/FTA (或 MLB H/AB)，當週數據也必須具備該欄位，且不可全隊 Game Player 皆為 '-'
        all_weekly_gp_missing = bool(weekly_by_id) and all(
            str((wt.get("stats") or {}).get("Game Player", "-")).strip() in ("-", "", "None")
            for wt in weekly_by_id.values()
        )
        for tid, d_team in daily_by_id.items():
            w_team = weekly_by_id.get(tid)
            if not w_team:
                continue
            d_st = d_team.get("stats") or {}
            w_st = w_team.get("stats") or {}
            for req_key in ("FGM/FGA", "FTM/FTA", "H/AB"):
                if req_key in d_st and req_key not in w_st:
                    raise StatsDataValidationError(
                        f"聯賽 {league_id} 隊伍 {tid} ({d_team.get('name')}) 當週數據缺少必要欄位 '{req_key}' "
                        f"（疑似抓到首頁摘要表而非 Matchup 對戰詳情表）。"
                    )
            for ck in counting_keys:
                if ck in d_st and ck in w_st:
                    try:
                        d_val = float(d_st.get(ck) or 0)
                        w_val = float(w_st.get(ck) or 0)
                    except (ValueError, TypeError):
                        continue
                    if d_val > w_val:
                        raise StatsDataValidationError(
                            f"聯賽 {league_id} 隊伍 {tid} ({d_team.get('name')}) 數據異常："
                            f"當日 {ck}={d_val} 大於當週累計 {ck}={w_val}（疑似對戰頁面漏抓或歸零）。"
                        )

        if all_weekly_gp_missing and isinstance(scraped_data, dict) and (scraped_data.get("weekly_pages") or scraped_data.get("matchup_urls")):
            raise StatsDataValidationError(
                f"聯賽 {league_id} 所有隊伍的當週出賽人次 (Game Player) 皆為 '-'，判定對戰頁面未完整載入。"
            )

        # 2. 單組對戰漏抓歸零檢測：若同聯賽其他隊伍已有當週出賽人次 (如 "11/41") 與正數成績，
        #    任一隊伍不可同時出現 Game Player == "-" 且所有計數統計全為 0
        def _team_counting_sum(st: dict) -> float:
            total = 0.0
            for ck in counting_keys:
                if ck in st:
                    try:
                        total += float(st.get(ck) or 0)
                    except (ValueError, TypeError):
                        pass
            return total

        teams_with_valid_gp = [
            tid for tid, wt in weekly_by_id.items()
            if "/" in str((wt.get("stats") or {}).get("Game Player", ""))
            and _team_counting_sum(wt.get("stats") or {}) > 0
        ]
        if teams_with_valid_gp:
            for tid, wt in weekly_by_id.items():
                w_st = wt.get("stats") or {}
                gp_str = str(w_st.get("Game Player", "-")).strip()
                if gp_str in ("-", "", "None") and _team_counting_sum(w_st) == 0:
                    raise StatsDataValidationError(
                        f"聯賽 {league_id} 隊伍 {tid} ({wt.get('name')}) 當週對戰數據全為 0 且無出賽人次 (Game Player='{gp_str}')，判定為對戰漏抓異常。"
                    )

        # 3. 當日無賽事 / 全聯盟當日全 0 防護：
        #    若全聯盟所有隊伍在 daily_list 中的 Today Player 皆為 0 且所有計數統計總和皆為 0，
        #    代表該日無任何比賽或尚未開打，拋出 NoGamesScheduledError 阻斷寫入全 0 的 daily JSON 與圖片。
        if daily_by_id:
            all_daily_zero = True
            for dt in daily_by_id.values():
                d_st = dt.get("stats") or {}
                try:
                    tp_val = int(d_st.get("Today Player") or 0)
                except (ValueError, TypeError):
                    tp_val = 0
                if tp_val > 0 or _team_counting_sum(d_st) > 0:
                    all_daily_zero = False
                    break
            if all_daily_zero:
                raise NoGamesScheduledError(
                    f"聯賽 {league_id} 於美西 {date_str} 全聯盟當日出賽人數與計數數據皆為 0（判定當日無比賽），已阻斷全 0 戰績存檔。"
                )

        # 4. 同週歷史遞增校驗：若同週前一日已有存檔，今日當週累計數據不得退化歸零
        if week_num is not None and league_id:
            try:
                weekly_dir = get_league_weekly_dir(league_id)
                if os.path.exists(weekly_dir):
                    prev_files = sorted(
                        f for f in os.listdir(weekly_dir)
                        if f.startswith("date_") and f.endswith("_weekly.json") and f < f"date_{date_str}_weekly.json"
                    )
                    if prev_files:
                        prev_path = os.path.join(weekly_dir, prev_files[-1])
                        with open(prev_path, "r", encoding="utf-8") as pf:
                            prev_data = json.load(pf)
                        if isinstance(prev_data, dict) and prev_data.get("week") == week_num:
                            for pt in prev_data.get("team_stats") or []:
                                pt_id = str(pt.get("team_id") or "")
                                if pt_id in weekly_by_id:
                                    prev_sum = _team_counting_sum(pt.get("stats") or {})
                                    curr_sum = _team_counting_sum(weekly_by_id[pt_id].get("stats") or {})
                                    if prev_sum > 0 and curr_sum == 0:
                                        raise StatsDataValidationError(
                                            f"聯賽 {league_id} 隊伍 {pt_id} 同週 (Week {week_num}) 累計數據異常歸零 "
                                            f"(前日總計 {prev_sum} -> 今日 0)。"
                                        )
            except StatsDataValidationError:
                raise
            except Exception as hist_err:
                logging.debug(f"[WEB_AGENT] 歷史週數據比對略過: {hist_err}")

    def fetch_daily_and_weekly_stats(self, league_id: str = None, target_date: str = None) -> tuple[dict, dict]:
        """從已登入的 Yahoo Fantasy 網站擷取並透過 DOM 權威解析（搭配 AI 備援與嚴格完整性守門員）回傳 (daily_stats, weekly_stats)。"""
        lid = league_id or self.league_id
        if not lid:
            raise ValueError("LEAGUE_ID 未設定，無法抓取網頁戰績。")

        date_str = target_date or get_pacific_date()
        sport, _, _ = build_league_url(lid)

        # 前置賽事檢查：透過 ESPN Scoreboard API 檢查該美西日期是否有比賽，避免爬出全 0 戰績
        has_games = has_games_on_yahoo_date(sport, date_str)
        if has_games is False:
            raise NoGamesScheduledError(
                f"聯盟 {lid} 於美西 {date_str} (對應台灣 {yahoo_date_to_tw_date(date_str)}) 確定無任何比賽排程，跳過當日戰績抓取。"
            )

        max_attempts = 3
        last_validation_err = None

        for attempt in range(1, max_attempts + 1):
            try:
                scraped_data = self._scrape_league_pages(lid, date_str)
                if has_ongoing_games_in_scraped_data(scraped_data, sport):
                    raise GamesInProgressError(f"聯盟 {lid} 於 {date_str} 網頁顯示仍有比賽正在進行中。")

                # 優先使用 DOM 確定性表格解析，100% 避免 LLM 漏填或將缺頁隊伍填 0
                dom_daily, dom_weekly = self._extract_stats_from_scraped_tables(scraped_data)
                discovered_ids = {
                    str(t.get("team_id")).strip()
                    for t in (scraped_data.get("discovered_teams") or [])
                    if isinstance(t, dict) and t.get("team_id")
                }
                dom_daily_map = {str(t["team_id"]): t for t in dom_daily if t.get("stats")}
                dom_weekly_map = {str(t["team_id"]): t for t in dom_weekly if t.get("stats")}

                if discovered_ids and set(dom_daily_map.keys()) >= discovered_ids and set(dom_weekly_map.keys()) >= discovered_ids:
                    logging.info(
                        f"[WEB_AGENT] 已透過 DOM 權威表格解析完整取得聯盟 {lid} 共 {len(discovered_ids)} 隊之當日與當週數據。"
                    )
                    daily_raw = dom_daily
                    weekly_raw = dom_weekly
                else:
                    parsed = self._parse_with_gemini(scraped_data, sport, date_str)

                    if isinstance(parsed, list):
                        merged = {}
                        for item in parsed:
                            if isinstance(item, dict):
                                merged.update(item)
                        parsed = merged

                    if isinstance(parsed, dict) and parsed.get("games_in_progress") is True:
                        raise GamesInProgressError(f"聯盟 {lid} 於 {date_str} 仍有比賽正在進行中。")

                    daily_raw = (parsed.get("daily_stats") or {}).get("team_stats", [])
                    weekly_raw = (parsed.get("weekly_stats") or {}).get("team_stats", [])
                    if not daily_raw and not weekly_raw and not dom_daily and not dom_weekly:
                        raise LeagueWebAuthError(f"無法從聯賽 {lid} 網頁獲取有效數據，Yahoo 網頁登入狀態可能已失效。")

                    # 若部分隊伍有 DOM 確定性解析結果，以 DOM 權威數據覆寫 AI 結果
                    if dom_daily_map:
                        existing_d_ids = set()
                        for idx_d, t in enumerate(daily_raw):
                            tid = str(t.get("team_id") or "")
                            if tid in dom_daily_map:
                                daily_raw[idx_d] = dom_daily_map[tid]
                                existing_d_ids.add(tid)
                        for tid, dom_t in dom_daily_map.items():
                            if tid not in existing_d_ids:
                                daily_raw.append(dom_t)

                    if dom_weekly_map:
                        existing_w_ids = set()
                        for idx_w, t in enumerate(weekly_raw):
                            tid = str(t.get("team_id") or "")
                            if tid in dom_weekly_map:
                                weekly_raw[idx_w] = dom_weekly_map[tid]
                                existing_w_ids.add(tid)
                        for tid, dom_t in dom_weekly_map.items():
                            if tid not in existing_w_ids:
                                weekly_raw.append(dom_t)

                # 權威資料覆寫：以 DOM 直接解析的 today_active_players 與 games_played_map 強制校準
                try:
                    today_gp_map = {}
                    for dp in scraped_data.get("daily_pages", []):
                        tid = str(dp.get("team_id") or "")
                        val = dp.get("today_active_players")
                        if tid and isinstance(val, int) and val >= 0:
                            today_gp_map[tid] = val
                    if today_gp_map:
                        for t in daily_raw:
                            tid = str(t.get("team_id") or "")
                            if tid in today_gp_map:
                                stats = t.setdefault("stats", {})
                                stats["Today Player"] = today_gp_map[tid]
                except Exception as te:
                    logging.debug(f"[WEB_AGENT] 自動校準 Today Player 失敗: {te}")

                try:
                    gp_map_total = {}
                    for wp in scraped_data.get("weekly_pages", []):
                        m_map = wp.get("games_played_map") or {}
                        gp_map_total.update(m_map)
                    if gp_map_total:
                        for t in weekly_raw:
                            tid = str(t.get("team_id") or "")
                            if tid in gp_map_total and gp_map_total[tid]:
                                stats = t.setdefault("stats", {})
                                stats["Game Player"] = gp_map_total[tid]
                except Exception as ge:
                    logging.debug(f"[WEB_AGENT] 自動校準 games_played 失敗: {ge}")

                official_names_map = {}
                for d_team in scraped_data.get("discovered_teams", []) or []:
                    if isinstance(d_team, dict) and d_team.get("team_id") and d_team.get("name"):
                        official_names_map[str(d_team["team_id"])] = str(d_team["name"])

                week_num, matchup_pairs = self._extract_week_and_matchups(scraped_data)

                self._sanitize_stat_categories(lid, scraped_data, daily_raw, weekly_raw)

                normalized_daily = self._normalize_team_list(daily_raw, is_daily=True, official_names=official_names_map)
                normalized_weekly = self._normalize_team_list(weekly_raw, is_daily=False, official_names=official_names_map)

                # 若有明確對戰配對，將 weekly team_stats 按對戰組合兩兩相鄰排序
                if matchup_pairs and normalized_weekly:
                    team_by_id = {str(t.get("team_id")): t for t in normalized_weekly}
                    ordered_weekly = []
                    used_ids = set()
                    for pair in matchup_pairs:
                        t1_id = str(pair.get("team1_id", ""))
                        t2_id = str(pair.get("team2_id", ""))
                        if t1_id in team_by_id and t2_id in team_by_id and t1_id not in used_ids and t2_id not in used_ids:
                            ordered_weekly.append(team_by_id[t1_id])
                            ordered_weekly.append(team_by_id[t2_id])
                            used_ids.add(t1_id)
                            used_ids.add(t2_id)
                    for t in normalized_weekly:
                        tid = str(t.get("team_id"))
                        if tid not in used_ids:
                            ordered_weekly.append(t)
                    normalized_weekly = ordered_weekly

                # 執行嚴格的數據合理性與完整性守門員檢查
                self._validate_stats_integrity(
                    league_id=lid,
                    date_str=date_str,
                    scraped_data=scraped_data,
                    daily_list=normalized_daily,
                    weekly_list=normalized_weekly,
                    week_num=week_num
                )

                daily_stats = {"league_id": lid, "date": date_str, "team_stats": normalized_daily}
                weekly_stats = {"league_id": lid, "date": date_str, "team_stats": normalized_weekly}
                if week_num is not None:
                    daily_stats["week"] = week_num
                    weekly_stats["week"] = week_num
                if matchup_pairs:
                    weekly_stats["matchups"] = matchup_pairs

                try:
                    daily_dir = get_league_daily_dir(lid)
                    weekly_dir = get_league_weekly_dir(lid)
                    os.makedirs(daily_dir, exist_ok=True)
                    os.makedirs(weekly_dir, exist_ok=True)
                    with open(os.path.join(daily_dir, f"date_{date_str}.json"), "w", encoding="utf-8") as f:
                        json.dump(daily_stats, f, ensure_ascii=False, indent=2)
                    with open(os.path.join(weekly_dir, f"date_{date_str}_weekly.json"), "w", encoding="utf-8") as f:
                        json.dump(weekly_stats, f, ensure_ascii=False, indent=2)
                    logging.info(f"[WEB_AGENT] 已成功儲存數據表 JSON 快取 ({lid}, 日期: {date_str})")
                except Exception as e:
                    logging.warning(f"[WEB_AGENT] 儲存數據表 JSON 快取失敗: {e}")

                return daily_stats, weekly_stats

            except (LeagueWebAuthError, GamesInProgressError, NoGamesScheduledError):
                raise
            except StatsDataValidationError as val_err:
                last_validation_err = val_err
                logging.warning(
                    f"[WEB_AGENT] 聯盟 {lid} 戰績數據未通過完整性校驗 (第 {attempt}/{max_attempts} 次嘗試): {val_err}"
                )
                if attempt < max_attempts:
                    time.sleep(2.0 * attempt)
                    continue
                raise

        if last_validation_err:
            raise last_validation_err
        raise RuntimeError(f"聯盟 {lid} 戰績抓取失敗。")


def _split_mlb_stats(processed_list: list) -> tuple[list, list]:
    hitter_list = [c for c in processed_list if c.get("is_common") or not c.get("is_pitcher")]
    pitcher_list = [c for c in processed_list if c.get("is_common") or c.get("is_pitcher")]
    return hitter_list, pitcher_list


def clean_old_images(image_dir: str) -> None:
    """保留本地端圖片，與原本 API 儲存行為一致，不主動刪除歷史戰績圖檔。"""
    pass


def run_web_agent_push(league_id: str = None, reply_to: str = None, target_date: str = None, send_push: bool = False) -> None:
    """執行 AI Agent 網頁戰績抓取、渲染並儲存圖檔。預設 send_push=False 不主動發送 LINE 圖片，僅在用戶輸入 #戰績 時回傳。"""
    config = load_config()
    lid = league_id or os.getenv("LEAGUE_ID") or config.get("LEAGUE_ID")
    target_chat = reply_to or os.getenv("LINE_REPLY_TO")
    explicit_date = target_date or os.getenv("TEST_DATE")
    tw_today_str = explicit_date or get_today_tw_date()
    yahoo_date_str = tw_date_to_yahoo_date(tw_today_str)

    if not lid:
        raise ValueError("未指定 LEAGUE_ID，無法執行 AI Agent 戰績抓取。")

    sport, raw_id = parse_league_id(lid)

    # 前置防線：當未強制指定特定日期時，若當日無比賽，自動回退至最後一天有比賽的台灣日期，避免產生全為 0 的戰績圖
    if not explicit_date:
        resolved_tw_date = resolve_latest_active_tw_date(sport, tw_today_str, league_id=lid)
    else:
        resolved_tw_date = tw_today_str
    if resolved_tw_date != tw_today_str:
        logging.info(
            f"[WEB_AGENT] 檢測到台灣 {tw_today_str} (美西 {yahoo_date_str}) 無賽事排程，"
            f"自動改以最後一天比賽日 {resolved_tw_date} 作為目標戰績日期。"
        )
        tw_today_str = resolved_tw_date
        yahoo_date_str = tw_date_to_yahoo_date(tw_today_str)

        # 若該最後比賽日的戰績圖片與 JSON 快取皆已存在，無須重複啟動瀏覽器抓取
        image_dir = get_league_image_dir(lid)
        daily_json_path = os.path.join(get_league_daily_dir(lid), f"date_{yahoo_date_str}.json")
        weekly_json_path = os.path.join(get_league_weekly_dir(lid), f"date_{yahoo_date_str}_weekly.json")
        if sport == "mlb":
            imgs_ready = (
                os.path.exists(os.path.join(image_dir, f"{tw_today_str}_combined_hitter.png"))
                and os.path.exists(os.path.join(image_dir, f"{tw_today_str}_combined_pitcher.png"))
            )
        else:
            imgs_ready = os.path.exists(os.path.join(image_dir, f"{tw_today_str}_combined.png"))

        if imgs_ready and os.path.exists(daily_json_path) and os.path.exists(weekly_json_path) and not send_push:
            logging.info(f"[WEB_AGENT] 最後比賽日 {tw_today_str} 本地戰績圖檔與 JSON 快取皆已備妥，跳過重複抓取。")
            return

    mapping_file = get_league_team_mapping_path(lid)
    team_mapping = {}
    if os.path.exists(mapping_file):
        try:
            with open(mapping_file, "r", encoding="utf-8") as f:
                team_mapping = json.load(f)
        except Exception as e:
            logging.warning(f"[WEB_AGENT] 讀取 team_mapping 失敗: {e}")

    fetcher = WebAgentFetcher(
        team_mapping=team_mapping,
        league_id=lid,
        api_key=config.get("LLM_API_KEY"),
        model_name=DEFAULT_AGENT_MODEL
    )

    try:
        logging.info(f"[WEB_AGENT] 正在從網站擷取聯盟 {lid} 於美西 {yahoo_date_str} (對應台灣 {tw_today_str}) 的當日與當週戰績...")
        daily_stats, weekly_stats = fetcher.fetch_daily_and_weekly_stats(lid, yahoo_date_str)
    except GamesInProgressError as gip_err:
        from src.scheduler import postpone_daily_schedule
        postponed = postpone_daily_schedule(tw_today_str)
        logging.info(
            f"[WEB_AGENT] {gip_err} 自動更新順延半小時至 {postponed['next_update_time']} "
            f"（開放查詢時間順延至 {postponed['query_open_time']}）。"
        )
        return
    except NoGamesScheduledError as ng_err:
        fallback_tw = resolve_latest_active_tw_date(sport, tw_today_str, league_id=lid)
        if fallback_tw != tw_today_str:
            logging.info(
                f"[WEB_AGENT] {ng_err} 自動回退至最後一天比賽日 {fallback_tw} 抓取戰績..."
            )
            tw_today_str = fallback_tw
            yahoo_date_str = tw_date_to_yahoo_date(tw_today_str)
            try:
                daily_stats, weekly_stats = fetcher.fetch_daily_and_weekly_stats(lid, yahoo_date_str)
            except Exception as retry_err:
                logging.warning(f"[WEB_AGENT] 回退至最後比賽日 {fallback_tw} 抓取失敗: {retry_err}")
                return
        else:
            logging.info(f"[WEB_AGENT] {ng_err} 已跳過產出全 0 戰績圖檔。")
            return
    except StatsDataValidationError as val_err:
        logging.error(f"[WEB_AGENT] 聯盟 {lid} 數據未通過合理性與完整性守門員，已阻斷錯誤戰績圖檔產出: {val_err}")
        return
    except LeagueWebAuthError as auth_err:
        logging.warning(f"[WEB_AGENT] 網頁未登入或登入已失效: {auth_err}")
        try:
            from src.utils.security import security_manager
            security_manager.set_league_authorized(lid, False)
        except Exception:
            pass
        if target_chat and config.get("LINE_CHANNEL_ACCESS_TOKEN"):
            from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
            login_url = build_mobile_web_login_url(lid, target_chat)
            msg_text = (
                f"⚠️ 獲取聯賽 {lid} 資料失敗（Yahoo 網頁登入狀態已失效或尚未登入）。\n"
                f"請點擊以下連結重新登入 Yahoo 帳號：\n👉 {login_url}"
            )
            line_config = Configuration(access_token=config["LINE_CHANNEL_ACCESS_TOKEN"])
            with ApiClient(line_config) as api_client:
                MessagingApi(api_client).push_message(
                    PushMessageRequest(to=target_chat, messages=[TextMessage(text=msg_text)])
                )
        return

    daily_processed = process_stats_for_visual(daily_stats, league_id=lid)
    weekly_processed = process_stats_for_visual(weekly_stats, league_id=lid)

    image_dir = get_league_image_dir(lid)
    os.makedirs(image_dir, exist_ok=True)
    clean_old_images(image_dir)

    sport, raw_id = parse_league_id(lid)

    if sport == "mlb":
        daily_hitter, daily_pitcher = _split_mlb_stats(daily_processed)
        weekly_hitter, weekly_pitcher = _split_mlb_stats(weekly_processed)

        hitter_html = render_stats_html(daily_hitter, weekly_hitter)
        hitter_path = os.path.join(image_dir, f"{tw_today_str}_combined_hitter.png")
        capture_html_to_png(hitter_html, hitter_path)

        pitcher_html = render_stats_html(daily_pitcher, weekly_pitcher)
        pitcher_path = os.path.join(image_dir, f"{tw_today_str}_combined_pitcher.png")
        capture_html_to_png(pitcher_html, pitcher_path)
    else:
        combined_html = render_stats_html(daily_processed, weekly_processed)
        combined_path = os.path.join(image_dir, f"{tw_today_str}_combined.png")
        capture_html_to_png(combined_html, combined_path)
        logging.info(f"[WEB_AGENT] 暫存戰績圖檔已生成: {combined_path}")

    # 依使用者需求：關閉主動推播，僅快取圖檔供 #戰績 查詢回傳
    auto_push_enabled = send_push or (str(os.getenv("ENABLE_AUTO_PUSH", "")).lower() in ("true", "1", "yes"))
    if auto_push_enabled and target_chat and config.get("LINE_CHANNEL_ACCESS_TOKEN"):
        from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, ImageMessage
        from src.utils.bot_utils import get_public_server_url

        server_url = config.get("SERVER_URL")
        if not server_url or "localhost" in server_url or "127.0.0.1" in server_url:
            server_url = get_public_server_url()
        https_url = server_url.replace("http://", "https://")
        if not https_url.startswith("https://"):
            https_url = f"https://{https_url.lstrip('https://')}"

        if sport == "mlb":
            img_filenames = [f"{tw_today_str}_combined_hitter.png", f"{tw_today_str}_combined_pitcher.png"]
            img_urls = [f"{https_url}/images/mlb/{raw_id}/{f}" for f in img_filenames]
            messages = [ImageMessage(original_content_url=url, preview_image_url=url) for url in img_urls]
        else:
            img_filename = f"{tw_today_str}_combined.png"
            img_url = f"{https_url}/images/{sport}/{raw_id}/{img_filename}"
            messages = [ImageMessage(original_content_url=img_url, preview_image_url=img_url)]

        line_config = Configuration(access_token=config["LINE_CHANNEL_ACCESS_TOKEN"])
        with ApiClient(line_config) as api_client:
            messaging_api = MessagingApi(api_client)
            push_req = PushMessageRequest(to=target_chat, messages=messages)
            try:
                messaging_api.push_message(push_req)
                logging.info(f"[WEB_AGENT] 已成功向 {target_chat} 推播戰績圖片！")
            except Exception as e:
                logging.warning(f"[WEB_AGENT] 向 {target_chat} 推播戰績圖片失敗 (可能達每月額度上限或網路問題): {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    parser = argparse.ArgumentParser(description="Yahoo Fantasy Web AI Agent 工具")
    parser.add_argument("--login", action="store_true", help="開啟本地瀏覽器視窗以登入 Yahoo Fantasy 並保存狀態")
    parser.add_argument("--push", action="store_true", help="執行 AI Agent 抓取並主動推播戰績圖片至 LINE (預設關閉)")
    parser.add_argument("--fetch-only", action="store_true", help="僅執行 AI Agent 抓取與生成圖檔快取，不推播至 LINE")
    parser.add_argument("--league-id", type=str, default=None, help="指定聯盟 ID (如 nba.l.49432)")
    parser.add_argument("--reply-to", type=str, default=None, help="指定推播目標 LINE Chat ID")
    parser.add_argument("--date", type=str, default=None, help="指定日期 (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.login:
        login_interactively(args.league_id)
    elif args.push or args.fetch_only:
        run_web_agent_push(league_id=args.league_id, reply_to=args.reply_to, target_date=args.date, send_push=args.push)
    else:
        fetcher = WebAgentFetcher(league_id=args.league_id)
        d_stats, w_stats = fetcher.fetch_daily_and_weekly_stats(args.league_id, args.date)
        print(json.dumps({"daily": d_stats, "weekly": w_stats}, ensure_ascii=False, indent=2))
