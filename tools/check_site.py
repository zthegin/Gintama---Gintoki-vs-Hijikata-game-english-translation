# Unofficial fan translation project for Gintama: Gintoki vs. Hijikata!? Kabukichou Gintama Dai Soudatsusen!! (Nintendo DS).
# I do not own Gintama or the original game. No affiliation or endorsement is implied.
# Use only legally obtained ROMs; piracy is discouraged. See RIGHTS.md for licensing and rights limits.
from __future__ import annotations

import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit

from check_public_tree import check, public_names, tracked_names


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.refs, self.ids, self.words, self.title = [], set(), [], []
        self.description = ""
        self.in_title = False
        self.ignored = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.in_title = self.in_title or tag == "title"
        if tag in {"script", "style"}:
            self.ignored += 1
        if "id" in attrs:
            if attrs["id"] in self.ids:
                raise ValueError("Repeated HTML id: " + attrs["id"])
            self.ids.add(attrs["id"])
        self.refs.extend(value for key, value in attrs.items() if key in {"href", "src"} and value)
        if tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content", "")

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        if tag in {"script", "style"}:
            self.ignored -= 1

    def handle_data(self, text):
        if self.in_title:
            self.title.append(text)
        elif not self.ignored:
            self.words.append(text)


def inspect_site(root):
    root = root.resolve()
    pages = {p: Page(p.read_text(encoding="utf-8")) for p in root.glob("*.html")}
    required = {"index.html", "cutscenes.html", "battle.html", "graphics.html", "guide.html", "install.html", "rights.html"}
    if not required <= {p.name for p in pages}:
        raise ValueError("Missing an editor or help page")
    references = 0

    def local(from_file, reference):
        nonlocal references
        url = urlsplit(reference)
        if url.scheme or url.netloc:
            if url.scheme != "https" or not url.netloc:
                raise ValueError("Unsupported link scheme in " + from_file.name)
            return
        path = (from_file.parent / unquote(url.path)).resolve() if url.path else from_file
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("Missing or unsafe local reference: " + from_file.name + " -> " + reference)
        if url.fragment and path.suffix == ".html" and unquote(url.fragment) not in pages[path].ids:
            raise ValueError("Missing HTML anchor: " + reference)
        references += 1

    for path, page in pages.items():
        text = " ".join(" ".join(page.words).split()).casefold()
        if "unofficial" not in "".join(page.title).casefold() or "unofficial" not in page.description.casefold():
            raise ValueError("Missing unofficial title or description: " + path.name)
        for notice in ("unofficial", "i do not own gintama", "legally obtained rom", "i do not support piracy"):
            if notice not in text:
                raise ValueError("Missing visible notice in " + path.name + ": " + notice)
        if "rights.html" not in page.refs:
            raise ValueError("Missing rights link: " + path.name)
        for ref in page.refs:
            local(path, ref)
    for path in root.glob("*.mjs"):
        text = path.read_text(encoding="utf-8")
        refs = re.findall(r"\bfrom\s*['\"](\.[^'\"]+)['\"]", text)
        refs += re.findall(r"['\"](assets/[^'\"]+\.json)['\"]", text)
        for ref in refs:
            local(path, ref)
    catalog = json.loads((root / "assets/catalog.json").read_text(encoding="utf-8"))
    for row in catalog["batches"]:
        if not isinstance(row.get("file"), str) or not re.fullmatch(r"ready/[a-z][a-z0-9_]*\.json", row["file"]):
            raise ValueError("Invalid batch file path")
        for kind in ("translations", "metadata"):
            local(root / "index.html", "assets/" + kind + "/" + row["file"])
    return {"pages": len(pages), "local_references": references, "batches": len(catalog["batches"])}


def main():
    parser = argparse.ArgumentParser(description="Check the unofficial editor's local links, assets and rights notices")
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--audit", action="store_true", help="Also audit every public/tracked file for prohibited payloads")
    args = parser.parse_args()
    try:
        if args.audit:
            names = sorted(set(public_names(args.site)) | set(tracked_names(args.site)))
            issues = check(args.site, names, profile="site")
            if issues:
                raise ValueError("; ".join(issues))
        print(json.dumps(inspect_site(args.site)))
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, str(error) + "\n")


if __name__ == "__main__":
    main()
