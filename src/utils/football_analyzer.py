import os
import logging
from typing import Optional
import google.generativeai as genai

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
    
    :param team_a: 第一支球隊名稱
    :param team_b: 第二支球隊名稱
    :param api_key: LLM API Key，若未提供則從環境變數 LLM_API_KEY 取得
    :param model_name: 模型名稱，若未提供則從環境變數 LLM_MODEL 取得，預設為 'gemini-3.5-flash'
    :return: 分析結果字串。如果發生錯誤或缺少設定，會回傳友好的錯誤提示訊息。
    """
    key = api_key or os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
    model_to_use = model_name or os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    
    if not key:
        return "LLM API key 尚未設定，無法進行對戰分析。"
        
    is_agnes = "agnes" in model_to_use.lower()
    
    try:
        if is_agnes:
            import requests
            model_to_send = model_to_use
            if model_to_send.lower() == "agnes":
                model_to_send = "agnes-2.0-flash"
            api_url = "https://apihub.agnes-ai.com/v1/chat/completions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {key}"
            }
            payload = {
                "model": model_to_send,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"請為以下兩支球隊進行對戰分析：{team_a} vs {team_b}"}
                ],
                "temperature": 0.2
            }
            response = requests.post(api_url, json=payload, headers=headers, timeout=15)
            response.raise_for_status()
            res_json = response.json()
            return res_json["choices"][0]["message"]["content"].strip()
        else:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name=model_to_use,
                system_instruction=SYSTEM_PROMPT
            )
            
            user_prompt = f"請為以下兩支球隊進行對戰分析：{team_a} vs {team_b}"
            response = model.generate_content(user_prompt)
            return response.text.strip()
    except Exception as e:
        logging.error(f"LLM API football analysis failed: {e}")
        return "系統繁忙，目前無法取得對戰分析，請稍後再試。"
