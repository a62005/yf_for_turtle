# LINE Flex Message 幫助功能實作計畫 (Implementation Plan)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 將 `#幫助` / `#help` 指令由純文字改為動態根據權限載入 JSON 的 LINE Flex Message 輪播卡片（Carousel），並建立穩固的 Python 程式碼預設 Fallback 機制。

**Architecture:** 在 `MiscHandler._handle_help` 中獲取使用者 User ID，使用 `security_manager.is_whitelisted` 驗證權限。依權限動態拼接 `data/help_flex/` 資料夾下的卡片 JSON，並以 `self.reply_flex` 回覆。若讀取 JSON 發生異常則 Fallback 回覆內建的 Flex Message 字典以確保高可用性。

**Tech Stack:** Python, LINE Messaging API SDK (linebot-v3), JSON, pytest

---

### Task 1: 建立 Flex Message JSON 設定檔

**Files:**
- Create: `data/help_flex/card_1_stats.json`
- Create: `data/help_flex/card_2_players.json`
- Create: `data/help_flex/card_3_info.json`
- Create: `data/help_flex/card_4_admin.json`

- [ ] **Step 1: 建立 card_1_stats.json**
寫入內容到 `data/help_flex/card_1_stats.json`。亮色極簡風格，三個 secondary / sm 的戰績按鈕：
```json
{
  "type": "bubble",
  "body": {
    "type": "box",
    "layout": "vertical",
    "spacing": "md",
    "contents": [
      {
        "type": "box",
        "layout": "vertical",
        "spacing": "xs",
        "contents": [
          {
            "type": "text",
            "text": "🏆 聯賽戰績板",
            "weight": "bold",
            "size": "xl",
            "color": "#111111"
          },
          {
            "type": "text",
            "text": "查詢最新排名與歷史戰績",
            "size": "sm",
            "color": "#555555"
          }
        ]
      },
      {
        "type": "text",
        "text": "支援輸入 #戰績W3 或特定日期",
        "size": "xs",
        "color": "#777777",
        "wrap": true
      },
      {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "今日戰績",
              "text": "#戰績"
            }
          },
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "昨日戰績",
              "text": "#戰績昨天"
            }
          },
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "上週戰績",
              "text": "#戰績上週"
            }
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 2: 建立 card_2_players.json**
寫入內容到 `data/help_flex/card_2_players.json`。兩個玩家與對戰按鈕，以及球員手動查詢說明：
```json
{
  "type": "bubble",
  "body": {
    "type": "box",
    "layout": "vertical",
    "spacing": "md",
    "contents": [
      {
        "type": "box",
        "layout": "vertical",
        "spacing": "xs",
        "contents": [
          {
            "type": "text",
            "text": "⚔️ 玩家與對戰",
            "weight": "bold",
            "size": "xl",
            "color": "#111111"
          },
          {
            "type": "text",
            "text": "查詢本週即時比分與玩家數據",
            "size": "sm",
            "color": "#555555"
          }
        ]
      },
      {
        "type": "text",
        "text": "※ 球員數據請直接在對話框輸入：\n#球員 球員名字 (例：#球員 老詹)",
        "size": "xs",
        "color": "#777777",
        "wrap": true
      },
      {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "即時對決",
              "text": "#對戰"
            }
          },
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "玩家數據",
              "text": "#玩家"
            }
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 3: 建立 card_3_info.json**
寫入內容到 `data/help_flex/card_3_info.json`。三個聯賽資訊相關按鈕：
```json
{
  "type": "bubble",
  "body": {
    "type": "box",
    "layout": "vertical",
    "spacing": "md",
    "contents": [
      {
        "type": "box",
        "layout": "vertical",
        "spacing": "xs",
        "contents": [
          {
            "type": "text",
            "text": "🏀 聯賽資訊",
            "weight": "bold",
            "size": "xl",
            "color": "#111111"
          },
          {
            "type": "text",
            "text": "掌握賽季日程與聯賽資訊",
            "size": "sm",
            "color": "#555555"
          }
        ]
      },
      {
        "type": "text",
        "text": "選秀與開季倒數僅於休賽季啟用",
        "size": "xs",
        "color": "#777777",
        "wrap": true
      },
      {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "聯賽獎金",
              "text": "#獎金"
            }
          },
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "開季倒數",
              "text": "#開季"
            }
          },
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "選秀倒數",
              "text": "#選秀"
            }
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 4: 建立 card_4_admin.json**
寫入內容到 `data/help_flex/card_4_admin.json`。限白名單管理員顯示的管理專區按鈕：
```json
{
  "type": "bubble",
  "body": {
    "type": "box",
    "layout": "vertical",
    "spacing": "md",
    "contents": [
      {
        "type": "box",
        "layout": "vertical",
        "spacing": "xs",
        "contents": [
          {
            "type": "text",
            "text": "⚙️ 管理員專區",
            "weight": "bold",
            "size": "xl",
            "color": "#111111"
          },
          {
            "type": "text",
            "text": "聯盟後台與參數配置",
            "size": "sm",
            "color": "#555555"
          }
        ]
      },
      {
        "type": "text",
        "text": "限聯賽白名單管理員使用",
        "size": "xs",
        "color": "#777777",
        "wrap": true
      },
      {
        "type": "box",
        "layout": "vertical",
        "spacing": "sm",
        "contents": [
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "系統設置",
              "text": "#設置"
            }
          },
          {
            "type": "button",
            "style": "secondary",
            "height": "sm",
            "action": {
              "type": "message",
              "label": "設置暱稱",
              "text": "#設置玩家暱稱"
            }
          }
        ]
      }
    ]
  }
}
```

- [ ] **Step 5: 提交 JSON 設定檔**
```bash
git add data/help_flex/
git commit -m "feat: add help flex message JSON templates"
```

---

### Task 2: 撰寫測試案例（使現有與新增的測試失敗）

**Files:**
- Modify: `tests/test_misc_handler.py:207-260`

- [ ] **Step 1: 修改測試案例**
將原本的 `test_execute_help_success` 與 `test_execute_help_fallback` 替換為驗證 `reply_flex` 行為的測試，並新增一個白名單用戶測試。在 `tests/test_misc_handler.py` 中更新為以下程式碼：

```python
@patch("src.handlers.misc_handler.security_manager")
@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_help_success(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_sec_manager, mock_event, mock_config):
    handler = MiscHandler()
    
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    mock_load_config.return_value = {"LEAGUE_ID": "nba.l.12345"}
    
    # 一般使用者 (非白名單)
    mock_sec_manager.is_whitelisted.return_value = False
    mock_event.source.user_id = "user_regular"
    mock_event.message.text = "#幫助"
    
    with patch.object(handler, "reply_flex") as mock_reply_flex:
        handler.execute(mock_event, mock_config)
        mock_reply_flex.assert_called_once()
        args = mock_reply_flex.call_args[0]
        assert args[2] == "聯賽數據助手-幫助選單"
        flex_dict = args[3]
        assert flex_dict["type"] == "carousel"
        # 預期一般用戶看見 3 張卡片
        assert len(flex_dict["contents"]) == 3

@patch("src.handlers.misc_handler.security_manager")
@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_help_admin(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_sec_manager, mock_event, mock_config):
    handler = MiscHandler()
    
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    mock_load_config.return_value = {"LEAGUE_ID": "nba.l.12345"}
    
    # 管理員 (白名單)
    mock_sec_manager.is_whitelisted.return_value = True
    mock_event.source.user_id = "user_admin"
    mock_event.message.text = "#幫助"
    
    with patch.object(handler, "reply_flex") as mock_reply_flex:
        handler.execute(mock_event, mock_config)
        mock_reply_flex.assert_called_once()
        args = mock_reply_flex.call_args[0]
        flex_dict = args[3]
        # 預期管理員看見 4 張卡片
        assert len(flex_dict["contents"]) == 4

@patch("src.handlers.misc_handler.security_manager")
@patch("src.handlers.misc_handler.load_league_metadata")
@patch("src.handlers.misc_handler.get_pacific_date")
@patch("src.handlers.misc_handler.load_config")
@patch("src.handlers.misc_handler.ApiClient")
@patch("src.handlers.misc_handler.MessagingApi")
def test_execute_help_fallback(mock_messaging_api, mock_api_client, mock_load_config, mock_get_pacific, mock_load_meta, mock_sec_manager, mock_event, mock_config):
    handler = MiscHandler()
    mock_event.message.text = "#help"
    mock_event.source.user_id = "user_regular"
    
    mock_load_meta.return_value = {"end_date": "2026-04-12"}
    mock_get_pacific.return_value = "2026-05-29"
    mock_load_config.return_value = {"LEAGUE_ID": "nba.l.12345"}
    mock_sec_manager.is_whitelisted.return_value = False
    
    # 模擬外部檔案均不存在，觸發 Fallback 機制
    with patch("os.path.exists", return_value=False), \
         patch.object(handler, "reply_flex") as mock_reply_flex:
        handler.execute(mock_event, mock_config)
        mock_reply_flex.assert_called_once()
        args = mock_reply_flex.call_args[0]
        flex_dict = args[3]
        # Fallback 的常數應包含 3 個 Bubble
        assert flex_dict["type"] == "carousel"
        assert len(flex_dict["contents"]) == 3
```

- [ ] **Step 2: 執行測試以確保失敗**
執行 pytest 來驗證測試如期失敗：
Run: `pytest tests/test_misc_handler.py::test_execute_help_success tests/test_misc_handler.py::test_execute_help_admin tests/test_misc_handler.py::test_execute_help_fallback -v`
Expected: FAIL (因為目前的 `MiscHandler` 依舊回傳純文字 TextMessage，沒有呼叫 `reply_flex` 且卡片長度不符)。

- [ ] **Step 3: 提交測試程式碼**
```bash
git add tests/test_misc_handler.py
git commit -m "test: update help command tests to verify Flex Carousel and role-based access"
```

---

### Task 3: 修改實作代碼以載入 JSON 卡片與 Fallback 邏輯

**Files:**
- Modify: `src/handlers/misc_handler.py:290-317`

- [ ] **Step 1: 修改 _handle_help 實作**
修改 `src/handlers/misc_handler.py`，加入 `security_manager` 匯入，定義 `DEFAULT_HELP_FLEX` 常數，並更新 `_handle_help` 的實作。

```python
# 修改 src/handlers/misc_handler.py
# 需要在文件最上方確保導入了 json 與 security_manager:
# import json
# from src.utils.security import security_manager

    # 在 MiscHandler 類別中定義 DEFAULT_HELP_FLEX 常數:
    DEFAULT_HELP_FLEX = {
        "type": "carousel",
        "contents": [
            {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "xs",
                            "contents": [
                                {"type": "text", "text": "🏆 聯賽戰績板", "weight": "bold", "size": "xl", "color": "#111111"},
                                {"type": "text", "text": "查詢最新排名與歷史戰績", "size": "sm", "color": "#555555"}
                            ]
                        },
                        {"type": "text", "text": "支援輸入 #戰績W3 或特定日期", "size": "xs", "color": "#777777", "wrap": True},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "今日戰績", "text": "#戰績"}},
                                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "昨日戰績", "text": "#戰績昨天"}},
                                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "上週戰績", "text": "#戰績上週"}}
                            ]
                        }
                    ]
                }
            },
            {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "xs",
                            "contents": [
                                {"type": "text", "text": "⚔️ 玩家與對戰", "weight": "bold", "size": "xl", "color": "#111111"},
                                {"type": "text", "text": "查詢本週即時比分與玩家數據", "size": "sm", "color": "#555555"}
                            ]
                        },
                        {"type": "text", "text": "※ 球員數據請直接在對話框輸入：\n#球員 球員名字 (例：#球員 老詹)", "size": "xs", "color": "#777777", "wrap": True},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "即時對決", "text": "#對戰"}},
                                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "玩家數據", "text": "#玩家"}}
                            ]
                        }
                    ]
                }
            },
            {
                "type": "bubble",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "spacing": "md",
                    "contents": [
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "xs",
                            "contents": [
                                {"type": "text", "text": "🏀 聯賽資訊", "weight": "bold", "size": "xl", "color": "#111111"},
                                {"type": "text", "text": "掌握賽季日程與聯賽資訊", "size": "sm", "color": "#555555"}
                            ]
                        },
                        {"type": "text", "text": "選秀與開季倒數僅於休賽季啟用", "size": "xs", "color": "#777777", "wrap": True},
                        {
                            "type": "box",
                            "layout": "vertical",
                            "spacing": "sm",
                            "contents": [
                                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "聯賽獎金", "text": "#獎金"}},
                                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "開季倒數", "text": "#開季"}},
                                {"type": "button", "style": "secondary", "height": "sm", "action": {"type": "message", "label": "選秀倒數", "text": "#選秀"}}
                            ]
                        }
                    ]
                }
            }
        ]
    }
```

實作 `_handle_help` 方法：
```python
    def _handle_help(self, event: MessageEvent, configuration: Configuration) -> None:
        import json
        from src.utils.security import security_manager
        
        user_id = event.source.user_id if event.source and hasattr(event.source, "user_id") else None
        is_admin = security_manager.is_whitelisted(user_id)
        
        # 定義要加載的卡片檔名
        card_files = [
            "card_1_stats.json",
            "card_2_players.json",
            "card_3_info.json"
        ]
        if is_admin:
            card_files.append("card_4_admin.json")
            
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        help_flex_dir = os.path.join(project_root, "data", "help_flex")
        
        bubbles = []
        try:
            for card_file in card_files:
                file_path = os.path.join(help_flex_dir, card_file)
                if not os.path.exists(file_path):
                    raise FileNotFoundError(f"Card file not found: {file_path}")
                with open(file_path, "r", encoding="utf-8") as f:
                    card_data = json.load(f)
                    bubbles.append(card_data)
                    
            carousel_dict = {
                "type": "carousel",
                "contents": bubbles
            }
        except Exception as e:
            logging.error(f"[MiscHandler] 載入 Flex 幫助選單失敗: {e}，改用內建預設值 Fallback。")
            carousel_dict = self.DEFAULT_HELP_FLEX
            
        try:
            self.reply_flex(event, configuration, "聯賽數據助手-幫助選單", carousel_dict)
        except Exception as e:
            logging.error(f"[MiscHandler] 發送 Flex 幫助選單失敗: {e}，改用純文字 Fallback。")
            default_help = (
                "👋 您好！歡迎使用聯賽數據助手。\n\n"
                "【常用指令】\n"
                "● #戰績 ：查詢當日聯賽綜合戰績\n"
                "● #對戰 肥儒 ：查詢指定玩家當週即時 9-Cat 對決\n"
                "● #玩家 肥儒 ：查詢指定玩家今日累積數據與排名\n"
                "● #球員 老詹 ：查詢指定球員今日即時比賽表現\n\n"
                "※ 提示：輸入「#幫助」可獲取完整的指令複製清單。"
            )
            # 若 data/help.txt 存在，試圖讀取
            help_txt_path = os.path.join(project_root, "data", "help.txt")
            reply_content = default_help
            if os.path.exists(help_txt_path):
                try:
                    with open(help_txt_path, "r", encoding="utf-8") as f:
                        content = f.read().strip()
                        if content:
                            reply_content = content
                except Exception:
                    pass
            self.reply_text(event, configuration, reply_content)
```

- [ ] **Step 2: 執行測試驗證實作**
執行 pytest：
Run: `pytest tests/test_misc_handler.py -v`
Expected: PASS (所有測試均順利通過，沒有任何錯誤)。

- [ ] **Step 3: 提交實作程式碼**
```bash
git add src/handlers/misc_handler.py
git commit -m "feat: implement dynamic LINE Flex help Carousel with privilege checks and fallback"
```

---

### Task 4: 驗證整體測試集與合併分支

- [ ] **Step 1: 執行整個專案的單元測試**
Run: `pytest`
Expected: PASS (確保其他 Handler 或元件未受影響)。

- [ ] **Step 2: 向使用者請求合併至 dev 分支**
不自動合併分支。輸出訊息向使用者回報計畫已完成且測試通過，請求同意將 `feat/flex-help-command` 合併回 `dev` 分支。
