from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_python_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Python CI/CD pipeline with proper DAG parallelism."""
    install_cmd = "pip install -r requirements.txt"
    if analysis.package_manager == "pip" and (analysis.framework == "fastapi" or analysis.framework == "django"):
        install_cmd = "pip install -r requirements.txt"

    stages: list[Stage] = []

    # Stage 1: Install dependencies
    stages.append(
        Stage(
            id="install",
            agent=AgentType.BUILD,
            command=install_cmd,
            depends_on=[],
            timeout_seconds=120,
        )
    )

    # Stage 2 (parallel): lint, unit_test, security_scan
    stages.append(
        Stage(
            id="lint",
            agent=AgentType.TEST,
            command="flake8 .",
            depends_on=["install"],
            timeout_seconds=60,
            critical=False,
        )
    )

    test_cmd = "pytest"
    if analysis.test_runner == "unittest":
        test_cmd = "python -m unittest discover"

    stages.append(
        Stage(
            id="unit_test",
            agent=AgentType.TEST,
            command=test_cmd,
            depends_on=["install"],
            timeout_seconds=300,
        )
    )

    stages.append(
        Stage(
            id="security_scan",
            agent=AgentType.SECURITY,
            command="pip audit",
            depends_on=["install"],
            timeout_seconds=120,
            critical=False,
        )
    )

    # Stage 3: Build (if Dockerfile exists)
    build_depends = ["lint", "unit_test", "security_scan"]

    if analysis.has_dockerfile:
        stages.append(
            Stage(
                id="build",
                agent=AgentType.BUILD,
                command="docker build -t app .",
                depends_on=build_depends,
                timeout_seconds=600,
            )
        )
        deploy_depends = ["build"]
    else:
        deploy_depends = build_depends

    # Stage 4: Deploy (if goal mentions deployment)
    deploy_keywords = ["deploy", "release", "publish", "production", "staging"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    if should_deploy:
        if analysis.has_dockerfile:
            deploy_cmd = "docker push app"
        else:
            deploy_cmd = "python -m deploy"

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
                command="curl -f http://localhost:8000/health || exit 1",
                depends_on=["deploy"],
                timeout_seconds=60,
                retry_count=2,
            )
        )

    return stages
