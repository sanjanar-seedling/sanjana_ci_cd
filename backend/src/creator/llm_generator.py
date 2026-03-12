import json
import logging

from google import genai

from src.config import settings
from src.models.pipeline import RepoAnalysis, Stage

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a CI/CD expert. Given repo analysis and deployment goal, generate pipeline stages as a JSON array.

Each stage has:
- id: unique string identifier
- agent: one of "build", "test", "security", "deploy", "verify"
- command: the shell command to run
- depends_on: list of stage ids this stage depends on (forms a DAG)
- timeout_seconds: integer timeout (default 300)
- retry_count: number of retries on failure (default 0)
- critical: boolean, if false the pipeline continues on failure (default true)
- env_vars: dict of environment variables (default {})

Ensure depends_on forms a valid DAG (no cycles). Start with install/setup stages,
then parallel lint/test/security, then build, then deploy, then verify.

Respond with ONLY the JSON array, no markdown formatting or explanation."""


async def generate_with_llm(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Use Gemini to generate pipeline stages for unknown project types."""
    client = genai.Client(api_key=settings.gemini_api_key)

    user_message = (
        f"Repository analysis:\n"
        f"- Language: {analysis.language}\n"
        f"- Framework: {analysis.framework}\n"
        f"- Package manager: {analysis.package_manager}\n"
        f"- Has Dockerfile: {analysis.has_dockerfile}\n"
        f"- Has tests: {analysis.has_tests}\n"
        f"- Test runner: {analysis.test_runner}\n"
        f"- Is monorepo: {analysis.is_monorepo}\n\n"
        f"Deployment goal: {goal}\n\n"
        f"Generate the CI/CD pipeline stages as a JSON array."
    )

    logger.info("Calling Gemini API for pipeline generation (language=%s)", analysis.language)

    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=user_message,
        config=genai.types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            max_output_tokens=2048,
        ),
    )

    response_text = response.text.strip()

    # Strip markdown code fences if present
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = lines[1:]  # remove opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]  # remove closing fence
        response_text = "\n".join(lines)

    try:
        raw_stages = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error("Failed to parse LLM response as JSON: %s", e)
        raise ValueError(f"LLM returned invalid JSON: {e}") from e

    stages = [Stage(**s) for s in raw_stages]
    logger.info("LLM generated %d pipeline stages", len(stages))
    return stages
