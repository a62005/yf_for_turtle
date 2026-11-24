import re
import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler
from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.utils.path_utils import parse_league_id
from src.utils.live_player_cache import get_cached_live_player, set_cached_live_player
from src.llm.llm_agent import LLMAgent
from src.live_api_fetcher import EspnLivePlayerFetcher
from src.visualizer.live_player_flex_renderer import LivePlayerFlexRenderer


class LivePlayerHandler(BaseHandler):
    """
    獨立的 NBA 球員即時比賽數據指令處理器（遵循 ADR-0001，不修改舊有 PlayerHandler）。
    負責處理 '#球員 <球員姓名或綽號>'（以及向下相容 '#球員昨晚 <球員姓名或綽號>'），
    串接 EspnLivePlayerFetcher 擷取數據並交由 LivePlayerFlexRenderer 渲染 Flex Message 卡片。
    """

    def __init__(
        self,
        fetcher: EspnLivePlayerFetcher | None = None,
        renderer: LivePlayerFlexRenderer | None = None,
    ) -> None:
        super().__init__()
        self.pattern: re.Pattern[str] = re.compile(r"^#球員(昨晚)?\s+(.+)$")
        self.fetcher = fetcher or EspnLivePlayerFetcher()
        self.renderer = renderer or LivePlayerFlexRenderer()

    @property
    def instruction_desc(self) -> str:
        return """
- #球員 <球員姓名或綽號>：查詢特定 NBA 球員的即時或最新比賽數據（例如：#球員 Stephen Curry、#球員 老詹）。
- #球員昨晚 <球員姓名或綽號>：查詢特定 NBA 球員昨晚（前一比賽日）的表現（例如：#球員昨晚 Stephen Curry）。
        """

    def can_handle(self, user_text: str) -> bool:
        if not user_text:
            return False
        return bool(self.pattern.match(user_text.strip()))

    def _resolve_player_identity(self, nickname: str) -> dict | None:
        raw_query = (nickname or "").strip()
        if not raw_query:
            return None

        # 1. Check independent live player cache first
        cached = get_cached_live_player(raw_query)
        if cached:
            return cached

        # 2. Cache Miss: call LLMAgent.player_fuzzy_search to resolve nickname into official English/Chinese names
        llm_res: dict = {}
        try:
            agent = LLMAgent()
            llm_res = agent.player_fuzzy_search(raw_query, sport="nba") or {}
        except Exception as e:
            logging.warning(f"[LivePlayerHandler] LLM player_fuzzy_search failed for '{raw_query}': {e}")

        is_known = bool(llm_res.get("is_known_player"))
        llm_en_name = str(llm_res.get("english_name") or "").strip()
        llm_zh_name = str(llm_res.get("chinese_name") or "").strip()

        espn_info = None
        if is_known and llm_en_name:
            espn_info = self.fetcher.search_player(llm_en_name)

        # Fallback: direct ESPN search if input is already an English name or LLM isn't configured
        if not espn_info and re.search(r"[A-Za-z]", raw_query):
            espn_info = self.fetcher.search_player(raw_query)

        if not espn_info:
            return None

        team_name = str(espn_info.get("team_name") or espn_info.get("team") or llm_res.get("team") or "").strip()
        resolved = {
            "athlete_id": str(espn_info.get("athlete_id") or "").strip(),
            "english_name": str(espn_info.get("english_name") or llm_en_name or raw_query).strip(),
            "chinese_name": str(espn_info.get("chinese_name") or llm_zh_name or "").strip(),
            "team_id": str(espn_info.get("team_id") or "").strip(),
            "team_abbr": str(espn_info.get("team_abbr") or "").strip(),
            "team_name": team_name,
            "team": team_name,
            "jersey_number": str(espn_info.get("jersey_number") or llm_res.get("jersey_number") or "").strip(),
            "position": str(espn_info.get("position") or "").strip(),
        }

        # 3. Save resolved identity to independent live player cache
        set_cached_live_player(raw_query, resolved)
        return resolved

    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = (event.message.text or "").strip()
        match = self.pattern.match(user_text)
        if not match:
            return

        prefer_previous_day = bool(match.group(1))
        query_name = match.group(2).strip()

        cfg = load_config() or {}
        if isinstance(configuration, dict) and configuration.get("LEAGUE_ID"):
            league_id = str(configuration["LEAGUE_ID"])
        else:
            league_id = str(cfg.get("LEAGUE_ID") or "nba.l.default")

        meta = load_league_metadata(league_id) or {}
        parsed_sport, _ = parse_league_id(league_id)
        sport = str(meta.get("sport") or parsed_sport or "nba").lower()

        if sport == "mlb" or league_id.lower().startswith("mlb"):
            self.reply_text(event, configuration, "⚠️ 球員即時數據查詢目前僅支援 NBA 聯賽。")
            return

        player_info = self._resolve_player_identity(query_name)
        if not player_info:
            self.reply_text(
                event,
                configuration,
                f"找不到現役 NBA 球員「{query_name}」，請嘗試輸入更清晰的名字或別稱。",
            )
            return

        game_data = self.fetcher.fetch_player_live_or_latest_game(
            player_info,
            prefer_previous_day=prefer_previous_day,
        )
        if not game_data:
            english_name = player_info.get("english_name") or query_name
            self.reply_text(
                event,
                configuration,
                f"目前查無 {english_name} 的近期出賽數據。",
            )
            return

        flex_dict = self.renderer.render_player_card(
            player_info,
            game_data,
            stat_categories=meta.get("stat_categories"),
        )
        english_name = player_info.get("english_name") or query_name
        self.reply_flex(event, configuration, f"球員 {english_name} 即時數據", flex_dict)
