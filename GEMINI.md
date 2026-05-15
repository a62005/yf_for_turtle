# Yahoo Fantasy NBA Scraper AI Instructions

## Context
This project is a Python scraper for Yahoo Fantasy NBA data. It uses the `yahoofantasy` package to handle OAuth2 and API interactions.

## Architecture Rules
1. **Separation of Concerns**: `fetcher.py` handles API calls, `storage.py` handles saving data, `config.py` handles environment variables.
2. **Data Format**: Currently outputs to JSON in the `data/` directory. If changing to a database, implement a new class in `storage.py` conforming to a common interface.
3. **Authentication**: Handled via `oauth2.json` which must NOT be committed. **CRITICAL: NEVER delete, modify, or overwrite the `.yahoofantasy` directory or `oauth2.json` file. These contain user credentials and are strictly off-limits.**
4. **Testing**: Use `pytest`. Run tests before committing.

## Setup Instructions
1. `pip install -r requirements.txt`
2. Copy `.env.example` to `.env` and fill in `LEAGUE_ID`.
3. First run will require browser-based OAuth authorization to generate `oauth2.json`.

## Git Workflow Rules
- **Branching Strategy**: The `master` branch is protected and no direct commits are allowed.
- **Main Development**: All work must be based on the `dev` branch. **CRITICAL: DEV 一律只能做 BRANCH 與 MERGE，禁止在 DEV 上直接 COMMIT。任何新需求或修改，一律先從 DEV 開新分支。**
- **Feature/Fix Branches**: Create new branches from `dev` using the naming convention `feat/xxxx` for new features or `fix/xxxx` for bug fixes.
- **Merging**: Once implementation is complete, merge the `feat/xxxx` or `fix/xxxx` branch back into `dev`. **CRITICAL: Merging into the `dev` branch requires explicit user approval. Do NOT automatically merge branches into `dev` without asking.**

## Language Preference
- Always respond to the user in Traditional Chinese (繁體中文) via the CLI.