from typing import Any


AUX_DISPLAY_NAMES = {"FGM/A", "FGM/FGA", "FTM/A", "FTM/FTA", "H/AB"}
AUX_STAT_IDS = {"9004003", "9007006", "60"}
STANDARD_NBA_KEYS = {
    "FGM/A", "FGM/FGA", "FG%", "FTM/A", "FTM/FTA", "FT%",
    "3PTM", "3PT", "3PM", "PTS", "REB", "AST", "ST", "STL", "BLK", "TO",
    "Today Player", "Game Player", "GP_PLAYED", "GP_TOTAL", "GP_SORT_KEY",
    "FG", "FT", "FGM", "FGA", "FTM", "FTA",
    "stat_3", "stat_4", "stat_6", "stat_7",
}
EXTRA_NBA_ORDER = ["3PT%", "OREB", "DREB", "A/T", "AST/TO", "A/TO", "DD", "TD"]
SMALLER_IS_BETTER_STATS = {"TO", "ERA", "WHIP", "L", "BB/9"}


class FantasyStatToolkit:
    """
    統一封裝 NBA / MLB 比項 (Stat Category) 別名取值、自訂比項排序提取、
    百分比與棒球/籃球特殊數值格式化，以及輔助統計項判定（遵循 ADR-0002）。
    """

    AUX_DISPLAY_NAMES = AUX_DISPLAY_NAMES
    AUX_STAT_IDS = AUX_STAT_IDS
    STANDARD_NBA_KEYS = STANDARD_NBA_KEYS
    EXTRA_NBA_ORDER = EXTRA_NBA_ORDER
    SMALLER_IS_BETTER_STATS = SMALLER_IS_BETTER_STATS

    @staticmethod
    def get_stat_raw(stats: dict | Any, key: str) -> Any:
        if not isinstance(stats, dict):
            return None
        if key in stats:
            return stats[key]
        if key in ("FGM/A", "FGM/FGA"):
            val = stats.get("FGM/FGA") if "FGM/FGA" in stats else stats.get("FGM/A")
            if val is not None:
                return val
            fgm, fga = stats.get("stat_4"), stats.get("stat_3")
            if fgm is not None and fga is not None:
                return f"{fgm}/{fga}" if str(fga) != "0" else "0/0"
            return None
        if key in ("FTM/A", "FTM/FTA"):
            val = stats.get("FTM/FTA") if "FTM/FTA" in stats else stats.get("FTM/A")
            if val is not None:
                return val
            ftm, fta = stats.get("stat_7"), stats.get("stat_6")
            if ftm is not None and fta is not None:
                return f"{ftm}/{fta}" if str(fta) != "0" else "0/0"
            return None
        if key in ("3PTM", "3PT", "3PM"):
            for k in ("3PTM", "3PT", "3PM"):
                if k in stats:
                    return stats[k]
        if key in ("ST", "STL"):
            for k in ("ST", "STL"):
                if k in stats:
                    return stats[k]
        if key in ("A/T", "AST/TO", "A/TO"):
            for k in ("A/T", "AST/TO", "A/TO"):
                if k in stats:
                    return stats[k]
        return None

    @staticmethod
    def extract_extra_custom_keys(*stats_dicts: dict | None) -> list[str]:
        all_keys: set[str] = set()
        for stats in stats_dicts:
            if isinstance(stats, dict):
                all_keys.update(stats.keys())
        if not all_keys:
            return []

        extra: list[str] = []
        seen_canonical: set[str] = set()
        for k in sorted(
            all_keys,
            key=lambda x: (0, EXTRA_NBA_ORDER.index(x)) if x in EXTRA_NBA_ORDER else (1, x),
        ):
            if k in STANDARD_NBA_KEYS or str(k).startswith("stat_"):
                continue
            canon = "A/T" if k in ("AST/TO", "A/TO") else k
            if canon not in seen_canonical:
                seen_canonical.add(canon)
                extra.append(canon)
        return extra

    @staticmethod
    def to_percent_str(val: Any) -> str:
        if val is None:
            return "-"
        s = str(val).strip()
        if not s or s == "-":
            return "-"
        if s.endswith("%"):
            return s
        try:
            f_val = float(s)
            if f_val == 0.0:
                return "-"
            if f_val <= 1.0:
                return f"{f_val * 100:.1f}%"
            return f"{f_val:.1f}%"
        except (ValueError, TypeError):
            return "-"

    @staticmethod
    def to_val_str(val: Any) -> str:
        if val is None:
            return "-"
        val_str = str(val).strip()
        if val_str == "" or val_str == "-":
            return "-"

        if "/" in val_str:
            parts = val_str.split("/")
            if len(parts) == 2:
                try:
                    float(parts[0].strip())
                    float(parts[1].strip())
                    return val_str
                except ValueError:
                    return "-"

        try:
            f_val = float(val_str)
            if f_val == 0.0:
                return "0"
            if f_val.is_integer():
                return str(int(f_val))
            return val_str
        except ValueError:
            return "-"

    @classmethod
    def format_stat_value(
        cls,
        display_name: str,
        val: Any,
        integer_at_ratio_as_int: bool = False,
    ) -> str:
        if val is None:
            return "-"
        s = str(val).strip()
        if not s or s == "-":
            return "-"

        if display_name in ("FG%", "FT%") or "%" in display_name:
            return cls.to_percent_str(val)

        if display_name in ("AVG", "OBP", "SLG", "OPS"):
            try:
                num = float(s)
                if num == 0:
                    return "-"
                formatted = f"{num:.3f}"
                return formatted[1:] if formatted.startswith("0.") else formatted
            except (ValueError, TypeError):
                return s

        if display_name in ("ERA", "WHIP"):
            try:
                num = float(s)
                return f"{num:.2f}"
            except (ValueError, TypeError):
                return s

        if display_name in ("A/T", "AST/TO", "A/TO"):
            try:
                num = float(s)
                if integer_at_ratio_as_int and num.is_integer():
                    return str(int(num))
                return f"{num:.2f}"
            except (ValueError, TypeError):
                return s

        if "/" in display_name:
            if integer_at_ratio_as_int:
                return s if s not in ("0", "None") else "-"
            return s

        try:
            return str(int(round(float(s))))
        except (ValueError, TypeError):
            return s

    @staticmethod
    def is_auxiliary_category(cat: dict) -> bool:
        if not isinstance(cat, dict):
            return False
        disp = str(cat.get("display_name") or "")
        sort_order = cat.get("sort_order")
        stat_id = str(cat.get("stat_id", ""))
        return (
            (sort_order is None)
            or (sort_order not in [0, 1])
            or (disp in AUX_DISPLAY_NAMES)
            or (stat_id in AUX_STAT_IDS)
        )


class FantasyStatComparator:
    """
    獨立領域服務：負責一對一即時對戰 (Scheduled Matchup) 比項勝負計算
    與全聯盟模擬比分 (All-Play Score Simulation) 分組排序計算（遵循 ADR-0002）。
    """

    def __init__(self, toolkit: FantasyStatToolkit | None = None) -> None:
        self.toolkit = toolkit or FantasyStatToolkit()

    def compare_stats(
        self,
        my_stats: dict,
        opp_stats: dict,
        stat_categories: list | None = None,
    ) -> dict:
        if not stat_categories:
            cats_to_compare = [
                ("FG%", True), ("FT%", True), ("3PTM", True), ("PTS", True),
                ("REB", True), ("AST", True), ("ST", True), ("BLK", True), ("TO", False),
            ]
            for extra_key in self.toolkit.extract_extra_custom_keys(my_stats, opp_stats):
                cats_to_compare.append((extra_key, extra_key not in SMALLER_IS_BETTER_STATS))

            wins, losses, ties = 0, 0, 0
            details: dict[str, dict] = {}

            details["FGM/A"] = {
                "my_val": self.toolkit.to_val_str(self.toolkit.get_stat_raw(my_stats, "FGM/FGA")),
                "opp_val": self.toolkit.to_val_str(self.toolkit.get_stat_raw(opp_stats, "FGM/FGA")),
            }
            details["FTM/A"] = {
                "my_val": self.toolkit.to_val_str(self.toolkit.get_stat_raw(my_stats, "FTM/FTA")),
                "opp_val": self.toolkit.to_val_str(self.toolkit.get_stat_raw(opp_stats, "FTM/FTA")),
            }

            for cat, is_larger_better in cats_to_compare:
                my_raw = self.toolkit.get_stat_raw(my_stats, cat)
                opp_raw = self.toolkit.get_stat_raw(opp_stats, cat)

                if "%" in cat:
                    my_val_str = self.toolkit.to_percent_str(my_raw)
                    opp_val_str = self.toolkit.to_percent_str(opp_raw)
                else:
                    my_val_str = self.toolkit.to_val_str(my_raw)
                    opp_val_str = self.toolkit.to_val_str(opp_raw)

                try:
                    my_num = float(my_raw) if my_raw is not None else 0.0
                except (ValueError, TypeError):
                    my_num = 0.0
                try:
                    opp_num = float(opp_raw) if opp_raw is not None else 0.0
                except (ValueError, TypeError):
                    opp_num = 0.0

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
                else:
                    if my_num < opp_num:
                        status = "my_win"
                        wins += 1
                    else:
                        status = "opp_win"
                        losses += 1

                details[cat] = {
                    "status": status,
                    "my_val": my_val_str,
                    "opp_val": opp_val_str,
                }

            return {
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "details": details,
            }

        wins, losses, ties = 0, 0, 0
        details = {}
        for cat in stat_categories:
            disp = cat["display_name"]
            sort_order = cat.get("sort_order")
            is_only_display = self.toolkit.is_auxiliary_category(cat)

            my_raw = self.toolkit.get_stat_raw(my_stats, disp)
            opp_raw = self.toolkit.get_stat_raw(opp_stats, disp)

            if "%" in disp:
                my_val_str = self.toolkit.to_percent_str(my_raw)
                opp_val_str = self.toolkit.to_percent_str(opp_raw)
            else:
                my_val_str = self.toolkit.to_val_str(my_raw)
                opp_val_str = self.toolkit.to_val_str(opp_raw)

            if is_only_display:
                details[disp] = {
                    "my_val": my_val_str,
                    "opp_val": opp_val_str,
                }
                continue

            is_larger_better = (sort_order == 1)

            try:
                my_num = float(my_raw) if my_raw is not None else 0.0
            except (ValueError, TypeError):
                my_num = 0.0
            try:
                opp_num = float(opp_raw) if opp_raw is not None else 0.0
            except (ValueError, TypeError):
                opp_num = 0.0

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
            else:
                if my_num < opp_num:
                    status = "my_win"
                    wins += 1
                else:
                    status = "opp_win"
                    losses += 1

            details[disp] = {
                "status": status,
                "my_val": my_val_str,
                "opp_val": opp_val_str,
            }

        return {
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "details": details,
        }

    def build_all_play_comparison(
        self,
        my_team: dict,
        opponents: list[dict],
        actual_opp_id: str | None,
        stat_categories: list | None = None,
    ) -> tuple[list[dict], list[dict], list[dict]]:
        win_rows: list[dict] = []
        tie_rows: list[dict] = []
        loss_rows: list[dict] = []

        for opp in opponents:
            comp_res = self.compare_stats(
                my_team["stats"],
                opp["stats"],
                stat_categories=stat_categories,
            )
            wins = int(comp_res["wins"])
            losses = int(comp_res["losses"])
            ties = int(comp_res["ties"])
            is_actual = bool(actual_opp_id and opp["team_id"] == actual_opp_id)
            row = {
                "opp_team_id": opp["team_id"],
                "opp_nickname": opp["name"],
                "opp_official": opp["official_name"],
                "wins": wins,
                "losses": losses,
                "ties": ties,
                "is_actual_opponent": is_actual,
                "order_index": opp["order_index"],
            }
            if wins > losses:
                win_rows.append(row)
            elif wins < losses:
                loss_rows.append(row)
            else:
                tie_rows.append(row)

        def sort_key(r: dict) -> tuple:
            return (
                -(r["wins"] - r["losses"]),
                -r["wins"],
                r["losses"],
                not r["is_actual_opponent"],
                r["order_index"],
            )

        win_rows.sort(key=sort_key)
        tie_rows.sort(key=sort_key)
        loss_rows.sort(key=sort_key)
        return win_rows, tie_rows, loss_rows
