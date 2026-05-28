import re
import os
import json
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, FlexMessage, FlexContainer, TextMessage, Configuration
from .base_handler import BaseHandler
from src.config import load_config
from src.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher
from src.utils.time_utils import get_pacific_datetime, get_fantasy_week

class MatchupHandler(BaseHandler):
    def __init__(self):
        self.pattern = re.compile(r"^#對戰\s+(.+)$")

    def _load_team_mapping(self) -> dict:
        config = load_config()
        mapping_file = config.get("TEAM_MAPPING_FILE", "team_mapping.json")
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load team mapping: {e}")
        return {}

    def can_handle(self, user_text: str) -> bool:
        match = self.pattern.match(user_text)
        if not match:
            return False
        nickname = match.group(1).strip()
        mapping = self._load_team_mapping()
        return nickname in mapping.values()

    def to_percent_str(self, val) -> str:
        try:
            f_val = float(val)
            if f_val == 0.0:
                return "-"
            return f"{f_val * 100:.1f}%"
        except (ValueError, TypeError):
            return "-"

    def to_val_str(self, val) -> str:
        if val is None:
            return "-"
        val_str = str(val).strip()
        if val_str == "":
            return "-"
            
        # Check if it's a valid fraction format like FGM/FGA or FTM/FTA
        if "/" in val_str:
            parts = val_str.split("/")
            if len(parts) == 2:
                try:
                    float(parts[0].strip())
                    float(parts[1].strip())
                    return val_str
                except ValueError:
                    return "-"
        
        # Check if it's a valid float/integer
        try:
            f_val = float(val_str)
            if f_val == 0.0:
                return "0"
            if f_val.is_integer():
                return str(int(f_val))
            return val_str
        except ValueError:
            return "-"

    def compare_stats(self, my_stats: dict, opp_stats: dict) -> dict:
        """比對 9-Cat 數據並統計比分"""
        cats_to_compare = [
            ("FG%", True), ("FT%", True), ("3PTM", True), ("PTS", True), 
            ("REB", True), ("AST", True), ("ST", True), ("BLK", True), ("TO", False)
        ]
        
        wins, losses, ties = 0, 0, 0
        details = {}

        # 1. 處理輔助行 (FGM/A, FTM/A) - 不進行比對
        details["FGM/A"] = {
            "my_val": self.to_val_str(my_stats.get("FGM/FGA")),
            "opp_val": self.to_val_str(opp_stats.get("FGM/FGA"))
        }
        details["FTM/A"] = {
            "my_val": self.to_val_str(my_stats.get("FTM/FTA")),
            "opp_val": self.to_val_str(opp_stats.get("FTM/FTA"))
        }

        # 2. 處理 9-Cat 指標比對
        for cat, is_larger_better in cats_to_compare:
            my_raw = my_stats.get(cat)
            opp_raw = opp_stats.get(cat)

            # 轉換為百分比或數值字串
            if cat in ["FG%", "FT%"]:
                my_val_str = self.to_percent_str(my_raw)
                opp_val_str = self.to_percent_str(opp_raw)
            else:
                my_val_str = self.to_val_str(my_raw)
                opp_val_str = self.to_val_str(opp_raw)

            # 安全轉換為 float 作為比較數值
            try:
                my_num = float(my_raw) if my_raw is not None else 0.0
            except ValueError:
                my_num = 0.0
            try:
                opp_num = float(opp_raw) if opp_raw is not None else 0.0
            except ValueError:
                opp_num = 0.0

            # 勝負判定
            if my_num == opp_num:
                status = "tie"
                ties += 1
            elif is_larger_better:
                if my_num > opp_num:
                    status = "my_win"
                    wins += 1
                else:
                    status = "opp_win"
                    losses += 1
            else:  # TO (越小越好)
                if my_num < opp_num:
                    status = "my_win"
                    wins += 1
                else:
                    status = "opp_win"
                    losses += 1

            details[cat] = {
                "status": status,
                "my_val": my_val_str,
                "opp_val": opp_val_str
            }

        return {
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "details": details
        }

    def format_matchup_stats(self, player_info: dict, comp_res: dict, week_str: str) -> dict:
        """組裝 11 行無 Footer 極簡風對稱 Flex Message 卡片"""
        details = comp_res["details"]
        wins = comp_res["wins"]
        losses = comp_res["losses"]

        # 1. 決定 Header 第三層比分的視覺樣式 (領先大黑，落後小灰)
        if wins > losses:
            my_score_style = {"size": "xl", "weight": "bold", "color": "#111111"}
            opp_score_style = {"size": "md", "weight": "regular", "color": "#aaaaaa"}
        elif wins < losses:
            my_score_style = {"size": "md", "weight": "regular", "color": "#aaaaaa"}
            opp_score_style = {"size": "xl", "weight": "bold", "color": "#111111"}
        else:
            my_score_style = {"size": "xl", "weight": "bold", "color": "#111111"}
            opp_score_style = {"size": "xl", "weight": "bold", "color": "#111111"}

        # 2. 建立 11 行指標數據的輔助渲染函式
        def build_row(label, is_aux=False):
            data = details[label]
            my_val = data["my_val"]
            opp_val = data["opp_val"]

            if is_aux:
                # 輔助指標：不受規則影響，統一常規灰色 13px
                return {
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {"type": "text", "text": my_val, "align": "start", "size": "sm", "color": "#777777"},
                        {"type": "text", "text": label, "align": "center", "size": "xs", "color": "#bbbbbb", "weight": "bold"},
                        {"type": "text", "text": opp_val, "align": "end", "size": "sm", "color": "#777777"}
                    ]
                }
            
            # 正式 9-Cat：領先黑色較大 (15px bold #111111)，落後灰色較小 (12px regular #aaaaaa)
            status = data.get("status")
            if status == "my_win":
                my_style = {"weight": "bold", "size": "md", "color": "#111111"}
                opp_style = {"weight": "regular", "size": "xs", "color": "#aaaaaa"}
            elif status == "opp_win":
                my_style = {"weight": "regular", "size": "xs", "color": "#aaaaaa"}
                opp_style = {"weight": "bold", "size": "md", "color": "#111111"}
            else: # 平手
                my_style = {"weight": "regular", "size": "sm", "color": "#555555"}
                opp_style = {"weight": "regular", "size": "sm", "color": "#555555"}

            # 將 ST 翻譯為 LINE 顯示的簡寫 STL
            display_label = "STL" if label == "ST" else label

            return {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {"type": "text", "text": my_val, "align": "start", "weight": my_style["weight"], "size": my_style["size"], "color": my_style["color"]},
                    {"type": "text", "text": display_label, "align": "center", "size": "xs", "color": "#bbbbbb", "weight": "bold"},
                    {"type": "text", "text": opp_val, "align": "end", "weight": opp_style["weight"], "size": opp_style["size"], "color": opp_style["color"]}
                ]
            }

        # 3. 依序建立 11 行指標數據的 rows
        rows = [
            build_row("FGM/A", is_aux=True),
            build_row("FG%"),
            build_row("FTM/A", is_aux=True),
            build_row("FT%"),
            build_row("3PTM"),
            build_row("PTS"),
            build_row("REB"),
            build_row("AST"),
            build_row("ST"),
            build_row("BLK"),
            build_row("TO")
        ]

        # 4. 組裝完整 bubble dictionary (無 Footer 設計，更加乾淨)
        return {
            "type": "bubble",
            "body": {
                "type": "box",
                "layout": "vertical",
                "spacing": "md",
                "contents": [
                    # 週次標題
                    {
                        "type": "text",
                        "text": f"WEEK {week_str} MATCHUP",
                        "weight": "bold",
                        "size": "xxs",
                        "color": "#cccccc",
                        "align": "center",
                        "margin": "xs"
                    },
                    # 【第一層】玩家中文暱稱 VS (最大粗體)
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": player_info["my_nickname"], "weight": "bold", "size": "xl", "color": "#111111"},
                            {"type": "text", "text": "VS", "align": "center", "weight": "bold", "size": "sm", "color": "#aaaaaa"},
                            {"type": "text", "text": player_info["opp_nickname"], "weight": "bold", "size": "xl", "color": "#111111", "align": "end"}
                        ]
                    },
                    # 【第二層】Fantasy 官方隊名 (較小灰色，無 VS)
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": player_info["my_official"], "size": "xxs", "color": "#999999"},
                            {"type": "text", "text": " ", "size": "xxs"},
                            {"type": "text", "text": player_info["opp_official"], "size": "xxs", "color": "#999999", "align": "end"}
                        ]
                    },
                    # 【第三層】即時比分對決 (領先大黑，落後小灰)
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "contents": [
                            {"type": "text", "text": str(wins), "align": "end", "weight": my_score_style["weight"], "size": my_score_style["size"], "color": my_score_style["color"]},
                            {"type": "text", "text": ":", "align": "center", "weight": "bold", "size": "md", "color": "#cccccc"},
                            {"type": "text", "text": str(losses), "align": "start", "weight": opp_score_style["weight"], "size": opp_score_style["size"], "color": opp_score_style["color"]}
                        ]
                    },
                    # 精緻對齊線
                    {
                        "type": "separator",
                        "color": "#eeeeee"
                    },
                    # 11 行指標 rows
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "sm",
                        "contents": rows
                    }
                ]
            }
        }

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        try:
            # 1. 取得指令內文並用 regex 解析 nickname
            user_text = event.message.text.strip()
            match = self.pattern.match(user_text)
            if not match:
                return
            nickname = match.group(1).strip()

            # 2. 讀取設定檔，取得 LEAGUE_ID
            config = load_config()
            league_id = config.get("LEAGUE_ID")
            if not league_id:
                logging.error("LEAGUE_ID is not configured in environment variables.")
                return

            # 3. 取得 team_mapping
            team_mapping = self._load_team_mapping()

            # 4. 初始化 YahooFetcher
            fetcher = YahooFantasyFetcher(team_mapping=team_mapping)

            # 5. 實時抓取聯盟 Meta 資訊
            metadata = fetcher.fetch_league_metadata(league_id)
            start_date = metadata.get("start_date")
            end_date = metadata.get("end_date")
            end_week = metadata.get("end_week") or 24

            if not start_date or not end_date:
                logging.error("Failed to fetch league start_date or end_date.")
                return

            # 6. 計算當前週數（採用美西時區進行時間比對，且有 offseason guard）
            current_dt = get_pacific_datetime()
            current_date_str = current_dt.strftime("%Y-%m-%d")

            if current_date_str > end_date:
                # offseason guard
                week = end_week
            else:
                week = get_fantasy_week(start_date, current_dt)
                if week > end_week:
                    week = end_week

            # 7. 抓取當週對戰列表 (fetch_matchups)
            matchups = fetcher.fetch_matchups(league_id, week)
            if not matchups:
                logging.error(f"No matchups found for week {week}.")
                return

            # 8. 搜尋目標暱稱對應的對戰 (role anchoring)
            target_matchup = None
            my_is_team1 = True
            for m in matchups:
                t1_name = m.get("team1", {}).get("name")
                t2_name = m.get("team2", {}).get("name")
                if t1_name == nickname:
                    target_matchup = m
                    my_is_team1 = True
                    break
                elif t2_name == nickname:
                    target_matchup = m
                    my_is_team1 = False
                    break

            if not target_matchup:
                logging.error(f"No matchup found for nickname: {nickname}")
                return

            # 9. 依據 Role Anchoring 區分我方與敵方
            if my_is_team1:
                my_team = target_matchup["team1"]
                opp_team = target_matchup["team2"]
            else:
                my_team = target_matchup["team2"]
                opp_team = target_matchup["team1"]

            player_info = {
                "my_nickname": my_team["name"],
                "my_official": my_team["official_name"],
                "opp_nickname": opp_team["name"],
                "opp_official": opp_team["official_name"]
            }

            # 10. 比對數據
            comp_res = self.compare_stats(my_team["stats"], opp_team["stats"])

            # 11. 產生 Flex Container 卡片
            flex_dict = self.format_matchup_stats(player_info, comp_res, str(week))

            # 12. 透過 LINE 回覆 Flex Message
            flex_container = FlexContainer.from_json(json.dumps(flex_dict))
            alt_text = f"WEEK {week} MATCHUP - {player_info['my_nickname']} vs {player_info['opp_nickname']}"
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[FlexMessage(alt_text=alt_text, contents=flex_container)]
                    )
                )
        except Exception as e:
            logging.error(f"Failed to execute MatchupHandler: {e}", exc_info=True)
            # Quiet exit
            return

