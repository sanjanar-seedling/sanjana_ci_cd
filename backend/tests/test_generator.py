import pytest

from src.creator.generator import generate_pipeline
from src.creator.templates.nodejs import generate_nodejs_pipeline
from src.creator.templates.python_tmpl import generate_python_pipeline
from src.models.pipeline import AgentType, RepoAnalysis


class TestNodejsTemplate:
    def test_produces_correct_stages(self) -> None:
        analysis = RepoAnalysis(
            language="javascript",
            framework="react",
            package_manager="npm",
            has_dockerfile=False,
            has_tests=True,
            test_runner="jest",
        )
        stages = generate_nodejs_pipeline(analysis, "build and test")

        stage_ids = [s.id for s in stages]
        assert "install" in stage_ids
        assert "lint" in stage_ids
        assert "unit_test" in stage_ids
        assert "security_scan" in stage_ids
        assert "build" in stage_ids
        # No deploy since goal doesn't mention it
        assert "deploy" not in stage_ids

    def test_parallel_stages_have_correct_deps(self) -> None:
        analysis = RepoAnalysis(
            language="javascript",
            framework="react",
            package_manager="npm",
            has_tests=True,
            test_runner="jest",
        )
        stages = generate_nodejs_pipeline(analysis, "build")
        stage_map = {s.id: s for s in stages}

        # lint, unit_test, security_scan all depend on install
        assert stage_map["lint"].depends_on == ["install"]
        assert stage_map["unit_test"].depends_on == ["install"]
        assert stage_map["security_scan"].depends_on == ["install"]

        # build depends on all three parallel stages
        assert set(stage_map["build"].depends_on) == {
            "lint",
            "unit_test",
            "security_scan",
        }

    def test_deploy_stages_when_goal_mentions_deploy(self) -> None:
        analysis = RepoAnalysis(
            language="javascript",
            package_manager="npm",
            has_dockerfile=True,
        )
        stages = generate_nodejs_pipeline(analysis, "deploy to production")

        stage_ids = [s.id for s in stages]
        assert "deploy" in stage_ids
        assert "health_check" in stage_ids

    def test_lint_is_not_critical(self) -> None:
        analysis = RepoAnalysis(
            language="javascript",
            package_manager="npm",
        )
        stages = generate_nodejs_pipeline(analysis, "build")
        lint = next(s for s in stages if s.id == "lint")
        assert lint.critical is False


class TestPythonTemplate:
    def test_produces_correct_stages(self) -> None:
        analysis = RepoAnalysis(
            language="python",
            framework="flask",
            package_manager="pip",
            has_tests=True,
            test_runner="pytest",
        )
        stages = generate_python_pipeline(analysis, "build and test")

        stage_ids = [s.id for s in stages]
        assert "install" in stage_ids
        assert "lint" in stage_ids
        assert "unit_test" in stage_ids
        assert "security_scan" in stage_ids

    def test_build_stage_with_dockerfile(self) -> None:
        analysis = RepoAnalysis(
            language="python",
            package_manager="pip",
            has_dockerfile=True,
        )
        stages = generate_python_pipeline(analysis, "build")
        stage_ids = [s.id for s in stages]
        assert "build" in stage_ids

    def test_no_build_stage_without_dockerfile(self) -> None:
        analysis = RepoAnalysis(
            language="python",
            package_manager="pip",
            has_dockerfile=False,
        )
        stages = generate_python_pipeline(analysis, "build and test")
        stage_ids = [s.id for s in stages]
        assert "build" not in stage_ids


class TestDAGValidation:
    @pytest.mark.asyncio
    async def test_generated_pipeline_has_valid_dag(self) -> None:
        analysis = RepoAnalysis(
            language="python",
            framework="fastapi",
            package_manager="pip",
            has_tests=True,
        )
        spec = await generate_pipeline(analysis, "build and deploy to staging")
        # If we get here without ValueError, the DAG is valid
        assert len(spec.stages) > 0

    @pytest.mark.asyncio
    async def test_nodejs_pipeline_has_valid_dag(self) -> None:
        analysis = RepoAnalysis(
            language="javascript",
            framework="react",
            package_manager="npm",
            has_tests=True,
            has_dockerfile=True,
        )
        spec = await generate_pipeline(analysis, "deploy to production")
        assert len(spec.stages) > 0
