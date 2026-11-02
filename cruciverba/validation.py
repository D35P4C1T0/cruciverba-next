"""Pulizia e validazione aggiuntiva dei contributi."""

import re


CONTROL_CHARACTERS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
CSV_FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def sanitize_input(text):
    if not text:
        return text
    return CONTROL_CHARACTERS.sub("", text).strip()


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
