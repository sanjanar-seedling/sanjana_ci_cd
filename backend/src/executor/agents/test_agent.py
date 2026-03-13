import logging

from src.executor.agents.base import BaseAgent
from src.models.messages import StageRequest, StageResult

logger = logging.getLogger(__name__)


class TestAgent(BaseAgent):
    """Agent responsible for test and lint pipeline stages."""

    async def execute(self, request: StageRequest) -> StageResult:
        logger.info("TestAgent executing stage %s: %s", request.stage_id, request.command)
        result = await self.run_command(
            cmd=request.command,
            cwd=request.working_dir,
            timeout=request.timeout,
            env=request.env_vars or None,
        )
        result.stage_id = request.stage_id
        return result
