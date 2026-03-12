from typing import Optional


def get_deploy_command(deploy_target: Optional[str], has_dockerfile: bool, fallback_cmd: str = "") -> str:
    """Return a deploy command based on the deploy target."""
    if deploy_target == "docker":
        return "docker build -t app . && docker run -d -p 8080:8080 app"
    elif deploy_target == "aws":
        return "aws ecr get-login-password | docker login --username AWS --password-stdin && docker build -t app . && docker push app"
    elif deploy_target == "heroku":
        return "heroku container:push web && heroku container:release web"
    elif deploy_target in ("kubernetes", "k8s"):
        return "kubectl apply -f k8s/ && kubectl rollout status deployment/app"
    elif deploy_target == "staging":
        if has_dockerfile:
            return "ENV=staging docker build -t app:staging . && docker push app:staging"
        return f"ENV=staging {fallback_cmd}" if fallback_cmd else "ENV=staging echo 'Deploy: configure staging deployment'"
    elif deploy_target == "production":
        if has_dockerfile:
            return "ENV=production docker build -t app:latest . && docker push app:latest"
        return f"ENV=production {fallback_cmd}" if fallback_cmd else "ENV=production echo 'Deploy: configure production deployment'"
    elif has_dockerfile:
        return "docker build -t app . && docker push app"
    elif fallback_cmd:
        return fallback_cmd
    else:
        return "echo 'Deploy: package application for distribution'"


def get_health_check_command(deploy_target: Optional[str], default_port: int = 8080) -> str:
    """Return a health check command based on the deploy target."""
    if deploy_target == "docker":
        return (
            f"sleep 5 && curl -f http://localhost:{default_port}/health "
            f"|| curl -f http://localhost:{default_port}/ "
            "|| echo 'Health check: container may need manual verification'"
        )
    elif deploy_target in ("kubernetes", "k8s"):
        return (
            "kubectl get pods -l app=app --field-selector=status.phase=Running "
            "&& kubectl rollout status deployment/app --timeout=60s"
        )
    elif deploy_target == "heroku":
        return (
            "sleep 10 && curl -f https://$(heroku apps:info -s | grep web_url | cut -d= -f2) "
            "|| echo 'Health check: app may need manual verification'"
        )
    else:
        return (
            f"echo 'Health check: verify deployment is accessible' "
            f"&& curl -f http://localhost:{default_port}/ 2>/dev/null "
            f"|| curl -f http://localhost:5000/ 2>/dev/null "
            "|| echo 'No running service detected - manual verification needed'"
        )
