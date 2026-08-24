#!/usr/bin/env python3
"""Cache-bust image references when their backing asset file changes.

devto-cli only re-publishes an article when its markdown content differs
from what's already live (strict frontmatter+body equality, `date`
excluded — see article.ts's `checkIfArticleNeedsUpdate`/`areArticlesEqual`
in @sinedied/devto-cli). Editing an asset file (e.g. a diagram PNG) under
articles/assets/<slug>/ doesn't change the article's markdown, so a plain
`dev push` silently skips it. This script closes that gap: given the asset
paths that changed in a push, it finds the owning article and bumps a
`?v=<token>` query string on the matching image reference(s) — a real
content change devto-cli will pick up. See
docs/superpowers/specs/2026-08-24-agent-harness-design.md for the
investigation behind this.

Usage:
    python scripts/bump_asset_versions.py articles/assets/foo/diagram.png [...]

Prints the article path(s) it modified, one per line, to stdout. Prints a
warning to stderr (does not fail) for any asset path with no owning
article.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

ARTICLES_DIR = Path("articles")

MD_IMAGE_RE = re.compile(r"(!\[[^\]]*\]\()([^)\s]+)(\))")
HTML_IMAGE_RE = re.compile(r"(<img[^>]+src=[\"'])([^\"']+)([\"'])")
COVER_IMAGE_RE = re.compile(r"^(cover_image:\s*[\"']?)([^\"'\s]+)([\"']?\s*)$", re.MULTILINE)


def owning_article(asset_path: Path) -> Path | None:
    """articles/assets/<slug>/... -> articles/<slug>.md, if it exists."""
    parts = asset_path.parts
    if len(parts) < 3 or parts[0] != "articles" or parts[1] != "assets":
        return None
    slug = parts[2]
    article = ARTICLES_DIR / f"{slug}.md"
    return article if article.is_file() else None


def version_token(asset_path: Path) -> str:
    """Short git blob hash of asset_path at HEAD — deterministic per content."""
    result = subprocess.run(
        ["git", "rev-parse", "--short", f"HEAD:{asset_path.as_posix()}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _bump_query(url: str, token: str) -> str:
    base = url.split("?", 1)[0]
    return f"{base}?v={token}"


def bump_references(text: str, asset_filename: str, token: str) -> tuple[str, bool]:
    """Rewrite image refs pointing at asset_filename to carry ?v=token.

    Matches on filename, not full path, so it works whether the article
    uses a relative markdown/HTML path or (for cover_image) an
    already-absolute raw.githubusercontent.com URL. Returns
    (new_text, changed).
    """
    changed = False

    def sub(m: re.Match) -> str:
        nonlocal changed
        prefix, url, suffix = m.group(1), m.group(2), m.group(3)
        if Path(url.split("?", 1)[0]).name != asset_filename:
            return m.group(0)
        changed = True
        return f"{prefix}{_bump_query(url, token)}{suffix}"

    text = MD_IMAGE_RE.sub(sub, text)
    text = HTML_IMAGE_RE.sub(sub, text)
    text = COVER_IMAGE_RE.sub(sub, text, count=1)
    return text, changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("asset_paths", nargs="+", help="Changed asset file paths, repo-relative")
    args = parser.parse_args(argv)

    touched: set[str] = set()
    for raw in args.asset_paths:
        asset_path = Path(raw)
        article = owning_article(asset_path)
        if article is None:
            print(f"warning: no owning article for {asset_path}", file=sys.stderr)
            continue

        try:
            token = version_token(asset_path)
        except subprocess.CalledProcessError:
            print(f"warning: cannot resolve {asset_path} at HEAD (deleted or invalid path); skipping", file=sys.stderr)
            continue

        text = article.read_text()
        new_text, changed = bump_references(text, asset_path.name, token)
        if changed:
            article.write_text(new_text)
            touched.add(str(article))

    for path in sorted(touched):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
