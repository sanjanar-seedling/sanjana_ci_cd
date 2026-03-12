from enum import Enum
from typing import Optional

from pydantic import BaseModel


class StageStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class StageRequest(BaseModel):
    stage_id: str
    command: str
    working_dir: str
    env_vars: dict[str, str] = {}
    timeout: int = 300
    artifacts_from: list[str] = []


class StageResult(BaseModel):
    stage_id: str
    status: StageStatus
    exit_code: int = -1
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0
    artifacts: list[str] = []
    metadata: dict = {}


class RecoveryStrategy(str, Enum):
    FIX_AND_RETRY = "FIX_AND_RETRY"
    SKIP_STAGE = "SKIP_STAGE"
    ROLLBACK = "ROLLBACK"
    ABORT = "ABORT"


class RecoveryPlan(BaseModel):
    strategy: RecoveryStrategy
    reason: str
    modified_command: Optional[str] = None
    rollback_steps: list[str] = []
