import json
import tempfile
from pathlib import Path

import pytest

from src.creator.detector import detect_language


def _make_repo(tmp_path: Path, files: dict[str, str]) -> str:
    """Create a fake repo directory with the given files."""
    for name, content in files.items():
        p = tmp_path / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
    return str(tmp_path)


class TestNodejsDetection:
    def test_detects_javascript_with_react(self, tmp_path: Path) -> None:
        pkg = {
            "dependencies": {"react": "^18.0.0", "react-dom": "^18.0.0"},
            "devDependencies": {"jest": "^29.0.0"},
        }
        repo = _make_repo(tmp_path, {"package.json": json.dumps(pkg)})
        result = detect_language(repo)

        assert result.language == "javascript"
        assert result.framework == "react"
        assert result.package_manager == "npm"
        assert result.test_runner == "jest"

    def test_detects_typescript(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {"express": "^4.18.0"}, "devDependencies": {}}
        repo = _make_repo(
            tmp_path,
            {"package.json": json.dumps(pkg), "tsconfig.json": "{}"},
        )
        result = detect_language(repo)

        assert result.language == "typescript"
        assert result.framework == "express"

    def test_detects_yarn(self, tmp_path: Path) -> None:
        pkg = {"dependencies": {}, "devDependencies": {}}
        repo = _make_repo(
            tmp_path,
            {"package.json": json.dumps(pkg), "yarn.lock": ""},
        )
        result = detect_language(repo)
        assert result.package_manager == "yarn"


class TestPythonDetection:
    def test_detects_python_with_flask(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, {"requirements.txt": "flask==3.0.0\nrequests\n"})
        result = detect_language(repo)

        assert result.language == "python"
        assert result.framework == "flask"
        assert result.package_manager == "pip"

    def test_detects_python_with_fastapi(self, tmp_path: Path) -> None:
        repo = _make_repo(
            tmp_path, {"requirements.txt": "fastapi\nuvicorn\npydantic\n"}
        )
        result = detect_language(repo)

        assert result.language == "python"
        assert result.framework == "fastapi"

    def test_detects_django_from_pyproject(self, tmp_path: Path) -> None:
        toml_content = '[project]\ndependencies = ["django>=4.2"]\n'
        repo = _make_repo(tmp_path, {"pyproject.toml": toml_content})
        result = detect_language(repo)

        assert result.language == "python"
        assert result.framework == "django"


class TestDockerfileDetection:
    def test_detects_dockerfile(self, tmp_path: Path) -> None:
        repo = _make_repo(
            tmp_path,
            {
                "requirements.txt": "flask\n",
                "Dockerfile": "FROM python:3.11\n",
            },
        )
        result = detect_language(repo)
        assert result.has_dockerfile is True

    def test_no_dockerfile(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, {"requirements.txt": "flask\n"})
        result = detect_language(repo)
        assert result.has_dockerfile is False


class TestTestDetection:
    def test_detects_tests_directory(self, tmp_path: Path) -> None:
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_app.py").write_text("def test_x(): pass")
        repo = _make_repo(tmp_path, {"requirements.txt": "pytest\n"})
        result = detect_language(repo)

        assert result.has_tests is True
        assert result.test_runner == "pytest"

    def test_detects_jest_tests(self, tmp_path: Path) -> None:
        (tmp_path / "__tests__").mkdir()
        repo = _make_repo(tmp_path, {"requirements.txt": ""})
        # __tests__ exists but it's a python project — still detects has_tests
        result = detect_language(repo)
        assert result.has_tests is True

    def test_no_tests(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, {"requirements.txt": ""})
        result = detect_language(repo)
        assert result.has_tests is False


class TestUnknownLanguage:
    def test_unknown_when_no_manifest(self, tmp_path: Path) -> None:
        repo = _make_repo(tmp_path, {"README.md": "# Hello"})
        result = detect_language(repo)

        assert result.language == "unknown"
        assert result.package_manager == "unknown"
