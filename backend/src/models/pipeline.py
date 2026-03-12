import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AgentType(str, Enum):
    BUILD = "build"
    TEST = "test"
    SECURITY = "security"
    DEPLOY = "deploy"
    VERIFY = "verify"


class Stage(BaseModel):
    id: str
    agent: AgentType
    command: str
    depends_on: list[str] = []
    timeout_seconds: int = 300
    retry_count: int = 0
    critical: bool = True
    env_vars: dict[str, str] = {}


class RepoAnalysis(BaseModel):
    language: str
    framework: Optional[str] = None
    package_manager: str
    has_dockerfile: bool = False
    has_tests: bool = False
    test_runner: Optional[str] = None
    is_monorepo: bool = False


class PipelineSpec(BaseModel):
    pipeline_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    repo_url: str = ""
    goal: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    analysis: RepoAnalysis
    stages: list[Stage]
