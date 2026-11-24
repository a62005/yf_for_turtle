from src.services.fantasy_stat_toolkit import FantasyStatToolkit
from src.visualizer.flex_builder import build_stats_list_card
from src.visualizer.processor import is_mlb_pitcher_stat


class UserStatsFlexRenderer:
    """
    獨立的 LINE Flex Message 玩家數據卡片渲染器（遵循 ADR-0002）。
    專職負責將 #玩家 的當日與當週統計數據組裝為 Flex Bubble（含 NBA 與 MLB 投打分表）。
    """

    DISPLAY_ALIASES = {"FGM/FGA": "FGM/A", "FTM/FTA": "FTM/A", "3PTM": "3PM"}

    def __init__(self, toolkit: FantasyStatToolkit | None = None) -> None:
        self.toolkit = toolkit or FantasyStatToolkit()

    def build_stat_rows(
        self,
        stats: dict,
        stat_categories: list | None = None,
    ) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        if stat_categories:
            for cat in stat_categories:
                disp = cat["display_name"]
                label = self.DISPLAY_ALIASES.get(disp, disp)
                val = self.toolkit.get_stat_raw(stats, disp)
                rows.append(
                    (
                        label,
                        self.toolkit.format_stat_value(disp, val, integer_at_ratio_as_int=True),
                    )
                )
        else:
            fgm_a = self.toolkit.get_stat_raw(stats, "FGM/FGA") or "0/0"
            fg_pct = self.toolkit.to_percent_str(self.toolkit.get_stat_raw(stats, "FG%") or "0.0")
            ftm_a = self.toolkit.get_stat_raw(stats, "FTM/FTA") or "0/0"
            ft_pct = self.toolkit.to_percent_str(self.toolkit.get_stat_raw(stats, "FT%") or "0.0")
            rows = [
                ("FGM/A", str(fgm_a)),
                ("FG%", fg_pct),
                ("FTM/A", str(ftm_a)),
                ("FT%", ft_pct),
                ("3PM", str(self.toolkit.get_stat_raw(stats, "3PTM") or "0")),
                ("PTS", str(self.toolkit.get_stat_raw(stats, "PTS") or "0")),
                ("REB", str(self.toolkit.get_stat_raw(stats, "REB") or "0")),
                ("AST", str(self.toolkit.get_stat_raw(stats, "AST") or "0")),
                ("STL", str(self.toolkit.get_stat_raw(stats, "ST") or "0")),
                ("BLK", str(self.toolkit.get_stat_raw(stats, "BLK") or "0")),
                ("TO", str(self.toolkit.get_stat_raw(stats, "TO") or "0")),
            ]
            for extra_key in self.toolkit.extract_extra_custom_keys(stats):
                raw_v = self.toolkit.get_stat_raw(stats, extra_key)
                rows.append(
                    (
                        extra_key,
                        self.toolkit.format_stat_value(extra_key, raw_v, integer_at_ratio_as_int=True),
                    )
                )
        return rows

    def render_user_stats_card(
        self,
        player_info: dict,
        daily_stats: dict,
        weekly_stats: dict,
        date_str: str,
        week_str: str,
        stat_categories: list | None = None,
    ) -> dict:
        has_mlb_split = False
        hitter_cats: list[dict] = []
        pitcher_cats: list[dict] = []
        if stat_categories:
            for cat in stat_categories:
                stat_id = cat.get("stat_id", "")
                disp = cat.get("display_name", "")
                if is_mlb_pitcher_stat(stat_id, disp):
                    pitcher_cats.append(cat)
                else:
                    hitter_cats.append(cat)
            if hitter_cats and pitcher_cats:
                has_mlb_split = True

        if has_mlb_split:
            daily_hitter_rows = self.build_stat_rows(daily_stats, hitter_cats)
            daily_pitcher_rows = self.build_stat_rows(daily_stats, pitcher_cats)
            weekly_hitter_rows = self.build_stat_rows(weekly_stats, hitter_cats)
            weekly_pitcher_rows = self.build_stat_rows(weekly_stats, pitcher_cats)

            sections = [
                {
                    "header": f"{date_str} (Hitter)",
                    "rows": daily_hitter_rows,
                },
                {
                    "header": f"{date_str} (Pitcher)",
                    "rows": daily_pitcher_rows,
                },
                {
                    "header": f"W{week_str} (Hitter)",
                    "rows": weekly_hitter_rows,
                },
                {
                    "header": f"W{week_str} (Pitcher)",
                    "rows": weekly_pitcher_rows,
                },
            ]
        else:
            daily_rows = self.build_stat_rows(daily_stats, stat_categories)
            weekly_rows = self.build_stat_rows(weekly_stats, stat_categories)
            sections = [
                {
                    "header": date_str,
                    "rows": daily_rows,
                },
                {
                    "header": f"W{week_str}",
                    "rows": weekly_rows,
                },
            ]

        return build_stats_list_card(
            title=player_info["manager_name"],
            subtitle=player_info["official_name"],
            sections=sections,
        )
