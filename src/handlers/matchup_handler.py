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
        if val is None or str(val) == "0" or str(val) == "0.0":
            return "-"
        return str(val)

    def compare_stats(self, my_stats: dict, opp_stats: dict) -> dict:
        """比對 9-Cat 數據並統計比分"""
        cats_to_compare = [
            ("FG%", True), ("FT%", True), ("3PTM", True), ("PTS", True), 
            ("REB", True), ("AST", True), ("STL", True), ("BLK", True), ("TO", False)
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
                if my_num == 0.0 and opp_num == 0.0:
                    status = "tie"
                    ties += 1
                elif my_num == 0.0:
                    status = "my_win"
                    wins += 1
                elif opp_num == 0.0:
                    status = "opp_win"
                    losses += 1
                elif my_num < opp_num:
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

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        pass
