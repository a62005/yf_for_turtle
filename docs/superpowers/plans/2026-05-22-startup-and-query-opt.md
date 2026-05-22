# 啟動優化與查詢規則調整實作計畫

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 確保 `bot.py` 啟動時自動釋放 Port 5001，並在休賽季期間解除 14:00 的查詢限制。

---

### Task 1: 實作 Port 自動清理

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: 在 bot.py 中添加清理函式**

```python
import psutil
import logging

def cleanup_port(port):
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            for conns in proc.connections(kind='inet'):
                if conns.laddr.port == port:
                    logging.info(f"[SYSTEM] 發現佔用 Port {port} 的進程 (PID: {proc.pid})，正在關閉...")
                    proc.terminate()
                    proc.wait(timeout=3)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
            pass
```

- [ ] **Step 2: 在 main 區塊調用 cleanup_port**

在 `if __name__ == "__main__":` 最開頭：
```python
if __name__ == "__main__":
    cleanup_port(5001)
    # ...
```

- [ ] **Step 3: 提交變更**

```bash
git add bot.py
git commit -m "feat: auto-kill processes occupying port 5001 on startup"
```

---

### Task 2: 調整休賽季查詢限制

**Files:**
- Modify: `bot.py`

- [ ] **Step 1: 在 handle_message 實作休賽季判斷**

```python
    # 取得賽季結束日期
    meta = load_league_metadata()
    today_pacific = get_pacific_date()
    # 判斷是否休賽季 (注意日期格式需一致)
    is_offseason = meta.get('end_date') and today_pacific > meta['end_date']
```

- [ ] **Step 2: 更新時間門檻判斷式**

```python
    # 修改原本的時間閘條件
    # 原: if is_current and get_tw_hour() < 14:
    # 新:
    if is_current and not is_offseason and get_tw_hour() < 14:
        # 回覆「請於 14:00 後查詢」
```

- [ ] **Step 3: 提交變更**

```bash
git add bot.py
git commit -m "feat: lift 14:00 query restriction during off-season"
```

---

### Execution Handoff
Plan complete and saved to `docs/superpowers/plans/2026-05-22-startup-and-query-opt.md`.

1. **Subagent-Driven (推薦)**
2. **Inline Execution**

Which approach?
