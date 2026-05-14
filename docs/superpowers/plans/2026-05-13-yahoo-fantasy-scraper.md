# Yahoo Fantasy NBA Scraper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Python application to fetch Yahoo Fantasy NBA league data (teams and player stats) using the `yahoofantasy` package and save it locally as JSON.

**Architecture:** A modular Python script separated into `config`, `fetcher` (Yahoo API via wrapper), and `storage` (JSON output, extensible to DB), coordinated by `main.py`.

**Tech Stack:** Python 3, `yahoofantasy`, `pytest`, `python-dotenv`

---

### Task 1: Project Setup and AI Instructions

**Files:**
- Create: `requirements.txt`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `GEMINI.md`

- [x] **Step 1: Create requirements.txt**
- [x] **Step 2: Create .gitignore**
- [x] **Step 3: Create .env.example**
- [x] **Step 4: Create GEMINI.md**
- [x] **Step 5: Commit Setup**

---

### Task 2: Config Module

**Files:**
- Create: `src/config.py`
- Create: `tests/test_config.py`

- [x] **Step 1: Write the failing test**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Write minimal implementation**
- [x] **Step 4: Run test to verify it passes**
- [x] **Step 5: Commit**

---

### Task 3: Storage Module

**Files:**
- Create: `src/storage.py`
- Create: `tests/test_storage.py`

- [x] **Step 1: Write the failing test**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Write minimal implementation**
- [x] **Step 4: Run test to verify it passes**
- [x] **Step 5: Commit**

---

### Task 4: Fetcher Module

**Files:**
- Create: `src/fetcher.py`
- Create: `tests/test_fetcher.py`

- [x] **Step 1: Write the failing test**
- [x] **Step 2: Run test to verify it fails**
- [x] **Step 3: Write minimal implementation**
- [x] **Step 4: Run test to verify it passes**
- [x] **Step 5: Commit**

---

### Task 5: Main Entrypoint

**Files:**
- Create: `main.py`

- [x] **Step 1: Write main implementation**
- [x] **Step 2: Commit**
