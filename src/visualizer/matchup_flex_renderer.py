from src.services.fantasy_stat_toolkit import FantasyStatToolkit
from src.visualizer.flex_builder import (
    build_all_play_score_card,
    build_matchup_comparison_card,
)
from src.visualizer.processor import is_mlb_pitcher_stat


class MatchupFlexRenderer:
    """
    獨立的 LINE Flex Message 對戰與全聯盟模擬比分卡片渲染器（遵循 ADR-0002）。
    專職負責將 #對戰 (Scheduled Matchup) 與 #比分 (All-Play Score Simulation) 的計算結果組裝為 Flex Bubble。
    """

    DISPLAY_ALIASES = {"FGM/FGA": "FGM/A", "FTM/FTA": "FTM/A"}

    def __init__(self, toolkit: FantasyStatToolkit | None = None) -> None:
        self.toolkit = toolkit or FantasyStatToolkit()

    def render_matchup_card(
        self,
        player_info: dict,
        comp_res: dict,
        week_str: str,
        stat_categories: list | None = None,
        is_mlb: bool = False,
    ) -> dict:
        details = comp_res["details"]
        wins = comp_res["wins"]
        losses = comp_res["losses"]

        subtitle_dict = {
            "my_nickname": player_info["my_nickname"],
            "my_official": player_info["my_official"],
            "opp_nickname": player_info["opp_nickname"],
            "opp_official": player_info["opp_official"],
            "wins": wins,
            "losses": losses,
        }

        if stat_categories:
            comparison_rows = []
            for cat in stat_categories:
                disp = cat["display_name"]
                label = self.DISPLAY_ALIASES.get(disp, disp)

                my_val = details[disp]["my_val"]
                opp_val = details[disp]["opp_val"]
                status = details[disp].get("status")

                stat_id = str(cat.get("stat_id", ""))
                is_aux = self.toolkit.is_auxiliary_category(cat)
                is_pitcher = is_mlb_pitcher_stat(stat_id, disp)
                comparison_rows.append((label, my_val, opp_val, status, is_aux, is_pitcher))
        else:
            comparison_rows = [
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
                ("TO", details["TO"]["my_val"], details["TO"]["opp_val"], details["TO"]["status"], False, False),
            ]
            standard_row_keys = {"FGM/A", "FG%", "FTM/A", "FT%", "3PTM", "PTS", "REB", "AST", "ST", "BLK", "TO"}
            for k, v in details.items():
                if k not in standard_row_keys:
                    comparison_rows.append((k, v["my_val"], v["opp_val"], v.get("status"), "status" not in v, False))

        return build_matchup_comparison_card(
            title=f"WEEK {week_str} MATCHUP",
            subtitle=subtitle_dict,
            comparison_rows=comparison_rows,
            is_mlb=is_mlb,
        )

    def render_all_play_score_card(
        self,
        week_str: str | int,
        player_info: dict,
        win_rows: list[dict],
        tie_rows: list[dict],
        loss_rows: list[dict],
    ) -> dict:
        return build_all_play_score_card(
            title=f"WEEK {week_str} ALL-PLAY",
            player_info=player_info,
            win_rows=win_rows,
            tie_rows=tie_rows,
            loss_rows=loss_rows,
        )
