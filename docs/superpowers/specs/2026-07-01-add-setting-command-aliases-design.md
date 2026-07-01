# 2026-07-01 新增設置指令別名設計文件 (Add Setting Command Aliases Design Spec)

## 1. 背景與目標
在目前系統中，管理員可以使用 `#設置` 指令叫出系統設置 Flex Message 選單（包含綁定聯賽 ID、修改暱稱、調整獎金等）。
為了提高操作的易用性與容錯率，希望為其新增多個常用的判斷詞（別名）：`#設定`、`#Setting`、`#setting`，使其功能完全一致。

---

## 2. 系統架構與設計方案

### A. 變更一：SettingsHandler 判斷詞擴充
在 [src/handlers/settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py) 的 `can_handle` 函數中：
* 原有邏輯：
  ```python
  def can_handle(self, user_text: str) -> bool:
      return user_text.strip() == "#設置"
  ```
* 變更後邏輯：
  ```python
  def can_handle(self, user_text: str) -> bool:
      cmd = user_text.strip()
      return cmd in ("#設置", "#設定", "#Setting", "#setting")
  ```

### B. 變更二：IntentRouter 放行白名單擴充
在 [src/handlers/intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py) 的 `should_process` 函數中，有一段邏輯是在聯賽 ID 尚未綁定時，過濾放行特定的系統指令：
* 原有邏輯：
  ```python
  is_allowed_cmd = (user_text == "#設置" or user_text == "#我的ID" or user_text.startswith("#設置聯盟ID"))
  ```
* 變更後邏輯：
  ```python
  is_allowed_cmd = (
      user_text in ("#設置", "#設定", "#Setting", "#setting") or 
      user_text == "#我的ID" or 
      user_text.startswith("#設置聯盟ID")
  )
  ```

---

## 3. 改動檔案明細
- **[src/handlers/settings_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/settings_handler.py)**：修改指令判定範圍。
- **[src/handlers/intent_router.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/intent_router.py)**：擴展系統未綁定時的指令放行清單。

---

## 4. 測試驗證計劃
- **單元測試**：
  - 在 `tests/handlers/test_settings_handler.py`（或是 `tests/handlers/test_settings_and_setup.py`）中，新增針對 `#設定`、`#Setting`、`#setting` 別名觸發的單元測試，驗證它們都能正確叫出設置選單。
  - 在 `tests/test_intent_router.py` 中，新增在 `LEAGUE_ID` 未綁定下，使用這些別名是否能通過 `should_process` 的測試案例。
