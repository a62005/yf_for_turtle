# LLM Dynamic Provider Refactoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the LLM integration by introducing a Factory & Provider pattern, renaming `gemini_parser.py` to `player_parser.py`, and completely removing all legacy `GEMINI_` prefix fallback configurations, keeping only `LLM_API_KEY` and `LLM_MODEL`.

**Architecture:** Use an abstract interface `BaseLLMProvider` with two concrete implementations: `GeminiProvider` and `AgnesProvider`. A central `LLMProviderFactory` resolves the correct provider dynamically based on the `LLM_MODEL` name. Existing caller modules are refactored to use the factory.

**Tech Stack:** Python 3.14+, `requests` (for Agnes AI API), `google-generativeai` (for Gemini SDK), `pytest`.

---

## File Structure Map

We will create/modify/delete the following files:

- **Create New Files**:
  - `src/utils/llm/__init__.py` - Exports factory and base provider.
  - `src/utils/llm/base.py` - Abstract base provider.
  - `src/utils/llm/gemini.py` - Gemini provider implementation.
  - `src/utils/llm/agnes.py` - Agnes AI provider implementation.
  - `src/utils/llm/factory.py` - Factory resolver.
  - `src/utils/player_parser.py` - Renamed from `gemini_parser.py`.
  - `tests/test_llm_factory.py` - Unit tests for factory and providers.
  - `tests/test_player_parser.py` - Unit tests for player parser.
- **Modify Existing Files**:
  - `src/config.py` - Remove `GEMINI_` key-value mappings.
  - `src/utils/llm_agent.py` - Integrate factory.
  - `src/utils/football_analyzer.py` - Integrate factory.
  - `src/handlers/player_handler.py` - Update imports and check `LLM_API_KEY`.
  - `tests/test_llm_agent.py` - Change mock environment variables.
  - `tests/test_football_analyzer.py` - Change mock environment variables.
  - `tests/test_player_handler.py` - Update mock configs.
- **Delete Files**:
  - `src/utils/gemini_parser.py` - Removed after renaming.
  - `tests/test_gemini_parser.py` - Removed after renaming.

---

## Refactoring Tasks

### Task 1: Create LLM Directory and Abstract Provider Interface

**Files:**
- Create: `src/utils/llm/base.py`
- Create: `src/utils/llm/__init__.py`

- [ ] **Step 1: Write `src/utils/llm/base.py`**
Create the file and write the abstract base provider:
```python
from abc import ABC, abstractmethod

class BaseLLMProvider(ABC):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    @abstractmethod
    def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> str:
        """Sends a plain text prompt and returns the response string."""
        pass

    @abstractmethod
    def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> dict:
        """Sends a prompt and returns a parsed JSON dictionary."""
        pass
```

- [ ] **Step 2: Write `src/utils/llm/__init__.py`**
Create the file to export base:
```python
from .base import BaseLLMProvider
```

- [ ] **Step 3: Commit interface creation**
Run:
```bash
git branch --show-current
git add src/utils/llm/base.py src/utils/llm/__init__.py
git commit -m "feat: create abstract BaseLLMProvider interface"
```

---

### Task 2: Implement Gemini and Agnes Providers

**Files:**
- Create: `src/utils/llm/gemini.py`
- Create: `src/utils/llm/agnes.py`
- Modify: `src/utils/llm/__init__.py`

- [ ] **Step 1: Write Gemini Provider**
Create `src/utils/llm/gemini.py` wrapping the official SDK:
```python
import json
import logging
import google.generativeai as genai
from .base import BaseLLMProvider

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str):
        super().__init__(api_key, model_name)
        genai.configure(api_key=self.api_key)
        self.model_cls = genai.GenerativeModel

    def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> str:
        model = self.model_cls(
            model_name=self.model_name,
            system_instruction=system_instruction
        )
        response = model.generate_content(
            prompt,
            generation_config={"temperature": temperature}
        )
        return response.text.strip()

    def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> dict:
        model = self.model_cls(
            model_name=self.model_name,
            system_instruction=system_instruction
        )
        response = model.generate_content(
            prompt,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": temperature
            }
        )
        return json.loads(response.text.strip())
```

- [ ] **Step 2: Write Agnes Provider**
Create `src/utils/llm/agnes.py` wrapping the requests API:
```python
import json
import requests
from .base import BaseLLMProvider

class AgnesProvider(BaseLLMProvider):
    def __init__(self, api_key: str, model_name: str):
        super().__init__(api_key, model_name)
        self.agnes_model = self.model_name
        if self.agnes_model.lower() == "agnes":
            self.agnes_model = "agnes-2.0-flash"
        self.api_url = "https://apihub.agnes-ai.com/v1/chat/completions"

    def _call_api(self, prompt: str, system_instruction: str = None, temperature: float = 0.2, response_format: dict = None) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}"
        }
        messages = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.agnes_model,
            "messages": messages,
            "temperature": temperature
        }
        if response_format:
            payload["response_format"] = response_format

        res = requests.post(self.api_url, json=payload, headers=headers, timeout=15)
        res.raise_for_status()
        res_json = res.json()
        return res_json["choices"][0]["message"]["content"].strip()

    def generate(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> str:
        return self._call_api(prompt, system_instruction, temperature)

    def generate_json(self, prompt: str, system_instruction: str = None, temperature: float = 0.2) -> dict:
        content = self._call_api(prompt, system_instruction, temperature, response_format={"type": "json_object"})
        return json.loads(content)
```

- [ ] **Step 3: Expose Providers in `src/utils/llm/__init__.py`**
Modify `src/utils/llm/__init__.py` to import both:
```python
from .base import BaseLLMProvider
from .gemini import GeminiProvider
from .agnes import AgnesProvider
```

- [ ] **Step 4: Commit providers**
Run:
```bash
git branch --show-current
git add src/utils/llm/gemini.py src/utils/llm/agnes.py src/utils/llm/__init__.py
git commit -m "feat: implement GeminiProvider and AgnesProvider"
```

---

### Task 3: Implement Factory and Write Factory Tests

**Files:**
- Create: `src/utils/llm/factory.py`
- Modify: `src/utils/llm/__init__.py`
- Create: `tests/test_llm_factory.py`

- [ ] **Step 1: Write Factory Implementation**
Create `src/utils/llm/factory.py` with strictly NO GEMINI default fallbacks:
```python
import os
from .base import BaseLLMProvider

class LLMProviderFactory:
    @staticmethod
    def get_provider(api_key: str = None, model_name: str = None) -> BaseLLMProvider:
        key = api_key or os.getenv("LLM_API_KEY")
        model = model_name or os.getenv("LLM_MODEL")

        if not key:
            raise ValueError("LLM API key (LLM_API_KEY) is not configured in the environment.")
        if not model:
            raise ValueError("LLM Model (LLM_MODEL) is not configured in the environment.")

        model_lower = model.lower()
        if "agnes" in model_lower:
            from .agnes import AgnesProvider
            return AgnesProvider(api_key=key, model_name=model)
        else:
            from .gemini import GeminiProvider
            return GeminiProvider(api_key=key, model_name=model)
```

- [ ] **Step 2: Export Factory**
Modify `src/utils/llm/__init__.py` to add `LLMProviderFactory`:
```python
from .base import BaseLLMProvider
from .gemini import GeminiProvider
from .agnes import AgnesProvider
from .factory import LLMProviderFactory
```

- [ ] **Step 3: Create tests for Factory**
Create `tests/test_llm_factory.py` asserting correct resolver behaviour:
```python
import pytest
from unittest.mock import MagicMock, patch
from src.utils.llm import LLMProviderFactory, GeminiProvider, AgnesProvider

def test_factory_missing_env():
    with patch.dict('os.environ', {}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            LLMProviderFactory.get_provider()
        assert "LLM API key" in str(excinfo.value)

def test_factory_missing_model():
    with patch.dict('os.environ', {'LLM_API_KEY': 'some_key'}, clear=True):
        with pytest.raises(ValueError) as excinfo:
            LLMProviderFactory.get_provider()
        assert "LLM Model" in str(excinfo.value)

def test_factory_resolves_gemini():
    with patch.dict('os.environ', {'LLM_API_KEY': 'k', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        provider = LLMProviderFactory.get_provider()
        assert isinstance(provider, GeminiProvider)
        assert provider.api_key == "k"
        assert provider.model_name == "gemini-2.5-flash"

def test_factory_resolves_agnes():
    with patch.dict('os.environ', {'LLM_API_KEY': 'k', 'LLM_MODEL': 'agnes-2.0-flash'}, clear=True):
        provider = LLMProviderFactory.get_provider()
        assert isinstance(provider, AgnesProvider)
        assert provider.api_key == "k"
        assert provider.model_name == "agnes-2.0-flash"
```

- [ ] **Step 4: Run new factory tests to verify passing**
Run:
```bash
.venv\Scripts\python -m pytest tests/test_llm_factory.py -v
```
Expected: PASS

- [ ] **Step 5: Commit factory**
Run:
```bash
git branch --show-current
git add src/utils/llm/factory.py src/utils/llm/__init__.py tests/test_llm_factory.py
git commit -m "feat: implement LLMProviderFactory and test resolving logic"
```

---

### Task 4: Clean up `config.py`

**Files:**
- Modify: `src/config.py`
- Modify: `tests/test_config.py`

- [ ] **Step 1: Update `src/config.py`**
Completely strip `GEMINI_` key-value logic.
Target lines 28-31 in `src/config.py` and replace with:
```python
        "LLM_API_KEY": os.getenv("LLM_API_KEY"),
        "LLM_MODEL": os.getenv("LLM_MODEL"),
```

- [ ] **Step 2: Update Config Tests**
Update any references to `GEMINI_` variables in `tests/test_config.py` to use `LLM_API_KEY` instead.

- [ ] **Step 3: Run config tests to verify passing**
Run:
```bash
.venv\Scripts\python -m pytest tests/test_config.py -v
```

- [ ] **Step 4: Commit config**
Run:
```bash
git branch --show-current
git add src/config.py tests/test_config.py
git commit -m "refactor: simplify src/config.py, remove GEMINI fallbacks"
```

---

### Task 5: Refactor `LLMAgent` and tests

**Files:**
- Modify: `src/utils/llm_agent.py`
- Modify: `tests/test_llm_agent.py`

- [ ] **Step 1: Update `src/utils/llm_agent.py`**
Refactor `LLMAgent` to use `LLMProviderFactory`.
Replace entire contents of `src/utils/llm_agent.py` with:
```python
import logging
from .llm.factory import LLMProviderFactory

class LLMAgent:
    def __init__(self):
        try:
            self.provider = LLMProviderFactory.get_provider()
        except ValueError as e:
            logging.warning(f"[LLM] 警告：{e} LLM 功能將無法正常運作。")
            self.provider = None

        self.system_prompt = """你是一個擁有多功能、博學且親切的 AI 助手。
你的主要任務是分析用戶的輸入：

1. 如果用戶的意圖是想要查詢我們的 Yahoo Fantasy NBA 聯賽數據、NBA 球員或對戰狀況，請對照下方的「#標準指令清單」，將其轉換成對應的 `#標準指令`（is_command 設為 true）。
2. 如果用戶的輸入與 these 指令無關（例如：詢問一般知識、歷史、科技、生活常識、其他運動或單純閒聊），請以一個博學的 AI 助手的身份，直接給出完整、正確的解答（is_command 設為 false，並將回答內容填入 reply_text）。

現有的「#標準指令清單」如下：
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
- reply_text: (string | null) 若沒有匹配到任何指令意圖，請在此填入直接且完整的回答內容；若有匹配到指令，則為 null。"""

    def analyze_intent(self, text: str, commands_desc: str) -> dict:
        if not self.provider:
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": "系統目前未配置 AI 金鑰，無法為您服務。"
            }

        formatted_system = self.system_prompt.replace("{commands_desc}", commands_desc)
        try:
            return self.provider.generate_json(text, system_instruction=formatted_system, temperature=0.2)
        except Exception as e:
            logging.error(f"[LLM] 意圖解析失敗: {e}")
            from .llm.agnes import AgnesProvider
            if isinstance(self.provider, AgnesProvider):
                return {
                    "is_command": False, 
                    "command_text": None, 
                    "reply_text": "我的大腦暫時離線了，請確認 Agnes AI 服務是否正常！"
                }
            else:
                return {
                    "is_command": False, 
                    "command_text": None, 
                    "reply_text": "我的大腦暫時離線了，請稍後再試！"
                }
```

- [ ] **Step 2: Update `tests/test_llm_agent.py`**
Replace `tests/test_llm_agent.py` with mock tests asserting `GeminiProvider` and `AgnesProvider` interaction:
```python
import pytest
from unittest.mock import MagicMock, patch
from src.utils.llm_agent import LLMAgent

@patch('src.utils.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_command_intent(mock_generate_json):
    mock_generate_json.return_value = {
        "is_command": True,
        "command_text": "#對戰 小謝",
        "reply_text": None
    }

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("幫我查小謝這週對戰", "指令清單")
        assert result["is_command"] is True
        assert result["command_text"] == "#對戰 小謝"

@patch('src.utils.llm.gemini.GeminiProvider.generate_json')
def test_llm_agent_gemini_chat_intent(mock_generate_json):
    mock_generate_json.return_value = {
        "is_command": False,
        "command_text": None,
        "reply_text": "哈囉！"
    }

    with patch.dict('os.environ', {'LLM_API_KEY': 'fake_key', 'LLM_MODEL': 'gemini-2.5-flash'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！"

@patch('requests.post')
def test_llm_agent_agnes_chat_intent(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"is_command": false, "command_text": null, "reply_text": "哈囉！我是 Agnes AI。"}'
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    with patch.dict('os.environ', {'LLM_MODEL': 'agnes-2.0-flash', 'LLM_API_KEY': 'agnes_key'}, clear=True):
        agent = LLMAgent()
        result = agent.analyze_intent("你好", "指令清單")
        
        assert result["is_command"] is False
        assert result["reply_text"] == "哈囉！我是 Agnes AI。"
        mock_post.assert_called_once()
```

- [ ] **Step 3: Run LLMAgent tests**
Run:
```bash
.venv\Scripts\python -m pytest tests/test_llm_agent.py -v
```
Expected: PASS

- [ ] **Step 4: Commit LLMAgent refactoring**
Run:
```bash
git branch --show-current
git add src/utils/llm_agent.py tests/test_llm_agent.py
git commit -m "refactor: rewrite LLMAgent to use unified LLM Provider Factory"
```

---

### Task 6: Rename and Refactor `gemini_parser` to `player_parser`

**Files:**
- Create: `src/utils/player_parser.py` (migrated from `gemini_parser.py`)
- Create: `tests/test_player_parser.py` (migrated from `test_gemini_parser.py`)
- Delete: `src/utils/gemini_parser.py`
- Delete: `tests/test_gemini_parser.py`

- [ ] **Step 1: Write `src/utils/player_parser.py`**
Create `src/utils/player_parser.py` using `LLMProviderFactory`:
```python
import json
import os
import logging
import re
import urllib.parse
import urllib.request
from .llm.factory import LLMProviderFactory

SYSTEM_PROMPT = """你是一個精準的 NBA 籃球專家，專門負責將使用者的模糊輸入（例如球員綽號、簡稱、中文音譯或背號加上球隊）解析為官方標準的現役球員資訊。

請遵循以下嚴格規則：
1. 僅識別真實存在的 NBA 「現役球員 (Active Players)」。如果球員已退休，請將 is_known_player 設為 false。
2. 根據大中華地區（包括台灣、中國大陸、香港等不同地區常見的中文譯名、英文簡寫與球員綽號）進行搜尋，不強制精準對應，允許合理的模糊對應與意譯。例如：
   - 台灣與大陸譯名或綽號：如 "姆斯"、"詹皇"、"LBJ" -> LeBron James；"柯瑞"、"咖哩"、"萌神" -> Stephen Curry；"杜蘭特"、"KD"、"死神" -> Kevin Durant
   - 其他常見綽號與譯名：如 "字母哥" -> Giannis Antetokounmpo；"東契奇"、"77" -> Luka Doncic；"胖虎" -> Zion Williamson
3. 如果輸入是完全無意義、非籃球球員、或非現役球員的字詞（例如 "喬丹", "科比", "哈囉", "測試"），你必須將 is_known_player 設為 false，並拒絕胡亂臆測。
4. 必須以指定的 JSON 格式回傳，不要包含任何額外的說明、Markdown 標記或 ```json 包裹。

【強制輸出 JSON 格式範例】：
{
  "is_known_player": true,
  "english_name": "LeBron James",
  "chinese_name": "勒布朗·詹姆斯",
  "team": "Los Angeles Lakers",
  "jersey_number": "23"
}"""

def _search_duckduckgo(query: str) -> list:
    url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8")
            matches = re.finditer(r'<td class="result-snippet">.*?>(.*?)</a>', html, re.DOTALL)
            results = []
            for snippet_match in matches:
                title_match = re.search(r'<a class="result-link".*?>(.*?)</a>', html[:snippet_match.start()])
                title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else ""
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
                results.append(f"標題: {title}\n摘要: {snippet}")
            return results[:5]
    except Exception as e:
        logging.error(f"Search failed for query '{query}': {e}")
        return []

def parse_player_nickname(nickname: str, api_key: str = None, model_name: str = None) -> dict:
    try:
        provider = LLMProviderFactory.get_provider(api_key, model_name)
    except ValueError as e:
        logging.error(f"LLM Provider initialization failed: {e}")
        return {"is_known_player": False, "english_name": None, "chinese_name": None, "team": None, "jersey_number": None, "confidence": 0.0, "reason": f"API Key 尚未設定: {e}"}
    
    try:
        data = provider.generate_json(f"請解析以下輸入：{nickname}", SYSTEM_PROMPT)
        
        if not data.get("is_known_player"):
            logging.info(f"LLM 解析 '{nickname}' 失敗，嘗試進行網路搜尋...")
            query = f'NBA "{nickname}"'
            search_results = _search_duckduckgo(query)
            if search_results:
                results_text = "\n\n".join(search_results)
                prompt = f"""你是一個精準的 NBA 籃球專家。我們在網路搜尋了「{query}」，得到以下結果：

{results_text}

請結合上述搜尋結果以及你的知識，解析使用者的輸入「{nickname}」是指哪位現役 NBA 球員。
如果搜尋結果或你的知識明確指出這是指哪位現役球員，請將 is_known_player 設為 true 並填寫其資訊。
如果仍然無法確定，或該球員已退休，請將 is_known_player 設為 false。
必須以指定的 JSON 格式回傳，不要包含任何額外的說明、Markdown 標記或 ```json 包裹。"""
                data_search = provider.generate_json(prompt, "你是一個精準的 NBA 籃球專家。")
                return data_search
        return data
    except Exception as e:
        logging.error(f"LLM API parse failed: {e}")
        return {"is_known_player": False, "english_name": None, "chinese_name": None, "team": None, "jersey_number": None, "confidence": 0.0, "reason": f"API 呼叫失敗: {str(e)}"}
```

- [ ] **Step 2: Write `tests/test_player_parser.py`**
Create `tests/test_player_parser.py` adapting the original test:
```python
import pytest
from unittest.mock import MagicMock, patch
from src.utils.player_parser import parse_player_nickname

@patch('src.utils.llm.gemini.GeminiProvider.generate_json')
def test_parse_player_nickname_success(mock_generate_json):
    mock_generate_json.return_value = {
        "is_known_player": True,
        "english_name": "LeBron James",
        "chinese_name": "勒布朗·詹姆斯",
        "team": "Los Angeles Lakers",
        "jersey_number": "23"
    }
    
    res = parse_player_nickname("喇叭", api_key="dummy_key", model_name="gemini-2.5-flash")
    assert res["is_known_player"] is True
    assert res["english_name"] == "LeBron James"
    assert res["jersey_number"] == "23"

@patch('src.utils.llm.gemini.GeminiProvider.generate_json')
def test_parse_player_nickname_unknown(mock_generate_json, mocker):
    mock_generate_json.return_value = {
        "is_known_player": False,
        "english_name": None,
        "chinese_name": None,
        "team": None,
        "jersey_number": None
    }
    mock_search = mocker.patch("src.utils.player_parser._search_duckduckgo", return_value=["NBA 測試結果"])
    
    res = parse_player_nickname("哈囉", api_key="dummy_key", model_name="gemini-2.5-flash")
    assert res["is_known_player"] is False
    assert mock_search.call_count == 1
    assert mock_generate_json.call_count == 2

@patch('requests.post')
def test_parse_player_nickname_agnes_success(mock_post, mocker):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": '{"is_known_player": true, "english_name": "Stephen Curry", "chinese_name": "史蒂芬·柯瑞", "team": "Golden State Warriors", "jersey_number": "30"}'
                }
            }
        ]
    }
    mock_post.return_value = mock_response
    mock_search = mocker.patch("src.utils.player_parser._search_duckduckgo")

    res = parse_player_nickname("咖哩", api_key="agnes_key", model_name="agnes-2.0-flash")
    
    assert res["is_known_player"] is True
    assert res["english_name"] == "Stephen Curry"
    mock_search.assert_not_called()
    mock_post.assert_called_once()
```

- [ ] **Step 3: Remove old files**
Remove `src/utils/gemini_parser.py` and `tests/test_gemini_parser.py`.

- [ ] **Step 4: Run new parser tests**
Run:
```bash
.venv\Scripts\python -m pytest tests/test_player_parser.py -v
```
Expected: PASS

- [ ] **Step 5: Commit parser renaming**
Run:
```bash
git branch --show-current
git rm src/utils/gemini_parser.py tests/test_gemini_parser.py
git add src/utils/player_parser.py tests/test_player_parser.py
git commit -m "refactor: rename gemini_parser to player_parser and rewrite to use LLM Factory"
```

---

### Task 7: Update `PlayerHandler` references

**Files:**
- Modify: `src/handlers/player_handler.py`
- Modify: `tests/test_player_handler.py`

- [ ] **Step 1: Modify `src/handlers/player_handler.py`**
Update imports and config check.
Replace lines 12-15 in `src/handlers/player_handler.py`:
```python
from src.config import load_config
from src.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher
from src.utils.gemini_parser import parse_player_nickname
```
With:
```python
from src.config import load_config
from src.cache_utils import load_league_metadata
from src.fetcher import YahooFantasyFetcher
from src.utils.player_parser import parse_player_nickname
```
And replace the check around line 35:
```python
        return bool(config.get("GEMINI_API_KEY"))
```
With:
```python
        return bool(config.get("LLM_API_KEY"))
```
And replace the call around line 151:
```python
            llm_res = parse_player_nickname(
                nickname, 
                api_key=config.get("GEMINI_API_KEY"),
                model_name=config.get("GEMINI_MODEL")
            )
```
With:
```python
            llm_res = parse_player_nickname(
                nickname, 
                api_key=config.get("LLM_API_KEY"),
                model_name=config.get("LLM_MODEL")
            )
```

- [ ] **Step 2: Update `tests/test_player_handler.py`**
Replace `GEMINI_API_KEY` mocks with `LLM_API_KEY` mocks.
Lines 7 and 14:
```python
    mocker.patch("src.handlers.player_handler.load_config", return_value={"GEMINI_API_KEY": "dummy_key"})
```
Replace with:
```python
    mocker.patch("src.handlers.player_handler.load_config", return_value={"LLM_API_KEY": "dummy_key"})
```

- [ ] **Step 3: Run player handler tests**
Run:
```bash
.venv\Scripts\python -m pytest tests/test_player_handler.py -v
```
Expected: PASS

- [ ] **Step 4: Commit player handler updates**
Run:
```bash
git branch --show-current
git add src/handlers/player_handler.py tests/test_player_handler.py
git commit -m "refactor: update PlayerHandler to import player_parser and query LLM_API_KEY"
```

---

### Task 8: Refactor `football_analyzer` and tests

**Files:**
- Modify: `src/utils/football_analyzer.py`
- Modify: `tests/test_football_analyzer.py`

- [ ] **Step 1: Modify `src/utils/football_analyzer.py`**
Replace entire content of `src/utils/football_analyzer.py` with:
```python
import os
import logging
from typing import Optional
from .llm.factory import LLMProviderFactory

DEFAULT_MODEL = "gemini-3.5-flash"

SYSTEM_PROMPT = """你是一個專業的足球分析員，專門研究2026世界盃。
請針對使用者提供的兩支足球隊伍進行專業的對戰分析。
請遵循以下嚴格限制：
1. 必須結合你所知道的最新足球數據與資訊進行分析（例如兩隊的實力對比、球星陣容、近期狀態等）。
2. 不要報導或引用新聞，請完全根據你自己的專業足球知識進行獨立分析。
3. 分析內容大約在 200 字左右，字數不可過長，使用繁體中文。
4. 不要包含額外的 Markdown 標題或多餘的引言，直接給出分析內容。
5. 必須根據兩隊的爆冷機率，在分析最後附上爆冷推薦或爆冷分析（如果沒有明顯爆冷機會，亦請簡短說明原因）。
6. 分析中必須包含投注下注推薦，且必須明確且分開提供：(1) 讓分/不讓分推薦、(2) 推薦的正確比分、(3) 爆冷下注推薦。"""

def analyze_football_matchup(
    team_a: str, 
    team_b: str, 
    api_key: Optional[str] = None, 
    model_name: Optional[str] = None
) -> str:
    """
    透過 Gemini 或是 Agnes AI 對指定的對戰組合進行專業的足球分析。
    """
    try:
        provider = LLMProviderFactory.get_provider(api_key, model_name)
    except ValueError as e:
        return f"LLM API key 尚未設定，無法進行對戰分析。: {e}"
        
    try:
        user_prompt = f"請為以下兩支球隊進行對戰分析：{team_a} vs {team_b}"
        return provider.generate(user_prompt, system_instruction=SYSTEM_PROMPT)
    except Exception as e:
        logging.error(f"LLM API football analysis failed: {e}")
        return "系統繁忙，目前無法取得對戰分析，請稍後再試。"
```

- [ ] **Step 2: Update `tests/test_football_analyzer.py`**
Replace `tests/test_football_analyzer.py` with mock tests verifying `LLMProviderFactory` and provider interaction:
```python
import pytest
from unittest.mock import MagicMock, patch
from src.utils.football_analyzer import analyze_football_matchup, SYSTEM_PROMPT

@patch('src.utils.llm.gemini.GeminiProvider.generate')
def test_analyze_football_matchup_success(mock_generate):
    mock_generate.return_value = "這是一段專業的足球對戰分析..."
    
    result = analyze_football_matchup("巴西", "德國", api_key="dummy_key", model_name="gemini-3.5-flash")
    assert "這是一段專業的足球對戰分析" in result
    mock_generate.assert_called_once_with(
        "請為以下兩支球隊進行對戰分析：巴西 vs 德國",
        system_instruction=SYSTEM_PROMPT
    )

@patch('src.utils.llm.gemini.GeminiProvider.generate')
def test_analyze_football_matchup_env_fallback(mock_generate):
    mock_generate.return_value = "環境變數 fallback 分析結果"
    
    with patch.dict('os.environ', {'LLM_API_KEY': 'env_api_key', 'LLM_MODEL': 'env_model_name'}, clear=True):
        result = analyze_football_matchup("巴西", "德國")
        assert result == "環境變數 fallback 分析結果"
        mock_generate.assert_called_once_with(
            "請為以下兩支球隊進行對戰分析：巴西 vs 德國",
            system_instruction=SYSTEM_PROMPT
        )

def test_analyze_football_matchup_missing_api_key():
    with patch.dict('os.environ', {}, clear=True):
        result = analyze_football_matchup("巴西", "德國")
        assert "LLM API key 尚未設定" in result

@patch('requests.post')
def test_analyze_football_matchup_agnes_success(mock_post):
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": "Agnes AI 對戰分析結果：巴西 vs 德國"
                }
            }
        ]
    }
    mock_post.return_value = mock_response

    result = analyze_football_matchup("巴西", "德國", api_key="agnes_key", model_name="agnes-2.0-flash")
    assert result == "Agnes AI 對戰分析結果：巴西 vs 德國"
    mock_post.assert_called_once()
```

- [ ] **Step 3: Run football analyzer tests**
Run:
```bash
.venv\Scripts\python -m pytest tests/test_football_analyzer.py -v
```
Expected: PASS

- [ ] **Step 4: Commit football analyzer updates**
Run:
```bash
git branch --show-current
git add src/utils/football_analyzer.py tests/test_football_analyzer.py
git commit -m "refactor: update football_analyzer to use LLM Provider Factory"
```

---

### Task 9: Final Sanity Check

**Files:**
- Test: All suites

- [ ] **Step 1: Execute all pytest tests**
Run:
```bash
.venv\Scripts\python -m pytest
```
Expected: All tests PASS.

- [ ] **Step 2: Commit any residual config cleanups or metadata**
Ensure there are no untracked `.pyc` files or cache issues.
Run:
```bash
git branch --show-current
git status
```
Expected: Working tree clean (ignoring unrelated untracked documents).
