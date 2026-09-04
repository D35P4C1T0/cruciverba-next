"""Pulizia e validazione aggiuntiva dei contributi."""

import re
from html.parser import HTMLParser


CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


class _TextExtractor(HTMLParser):
    """Keep text, discard HTML elements and comments."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.blocked_depth = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "template"}:
            self.blocked_depth += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "template"} and self.blocked_depth:
            self.blocked_depth -= 1

    def handle_data(self, data):
        if not self.blocked_depth:
            self.parts.append(data)


def sanitize_input(text):
    if not text:
        return text
    parser = _TextExtractor()
    parser.feed(CONTROL_CHARACTERS.sub("", text.strip()))
    parser.close()
    return "".join(parser.parts).strip()


def is_valid_word(word):
    return bool(word and word.strip())


def is_valid_clue(clue):
    return bool(clue and clue.strip())


def sanitize_csv_cell(value):
    """Prevent spreadsheet software from evaluating exported user input."""
    text = "" if value is None else str(value)
    if text.lstrip().startswith(CSV_FORMULA_PREFIXES):
        return f"'{text}"
    return text
