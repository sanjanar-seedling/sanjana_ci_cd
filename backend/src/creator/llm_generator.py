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


def _fallback_stages(analysis: RepoAnalysis) -> list[Stage]:
    """Return a smart fallback pipeline based on repo analysis when the LLM call fails."""
    language = analysis.language

    # Build install command based on what files exist
    if analysis.has_requirements_txt:
        install_cmd = "pip install -r requirements.txt"
    elif analysis.package_manager == "pip":
        install_cmd = "pip install -e . || pip install . || echo 'No installable package found'"
    elif analysis.package_manager == "npm":
        install_cmd = "npm install"
    elif analysis.package_manager == "yarn":
        install_cmd = "yarn install"
    elif analysis.package_manager == "go":
        install_cmd = "go mod download"
    elif analysis.package_manager == "cargo":
        install_cmd = "cargo fetch"
    elif analysis.package_manager == "maven":
        install_cmd = "mvn dependency:resolve"
    elif analysis.package_manager == "gradle":
        install_cmd = "./gradlew dependencies || gradle dependencies"
    else:
        install_cmd = "echo 'No package manager detected — skipping install'"

    # Build test command
    if analysis.test_runner == "pytest":
        test_cmd = "python -m pytest --tb=short -q || echo 'No tests found'"
    elif analysis.test_runner in ("jest", "vitest", "mocha"):
        test_cmd = "npm test || echo 'No tests found'"
    elif analysis.has_tests:
        test_cmd = "echo 'Tests detected but no runner configured'"
    else:
        test_cmd = "echo 'No tests detected — skipping'"

    # Build lint command
    if language == "python":
        lint_cmd = "flake8 . --max-line-length=120 --exclude=.venv,venv,node_modules || true"
    elif language in ("javascript", "typescript"):
        lint_cmd = "npx eslint . --no-error-on-unmatched-pattern || true"
    elif language == "go":
        lint_cmd = "go vet ./... || true"
    elif language == "rust":
        lint_cmd = "cargo clippy || true"
    else:
        lint_cmd = "echo 'No linter configured — skipping'"

    # Build command
    if language in ("javascript", "typescript"):
        build_cmd = "npm run build || echo 'No build script — skipping'"
    elif language == "go":
        build_cmd = "go build ./..."
    elif language == "rust":
        build_cmd = "cargo build"
    elif language == "java":
        build_cmd = "mvn package -DskipTests || ./gradlew build -x test"
    elif language == "python":
        build_cmd = "python -m py_compile $(find . -name '*.py' -not -path './.venv/*' | head -20) && echo 'Build check passed'"
    else:
        build_cmd = "echo 'No build step configured — skipping'"

    return [
        Stage(
            id="install",
            agent=AgentType.BUILD,
            command=install_cmd,
            depends_on=[],
            timeout_seconds=120,
        ),
        Stage(
            id="lint",
            agent=AgentType.TEST,
            command=lint_cmd,
            depends_on=["install"],
            timeout_seconds=60,
            critical=False,
        ),
        Stage(
            id="test",
            agent=AgentType.TEST,
            command=test_cmd,
            depends_on=["install"],
            timeout_seconds=120,
            critical=False,
        ),
        Stage(
            id="build",
            agent=AgentType.BUILD,
            command=build_cmd,
            depends_on=["lint", "test"],
            timeout_seconds=120,
        ),
        Stage(
            id="integration_test",
            agent=AgentType.TEST,
            command="echo 'No integration tests configured — skipping'",
            depends_on=["build"],
            timeout_seconds=300,
            critical=False,
        ),
    ]


async def generate_with_llm(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Use Hugging Face Inference API to generate pipeline stages for unknown project types."""
    if not settings.hf_api_key:
        logger.warning("HF_API_KEY is not set — returning fallback pipeline")
        return _fallback_stages(analysis)

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
        return _fallback_stages(analysis)
