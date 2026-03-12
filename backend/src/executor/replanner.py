import json
import logging
import re

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


# ---------------------------------------------------------------------------
# Rule-based recovery — handles common CI/CD failures without needing an LLM
# ---------------------------------------------------------------------------

def _try_rule_based_recovery(
    stage: Stage, result: StageResult, spec: PipelineSpec
) -> RecoveryPlan | None:
    """Attempt to match the failure against known patterns and return a recovery plan.
    Returns None if no rule matches, so the LLM fallback is used."""

    stderr = (result.stderr or "").lower()
    stdout = (result.stdout or "").lower()
    combined = stderr + "\n" + stdout
    command = stage.command

    # ── Missing Python package / ModuleNotFoundError ──
    module_match = re.search(r"no module named ['\"]?(\w+)", combined)
    if module_match:
        missing_mod = module_match.group(1)
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason=f"Missing Python module '{missing_mod}' — installing it and retrying",
            modified_command=f"pip install {missing_mod} && {command}",
        )

    # ── pip install failures: no setup.py / pyproject.toml ──
    if "no setup.py" in combined or "does not appear to be a python project" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="No setup.py found — trying pip install with requirements.txt fallback",
            modified_command="pip install -r requirements.txt 2>/dev/null || pip install . 2>/dev/null || echo 'Install skipped — no installable package'",
        )

    # ── requirements.txt not found ──
    if "no such file or directory" in combined and "requirements" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="requirements.txt not found — trying alternative install methods",
            modified_command="pip install -e . 2>/dev/null || pip install . 2>/dev/null || echo 'No requirements found — install skipped'",
        )

    # ── npm install failures ──
    if "enoent" in combined and "package.json" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="package.json not found in working directory — trying to locate it",
            modified_command="if [ -f package.json ]; then npm install; elif [ -f */package.json ]; then cd $(dirname $(ls */package.json | head -1)) && npm install; else echo 'No package.json found'; fi",
        )

    # ── npm ERR! missing script ──
    if "missing script" in combined:
        script_match = re.search(r'missing script:\s*["\']?(\w+)', combined)
        script_name = script_match.group(1) if script_match else "unknown"
        return RecoveryPlan(
            strategy=RecoveryStrategy.SKIP_STAGE,
            reason=f"npm script '{script_name}' does not exist in package.json — skipping stage",
        )

    # ── Command not found ──
    cmd_not_found = re.search(r"(?:command not found|not found):\s*(\S+)", combined)
    if not cmd_not_found:
        cmd_not_found = re.search(r"(\S+):\s*(?:command not found|not found)", combined)
    if cmd_not_found:
        missing_cmd = cmd_not_found.group(1).strip("'\":")
        # Try common pip-installable tools
        pip_tools = {
            "flake8": "flake8", "pytest": "pytest", "black": "black",
            "mypy": "mypy", "pylint": "pylint", "pip-audit": "pip-audit",
            "isort": "isort", "ruff": "ruff", "bandit": "bandit",
        }
        if missing_cmd in pip_tools:
            return RecoveryPlan(
                strategy=RecoveryStrategy.FIX_AND_RETRY,
                reason=f"'{missing_cmd}' not installed — installing it and retrying",
                modified_command=f"pip install {pip_tools[missing_cmd]} && {command}",
            )
        return RecoveryPlan(
            strategy=RecoveryStrategy.SKIP_STAGE,
            reason=f"Command '{missing_cmd}' not found and cannot be auto-installed — skipping",
        )

    # ── Permission denied ──
    if "permission denied" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="Permission denied — retrying with relaxed permissions",
            modified_command=f"chmod +x . 2>/dev/null; {command}",
        )

    # ── Docker not running / not installed ──
    if "docker" in combined and ("daemon" in combined or "connect" in combined or "not found" in combined):
        return RecoveryPlan(
            strategy=RecoveryStrategy.ABORT,
            reason="Docker daemon is not running or Docker is not installed. Start Docker Desktop and re-execute.",
        )

    # ── Git clone failures ──
    if "fatal:" in combined and ("repository" in combined or "clone" in combined):
        if "authentication" in combined or "permission" in combined:
            return RecoveryPlan(
                strategy=RecoveryStrategy.ABORT,
                reason="Git authentication failed — check SSH keys or access tokens",
            )
        return RecoveryPlan(
            strategy=RecoveryStrategy.ABORT,
            reason="Git clone failed — check the repository URL and network connection",
        )

    # ── Timeout ──
    if result.exit_code == -1 or "timed out" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.FIX_AND_RETRY,
            reason="Stage timed out — retrying with double the timeout",
            modified_command=command,  # Same command, timeout is handled by the executor
        )

    # ── Python syntax / compilation errors ──
    if "syntaxerror" in combined or "indentationerror" in combined:
        return RecoveryPlan(
            strategy=RecoveryStrategy.ABORT,
            reason="Python syntax error in source code — cannot auto-fix, manual intervention needed",
        )

    # ── Test failures (exit code 1 with test runner) ──
    if result.exit_code == 1 and any(runner in command for runner in ["pytest", "jest", "mocha", "npm test"]):
        return RecoveryPlan(
            strategy=RecoveryStrategy.SKIP_STAGE,
            reason="Tests failed — some tests did not pass but this may be expected for the target repo",
        )

    # ── Lint failures ──
    if any(linter in command for linter in ["flake8", "eslint", "pylint", "ruff"]) and result.exit_code in (1, 2):
        return RecoveryPlan(
            strategy=RecoveryStrategy.SKIP_STAGE,
            reason="Linter found issues — code style violations are non-blocking",
        )

    # No rule matched
    return None


async def analyze_failure(
    stage: Stage, result: StageResult, spec: PipelineSpec
) -> RecoveryPlan:
    """Analyze a stage failure: first try rule-based recovery, then fall back to LLM."""

    # Try rule-based first
    rule_plan = _try_rule_based_recovery(stage, result, spec)
    if rule_plan:
        logger.info(
            "Rule-based recovery for stage %s: strategy=%s reason=%s",
            stage.id, rule_plan.strategy.value, rule_plan.reason,
        )
        return rule_plan

    # Fall back to LLM
    if not settings.hf_api_key:
        logger.warning("HF_API_KEY is not set and no rule matched — returning ABORT")
        return RecoveryPlan(
            strategy=RecoveryStrategy.ABORT,
            reason="No recovery rule matched and LLM is unavailable",
        )

    try:
        client = InferenceClient(api_key=settings.hf_api_key)

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
            "LLM recovery plan for stage %s: strategy=%s reason=%s",
            stage.id, plan.strategy.value, plan.reason,
        )
        return plan

    except Exception as e:
        logger.warning("Hugging Face API call failed (%s), returning ABORT strategy", e)
        return RecoveryPlan(
            strategy=RecoveryStrategy.ABORT,
            reason="LLM unavailable and no recovery rule matched",
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
