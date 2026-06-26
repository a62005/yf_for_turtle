import logging
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration
from typing import List
from .base_handler import BaseHandler
from src.utils.security import security_manager

class CommandDispatcher:
    def __init__(self):
        self._handlers: List[BaseHandler] = []
        
    def register(self, handler: BaseHandler) -> None:
        """Register a handler to the dispatcher."""
        self._handlers.append(handler)
        
    def handle(self, event: MessageEvent, configuration: Configuration) -> None:
        """Route the event to the appropriate handler with permission checks."""
        user_text = event.message.text.strip()
        user_id = event.source.user_id if event.source and hasattr(event.source, 'user_id') else None
        
        for handler in self._handlers:
            try:
                if handler.can_handle(user_text):
                    # 1. 超級管理員權限檢查
                    if getattr(handler, 'requires_super_admin', False):
                        if not security_manager.is_super_admin(user_id):
                            logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非超級管理員被安靜攔截")
                            return  # 安靜攔截，不作任何回覆
                    
                    # 2. 白名單權限檢查
                    if getattr(handler, 'requires_whitelist', False):
                        if not security_manager.is_whitelisted(user_id):
                            logging.info(f"[Dispatcher] 使用者 {user_id} 嘗試執行 {handler.__class__.__name__}，因非白名單被安靜攔截")
                            return  # 安靜攔截，不作 any response

                    handler.execute(event, configuration)
                    return # Stop routing once a handler takes it
            except Exception as e:
                logging.error(f"[Dispatcher] Handler {handler.__class__.__name__} failed: {e}")
                
        logging.info(f"[Dispatcher] No handler found for command: {user_text}")


    def get_all_instruction_descs(self) -> str:
        """Collect and concatenate instruction descriptions from all registered handlers."""
        descs = []
        for handler in self._handlers:
            if getattr(handler, 'exclude_from_llm', False):
                continue
            desc = handler.instruction_desc
            if desc:
                descs.append(desc.strip())
        return "\n".join(descs)

