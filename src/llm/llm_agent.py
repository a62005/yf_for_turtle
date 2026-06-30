import logging
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

    def analyze_intent(self, text: str, commands_desc: str, players_list: str = "", temporal_context: str = "") -> dict:
        if not self.provider:
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": "系統目前未配置 AI 金鑰，無法為您服務。",
                "error": True
            }

        # 第一階段：意圖分類
        from .prompts.intent_router_prompt import CLASSIFIER_PROMPT, CHAT_PROMPT
        try:
            category_res = self.provider.generate_json(text, system_instruction=CLASSIFIER_PROMPT, temperature=0.1)
            category = category_res.get("category", "casual_chat")
            logging.info(f"[LLM] 第一階段意圖分類結果: {category}")
        except Exception as ce:
            logging.error(f"[LLM] 第一階段意圖分類失敗: {ce}，預設進行聯賽查詢解析")
            category = "league_query"

        # 第二階段：根據分類載入相對應的 Prompt 處理
        if category == "league_query":
            formatted_system = (
                self.system_prompt
                .replace("{commands_desc}", commands_desc)
                .replace("{players_list}", players_list)
                .replace("{temporal_context}", temporal_context)
            )
            try:
                return self.provider.generate_json(text, system_instruction=formatted_system, temperature=0.2)
            except Exception as e:
                logging.error(f"[LLM] 第二階段聯賽意圖解析失敗: {e}")
                return self._handle_exception()
        else:
            # 閒聊意圖：使用極簡對話 Prompt，避免無謂的 Token 浪費與指令綁定
            try:
                chat_reply = self.provider.generate(text, system_instruction=CHAT_PROMPT, temperature=0.7)
                return {
                    "is_command": False,
                    "command_text": None,
                    "reply_text": chat_reply
                }
            except Exception as e:
                logging.error(f"[LLM] 第二階段閒聊生成失敗: {e}")
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



