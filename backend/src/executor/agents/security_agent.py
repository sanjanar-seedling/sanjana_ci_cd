import logging

from src.executor.agents.base import BaseAgent
from src.models.messages import StageRequest, StageResult

logger = logging.getLogger(__name__)


class SecurityAgent(BaseAgent):
    """Agent responsible for security scanning pipeline stages."""

    async def execute(self, request: StageRequest) -> StageResult:
        logger.info("SecurityAgent executing stage %s: %s", request.stage_id, request.command)
        result = await self.run_command(
            cmd=request.command,
            cwd=request.working_dir,
            timeout=request.timeout,
            env=request.env_vars or None,
        )
        result.stage_id = request.stage_id
        return result
