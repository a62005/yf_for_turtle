from __future__ import annotations

from dataclasses import dataclass, field, asdict
import logging
import re
from typing import Any, Callable, Mapping

from src.live_api_fetcher import EspnLivePlayerFetcher
from src.llm.llm_agent import LLMAgent
from src.utils.live_player_cache import get_cached_live_player, set_cached_live_player


@dataclass(frozen=True)
class PlayerIdentity:
    """
    真實球員身份領域模型（遵循 ADR-0002 & GLOSSARY）。
    既提供強型別不可變屬性存取，也完整相容 Mapping 字典介面（`[]`、`.get()`、`in`）。
    """

    athlete_id: str
    english_name: str
    chinese_name: str = ""
    team_id: str = ""
    team_abbr: str = ""
    team_name: str = ""
    team: str = ""
    jersey_number: str = ""
    position: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | PlayerIdentity) -> PlayerIdentity:
        if isinstance(data, cls):
            return data
        team_name = str(data.get("team_name") or data.get("team") or "").strip()
        team_val = str(data.get("team") or team_name).strip()
        return cls(
            athlete_id=str(data.get("athlete_id") or "").strip(),
            english_name=str(data.get("english_name") or "").strip(),
            chinese_name=str(data.get("chinese_name") or "").strip(),
            team_id=str(data.get("team_id") or "").strip(),
            team_abbr=str(data.get("team_abbr") or "").strip(),
            team_name=team_name,
            team=team_val,
            jersey_number=str(data.get("jersey_number") or "").strip(),
            position=str(data.get("position") or "").strip(),
        )

    def get(self, key: str, default: Any = None) -> Any:
        d = self.to_dict()
        return d.get(key, default)

    def __getitem__(self, key: str) -> Any:
        d = self.to_dict()
        if key not in d:
            raise KeyError(key)
        return d[key]

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key in self.to_dict()


@dataclass(frozen=True)
class LiveGameBoxscore:
    """
    球員即時比賽數據領域模型（遵循 ADR-0002 & GLOSSARY）。
    既提供強型別不可變屬性存取，也完整相容 Mapping 字典介面（`[]`、`.get()`、`in`）。
    """

    event_id: str = ""
    game_date: str = ""
    game_state: str = "post"
    status_label: str = "🏁 FINAL"
    score_text: str = ""
    minutes: str = "0"
    stats: dict[str, Any] = field(default_factory=dict)
    notice_banner: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Mapping[str, Any] | LiveGameBoxscore) -> LiveGameBoxscore:
        if isinstance(data, cls):
            return data
        raw_stats = data.get("stats")
        stats_copy = dict(raw_stats) if isinstance(raw_stats, Mapping) else {}
        notice = data.get("notice_banner")
        notice_str = str(notice).strip() if notice is not None and str(notice).strip() else None
        return cls(
            event_id=str(data.get("event_id") or "").strip(),
            game_date=str(data.get("game_date") or "").strip(),
            game_state=str(data.get("game_state") or "post").strip(),
            status_label=str(data.get("status_label") or "🏁 FINAL").strip(),
            score_text=str(data.get("score_text") or "").strip(),
            minutes=str(data.get("minutes") or stats_copy.get("MIN") or "0").strip(),
            stats=stats_copy,
            notice_banner=notice_str,
        )

    def get(self, key: str, default: Any = None) -> Any:
        d = self.to_dict()
        return d.get(key, default)

    def __getitem__(self, key: str) -> Any:
        d = self.to_dict()
        if key not in d:
            raise KeyError(key)
        return d[key]

    def __contains__(self, key: object) -> bool:
        if not isinstance(key, str):
            return False
        return key in self.to_dict()


class LivePlayerIdentityResolver:
    """
    獨立的球員身份解析服務（遵循 ADR-0002）。
    透過建構子依賴注入擷取器、LLM 代理（或工廠函式）與快取讀寫函式，
    統一封裝「快取檢索 ➔ LLM 綽號解析 ➔ ESPN 現役球隊校準 ➔ 寫回快取」完整流程。
    """

    def __init__(
        self,
        fetcher: EspnLivePlayerFetcher | None = None,
        llm_agent: LLMAgent | None = None,
        llm_agent_factory: Callable[[], LLMAgent] | None = None,
        cache_getter: Callable[[str], dict | None] | None = None,
        cache_setter: Callable[[str, dict], None] | None = None,
    ) -> None:
        self.fetcher = fetcher or EspnLivePlayerFetcher()
        self._llm_agent = llm_agent
        self._llm_agent_factory = llm_agent_factory or LLMAgent
        self._cache_getter = cache_getter or (lambda q: get_cached_live_player(q))
        self._cache_setter = cache_setter or (lambda q, d: set_cached_live_player(q, d))

    def _get_llm_agent(self) -> LLMAgent:
        if self._llm_agent is not None:
            return self._llm_agent
        return self._llm_agent_factory()

    def resolve_identity(self, nickname: str) -> PlayerIdentity | None:
        raw_query = (nickname or "").strip()
        if not raw_query:
            return None

        # 1. Check independent live player cache first
        cached = self._cache_getter(raw_query)
        if cached:
            return PlayerIdentity.from_dict(cached)

        # 2. Cache Miss: call LLMAgent.player_fuzzy_search to resolve nickname into official English/Chinese names
        llm_res: dict[str, Any] = {}
        try:
            agent = self._get_llm_agent()
            llm_res = agent.player_fuzzy_search(raw_query, sport="nba") or {}
        except Exception as e:
            logging.warning(
                f"[LivePlayerIdentityResolver] LLM player_fuzzy_search failed for '{raw_query}': {e}"
            )

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

        team_name = str(
            espn_info.get("team_name") or espn_info.get("team") or llm_res.get("team") or ""
        ).strip()
        identity = PlayerIdentity(
            athlete_id=str(espn_info.get("athlete_id") or "").strip(),
            english_name=str(espn_info.get("english_name") or llm_en_name or raw_query).strip(),
            chinese_name=str(espn_info.get("chinese_name") or llm_zh_name or "").strip(),
            team_id=str(espn_info.get("team_id") or "").strip(),
            team_abbr=str(espn_info.get("team_abbr") or "").strip(),
            team_name=team_name,
            team=team_name,
            jersey_number=str(
                espn_info.get("jersey_number") or llm_res.get("jersey_number") or ""
            ).strip(),
            position=str(espn_info.get("position") or "").strip(),
        )

        # 3. Save resolved identity to independent live player cache
        self._cache_setter(raw_query, identity.to_dict())
        return identity
