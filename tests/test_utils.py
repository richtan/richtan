from utils import safe_href, visual_len, visual_pad, visual_truncate, word_wrap


class TestVisualLen:
    def test_ascii(self):
        assert visual_len("hello") == 5

    def test_empty(self):
        assert visual_len("") == 0

    def test_cjk_wide_chars(self):
        # CJK characters are 2 visual units wide
        assert visual_len("漢字") == 4

    def test_html_tags_stripped(self):
        assert visual_len('<a href="url">text</a>') == 4

    def test_html_entities_unescaped(self):
        assert visual_len("&amp;") == 1

    def test_zero_width_chars(self):
        assert visual_len("a\u200bb") == 2

    def test_combining_marks(self):
        # e + combining acute accent = 1 visual char
        assert visual_len("e\u0301") == 1

    def test_mixed_content(self):
        assert visual_len('<b>hello</b>') == 5


class TestVisualPad:
    def test_basic(self):
        result = visual_pad("hi", 5)
        assert result == "hi   "
        assert visual_len(result) == 5

    def test_already_at_width(self):
        result = visual_pad("hello", 5)
        assert result == "hello"

    def test_over_width_no_negative(self):
        result = visual_pad("toolong", 3)
        assert result == "toolong"  # no truncation, just no padding


class TestVisualTruncate:
    def test_no_truncation_needed(self):
        assert visual_truncate("hi", 10) == "hi"

    def test_truncation(self):
        result = visual_truncate("hello world", 8)
        assert visual_len(result) <= 8
        assert result.endswith("...")

    def test_custom_suffix(self):
        result = visual_truncate("hello world", 8, suffix="..")
        assert result.endswith("..")


class TestWordWrap:
    def test_empty_string(self):
        assert word_wrap("", 10) == [""]

    def test_fits_on_one_line(self):
        assert word_wrap("hello world", 20) == ["hello world"]

    def test_wraps_correctly(self):
        result = word_wrap("hello world foo bar", 10)
        for line in result:
            assert visual_len(line) <= 10

    def test_long_word_truncated(self):
        result = word_wrap("abcdefghijklmnopqrstuvwxyz", 10)
        assert len(result) == 1
        assert visual_len(result[0]) <= 10
        assert result[0].endswith("...")

    def test_exact_fit(self):
        assert word_wrap("12345", 5) == ["12345"]


class TestSafeHref:
    def test_https_valid(self):
        url = "https://github.com/user/repo"
        assert safe_href(url) == url

    def test_http_valid(self):
        url = "http://example.com"
        assert safe_href(url) == url

    def test_javascript_rejected(self):
        assert safe_href("javascript:alert(1)") == "#"

    def test_empty_rejected(self):
        assert safe_href("") == "#"

    def test_none_rejected(self):
        assert safe_href(None) == "#"

    def test_html_escaping(self):
        url = 'https://example.com/a&b"c'
        result = safe_href(url)
        assert "&amp;" in result
        assert "&quot;" in result
