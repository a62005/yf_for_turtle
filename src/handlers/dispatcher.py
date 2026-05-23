import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from typing import List
from .base_handler import BaseHandler

class CommandDispatcher:
    def __init__(self):
        self._handlers: List[BaseHandler] = []
        
    def register(self, handler: BaseHandler) -> None:
        """Register a handler to the dispatcher."""
        self._handlers.append(handler)
        
    def handle(self, event: MessageEvent, configuration: Configuration) -> None:
        """Route the event to the appropriate handler."""
        user_text = event.message.text.strip()
        
        for handler in self._handlers:
            try:
                if handler.can_handle(user_text):
                    handler.execute(event, configuration)
                    return # Stop routing once a handler takes it
            except Exception as e:
                logging.error(f"[Dispatcher] Handler {handler.__class__.__name__} failed: {e}")
                
        logging.info(f"[Dispatcher] No handler found for command: {user_text}")
