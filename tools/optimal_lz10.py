# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
import bisect
import collections


def compress(data):
    n = len(data)
    occurrences = collections.defaultdict(list)
    for p in range(n - 2):
        occurrences[data[p : p + 3]].append(p)
    matches = []
    for p in range(n):
        distances = {}
        candidates = occurrences.get(data[p : p + 3], [])
        limit = min(18, n - p)
        for q in reversed(candidates[: bisect.bisect_right(candidates, p - 2)]):
            distance = p - q
            if distance > 4096:
                break
            length = 3
            while length < limit and data[p + length] == data[p + length - distance]:
                length += 1
            for size in range(3, length + 1):
                distances.setdefault(size, distance)
            if length == limit:
                break
        matches.append(distances)
    cost = [[0] * 8 for _ in range(n + 1)]
    choice = {}
    for p in range(n - 1, -1, -1):
        for mod in range(8):
            flag = int(mod == 0)
            nextmod = (mod + 1) % 8
            best = flag + 1 + cost[p + 1][nextmod]
            selected = (1, 0)
            for size, distance in sorted(matches[p].items(), reverse=True):
                value = flag + 2 + cost[p + size][nextmod]
                if value < best:
                    best = value
                    selected = (size, distance)
            cost[p][mod] = best
            choice[p, mod] = selected
    result = bytearray(b"\x10" + n.to_bytes(3, "little"))
    p = 0
    while p < n:
        flag_at = len(result)
        result.append(0)
        flags = 0
        for mod in range(8):
            if p >= n:
                break
            size, distance = choice[p, mod]
            if distance:
                flags |= 1 << (7 - mod)
                token = ((size - 3) << 12) | (distance - 1)
                result.extend(token.to_bytes(2, "big"))
            else:
                result.append(data[p])
            p += size
        result[flag_at] = flags
    assert len(result) == 4 + cost[0][0]
    return bytes(result)
