from typing import Any
from src.services.fantasy_stat_toolkit import FantasyStatToolkit
from src.visualizer.flex_builder import (
    create_bubble,
    create_header,
    create_separator,
)


class LivePlayerFlexRenderer:
    """
    獨立的 LINE Flex Message 球員即時數據卡片渲染器（遵循 ADR-0001）。
    專職負責將結構化的球員基本資料與單場統計數據組裝為白底極簡風 Flex Bubble，
    不依賴任何網路請求或 LINE 事件物件。
    """

    DEFAULT_STAT_ORDER = [
        "FGM/A",
        "FG%",
        "FTM/A",
        "FT%",
        "3PT",
        "PTS",
        "REB",
        "AST",
        "ST",
        "BLK",
        "TO",
    ]

    DISPLAY_ALIASES = {
        "FGM/FGA": "FGM/A",
        "FTM/FTA": "FTM/A",
        "3PTM": "3PT",
        "3PM": "3PT",
        "STL": "ST",
        "AST/TO": "A/T",
        "A/TO": "A/T",
    }

    @staticmethod
    def _lookup_stat_val(stats: dict, label: str) -> Any:
        return FantasyStatToolkit.get_stat_raw(stats, label)

    @staticmethod
    def _format_stat_value(label: str, raw_val: Any) -> str:
        return FantasyStatToolkit.format_stat_value(label, raw_val, integer_at_ratio_as_int=False)

    def build_ordered_stat_rows(
        self,
        stats: dict,
        stat_categories: list | None = None,
    ) -> list[tuple[str, str]]:
        """
        依據聯盟 stat_categories 或預設標準順序建立 (label, formatted_value) 列表。
        - 在 FG% 前自動補上 FGM/A
        - 在 FT% 前自動補上 FTM/A
        - 將 3PTM/3PM 統一顯示為 3PT、STL 統一顯示為 ST、AST/TO 統一顯示為 A/T
        """
        ordered_labels: list[str] = []
        seen: set[str] = set()

        def add_label(lbl: str) -> None:
            if lbl not in seen:
                seen.add(lbl)
                ordered_labels.append(lbl)

        if stat_categories:
            for cat in stat_categories:
                if isinstance(cat, dict):
                    disp = str(cat.get("display_name") or "").strip()
                else:
                    disp = str(cat or "").strip()
                if not disp:
                    continue
                canonical = self.DISPLAY_ALIASES.get(disp, disp)
                if canonical == "FG%":
                    add_label("FGM/A")
                elif canonical == "FT%":
                    add_label("FTM/A")
                add_label(canonical)
        else:
            for std_lbl in self.DEFAULT_STAT_ORDER:
                add_label(std_lbl)

        rows: list[tuple[str, str]] = []
        for label in ordered_labels:
            raw_v = self._lookup_stat_val(stats, label)
            rows.append((label, self._format_stat_value(label, raw_v)))
        return rows

    @staticmethod
    def _build_subtitle(player_info: dict) -> str:
        chinese_name = str(player_info.get("chinese_name") or "").strip()
        team_abbr = str(player_info.get("team_abbr") or player_info.get("team") or "").strip()
        jersey = str(player_info.get("jersey_number") or "").strip().lstrip("#")
        position = str(player_info.get("position") or "").strip()

        meta_parts: list[str] = []
        if team_abbr and jersey:
            meta_parts.append(f"{team_abbr} #{jersey}")
        elif team_abbr:
            meta_parts.append(team_abbr)
        elif jersey:
            meta_parts.append(f"#{jersey}")

        if position:
            meta_str = f"{' '.join(meta_parts)} • {position}".strip(" •")
        else:
            meta_str = " ".join(meta_parts)

        if chinese_name and meta_str:
            return f"{chinese_name} ｜ {meta_str}"
        return chinese_name or meta_str

    def render_player_card(
        self,
        player_info: dict,
        game_data: dict,
        stat_categories: list | None = None,
    ) -> dict:
        """
        將球員基本資料與單場統計數據組裝為白底極簡風 LINE Flex Message Bubble。
        """
        english_name = str(player_info.get("english_name") or "Unknown").strip()
        subtitle = self._build_subtitle(player_info)

        body_contents: list[dict] = [
            create_header(english_name, subtitle or None)
        ]

        notice_banner = str(game_data.get("notice_banner") or "").strip()
        if notice_banner:
            body_contents.append(
                {
                    "type": "box",
                    "layout": "vertical",
                    "backgroundColor": "#FEF9E7",
                    "borderColor": "#F9E79F",
                    "borderWidth": "1px",
                    "cornerRadius": "md",
                    "paddingAll": "sm",
                    "contents": [
                        {
                            "type": "text",
                            "text": notice_banner,
                            "size": "xs",
                            "weight": "bold",
                            "color": "#B7950B",
                            "wrap": True,
                        }
                    ],
                }
            )

        status_label = str(game_data.get("status_label") or "🏁 FINAL").strip()
        game_state = str(game_data.get("game_state") or "").lower()
        is_live = game_state == "in" or "LIVE" in status_label.upper()
        status_color = "#C0392B" if is_live else "#2C3E50"
        score_text = str(game_data.get("score_text") or "").strip()

        status_box_contents = [
            {
                "type": "text",
                "text": status_label,
                "size": "xs",
                "weight": "bold",
                "color": status_color,
                "flex": 5,
            }
        ]
        if score_text:
            status_box_contents.append(
                {
                    "type": "text",
                    "text": score_text,
                    "size": "sm",
                    "weight": "bold",
                    "color": "#111111",
                    "align": "end",
                    "flex": 5,
                }
            )

        body_contents.append(
            {
                "type": "box",
                "layout": "horizontal",
                "alignItems": "center",
                "backgroundColor": "#F8F9F9",
                "borderColor": "#EAECEE",
                "borderWidth": "1px",
                "cornerRadius": "md",
                "paddingAll": "sm",
                "contents": status_box_contents,
            }
        )

        body_contents.append(create_separator())

        game_date = str(game_data.get("game_date") or "").strip()
        stats_dict = game_data.get("stats") or {}
        minutes = str(game_data.get("minutes") or stats_dict.get("MIN") or "0").strip()

        ordered_rows = self.build_ordered_stat_rows(stats_dict, stat_categories=stat_categories)
        row_boxes = [
            {
                "type": "box",
                "layout": "horizontal",
                "contents": [
                    {
                        "type": "text",
                        "text": label,
                        "size": "sm",
                        "color": "#666666",
                        "flex": 5,
                    },
                    {
                        "type": "text",
                        "text": str(val),
                        "size": "sm",
                        "weight": "bold",
                        "color": "#111111",
                        "align": "end",
                        "flex": 5,
                    },
                ],
            }
            for label, val in ordered_rows
        ]

        body_contents.append(
            {
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": [
                    {
                        "type": "box",
                        "layout": "horizontal",
                        "alignItems": "center",
                        "contents": [
                            {
                                "type": "text",
                                "text": game_date,
                                "weight": "bold",
                                "size": "md",
                                "color": "#111111",
                                "flex": 6,
                            },
                            {
                                "type": "text",
                                "text": f"MIN {minutes}",
                                "size": "xs",
                                "color": "#888888",
                                "align": "end",
                                "flex": 4,
                            },
                        ],
                    },
                    {
                        "type": "box",
                        "layout": "vertical",
                        "spacing": "xs",
                        "contents": row_boxes,
                    },
                ],
            }
        )

        return create_bubble(body_contents)
