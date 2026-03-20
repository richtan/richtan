from datetime import datetime
from zoneinfo import ZoneInfo

from render_activity import _parse_date, _render_repo_lines, render_activity
from utils import visual_len

_UTC = ZoneInfo("UTC")
_ET = ZoneInfo("America/New_York")


class TestParseDate:
    def test_valid_iso_date(self):
        result = _parse_date("2025-03-15T10:00:00Z", _ET)
        assert result is not None
        assert isinstance(result, datetime)

    def test_empty_string(self):
        assert _parse_date("", _ET) is None

    def test_none(self):
        assert _parse_date(None, _ET) is None

    def test_malformed(self):
        assert _parse_date("not-a-date", _ET) is None

    def test_timezone_conversion(self):
        result = _parse_date("2025-03-15T05:00:00Z", _ET)
        # 5am UTC = 1am ET (during EDT)
        assert result.tzinfo is not None


class TestRenderRepoLines:
    def test_single_repo(self):
        repos = [("user/repo", {"url": "https://github.com/user/repo", "count": 5})]
        lines = _render_repo_lines(repos, show_count=True)
        assert len(lines) == 1
        assert "└─" in lines[0]
        assert "5" in lines[0]

    def test_multiple_repos(self):
        repos = [
            ("user/repo1", {"url": "https://github.com/user/repo1", "count": 10}),
            ("user/repo2", {"url": "https://github.com/user/repo2", "count": 5}),
        ]
        lines = _render_repo_lines(repos, show_count=True)
        assert len(lines) == 2
        assert "├─" in lines[0]
        assert "└─" in lines[1]

    def test_alignment(self):
        repos = [("user/repo", {"url": "https://github.com/user/repo", "count": 42})]
        lines = _render_repo_lines(repos, show_count=True)
        # Should have dot leaders
        assert "·" in lines[0]


class TestRenderActivity:
    def test_empty_data(self):
        lines = render_activity({})
        assert len(lines) >= 1
        assert "<b>Contribution Activity</b>" in lines[0]

    def test_all_private_repos_filtered(self):
        data = {
            "commitContributionsByRepository": [
                {
                    "repository": {"name": "secret", "nameWithOwner": "user/secret",
                                   "url": "https://github.com/user/secret", "isPrivate": True},
                    "contributions": {
                        "totalCount": 5,
                        "nodes": [{"occurredAt": "2025-03-15T10:00:00Z", "commitCount": 5}],
                    },
                }
            ],
        }
        lines = render_activity(data, tz=_ET)
        joined = "\n".join(lines)
        # Repo name should not appear, but private summary should
        assert "secret" not in joined
        assert "contribution" in joined
        assert "private" in joined

    def test_private_summary_date_range(self):
        data = {
            "commitContributionsByRepository": [
                {
                    "repository": {"nameWithOwner": "user/public",
                                   "url": "https://github.com/user/public", "isPrivate": False},
                    "contributions": {
                        "nodes": [{"occurredAt": "2025-03-10T10:00:00Z", "commitCount": 3}],
                    },
                },
                {
                    "repository": {"nameWithOwner": "user/secret",
                                   "url": "https://github.com/user/secret", "isPrivate": True},
                    "contributions": {
                        "nodes": [
                            {"occurredAt": "2025-03-02T10:00:00Z", "commitCount": 4},
                            {"occurredAt": "2025-03-14T10:00:00Z", "commitCount": 7},
                        ],
                    },
                },
            ],
        }
        lines = render_activity(data, tz=_ET)
        joined = "\n".join(lines)
        assert "11 contributions in private repositories" in joined
        assert "Mar 2" in joined
        assert "Mar 14" in joined

    def test_private_single_date(self):
        data = {
            "commitContributionsByRepository": [
                {
                    "repository": {"nameWithOwner": "user/secret",
                                   "url": "https://github.com/user/secret", "isPrivate": True},
                    "contributions": {
                        "nodes": [{"occurredAt": "2025-03-02T10:00:00Z", "commitCount": 3}],
                    },
                },
            ],
        }
        lines = render_activity(data, tz=_ET)
        joined = "\n".join(lines)
        assert "3 contributions in private repositories" in joined
        # Single date, not a range
        assert "–" not in joined
        assert "Mar 2" in joined

    def test_private_only_month(self):
        """Month with only private activity still renders."""
        data = {
            "pullRequestContributionsByRepository": [
                {
                    "repository": {"nameWithOwner": "user/secret",
                                   "url": "https://github.com/user/secret", "isPrivate": True},
                    "contributions": {
                        "nodes": [{"occurredAt": "2025-04-05T10:00:00Z"}],
                    },
                },
            ],
        }
        lines = render_activity(data, tz=_ET)
        joined = "\n".join(lines)
        assert "April" in joined
        assert "1 contribution in private repositories" in joined

    def test_private_line_width(self):
        """Private summary line must not exceed LINE_WIDTH (72)."""
        data = {
            "commitContributionsByRepository": [
                {
                    "repository": {"nameWithOwner": "user/secret",
                                   "url": "https://github.com/user/secret", "isPrivate": True},
                    "contributions": {
                        "nodes": [
                            {"occurredAt": "2025-03-01T10:00:00Z", "commitCount": 999},
                            {"occurredAt": "2025-03-31T10:00:00Z", "commitCount": 1},
                        ],
                    },
                },
            ],
        }
        lines = render_activity(data, tz=_ET)
        for line in lines:
            assert visual_len(line) <= 72, f"Line too wide ({visual_len(line)}): {line!r}"

    def test_with_commit_data(self):
        data = {
            "commitContributionsByRepository": [
                {
                    "repository": {"name": "myrepo", "nameWithOwner": "user/myrepo",
                                   "url": "https://github.com/user/myrepo", "isPrivate": False},
                    "contributions": {
                        "totalCount": 10,
                        "nodes": [{"occurredAt": "2025-03-15T10:00:00Z", "commitCount": 10}],
                    },
                }
            ],
        }
        lines = render_activity(data, tz=_ET)
        joined = "\n".join(lines)
        assert "user/myrepo" in joined
        assert "10" in joined
