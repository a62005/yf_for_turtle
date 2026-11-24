import json
import os
import logging
import re
import urllib.parse
import urllib.request
from src.llm.factory import LLMProviderFactory

def get_system_prompt(sport: str) -> str:
    sport = str(sport).lower()
    sport_name = "MLB 棒球" if sport == "mlb" else "NBA 籃球"
    sport_short = "MLB" if sport == "mlb" else "NBA"
    expert_desc = "棒球專家" if sport == "mlb" else "籃球專家"
    
    nba_nicknames_guide = ""
    if sport != "mlb":
        nba_nicknames_guide = """
【台灣/PTT 常見 NBA 球員綽號、音譯與英文姓氏字面直譯對照參考】：
- 老詹 / 喇叭詹 / 喇叭 / 詹皇 / 姆斯 / LBJ ➔ LeBron James (勒布朗·詹姆斯)
- 咖哩 / 柯瑞 / 萌神 / 廚師 ➔ Stephen Curry (史蒂芬·柯瑞)
- 泳池 / 普爾 / 茶喬丹 / Poole / Pool ➔ Jordan Poole (喬丹·普爾，因 Poole 與 Pool 泳池同音)
- 斑馬 / 外星人 / Wemby ➔ Victor Wembanyama (維克多·文班亞馬)
- 小丑 / 阿肥 / 約老師 ➔ Nikola Jokic (尼古拉·約基奇)
- 77 / 東77 / 東契奇 / 胖77 / Luka ➔ Luka Doncic (盧卡·唐西奇)
- SGA / 鴨梨 / 亞歷山大 ➔ Shai Gilgeous-Alexander (謝伊·吉爾傑斯-亞歷山大)
- 蟻人 / AE / 愛德華茲 ➔ Anthony Edwards (安東尼·愛德華茲)
- 書人 / 奪命書生 / Booker ➔ Devin Booker (德文·布克，Book+er=書人)
- 字母哥 / 字母 / 希臘怪物 ➔ Giannis Antetokounmpo (揚尼斯·阿德托昆博)
- KD / 死神 / 杜蘭特 / 小帥 ➔ Kevin Durant (凱文·杜蘭特)
- AD / 濃眉 / 一眉道人 ➔ Anthony Davis (安東尼·戴維斯)
- 大鬍子 / 登哥 / 哈登 ➔ James Harden (詹姆斯·哈登)
- 龜龜 / 威少 / 忍者龜 / 西河 ➔ Russell Westbrook (羅素·威斯布魯克)
- 吉巴 / 士官長 / 奶油 / 巴特勒 ➔ Jimmy Butler (吉米·巴特勒)
- 嘴綠 / 追夢綠 ➔ Draymond Green (德雷蒙德·格林)
- 胖虎 / 錫安 ➔ Zion Williamson (錫安·威廉森)
- 假日 / 假日哥 ➔ Jrue Holiday (朱·霍勒迪，Holiday=假日)
- 聰明哥 ➔ Marcus Smart (馬庫斯·史馬特，Smart=聰明)
- 小可愛 / 卡哇伊 ➔ Kawhi Leonard (科懷·雷納德)
- 狐狸 / Fox ➔ De'Aaron Fox (達龍·福克斯，Fox=狐狸)
- 大橋 ➔ Mikal Bridges (米卡爾·布里吉斯，Bridges=橋)
- 小橋 ➔ Miles Bridges (邁爾斯·布里吉斯)
- 三球 / 球三 ➔ LaMelo Ball (拉梅洛·鮑爾)
- 大球 / 球哥 ➔ Lonzo Ball (朗佐·鮑爾)
- 小薩 ➔ Domantas Sabonis (多曼塔斯·薩博尼斯)
- 吹楊 / 老鷹楊 ➔ Trae Young (特雷·楊)
- 哈利 / 魔法師 ➔ Tyrese Haliburton (泰瑞斯·哈利伯頓)
- 米丘 / 蜘蛛人 ➔ Donovan Mitchell (多諾萬·米契爾)
"""

    return f"""你是一個精準的 {sport_name} 專家（{expert_desc}），專門負責將使用者的模糊輸入（例如球員綽號、簡稱、中文音譯或背號加上球隊）解析為官方標準的現役球員資訊。

請遵循以下嚴格規則：
1. 僅識別真實存在的 {sport_short} 「現役球員 (Active Players)」。如果球員已退休，請將 is_known_player 設為 false。
2. 根據大中華地區（包括台灣、PTT 鄉民用語、中文音譯與球員綽號）進行搜尋，不強制精準對應，允許合理的模糊對應與意譯。
3. 如果輸入是完全無意義、非該運動球員、或非現役球員的字詞，你必須將 is_known_player 設為 false，並拒絕胡亂臆測。
4. 必須以指定的 JSON 格式回傳，不要包含任何額外的說明、Markdown 標記或 ```json 包裹。
{nba_nicknames_guide}
【強制輸出 JSON 格式範例】：
{{
  "is_known_player": true,
  "english_name": "LeBron James",
  "chinese_name": "勒布朗·詹姆斯",
  "team": "Los Angeles Lakers",
  "jersey_number": "23"
}}"""

SYSTEM_PROMPT = get_system_prompt("nba")

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
必須以指定的 JSON 格式回傳，不要包含 any 額外的說明、Markdown 標記或 ```json 包裹。"""
                data_search = provider.generate_json(prompt, "你是一個精準的 NBA 籃球專家。")
                return data_search
        return data
    except Exception as e:
        logging.error(f"LLM API parse failed: {e}")
        return {"is_known_player": False, "english_name": None, "chinese_name": None, "team": None, "jersey_number": None, "confidence": 0.0, "reason": f"API 呼叫失敗: {str(e)}"}
