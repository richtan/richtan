"""Shared rendering utilities for visual width calculation and text formatting."""

import html
import re
import unicodedata


def visual_len(text):
    """Return the display width of text, stripping HTML tags and entities."""
    text = re.sub(r'<[^>]+>', '', text)
    text = html.unescape(text)
    text = unicodedata.normalize('NFC', text)
    width = 0
    for c in text:
        cat = unicodedata.category(c)
        if cat in ('Mn', 'Me', 'Cf'):
            continue
        if c in ('\u200b', '\u200c', '\u200d', '\u200e', '\u200f',
                 '\u2060', '\ufeff', '\u00ad'):
            continue
        eaw = unicodedata.east_asian_width(c)
        if eaw in ('W', 'F'):
            width += 2
        else:
            width += 1
    return width


def visual_pad(text, target_width):
    """Pad text with spaces so its visual width equals target_width."""
    spaces_needed = target_width - visual_len(text)
    return text + ' ' * max(0, spaces_needed)


def visual_truncate(text, max_width, suffix='...'):
    """Truncate text to max_width visual chars, appending suffix if truncated."""
    if visual_len(text) <= max_width:
        return text
    suffix_width = visual_len(suffix)
    result = []
    current_width = 0
    for c in text:
        c_width = visual_len(c)
        if current_width + c_width > max_width - suffix_width:
            break
        result.append(c)
        current_width += c_width
    return ''.join(result) + suffix


def word_wrap(text, max_width):
    """Word wrap using visual_len() instead of len(). Returns list of lines."""
    words = text.split(' ')
    lines = []
    current_line = ''
    for word in words:
        if not word:
            continue
        if current_line == '':
            current_line = word
        else:
            test = current_line + ' ' + word
            if visual_len(test) <= max_width:
                current_line = test
            else:
                lines.append(current_line)
                current_line = word
    if current_line:
        lines.append(current_line)
    return lines if lines else ['']


def safe_href(url):
    """Return an HTML-safe href value, or '#' if the URL scheme is invalid."""
    if url and url.startswith(("https://", "http://")):
        return html.escape(url)
    return "#"
