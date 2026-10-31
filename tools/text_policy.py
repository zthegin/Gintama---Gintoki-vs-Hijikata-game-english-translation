# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import base64
import html
import json
import math
import re
import unicodedata
from urllib.parse import unquote

from field_markup import strip_color_markers

SCHEMES = "http https hxxp hxxps ftp ftps sftp ssh smb javascript vbscript mailto telnet magnet ws wss ipfs intent ms-msdt".split()
SCHEME = re.compile(
    r"(?<![a-z0-9_])(?:" + "|".join(r"\s*".join(word) for word in SCHEMES) + r")\s*:",
    re.I | re.ASCII,
)
DOMAIN = re.compile(
    r"(?<![\w-])[\w-]+(?:[ \t]*\.[ \t]*[\w-]+)+", re.I
)
SUFFIXES = set(
    "com net org io gg ru xyz dev app info biz co uk me ly link site online top zip mov onion click news shop pro club live mobi world".split()
)
SHORTENERS = {
    "tiny.one",
    "short.io",
    "rebrand.ly",
    "rb.gy",
    "is.gd",
    "v.gd",
    "tiny.cc",
    "t.co",
    "t.ly",
    "bit.ly",
    "cutt.ly",
    "shorturl.at",
    "lnkd.in",
    "goo.gl",
    "youtu.be",
}
LINK_SYNTAX = re.compile(
    r"(?:^|[\s(\[<])//[a-z0-9\[]|!?\[[^\]\n]*\]\(\s*\S|\[(?=[a-f0-9:]*:[a-f0-9:]*:)[a-f0-9:]+\]",
    re.I | re.ASCII,
)
ROLE_MARKER = re.compile(
    r"<\|(?:im_start|im_end|system|assistant|user|developer|eot_id|start_header_id|end_header_id|endoftext)\|>"
    r"|\[/?(?:INST|SYS|SYSTEM|DEVELOPER|ASSISTANT|TOOL)\]"
    r"|</?(?:system|developer|assistant|tool|function_call|tool_call)(?:\s[^>]*)?>"
    r"|<<\s*/?\s*SYS\s*>>",
    re.I | re.ASCII,
)


CONTEXT_URI = re.compile(
    r"(?:(?<![a-z0-9_])data\s*:\s*(?:[a-z][a-z0-9.+-]*/[^,\s]+|;[^,\s]*|),|(?<![a-z0-9_])file\s*:\s*(?:[/\\]|[a-z]:|[^\s]*[./\\][^\s]+)|(?<![a-z0-9_])blob\s*:\s*(?:https?:|null/|[a-f0-9]{8}-))",
    re.I | re.ASCII,
)
HTML = re.compile(
    r"<\s*/?\s*(?:script|iframe|a|img|object|embed|form|meta|style|svg|link|base|video|audio)\b",
    re.I | re.ASCII,
)
SECRET = re.compile(
    r"(?:github_pat_[A-Za-z0-9_]{16,}|gh[pousr]_[A-Za-z0-9]{18,}|glpat-[A-Za-z0-9_-]{16,}|"
    r"xox[baprs]-[A-Za-z0-9-]{16,}|AIza[A-Za-z0-9_-]{30,}|(?:AKIA|ASIA)[A-Z0-9]{16}|"
    r"(?:sk|rk)_(?:live|test)_[A-Za-z0-9]{16,}|sk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}|"
    r"-----BEGIN (?:RSA |OPENSSH |EC |DSA |ENCRYPTED )?PRIVATE KEY-----|"
    r"ssh-(?:rsa|ed25519)\s+[A-Za-z0-9+/]{32,}={0,2}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{16,})"
)
PAYLOAD = re.compile(
    r"(?<![A-Za-z0-9+/=_-])(?:[A-Za-z0-9+/]{6,}={0,2}|[A-Za-z0-9_-]{32,})(?![A-Za-z0-9+/=_-])"
)
SIGNATURES = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"7z\xbc\xaf\x27\x1c",
    b"Rar!",
    b"\x1f\x8b",
    b"BZh",
    b"\x7fELF",
    b"MZ",
    b"\x89PNG",
    b"GIF8",
    b"RIFF",
    b"OggS",
    b"fLaC",
    b"%PDF-",
)


def strict_json(text: str):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON key: {key!r}")
            result[key] = value
        return result

    def constant(token):
        raise ValueError(f"Non-finite JSON number: {token}")

    def number(token):
        value = float(token)
        if not math.isfinite(value):
            raise ValueError("Non-finite JSON number")
        return value

    return json.loads(
        text, object_pairs_hook=unique, parse_constant=constant, parse_float=number
    )


def normalized(value: str) -> str:
    """Inspect bounded decoded forms without rewriting submitted text."""
    result = (
        unicodedata.normalize("NFKC", value)
        .replace("\u3002", ".")
        .replace("\uff61", ".")
    )
    for _ in range(3):
        if has_hidden(result):
            raise ValueError("forbidden hidden/control character")
        result = unquote(result)

        def numeric(match):
            token = match.group(1)
            if len(token) > 9:
                raise ValueError("Invalid numeric entity")
            code = int(token[1:], 16) if token[:1].lower() == "x" else int(token)
            if code <= 0x10FFFF and has_hidden(chr(code)):
                raise ValueError("forbidden encoded control character")
            return match.group()

        result = re.sub(r"&#(x[0-9a-f]+|[0-9]+);?", numeric, result, flags=re.I)
        result = (
            unicodedata.normalize("NFKC", html.unescape(result))
            .replace("\u3002", ".")
            .replace("\uff61", ".")
        )
    return re.sub(
        r"[\[({]\s*(?:dot|\.)\s*[\])}]",
        ".",
        re.sub(r"[\[({]\s*(?:colon|:)\s*[\])}]", ":", result, flags=re.I),
        flags=re.I | re.ASCII,
    )


def has_hidden(value: str) -> bool:
    return any(
        (unicodedata.category(c) in {"Cc", "Cf", "Cs"} and c not in "\n\f")
        or c == "\u034f"
        or "\u180b" <= c <= "\u180f"
        or "\ufe00" <= c <= "\ufe0f"
        or "\U000e0100" <= c <= "\U000e01ef"
        for c in value
    )


def has_link(value: str) -> bool:
    compact = re.sub(r"\s+", "", value)
    if (
        SCHEME.search(value)
        or CONTEXT_URI.search(value)
        or CONTEXT_URI.search(compact)
        or LINK_SYNTAX.search(value)
    ):
        return True
    for match in DOMAIN.finditer(value):
        raw = match.group()
        host = re.sub(r"[ \t]", "", raw).lower()
        labels = host.split(".")
        contiguous = raw.lower() == host
        spaced_dot = re.search(r"[ \t]+\.", raw) is not None
        file_reference = labels[-1] in {
            "py", "md", "js", "mjs", "sh", "ts", "cs", "json", "csv", "txt", "html", "css"
        } and (
            value[max(0, match.start() - 1) : match.start()] in {"/", "\\"}
            or (
                value[max(0, match.start() - 1) : match.start()] == "`"
                and value[match.end() : match.end() + 1] == "`"
            )
        )
        if labels[0] == "www" or labels[-1] in SUFFIXES or host in SHORTENERS:
            return True
        if (
            (contiguous or spaced_dot)
            and not file_reference
            and (
                re.fullmatch(r"[a-z]{2,63}", labels[-1])
                or labels[-1].startswith("xn--")
                or not labels[-1].isascii()
            )
        ):
            return True
        if len(labels) == 4 and all(
            part.isascii() and part.isdigit() and 0 <= int(part) <= 255
            for part in labels
        ):
            return True
        if value[match.end() : match.end() + 1] in {"/", ":"}:
            return True
    return False


def encoded_payload(value: str) -> bool:
    if re.search(
        r"(?i)(?<!\w)(?:(?:0x)?[0-9a-f]{2}(?:\s*,\s*|\s+)){63}(?:0x)?[0-9a-f]{2}(?!\w)",
        value,
    ):
        return True
    # Recognize wrapped encodings without mistaking ordinary spaced prose for
    # Base64. A long encoded line/hex-dump run is not a dialogue contribution.
    wrapped = re.findall(r"(?m)^[ \t]*([A-Za-z0-9+/_-]{48,}={0,2})[ \t]*$", value)
    if sum(map(len, wrapped)) >= 128:
        return True
    for match in PAYLOAD.finditer(value):
        token = match.group()
        # Long unbroken encodings have no purpose in an English dialogue field.
        if len(token) >= 128:
            return True
        candidates = []
        if len(token) % 2 == 0 and re.fullmatch("[0-9a-fA-F]+", token):
            candidates.append(bytes.fromhex(token))
        try:
            candidates.append(
                base64.b64decode(
                    token.replace("-", "+").replace("_", "/") + "=" * (-len(token) % 4),
                    validate=True,
                )
            )
        except ValueError:
            pass
        if any(data.startswith(sig) for data in candidates for sig in SIGNATURES):
            return True
        for data in candidates:
            if data.isascii():
                decoded_text = data.decode("ascii")
                if len(token) < 16:
                    # Short ordinary words can decode to control bytes by chance.
                    decoded_text = "".join(c for c in decoded_text if not has_hidden(c))
                decoded = normalized(decoded_text)
                if (
                    has_link(decoded)
                    or ROLE_MARKER.search(decoded)
                    or HTML.search(decoded)
                    or SECRET.search(decoded)
                ):
                    return True
    return False


def check_safe_text(value, label: str, limit: int = 2500) -> None:
    if value is None:
        return
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(
            f"{label}: expected nonempty text of at most {limit} characters or null"
        )
    stripped = strip_color_markers(value)
    # Inspect the submitted text and the result of removing only recognized
    # color spans. The second pass catches dangerous strings split by markup.
    for candidate in dict.fromkeys((value, stripped)):
        inspected = normalized(candidate)
        for visible in dict.fromkeys((inspected, strip_color_markers(inspected))):
            if has_hidden(candidate) or has_hidden(visible):
                raise ValueError(f"{label}: forbidden hidden/control character")
            if has_link(visible) or HTML.search(visible):
                raise ValueError(f"{label}: links/active markup are not allowed")
            if ROLE_MARKER.search(visible):
                raise ValueError(f"{label}: reserved instruction/role marker")
            if SECRET.search(visible):
                raise ValueError(f"{label}: possible credential material")
            if encoded_payload(visible):
                raise ValueError(f"{label}: possible encoded binary/data payload")
            if "⟦0x" in visible:
                raise ValueError(f"{label}: unresolved source glyph marker")
