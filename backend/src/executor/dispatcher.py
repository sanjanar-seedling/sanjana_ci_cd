import asyncio
import logging
from typing import Callable, Awaitable

from src.executor.agents import (
    BuildAgent,
    DeployAgent,
    SecurityAgent,
    TestAgent,
    VerifyAgent,
)
from src.executor.docker_runner import run_in_docker
from src.executor.replanner import analyze_failure, execute_recovery
from src.executor.scheduler import DAGScheduler
from src.models.messages import StageRequest, StageResult, StageStatus
from src.models.pipeline import AgentType, PipelineSpec

logger = logging.getLogger(__name__)

AGENT_MAP = {
    AgentType.BUILD: BuildAgent,
    AgentType.TEST: TestAgent,
    AgentType.SECURITY: SecurityAgent,
    AgentType.DEPLOY: DeployAgent,
    AgentType.VERIFY: VerifyAgent,
}


async def _execute_stage(
    stage_id: str,
    scheduler: DAGScheduler,
    agents: dict,
    working_dir: str,
    use_docker: bool = False,
    language: str = "",
) -> StageResult:
    """Execute a single stage using the appropriate agent."""
    stage = scheduler.get_stage(stage_id)

    scheduler.mark_running(stage_id)

    # Docker execution path
    if use_docker:
        result = await run_in_docker(
            command=stage.command,
            work_dir=working_dir,
            language=language,
            timeout=stage.timeout_seconds,
            env_vars=stage.env_vars or None,
        )
        # If Docker fails (not installed), fall back to local execution
        if result.status == StageStatus.FAILED and "Docker not installed" in result.stderr:
            logger.warning("Docker unavailable, falling back to local execution for stage %s", stage_id)
        else:
            result.stage_id = stage_id
            return result

    # Local execution path
    agent = agents.get(stage.agent)
    if not agent:
        logger.error("No agent for type %s", stage.agent)
        return StageResult(
            stage_id=stage_id,
            status=StageStatus.FAILED,
            stderr=f"No agent registered for type {stage.agent}",
        )

    request = StageRequest(
        stage_id=stage_id,
        command=stage.command,
        working_dir=working_dir,
        env_vars=stage.env_vars,
        timeout=stage.timeout_seconds,
    )

    result = await agent.execute(request)
    return result


async def run_pipeline(
    spec: PipelineSpec,
    working_dir: str = ".",
    on_update: Callable[[dict], Awaitable[None]] | None = None,
) -> dict[str, StageResult]:
    """Execute a full pipeline using DAG-based scheduling.

    Dispatches ready stages concurrently, handles failures with
    retry logic and AI-powered replanning.
    """
    scheduler = DAGScheduler(spec)
    agents = {agent_type: cls() for agent_type, cls in AGENT_MAP.items()}
    use_docker = spec.use_docker
    language = spec.analysis.language if spec.analysis else ""

    if use_docker:
        logger.info("Docker execution enabled for pipeline %s", spec.pipeline_id)

    async def _broadcast(data: dict) -> None:
        if on_update:
            await on_update(data)

    logger.info(
        "Starting pipeline %s with %d stages", spec.pipeline_id, len(spec.stages)
    )

    while not scheduler.is_finished():
        ready = scheduler.get_ready_stages()

        if not ready:
            # No stages ready but not finished — deadlock or all remaining are blocked
            logger.warning("No ready stages but pipeline not finished — breaking")
            break

        logger.info("Dispatching %d stages: %s", len(ready), ready)

        # Broadcast running status for all ready stages
        for stage_id in ready:
            await _broadcast({
                "stage_id": stage_id,
                "status": "running",
            })

        # Run all ready stages concurrently
        tasks = [
            _execute_stage(stage_id, scheduler, agents, working_dir, use_docker, language)
            for stage_id in ready
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        for stage_id, result in zip(ready, results):
            if isinstance(result, Exception):
                logger.error("Stage %s raised exception: %s", stage_id, result)
                error_result = StageResult(
                    stage_id=stage_id,
                    status=StageStatus.FAILED,
                    stderr=str(result),
                )
                scheduler.mark_complete(stage_id, StageStatus.FAILED, error_result)
                await _broadcast({"stage_id": stage_id, "status": "failed"})
                stage = scheduler.get_stage(stage_id)
                if stage.critical:
                    scheduler.skip_dependents(stage_id)
                continue

            if result.status == StageStatus.SUCCESS:
                scheduler.mark_complete(stage_id, StageStatus.SUCCESS, result)
                await _broadcast({
                    "stage_id": stage_id,
                    "status": "success",
                    "duration_seconds": result.duration_seconds,
                })
                continue

            # Stage failed — handle recovery
            stage = scheduler.get_stage(stage_id)

            # Check if non-critical — skip and continue
            if not stage.critical:
                logger.info("Non-critical stage %s failed, skipping", stage_id)
                result.status = StageStatus.SKIPPED
                scheduler.mark_complete(stage_id, StageStatus.SKIPPED, result)
                await _broadcast({"stage_id": stage_id, "status": "skipped"})
                continue

            # Check retry count
            if stage.retry_count > 0:
                logger.info(
                    "Retrying stage %s (%d retries remaining)",
                    stage_id,
                    stage.retry_count,
                )
                stage.retry_count -= 1
                scheduler.mark_complete(stage_id, StageStatus.FAILED, result)
                scheduler._statuses[stage_id] = StageStatus.PENDING
                await _broadcast({"stage_id": stage_id, "status": "running"})
                continue

            # Use AI replanner for critical failures
            try:
                plan = await analyze_failure(stage, result, spec)

                # Broadcast recovery plan through WebSocket
                await _broadcast({
                    "stage_id": stage_id,
                    "status": "failed",
                    "recovery_strategy": plan.strategy.value,
                    "recovery_reason": plan.reason,
                    "modified_command": plan.modified_command,
                })

                recovery_result = await execute_recovery(plan, stage, scheduler, agents)
                if recovery_result is None:
                    scheduler.mark_complete(stage_id, StageStatus.FAILED, result)
                    scheduler.skip_dependents(stage_id)
                elif recovery_result.status == StageStatus.SUCCESS:
                    await _broadcast({
                        "stage_id": stage_id,
                        "status": "success",
                        "duration_seconds": recovery_result.duration_seconds,
                    })
            except Exception as e:
                logger.error("Recovery failed for stage %s: %s", stage_id, e)
                scheduler.mark_complete(stage_id, StageStatus.FAILED, result)
                scheduler.skip_dependents(stage_id)
                await _broadcast({"stage_id": stage_id, "status": "failed"})

    all_results = scheduler.get_all_results()
    succeeded = sum(1 for r in all_results.values() if r.status == StageStatus.SUCCESS)
    failed = sum(1 for r in all_results.values() if r.status == StageStatus.FAILED)
    skipped = sum(1 for r in all_results.values() if r.status == StageStatus.SKIPPED)

    logger.info(
        "Pipeline %s complete: %d succeeded, %d failed, %d skipped",
        spec.pipeline_id,
        succeeded,
        failed,
        skipped,
    )

    return all_results
