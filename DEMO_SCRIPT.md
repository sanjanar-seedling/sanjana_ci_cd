# Demo Script — Distributed CI/CD Pipeline Orchestrator

Total runtime: ~10 minutes

---

## 1. Setup (30 sec)

Start all services before the demo begins.

```bash
# Terminal 1: PostgreSQL (if not already running)
brew services start postgresql
# or: sudo systemctl start postgresql

# Terminal 2: Backend
cd backend
source .venv/bin/activate
python -m src.api.main
# Runs on http://localhost:8001

# Terminal 3: Frontend
cd frontend
npm run dev
# Runs on http://localhost:5173
```

Open `http://localhost:5173` in a browser. You should see the **Create Pipeline** form.

---

## 2. Demo 1 — Python Pipeline (2 min)

**Goal:** Show automatic repo analysis and template-based pipeline generation.

1. Paste into Repository URL: `https://github.com/pallets/flask`
2. Enter goal: `build and test`
3. Click **Generate Pipeline**

**Talking points while it loads:**
- The backend clones the repo, scans for `requirements.txt`, `setup.py`, `pytest.ini`, `Dockerfile`, etc.
- Auto-detects **Python**, **Flask** framework, **pip** package manager

**Once the DAG appears:**
- Point out the stage layout: `install` → `lint` / `unit_test` / `security_scan` (parallel) → `build`
- Parallel stages run concurrently thanks to DAG scheduling with NetworkX

4. Click **Execute Pipeline**
5. Watch stages turn blue (running) → green (success) in real-time via WebSocket
6. Click on a stage node to open the **StageDetailPanel** — show stdout/stderr tabs, command, timeout, agent type

---

## 3. Demo 2 — Node.js Pipeline (2 min)

**Goal:** Show lockfile-aware dependency management.

1. Paste: `https://github.com/expressjs/express`
2. Goal: `build and test`
3. Click **Generate Pipeline**

**Talking points:**
- Detects `package-lock.json` → uses `npm ci` (deterministic installs) instead of `npm install`
- If the repo had `yarn.lock`, it would switch to `yarn install --frozen-lockfile`
- Template generates `npm run lint`, `npm test`, `npm audit`, `npm run build`

4. Execute and show real-time stage progression
5. Click the **Details** tab on a stage to show command, timeout, retry count, dependencies

---

## 4. Demo 3 — LLM Fallback (2 min)

**Goal:** Show what happens when no template exists.

> **Note:** Go actually has a built-in template now. To demonstrate the LLM fallback, use a less common language repo, or describe the behavior.

1. Paste: `https://github.com/gin-gonic/gin`
2. Goal: `build and test`
3. Click **Generate Pipeline**

**Talking points:**
- For the six supported languages (Python, JS, TS, Go, Java, Rust), optimized templates generate the pipeline instantly with no API call
- For unsupported languages, the system calls the **Hugging Face Inference API** (Meta-Llama-3-8B-Instruct)
- The LLM receives the full repo analysis (language, framework, package manager, Dockerfile, test runner) and returns a JSON array of stages
- If the LLM is unavailable, a safe fallback pipeline with placeholder commands is generated

4. Execute and show the generated stages

---

## 5. Demo 4 — Deploy Target Awareness (2 min)

**Goal:** Show how the system parses deployment targets from the goal string.

1. Paste: `https://github.com/pallets/flask`
2. Goal: `build and deploy to docker`
3. Click **Generate Pipeline**

**Talking points while it loads:**
- The system parses "docker" from the goal string using keyword detection
- Supported targets: `aws`, `gcp`, `azure`, `docker`, `heroku`, `kubernetes`/`k8s`, `staging`, `production`

**Once the DAG appears:**
- Point out the **deploy** stage: `docker build -t app . && docker run -d -p 8080:8080 app`
- Point out the **health_check** stage: `sleep 5 && curl -f http://localhost:8000/health || ...`
- Health checks are target-specific:
  - Docker: curl with sleep
  - Kubernetes: `kubectl get pods` + `kubectl rollout status`
  - Heroku: curl the Heroku app URL
- Health check is `critical: true` so the AI replanner kicks in if it fails

4. Try another goal: `deploy to kubernetes` — show `kubectl apply -f k8s/` in the deploy stage

---

## 6. Demo 5 — AI Replanning (1 min)

**Goal:** Show the failure recovery UI.

1. Use any executed pipeline where a stage has failed (or trigger one with a repo that has no tests)
2. Click on the **failed stage** (red node) in the DAG

**Talking points:**
- When a critical stage fails, the system sends the error output to the LLM
- The LLM analyzes stderr and recommends a recovery strategy
- The **Recovery Plan** section appears below the output:
  - **Green badge** — FIX_AND_RETRY: LLM suggests a corrected command (shown in a code block)
  - **Yellow badge** — SKIP_STAGE: Stage isn't essential, pipeline continues
  - **Orange badge** — ROLLBACK: Undo destructive deploy actions
  - **Red badge** — ABORT: Unrecoverable failure
- Recovery plans are broadcast via WebSocket in real-time
- The **StatusBanner** at the top shows the latest recovery event

3. Point out the modified command code block (if FIX_AND_RETRY)

---

## 7. Demo 6 — Docker Execution (1 min)

**Goal:** Show isolated container-based stage execution.

1. Create a new pipeline with any repo and goal
2. **Toggle on** "Run in Docker containers" (the switch below the goal input)
3. Click **Generate Pipeline**, then **Execute Pipeline**

**Talking points:**
- Each stage runs inside a language-specific Docker container:
  - Python → `python:3.11-slim`
  - Node.js → `node:18-slim`
  - Go → `golang:1.21-alpine`
  - Rust → `rust:1.73-slim`
  - Java → `maven:3.9-eclipse-temurin-17`
- The cloned repo is mounted at `/workspace` inside the container
- Environment variables are passed through to the container
- If Docker is not installed or not running, the system **automatically falls back** to local execution with a warning in the logs
- Docker isolation means pipeline stages can't affect the host system

---

## 8. Demo 7 — Persistence (30 sec)

**Goal:** Show that data survives page refreshes.

1. **Refresh the browser page** (F5 or Cmd+R)
2. Look at the **history sidebar** on the left — all previous pipelines are still there

**Talking points:**
- All pipeline specs and execution results are stored in **PostgreSQL**
- On page load, the frontend calls `GET /pipelines` to restore history
- Each history entry shows the repo URL, goal, timestamp, and overall status (success/failed)
- Hover over a history entry to reveal the **delete button** (trash icon)
- Click a history entry to reload the full DAG with all stage results

---

## Key Architecture Highlights

| Feature | Implementation |
|---------|---------------|
| **DAG-based parallel scheduling** | NetworkX validates acyclicity and resolves execution order; independent stages dispatch concurrently via `asyncio.gather()` |
| **Pydantic validation** | Every data model (Stage, PipelineSpec, StageResult, RecoveryPlan) is a Pydantic v2 BaseModel with strict typing |
| **WebSocket real-time updates** | `ConnectionManager` broadcasts stage status changes and recovery plans to all connected clients per pipeline |
| **Template + LLM hybrid generation** | Six language templates for instant generation; Hugging Face Inference API fallback for unknown languages |
| **4-strategy AI replanning** | LLM analyzes stderr context → FIX_AND_RETRY (modified command), SKIP_STAGE, ROLLBACK (undo steps), ABORT |
| **Docker isolation** | Language-specific containers with repo volume mount; transparent fallback to local execution |
| **Deploy target awareness** | Goal string parsing detects AWS/GCP/Azure/Docker/Heroku/K8s/staging/production → target-specific deploy and health check commands |
| **Persistent history** | PostgreSQL with SQLAlchemy async; cascade delete for pipeline + results cleanup |
