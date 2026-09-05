#!/usr/bin/env python3
"""
Shared helpers for the directory-based series convention.

An article directly under articles/ must not carry a `series` key. An article one level under articles/<dir>/, where <dir> is not reserved, gets its `series` derived from <dir> via sanitize_series_name(). Anything nested deeper than one level is a validation error, not a silently-ignored file.
"""

from __future__ import annotations

import glob
import os
import subprocess

ARTICLES_DIR = "articles"
RESERVED_DIRS = {"TIL", "assets", "DRAFT", "JA"}
"""
These already have distinct meaning (TIL notes, per-article assets, gitignored drafts/translations) and must never be mistaken for a series directory
"""
_RESERVED_DIRS_CASEFOLD = {d.casefold() for d in RESERVED_DIRS}


def _is_reserved(dirname: str) -> bool:
    return dirname.casefold() in _RESERVED_DIRS_CASEFOLD


_gitignore_cache: dict[str, bool] = {}


def _is_gitignored(path: str) -> bool:
    """
    True if git would ignore `path` (e.g. a future local-only language dir).

    Lets an author add a new gitignored dir (per AGENTS.md's "create new
    gitignored dirs" convention) without also having to update RESERVED_DIRS
    everywhere it's duplicated. Memoized: this is called once per directory
    (not per article), but classify() may be called once per article, and
    every call for the same directory has the same answer.
    """
    if path in _gitignore_cache:
        return _gitignore_cache[path]

    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", path],
            capture_output=True,
            timeout=5,
            check=False,  # don't raise on non-zero exit codes
        )
        ignored = result.returncode == 0
    except (OSError, subprocess.SubprocessError):
        ignored = False

    _gitignore_cache[path] = ignored

    return ignored


def sanitize_series_name(dirname: str) -> str:
    """
    kebab-case directory name -> Title Case series string.

    e.g. "pipeline-pattern" -> "Pipeline Pattern".

    Deliberately simple (verified to reproduce both existing series names byte-for-byte). It cannot represent an acronym-bearing series name (e.g. "MCP Deep Dives" -> "Mcp Deep Dives") — if that's ever needed, this needs a per-directory override (e.g. a `.series` file) rather than a smarter string transform.
    """
    return " ".join(word.capitalize() for word in dirname.split("-") if word)


def classify(path: str, root: str = ARTICLES_DIR):
    """
    Classify an article path relative to root.

    Returns (kind, dirname):
      - `("outside", None)`     - path is not under root at all.
      - `("flat", None)`        - directly under root.
      - `("series", dirname)`   - exactly one level under a non-reserved dirname.
      - `("reserved", dirname)` - under a reserved or gitignored dirname, any depth.
      - `("too_deep", dirname)` - more than one level under a non-reserved dirname.
    """
    rel = os.path.relpath(path, root)
    parts = rel.split(os.sep)

    if parts[0] == os.pardir:
        return "outside", None

    if len(parts) == 1:
        return "flat", None

    dirname = parts[0]
    if _is_reserved(dirname) or _is_gitignored(os.path.join(root, dirname)):
        return "reserved", dirname

    if len(parts) > 2:
        return "too_deep", dirname

    return "series", dirname


def series_dir(path: str, root: str = ARTICLES_DIR) -> str | None:
    """
    Return the series directory name for a well-formed article path, or None if flat.

    Callers that must also reject too-deep nesting should use classify() instead.
    """
    kind, dirname = classify(path, root)

    return dirname if kind in ("series", "too_deep") else None


def discover_paths(root: str = ARTICLES_DIR):
    """
    Flat articles + one-level-deep series articles under root.

    Returns `(paths, too_deep)`: `too_deep` lists any *.md file nested more than one level under root outside a reserved directory.
    """
    paths = sorted(glob.glob(os.path.join(root, "*.md")))
    too_deep = []

    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            full = os.path.join(root, name)
            if not os.path.isdir(full) or _is_reserved(name) or _is_gitignored(full):
                continue

            paths += sorted(glob.glob(os.path.join(full, "*.md")))
            for nested in glob.glob(os.path.join(full, "**", "*.md"), recursive=True):
                if os.path.dirname(nested) != full:
                    too_deep.append(nested)

    return sorted(paths), sorted(too_deep)
