import re
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from .base_handler import BaseHandler
from src.config import load_config
from src.utils.cache_utils import load_league_metadata
from src.utils.path_utils import parse_league_id
from src.utils.live_player_cache import get_cached_live_player, set_cached_live_player
from src.llm.llm_agent import LLMAgent
from src.live_api_fetcher import EspnLivePlayerFetcher
from src.services.live_player_identity_resolver import (
    LiveGameBoxscore,
    LivePlayerIdentityResolver,
    PlayerIdentity,
)
from src.visualizer.live_player_flex_renderer import LivePlayerFlexRenderer


class LivePlayerHandler(BaseHandler):
    """
    獨立的 NBA 球員即時比賽數據指令處理器（遵循 ADR-0001 與 ADR-0002，不修改舊有 PlayerHandler）。
    負責處理 '#球員 <球員姓名或綽號>'（以及向下相容 '#球員昨晚 <球員姓名或綽號>'），
    透過 LivePlayerIdentityResolver 解析球員身份、EspnLivePlayerFetcher 擷取數據，
    並交由 LivePlayerFlexRenderer 渲染 Flex Message 卡片。
    """

    def __init__(
        self,
        fetcher: EspnLivePlayerFetcher | None = None,
        renderer: LivePlayerFlexRenderer | None = None,
        identity_resolver: LivePlayerIdentityResolver | None = None,
        llm_agent: LLMAgent | None = None,
    ) -> None:
        super().__init__()
        self.pattern: re.Pattern[str] = re.compile(r"^#球員(昨晚)?\s+(.+)$")
        self.fetcher = fetcher or EspnLivePlayerFetcher()
        self.renderer = renderer or LivePlayerFlexRenderer()
        self.identity_resolver = identity_resolver or LivePlayerIdentityResolver(
            fetcher=self.fetcher,
            llm_agent=llm_agent,
            llm_agent_factory=lambda: LLMAgent(),
            cache_getter=lambda q: get_cached_live_player(q),
            cache_setter=lambda q, d: set_cached_live_player(q, d),
        )

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

    def _resolve_player_identity(self, nickname: str) -> PlayerIdentity | None:
        return self.identity_resolver.resolve_identity(nickname)

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

        raw_game_data = self.fetcher.fetch_player_live_or_latest_game(
            player_info,
            prefer_previous_day=prefer_previous_day,
        )
        if not raw_game_data:
            english_name = player_info.get("english_name") or query_name
            self.reply_text(
                event,
                configuration,
                f"目前查無 {english_name} 的近期出賽數據。",
            )
            return

        boxscore = LiveGameBoxscore.from_dict(raw_game_data)
        flex_dict = self.renderer.render_player_card(
            player_info,
            boxscore,
            stat_categories=meta.get("stat_categories"),
        )
        english_name = player_info.get("english_name") or query_name
        self.reply_flex(event, configuration, f"球員 {english_name} 即時數據", flex_dict)
