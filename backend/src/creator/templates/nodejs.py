from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_nodejs_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Node.js CI/CD pipeline with proper DAG parallelism."""
    install_cmd = "npm ci"
    if analysis.package_manager == "yarn":
        install_cmd = "yarn install --frozen-lockfile"
    elif analysis.package_manager == "pnpm":
        install_cmd = "pnpm install --frozen-lockfile"

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
            command="npm run lint",
            depends_on=["install"],
            timeout_seconds=60,
            critical=False,
        )
    )

    test_cmd = "npm test"
    if analysis.test_runner == "vitest":
        test_cmd = "npx vitest run"
    elif analysis.test_runner == "mocha":
        test_cmd = "npx mocha"

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
            command="npm audit --audit-level=moderate",
            depends_on=["install"],
            timeout_seconds=120,
            critical=False,
        )
    )

    # Stage 3: Build
    stages.append(
        Stage(
            id="build",
            agent=AgentType.BUILD,
            command="npm run build",
            depends_on=["lint", "unit_test", "security_scan"],
            timeout_seconds=300,
        )
    )

    # Stage 4: Deploy (if goal mentions deployment)
    deploy_keywords = ["deploy", "release", "publish", "production", "staging"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    if should_deploy:
        if analysis.has_dockerfile:
            deploy_cmd = "docker build -t app . && docker push app"
        else:
            deploy_cmd = "npm run deploy"

        stages.append(
            Stage(
                id="deploy",
                agent=AgentType.DEPLOY,
                command=deploy_cmd,
                depends_on=["build"],
                timeout_seconds=600,
                retry_count=1,
            )
        )

        # Stage 5: Health check
        stages.append(
            Stage(
                id="health_check",
                agent=AgentType.VERIFY,
                command="curl -f http://localhost:3000/health || exit 1",
                depends_on=["deploy"],
                timeout_seconds=60,
                retry_count=2,
            )
        )

    return stages
