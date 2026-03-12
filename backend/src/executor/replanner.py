import json
import logging

from huggingface_hub import InferenceClient

from src.config import settings
from src.executor.scheduler import DAGScheduler
from src.models.messages import RecoveryPlan, RecoveryStrategy, StageResult, StageStatus
from src.models.pipeline import PipelineSpec, Stage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a CI/CD failure analyst. A pipeline stage has failed.
Analyze the error output and respond with a JSON object containing your recovery plan.

The JSON must have these fields:
- strategy: one of "FIX_AND_RETRY", "SKIP_STAGE", "ROLLBACK", "ABORT"
- reason: brief explanation of what went wrong and why you chose this strategy
- modified_command: (only for FIX_AND_RETRY) the corrected command to try
- rollback_steps: (only for ROLLBACK) list of commands to undo changes

Guidelines:
- FIX_AND_RETRY: Use when the error is fixable by modifying the command (e.g., missing flag, wrong path)
- SKIP_STAGE: Use for non-critical stages where failure is acceptable
- ROLLBACK: Use when a deployment or destructive action needs to be undone
- ABORT: Use when the error is fundamental and cannot be recovered from

Respond with ONLY the JSON object, no markdown or explanation."""

HF_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"


async def analyze_failure(
    stage: Stage, result: StageResult, spec: PipelineSpec
) -> RecoveryPlan:
    """Use Hugging Face Inference API to analyze a stage failure and recommend a recovery strategy."""
    if not settings.hf_api_key:
        logger.warning("HF_API_KEY is not set — returning ABORT")
        return RecoveryPlan(
            strategy=RecoveryStrategy.ABORT,
            reason="HF_API_KEY not configured, cannot analyze failure",
        )

    try:
        client = InferenceClient(api_key=settings.hf_api_key)

        # Truncate stderr to last 200 lines
        stderr_lines = result.stderr.strip().split("\n")
        truncated_stderr = "\n".join(stderr_lines[-200:])

        user_message = (
            f"Failed stage details:\n"
            f"- Stage ID: {stage.id}\n"
            f"- Agent type: {stage.agent.value}\n"
            f"- Command: {stage.command}\n"
            f"- Exit code: {result.exit_code}\n"
            f"- Duration: {result.duration_seconds:.1f}s\n\n"
            f"Stderr (last 200 lines):\n{truncated_stderr}\n\n"
            f"Pipeline goal: {spec.goal}\n"
            f"Stage is critical: {stage.critical}\n"
            f"Retry count remaining: {stage.retry_count}"
        )

        logger.info("Calling Hugging Face API for failure analysis of stage %s", stage.id)

        response = client.chat.completions.create(
            model=HF_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=1024,
        )

        response_text = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            response_text = "\n".join(lines)

        try:
            plan_data = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error("Failed to parse recovery plan JSON: %s", e)
            return RecoveryPlan(
                strategy=RecoveryStrategy.ABORT,
                reason=f"Failed to parse AI recovery suggestion: {e}",
            )

        plan = RecoveryPlan(**plan_data)
        logger.info(
            "Recovery plan for stage %s: strategy=%s reason=%s",
            stage.id,
            plan.strategy.value,
            plan.reason,
        )
        return plan

    except Exception as e:
        logger.warning("Hugging Face API call failed (%s), returning ABORT strategy", e)
        return RecoveryPlan(
            strategy=RecoveryStrategy.ABORT,
            reason="LLM unavailable",
        )


async def execute_recovery(
    plan: RecoveryPlan,
    stage: Stage,
    scheduler: DAGScheduler,
    agents: dict,
) -> StageResult | None:
    """Execute a recovery plan and return the result if retried."""
    from src.models.messages import StageRequest

    if plan.strategy == RecoveryStrategy.FIX_AND_RETRY:
        if not plan.modified_command:
            logger.error("FIX_AND_RETRY plan has no modified_command")
            scheduler.skip_dependents(stage.id)
            return None

        logger.info("Retrying stage %s with modified command: %s", stage.id, plan.modified_command)
        agent = agents.get(stage.agent)
        if not agent:
            logger.error("No agent found for type %s", stage.agent)
            return None

        request = StageRequest(
            stage_id=stage.id,
            command=plan.modified_command,
            working_dir=".",
            env_vars=stage.env_vars,
            timeout=stage.timeout_seconds,
        )
        result = await agent.execute(request)
        scheduler.mark_complete(stage.id, result.status, result)
        if result.status == StageStatus.FAILED:
            scheduler.skip_dependents(stage.id)
        return result

    elif plan.strategy == RecoveryStrategy.SKIP_STAGE:
        logger.info("Skipping stage %s: %s", stage.id, plan.reason)
        skip_result = StageResult(
            stage_id=stage.id,
            status=StageStatus.SKIPPED,
            stdout=f"Skipped: {plan.reason}",
        )
        scheduler.mark_complete(stage.id, StageStatus.SKIPPED, skip_result)
        return skip_result

    elif plan.strategy == RecoveryStrategy.ROLLBACK:
        logger.info("Rolling back stage %s with %d steps", stage.id, len(plan.rollback_steps))
        for step in plan.rollback_steps:
            logger.info("Rollback step: %s", step)
            agent = agents.get(stage.agent)
            if agent:
                request = StageRequest(
                    stage_id=f"{stage.id}_rollback",
                    command=step,
                    working_dir=".",
                    timeout=120,
                )
                await agent.execute(request)
        scheduler.skip_dependents(stage.id)
        return None

    else:  # ABORT
        logger.error("Aborting pipeline: %s", plan.reason)
        scheduler.skip_dependents(stage.id)
        return None
