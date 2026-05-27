import json
import os
import logging
import google.generativeai as genai

SYSTEM_PROMPT = """你是一個精準的 NBA 籃球專家，專門負責將使用者的模糊輸入（例如球員綽號、簡稱、中文音譯或背號加上球隊）解析為官方標準的現役球員資訊。

請遵循以下嚴格規則：
1. 僅識別真實存在的 NBA 「現役球員 (Active Players)」。如果球員已退休，請將 is_known_player 設為 false。
2. 對於常見的中文或英文綽號，你必須精準對應，例如：
   - "喇叭", "LBJ", "老漢", "詹皇" -> LeBron James
   - "咖哩", "萌神", "廚師" -> Stephen Curry
   - "死神", "KD" -> Kevin Durant
   - "字母哥" -> Giannis Antetokounmpo
   - "77", "胖虎" -> Luka Doncic
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

def parse_player_nickname(nickname: str, api_key: str = None) -> dict:
    key = api_key or os.getenv("GEMINI_API_KEY")
    if not key:
        logging.error("Gemini API key is not configured.")
        return {"is_known_player": False, "english_name": None, "chinese_name": None, "team": None, "jersey_number": None, "confidence": 0.0, "reason": "API Key 尚未設定"}
    
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel(
            model_name="gemini-2.5-flash",
            system_instruction=SYSTEM_PROMPT
        )
        
        response = model.generate_content(
            f"請解析以下輸入：{nickname}",
            generation_config={"response_mime_type": "application/json"}
        )
        
        data = json.loads(response.text.strip())
        return data
    except Exception as e:
        logging.error(f"Gemini API parse failed: {e}")
        return {"is_known_player": False, "english_name": None, "chinese_name": None, "team": None, "jersey_number": None, "confidence": 0.0, "reason": f"API 呼叫失敗: {str(e)}"}
