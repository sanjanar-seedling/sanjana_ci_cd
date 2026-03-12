from src.creator.templates.deploy_commands import get_deploy_command, get_health_check_command
from src.models.pipeline import AgentType, RepoAnalysis, Stage


def generate_java_pipeline(analysis: RepoAnalysis, goal: str) -> list[Stage]:
    """Generate a Java CI/CD pipeline with proper DAG parallelism."""
    use_gradle = analysis.package_manager == "gradle"

    if use_gradle:
        build_tool = "./gradlew"
        install_cmd = f"{build_tool} dependencies"
        test_cmd = f"{build_tool} test"
        build_cmd = f"{build_tool} build -x test"
        audit_cmd = f"{build_tool} dependencyCheckAnalyze 2>/dev/null || echo 'OWASP plugin not configured, skipping'"
    else:
        build_tool = "mvn"
        install_cmd = f"{build_tool} dependency:resolve"
        test_cmd = f"{build_tool} test"
        build_cmd = f"{build_tool} package -DskipTests"
        audit_cmd = f"{build_tool} org.owasp:dependency-check-maven:check 2>/dev/null || echo 'OWASP plugin not configured, skipping'"

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

    # Stage 2 (parallel): test, security_scan
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
            command=audit_cmd,
            depends_on=["install"],
            timeout_seconds=180,
            critical=False,
        )
    )

    # Stage 3: Build
    stages.append(
        Stage(
            id="build",
            agent=AgentType.BUILD,
            command=build_cmd,
            depends_on=["unit_test", "security_scan"],
            timeout_seconds=300,
        )
    )

    # Stage 4: Deploy
    deploy_keywords = ["deploy", "release", "publish", "production", "staging"]
    should_deploy = any(kw in goal.lower() for kw in deploy_keywords)

    if should_deploy:
        java_fallback = f"{build_tool} {'bootRun' if analysis.framework == 'spring-boot' else 'exec:java'}"
        deploy_cmd = get_deploy_command(analysis.deploy_target, analysis.has_dockerfile, java_fallback)

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
