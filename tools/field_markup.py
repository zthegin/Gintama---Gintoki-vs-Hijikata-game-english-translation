# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
"""Strict field dialogue markup and non-executing security inspection helpers."""
from __future__ import annotations

import re

RED, BLUE, RESET = 0xFF81, 0xFF82, 0xFF84
PAGE = 0xFF72
ACCENT = 0xFF83  # Exact source color selector; no color name is assumed.
COLOR_CONTROLS = frozenset({RED, BLUE, ACCENT, RESET})
INLINE_CONTROLS = frozenset({0xFFA1, 0xFFA2, 0xFFA3, 0xFFA5, 0xFFB1, 0xFFB2})
TEXT_CONTROLS = COLOR_CONTROLS | INLINE_CONTROLS
COLOR_MARKER = re.compile(r"\[(blue|red|/color)\]", re.IGNORECASE)
CONTROL_MARKER = re.compile(r"\[ctrl:([0-9a-f]{4})\]", re.IGNORECASE)
TEXT_MARKER = re.compile(r"\[(blue|red|/color)\]|\[ctrl:([0-9a-f]{4})\]", re.IGNORECASE)
_MARKER = TEXT_MARKER
_OPEN_CODES = {"blue": BLUE, "red": RED}
_CLOSE_CODE = RESET
_MALFORMED = re.compile(
    r"\[/?(?:blue|red|color|ctrl|FF8[1234])(?=[\]\s/:]|$)", re.IGNORECASE
)


def _parse(text: str) -> tuple[str, tuple[int, ...]]:
    if not isinstance(text, str):
        raise ValueError("Dialogue markup must be text")
    if _MALFORMED.search(_MARKER.sub("", text)):
        raise ValueError("Malformed color marker; use [blue], [red] and [/color]")
    pieces: list[str] = []
    codes: list[int] = []
    cursor = 0
    opened = False
    color_start = 0
    for match in _MARKER.finditer(text):
        pieces.append(text[cursor : match.start()])
        marker = match.group(1).lower() if match.group(1) else None
        if marker is None:
            code = int(match.group(2), 16)
            if code not in TEXT_CONTROLS:
                raise ValueError("Unsupported inline control marker")
            codes.append(code)
            if code == ACCENT:
                if opened:
                    raise ValueError("Color markers cannot be nested")
                opened = True
                color_start = match.end()
            cursor = match.end()
            continue
        if marker == "/color":
            if not opened:
                raise ValueError("Color close marker has no matching open marker")
            if not TEXT_MARKER.sub("", text[color_start : match.start()]).strip():
                raise ValueError("A colored span needs visible text")
            codes.append(_CLOSE_CODE)
            opened = False
        else:
            if opened:
                raise ValueError("Color markers cannot be nested")
            codes.append(_OPEN_CODES[marker])
            opened = True
            color_start = match.end()
        cursor = match.end()
    pieces.append(text[cursor:])
    if opened:
        raise ValueError("Color open marker has no matching close marker")
    return "".join(pieces), tuple(codes)


def strip_colors(text: str) -> str:
    """Remove recognized color markup, rejecting unbalanced or nested spans."""
    return _parse(text)[0]


def strip_color_markers(text: str) -> str:
    """Remove recognized lexemes for security inspection, without parsing notes."""
    if not isinstance(text, str):
        raise ValueError("Dialogue markup must be text")
    return _MARKER.sub("", text)


def color_controls(text: str) -> tuple[int, ...]:
    """Return source control codes in markup order (blue FF82, red FF81, end FF84)."""
    return tuple(code for code in _parse(text)[1] if code in COLOR_CONTROLS)


def color_tokens(text: str) -> list[str | int]:
    """Return plain text and color codes without changing their order."""
    _parse(text)
    result: list[str | int] = []
    cursor = 0
    for match in _MARKER.finditer(text):
        if match.start() > cursor:
            result.append(text[cursor : match.start()])
        marker = match.group(1).lower() if match.group(1) else None
        result.append(int(match.group(2), 16) if marker is None else
                      _CLOSE_CODE if marker == "/color" else _OPEN_CODES[marker])
        cursor = match.end()
    if cursor < len(text):
        result.append(text[cursor:])
    return result


def control_sequence(text: str) -> tuple[int, ...]:
    """Return color and page controls in the order they will enter the game."""
    result = []
    for token in color_tokens(text):
        if isinstance(token, int):
            result.append(token)
        else:
            result.extend(PAGE for char in token if char == "\f")
    return tuple(result)


def check_record_controls(text: str | None, indexed: dict) -> None:
    """Keep source field controls fixed; image labels do not support color markup."""
    if text is None:
        return
    if not isinstance(indexed, dict) or not isinstance(indexed.get("id"), str):
        raise ValueError("Invalid indexed record identity")
    if "raw_color_controls" in indexed and type(indexed["raw_color_controls"]) is not bool:
        raise ValueError("Invalid raw color controls flag")
    actual = control_sequence(text)
    identifier = indexed["id"]
    if not identifier.startswith("msb_"):
        if any(code in TEXT_CONTROLS for code in actual):
            raise ValueError("Color markers are not supported in image labels: " + identifier)
        return
    pages = indexed.get("page_breaks", 0)
    if type(pages) is not int or not 0 <= pages <= 2500:
        raise ValueError("Invalid indexed page count: " + identifier)
    expected = indexed.get("control_sequence", [PAGE] * pages)
    if (not isinstance(expected, (list, tuple))
            or any(type(code) is not int or code not in TEXT_CONTROLS | {PAGE}
                   for code in expected)
            or expected.count(PAGE) != pages):
        raise ValueError("Invalid indexed control sequence: " + identifier)
    if actual != tuple(expected):
        raise ValueError("Preserve source color controls and dialogue page order: " + identifier)
