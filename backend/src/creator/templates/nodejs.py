from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_nodejs_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Node.js CI/CD pipeline with proper DAG parallelism."""
    use_yarn = analysis.has_yarn_lock or analysis.package_manager == "yarn"
    use_pnpm = analysis.package_manager == "pnpm"
    scripts = analysis.available_scripts

    if use_yarn:
        run = "yarn"
        install_cmd = "yarn install --frozen-lockfile"
        audit_cmd = "yarn audit --level moderate || true"
    elif use_pnpm:
        run = "pnpm"
        install_cmd = "pnpm install --frozen-lockfile"
        audit_cmd = "pnpm audit --audit-level moderate || true"
    else:
        run = "npm"
        install_cmd = "npm ci" if analysis.has_package_lock else "npm install"
        audit_cmd = "npm audit --audit-level=moderate || true"

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
    has_lint = "lint" in scripts
    has_test = "test" in scripts
    has_build = "build" in scripts

    if has_lint:
        lint_cmd = f"{run} run lint"
    else:
        lint_cmd = "echo 'No lint script found, skipping'"

    stages.append(
        Stage(
            id="lint",
            agent=AgentType.TEST,
            command=lint_cmd,
            depends_on=["install"],
            timeout_seconds=60,
            critical=False,
        )
    )

    if has_test:
        test_cmd = f"{run} test"
        if analysis.test_runner == "vitest":
            test_cmd = "npx vitest run"
        elif analysis.test_runner == "mocha":
            test_cmd = "npx mocha"
    else:
        test_cmd = "echo 'No test script found, skipping'"

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
            command=audit_cmd,
            depends_on=["install"],
            timeout_seconds=120,
            critical=False,
        )
    )

    # Stage 3: Build
    if has_build:
        build_cmd = f"{run} run build"
    else:
        build_cmd = "echo 'No build script found — install verified, package is ready'"

    stages.append(
        Stage(
            id="build",
            agent=AgentType.BUILD,
            command=build_cmd,
            depends_on=["lint", "unit_test", "security_scan"],
            timeout_seconds=300,
        )
    )

    # Stage 4: Deploy (if goal mentions deployment)
    deploy_keywords = ["deploy", "release", "publish", "production", "staging"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    if should_deploy:
        deploy_cmd = get_deploy_command(analysis.deploy_target, analysis.has_dockerfile, f"{run} run deploy")

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
                command=get_health_check_command(analysis.deploy_target, default_port=3000),
                depends_on=["deploy"],
                timeout_seconds=120,
                retry_count=2,
                critical=True,
            )
        )

    return stages
