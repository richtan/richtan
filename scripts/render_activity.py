import html
import re
import unicodedata
from collections import defaultdict
from datetime import datetime

from render_pinned import visual_len, visual_pad


def render_activity(contributions_collection):
    """Render the contribution activity timeline. Returns list of text lines."""
    # --- Gather per-month data ---
    # commits_by_month: {(year, month): {nameWithOwner: {"url":..., "count":...}}}
    commits_by_month = defaultdict(lambda: defaultdict(lambda: {"url": "", "count": 0}))
    for entry in contributions_collection.get("commitContributionsByRepository", []):
        if entry is None:
            continue
        repo = entry.get("repository") or {}
        if repo.get("isPrivate", False):
            continue
        name = repo.get("nameWithOwner", "")
        url = repo.get("url", "")
        for node in entry.get("contributions", {}).get("nodes", []):
            if node is None:
                continue
            dt = _parse_date(node.get("occurredAt", ""))
            if dt is None:
                continue
            key = (dt.year, dt.month)
            commits_by_month[key][name]["url"] = url
            commits_by_month[key][name]["count"] += node.get("commitCount", 0)

    # prs_by_month: {(year, month): {nameWithOwner: {"url":..., "count":...}}}
    prs_by_month = defaultdict(lambda: defaultdict(lambda: {"url": "", "count": 0}))
    for entry in contributions_collection.get("pullRequestContributionsByRepository", []):
        if entry is None:
            continue
        repo = entry.get("repository") or {}
        name = repo.get("nameWithOwner", "")
        url = repo.get("url", "")
        for node in entry.get("contributions", {}).get("nodes", []):
            if node is None:
                continue
            dt = _parse_date(node.get("occurredAt", ""))
            if dt is None:
                continue
            key = (dt.year, dt.month)
            prs_by_month[key][name]["url"] = url
            prs_by_month[key][name]["count"] += 1

    # reviews_by_month: {(year, month): {nameWithOwner: {"url":..., "count":...}}}
    reviews_by_month = defaultdict(lambda: defaultdict(lambda: {"url": "", "count": 0}))
    for entry in contributions_collection.get("pullRequestReviewContributionsByRepository", []):
        if entry is None:
            continue
        repo = entry.get("repository") or {}
        name = repo.get("nameWithOwner", "")
        url = repo.get("url", "")
        for node in entry.get("contributions", {}).get("nodes", []):
            if node is None:
                continue
            dt = _parse_date(node.get("occurredAt", ""))
            if dt is None:
                continue
            key = (dt.year, dt.month)
            reviews_by_month[key][name]["url"] = url
            reviews_by_month[key][name]["count"] += 1

    # repos_by_month: {(year, month): [{"name":..., "nameWithOwner":..., "url":...}]}
    repos_by_month = defaultdict(list)
    for node in contributions_collection.get("repositoryContributions", {}).get("nodes", []):
        if node is None:
            continue
        repo = node.get("repository") or {}
        if repo.get("isPrivate", False):
            continue
        dt = _parse_date(node.get("occurredAt", ""))
        if dt is None:
            continue
        key = (dt.year, dt.month)
        repos_by_month[key].append({
            "name": repo.get("name", ""),
            "nameWithOwner": repo.get("nameWithOwner", ""),
            "url": repo.get("url", ""),
        })

    # --- Collect all months and sort descending ---
    all_months = set()
    all_months.update(commits_by_month.keys())
    all_months.update(prs_by_month.keys())
    all_months.update(reviews_by_month.keys())
    all_months.update(repos_by_month.keys())
    sorted_months = sorted(all_months, reverse=True)

    # --- Render ---
    lines = []
    lines.append("  Contribution Activity")
    lines.append("")

    for year, month in sorted_months:
        month_name = datetime(year, month, 1).strftime("%B")
        lines.append(f"  {month_name} {year}")
        lines.append("")

        # Commits
        month_commits = commits_by_month.get((year, month), {})
        if month_commits:
            sorted_repos = sorted(month_commits.items(), key=lambda x: x[1]["count"], reverse=True)
            total_commits = sum(r["count"] for _, r in sorted_repos)
            repo_word = "repository" if len(sorted_repos) == 1 else "repositories"
            commit_word = "commit" if total_commits == 1 else "commits"
            lines.append(f"    Created {total_commits} {commit_word} in {len(sorted_repos)} {repo_word}")
            lines.extend(_render_repo_lines(sorted_repos, show_count=True))
            lines.append("")

        # PRs
        month_prs = prs_by_month.get((year, month), {})
        if month_prs:
            sorted_repos = sorted(month_prs.items(), key=lambda x: x[1]["count"], reverse=True)
            total_prs = sum(r["count"] for _, r in sorted_repos)
            repo_word = "repository" if len(sorted_repos) == 1 else "repositories"
            pr_word = "pull request" if total_prs == 1 else "pull requests"
            lines.append(f"    Opened {total_prs} {pr_word} in {len(sorted_repos)} {repo_word}")
            lines.extend(_render_repo_lines(sorted_repos, show_count=True))
            lines.append("")

        # Reviews
        month_reviews = reviews_by_month.get((year, month), {})
        if month_reviews:
            sorted_repos = sorted(month_reviews.items(), key=lambda x: x[1]["count"], reverse=True)
            total_reviews = sum(r["count"] for _, r in sorted_repos)
            repo_word = "repository" if len(sorted_repos) == 1 else "repositories"
            pr_word = "pull request" if total_reviews == 1 else "pull requests"
            lines.append(f"    Reviewed {total_reviews} {pr_word} in {len(sorted_repos)} {repo_word}")
            lines.extend(_render_repo_lines(sorted_repos, show_count=True))
            lines.append("")

        # Repos created
        month_repos = repos_by_month.get((year, month), [])
        if month_repos:
            repo_word = "repository" if len(month_repos) == 1 else "repositories"
            lines.append(f"    Created {len(month_repos)} {repo_word}")
            for i, repo in enumerate(month_repos):
                is_last = (i == len(month_repos) - 1)
                branch = "└─ " if is_last else "├─ "
                escaped_name = html.escape(repo["nameWithOwner"])
                link = f'<a href="{repo["url"]}">{escaped_name}</a>'
                lines.append(f"    {branch}{link}")
            lines.append("")

    return lines


def _parse_date(date_str):
    """Parse an ISO 8601 date string into a datetime, or None."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def _render_repo_lines(sorted_repos, show_count=True):
    """Render tree-style repo lines with dot-leader alignment.

    sorted_repos: list of (nameWithOwner, {"url": ..., "count": ...})
    Returns list of strings.
    """
    LINE_WIDTH = 72
    lines = []
    for i, (name, info) in enumerate(sorted_repos):
        is_last = (i == len(sorted_repos) - 1)
        branch = "└─ " if is_last else "├─ "
        escaped_name = html.escape(name)
        link = f'<a href="{info["url"]}">{escaped_name}</a>'

        if show_count:
            count_str = f" {info['count']}"
            prefix = f"    {branch}{link} "
            # Visual width of the prefix (indent + branch + link text + space)
            prefix_visual = visual_len(prefix)
            count_visual = len(count_str)
            dots_needed = LINE_WIDTH - prefix_visual - count_visual
            if dots_needed < 2:
                dots_needed = 2
            dots = "·" * dots_needed
            lines.append(f"    {branch}{link} {dots}{count_str}")
        else:
            lines.append(f"    {branch}{link}")

    return lines
