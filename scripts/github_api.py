import sys
from datetime import datetime, timedelta, timezone

import requests

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"

PROFILE_QUERY = """
query($from: DateTime!, $to: DateTime!) {{
  user(login: "{username}") {{
    pinnedItems(first: 6, types: REPOSITORY) {{
      nodes {{
        ... on Repository {{
          name
          nameWithOwner
          url
          description
          isPrivate
          isFork
          primaryLanguage {{ name }}
          stargazerCount
          forkCount
        }}
      }}
    }}
    contributionsCollection(from: $from, to: $to) {{
      totalCommitContributions
      totalPullRequestContributions
      totalPullRequestReviewContributions
      totalIssueContributions
      totalRepositoriesWithContributedCommits
      contributionCalendar {{
        totalContributions
        months {{ name firstDay totalWeeks }}
        weeks {{
          contributionDays {{
            contributionCount
            contributionLevel
            date
            weekday
          }}
        }}
      }}
      commitContributionsByRepository(maxRepositories: 10) {{
        repository {{ name nameWithOwner url isPrivate }}
        contributions(first: 100) {{
          totalCount
          nodes {{ occurredAt commitCount }}
        }}
      }}
      pullRequestContributionsByRepository(maxRepositories: 5) {{
        repository {{ name nameWithOwner url }}
        contributions(first: 100) {{
          totalCount
          nodes {{ occurredAt }}
        }}
      }}
      pullRequestReviewContributionsByRepository(maxRepositories: 5) {{
        repository {{ name nameWithOwner url }}
        contributions(first: 100) {{
          totalCount
          nodes {{ occurredAt }}
        }}
      }}
      repositoryContributions(first: 10) {{
        totalCount
        nodes {{
          occurredAt
          repository {{ name nameWithOwner url }}
        }}
      }}
    }}
  }}
}}
"""


def fetch_profile_data(token, username):
    if not token:
        sys.exit("GITHUB_TOKEN not set")

    print(f"Fetching profile data for {username}...")

    now = datetime.now(timezone.utc)
    from_date = now - timedelta(days=366)

    variables = {
        "from": from_date.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "to": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }

    query = PROFILE_QUERY.format(username=username)

    response = requests.post(
        GITHUB_GRAPHQL_URL,
        json={"query": query, "variables": variables},
        headers={"Authorization": f"bearer {token}"},
        timeout=30,
    )

    if response.status_code != 200:
        sys.exit(f"GitHub API returned HTTP {response.status_code}")

    data = response.json()

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
            repo["description"] = "No description"
        repo["primaryLanguage"] = (
            repo["primaryLanguage"]["name"] if repo.get("primaryLanguage") else None
        )

    return data["data"]
