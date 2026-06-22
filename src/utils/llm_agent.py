import os
import json
import logging
import requests

class LLMAgent:
    def __init__(self):
        # 讀取 LLM_MODEL 或 GEMINI_MODEL 設定，預設為 gemini-2.5-flash
        self.model_name = os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL") or "gemini-2.5-flash"
        logging.info(f"[LLM] 初始化模型: {self.model_name}")
        
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
        formatted_system = self.system_prompt.replace("{commands_desc}", commands_desc)
        
        model_to_use = self.model_name
        is_agnes = "agnes" in model_to_use.lower()
        
        # 依模型類型進行動態分流與金鑰配置
        if is_agnes:
            api_url = "https://apihub.agnes-ai.com/v1/chat/completions"
            api_key = os.getenv("AGNES_API_KEY") or os.getenv("GEMINI_API_KEY") or "sk-dummy"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            # 如果只寫了 agnes，預設對應 agnes-2.0-flash
            if model_to_use.lower() == "agnes":
                model_to_use = "agnes-2.0-flash"
        else:
            api_url = "http://localhost:20128/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": "Bearer sk-dummy"
            }
            # 自動為 unprefixed gemini/gemma 模型添加 provider 前綴，防止 omniroute 丟出 400 Ambiguous Model 錯誤
            if "/" not in model_to_use and (model_to_use.startswith("gemini-") or model_to_use.startswith("gemma-")):
                model_to_use = f"gemini/{model_to_use}"

        payload = {
            "model": model_to_use,
            "messages": [
                {"role": "system", "content": formatted_system},
                {"role": "user", "content": text}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        try:
            response = requests.post(api_url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            
            res_json = response.json()
            content = res_json["choices"][0]["message"]["content"]
            data = json.loads(content.strip())
            return data
            
        except requests.exceptions.RequestException as e:
            target_name = "Agnes AI" if is_agnes else "本地 omniroute"
            logging.error(f"[LLM] 呼叫 {target_name} 服務失敗: {e}")
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": f"我的大腦暫時離線了，請確認 {'Agnes AI 服務是否正常' if is_agnes else '本地 AI 服務是否已啟動'}！"
            }
        except (KeyError, json.JSONDecodeError) as e:
            logging.error(f"[LLM] 回傳的 JSON 結構解析失敗: {e}")
            return {
                "is_command": False, 
                "command_text": None, 
                "reply_text": "我剛剛有點神智不清，可以請您再問一次嗎？"
            }
