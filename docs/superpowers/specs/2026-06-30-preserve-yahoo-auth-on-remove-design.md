# 2026-06-30 移除聯盟時保留 Yahoo 授權設計文件 (Preserve Yahoo Auth on Remove Design Spec)

## 1. 背景與目標
在目前解綁聯盟 ID（執行 `#確定移除聯盟ID`）的邏輯中，當系統偵測到沒有其他群組綁定此聯盟時，會判定為孤立聯賽，並直接調用 `shutil.rmtree(league_dir)` 將該聯賽在 `data/league/[sport]/[id]` 下的資料夾整個刪除。
然而，這個目錄下包含了 Yahoo Fantasy 庫的授權快取憑證 `.yahoofantasy`。將其連同整個目錄刪除，會造成使用者的 OAuth 授權遺失，再次綁定時需要重新進行繁瑣的瀏覽器授權。

本優化案之目標為：
- 當解除綁定且無其他群組使用該聯盟時，**不刪除** `.yahoofantasy` 或與 `.yahoo` 相關的授權快取憑證。
- 其餘數據檔案（如 `metadata.json`, `team_mapping.json`, `week_*_stats.json`）與暫存/圖片子目錄（如 `daily/`, `weekly/`, `image/`）則一樣一律徹底清除。

---

## 2. 系統架構與設計方案

### A. 聯賽目錄清理邏輯修改
修改 [src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py) 中的 `#確定移除聯盟ID` 處理段落：
* 取代原本的 `shutil.rmtree(league_dir)` 暴力刪除。
* 改為遍歷 `league_dir` 中的所有項目：
  * 若遇到名稱為 `.yahoofantasy` 或包含 `.yahoo` 的檔案或目錄，將其保留。
  * 其餘所有項目（不論是檔案或是子目錄），則予以刪除。

### B. 修改的代碼區塊
在 [src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py) 中：
```diff
-            if not has_others:
-                league_dir = get_league_dir(removed_league_id)
-                if os.path.exists(league_dir):
-                    try:
-                        shutil.rmtree(league_dir)
-                        logging.info(f"[SetLeagueIdHandler] 已成功刪除孤立聯賽目錄: {league_dir}")
-                    except Exception as delete_error:
-                        logging.error(f"[SetLeagueIdHandler] 刪除聯賽目錄 {league_dir} 失敗: {delete_error}")
+            if not has_others:
+                league_dir = get_league_dir(removed_league_id)
+                if os.path.exists(league_dir):
+                    try:
+                        for item in os.listdir(league_dir):
+                            item_path = os.path.join(league_dir, item)
+                            if item == ".yahoofantasy" or ".yahoo" in item:
+                                logging.info(f"[SetLeagueIdHandler] 保留授權憑證: {item_path}")
+                                continue
+                            if os.path.isdir(item_path):
+                                shutil.rmtree(item_path)
+                            else:
+                                os.remove(item_path)
+                        logging.info(f"[SetLeagueIdHandler] 已成功清理孤立聯賽目錄 (保留授權憑證): {league_dir}")
+                    except Exception as delete_error:
+                        logging.error(f"[SetLeagueIdHandler] 清理聯賽目錄 {league_dir} 失敗: {delete_error}")
```

---

## 3. 改動檔案明細
- **[src/handlers/set_league_id_handler.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/handlers/set_league_id_handler.py)**：修改解綁聯盟 ID 後孤立聯賽目錄的清理邏輯，實作精確過濾與保留。

---

## 4. 測試驗證計劃
- **單元測試**：
  - 新增測試 `test_execute_remove_league_id_preserves_auth` 在 `tests/handlers/test_settings_and_setup.py`（或是對應的 set_league_id 測試檔中）。
  - 在測試中模擬孤立聯賽目錄下同時存在 `.yahoofantasy` 憑證與其他戰績檔案，執行解綁指令，並斷言測試結束後 `.yahoofantasy` 依然完好，其餘數據檔案皆被成功刪除。
  - 執行 pytest 驗證新增的測試與所有舊有測試皆全數通過。
