import re
import logging
from typing import Any
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler
from src.config import load_config
from src.fetcher import YahooFantasyFetcher
from src.utils.time_utils import get_pacific_datetime, get_fantasy_week
from src.visualizer.flex_builder import build_matchup_comparison_card
from src.visualizer.processor import is_mlb_pitcher_stat



class MatchupHandler(BaseHandler):
    def __init__(self) -> None:
        self.pattern = re.compile(r"^#對戰(?:\s+(.+))?$")

    @property
    def instruction_desc(self) -> str:
        return """
- #對戰：顯示對戰比分查詢的玩家選單。
- #對戰 <玩家名稱>：查詢特定玩家的本週對戰比分。
        """

    def can_handle(self, user_text: str) -> bool:
        user_text = user_text.strip()
        match = self.pattern.match(user_text)
        if not match:
            return False
            
        nickname_raw = match.group(1)
        if not nickname_raw:
            return True
            
        nickname = nickname_raw.strip()
        if not nickname:
            return True
            
        mapping = self._load_team_mapping()
        return nickname in mapping.values()

    def to_percent_str(self, val: Any) -> str:
        try:
            f_val = float(val)
            if f_val == 0.0:
                return "-"
            return f"{f_val * 100:.1f}%"
        except (ValueError, TypeError):
            return "-"

    def to_val_str(self, val: Any) -> str:
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

    def compare_stats(self, my_stats: dict, opp_stats: dict, stat_categories: list = None) -> dict:
        """比對數據並統計比分"""
        if not stat_categories:
            # Fallback to NBA 9-cat
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
        else:
            # MLB / 動態比對邏輯
            wins, losses, ties = 0, 0, 0
            details = {}
            for cat in stat_categories:
                disp = cat["display_name"]
                sort_order = cat.get("sort_order")
                is_only_display = (sort_order is None) or (sort_order not in [0, 1])

                my_raw = my_stats.get(disp)
                opp_raw = opp_stats.get(disp)

                if "%" in disp:
                    my_val_str = self.to_percent_str(my_raw)
                    opp_val_str = self.to_percent_str(opp_raw)
                else:
                    my_val_str = self.to_val_str(my_raw)
                    opp_val_str = self.to_val_str(opp_raw)

                if is_only_display:
                    details[disp] = {
                        "my_val": my_val_str,
                        "opp_val": opp_val_str
                    }
                    continue

                is_larger_better = (sort_order == 1)

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
                else:  # 越小越好 (sort_order=0, 如 ERA, WHIP, TO)
                    if my_num < opp_num:
                        status = "my_win"
                        wins += 1
                    else:
                        status = "opp_win"
                        losses += 1

                details[disp] = {
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

    def format_matchup_stats(self, player_info: dict, comp_res: dict, week_str: str, stat_categories: list = None, is_mlb: bool = False) -> dict:
        """組裝 Matchup Flex Message 卡片"""
        details = comp_res["details"]
        wins = comp_res["wins"]
        losses = comp_res["losses"]

        subtitle_dict = {
            "my_nickname": player_info["my_nickname"],
            "my_official": player_info["my_official"],
            "opp_nickname": player_info["opp_nickname"],
            "opp_official": player_info["opp_official"],
            "wins": wins,
            "losses": losses
        }

        if stat_categories:
            DISPLAY_ALIASES = {"FGM/FGA": "FGM/A", "FTM/FTA": "FTM/A"}
            comparison_rows = []
            for cat in stat_categories:
                disp = cat["display_name"]
                label = DISPLAY_ALIASES.get(disp, disp)
                
                my_val = details[disp]["my_val"]
                opp_val = details[disp]["opp_val"]
                status = details[disp].get("status")
                
                sort_order = cat.get("sort_order")
                is_aux = (sort_order is None) or (sort_order not in [0, 1])
                
                stat_id = cat.get("stat_id", "")
                is_pitcher = is_mlb_pitcher_stat(stat_id, disp)
                
                comparison_rows.append((label, my_val, opp_val, status, is_aux, is_pitcher))
        else:
            comparison_rows = [
                # (指標名稱, 左側數值, 右側數值, 勝負狀態, 是否為輔助行, is_pitcher)
                ("FGM/A", details["FGM/A"]["my_val"], details["FGM/A"]["opp_val"], None, True, False),
                ("FG%", details["FG%"]["my_val"], details["FG%"]["opp_val"], details["FG%"]["status"], False, False),
                ("FTM/A", details["FTM/A"]["my_val"], details["FTM/A"]["opp_val"], None, True, False),
                ("FT%", details["FT%"]["my_val"], details["FT%"]["opp_val"], details["FT%"]["status"], False, False),
                ("3PTM", details["3PTM"]["my_val"], details["3PTM"]["opp_val"], details["3PTM"]["status"], False, False),
                ("PTS", details["PTS"]["my_val"], details["PTS"]["opp_val"], details["PTS"]["status"], False, False),
                ("REB", details["REB"]["my_val"], details["REB"]["opp_val"], details["REB"]["status"], False, False),
                ("AST", details["AST"]["my_val"], details["AST"]["opp_val"], details["AST"]["status"], False, False),
                ("ST", details["ST"]["my_val"], details["ST"]["opp_val"], details["ST"]["status"], False, False),
                ("BLK", details["BLK"]["my_val"], details["BLK"]["opp_val"], details["BLK"]["status"], False, False),
                ("TO", details["TO"]["my_val"], details["TO"]["opp_val"], details["TO"]["status"], False, False)
            ]

        return build_matchup_comparison_card(
            title=f"WEEK {week_str} MATCHUP",
            subtitle=subtitle_dict,
            comparison_rows=comparison_rows,
            is_mlb=is_mlb
        )

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        try:
            # 1. 取得指令內文並用 regex 解析 nickname
            user_text = event.message.text.strip()
            match = self.pattern.match(user_text)
            if not match:
                return
            
            nickname_raw = match.group(1)
            nickname = nickname_raw.strip() if nickname_raw else ""
            
            if not nickname:
                self.reply_player_list(event, configuration, is_matchup=True)
                return

            # 2. 讀取設定檔，取得 LEAGUE_ID
            config = load_config()
            league_id = config.get("LEAGUE_ID")
            if not league_id:
                logging.error("LEAGUE_ID is not configured in environment variables.")
                return

            # 3. 取得 team_mapping
            team_mapping = self._load_team_mapping()

            # 4. 初始化 YahooFetcher
            fetcher = YahooFantasyFetcher(team_mapping=team_mapping, league_id=league_id)

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
            from src.utils.path_utils import parse_league_id
            sport, _ = parse_league_id(league_id)
            is_mlb = (sport == "mlb")
            stat_categories = metadata.get("stat_categories")

            comp_res = self.compare_stats(my_team["stats"], opp_team["stats"], stat_categories=stat_categories)

            # 11. 產生 Flex Container 卡片
            flex_dict = self.format_matchup_stats(player_info, comp_res, str(week), stat_categories=stat_categories, is_mlb=is_mlb)

            # 12. 透過 LINE 回覆 Flex Message
            alt_text = f"WEEK {week} MATCHUP - {player_info['my_nickname']} vs {player_info['opp_nickname']}"
            self.reply_flex(event, configuration, alt_text, flex_dict)
        except Exception as e:
            logging.error(f"Failed to execute MatchupHandler: {e}", exc_info=True)
            # Quiet exit
            return



