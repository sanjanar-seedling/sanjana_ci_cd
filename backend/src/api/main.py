import logging

import uvicorn
from fastapi import FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from src.api.websocket import manager
from src.creator.analyzer import analyze_repo
from src.creator.generator import generate_pipeline
from src.executor.dispatcher import run_pipeline
from src.models.messages import StageResult
from src.models.pipeline import PipelineSpec

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="CI/CD Pipeline Orchestrator")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for demo (replace with SQLite later)
pipelines: dict[str, PipelineSpec] = {}
results: dict[str, dict[str, StageResult]] = {}


@app.post("/pipelines")
async def create_pipeline(
    repo_url: str = Query(..., description="Git repository URL"),
    goal: str = Query(..., description="Deployment goal"),
) -> PipelineSpec:
    """Analyze a repository and generate a pipeline spec."""
    analysis = await analyze_repo(repo_url)
    spec = await generate_pipeline(analysis, goal, repo_url=repo_url)
    pipelines[spec.pipeline_id] = spec
    logger.info("Created pipeline %s for %s", spec.pipeline_id, repo_url)
    return spec


@app.post("/pipelines/{pipeline_id}/execute")
async def execute_pipeline(pipeline_id: str) -> dict[str, StageResult]:
    """Execute a generated pipeline."""
    spec = pipelines.get(pipeline_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    result = await run_pipeline(spec)
    results[pipeline_id] = result
    return result


@app.get("/pipelines/{pipeline_id}")
async def get_pipeline(pipeline_id: str) -> PipelineSpec:
    """Get a pipeline spec by ID."""
    spec = pipelines.get(pipeline_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return spec


@app.get("/pipelines/{pipeline_id}/results")
async def get_results(pipeline_id: str) -> dict[str, StageResult]:
    """Get execution results for a pipeline."""
    result = results.get(pipeline_id)
    if not result:
        raise HTTPException(status_code=404, detail="Results not found")
    return result


@app.websocket("/ws/{pipeline_id}")
async def websocket_endpoint(websocket: WebSocket, pipeline_id: str) -> None:
    """WebSocket endpoint for real-time pipeline status updates."""
    await manager.connect(websocket, pipeline_id)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, pipeline_id)


if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8001, reload=True)
