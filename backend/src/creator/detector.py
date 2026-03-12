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

# Ordered by priority — check more specific frameworks first
JS_FRAMEWORK_PRIORITY = [
    ("next", "nextjs"),
    ("@nestjs/core", "nestjs"),
    ("@angular/core", "angular"),
    ("svelte", "svelte"),
    ("vue", "vue"),
    ("react", "react"),
    ("express", "express"),
    ("fastify", "fastify"),
    ("koa", "koa"),
    ("@hapi/hapi", "hapi"),
    ("hapi", "hapi"),
]

JS_TEST_RUNNERS = ["jest", "mocha", "vitest", "jasmine", "ava"]

PYTHON_FRAMEWORKS = ["django", "flask", "fastapi", "streamlit", "tornado"]

JAVA_FRAMEWORKS = ["spring-boot", "quarkus", "micronaut"]

RUBY_FRAMEWORKS = {"rails": "rails", "sinatra": "sinatra"}


def _detect_js_details(repo_path: Path) -> tuple[str | None, str | None, list[str]]:
    """Detect JavaScript framework, test runner, and available scripts from package.json."""
    pkg_path = repo_path / "package.json"
    if not pkg_path.exists():
        return None, None, []

    try:
        data = json.loads(pkg_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None, None, []

    framework = None
    all_deps = {}
    all_deps.update(data.get("dependencies", {}))
    all_deps.update(data.get("devDependencies", {}))

    for dep, fw_name in JS_FRAMEWORK_PRIORITY:
        if dep in all_deps:
            framework = fw_name
            break

    test_runner = None
    dev_deps = data.get("devDependencies", {})
    for runner in JS_TEST_RUNNERS:
        if runner in dev_deps:
            test_runner = runner
            break

    # Fallback: check the "test" script for runner names
    if test_runner is None:
        test_script = data.get("scripts", {}).get("test", "")
        for runner in JS_TEST_RUNNERS:
            if runner in test_script:
                test_runner = runner
                break

    available_scripts = list(data.get("scripts", {}).keys())

    return framework, test_runner, available_scripts


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


def _detect_java_framework(repo_path: Path) -> str | None:
    """Detect Java framework from pom.xml or build.gradle."""
    for manifest in ("pom.xml", "build.gradle"):
        mpath = repo_path / manifest
        if mpath.exists():
            try:
                content = mpath.read_text().lower()
                for fw in JAVA_FRAMEWORKS:
                    if fw in content:
                        return fw
            except OSError:
                pass
    return None


def _detect_ruby_framework(repo_path: Path) -> str | None:
    """Detect Ruby framework from Gemfile."""
    gemfile = repo_path / "Gemfile"
    if gemfile.exists():
        try:
            content = gemfile.read_text().lower()
            for gem, fw_name in RUBY_FRAMEWORKS.items():
                if gem in content:
                    return fw_name
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


def _detect_python_test_extras(repo_path: Path) -> bool:
    """Check if the Python project has test/dev extras in pyproject.toml or setup.cfg."""
    for fname in ("pyproject.toml", "setup.cfg", "setup.py"):
        fpath = repo_path / fname
        if fpath.exists():
            try:
                content = fpath.read_text().lower()
                if any(extra in content for extra in ("[dev]", "[test]", "[testing]", "extras_require")):
                    return True
            except OSError:
                pass
    return False


def detect_language(repo_path: str) -> RepoAnalysis:
    """Analyze a repository directory and detect language, framework, etc."""
    path = Path(repo_path)
    if not path.is_dir():
        raise ValueError(f"Repository path does not exist: {repo_path}")

    language = "unknown"
    package_manager = "unknown"
    framework = None
    test_runner = None

    # First check root-level manifests
    for manifest in MANIFEST_PRIORITY:
        if (path / manifest).exists():
            language = LANGUAGE_MAP[manifest]
            package_manager = PACKAGE_MANAGER_MAP[manifest]
            break

    # If unknown, scan immediate subdirectories for manifests (monorepo / nested project)
    if language == "unknown":
        for subdir in sorted(path.iterdir()):
            if not subdir.is_dir() or subdir.name.startswith("."):
                continue
            for manifest in MANIFEST_PRIORITY:
                if (subdir / manifest).exists():
                    language = LANGUAGE_MAP[manifest]
                    package_manager = PACKAGE_MANAGER_MAP[manifest]
                    logger.info("Detected %s in subdirectory %s", language, subdir.name)
                    break
            if language != "unknown":
                break

    available_scripts: list[str] = []
    has_test_extras = False

    if language in ("javascript", "typescript"):
        framework, test_runner, available_scripts = _detect_js_details(path)
        if (path / "tsconfig.json").exists():
            language = "typescript"
        if (path / "yarn.lock").exists():
            package_manager = "yarn"
        elif (path / "pnpm-lock.yaml").exists():
            package_manager = "pnpm"
    elif language == "python":
        framework = _detect_python_framework(path)
        test_runner = _detect_test_runner_python(path)
        has_test_extras = _detect_python_test_extras(path)
    elif language == "java":
        framework = _detect_java_framework(path)
    elif language == "ruby":
        framework = _detect_ruby_framework(path)

    has_dockerfile = (path / "Dockerfile").exists()
    has_requirements_txt = (path / "requirements.txt").exists()
    has_yarn_lock = (path / "yarn.lock").exists()
    has_package_lock = (path / "package-lock.json").exists()
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
        has_requirements_txt=has_requirements_txt,
        has_yarn_lock=has_yarn_lock,
        has_package_lock=has_package_lock,
        has_tests=has_tests,
        test_runner=test_runner,
        is_monorepo=is_monorepo,
        available_scripts=available_scripts,
        has_test_extras=has_test_extras,
    )
