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
        
        # 優先使用環境變數設定的 model，否則預設使用 gemini-2.5-flash
        model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
        logging.info(f"[LLM] 初始化模型: {model_name}")
        self.model = genai.GenerativeModel(
            model_name=model_name,
            generation_config={
                "response_mime_type": "application/json",
                "temperature": 0.2
            }
        )
        self.system_prompt = """你是一個擁有多功能、博學且親切的 AI 助手。
你的主要任務是分析用戶的輸入：

1. 如果用戶的意圖是想要查詢我們的 Yahoo Fantasy NBA 聯賽數據、NBA 球員或對戰狀況，請對照下方的「#標準指令清單」，將其轉換成對應的 `#標準指令`（is_command 設為 true）。
2. 如果用戶的輸入與這些指令無關（例如：詢問一般知識、歷史、科技、生活常識、其他運動或單純閒聊），請以一個博學的 AI 助手的身份，直接給出完整、正確的解答（is_command 設為 false，並將回答內容填入 reply_text）。

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
