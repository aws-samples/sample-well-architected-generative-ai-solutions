"""GitHub API → mermaid gitgraph conversion."""
import logging
import re
from urllib.request import urlopen, Request
from urllib.error import URLError
import json

logger = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com"
MAX_COMMITS = 20


def _parse_repo(repo_url: str) -> str:
    """Extract 'owner/repo' from a GitHub URL."""
    m = re.search(r"github\.com[/:]([^/]+/[^/.]+)", repo_url)
    if not m:
        raise ValueError(f"Cannot parse GitHub repo from: {repo_url}")
    return m.group(1).rstrip("/")


def _gh_get(path: str) -> list | dict:
    """Simple GitHub API GET (unauthenticated, rate-limited to 60/hr)."""
    req = Request(f"{GITHUB_API}{path}", headers={"Accept": "application/vnd.github+json", "User-Agent": "devtool-agent"})
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read())
    except URLError as e:
        if hasattr(e, "code") and e.code == 409:
            return []  # empty repo
        raise


def get_repo_gitgraph(repo_url: str) -> str:
    """Fetch branches + recent commits from GitHub and return mermaid gitgraph string."""
    owner_repo = _parse_repo(repo_url)

    # Get default branch
    repo_info = _gh_get(f"/repos/{owner_repo}")
    default_branch = repo_info.get("default_branch", "main")

    # Get branches
    branches = _gh_get(f"/repos/{owner_repo}/branches?per_page=30")
    branch_names = [b["name"] for b in branches]

    # Get recent commits on default branch
    commits = _gh_get(f"/repos/{owner_repo}/commits?sha={default_branch}&per_page={MAX_COMMITS}")
    if not commits:
        return f"gitgraph\n  commit id: \"empty repo\""

    # Build mermaid gitgraph
    lines = [f"gitgraph"]
    commit_shas = set()

    # Add main branch commits (newest first from API, reverse for graph)
    for c in reversed(commits):
        sha_short = c["sha"][:7]
        msg = c["commit"]["message"].split("\n")[0][:40].replace('"', "'")
        lines.append(f'  commit id: "{sha_short}: {msg}"')
        commit_shas.add(c["sha"])

    # Add other branches as branch points
    for b in branch_names:
        if b == default_branch:
            continue
        try:
            bc = _gh_get(f"/repos/{owner_repo}/commits?sha={b}&per_page=3")
            if not bc:
                continue
            lines.append(f'  branch {b.replace("/", "-")}')
            lines.append(f'  checkout {b.replace("/", "-")}')
            for c in reversed(bc[:3]):
                if c["sha"] not in commit_shas:
                    sha_short = c["sha"][:7]
                    msg = c["commit"]["message"].split("\n")[0][:40].replace('"', "'")
                    lines.append(f'  commit id: "{sha_short}: {msg}"')
                    commit_shas.add(c["sha"])
            lines.append(f"  checkout {default_branch}")
        except Exception:
            continue

    return "\n".join(lines)
