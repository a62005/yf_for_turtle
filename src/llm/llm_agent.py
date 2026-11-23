import logging
import os
import json
from cachetools import TTLCache
from .factory import LLMProviderFactory
from .prompts.intent_router_prompt import SYSTEM_PROMPT

class LLMAgent:
    def __init__(self):
        try:
            self.provider = LLMProviderFactory.get_provider()
        except ValueError as e:
            logging.warning(f"[LLM] 警告：{e} LLM 功能將無法正常運作。")
            self.provider = None

        self.system_prompt = SYSTEM_PROMPT
        self._intent_cache = TTLCache(maxsize=256, ttl=600)
        self._team_mapping_cache = {}  # mapping_file -> (mtime, dict)
        self._commands_desc_cache = {} # id(dispatcher) -> (handler_count, str)

    def analyze_intent(self, text: str, commands_desc: str = None, players_list: str = None, temporal_context: str = None, dispatcher = None) -> dict:
        if not self.provider:
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": "系統目前未配置 AI 金鑰，無法為您服務。",
                "error": True
            }

        # Dynamic fallback loading of contexts
        if commands_desc is None:
            if dispatcher is not None:
                disp_id = id(dispatcher)
                handlers = getattr(dispatcher, "_handlers", None)
                h_count = len(handlers) if isinstance(handlers, list) else -1
                cached_desc = self._commands_desc_cache.get(disp_id)
                if cached_desc and cached_desc[0] == h_count and h_count >= 0:
                    commands_desc = cached_desc[1]
                else:
                    commands_desc = dispatcher.get_all_instruction_descs()
                    if h_count >= 0:
                        self._commands_desc_cache[disp_id] = (h_count, commands_desc)
            else:
                commands_desc = ""

        if players_list is None:
            mapping = self._load_team_mapping()
            players_list = ", ".join(mapping.values()) if mapping else ""

        if temporal_context is None:
            temporal_context = ""
            try:
                from src.utils.cache_utils import load_league_metadata
                from src.utils.time_utils import get_pacific_date
                from src.config import load_config as _load_config
                
                _league_id = _load_config().get("LEAGUE_ID")
                meta = load_league_metadata(_league_id) or {}
                today_str = get_pacific_date()
                current_week = meta.get("date_to_week", {}).get(today_str)
                end_week = meta.get("end_week")
                
                parts = [f"今天的太平洋時間日期為：{today_str}。"]
                if current_week:
                    parts.append(f"目前聯賽進行到第 {current_week} 週。")
                if end_week:
                    parts.append(f"聯賽的最後一週（例行賽結束週）為第 {end_week} 週。")
                temporal_context = "".join(parts)
            except Exception as te:
                logging.error(f"[LLM] 獲取時間/週數上下文失敗: {te}")

        cache_key = (text, commands_desc, players_list, temporal_context)
        if cache_key in self._intent_cache:
            logging.info(f"[LLM] 命中語意解析快取: {text}")
            return dict(self._intent_cache[cache_key])

        # 單階段直接解析聯賽查詢與指令轉換（閒聊或無關內容直接由 SYSTEM_PROMPT 判定 is_command=False）
        formatted_system = (
            self.system_prompt
            .replace("{commands_desc}", commands_desc)
            .replace("{players_list}", players_list)
            .replace("{temporal_context}", temporal_context)
        )
        try:
            res = self.provider.generate_json(text, system_instruction=formatted_system, temperature=0.1)
            if isinstance(res, dict) and not res.get("error"):
                # 確保預設欄位存在
                res.setdefault("is_command", False)
                res.setdefault("command_text", None)
                res.setdefault("reply_text", None)
                self._intent_cache[cache_key] = dict(res)
            return res
        except Exception as e:
            logging.error(f"[LLM] 語意解析失敗: {e}")
            return self._handle_exception()

    def _handle_exception(self) -> dict:
        from .agnes import AgnesProvider
        if isinstance(self.provider, AgnesProvider):
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": "我的大腦暫時離線了，請確認 Agnes AI 服務是否正常！",
                "error": True
            }
        else:
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": "我的大腦暫時離線了，請稍後再試！",
                "error": True
            }

    def search_nba_season_start(self, year: int) -> dict:
        """使用 LLM 搭配 Google 搜尋，查詢特定年份/賽季的 NBA 開季日期。"""
        if not self.provider or not hasattr(self.provider, "generate_json_with_search"):
            return {"success": False, "start_date": None}
            
        prompt = (
            f"請搜尋網路，找出 NBA {year}-{str(year+1)[2:]} 新賽季（或下一個即將開始的賽季）官方公佈的開季日期與時間。"
            "請嚴格回傳 JSON 格式，欄位包含：\n"
            "- 'start_date': 字串，格式必須為 'YYYY-MM-DD HH:MM:SS' (例如 '2026-10-20 08:00:00'，時間若無精確公佈請使用上午8點 '08:00:00')。\n"
            "- 'success': 布林值，代表是否找到該球季精確的官方開季日期。"
        )
        
        try:
            result = self.provider.generate_json_with_search(prompt)
            return result
        except Exception as e:
            import logging
            logging.warning(f"[LLM] 搜尋開季日期失敗 (可能為搜尋工具配額限制): {e}。嘗試啟用不含搜尋的備用推估方案...")
            try:
                fallback_prompt = (
                    f"請推估或提供 NBA {year}-{str(year+1)[2:]} 新賽季官方公佈或預計的開季日期與時間（通常在 {year} 年 10 月中下旬的某個星期二，例如 10 月 20 日、21 日或 22 日等）。\n"
                    "請嚴格回傳 JSON 格式，欄位包含：\n"
                    "- 'start_date': 字串，格式必須為 'YYYY-MM-DD HH:MM:SS' (例如 '2026-10-20 08:00:00'，時間請使用上午8點 '08:00:00')。\n"
                    "- 'success': 布林值，代表是否成功產生此日期。"
                )
                result = self.provider.generate_json(fallback_prompt)
                logging.info(f"[LLM] 備用方案成功推估開季日期: {result}")
                return result
            except Exception as fe:
                logging.error(f"[LLM] 備用推估方案也失敗: {fe}")
                return {"success": False, "start_date": None}

    def parse_draft_date(self, text: str) -> dict:
        """將自然語言的時間描述解析為標準格式 YYYY-MM-DD HH:MM。"""
        if not self.provider:
            return {"success": False, "date": None}
            
        import datetime
        current_year = datetime.datetime.now().year
        
        prompt = (
            f"請將以下這段中文所描述的時間，轉換成標準的日期與時間格式 'YYYY-MM-DD HH:MM'。\n"
            f"當前年份是 {current_year} 年。如果使用者描述中未指明年份，請合理推估為當前或下一個最接近的年份。\n"
            f"待解析字串：'{text}'\n\n"
            "請嚴格以 JSON 格式回傳，包含以下兩個欄位：\n"
            "- 'success': 布林值，代表是否能成功解析出明確的日期與時間（包含時與分，最小為分鐘，不包含秒數）。\n"
            "- 'date': 字串，格式為 'YYYY-MM-DD HH:MM'（例如 '2026-10-15 20:30'）。若 success 為 false，此欄位必須為 null。"
        )
        
        try:
            result = self.provider.generate_json(prompt, temperature=0.1)
            success = result.get("success") is True
            date_str = result.get("date")
            if success and date_str:
                return {"success": True, "date": date_str}
            return {"success": False, "date": None}
        except Exception as e:
            import logging
            logging.error(f"[LLM] 解析選秀時間失敗: {e}")
            return {"success": False, "date": None}

    def google_search(self, query: str) -> list:
        from src.llm.prompts.player_fuzzy_search import _search_duckduckgo
        return _search_duckduckgo(query)

    def player_fuzzy_search(self, nickname: str, sport: str = "nba") -> dict:
        sport = str(sport).lower()
        sport_name = "MLB" if sport == "mlb" else "NBA"
        sport_desc = "MLB 棒球" if sport == "mlb" else "NBA 籃球"
        expert_desc = "棒球專家" if sport == "mlb" else "籃球專家"

        if not self.provider:
            return {
                "is_known_player": False,
                "english_name": None,
                "chinese_name": None,
                "team": None,
                "jersey_number": None,
                "confidence": 0.0,
                "reason": "API Key 尚未設定"
            }

        from src.llm.prompts.player_fuzzy_search import get_system_prompt
        system_prompt = get_system_prompt(sport)

        try:
            # 第一次先直接解析
            data = self.provider.generate_json(f"請解析以下輸入：{nickname}", system_prompt)
            
            if not data.get("is_known_player"):
                logging.info(f"LLM 解析 '{nickname}' 失敗，嘗試進行網路搜尋...")
                query = f'{sport_name} "{nickname}"'
                search_results = self.google_search(query)
                results_text = "\n\n".join(search_results) if search_results else "無搜尋結果"

                prompt = f"""你是一個精準的 {sport_desc} 專家（{expert_desc}）。我們在網路搜尋了「{query}」，得到以下結果：

{results_text}

請結合上述搜尋結果以及你的知識，解析使用者的輸入「{nickname}」是指哪位現役 {sport_name} 球員。
如果搜尋結果或你的知識明確指出這是指哪位現役球員，請將 is_known_player 設為 true 並填寫其資訊。
如果仍然無法確定，或該球員已退休，請將 is_known_player 設為 false。
必須以指定的 JSON 格式回傳，不要包含 any 額外的說明、Markdown 標記或 ```json 包裹。"""
                data_search = self.provider.generate_json(prompt, system_prompt)
                return data_search
            return data
        except Exception as e:
            logging.error(f"LLM API parse failed: {e}")
            return {
                "is_known_player": False,
                "english_name": None,
                "chinese_name": None,
                "team": None,
                "jersey_number": None,
                "confidence": 0.0,
                "reason": f"API 呼叫失敗: {str(e)}"
            }

    def _load_team_mapping(self) -> dict:
        """Load and return the team mapping from json config file with mtime caching."""
        from src.utils.path_utils import get_league_team_mapping_path
        mapping_file = get_league_team_mapping_path()
        if os.path.exists(mapping_file):
            try:
                mtime = os.path.getmtime(mapping_file)
                cached = self._team_mapping_cache.get(mapping_file)
                if cached and cached[0] == mtime:
                    return cached[1]
                with open(mapping_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._team_mapping_cache[mapping_file] = (mtime, data)
                return data
            except Exception as e:
                logging.error(f"Failed to load team mapping in LLMAgent: {e}")
        return {}
