# LINE Bot 整合 LLM 意圖路由器與對話系統實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 為 LINE Bot 新增 @提及 功能並整合 Google Gemini API，當接收到自然語言時，自動轉化為標準指令執行，或直接由 LLM 回覆對話。

**Architecture:** 採用雙層路由器架構（Intent Router Middleware），利用 `IntentRouter` 對 Webhook 訊息進行初步過濾（包括群聊 @提及 判斷與日誌減噪），再調用 `LLMAgent`（Gemini）解析意圖，動態轉換為標準指令後交由 `CommandDispatcher` 執行，或由 LLM 直接回覆聊天。

**Tech Stack:** Python, google-generativeai, line-bot-sdk (v3), pytest

---

### Task 1: 基礎類別動態指令清單收集擴充

**Files:**
- Modify: `src/handlers/base_handler.py`
- Modify: `src/handlers/dispatcher.py`
- Test: `tests/test_dispatcher_instruction.py`

- [ ] **Step 1: 撰寫失敗測試**

建立測試檔 `tests/test_dispatcher_instruction.py`，驗證 `CommandDispatcher` 是否能動態收集 Handlers 的指令描述：

```python
import pytest
from src.handlers.base_handler import BaseHandler
from src.handlers.dispatcher import CommandDispatcher

class DummyHandler(BaseHandler):
    @property
    def instruction_desc(self) -> str:
        return "- #測試指令: 測試用"
    def can_handle(self, user_text: str) -> bool:
        return False
    def execute(self, event, configuration) -> None:
        pass

def test_dispatcher_gets_all_instructions():
    dispatcher = CommandDispatcher()
    dispatcher.register(DummyHandler())
    assert dispatcher.get_all_instruction_descs() == "- #測試指令: 測試用"
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/test_dispatcher_instruction.py -v`
Expected: FAIL (AttributeError: 'CommandDispatcher' object has no attribute 'get_all_instruction_descs')

- [ ] **Step 3: 撰寫最小實作**

修改 `src/handlers/base_handler.py`（在 `BaseHandler` 類別內新增 `instruction_desc` 屬性）：

```python
    @property
    def instruction_desc(self) -> str:
        """Return the user-friendly instruction format supported by this handler."""
        return ""
```

修改 `src/handlers/dispatcher.py`（在 `CommandDispatcher` 內新增方法）：

```python
    def get_all_instruction_descs(self) -> str:
        """Collect and concatenate instruction descriptions from all registered handlers."""
        descs = []
        for handler in self._handlers:
            desc = handler.instruction_desc
            if desc:
                descs.append(desc.strip())
        return "\n".join(descs)
```

- [ ] **Step 4: 執行測試並確認其通過**

Run: `pytest tests/test_dispatcher_instruction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/handlers/base_handler.py src/handlers/dispatcher.py tests/test_dispatcher_instruction.py
git commit -m "feat: extend BaseHandler and Dispatcher for dynamic instruction collection"
```

---

### Task 2: 實作主要 Handlers 的指令說明描述

**Files:**
- Modify: `src/handlers/stats_handler.py`
- Modify: `src/handlers/matchup_handler.py`
- Modify: `src/handlers/player_handler.py`
- Modify: `src/handlers/misc_handler.py`
- Test: `tests/test_handlers_instruction.py`

- [ ] **Step 1: 撰寫失敗測試**

建立測試檔 `tests/test_handlers_instruction.py`，驗證主要 Handler 的指令說明不為空字串：

```python
import pytest
from src.handlers.stats_handler import StatsHandler
from src.handlers.matchup_handler import MatchupHandler
from src.handlers.player_handler import PlayerHandler
from src.handlers.misc_handler import MiscHandler

def test_handler_instruction_descs():
    assert len(StatsHandler().instruction_desc) > 0
    assert len(MatchupHandler().instruction_desc) > 0
    assert len(PlayerHandler().instruction_desc) > 0
    assert len(MiscHandler().instruction_desc) > 0
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/test_handlers_instruction.py -v`
Expected: FAIL (AssertionError: len(StatsHandler().instruction_desc) > 0 fails, returning "")

- [ ] **Step 3: 撰寫實作以宣告指令說明**

修改 `src/handlers/stats_handler.py`，新增屬性：

```python
    @property
    def instruction_desc(self) -> str:
        return """
- #戰績：查詢當天的聯賽整體戰績。
- #戰績昨天：查詢昨天的聯賽整體戰績。
- #戰績上週：查詢上週的聯賽整體戰績。
- #戰績W<週數>：查詢特定週數的戰績（例如：#戰績W5）。
- #戰績<年月日>：查詢特定日期的戰績（例如：#戰績20251120）。
        """
```

修改 `src/handlers/matchup_handler.py`，新增屬性：

```python
    @property
    def instruction_desc(self) -> str:
        return """
- #對戰：顯示對戰比分查詢的玩家選單。
- #對戰 <玩家名稱>：查詢特定玩家的本週對戰比分。
        """
```

修改 `src/handlers/player_handler.py`，新增屬性：

```python
    @property
    def instruction_desc(self) -> str:
        return """
- #球員 <球員英文姓名>：查詢特定 NBA 球員的數據與分析（例如：#球員 Stephen Curry）。
- #球員昨晚 <球員英文姓名>：查詢特定 NBA 球員昨晚的表現（例如：#球員昨晚 Stephen Curry）。
        """
```

修改 `src/handlers/misc_handler.py`，新增屬性：

```python
    @property
    def instruction_desc(self) -> str:
        return """
- #運勢：測試運勢或運氣。
        """
```

- [ ] **Step 4: 執行測試並確認其通過**

Run: `pytest tests/test_handlers_instruction.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/handlers/stats_handler.py src/handlers/matchup_handler.py src/handlers/player_handler.py src/handlers/misc_handler.py tests/test_handlers_instruction.py
git commit -m "feat: implement instruction_desc for major handlers"
```

---

### Task 3: 建立 LLMAgent 意圖解析模組

**Files:**
- Create: `src/utils/llm_agent.py`
- Test: `tests/test_llm_agent.py`

- [ ] **Step 1: 撰寫測試（並 Mock Gemini API 呼叫）**

建立測試檔 `tests/test_llm_agent.py`，驗證 `LLMAgent` 的意圖解析功能：

```python
import pytest
from unittest.mock import MagicMock, patch
from src.utils.llm_agent import LLMAgent

@patch('google.generativeai.GenerativeModel')
def test_llm_agent_command_intent(mock_model_cls):
    # Mock Response
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_command": true, "command_text": "#對戰 小謝", "reply_text": null}'
    mock_model.generate_content.return_value = mock_response
    mock_model_cls.return_value = mock_model

    # 必須設置臨時環境變數以供測試運行
    with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake_key'}):
        agent = LLMAgent()
        result = agent.analyze_intent("幫我查小謝這週對戰", "指令清單")
        assert result["is_command"] is True
        assert result["command_text"] == "#對戰 小謝"

@patch('google.generativeai.GenerativeModel')
def test_llm_agent_chat_intent(mock_model_cls):
    mock_model = MagicMock()
    mock_response = MagicMock()
    mock_response.text = '{"is_command": false, "command_text": null, "reply_text": "哈囉！"}'
    mock_model.generate_content.return_value = mock_response
    mock_model_cls.return_value = mock_model

    with patch.dict('os.environ', {'GEMINI_API_KEY': 'fake_key'}):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！"
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/test_llm_agent.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'src.utils.llm_agent')

- [ ] **Step 3: 撰寫實作**

建立 `src/utils/llm_agent.py`：

```python
import os
import json
import logging
import google.generativeai as genai

class LLMAgent:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logging.warning("[LLM] 警告：未設定 GEMINI_API_KEY，LLM 功能將無法正常運作。")
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        )
        self.system_prompt = """你是一個專門處理 Yahoo Fantasy NBA 聯賽 LINE Bot 意圖路由的 AI 助手。
你的任務是將用戶的自然語言請求分析並歸類。

現有的「#標準指令」清單如下：
{commands_desc}

【聯賽玩家名稱對照表】：
若用戶查詢對戰或玩家數據，請將其提及的名字轉換為以下官方玩家名稱之一：
- 韋哥、Jerry、小謝、肥儒、陳威、Jason、胡哲、Andy、Joseph、阿昇、林宗、Covi。
例如：「肥儒這週打得怎樣」應轉換為 `#對戰 肥儒`。

【NBA球員姓名翻譯規範】：
若用戶使用中文或暱稱查詢球員（如：柯瑞、LBJ、詹皇、咖哩），請在轉換為指令時翻譯為其正式的英文姓名（如：Stephen Curry, LeBron James）。
例如：「幫我查查昨晚柯瑞的表現」應轉換為 `#球員昨晚 Stephen Curry`。

【輸出規範】：
你必須且只能回傳一個 JSON 物件，格式如下：
- is_command: (boolean) 是否匹配到上述指令意圖。
- command_text: (string | null) 若匹配到指令，輸出轉換後格式完全正確的「#標準指令」；否則為 null。
- reply_text: (string | null) 若沒有匹配到任何指令意圖，請在此填入直接回覆給用戶的對話內容（中文，親切且帶點幽默的籃球助手語氣）；若有匹配到指令，則為 null。"""

    def analyze_intent(self, text: str, commands_desc: str) -> dict:
        if not os.getenv("GEMINI_API_KEY"):
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": "系統目前未配置 AI 金鑰，無法為您服務。"
            }

        formatted_system = self.system_prompt.replace("{commands_desc}", commands_desc)
        prompt = f"{formatted_system}\n\n用戶輸入：{text}"
        try:
            response = self.model.generate_content(prompt)
            data = json.loads(response.text.strip())
            return data
        except Exception as e:
            logging.error(f"[LLM] 意圖解析出錯: {e}")
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": "我的大腦暫時離線了，請稍後再試！"
            }
```

- [ ] **Step 4: 執行測試並確認其通過**

Run: `pytest tests/test_llm_agent.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/utils/llm_agent.py tests/test_llm_agent.py
git commit -m "feat: implement LLMAgent with Gemini API integration"
```

---

### Task 4: 建立 IntentRouter 與過濾及 Log 減噪邏輯

**Files:**
- Create: `src/handlers/intent_router.py`
- Test: `tests/test_intent_router.py`

- [ ] **Step 1: 撰寫測試 (Mock LINE Event 結構與 LLMAgent)**

建立測試檔 `tests/test_intent_router.py`，驗證 `IntentRouter` 的路由與過濾邏輯是否正確：

```python
import pytest
from unittest.mock import MagicMock, patch
from src.handlers.intent_router import IntentRouter

def create_mock_event(text, chat_type="user", mentionees=None):
    event = MagicMock()
    event.reply_token = "dummy_reply_token"
    
    # Message Mock
    message = MagicMock()
    message.text = text
    
    if mentionees is not None:
        mention = MagicMock()
        m_list = []
        for m_type in mentionees:
            m = MagicMock()
            m.type = m_type
            m_list.append(m)
        mention.mentionees = m_list
        message.mention = mention
    else:
        message.mention = None
        
    event.message = message
    
    # Source Mock
    source = MagicMock()
    source.type = chat_type
    event.source = source
    return event

@patch('src.utils.llm_agent.LLMAgent.analyze_intent')
def test_router_skips_unmentioned_group_chat(mock_analyze):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組普通閒聊且無 mention
    event = create_mock_event("哈囉", chat_type="group")
    router.route(event, MagicMock())
    
    mock_analyze.assert_not_called()
    dispatcher.handle.assert_not_called()

@patch('src.utils.llm_agent.LLMAgent.analyze_intent')
def test_router_handles_mentioned_group_chat(mock_analyze):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 群組中 @提及 機器人
    event = create_mock_event("哈囉", chat_type="group", mentionees=["user"])
    mock_analyze.return_value = {"is_command": False, "command_text": None, "reply_text": "你好"}
    
    with patch('linebot.v3.messaging.MessagingApi.reply_message') as mock_reply:
        router.route(event, MagicMock())
        mock_analyze.assert_called_once()
        mock_reply.assert_called_once()

@patch('src.utils.llm_agent.LLMAgent.analyze_intent')
def test_router_converts_command_and_dispatches(mock_analyze):
    dispatcher = MagicMock()
    router = IntentRouter(dispatcher)
    
    # 單聊
    event = create_mock_event("幫我查 Curry", chat_type="user")
    mock_analyze.return_value = {"is_command": True, "command_text": "#球員 Stephen Curry", "reply_text": None}
    
    router.route(event, MagicMock())
    
    assert event.message.text == "#球員 Stephen Curry"
    dispatcher.handle.assert_called_once_with(event, router.dispatcher._handlers if hasattr(router.dispatcher, '_handlers') else MagicMock())
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/test_intent_router.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'src.handlers.intent_router')

- [ ] **Step 3: 撰寫實作**

建立 `src/handlers/intent_router.py`：

```python
import logging
import re
from linebot.v3.webhooks import MessageEvent
from linebot.v3.messaging import Configuration, ApiClient, MessagingApi, ReplyMessageRequest, TextMessage
from src.handlers.dispatcher import CommandDispatcher
from src.utils.llm_agent import LLMAgent

class IntentRouter:
    def __init__(self, dispatcher: CommandDispatcher):
        self.dispatcher = dispatcher
        self.llm_agent = LLMAgent()

    def route(self, event: MessageEvent, configuration: Configuration) -> None:
        user_text = event.message.text.strip() if event.message and hasattr(event.message, 'text') else ""
        if not user_text:
            return

        # 1. 優先處理標準指令
        if user_text.startswith("#"):
            logging.info(f"[IntentRouter] 收到標準指令: {user_text}")
            self.dispatcher.handle(event, configuration)
            return

        # 2. 判斷是否為單聊
        is_private_chat = event.source.type == "user"
        
        # 3. 判斷群聊中的 @提及
        is_mentioned = False
        if event.source.type in ["group", "room"]:
            # 檢查 LINE 官方 mention 物件 (排除 @ALL)
            if hasattr(event.message, "mention") and event.message.mention:
                mentionees = event.message.mention.mentionees
                for m in mentionees:
                    if m.type == "user": 
                        is_mentioned = True
                    elif m.type == "all":
                        pass
            
            # 備用：檢查文字中手動輸入包含 @bot 等字樣
            lower_text = user_text.lower()
            if "@bot" in lower_text or "@linebot" in lower_text:
                is_mentioned = True

        # 4. 路由分流
        if is_private_chat or is_mentioned:
            chat_type = "單聊" if is_private_chat else "群組提及"
            logging.info(f"[IntentRouter] 收到{chat_type}，開始 LLM 意圖解析: {user_text}")
            
            clean_text = self._clean_mention_text(user_text)
            self._handle_llm_flow(event, configuration, clean_text)
        else:
            # 群組閒聊直接忽略，不留 Log
            pass

    def _clean_mention_text(self, text: str) -> str:
        return re.sub(r'(?i)@(?:bot|linebot)\s*', '', text).strip()

    def _handle_llm_flow(self, event: MessageEvent, configuration: Configuration, text: str) -> None:
        commands_desc = self.dispatcher.get_all_instruction_descs()
        result = self.llm_agent.analyze_intent(text, commands_desc)
        
        if result.get("is_command") and result.get("command_text"):
            command_text = result["command_text"]
            logging.info(f"[IntentRouter] LLM 意圖匹配成功，轉化指令: {command_text}")
            
            try:
                event.message.text = command_text
            except AttributeError:
                class TextMessageWrapper:
                    def __init__(self, original_msg, new_text):
                        self.__dict__.update(original_msg.__dict__)
                        self.text = new_text
                event.message = TextMessageWrapper(event.message, command_text)
                
            self.dispatcher.handle(event, configuration)
        else:
            reply_text = result.get("reply_text") or "我現在無法理解您的意思，請試著換個方式詢問。"
            logging.info(f"[IntentRouter] LLM 生成對話回覆: {reply_text}")
            
            with ApiClient(configuration) as api_client:
                MessagingApi(api_client).reply_message(
                    ReplyMessageRequest(
                        reply_token=event.reply_token,
                        messages=[TextMessage(text=reply_text)]
                    )
                )
```

- [ ] **Step 4: 執行測試並確認其通過**

Run: `pytest tests/test_intent_router.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/handlers/intent_router.py tests/test_intent_router.py
git commit -m "feat: implement IntentRouter with mention filtering and log noise reduction"
```

---

### Task 5: 整合 Webhook 入口點 (bot.py) 

**Files:**
- Modify: `bot.py`
- Test: `tests/test_bot_integration.py`

- [ ] **Step 1: 撰寫整合測試**

建立 `tests/test_bot_integration.py`，測試 `bot.py` 中的 `handle_message` 是否正常調用 `IntentRouter`：

```python
import pytest
from unittest.mock import MagicMock, patch
import bot

@patch('src.handlers.intent_router.IntentRouter.route')
def test_bot_webhook_calls_intent_router(mock_route):
    # Mock Event
    event = MagicMock()
    event.reply_token = "dummy_token"
    event.message = MagicMock()
    event.message.text = "#戰績"
    
    # 呼叫 bot 的 handle_message
    with patch('bot.is_token_processed', return_value=False):
        bot.handle_message(event)
        
    mock_route.assert_called_once_with(event, bot.configuration)
```

- [ ] **Step 2: 執行測試並確認其失敗**

Run: `pytest tests/test_bot_integration.py -v`
Expected: FAIL (AssertionError: mock_route not called, or bot still using CommandDispatcher directly)

- [ ] **Step 3: 修改 bot.py 實作**

修改 `bot.py` 的對應行數：
1. 於第 26 行後新增導入：
```python
from src.handlers.intent_router import IntentRouter
```
2. 於第 77 行後（初始化 dispatcher 並註冊完 handlers 後）加入 `IntentRouter` 初始化：
```python
# Initialize IntentRouter
intent_router = IntentRouter(dispatcher)
```
3. 於第 118-122 行（`handle_message` 內原有的 `#` 指令判斷處），修改為呼叫 `intent_router.route`：

尋找原始碼：
```python
    user_text = event.message.text.strip()
    
    if user_text.startswith("#"):
        logging.info(f"[LINE] 收到指令: {user_text}")
        dispatcher.handle(event, configuration)
```

覆寫為：
```python
    # 交由 intent_router 進行意圖路由與過濾
    intent_router.route(event, configuration)
```

- [ ] **Step 4: 執行整合測試與現有測試並確認全部通過**

Run: `pytest -v`
Expected: PASS (所有測試皆成功通過，且包括新增的 intent 測試)

- [ ] **Step 5: Commit**

```bash
git add bot.py tests/test_bot_integration.py
git commit -m "feat: integrate IntentRouter into bot.py webhook handler"
```
