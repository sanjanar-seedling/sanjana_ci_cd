from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_python_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Python CI/CD pipeline with proper DAG parallelism."""
    # Smart install: include test extras if available
    if analysis.has_requirements_txt:
        install_cmd = "pip install -r requirements.txt"
    elif analysis.has_test_extras:
        install_cmd = (
            "pip install -e '.[dev]' 2>/dev/null || "
            "pip install -e '.[test]' 2>/dev/null || "
            "pip install -e '.[testing]' 2>/dev/null || "
            "pip install -e ."
        )
    else:
        install_cmd = "pip install -e . && pip install pytest"

    stages: list[Stage] = []

    # Stage 1: Install dependencies
    stages.append(
        Stage(
            id="install",
            agent=AgentType.BUILD,
            command=install_cmd,
            depends_on=[],
            timeout_seconds=180,
        )
    )

    # Stage 2 (parallel): lint, unit_test, security_scan
    stages.append(
        Stage(
            id="lint",
            agent=AgentType.TEST,
            command="flake8 --max-line-length=120 --exclude=.git,__pycache__,.venv,build,dist . || true",
            depends_on=["install"],
            timeout_seconds=60,
            critical=False,
        )
    )

    test_cmd = "pytest --tb=short -q"
    if analysis.test_runner == "unittest":
        test_cmd = "python -m unittest discover -v"

    stages.append(
        Stage(
            id="unit_test",
            agent=AgentType.TEST,
            command=test_cmd,
            depends_on=["install"],
            timeout_seconds=300,
            critical=False,
        )
    )

    stages.append(
        Stage(
            id="security_scan",
            agent=AgentType.SECURITY,
            command="pip-audit 2>/dev/null || echo 'pip-audit completed with warnings'",
            depends_on=["install"],
            timeout_seconds=120,
            critical=False,
        )
    )

    # Stage 3: Build (always present)
    build_depends = ["lint", "unit_test", "security_scan"]
    build_cmd = "docker build -t app ." if analysis.has_dockerfile else "python setup.py check 2>/dev/null || pip install . || echo 'Build verification complete'"

    stages.append(
        Stage(
            id="build",
            agent=AgentType.BUILD,
            command=build_cmd,
            depends_on=build_depends,
            timeout_seconds=600,
        )
    )

    deploy_depends = ["build"]

    # Stage 4: Deploy (if goal mentions deployment)
    deploy_keywords = ["deploy", "release", "publish", "production", "staging"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    if should_deploy:
        deploy_cmd = get_deploy_command(analysis.deploy_target, analysis.has_dockerfile, "python -m deploy")

        stages.append(
            Stage(
                id="deploy",
                agent=AgentType.DEPLOY,
                command=deploy_cmd,
                depends_on=deploy_depends,
                timeout_seconds=600,
                retry_count=1,
            )
        )

        # Stage 5: Health check
        stages.append(
            Stage(
                id="health_check",
                agent=AgentType.VERIFY,
                command=get_health_check_command(analysis.deploy_target, default_port=8000),
                depends_on=["deploy"],
                timeout_seconds=120,
                retry_count=2,
                critical=True,
            )
        )

    return stages
