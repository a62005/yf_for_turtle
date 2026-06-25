"""Flex Message Builder for LINE.

Provides templates for generating structured Flex Messages.
"""

def _create_bubble(body_contents: list) -> dict:
    """Wrap body contents into a Flex Bubble.

    Args:
        body_contents: A list of LINE Flex component dicts.

    Returns:
        dict: Flex bubble dictionary.
    """
    return {
        "type": "bubble",
        "body": {
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": body_contents
        }
    }


def _create_header(title: str, subtitle: str | None = None) -> dict:
    """Create a header box for Flex Messages.

    Args:
        title: Title of the card.
        subtitle: Optional subtitle (str).

    Returns:
        dict: Flex box component.
    """
    header_contents = [
        {
            "type": "text",
            "text": title,
            "weight": "bold",
            "size": "xl",
            "color": "#111111"
        }
    ]
    if subtitle:
        header_contents.append({
            "type": "text",
            "text": subtitle,
            "size": "sm",
            "color": "#555555"
        })
    return {
        "type": "box",
        "layout": "vertical",
        "spacing": "xs",
        "contents": header_contents
    }


def _create_separator(color: str = "#EAEAEA") -> dict:
    """Create a refined separator.

    Args:
        color: Hex color string.

    Returns:
        dict: Flex separator component.
    """
    return {
        "type": "separator",
        "color": color
    }


def get_status_color(status: str) -> str:
    """Get hex color code for player injury status.

    Args:
        status: Status code (e.g. "O", "DTD", "GTD").

    Returns:
        str: Hex color code.
    """
    if not status:
        return "#7F8C8D"
    status_upper = status.upper().strip()
    if status_upper in ("O", "INJ", "OUT"):
        return "#922B21"
    elif status_upper in ("DOUBTFUL", "DOU"):
        return "#D35400"
    elif status_upper in ("QUESTIONABLE", "QUE", "DTD"):
        return "#E67E22"
    elif status_upper in ("PROBABLE", "PRO", "GTD"):
        return "#F1C40F"
    else:
        return "#7F8C8D"


def build_stats_list_card(title: str, subtitle: str = None, sections: list = None) -> dict:
    """Build a clean stats list card.

    Args:
        title: Main title of the card.
        subtitle: Subtitle.
        sections: List of sections in the following format:
            [
                {
                    "header": "2026-06-24",  # Optional section header
                    "rows": [
                        ("FGM/A", "5/10"),
                        ("FG%", "50.0%"),
                        ...
                    ]
                }
            ]

    Returns:
        dict: LINE Flex bubble message.
    """
    body_contents = []
    body_contents.append(_create_header(title, subtitle))

    if sections:
        for i, sec in enumerate(sections):
            section_contents = []
            sec_header = sec.get("header")
            if sec_header:
                section_contents.append({
                    "type": "text",
                    "text": sec_header,
                    "weight": "bold",
                    "size": "md",
                    "color": "#111111"
                })

            rows_contents = []
            for label, val in sec.get("rows", []):
                rows_contents.append({
                    "type": "box",
                    "layout": "horizontal",
                    "contents": [
                        {
                            "type": "text",
                            "text": label,
                            "size": "sm",
                            "color": "#666666",
                            "flex": 5
                        },
                        {
                            "type": "text",
                            "text": str(val),
                            "size": "sm",
                            "weight": "bold",
                            "color": "#111111",
                            "align": "end",
                            "flex": 5
                        }
                    ]
                })

            section_contents.append({
                "type": "box",
                "layout": "vertical",
                "spacing": "xs",
                "contents": rows_contents
            })

            body_contents.append({
                "type": "box",
                "layout": "vertical",
                "spacing": "sm",
                "contents": section_contents
            })

    return _create_bubble(body_contents)


def build_matchup_comparison_card(title: str, subtitle: dict | str = None, comparison_rows: list = None) -> dict:
    """Build a matchup comparison card.

    Args:
        title: E.g. "WEEK 6 MATCHUP"
        subtitle: Dict containing nickname, official name and score, or str.
        comparison_rows: List of comparison tuples/lists:
            [
                (metric_name, my_val, opp_val, status, is_aux)
            ]

    Returns:
        dict: LINE Flex bubble message.
    """
    body_contents = []

    if isinstance(subtitle, dict):
        # 週次標題 (E.g. WEEK 6 MATCHUP)
        body_contents.append({
            "type": "text",
            "text": title,
            "weight": "bold",
            "size": "xxs",
            "color": "#cccccc",
            "align": "center",
            "margin": "xs"
        })
        # 第一層：玩家中文暱稱 VS
        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": subtitle.get("my_nickname", ""), "weight": "bold", "size": "xl", "color": "#111111", "flex": 4},
                {"type": "text", "text": "VS", "align": "center", "weight": "bold", "size": "sm", "color": "#aaaaaa", "flex": 2},
                {"type": "text", "text": subtitle.get("opp_nickname", ""), "weight": "bold", "size": "xl", "color": "#111111", "align": "end", "flex": 4}
            ]
        })
        # 第二層：Fantasy 官方隊名
        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": subtitle.get("my_official", ""), "size": "xxs", "color": "#999999", "flex": 5},
                {"type": "text", "text": " ", "size": "xxs", "flex": 1},
                {"type": "text", "text": subtitle.get("opp_official", ""), "size": "xxs", "color": "#999999", "align": "end", "flex": 5}
            ]
        })
        # 第三層：即時比分對決
        wins_val = subtitle.get("wins", 0)
        losses_val = subtitle.get("losses", 0)
        try:
            w_f = float(wins_val)
            l_f = float(losses_val)
        except (ValueError, TypeError):
            w_f = 0.0
            l_f = 0.0

        if w_f > l_f:
            my_score_style = {"size": "20px", "weight": "bold", "color": "#111111"}
            opp_score_style = {"size": "18px", "weight": "regular", "color": "#aaaaaa"}
        elif w_f < l_f:
            my_score_style = {"size": "18px", "weight": "regular", "color": "#aaaaaa"}
            opp_score_style = {"size": "20px", "weight": "bold", "color": "#111111"}
        else:
            my_score_style = {"size": "20px", "weight": "bold", "color": "#111111"}
            opp_score_style = {"size": "20px", "weight": "bold", "color": "#111111"}

        body_contents.append({
            "type": "box",
            "layout": "horizontal",
            "contents": [
                {"type": "text", "text": str(wins_val), "align": "end", "weight": my_score_style["weight"], "size": my_score_style["size"], "color": my_score_style["color"], "flex": 4},
                {"type": "text", "text": ":", "align": "center", "weight": "bold", "size": "md", "color": "#cccccc", "flex": 2},
                {"type": "text", "text": str(losses_val), "align": "start", "weight": opp_score_style["weight"], "size": opp_score_style["size"], "color": opp_score_style["color"], "flex": 4}
            ]
        })
    else:
        body_contents.append(_create_header(title, subtitle))

    if comparison_rows:
        rows_boxes = []
        for row in comparison_rows:
            metric_name = row[0]
            my_val = row[1]
            opp_val = row[2]
            status = row[3] if len(row) > 3 else None
            is_aux = row[4] if len(row) > 4 else False

            # Translate metric ST -> STL
            if metric_name == "ST":
                metric_name = "STL"

            if is_aux:
                left_style = {"size": "xs", "weight": "regular", "color": "#777777"}
                right_style = {"size": "xs", "weight": "regular", "color": "#777777"}
                center_style = {"size": "xs", "weight": "bold", "color": "#999999"}
            else:
                center_style = {"size": "sm", "weight": "bold", "color": "#333333"}
                if status == "my_win":
                    left_style = {"size": "16px", "weight": "bold", "color": "#111111"}
                    right_style = {"size": "14px", "weight": "regular", "color": "#aaaaaa"}
                elif status == "opp_win":
                    left_style = {"size": "14px", "weight": "regular", "color": "#aaaaaa"}
                    right_style = {"size": "16px", "weight": "bold", "color": "#111111"}
                else:
                    left_style = {"size": "14px", "weight": "regular", "color": "#555555"}
                    right_style = {"size": "14px", "weight": "regular", "color": "#555555"}

            rows_boxes.append({
                "type": "box",
                "layout": "horizontal",
                "alignItems": "center",
                "contents": [
                    {
                        "type": "text",
                        "text": str(my_val),
                        "size": left_style.get("size", "sm"),
                        "weight": left_style.get("weight", "regular"),
                        "color": left_style.get("color", "#111111"),
                        "flex": 4
                    },
                    {
                        "type": "text",
                        "text": metric_name,
                        "size": center_style.get("size", "sm"),
                        "weight": center_style.get("weight", "regular"),
                        "color": center_style.get("color", "#333333"),
                        "align": "center",
                        "flex": 3
                    },
                    {
                        "type": "text",
                        "text": str(opp_val),
                        "size": right_style.get("size", "sm"),
                        "weight": right_style.get("weight", "regular"),
                        "color": right_style.get("color", "#111111"),
                        "align": "end",
                        "flex": 4
                    }
                ]
            })

        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": rows_boxes
        })

    return _create_bubble(body_contents)


def build_status_badge_list_card(title: str, subtitle: str = None, items: list = None, empty_msg: str = "🟢 目前全隊球員皆健康！") -> dict:
    """Build a card displaying status badges for team members.

    Args:
        title: Main title.
        subtitle: Subtitle.
        items: List of tuples representing player status:
            [
                (name, injury_detail, status_code, status_color)
            ]
        empty_msg: Message to display if there are no items.

    Returns:
        dict: LINE Flex bubble message.
    """
    body_contents = []
    body_contents.append(_create_header(title, subtitle))

    if not items:
        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "paddingAll": "lg",
            "contents": [
                {
                    "type": "text",
                    "text": empty_msg,
                    "color": "#27AE60",
                    "weight": "bold",
                    "size": "md",
                    "align": "center"
                }
            ]
        })
    else:
        rows_contents = []
        for item in items:
            name = item[0]
            injury = item[1] if len(item) > 1 else None
            status_code = item[2] if len(item) > 2 else ""
            badge_color = item[3] if len(item) > 3 else "#7F8C8D"

            left_text = name
            if injury:
                left_text = f"{name} - {injury}"

            badge_box = {
                "type": "box",
                "layout": "vertical",
                "width": "42px",
                "height": "20px",
                "backgroundColor": badge_color,
                "cornerRadius": "md",
                "justifyContent": "center",
                "alignItems": "center",
                "contents": [
                    {
                        "type": "text",
                        "text": status_code,
                        "color": "#FFFFFF",
                        "size": "xxs",
                        "weight": "bold",
                        "align": "center",
                        "gravity": "center"
                    }
                ]
            }

            rows_contents.append({
                "type": "box",
                "layout": "horizontal",
                "alignItems": "center",
                "contents": [
                    {
                        "type": "text",
                        "text": left_text,
                        "size": "sm",
                        "color": "#333333",
                        "gravity": "center",
                        "flex": 8
                    },
                    badge_box
                ]
            })

        body_contents.append({
            "type": "box",
            "layout": "vertical",
            "spacing": "md",
            "contents": rows_contents
        })

    return _create_bubble(body_contents)


def build_button_menu_card(title: str, subtitle: str = None, buttons: list = None) -> dict:
    """Build a button menu card.

    Args:
        title: Main title.
        subtitle: Subtitle.
        buttons: List of tuples representing buttons:
            [
                (label, msg_text)
            ]

    Returns:
        dict: LINE Flex bubble message.
    """
    body_contents = []
    body_contents.append(_create_header(title, subtitle))

    if buttons:
        buttons_box = {
            "type": "box",
            "layout": "vertical",
            "spacing": "sm",
            "contents": [
                {
                    "type": "button",
                    "style": "secondary",
                    "height": "sm",
                    "action": {
                        "type": "message",
                        "label": btn_label,
                        "text": btn_text
                    }
                }
                for btn_label, btn_text in buttons
            ]
        }
        body_contents.append(buttons_box)

    return _create_bubble(body_contents)
