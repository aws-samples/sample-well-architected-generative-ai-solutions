"""Dev-tool module — enrich tasks with codebase context (origin, branch, commit)."""
import logging
import re
from urllib.request import urlopen, Request
from urllib.error import URLError
import json

logger = logging.getLogger(__name__)


def resolve_repo_context(repo_url: str, branch: str = "") -> dict:
    """Resolve origin, branch, and latest commit SHA from a GitHub repo URL.

    Returns dict with keys: origin, branch, commit.
    """
    ctx = {"origin": repo_url, "branch": "", "commit": ""}
    owner_repo = _parse_repo(repo_url)
    if not owner_repo:
        return ctx

    try:
        if not branch:
            info = _gh_get(f"/repos/{owner_repo}")
            branch = info.get("default_branch", "main") if isinstance(info, dict) else "main"
        ctx["branch"] = branch

        commits = _gh_get(f"/repos/{owner_repo}/commits?sha={branch}&per_page=1")
        if commits and isinstance(commits, list):
            ctx["commit"] = commits[0]["sha"][:7]
    except Exception as e:
        logger.warning(f"Failed to resolve repo context: {e}")

    return ctx


def enrich_task(task: dict, repo_url: str, branch: str = "", commit: str = "") -> dict:
    """Add origin/branch/commit to a task dict.

    If branch/commit not provided, resolves from GitHub API.
    """
    if commit and branch:
        task["origin"] = repo_url
        task["branch"] = branch
        task["commit"] = commit
    else:
        ctx = resolve_repo_context(repo_url, branch)
        task["origin"] = ctx["origin"]
        task["branch"] = ctx["branch"]
        task["commit"] = ctx["commit"]
    return task


def _parse_repo(repo_url: str) -> str:
    m = re.search(r"github\.com[/:]([^/]+/[^/.]+)", repo_url)
    return m.group(1).rstrip("/") if m else ""


def _gh_get(path: str):
    req = Request(f"https://api.github.com{path}", headers={"Accept": "application/vnd.github+json", "User-Agent": "devtool-agent"})
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except URLError as e:
        if hasattr(e, "code") and e.code == 409:
            return []
        raise
