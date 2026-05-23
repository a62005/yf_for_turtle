from abc import ABC, abstractmethod
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration

class BaseHandler(ABC):
    """Base interface for all bot message handlers."""
    
    @abstractmethod
    def can_handle(self, user_text: str) -> bool:
        """Return True if this handler can process the given text."""
        pass
        
    @abstractmethod
    def execute(self, event: MessageEvent, configuration: Configuration) -> None:
        """Execute the core logic and handle LINE API replies."""
        pass
