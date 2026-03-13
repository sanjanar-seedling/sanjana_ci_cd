import asyncio
import logging
import os
import time
from abc import ABC, abstractmethod

from src.models.messages import StageRequest, StageResult, StageStatus

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all pipeline execution agents."""

    @abstractmethod
    async def execute(self, request: StageRequest) -> StageResult:
        """Execute a pipeline stage and return the result."""

    async def run_command(
        self, cmd: str, cwd: str, timeout: int = 300, env: dict[str, str] | None = None
    ) -> StageResult:
        """Run a shell command asynchronously, capturing output."""
        start = time.monotonic()
        logger.info("Running command: %s (cwd=%s, timeout=%ds)", cmd, cwd, timeout)

        try:
            # Merge custom env vars with system environment so PATH etc. are preserved
            merged_env = None
            if env:
                merged_env = {**os.environ, **env}

            process = await asyncio.create_subprocess_shell(
                cmd,
                cwd=cwd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=merged_env,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                duration = time.monotonic() - start
                logger.warning("Command timed out after %.1fs: %s", duration, cmd)
                return StageResult(
                    stage_id="",
                    status=StageStatus.FAILED,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Command timed out after {timeout}s",
                    duration_seconds=duration,
                )

            duration = time.monotonic() - start
            exit_code = process.returncode or 0
            stdout = stdout_bytes.decode("utf-8", errors="replace")
            stderr = stderr_bytes.decode("utf-8", errors="replace")

            status = StageStatus.SUCCESS if exit_code == 0 else StageStatus.FAILED
            logger.info(
                "Command finished: exit_code=%d duration=%.1fs", exit_code, duration
            )

            return StageResult(
                stage_id="",
                status=status,
                exit_code=exit_code,
                stdout=stdout,
                stderr=stderr,
                duration_seconds=duration,
            )

        except OSError as e:
            duration = time.monotonic() - start
            logger.error("Failed to execute command: %s", e)
            return StageResult(
                stage_id="",
                status=StageStatus.FAILED,
                exit_code=-1,
                stdout="",
                stderr=str(e),
                duration_seconds=duration,
            )
