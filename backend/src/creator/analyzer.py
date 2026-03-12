import logging
import shutil
import tempfile

import git

from src.creator.detector import detect_language
from src.models.pipeline import RepoAnalysis

logger = logging.getLogger(__name__)


async def analyze_repo(repo_url: str) -> RepoAnalysis:
    """Clone a repository and analyze its structure.

    Clones the repo into a temporary directory, runs detection,
    then cleans up the clone.
    """
    tmp_dir = tempfile.mkdtemp(prefix="cicd-analyzer-")
    try:
        logger.info("Cloning %s into %s", repo_url, tmp_dir)
        git.Repo.clone_from(repo_url, tmp_dir, depth=1)
        logger.info("Clone complete, running analysis")
        analysis = detect_language(tmp_dir)
        logger.info(
            "Analysis complete: language=%s framework=%s",
            analysis.language,
            analysis.framework,
        )
        return analysis
    except git.GitCommandError as e:
        logger.error("Failed to clone repository: %s", e)
        raise ValueError(f"Failed to clone repository: {e}") from e
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
