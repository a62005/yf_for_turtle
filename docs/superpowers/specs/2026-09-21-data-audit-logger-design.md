# 2026-09-21 Data 目錄異動稽核日誌設計文件 (Data Audit Logger Design Spec)

## 1. 背景與目標
在專案中，`data/` 目錄包含聯盟數據、快取、設定與安全性映射資料。由於這些資料會隨系統運行頻繁更新，已在 `.gitignore` 中被忽略，避免將動態資料提交到 Git。
然而，這導致無法追蹤與觀測 `data/` 目錄下的資料變動歷程。當資料遺失、異常覆蓋或數值錯誤時，難以進行除錯與排查。

本設計之目標為：
- 建立專屬的資料異動稽核日誌系統（`DataAuditLogger`），記錄所有對 `data/` 目錄內檔案的變動紀錄。
- 記錄維度包含：時間戳記、操作類型（`CREATE`、`OVERWRITE`、`DELETE`）、檔案相對路徑、異動後檔案大小（Bytes）、觸發呼叫端來源（Caller 模組與函式）。
- 支援獨立日誌檔輸出（預設 `logs/data_audit.log`）、大小輪替機制（`RotatingFileHandler`），並將 `logs/` 列入 `.gitignore`。
- 升級 `JsonStorage` 與提供通用輔助函式（`save_json_file`、`delete_data_file`），確保變動稽核集中且具備單一真實來源（Single Source of Truth）。
- 落實異常容錯（Fail-Safe）與測試沙盒（Sandboxing）原則，確保日誌紀錄不中斷業務流程，且測試時不污染正式日誌。

---

## 2. 系統架構與設計方案

### A. 稽核日誌核心 (`src/utils/audit_logger.py`)
1. **日誌記錄器設定**：
   - 建立獨立的 Logger 名稱：`"data_audit"`，避免被全域 root logger 的 handler 重複輸出。
   - 使用 `logging.handlers.RotatingFileHandler`：
     - 單一檔案上限：`5MB`（`5 * 1024 * 1024` bytes）
     - 備份歷史數量：5 個（`backupCount=5`）
     - 編碼：`utf-8`
   - 日誌儲存路徑：由 `src/utils/path_utils.py` 之 `LOGS_DIR` 統一管理（預設 `<BASE_DIR>/logs`），日誌檔為 `logs/data_audit.log`。
   - 在 `.gitignore` 中新增 `logs/`，避免日誌進入版本控制。
2. **日誌格式規格**：
   ```text
   2026-09-21 15:35:10 [INFO] [DATA_AUDIT] action=CREATE path=league/nba/123/123_season_stats.json size=4521B caller=fetcher.py:fetch_team_stats
   ```
   - `action`：`CREATE`（新檔案）、`OVERWRITE`（檔案已存在並覆蓋）、`DELETE`（刪除檔案）。
   - `path`：相對於 `data/` 目錄的路徑。若路徑在 `data/` 外，則顯示相對於專案根目錄的相對路徑。
   - `size`：異動完成後的檔案大小（如 `4521B`，若為 `DELETE` 則為 `0B`）。
   - `caller`：呼叫來源，透過 `inspect.stack()` 解析呼叫該儲存函式的檔名與函式（如 `fetcher.py:fetch_team_stats`），亦支援由參數顯式傳入自訂標籤。

### B. 統一資料操作函式 (`src/utils/audit_logger.py`)
提供全域輕量級的統一檔案操作介面：
1. `save_json_file(filepath: str, data: dict, indent: int = 4, caller_tag: str = None) -> str`
   - 檢查目標檔案是否存在以決定 `action` 為 `OVERWRITE` 或 `CREATE`。
   - 自動建立父層資料夾（如不存在）。
   - 將 `data` 序列化並寫入 `filepath`（`utf-8` 編碼）。
   - 取得寫入後檔案大小，並呼叫 `record_data_change(...)`。
   - 回傳 `filepath`。
2. `delete_data_file(filepath: str, caller_tag: str = None) -> bool`
   - 檢查檔案是否存在，存在則執行 `os.remove(filepath)`。
   - 記錄 `action="DELETE"`，`size="0B"`。
   - 回傳刪除是否成功。

### C. 儲存模組整合 (`src/storage.py`)
1. **`JsonStorage` 升級**：
   - `JsonStorage.save(self, data: dict, identifier: str, sub_dir: str = "", overwrite: bool = False) -> str`：
     內部改為調用 `save_json_file`，自動繼承檔案檢查、建立與稽核日誌記錄。
   - 在 `BaseStorage` 與 `JsonStorage` 新增 `delete(self, identifier: str, sub_dir: str = "") -> bool`：
     支援透過 identifier 與 sub_dir 刪除檔案，並自動調用 `delete_data_file` 進行稽核。

---

## 3. 異常容錯與測試沙盒 (Fail-Safe & Sandboxing)

### A. 異常容錯 (Fail-Safe)
- 稽核日誌記錄過程包含完整的 `try...except Exception` 區塊。
- 若發生磁碟寫入失敗、日誌輪替權限不足或路徑解析異常，`DataAuditLogger` 僅發出 `logging.warning` 警告，**嚴禁拋出例外中斷原有的資料儲存或業務主流程**。

### B. 測試沙盒機制 (Sandboxing)
- **遵循專案 `GEMINI.md` 規則**：
  - `src/utils/path_utils.py` 提供 `LOGS_DIR` 定義。
  - `DataAuditLogger` 支援動態讀取 `LOGS_DIR` 或提供 `get_audit_log_path()`。
  - 在單元測試中，透過 mock `src.utils.path_utils.LOGS_DIR` 指向 `tmp_path`，確保測試期間寫入的日誌完全隔離於臨時目錄中，禁止污染生產環境的 `logs/` 目錄。
  - 在 `tests/conftest.py` 中將測試產生的 `logs/`（若有）納入清理機制。

---

## 4. 改動檔案明細

1. **[.gitignore](file:///C:/Users/HsiehLink/Python/yf_for_turtle/.gitignore)**：
   - 新增 `logs/` 排除規則。
2. **[src/utils/path_utils.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/path_utils.py)**：
   - 定義 `LOGS_DIR = os.path.join(BASE_DIR, "logs")` 與輔助函式。
3. **[src/utils/audit_logger.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/utils/audit_logger.py)**（新增）：
   - 實作 `DataAuditLogger`、`record_data_change`、`save_json_file`、`delete_data_file`。
4. **[src/storage.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/src/storage.py)**：
   - 整合 `save_json_file`，實作 `delete` 方法。
5. **[tests/test_audit_logger.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_audit_logger.py)**（新增）：
   - 單元測試：CREATE、OVERWRITE、DELETE、Caller 追蹤、日誌輪替與容錯保護。
6. **[tests/test_storage.py](file:///C:/Users/HsiehLink/Python/yf_for_turtle/tests/test_storage.py)**：
   - 更新既有測試並驗證儲存操作均伴隨稽核日誌觸發。

---

## 5. 測試驗證計劃

1. **基礎異動測試**：
   - 驗證全新寫入檔案時，日誌記錄包含 `action=CREATE` 與檔案大小。
   - 驗證重複覆蓋檔案時，日誌記錄包含 `action=OVERWRITE`。
   - 驗證刪除檔案時，日誌記錄包含 `action=DELETE` 與 `size=0B`。
2. **Caller 溯源測試**：
   - 驗證自動從 call stack 捕捉到的函式名是否符合預期。
   - 驗證傳入自訂 `caller_tag` 時，日誌優先顯示自訂標籤。
3. **日誌輪替測試**：
   - 設定較小的 `maxBytes`，連續寫入多筆資料，驗證 `data_audit.log.1` 等備份檔如期產生。
4. **容錯保護測試**：
   - 模擬 Handler 拋出 I/O 例外，驗證 `save_json_file` 仍能成功寫入資料並返回，不中斷業務流程。
5. **沙盒清理驗證**：
   - 運行 `pytest`，確認專案目錄下的 `logs/` 與 `data/` 未產生任何測試髒檔案。
