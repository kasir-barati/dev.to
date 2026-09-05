#!/usr/bin/env python3
"""
Derive an article's `series` frontmatter from its directory location.

- Articles/<slug>.md (flat)                                     -> must have NO `series` key.
- Articles/<dir>/<slug>.md (one level)                          -> `series` is sanitize_series_name(<dir>); written if missing, checked if present.
- Anything nested deeper, or under a reserved directory name    -> error.

Usage:
    python scripts/apply_series_from_dir.py articles/foo.md articles/pipeline-pattern/bar.md
"""

from __future__ import annotations

import argparse
import re
import sys
from typing import cast

import yaml
from series_dirs import ARTICLES_DIR, classify, sanitize_series_name

FRONTMATTER_RE = re.compile(r"^(---\n)(.*?\n)(---\n?)", re.DOTALL)
SERIES_LINE_RE = re.compile(r"^series:.*$", re.MULTILINE)


def process(path: str) -> str | None:
    """
    Apply the series rule to one article.
    """
    with open(path, encoding="utf-8") as handle:
        raw = handle.read()

    match = FRONTMATTER_RE.match(raw)
    if not match:
        return "no YAML frontmatter"

    body_start, fm_body, closing = match.group(1), match.group(2), match.group(3)
    try:
        data = yaml.safe_load(fm_body)
    except yaml.YAMLError as exc:
        return f"invalid frontmatter: {exc}"

    if not isinstance(data, dict):
        return "frontmatter is not a mapping"

    current = data.get("series") or None
    kind, dirname = classify(path, ARTICLES_DIR)

    if kind == "outside":
        return f"path is not under {ARTICLES_DIR}/"

    if kind == "flat":
        if current:
            return f"flat article must not have a `series` key (found {current!r})"
        return None

    if kind == "reserved":
        return None

    if kind == "too_deep":
        return f"nested more than one level deep under {ARTICLES_DIR}/{dirname}/; not a valid series article"

    expected = sanitize_series_name(cast(str, dirname))
    if current:
        if str(current) != expected:
            return f"`series: {current}` conflicts with directory-derived {expected!r}"
        return None

    # `current` is falsy here (missing, empty, or null) but the key itself may already be present in the text — replace it in place rather than appending, or a falsy `series: ''`/`series: null` line stays behind alongside the new one and js-yaml (which devto-cli uses) rejects thes resulting duplicate mapping key.
    if SERIES_LINE_RE.search(fm_body):
        new_fm_body = SERIES_LINE_RE.sub(
            lambda _m: f"series: {expected}", fm_body, count=1
        )
    else:
        new_fm_body = fm_body.rstrip("\n") + f"\nseries: {expected}\n"
    new_raw = (
        raw[: match.start()] + body_start + new_fm_body + closing + raw[match.end() :]
    )
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(new_raw)
    return None


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("paths", nargs="+", help="article paths")
    args = parser.parse_args()

    paths = [p for p in args.paths if p.endswith(".md")]

    errors = []
    for path in paths:
        error = process(path)
        if error:
            errors.append(f"{path}: {error}")

    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        print(f"\n[!] {len(errors)} article(s) failed.", file=sys.stderr)
        return 1

    print(f"[+] {len(paths)} article(s) OK.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
