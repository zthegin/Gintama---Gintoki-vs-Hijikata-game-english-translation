#!/usr/bin/env python3
# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import os
import sys

from text_policy import check_safe_text


def main():
    for field, maximum in (("PR_TITLE", 300), ("PR_BODY", 20000)):
        value = os.environ.get(field, "")
        # The body is optional; preserve blank metadata rather than demanding
        # filler. Any actual content gets the same checks as translation text.
        if value:
            try:
                check_safe_text(value, field, maximum)
            except ValueError as error:
                return str(error)
    return None


if __name__ == "__main__":
    error = main()
    if error:
        print("PR REJECTED:", error, file=sys.stderr)
        sys.exit(1)
    print("PR metadata scan passed; reviewers must still check the discussion.")
