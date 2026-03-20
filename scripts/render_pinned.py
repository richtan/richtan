import html

from utils import safe_href, visual_len, visual_pad, visual_truncate, word_wrap

# Re-export utilities for backwards compatibility with forks
__all__ = ['visual_len', 'visual_pad', 'visual_truncate', 'word_wrap', 'safe_href',
           'render_pinned']


def _render_card_lines(repo, username, inner_width=35):
    """Render a single repo card as a list of strings (each 39 chars wide)."""
    top = '┌' + '─' * (inner_width + 2) + '┐'
    bottom = '└' + '─' * (inner_width + 2) + '┘'

    def content_line(text):
        return '│ ' + visual_pad(text, inner_width) + ' │'

    lines = [top]

    # Repo name line
    name = repo.get('name', '')
    url = repo.get('url', '')
    name_with_owner = repo.get('nameWithOwner', name)
    if not name_with_owner.lower().startswith(f'{username.lower()}/'):
        display_name = name_with_owner
    else:
        display_name = name

    truncated_name = visual_truncate(display_name, 30)
    name_link = f'<a href="{safe_href(url)}"><b>{html.escape(truncated_name)}</b></a>'
    lines.append(content_line(name_link))

    # Fork line (only if fork with known parent)
    if repo.get('isFork') and repo.get('parent'):
        parent_nwo = repo['parent'].get('nameWithOwner', '')
        if parent_nwo:
            fork_text = f'Forked from {parent_nwo}'
            if visual_len(fork_text) > inner_width:
                max_nwo = inner_width - visual_len('Forked from ')
                parent_nwo = visual_truncate(parent_nwo, max_nwo)
            lines.append(content_line(f'Forked from <ins>{html.escape(parent_nwo)}</ins>'))

    # Description lines (2 max)
    description = repo.get('description') or 'No description'
    escaped_desc = html.escape(description)
    desc_lines = word_wrap(escaped_desc, inner_width)
    if len(desc_lines) > 2:
        desc_lines = desc_lines[:2]
        desc_lines[1] = visual_truncate(desc_lines[1], inner_width)
    for dl in desc_lines:
        lines.append(content_line(dl))
    # Pad to exactly 2 description lines
    for _ in range(2 - len(desc_lines)):
        lines.append(content_line(''))

    # Blank line
    lines.append(content_line(''))

    # Stats line
    language = repo.get('primaryLanguage')
    lang_name = language or ''

    stars = repo.get('stargazerCount', 0)
    forks = repo.get('forkCount', 0)

    right_parts = []
    if stars:
        right_parts.append(f'★ {stars}')
    if forks:
        right_parts.append(f'⑂ {forks}')
    right_text = '  '.join(right_parts)

    if lang_name and right_text:
        gap = inner_width - visual_len(lang_name) - visual_len(right_text)
        if gap < 1:
            # Truncate language name to fit
            max_lang = inner_width - visual_len(right_text) - 1
            lang_name = visual_truncate(lang_name, max_lang)
            gap = 1
        stats = lang_name + ' ' * gap + right_text
    elif lang_name:
        stats = lang_name
    elif right_text:
        stats = right_text
    else:
        stats = ''

    lines.append(content_line(stats))
    lines.append(bottom)

    return lines


def render_pinned(pinned_repos, username):
    """Render pinned repos as 2-column box-drawn text art. Returns list of strings."""
    if not pinned_repos:
        return []

    output = []
    pairs = []
    for i in range(0, len(pinned_repos), 2):
        if i + 1 < len(pinned_repos):
            pairs.append((pinned_repos[i], pinned_repos[i + 1]))
        else:
            pairs.append((pinned_repos[i], None))

    blank_line = '│ ' + ' ' * 35 + ' │'

    for left_repo, right_repo in pairs:
        left_lines = _render_card_lines(left_repo, username)
        right_lines = _render_card_lines(right_repo, username) if right_repo else None

        if right_lines:
            max_height = max(len(left_lines), len(right_lines))
            for card_lines in (left_lines, right_lines):
                while len(card_lines) < max_height:
                    card_lines.insert(-1, blank_line)

        for j in range(len(left_lines)):
            if right_lines:
                output.append(left_lines[j] + '  ' + right_lines[j])
            else:
                output.append(left_lines[j])

    return output
