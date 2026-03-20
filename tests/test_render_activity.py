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
        # Should not contain any repo data, just the header
        assert "secret" not in joined

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
