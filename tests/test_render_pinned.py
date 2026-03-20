from render_pinned import _render_card_lines, render_pinned
from utils import visual_len


def _make_repo(**overrides):
    """Create a minimal repo dict for testing."""
    defaults = {
        "name": "test-repo",
        "nameWithOwner": "user/test-repo",
        "url": "https://github.com/user/test-repo",
        "description": "A test repository",
        "isPrivate": False,
        "isFork": False,
        "parent": None,
        "primaryLanguage": "Python",
        "stargazerCount": 0,
        "forkCount": 0,
    }
    defaults.update(overrides)
    return defaults


class TestCardDimensions:
    def test_card_is_39_wide(self):
        repo = _make_repo()
        lines = _render_card_lines(repo, "user")
        for line in lines:
            assert visual_len(line) == 39, f"Line width {visual_len(line)}: {line}"

    def test_two_column_is_80_wide(self):
        repos = [_make_repo(name="repo1"), _make_repo(name="repo2")]
        output = render_pinned(repos, "user")
        for line in output:
            assert visual_len(line) == 80, f"Line width {visual_len(line)}: {line}"


class TestNameTruncation:
    def test_long_name_truncated(self):
        repo = _make_repo(name="a" * 40)
        lines = _render_card_lines(repo, "user")
        # All lines should still be 39 wide
        for line in lines:
            assert visual_len(line) == 39


class TestDescriptionWrapping:
    def test_long_description_wraps(self):
        repo = _make_repo(description="word " * 20)
        lines = _render_card_lines(repo, "user")
        for line in lines:
            assert visual_len(line) == 39

    def test_no_description(self):
        repo = _make_repo(description=None)
        lines = _render_card_lines(repo, "user")
        # Should show "No description"
        joined = "\n".join(lines)
        assert "No description" in joined


class TestForkDisplay:
    def test_fork_shows_parent(self):
        repo = _make_repo(
            isFork=True,
            parent={"nameWithOwner": "upstream/repo"},
        )
        lines = _render_card_lines(repo, "user")
        joined = "\n".join(lines)
        assert "Forked from" in joined
        assert "upstream/repo" in joined

    def test_fork_parent_html_escaped(self):
        repo = _make_repo(
            isFork=True,
            parent={"nameWithOwner": "up<stream>/repo"},
        )
        lines = _render_card_lines(repo, "user")
        joined = "\n".join(lines)
        assert "&lt;" in joined


class TestStatsLine:
    def test_stats_with_language_and_stars(self):
        repo = _make_repo(primaryLanguage="Python", stargazerCount=42)
        lines = _render_card_lines(repo, "user")
        joined = "\n".join(lines)
        assert "Python" in joined
        assert "★ 42" in joined

    def test_stats_overflow_truncates_language(self):
        # Very long language name + high stars should still fit in card
        repo = _make_repo(
            primaryLanguage="A" * 30,
            stargazerCount=99999,
            forkCount=9999,
        )
        lines = _render_card_lines(repo, "user")
        for line in lines:
            assert visual_len(line) == 39, f"Overflow: {line}"


class TestRenderPinned:
    def test_empty_repos(self):
        assert render_pinned([], "user") == []

    def test_single_repo(self):
        output = render_pinned([_make_repo()], "user")
        assert len(output) > 0
        # Single repo: 39 wide
        for line in output:
            assert visual_len(line) == 39

    def test_odd_number_of_repos(self):
        repos = [_make_repo(name=f"repo{i}") for i in range(3)]
        output = render_pinned(repos, "user")
        assert len(output) > 0
