# Distributed CI/CD Pipeline Orchestrator

An AI-powered system that automatically analyzes code repositories, generates CI/CD pipeline specifications as directed acyclic graphs (DAGs), executes them with specialized agents, and uses LLM-based intelligence for fallback pipeline generation and intelligent failure recovery.

## Architecture

The system is split into two core subsystems:

### Pipeline Creator
- **Repo Analyzer** — Clones a Git repository and detects language, framework, package manager, test runner, Dockerfile presence, and deployment target from the user's goal.
- **Template Engine** — Generates optimized pipeline DAGs for known languages (Python, Node.js, Go, Java, Rust) with parallel stage execution, deploy-target-aware commands, and real health checks.
- **LLM Fallback** — For unsupported languages, calls the Hugging Face Inference API (Meta-Llama-3-8B-Instruct) to generate pipeline stages as structured JSON.

### Pipeline Executor
- **DAG Scheduler** — Resolves stage dependencies using NetworkX, dispatches independent stages concurrently.
- **Specialized Agents** — Five agent types (Build, Test, Security, Deploy, Verify) execute stages locally or inside Docker containers.
- **AI Replanner** — When a critical stage fails, the LLM analyzes stderr output and recommends one of four recovery strategies: FIX_AND_RETRY, SKIP_STAGE, ROLLBACK, or ABORT. Recovery plans are broadcast to the frontend via WebSocket and displayed in the UI.

```
                +-----------------+
                |  React Frontend |
                |  (Vite + Flow)  |
                +--------+--------+
                         |
                    REST / WebSocket
                         |
                +--------+--------+
                |  FastAPI Backend |
                +--------+--------+
                    /          \
        +---------+--+    +----+---------+
        |  Pipeline  |    |   Pipeline   |
        |  Creator   |    |   Executor   |
        +-----+------+    +------+-------+
              |                  |
     +--------+-------+   +-----+------+
     | Repo Analyzer  |   | DAG Sched  |
     | Templates/LLM  |   | Agents     |
     +----------------+   | Replanner  |
                           +-----+------+
                                 |
                          +------+------+
                          |  PostgreSQL |
                          +-------------+
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.11+, FastAPI, Uvicorn |
| LLM | Hugging Face Inference API (Meta-Llama-3-8B-Instruct) |
| Frontend | React 18, Vite, TypeScript, Tailwind CSS |
| DAG Visualization | ReactFlow |
| Graph Processing | NetworkX |
| Database | PostgreSQL with SQLAlchemy (async) |
| Container Execution | Docker (optional) |
| Data Validation | Pydantic v2 |
| Real-time Updates | WebSockets |

## Features

- **Automatic Repo Analysis** — Detects language, framework, package manager, test runner, lockfile presence, Dockerfile, and monorepo structure.
- **Template-Based Pipeline Generation** — Optimized templates for Python, JavaScript/TypeScript, Go, Java, and Rust with parallel stage DAGs.
- **LLM Fallback** — Generates pipelines for any language via Hugging Face Inference API when no template exists.
- **Deployment Target Awareness** — Parses goal keywords to detect targets (AWS, GCP, Azure, Docker, Heroku, Kubernetes, staging, production) and generates target-specific deploy and health check commands.
- **Real Health Check Verification** — Uses `curl`, `kubectl`, or Heroku CLI to verify deployments are actually responding, with appropriate startup delays.
- **DAG-Based Parallel Execution** — Independent stages run concurrently; dependent stages wait for prerequisites.
- **Optional Docker Execution** — Run pipeline stages inside language-specific Docker containers with the repo mounted as a volume. Falls back to local execution if Docker is unavailable.
- **Real-Time WebSocket Updates** — Stage status changes (running, success, failed, skipped) and recovery plans stream to the frontend instantly.
- **AI Failure Recovery** — Four strategies displayed in the UI with colored badges:
  - **FIX_AND_RETRY** (green) — LLM modifies the command and retries
  - **SKIP_STAGE** (yellow) — Non-critical stage skipped
  - **ROLLBACK** (orange) — Undo destructive actions
  - **ABORT** (red) — Unrecoverable failure
- **Pipeline History** — All pipelines and results persist in PostgreSQL, survive page refreshes, with delete support.

## Setup

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Docker (optional, for container-based execution)

### Database

```bash
psql -U postgres -c "CREATE DATABASE cicd_orchestrator;"
```

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Create `backend/.env`:

```env
HF_API_KEY=your_huggingface_api_key
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/cicd_orchestrator
```

Start the server:

```bash
cd backend
source .venv/bin/activate
python -m src.api.main
```

The API runs on `http://localhost:8001`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI runs on `http://localhost:5173` and proxies API requests to the backend.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/pipelines?repo_url=...&goal=...&use_docker=false` | Analyze repo and generate pipeline |
| `POST` | `/pipelines/{id}/execute` | Execute a pipeline |
| `GET` | `/pipelines` | List all pipelines with results |
| `GET` | `/pipelines/{id}` | Get pipeline spec |
| `GET` | `/pipelines/{id}/results` | Get execution results |
| `DELETE` | `/pipelines/{id}` | Delete pipeline and results |
| `WS` | `/ws/{id}` | Real-time stage status updates |

## Project Structure

```
backend/
  src/
    api/           # FastAPI endpoints, WebSocket manager
    creator/       # Repo analyzer, pipeline generator, language templates
      templates/   # Python, Node.js, Go, Java, Rust pipeline templates
    executor/      # DAG scheduler, agents, Docker runner, AI replanner
    models/        # Pydantic models (Stage, PipelineSpec, StageResult)
    db/            # SQLAlchemy models, async session, repository
    config.py      # Settings from .env

frontend/
  src/
    api/           # REST client
    components/    # CreatePipeline, StageDetailPanel, ExecutionControls, DAG view
    context/       # React context for pipeline state
    hooks/         # usePipeline, useWebSocket
    types/         # TypeScript interfaces
```
