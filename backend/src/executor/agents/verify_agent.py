import logging
import time

import httpx

from src.executor.agents.base import BaseAgent
from src.models.messages import StageRequest, StageResult, StageStatus

logger = logging.getLogger(__name__)


class VerifyAgent(BaseAgent):
    """Agent responsible for verification/health-check pipeline stages.

    If the command starts with 'curl', uses httpx for better error handling.
    Otherwise falls back to shell execution.
    """

    async def execute(self, request: StageRequest) -> StageResult:
        logger.info("VerifyAgent executing stage %s: %s", request.stage_id, request.command)

        if request.command.strip().startswith("curl"):
            return await self._http_check(request)

        result = await self.run_command(
            cmd=request.command,
            cwd=request.working_dir,
            timeout=request.timeout,
            env=request.env_vars or None,
        )
        result.stage_id = request.stage_id
        return result

    async def _http_check(self, request: StageRequest) -> StageResult:
        """Perform an HTTP health check using httpx instead of curl."""
        # Extract URL from curl command
        parts = request.command.split()
        url = None
        for i, part in enumerate(parts):
            if part.startswith("http://") or part.startswith("https://"):
                url = part
                break
            if part == "-f" and i + 1 < len(parts):
                candidate = parts[i + 1]
                if candidate.startswith("http"):
                    url = candidate
                    break

        if not url:
            # Can't parse URL, fall back to shell
            result = await self.run_command(
                cmd=request.command,
                cwd=request.working_dir,
                timeout=request.timeout,
                env=request.env_vars or None,
            )
            result.stage_id = request.stage_id
            return result

        # Strip trailing "||" and everything after
        url = url.split("||")[0].strip()

        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=request.timeout) as client:
                response = await client.get(url)
                duration = time.monotonic() - start

                if response.status_code < 400:
                    return StageResult(
                        stage_id=request.stage_id,
                        status=StageStatus.SUCCESS,
                        exit_code=0,
                        stdout=f"HTTP {response.status_code}: {response.text[:500]}",
                        stderr="",
                        duration_seconds=duration,
                        metadata={"status_code": response.status_code},
                    )
                else:
                    return StageResult(
                        stage_id=request.stage_id,
                        status=StageStatus.FAILED,
                        exit_code=1,
                        stdout=f"HTTP {response.status_code}: {response.text[:500]}",
                        stderr=f"Health check failed with status {response.status_code}",
                        duration_seconds=duration,
                        metadata={"status_code": response.status_code},
                    )
        except httpx.HTTPError as e:
            duration = time.monotonic() - start
            logger.error("HTTP health check failed: %s", e)
            return StageResult(
                stage_id=request.stage_id,
                status=StageStatus.FAILED,
                exit_code=1,
                stdout="",
                stderr=f"Health check error: {e}",
                duration_seconds=duration,
            )
