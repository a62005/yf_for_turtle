import re
import os
import sys
import logging
from datetime import datetime
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage, ImageMessage
from .base_handler import BaseHandler

# Required project imports
from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.utils.time_utils import get_stats_rule_date, tw_date_to_yahoo_date
from src.utils.path_utils import get_league_dir, get_league_image_dir, parse_league_id


def _split_mlb_stats(processed_list):
    hitter_list = [c for c in processed_list if c.get("is_common") or not c.get("is_pitcher")]
    pitcher_list = [c for c in processed_list if c.get("is_common") or c.get("is_pitcher")]
    return hitter_list, pitcher_list


class StatsHandler(BaseHandler):
    """
    戰績查詢處理器：
    僅接受 '#戰績' 指令，暫時移除其他特定天數查詢。
    依時段規則判定查詢日期 (以台北時間為準)：
    - 每日 14:00 前：回傳前一天戰績 (例如 10/27 10:30 回傳 10/26)
    - 每日 14:00 後：回傳當天戰績 (例如 10/27 14:01 回傳 10/27)
    """

    def __init__(self):
        self.pattern = re.compile(r"^#戰績$")

    @property
    def instruction_desc(self) -> str:
        return """
- #戰績：查詢聯賽整體戰績（每日 14:00 前提供前一日戰績，14:00 後提供當日戰績）。
        """

    def parse_command(self, user_text: str) -> tuple[str | None, None]:
        if self.pattern.match(user_text.strip()):
            return "combined", None
        return None, None

    def can_handle(self, user_text: str) -> bool:
        return bool(self.pattern.match(user_text.strip()))

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip()
        cmd_type, _ = self.parse_command(user_text)
        if not cmd_type:
            return

        config = load_config()
        league_id = config.get("LEAGUE_ID")
        if not league_id:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text="⚠️ 尚未設定或未綁定聯盟 ID，請先使用 #設置 進行綁定。")]
                    )
                )
            return

        target_date = get_stats_rule_date()
        sport, raw_id = parse_league_id(league_id)
        image_dir = get_league_image_dir(league_id)

        is_mlb = (sport == "mlb")
        if is_mlb:
            hitter_name = f"{target_date}_combined_hitter.png"
            pitcher_name = f"{target_date}_combined_pitcher.png"
            h_path = os.path.join(image_dir, hitter_name)
            p_path = os.path.join(image_dir, pitcher_name)
            image_exists = os.path.exists(h_path) and os.path.exists(p_path)
        else:
            img_filename = f"{target_date}_combined.png"
            img_path = os.path.join(image_dir, img_filename)
            image_exists = os.path.exists(img_path)

        # 本地若無圖檔，嘗試現場以 WebAgentFetcher 即時擷取並生成
        if not image_exists:
            logging.info(f"[STATS] 本地尚未有 {target_date} 圖片，正在啟動 WebAgentFetcher 現場生成...")
            try:
                import json
                from src.web_agent_fetcher import WebAgentFetcher
                from src.visualizer.processor import process_stats_for_visual
                from src.visualizer.renderer import render_stats_html
                from src.visualizer.capturer import capture_html_to_png
                from src.utils.path_utils import get_league_team_mapping_path

                mapping_file = get_league_team_mapping_path(league_id)
                team_mapping = {}
                if os.path.exists(mapping_file):
                    try:
                        with open(mapping_file, "r", encoding="utf-8") as f:
                            team_mapping = json.load(f)
                    except Exception:
                        pass

                fetcher = WebAgentFetcher(team_mapping=team_mapping, league_id=league_id)
                yahoo_date = tw_date_to_yahoo_date(target_date)
                daily_stats, weekly_stats = fetcher.fetch_daily_and_weekly_stats(league_id, yahoo_date)
                daily_processed = process_stats_for_visual(daily_stats, league_id=league_id)
                weekly_processed = process_stats_for_visual(weekly_stats, league_id=league_id)

                os.makedirs(image_dir, exist_ok=True)
                if is_mlb:
                    daily_hitter, daily_pitcher = _split_mlb_stats(daily_processed)
                    weekly_hitter, weekly_pitcher = _split_mlb_stats(weekly_processed)
                    capture_html_to_png(render_stats_html(daily_hitter, weekly_hitter), h_path)
                    capture_html_to_png(render_stats_html(daily_pitcher, weekly_pitcher), p_path)
                    image_exists = os.path.exists(h_path) and os.path.exists(p_path)
                else:
                    combined_html = render_stats_html(daily_processed, weekly_processed)
                    capture_html_to_png(combined_html, img_path)
                    image_exists = os.path.exists(img_path)
            except Exception as fe:
                logging.error(f"[STATS] 現場生成戰績圖片失敗: {fe}")

        if image_exists:
            from src.utils.bot_utils import get_public_server_url
            server_url = get_public_server_url()
            https_url = server_url.replace("http://", "https://")
            if not https_url.startswith("https://"):
                https_url = f"https://{https_url.lstrip('https://')}"

            if is_mlb:
                img_urls = [
                    f"{https_url}/images/mlb/{raw_id}/{hitter_name}",
                    f"{https_url}/images/mlb/{raw_id}/{pitcher_name}"
                ]
            else:
                img_urls = [f"{https_url}/images/{sport}/{raw_id}/{img_filename}"]

            date_msg = TextMessage(text=f"戰績數據日期：{target_date}")
            messages = [date_msg] + [ImageMessage(original_content_url=url, preview_image_url=url) for url in img_urls]
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(reply_token=event.reply_token, messages=messages)
                )
        else:
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=f"戰績數據 ({target_date}) 正在更新中或尚未備妥，請稍後重試。")]
                    )
                )
