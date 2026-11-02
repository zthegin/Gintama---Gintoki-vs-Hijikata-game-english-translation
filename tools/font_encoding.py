# Unofficial fan project; see RIGHTS.md. No game bytes are included here.
"""Reconstruct the native font's character order from the standard CP932 codec."""


def native_glyph_map():
    chars = []
    seen = set()
    for lead in (*range(0x81, 0xA0), *range(0xE0, 0xEB)):
        for trail in (*range(0x40, 0x7F), *range(0x80, 0xFD)):
            try:
                char = bytes((lead, trail)).decode('cp932')
            except UnicodeDecodeError:
                continue
            if char not in seen:
                chars.append(char)
                seen.add(char)
    if len(chars) != 6953:
        raise ValueError('Unexpected CP932 font repertoire')
    return {f'0x{i:04X}': char for i, char in enumerate(chars, 1)}
