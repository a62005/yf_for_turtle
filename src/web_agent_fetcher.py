import os
import sys
import json
import logging
import argparse
from playwright.sync_api import sync_playwright
from src.config import load_config
from src.utils.path_utils import (
    BASE_DIR,
    DATA_DIR,
    parse_league_id,
    get_league_image_dir,
    get_league_team_mapping_path,
)
from src.utils.time_utils import get_pacific_date
from src.llm.gemini import GeminiProvider
from src.visualizer.processor import process_stats_for_visual
from src.visualizer.renderer import render_stats_html
from src.visualizer.capturer import capture_html_to_png
from src.web_login_bridge import (
    get_league_storage_state_path,
    is_page_authorized_for_league,
)
from src.handlers.web_set_league_id_handler import build_mobile_web_login_url


class LeagueWebAuthError(RuntimeError):
    """當瀏覽器未登入 Yahoo 或登入帳號無該聯盟檢視權限時拋出。"""
    pass


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
        self.model_name = model_name or config.get("LLM_MODEL") or os.getenv("LLM_MODEL") or "gemini-2.5-flash"

        if headless is None:
            env_headless = os.getenv("HEADLESS_BROWSER", "true").lower()
            self.headless = env_headless not in ("false", "0", "no")
        else:
            self.headless = headless

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

                scraped = page.evaluate(
                    """async ({ baseUrl, sportSlug, rawId, targetDate }) => {
                        const extractTablesText = (rootDoc) => {
                            const tables = Array.from(rootDoc.querySelectorAll('table'));
                            return tables.map(t => {
                                const rows = Array.from(t.querySelectorAll('tr'));
                                return rows.map(r => {
                                    const cells = Array.from(r.querySelectorAll('th, td'));
                                    return cells.map(c => c.innerText.replace(/\\s+/g, ' ').trim()).join(' | ');
                                }).filter(Boolean).join('\\n');
                            }).filter(Boolean);
                        };

                        // 1. 探索聯盟中所有真實隊伍 (team_id 與名稱)
                        const teamMap = new Map();
                        const teamRegex = new RegExp(`/${sportSlug}/${rawId}/(\\\\d+)$`);
                        for (const a of Array.from(document.querySelectorAll('a[href]'))) {
                            try {
                                const u = new URL(a.href, window.location.origin);
                                const m = u.pathname.match(teamRegex);
                                if (m && !u.search) {
                                    const tid = m[1];
                                    const name = a.innerText.trim();
                                    if (name && !teamMap.has(tid)) {
                                        teamMap.set(tid, name);
                                    }
                                }
                            } catch (e) {}
                        }

                        // 2. 探索本週所有 Matchup 連結
                        const matchupUrls = new Set();
                        for (const a of Array.from(document.querySelectorAll('a[href*="matchup"]'))) {
                            try {
                                const u = new URL(a.href, window.location.origin);
                                if (u.pathname.includes(`/${sportSlug}/${rawId}/matchup`) && u.searchParams.has('mid1') && u.searchParams.has('mid2')) {
                                    const m1 = Number(u.searchParams.get('mid1'));
                                    const m2 = Number(u.searchParams.get('mid2'));
                                    matchupUrls.add(`${baseUrl}/matchup?mid1=${Math.min(m1, m2)}&mid2=${Math.max(m1, m2)}`);
                                }
                            } catch (e) {}
                        }

                        const matchupList = Array.from(matchupUrls);
                        if (matchupList.length === 0) {
                            const tids = Array.from(teamMap.keys()).sort((a, b) => Number(a) - Number(b));
                            for (let i = 0; i < tids.length; i += 2) {
                                if (i + 1 < tids.length) {
                                    matchupList.push(`${baseUrl}/matchup?mid1=${tids[i]}&mid2=${tids[i+1]}`);
                                }
                            }
                        }

                        const fetchDocTables = async (url) => {
                            try {
                                const resp = await fetch(url, { credentials: 'include' });
                                if (!resp.ok) return { url, tables: [] };
                                const html = await resp.text();
                                const parser = new DOMParser();
                                const doc = parser.parseFromString(html, 'text/html');
                                const titleEl = doc.querySelector('title');
                                return {
                                    url,
                                    title: titleEl ? titleEl.innerText.trim() : '',
                                    tables: extractTablesText(doc)
                                };
                            } catch (e) {
                                return { url, tables: [], error: String(e) };
                            }
                        };

                        const weeklyResults = await Promise.all(matchupList.map(u => fetchDocTables(u)));

                        const teamEntries = Array.from(teamMap.entries());
                        const dailyResults = await Promise.all(teamEntries.map(async ([tid, tname]) => {
                            const dailyUrl = `${baseUrl}/${tid}?date=${targetDate}`;
                            const res = await fetchDocTables(dailyUrl);
                            return {
                                team_id: tid,
                                team_name: tname,
                                url: dailyUrl,
                                tables: res.tables
                            };
                        }));

                        return {
                            discovered_teams: teamEntries.map(([team_id, name]) => ({ team_id, name })),
                            home_tables: extractTablesText(document),
                            weekly_pages: weeklyResults,
                            daily_pages: dailyResults
                        };
                    }""",
                    {
                        "baseUrl": base_url,
                        "sportSlug": sport_slug,
                        "rawId": raw_id,
                        "targetDate": target_date
                    }
                )

                if not scraped.get("discovered_teams"):
                    raise LeagueWebAuthError(f"聯盟 {league_id} 頁面未找到任何隊伍資料，可能尚未登入或無檢視權限。")

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
        if not self.api_key:
            raise RuntimeError("未設定 LLM_API_KEY，無法啟動 Gemini AI Agent 解析網頁戰績。")

        provider = GeminiProvider(api_key=self.api_key, model_name=self.model_name)

        if sport == "mlb":
            categories_hint = (
                'MLB 統計項目鍵名請使用: "H/AB", "R", "H", "HR", "RBI", "SB", "BB", "AVG", "OPS", '
                '"IP", "W", "K", "ERA", "WHIP", "QS", "SV+H"'
            )
        else:
            categories_hint = (
                'NBA 統計項目鍵名請使用: "FGM/FGA", "FG%", "FTM/FTA", "FT%", "3PTM", '
                '"PTS", "REB", "AST", "ST", "BLK", "TO" (注意 FG% 與 FT% 請輸出 0~1 的小數，例如 0.485 代表 48.5%)'
            )

        system_instruction = f"""
你是一個精準的 Yahoo Fantasy 運動數據萃取 AI Agent。
請根據提供的已登入 Yahoo Fantasy 聯盟網頁表格內容，解析出全聯盟每一支隊伍的：
1. `daily_stats`（{target_date} 當日各隊總計數據，通常位於各隊頁面表格底部的 Total 列）
2. `weekly_stats`（本週 Matchup 對戰表中各隊的當週累計數據）

規則：
- {categories_hint}
- 若某隊當日沒有比賽或 Total 為 `-` / `0`，數值項目請填 `0`，命中率請填 `0.0`，投籃/打數請填 `"0/0"`。
- 不要包含 `Today Player` 或 `GP_PLAYED` / `Game Player`。
- 嚴格輸出以下 JSON 結構：
{{
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
        prompt = (
            f"目標日期: {target_date}\n"
            f"已知隊伍對應表 (team_mapping): {json.dumps(self.team_mapping, ensure_ascii=False)}\n"
            f"網頁擷取內容:\n{json.dumps(scraped_data, ensure_ascii=False)}"
        )

        logging.info("[WEB_AGENT] 正在呼叫 Gemini AI 解析當日與當週戰績數據...")
        return provider.generate_json(prompt=prompt, system_instruction=system_instruction, temperature=0.0)

    def _normalize_team_list(self, team_stats: list) -> list:
        """標準化各隊名稱對應、百分比格式與欄位別名，以完全相容 process_stats_for_visual。"""
        normalized = []
        for idx, item in enumerate(team_stats or [], 1):
            tid = str(item.get("team_id") or idx)
            raw_name = item.get("name") or f"Team {tid}"
            name = self.team_mapping.get(tid, raw_name)
            raw_stats = dict(item.get("stats") or {})

            # 移除出賽人次欄位（確保不顯示 Today Player / Game Player）
            raw_stats.pop("Today Player", None)
            raw_stats.pop("Game Player", None)
            raw_stats.pop("GP_PLAYED", None)
            raw_stats.pop("GP_TOTAL", None)

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

            for pct_key in ("FG%", "FT%"):
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
                "stats": raw_stats
            })
        return normalized

    def fetch_daily_and_weekly_stats(self, league_id: str = None, target_date: str = None) -> tuple[dict, dict]:
        """從已登入的 Yahoo Fantasy 網站擷取並透過 Gemini AI 解析回傳 (daily_stats, weekly_stats)。"""
        lid = league_id or self.league_id
        if not lid:
            raise ValueError("LEAGUE_ID 未設定，無法抓取網頁戰績。")

        date_str = target_date or get_pacific_date()
        sport, _, _ = build_league_url(lid)

        scraped_data = self._scrape_league_pages(lid, date_str)
        parsed = self._parse_with_gemini(scraped_data, sport, date_str)

        daily_raw = (parsed.get("daily_stats") or {}).get("team_stats", [])
        weekly_raw = (parsed.get("weekly_stats") or {}).get("team_stats", [])

        daily_stats = {"team_stats": self._normalize_team_list(daily_raw)}
        weekly_stats = {"team_stats": self._normalize_team_list(weekly_raw)}
        return daily_stats, weekly_stats


def _split_mlb_stats(processed_list: list) -> tuple[list, list]:
    hitter_list = [c for c in processed_list if c.get("is_common") or not c.get("is_pitcher")]
    pitcher_list = [c for c in processed_list if c.get("is_common") or c.get("is_pitcher")]
    return hitter_list, pitcher_list


def clean_old_images(image_dir: str) -> None:
    """清除目錄中所有舊的暫存 PNG 圖片，確保不保留任何歷史戰績圖檔。"""
    if not os.path.exists(image_dir):
        return
    for fname in os.listdir(image_dir):
        if fname.lower().endswith(".png"):
            fpath = os.path.join(image_dir, fname)
            try:
                os.remove(fpath)
            except OSError as e:
                logging.warning(f"Failed to remove old image {fpath}: {e}")


def run_web_agent_push(league_id: str = None, reply_to: str = None, target_date: str = None) -> None:
    """執行 AI Agent 網頁戰績抓取、渲染成原格式圖片並推播至 LINE（若未登入則推播手機登入網址）。"""
    config = load_config()
    lid = league_id or os.getenv("LEAGUE_ID") or config.get("LEAGUE_ID")
    target_chat = reply_to or os.getenv("LINE_REPLY_TO")
    today_str = target_date or os.getenv("TEST_DATE") or get_pacific_date()

    if not lid:
        raise ValueError("未指定 LEAGUE_ID，無法執行 AI Agent 戰績抓取。")

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
        model_name=config.get("LLM_MODEL")
    )

    try:
        logging.info(f"[WEB_AGENT] 正在從網站擷取聯盟 {lid} 於 {today_str} 的當日與當週戰績 (不落盤模式)...")
        daily_stats, weekly_stats = fetcher.fetch_daily_and_weekly_stats(lid, today_str)
    except LeagueWebAuthError as auth_err:
        logging.warning(f"[WEB_AGENT] 網頁未登入或無權限: {auth_err}")
        if target_chat and config.get("LINE_CHANNEL_ACCESS_TOKEN"):
            from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, TextMessage
            login_url = build_mobile_web_login_url(lid, target_chat)
            msg_text = (
                f"⚠️ 無法獲取聯賽 {lid} 戰績（尚未登入 Yahoo 或該帳號無此聯賽檢視權限）。\n"
                f"請點擊下方網址於手機完成 Yahoo 帳號登入：\n{login_url}"
            )
            line_config = Configuration(access_token=config["LINE_CHANNEL_ACCESS_TOKEN"])
            with ApiClient(line_config) as api_client:
                MessagingApi(api_client).push_message(
                    PushMessageRequest(to=target_chat, messages=[TextMessage(text=msg_text)])
                )
        return

    daily_processed = process_stats_for_visual(daily_stats)
    weekly_processed = process_stats_for_visual(weekly_stats)

    image_dir = get_league_image_dir(lid)
    os.makedirs(image_dir, exist_ok=True)
    clean_old_images(image_dir)

    sport, raw_id = parse_league_id(lid)

    if sport == "mlb":
        daily_hitter, daily_pitcher = _split_mlb_stats(daily_processed)
        weekly_hitter, weekly_pitcher = _split_mlb_stats(weekly_processed)

        hitter_html = render_stats_html(daily_hitter, weekly_hitter)
        hitter_path = os.path.join(image_dir, f"{today_str}_combined_hitter.png")
        capture_html_to_png(hitter_html, hitter_path)

        pitcher_html = render_stats_html(daily_pitcher, weekly_pitcher)
        pitcher_path = os.path.join(image_dir, f"{today_str}_combined_pitcher.png")
        capture_html_to_png(pitcher_html, pitcher_path)
    else:
        combined_html = render_stats_html(daily_processed, weekly_processed)
        combined_path = os.path.join(image_dir, f"{today_str}_combined.png")
        capture_html_to_png(combined_html, combined_path)
        logging.info(f"[WEB_AGENT] 暫存戰績圖檔已生成: {combined_path}")

    if target_chat and config.get("LINE_CHANNEL_ACCESS_TOKEN"):
        from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, PushMessageRequest, ImageMessage

        server_url = config.get("SERVER_URL") or "http://localhost:5001"
        https_url = server_url.replace("http://", "https://")
        if not https_url.startswith("https://"):
            https_url = f"https://{https_url.lstrip('https://')}"

        if sport == "mlb":
            img_filenames = [f"{today_str}_combined_hitter.png", f"{today_str}_combined_pitcher.png"]
            img_urls = [f"{https_url}/images/mlb/{raw_id}/{f}" for f in img_filenames]
            messages = [ImageMessage(original_content_url=url, preview_image_url=url) for url in img_urls]
        else:
            img_filename = f"{today_str}_combined.png"
            img_url = f"{https_url}/images/{sport}/{raw_id}/{img_filename}"
            messages = [ImageMessage(original_content_url=img_url, preview_image_url=img_url)]

        line_config = Configuration(access_token=config["LINE_CHANNEL_ACCESS_TOKEN"])
        with ApiClient(line_config) as api_client:
            messaging_api = MessagingApi(api_client)
            push_req = PushMessageRequest(to=target_chat, messages=messages)
            messaging_api.push_message(push_req)
        logging.info(f"[WEB_AGENT] 已成功向 {target_chat} 推播戰績圖片！")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    parser = argparse.ArgumentParser(description="Yahoo Fantasy Web AI Agent 工具")
    parser.add_argument("--login", action="store_true", help="開啟本地瀏覽器視窗以登入 Yahoo Fantasy 並保存狀態")
    parser.add_argument("--push", action="store_true", help="執行 AI Agent 抓取並推播戰績圖片至 LINE")
    parser.add_argument("--league-id", type=str, default=None, help="指定聯盟 ID (如 nba.l.49432)")
    parser.add_argument("--reply-to", type=str, default=None, help="指定推播目標 LINE Chat ID")
    parser.add_argument("--date", type=str, default=None, help="指定日期 (YYYY-MM-DD)")
    args = parser.parse_args()

    if args.login:
        login_interactively(args.league_id)
    elif args.push:
        run_web_agent_push(league_id=args.league_id, reply_to=args.reply_to, target_date=args.date)
    else:
        fetcher = WebAgentFetcher(league_id=args.league_id)
        d_stats, w_stats = fetcher.fetch_daily_and_weekly_stats(args.league_id, args.date)
        print(json.dumps({"daily": d_stats, "weekly": w_stats}, ensure_ascii=False, indent=2))
