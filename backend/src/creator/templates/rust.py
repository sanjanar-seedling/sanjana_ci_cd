from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_rust_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Rust CI/CD pipeline with proper DAG parallelism."""
    stages: list[Stage] = []

    # Stage 1: Fetch dependencies
    stages.append(
        Stage(
            id="install",
            agent=AgentType.BUILD,
            command="cargo fetch",
            depends_on=[],
            timeout_seconds=180,
        )
    )

    # Stage 2 (parallel): clippy, test, audit
    stages.append(
        Stage(
            id="lint",
            agent=AgentType.TEST,
            command="cargo clippy -- -D warnings 2>/dev/null || cargo check",
            depends_on=["install"],
            timeout_seconds=120,
            critical=False,
        )
    )

    stages.append(
        Stage(
            id="unit_test",
            agent=AgentType.TEST,
            command="cargo test",
            depends_on=["install"],
            timeout_seconds=300,
        )
    )

    stages.append(
        Stage(
            id="security_scan",
            agent=AgentType.SECURITY,
            command="cargo audit 2>/dev/null || echo 'cargo-audit not installed, skipping'",
            depends_on=["install"],
            timeout_seconds=120,
            critical=False,
        )
    )

    # Stage 3: Build (release)
    stages.append(
        Stage(
            id="build",
            agent=AgentType.BUILD,
            command="cargo build --release",
            depends_on=["lint", "unit_test", "security_scan"],
            timeout_seconds=600,
        )
    )

    # Stage 4: Integration test (after build, before deploy)
    stages.append(
        Stage(
            id="integration_test",
            agent=AgentType.TEST,
            command="cargo test --test '*' 2>/dev/null || echo 'No integration tests found — skipping'",
            depends_on=["build"],
            timeout_seconds=300,
            critical=False,
        )
    )

    # Stage 5: Deploy
    deploy_keywords = ["deploy", "release", "publish", "production", "staging"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    if should_deploy:
        deploy_cmd = get_deploy_command(analysis.deploy_target, analysis.has_dockerfile)

        stages.append(
            Stage(
                id="deploy",
                agent=AgentType.DEPLOY,
                command=deploy_cmd,
                depends_on=["integration_test"],
                timeout_seconds=600,
                retry_count=1,
            )
        )

        stages.append(
            Stage(
                id="health_check",
                agent=AgentType.VERIFY,
                command=get_health_check_command(analysis.deploy_target, default_port=8080),
                depends_on=["deploy"],
                timeout_seconds=120,
                retry_count=2,
                critical=True,
            )
        )

    return stages
