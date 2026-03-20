import re
import sys
from datetime import datetime, timedelta, timezone

import requests

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

# GitHub username: 1-39 alphanumeric/hyphens, starts and ends with alphanumeric
_USERNAME_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9-]{0,37}[a-zA-Z0-9])?$')


def fetch_username(token):
    """Auto-detect the authenticated user's login via REST API."""
    try:
        resp = requests.get(
            "https://api.github.com/user",
            headers={"Authorization": f"bearer {token}"},
            timeout=10,
        )
    except requests.exceptions.RequestException as e:
        sys.exit(f"Failed to fetch user: {e}")
    if resp.status_code != 200:
        sys.exit(f"Failed to fetch user: HTTP {resp.status_code}")
    try:
        data = resp.json()
    except ValueError:
        sys.exit("Failed to parse user API response")
    if "login" not in data:
        sys.exit("Failed to detect username from token")
    return data["login"]

PROFILE_QUERY = """
query($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    pinnedItems(first: 6, types: REPOSITORY) {
      nodes {
        ... on Repository {
          name
          nameWithOwner
          url
          description
          isPrivate
          isFork
          parent { nameWithOwner }
          primaryLanguage { name }
          stargazerCount
          forkCount
        }
      }
    }
    repositories(first: 6, ownerAffiliations: [OWNER], orderBy: {field: STARGAZERS, direction: DESC}, privacy: PUBLIC) {
      nodes {
        name
        nameWithOwner
        url
        description
        isPrivate
        isFork
        parent { nameWithOwner }
        primaryLanguage { name }
        stargazerCount
        forkCount
      }
    }
    contributionsCollection(from: $from, to: $to) {
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {
        totalContributions
        months { name firstDay totalWeeks }
        weeks {
          contributionDays {
            contributionCount
            contributionLevel
            date
            weekday
          }
        }
      }
      commitContributionsByRepository(maxRepositories: 100) {
        repository { name nameWithOwner url isPrivate }
        contributions(first: 100) {
          totalCount
          nodes { occurredAt commitCount }
        }
      }
      pullRequestContributionsByRepository(maxRepositories: 50) {
        repository { name nameWithOwner url isPrivate }
        contributions(first: 100) {
          totalCount
          nodes { occurredAt }
        }
      }
      pullRequestReviewContributionsByRepository(maxRepositories: 50) {
        repository { name nameWithOwner url isPrivate }
        contributions(first: 100) {
          totalCount
          nodes { occurredAt }
        }
      }
      repositoryContributions(first: 10) {
        totalCount
        nodes {
          occurredAt
          repository { name nameWithOwner url isPrivate }
        }
      }
    }
  }
}
"""


def fetch_profile_data(token, username):
    if not token:
        sys.exit("GITHUB_TOKEN not set")
    if not _USERNAME_RE.match(username):
        sys.exit(f"Invalid GitHub username: {username!r}")

    print(f"Fetching profile data for {username}...")

    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=366)

    variables = {
        "login": username,
        "from": from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    try:
        response = requests.post(
            GITHUB_GRAPHQL_URL,
            json={"query": PROFILE_QUERY, "variables": variables},
            headers={"Authorization": f"bearer {token}"},
            timeout=30,
        )
    except requests.exceptions.RequestException as e:
        sys.exit(f"GitHub API request failed: {e}")

    if response.status_code != 200:
        sys.exit(f"GitHub API returned HTTP {response.status_code}")

    try:
        data = response.json()
    except (ValueError, requests.exceptions.JSONDecodeError):
        sys.exit("Failed to parse GitHub API response")

    if "errors" in data:
        errors = data["errors"]
        for error in errors:
            if error.get("type") == "RATE_LIMITED":
                sys.exit("Rate limited. Try again later.")
        sys.exit(f"GraphQL error: {errors}")

    if data["data"]["user"] is None:
        sys.exit("Could not fetch user. Check token scopes (needs read:user)")

    user = data["data"]["user"]

    # Apply nullable defaults to pinned repos
    for repo in user["pinnedItems"]["nodes"]:
        if not repo.get("description"):
            repo["description"] = ""
        repo["primaryLanguage"] = (
            repo["primaryLanguage"]["name"] if repo.get("primaryLanguage") else None
        )

    # Apply nullable defaults to popular repos (fallback for empty pinned)
    for repo in user.get("repositories", {}).get("nodes", []):
        if not repo.get("description"):
            repo["description"] = ""
        repo["primaryLanguage"] = (
            repo["primaryLanguage"]["name"] if repo.get("primaryLanguage") else None
        )

    return data["data"]
