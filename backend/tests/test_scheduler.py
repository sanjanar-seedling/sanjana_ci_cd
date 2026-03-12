import pytest

from src.executor.scheduler import DAGScheduler
from src.models.messages import StageResult, StageStatus
from src.models.pipeline import AgentType, PipelineSpec, RepoAnalysis, Stage


def _make_spec(stages: list[Stage]) -> PipelineSpec:
    """Create a minimal PipelineSpec for testing."""
    return PipelineSpec(
        repo_url="https://github.com/test/repo",
        goal="test",
        analysis=RepoAnalysis(language="python", package_manager="pip"),
        stages=stages,
    )


def _make_result(stage_id: str, status: StageStatus = StageStatus.SUCCESS) -> StageResult:
    return StageResult(stage_id=stage_id, status=status, exit_code=0)


class TestTopologicalSort:
    def test_linear_chain(self) -> None:
        """A -> B -> C should execute in order."""
        stages = [
            Stage(id="A", agent=AgentType.BUILD, command="echo A"),
            Stage(id="B", agent=AgentType.TEST, command="echo B", depends_on=["A"]),
            Stage(id="C", agent=AgentType.DEPLOY, command="echo C", depends_on=["B"]),
        ]
        scheduler = DAGScheduler(_make_spec(stages))

        # Only A should be ready initially
        ready = scheduler.get_ready_stages()
        assert ready == ["A"]

        # After A completes, B should be ready
        scheduler.mark_complete("A", StageStatus.SUCCESS, _make_result("A"))
        ready = scheduler.get_ready_stages()
        assert ready == ["B"]

        # After B completes, C should be ready
        scheduler.mark_complete("B", StageStatus.SUCCESS, _make_result("B"))
        ready = scheduler.get_ready_stages()
        assert ready == ["C"]

        # After C completes, pipeline is finished
        scheduler.mark_complete("C", StageStatus.SUCCESS, _make_result("C"))
        assert scheduler.is_finished()


class TestParallelDetection:
    def test_diamond_dag(self) -> None:
        """A -> {B, C} -> D: B and C should be parallel after A."""
        stages = [
            Stage(id="A", agent=AgentType.BUILD, command="echo A"),
            Stage(id="B", agent=AgentType.TEST, command="echo B", depends_on=["A"]),
            Stage(id="C", agent=AgentType.SECURITY, command="echo C", depends_on=["A"]),
            Stage(
                id="D",
                agent=AgentType.DEPLOY,
                command="echo D",
                depends_on=["B", "C"],
            ),
        ]
        scheduler = DAGScheduler(_make_spec(stages))

        # A is ready first
        ready = scheduler.get_ready_stages()
        assert ready == ["A"]

        scheduler.mark_complete("A", StageStatus.SUCCESS, _make_result("A"))

        # B and C should both be ready
        ready = scheduler.get_ready_stages()
        assert set(ready) == {"B", "C"}

        # D is not ready until both B and C complete
        scheduler.mark_complete("B", StageStatus.SUCCESS, _make_result("B"))
        ready = scheduler.get_ready_stages()
        assert "D" not in ready

        scheduler.mark_complete("C", StageStatus.SUCCESS, _make_result("C"))
        ready = scheduler.get_ready_stages()
        assert ready == ["D"]


class TestCycleDetection:
    def test_raises_on_cycle(self) -> None:
        """A -> B -> A should raise ValueError."""
        stages = [
            Stage(id="A", agent=AgentType.BUILD, command="echo A", depends_on=["B"]),
            Stage(id="B", agent=AgentType.TEST, command="echo B", depends_on=["A"]),
        ]
        with pytest.raises(ValueError, match="cycle"):
            DAGScheduler(_make_spec(stages))

    def test_raises_on_self_dependency(self) -> None:
        stages = [
            Stage(id="A", agent=AgentType.BUILD, command="echo A", depends_on=["A"]),
        ]
        with pytest.raises(ValueError, match="cycle"):
            DAGScheduler(_make_spec(stages))


class TestNonCriticalSkip:
    def test_skipped_non_critical_does_not_block(self) -> None:
        """If B is non-critical and skipped, C should still run."""
        stages = [
            Stage(id="A", agent=AgentType.BUILD, command="echo A"),
            Stage(
                id="B",
                agent=AgentType.TEST,
                command="echo B",
                depends_on=["A"],
                critical=False,
            ),
            Stage(id="C", agent=AgentType.DEPLOY, command="echo C", depends_on=["B"]),
        ]
        scheduler = DAGScheduler(_make_spec(stages))

        scheduler.mark_complete("A", StageStatus.SUCCESS, _make_result("A"))
        # B fails but is non-critical — mark as SKIPPED
        scheduler.mark_complete(
            "B",
            StageStatus.SKIPPED,
            _make_result("B", StageStatus.SKIPPED),
        )

        # C should be ready because B is SKIPPED (not PENDING/RUNNING)
        ready = scheduler.get_ready_stages()
        assert "C" in ready


class TestSkipDependents:
    def test_skip_dependents_cascades(self) -> None:
        """If A fails, both B and C (descendants) should be skipped."""
        stages = [
            Stage(id="A", agent=AgentType.BUILD, command="echo A"),
            Stage(id="B", agent=AgentType.TEST, command="echo B", depends_on=["A"]),
            Stage(id="C", agent=AgentType.DEPLOY, command="echo C", depends_on=["B"]),
        ]
        scheduler = DAGScheduler(_make_spec(stages))

        scheduler.mark_complete(
            "A", StageStatus.FAILED, _make_result("A", StageStatus.FAILED)
        )
        scheduler.skip_dependents("A")

        assert scheduler.get_status("B") == StageStatus.SKIPPED
        assert scheduler.get_status("C") == StageStatus.SKIPPED
        assert scheduler.is_finished()
