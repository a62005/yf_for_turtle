import os
import json
import logging
from abc import ABC, abstractmethod
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import ApiClient, MessagingApi, ReplyMessageRequest, FlexMessage, FlexContainer, Configuration
from src.config import load_config
from src.visualizer.flex_builder import build_button_menu_card

class BaseHandler(ABC):
    """Base interface for all bot message handlers."""
    
    def __init__(self):
        self.requires_super_admin: bool = False
        self.requires_whitelist: bool = False
        self.exclude_from_llm: bool = False
        
        # 動態包裝子類別的 execute 方法以統一處理 LeaguePermissionError
        original_execute = self.execute
        def wrapped_execute(event, configuration):
            try:
                original_execute(event, configuration)
            except Exception as e:
                from src.fetcher import LeaguePermissionError
                if isinstance(e, LeaguePermissionError) or e.__class__.__name__ == "LeaguePermissionError":
                    self.reply_text(
                        event,
                        configuration,
                        "⚠️ 機器人 Yahoo 帳號目前無權限存取此聯盟。請確保已將機器人的 Yahoo 帳號邀請為該聯盟的成員或 Co-manager。"
                    )
                else:
                    raise
        self.execute = wrapped_execute
        
    @abstractmethod
    def can_handle(self, user_text: str) -> bool:
        """Return True if this handler can process the given text."""
        pass
        
    @abstractmethod
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        """Execute the core logic and handle LINE API replies."""
        pass

    @property
    def instruction_desc(self) -> str:
        """Return the user-friendly instruction format supported by this handler."""
        return ""

    def _load_team_mapping(self) -> dict:
        """Load and return the team mapping from json config file."""
        from src.utils.path_utils import get_league_team_mapping_path
        mapping_file = get_league_team_mapping_path()
        if os.path.exists(mapping_file):
            try:
                with open(mapping_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logging.error(f"Failed to load team mapping in BaseHandler: {e}")
        else:
            logging.warning(f"Team mapping file does not exist: {mapping_file}")
        return {}

    def reply_flex(self, event: MessageEvent, configuration: Configuration, alt_text: str, flex_dict: dict) -> None:
        """Reply to user with a LINE Flex Message."""
        flex_container = FlexContainer.from_json(json.dumps(flex_dict))
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[FlexMessage(alt_text=alt_text, contents=flex_container)]
                )
            )

    def reply_text(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
        """Reply to user with a LINE Text Message."""
        from linebot.v3.messaging import TextMessage
        with ApiClient(configuration) as api_client:
            MessagingApi(api_client).reply_message(
                ReplyMessageRequest(
                    reply_token=event.reply_token,
                    messages=[TextMessage(text=text)]
                )
            )

    def reply_player_list(self, event: MessageEvent, configuration: Configuration, is_matchup: bool) -> None:
        """Reply with a vertical player list Flex Message."""
        mapping = self._load_team_mapping()
        if not mapping:
            logging.warning("No team mapping found when trying to reply player list.")
            return

        # Ensure nicknames are unique and preserved
        nicknames = []
        for name in mapping.values():
            if name not in nicknames:
                nicknames.append(name)

        title = "⚔️ 對戰比分查詢" if is_matchup else "🙋‍♂️ 玩家數據查詢"
        subtitle = "請點擊下方玩家，將自動搜尋該數據"
        command_prefix = "#對戰" if is_matchup else "#玩家"

        buttons = [(name, f"{command_prefix} {name}") for name in nicknames]
        flex_dict = build_button_menu_card(title, subtitle, buttons)

        self.reply_flex(event, configuration, f"{title}選單", flex_dict)
