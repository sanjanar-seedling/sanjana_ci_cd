import json
import logging

from huggingface_hub import InferenceClient

from src.config import settings
from src.models.pipeline import AgentType, RepoAnalysis, Stage

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

The health_check stage (agent: "verify") should use curl to verify the deployed application
is responding. Include appropriate sleep time (5-10s) for the service to start before checking.
Set critical: true and retry_count: 2 on health_check so the replanner can analyze failures.

Respond with ONLY the JSON array, no markdown formatting or explanation."""

HF_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct"


def _fallback_stages(language: str) -> list[Stage]:
    """Return a basic fallback pipeline when the LLM call fails."""
    return [
        Stage(
            id="install",
            agent=AgentType.BUILD,
            command=f"echo 'Install: configure manually for {language}'",
            depends_on=[],
            timeout_seconds=60,
        ),
        Stage(
            id="test",
            agent=AgentType.TEST,
            command=f"echo 'Test: configure manually for {language}'",
            depends_on=["install"],
            timeout_seconds=60,
        ),
        Stage(
            id="build",
            agent=AgentType.BUILD,
            command=f"echo 'Build: configure manually for {language}'",
            depends_on=["test"],
            timeout_seconds=60,
        ),
    ]


async def generate_with_llm(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Use Hugging Face Inference API to generate pipeline stages for unknown project types."""
    if not settings.hf_api_key:
        logger.warning("HF_API_KEY is not set — returning fallback pipeline")
        return _fallback_stages(analysis.language)

    try:
        client = InferenceClient(api_key=settings.hf_api_key)

        user_message = (
            f"Repository analysis:\n"
            f"- Language: {analysis.language}\n"
            f"- Framework: {analysis.framework}\n"
            f"- Package manager: {analysis.package_manager}\n"
            f"- Has Dockerfile: {analysis.has_dockerfile}\n"
            f"- Has requirements.txt: {analysis.has_requirements_txt}\n"
            f"- Has tests: {analysis.has_tests}\n"
            f"- Test runner: {analysis.test_runner}\n"
            f"- Is monorepo: {analysis.is_monorepo}\n"
            f"- Deploy target: {analysis.deploy_target}\n\n"
            f"Deployment goal: {goal}\n\n"
            f"Generate the CI/CD pipeline stages as a JSON array."
        )

        logger.info("Calling Hugging Face API for pipeline generation (language=%s)", analysis.language)

        response = client.chat.completions.create(
            model=HF_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=2048,
        )

        response_text = response.choices[0].message.content.strip()

        # Strip markdown code fences if present
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            lines = lines[1:]  # remove opening fence
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]  # remove closing fence
            response_text = "\n".join(lines)

        raw_stages = json.loads(response_text)
        stages = [Stage(**s) for s in raw_stages]
        logger.info("LLM generated %d pipeline stages", len(stages))
        return stages

    except Exception as e:
        logger.warning("Hugging Face API call failed (%s), returning fallback pipeline", e)
        return _fallback_stages(analysis.language)
