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
