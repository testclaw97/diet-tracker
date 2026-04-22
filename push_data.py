import subprocess
import logging
from pathlib import Path

REPO_DIR = Path(__file__).parent
log = logging.getLogger(__name__)

def push_to_github():
    try:
        today_files = list((REPO_DIR / "data").glob("*.json"))
        if not today_files:
            log.info("No data files to push")
            return
        subprocess.run(["git", "add", "data/"], cwd=REPO_DIR, check=True)
        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            cwd=REPO_DIR
        )
        if result.returncode == 0:
            log.info("No changes to push")
            return
        subprocess.run(
            ["git", "commit", "-m", "data: nightly update"],
            cwd=REPO_DIR, check=True
        )
        subprocess.run(["git", "push", "origin", "main"], cwd=REPO_DIR, check=True)
        log.info("Data pushed to GitHub")
    except subprocess.CalledProcessError as e:
        log.error(f"Git push failed: {e}")
