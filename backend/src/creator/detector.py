import json
import logging
from pathlib import Path

from src.models.pipeline import RepoAnalysis

logger = logging.getLogger(__name__)

MANIFEST_PRIORITY = [
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Cargo.toml",
    "Gemfile",
]

LANGUAGE_MAP = {
    "package.json": "javascript",
    "requirements.txt": "python",
    "pyproject.toml": "python",
    "go.mod": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "Cargo.toml": "rust",
    "Gemfile": "ruby",
}

PACKAGE_MANAGER_MAP = {
    "package.json": "npm",
    "requirements.txt": "pip",
    "pyproject.toml": "pip",
    "go.mod": "go",
    "pom.xml": "maven",
    "build.gradle": "gradle",
    "Cargo.toml": "cargo",
    "Gemfile": "bundler",
}

JS_FRAMEWORKS = {
    "react": "react",
    "react-dom": "react",
    "next": "next",
    "express": "express",
    "vue": "vue",
    "@angular/core": "angular",
}

JS_TEST_RUNNERS = ["jest", "mocha", "vitest", "ava", "jasmine"]

PYTHON_FRAMEWORKS = ["django", "flask", "fastapi"]


def _detect_js_details(repo_path: Path) -> tuple[str | None, str | None]:
    """Detect JavaScript framework and test runner from package.json."""
    pkg_path = repo_path / "package.json"
    if not pkg_path.exists():
        return None, None

    try:
        data = json.loads(pkg_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None, None

    framework = None
    all_deps = {}
    all_deps.update(data.get("dependencies", {}))
    all_deps.update(data.get("devDependencies", {}))

    for dep, fw_name in JS_FRAMEWORKS.items():
        if dep in all_deps:
            framework = fw_name
            break

    test_runner = None
    dev_deps = data.get("devDependencies", {})
    for runner in JS_TEST_RUNNERS:
        if runner in dev_deps or runner in data.get("dependencies", {}):
            test_runner = runner
            break

    return framework, test_runner


def _detect_python_framework(repo_path: Path) -> str | None:
    """Detect Python framework from requirements.txt or pyproject.toml."""
    req_path = repo_path / "requirements.txt"
    if req_path.exists():
        try:
            content = req_path.read_text().lower()
            for fw in PYTHON_FRAMEWORKS:
                if fw in content:
                    return fw
        except OSError:
            pass

    pyproject_path = repo_path / "pyproject.toml"
    if pyproject_path.exists():
        try:
            content = pyproject_path.read_text().lower()
            for fw in PYTHON_FRAMEWORKS:
                if fw in content:
                    return fw
        except OSError:
            pass

    return None


def _detect_tests(repo_path: Path) -> bool:
    """Check if test directories exist."""
    test_dirs = ["test", "tests", "__tests__", "spec"]
    for d in test_dirs:
        if (repo_path / d).is_dir():
            return True
    return False


def _detect_test_runner_python(repo_path: Path) -> str | None:
    """Detect Python test runner."""
    if (repo_path / "pytest.ini").exists() or (repo_path / "conftest.py").exists():
        return "pytest"
    req_path = repo_path / "requirements.txt"
    if req_path.exists():
        try:
            content = req_path.read_text().lower()
            if "pytest" in content:
                return "pytest"
            if "unittest" in content:
                return "unittest"
        except OSError:
            pass
    return "pytest" if _detect_tests(repo_path) else None


def detect_language(repo_path: str) -> RepoAnalysis:
    """Analyze a repository directory and detect language, framework, etc."""
    path = Path(repo_path)
    if not path.is_dir():
        raise ValueError(f"Repository path does not exist: {repo_path}")

    language = "unknown"
    package_manager = "unknown"
    framework = None
    test_runner = None

    for manifest in MANIFEST_PRIORITY:
        if (path / manifest).exists():
            language = LANGUAGE_MAP[manifest]
            package_manager = PACKAGE_MANAGER_MAP[manifest]
            break

    if language in ("javascript", "typescript"):
        framework, test_runner = _detect_js_details(path)
        if (path / "tsconfig.json").exists():
            language = "typescript"
        if (path / "yarn.lock").exists():
            package_manager = "yarn"
        elif (path / "pnpm-lock.yaml").exists():
            package_manager = "pnpm"
    elif language == "python":
        framework = _detect_python_framework(path)
        test_runner = _detect_test_runner_python(path)

    has_dockerfile = (path / "Dockerfile").exists()
    has_tests = _detect_tests(path)
    is_monorepo = (path / "lerna.json").exists() or (path / "pnpm-workspace.yaml").exists()

    # Check for existing CI config
    ci_files = [".github/workflows", "Jenkinsfile", ".gitlab-ci.yml"]
    for ci in ci_files:
        if (path / ci).exists():
            logger.info("Existing CI config found: %s", ci)

    return RepoAnalysis(
        language=language,
        framework=framework,
        package_manager=package_manager,
        has_dockerfile=has_dockerfile,
        has_tests=has_tests,
        test_runner=test_runner,
        is_monorepo=is_monorepo,
    )
