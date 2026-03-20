import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from generate import sanitize, validate_output


class TestSanitize:
    def test_null_bytes_removed(self):
        assert "\x00" not in sanitize("hello\x00world")

    def test_control_chars_removed(self):
        result = sanitize("hello\x01\x02\x03world")
        assert result == "helloworld"

    def test_tabs_replaced(self):
        assert sanitize("a\tb") == "a    b"

    def test_nfc_normalization(self):
        # Decomposed e + combining acute → precomposed é
        result = sanitize("e\u0301")
        assert result == "\u00e9"

    def test_normal_text_unchanged(self):
        assert sanitize("hello world") == "hello world"


class TestValidateOutput:
    def test_empty_is_false(self):
        assert validate_output([]) is False
        assert validate_output([""]) is False
        assert validate_output(["", "  "]) is False

    def test_non_empty_is_true(self):
        assert validate_output(["hello"]) is True
