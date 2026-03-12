import asyncio
import logging

from src.executor.agents import (
    BuildAgent,
    DeployAgent,
    SecurityAgent,
    TestAgent,
    VerifyAgent,
)
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
) -> StageResult:
    """Execute a single stage using the appropriate agent."""
    stage = scheduler.get_stage(stage_id)
    agent = agents.get(stage.agent)

    if not agent:
        logger.error("No agent for type %s", stage.agent)
        return StageResult(
            stage_id=stage_id,
            status=StageStatus.FAILED,
            stderr=f"No agent registered for type {stage.agent}",
        )

    scheduler.mark_running(stage_id)

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
    spec: PipelineSpec, working_dir: str = "."
) -> dict[str, StageResult]:
    """Execute a full pipeline using DAG-based scheduling.

    Dispatches ready stages concurrently, handles failures with
    retry logic and AI-powered replanning.
    """
    scheduler = DAGScheduler(spec)
    agents = {agent_type: cls() for agent_type, cls in AGENT_MAP.items()}

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

        # Run all ready stages concurrently
        tasks = [
            _execute_stage(stage_id, scheduler, agents, working_dir)
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
                stage = scheduler.get_stage(stage_id)
                if stage.critical:
                    scheduler.skip_dependents(stage_id)
                continue

            if result.status == StageStatus.SUCCESS:
                scheduler.mark_complete(stage_id, StageStatus.SUCCESS, result)
                continue

            # Stage failed — handle recovery
            stage = scheduler.get_stage(stage_id)

            # Check if non-critical — skip and continue
            if not stage.critical:
                logger.info("Non-critical stage %s failed, skipping", stage_id)
                result.status = StageStatus.SKIPPED
                scheduler.mark_complete(stage_id, StageStatus.SKIPPED, result)
                continue

            # Check retry count
            if stage.retry_count > 0:
                logger.info(
                    "Retrying stage %s (%d retries remaining)",
                    stage_id,
                    stage.retry_count,
                )
                stage.retry_count -= 1
                # Re-queue by keeping status as PENDING
                scheduler.mark_complete(stage_id, StageStatus.FAILED, result)
                # Reset to pending for retry
                scheduler._statuses[stage_id] = StageStatus.PENDING
                continue

            # Use AI replanner for critical failures
            try:
                plan = await analyze_failure(stage, result, spec)
                recovery_result = await execute_recovery(plan, stage, scheduler, agents)
                if recovery_result is None:
                    scheduler.mark_complete(stage_id, StageStatus.FAILED, result)
                    scheduler.skip_dependents(stage_id)
            except Exception as e:
                logger.error("Recovery failed for stage %s: %s", stage_id, e)
                scheduler.mark_complete(stage_id, StageStatus.FAILED, result)
                scheduler.skip_dependents(stage_id)

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
