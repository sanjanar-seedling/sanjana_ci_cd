import asyncio
import logging
import time
from typing import Optional

from src.models.messages import StageResult, StageStatus

logger = logging.getLogger(__name__)

LANGUAGE_IMAGES = {
    "python": "python:3.11-slim",
    "javascript": "node:18-slim",
    "typescript": "node:18-slim",
    "go": "golang:1.21-alpine",
    "rust": "rust:1.73-slim",
    "java": "maven:3.9-eclipse-temurin-17",
}


async def run_in_docker(
    command: str,
    work_dir: str,
    language: str,
    timeout: int = 300,
    env_vars: Optional[dict[str, str]] = None,
) -> StageResult:
    """Run a command inside a Docker container with the repo mounted."""
    image = LANGUAGE_IMAGES.get(language, "ubuntu:22.04")

    docker_cmd = [
        "docker", "run", "--rm",
        "-v", f"{work_dir}:/workspace",
        "-w", "/workspace",
    ]

    if env_vars:
        for key, value in env_vars.items():
            docker_cmd.extend(["-e", f"{key}={value}"])

    docker_cmd.extend([image, "sh", "-c", command])

    start = time.monotonic()
    logger.info("Running in Docker (%s): %s", image, command)

    try:
        proc = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            duration = time.monotonic() - start
            logger.warning("Docker command timed out after %.1fs", duration)
            return StageResult(
                stage_id="",
                status=StageStatus.FAILED,
                exit_code=-1,
                stdout="",
                stderr=f"Docker command timed out after {timeout}s",
                duration_seconds=duration,
            )

        duration = time.monotonic() - start
        exit_code = proc.returncode or 0
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")

        status = StageStatus.SUCCESS if exit_code == 0 else StageStatus.FAILED
        logger.info("Docker command finished: exit_code=%d duration=%.1fs", exit_code, duration)

        return StageResult(
            stage_id="",
            status=status,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            duration_seconds=duration,
        )

    except FileNotFoundError:
        duration = time.monotonic() - start
        logger.error("Docker not installed or not running")
        return StageResult(
            stage_id="",
            status=StageStatus.FAILED,
            exit_code=-1,
            stdout="",
            stderr="Docker not installed or not running",
            duration_seconds=duration,
        )
    except OSError as e:
        duration = time.monotonic() - start
        logger.error("Docker execution failed: %s", e)
        return StageResult(
            stage_id="",
            status=StageStatus.FAILED,
            exit_code=-1,
            stdout="",
            stderr=str(e),
            duration_seconds=duration,
        )
