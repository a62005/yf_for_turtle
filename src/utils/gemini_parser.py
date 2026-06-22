import json
import os
import logging
import google.generativeai as genai

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
    import urllib.request
    import urllib.parse
    import re

    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(
        url, 
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            html = response.read().decode('utf-8')
            parts = html.split('<h2 class="result__title">')
            results = []
            for part in parts[1:]:
                a_match = re.search(r'<a\s+[^>]*class="[^"]*result__a[^"]*"\s+[^>]*href="([^"]+)"[^>]*>(.*?)</a>', part, re.DOTALL)
                if not a_match:
                    continue
                href = a_match.group(1)
                if "y.js" in href:
                    continue
                title = re.sub(r'<[^>]+>', '', a_match.group(2)).strip()
                
                snippet_match = re.search(r'<a\s+[^>]*class="[^"]*result__snippet[^"]*"\s*[^>]*>(.*?)</a>', part, re.DOTALL)
                snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
                
                results.append(f"標題: {title}\n摘要: {snippet}")
            return results[:5]
    except Exception as e:
        logging.error(f"Search failed for query '{query}': {e}")
        return []

def parse_player_nickname(nickname: str, api_key: str = None, model_name: str = None) -> dict:
    key = api_key or os.getenv("LLM_API_KEY") or os.getenv("GEMINI_API_KEY")
    model_to_use = model_name or os.getenv("LLM_MODEL") or os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    if not key:
        logging.error("LLM API key is not configured.")
        return {"is_known_player": False, "english_name": None, "chinese_name": None, "team": None, "jersey_number": None, "confidence": 0.0, "reason": "API Key 尚未設定"}
    
    is_agnes = "agnes" in model_to_use.lower()
    
    try:
        if is_agnes:
            import requests
            model_to_send = model_to_use
            if model_to_send.lower() == "agnes":
                model_to_send = "agnes-2.0-flash"
                
            def call_agnes_api(prompt_text, system_instruction):
                api_url = "https://apihub.agnes-ai.com/v1/chat/completions"
                headers = {
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {key}"
                }
                payload = {
                    "model": model_to_send,
                    "messages": [
                        {"role": "system", "content": system_instruction},
                        {"role": "user", "content": prompt_text}
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2
                }
                res = requests.post(api_url, json=payload, headers=headers, timeout=15)
                res.raise_for_status()
                res_json = res.json()
                content = res_json["choices"][0]["message"]["content"]
                return json.loads(content.strip())

            data = call_agnes_api(f"請解析以下輸入：{nickname}", SYSTEM_PROMPT)
            
            # 若不知道則根據網路搜尋看是誰
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
                    data_search = call_agnes_api(prompt, "你是一個精準的 NBA 籃球專家。")
                    return data_search
            return data

        else:
            genai.configure(api_key=key)
            model = genai.GenerativeModel(
                model_name=model_to_use,
                system_instruction=SYSTEM_PROMPT
            )
            
            response = model.generate_content(
                f"請解析以下輸入：{nickname}",
                generation_config={"response_mime_type": "application/json"}
            )
            
            data = json.loads(response.text.strip())
            
            # 若不知道則根據網路搜尋看是誰
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
                    
                    response_search = model.generate_content(
                        prompt,
                        generation_config={"response_mime_type": "application/json"}
                    )
                    data_search = json.loads(response_search.text.strip())
                    return data_search
                    
            return data
    except Exception as e:
        logging.error(f"LLM API parse failed: {e}")
        return {"is_known_player": False, "english_name": None, "chinese_name": None, "team": None, "jersey_number": None, "confidence": 0.0, "reason": f"API 呼叫失敗: {str(e)}"}
