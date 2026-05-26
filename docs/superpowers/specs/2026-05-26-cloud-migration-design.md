# Cloud Run Migration Design Spec

## 1. Context and Goals
The current bot runs locally, saving JSON files and images to the local hard drive, and uses `subprocess.Popen` for background tasks. To deploy to a serverless environment like Google Cloud Run, the architecture must handle ephemeral storage and stateless HTTP constraints.

**Goals:**
1. Migrate storage (images, metadata, JSON cache) from local disk to Google Cloud Storage (GCS).
2. Migrate background task triggering from `subprocess.Popen` to Google Cloud Pub/Sub.
3. Handle concurrent requests for the same data by implementing a "Task Waiting List" (Pending Jobs) mechanism.
4. Push notifications (Push Messages) to users when background tasks complete.
5. Package the application with Playwright using a custom Dockerfile.
6. **Maintain Local-Cloud Parity**: Ensure the bot can still run locally without GCP services via environment variable toggles.

## 2. Architecture & Implementation Design

### 2.1. Environment Configuration (`src/config.py` & `.env`)
Introduce a new environment variable `ENV` (defaults to `local`).
- If `ENV=production`:
  - `STORAGE_TYPE = gcs`
  - `TASK_MODE = pubsub`
  - Requires: `GCP_PROJECT_ID`, `GCS_BUCKET_NAME`, `PUBSUB_TOPIC_NAME`
- If `ENV=local`:
  - `STORAGE_TYPE = local`
  - `TASK_MODE = subprocess`

### 2.2. Storage Abstraction (`src/storage.py` & `src/cache_utils.py`)
- Refactor `src/storage.py` to include a `GCSStorage` class implementing `BaseStorage`.
- Refactor `src/cache_utils.py` (which handles `league_metadata.json` and empty records) to dynamically choose between local file reading/writing and GCS object reading/writing based on `ENV`.
- *Note: In production, LINE will serve images directly via the public GCS URL.*

### 2.3. Task Waiting List (Pending Jobs Tracker)
To handle concurrent requests and push messaging, we need a state tracker.
- Create `src/utils/job_tracker.py`.
- **Structure**: A dictionary mapping a unique task key (e.g., `2025-11-15_combined`) to a list of waiting LINE `user_id`s.
- **Local Mode**: Save to `data/pending_jobs.json`.
- **Production Mode**: Save to a designated GCS object `pending_jobs.json` (acting as a lightweight NoSQL DB since traffic is low).
- **Flow**:
  - Webhook checks if data exists.
  - If no: Webhook checks `job_tracker`.
  - If job already exists: Add `user_id` to the list. Do NOT trigger a new task.
  - If job does NOT exist: Create job with `[user_id]`. Trigger task (Subprocess or Pub/Sub).
  - Worker finishes task: Reads `job_tracker`, gets `user_ids`, sends Push Messages, deletes job entry.

### 2.4. Worker & Pub/Sub Integration (`main.py` & `bot.py`)
- **Webhook (`bot.py`)**: Add an endpoint `/pubsub-worker` to receive POST requests from Pub/Sub (Push subscription). This endpoint validates the Pub/Sub payload and directly calls the logic in `main.py`.
- **Dispatcher (`src/handlers/stats_handler.py`)**: Instead of `subprocess.Popen`, when `ENV=production`, it uses the `google-cloud-pubsub` client to publish a message containing `{ "target_date": "...", "target_week": "...", "reply_token": "..." }`.

### 2.5. Dockerfile
Create a `Dockerfile` at the project root based on Microsoft's official Playwright Python image.
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.40.0-jammy
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "bot.py"]
```

## 3. Implementation Plan
This will be executed in phases on the `feat/cloud-migration` branch:
1. **Phase 1: Environment & Storage Abstraction**. Implement `GCSStorage` and adapt `cache_utils.py` while ensuring local mode still passes all tests.
2. **Phase 2: Job Tracker & Push Messaging**. Implement the waiting list logic and update `stats_handler.py` and `main.py` to use it (tested locally first).
3. **Phase 3: Pub/Sub Integration & Docker**. Add the `/pubsub-worker` route, write the Dockerfile, and finalize production toggles.

## 4. Testing Strategy
- Ensure all existing local unit tests pass (Local Parity).
- Add mocking tests for GCS and Pub/Sub interactions.
- Test the Job Tracker logic specifically for race conditions (mocking two users requesting simultaneously).