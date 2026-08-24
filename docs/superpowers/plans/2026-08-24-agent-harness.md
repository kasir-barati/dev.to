# Agent Harness for dev.to Content Repo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give this repo a documented, working handoff protocol between project-specific Claude Code subagents, and close a real bug in it (asset-only edits under `articles/assets/<slug>/` never actually reach dev.to).

**Architecture:** Four static `.claude/agents/*.md` subagent definitions (content-editor, ci-ops, reviewer, self-improvement) plus two root docs (`PROCESS.md`, `SELF_IMPROVEMENT.md`) that define how an orchestrating Claude Code session dispatches work between them. Separately, a new `scripts/bump_asset_versions.py` and a `publish.yml` change implement real cache-busting so an asset-only change actually triggers a dev.to update, since `devto-cli` silently no-ops when an article's markdown content hasn't changed.

**Tech Stack:** Plain Python 3 (argparse, no external deps for the new script — no PyYAML needed), Bash inside GitHub Actions `run:` blocks, Claude Code project subagent frontmatter (Markdown + YAML frontmatter).

**Spec:** `docs/superpowers/specs/2026-08-24-agent-harness-design.md`

## Global Constraints

- No `?v=` token is ever hand-written by the article author — the version bump is 100% automated by CI, same spirit as the existing relative→absolute image URL rewrite the author never touches.
- `reviewer`'s `tools:` frontmatter must be exactly `Read, Grep, Glob` — no Write, Edit, NotebookEdit, or Bash, ever. This is the only mechanism that actually guarantees it cannot change anything (Bash could write files via redirection even if discouraged only in its prompt).
- `self-improvement` is the only agent whose prompt authorizes editing `PROCESS.md` or `SELF_IMPROVEMENT.md`.
- Any diff touching `.github/workflows/**` or `scripts/**` must go through the `reviewer` agent before it is committed to `main` — this plan's own Task 4/5 diff is not exempt (Task 6 dogfoods this).
- `publish.yml` and `schedule.yml` share the `devto-main-write` concurrency group (both can push to `main`) — do not remove or fork that group. `audit.yml` (`devto-audit`) and `validate.yml` (`validate-${{ github.ref }}`) each have their own separate group.
- `DEVTO_API_KEY` is passed to devto-cli only via the `DEVTO_TOKEN` env var, never a CLI flag — preserve this in any step that's touched.
- No test framework is being introduced. This repo has none (`scripts/*.py` has zero test files); new script logic is verified by direct invocation with real assertions, matching the codebase's existing convention.
- `validate_articles.py` already strips query strings before checking image existence (`url.split("?")[0]` at both the cover-image and inline-image checks) — confirmed by reading `scripts/validate_articles.py:150,166`. The new `?v=` suffix will not trip validation; no change to `validate_articles.py` is needed.

---

## Task 1: Project subagent definitions

**Files:**
- Create: `.claude/agents/content-editor.md`
- Create: `.claude/agents/ci-ops.md`
- Create: `.claude/agents/reviewer.md`
- Create: `.claude/agents/self-improvement.md`

**Interfaces:**
- Produces: four subagent names (`content-editor`, `ci-ops`, `reviewer`, `self-improvement`) that Task 6 and Task 7 invoke for real via the `Agent` tool with `subagent_type` set to the matching name.

- [ ] **Step 1: Create `.claude/agents/content-editor.md`**

```markdown
---
name: content-editor
description: Scaffolds and edits dev.to articles under articles/**/*.md — applying this repo's AGENTS.md content rules (template, frontmatter, tags, series, cover_image, relative asset paths). Use for article authoring/editing tasks, never for .github/workflows/** or scripts/** changes — that's ci-ops's job.
tools: Read, Write, Edit, Grep, Glob, Bash
model: haiku
---

You edit articles in this dev.to content repo. Read AGENTS.md before every
task — it is the source of truth for the rules below, and it may have
changed since your last run.

Hard rules (from AGENTS.md):
- New articles start from `templates/article-template.md`.
- Frontmatter renders as the dev.to H1; the body must start at `##`, never
  `#` (a body `#` produces a second H1 and trips MD025).
- `tags`: at most 4, lowercase alphanumeric only. dev.to silently drops the
  5th and lowercases the rest.
- `cover_image`: absolute `raw.githubusercontent.com` URL (generate via
  `python scripts/gen_cover_image.py`), never a relative path — devto-cli
  does not rewrite it.
- `series`: must match an existing series name exactly — check `INDEX.md`
  first. A near-miss creates a second series on dev.to.
- Assets for an article live under `articles/assets/<slug>/` and are
  referenced from the article body with relative `./assets/<slug>/...`
  paths — never write an absolute URL for an inline image yourself,
  devto-cli rewrites relative paths at push time.
- One paragraph = one unwrapped line (house style — no hand-wrapping).
- Only `articles/*.md` (top-level) is synced to dev.to. `articles/TIL/`,
  `articles/DRAFT/`, `articles/JA/` are not.

Scope boundary: you touch `articles/**` and `templates/**` only. If a task
needs a change to `.github/workflows/**` or `scripts/**`, stop and say so —
that belongs to `ci-ops`, not you.

Before finishing, run `python scripts/validate_articles.py <files you
touched>` and fix anything it reports as an error (warnings don't block,
but note them).
```

- [ ] **Step 2: Create `.claude/agents/ci-ops.md`**

```markdown
---
name: ci-ops
description: Edits this repo's GitHub Actions workflows (.github/workflows/**) and Python tooling (scripts/**) — the publish/validate/schedule/audit pipeline. Use for CI/script changes, never for article content — that's content-editor's job. Any diff this agent produces must go through the reviewer agent before it's committed.
tools: Read, Write, Edit, Grep, Glob, Bash
model: sonnet
---

You maintain the CI pipeline for this dev.to content repo:
`.github/workflows/*.yml` and `scripts/*.py`. Read `PROCESS.md` and
`AGENTS.md` before every task — `PROCESS.md` documents how the pipeline
actually behaves today (including known gaps), `AGENTS.md` has the repo's
content/validation rules your scripts must enforce.

Constraints:
- `publish.yml` and `schedule.yml` share the `devto-main-write` concurrency
  group because both can push to `main` — don't remove that without
  understanding why (races between them). `audit.yml` has its own separate
  `devto-audit` group and `validate.yml` its own `validate-${{ github.ref }}`
  group — neither shares `devto-main-write`.
- `DEVTO_API_KEY` is passed to devto-cli as the `DEVTO_TOKEN` env var,
  never a CLI flag (keeps it out of the runner's process table) — preserve
  that pattern in any step you touch.
- New Python scripts follow the existing style in `scripts/`: argparse
  CLI, docstring usage examples at the top, no test framework (there isn't
  one in this repo — verify by direct invocation with real assertions
  instead).
- Pin third-party Actions by commit SHA with a version comment, matching
  the existing steps (e.g. `actions/checkout@<sha> # v7.0.1`).

Scope boundary: you touch `.github/workflows/**` and `scripts/**` only. If
a task needs article content changes, stop and say so — that belongs to
`content-editor`, not you.

Before finishing, describe exactly what you changed and why, so the
orchestrator can hand it to `reviewer`. Do not consider your own diff
"done" until it passes review — you don't self-approve CI changes.
```

- [ ] **Step 3: Create `.claude/agents/reviewer.md`**

```markdown
---
name: reviewer
description: Read-only reviewer for changes to .github/workflows/** and scripts/** in this repo. Cannot edit, write, or run shell commands — static review only. The orchestrator must send it every diff touching Actions workflows or scripts before that diff is committed.
tools: Read, Grep, Glob
model: opus
---

You review changes to this dev.to content repo's CI pipeline:
`.github/workflows/*.yml` and `scripts/*.py`. You have no Write, Edit, or
Bash access — you cannot change anything, by design. If you conclude
something needs to change, say so in your findings; you do not make the
change yourself.

Read `PROCESS.md` and `AGENTS.md` first for context on how the pipeline is
supposed to behave and what the content rules are, then review the diff
you're given for:

- Correctness bugs: logic errors, wrong shell quoting/globs, off-by-one
  diff ranges, race conditions with the shared `devto-main-write`
  concurrency group.
- Secret handling: anything that could put `DEVTO_API_KEY`/`DEVTO_TOKEN`
  in a log, a CLI arg, or the process table.
- Silent failure modes: a step that should fail loudly but instead
  no-ops or swallows an error.
- Style/consistency with the rest of `scripts/` and
  `.github/workflows/**` (Action pinning by SHA, argparse CLI shape,
  existing regex/path-handling conventions).

Report findings ranked most-severe first. If you find nothing, say so
explicitly rather than staying silent — the orchestrator needs to know
the review actually ran and passed, not just that you produced no output.

State up front when relevant: you cannot run `actionlint`, `shellcheck`,
or the scripts themselves — this is static review only, not execution
verification.
```

- [ ] **Step 4: Create `.claude/agents/self-improvement.md`**

```markdown
---
name: self-improvement
description: Mandatory close-out agent — invoke as the last step of any task before the orchestrator considers it done. Reflects on challenges/bugs/strengths/weaknesses from the task just completed, appends a dated entry to SELF_IMPROVEMENT.md, and revises PROCESS.md when a durable process gap surfaced. Only agent allowed to edit PROCESS.md or SELF_IMPROVEMENT.md.
tools: Read, Edit, Grep, Glob
model: sonnet
---

You close out a task in this repo. You run last, always — the orchestrator
invokes you before ending any task that went through the `PROCESS.md`
handoff protocol, no exceptions for small tasks.

Scope: you may only edit `PROCESS.md` and `SELF_IMPROVEMENT.md`. Nothing
else. If you believe another file needs to change, say so in your output —
don't touch it.

Steps:
1. Read `SELF_IMPROVEMENT.md`'s instructions block and its most recent
   entries for context on prior lessons.
2. Reflect on the task you were just told about: what challenges, issues,
   or bugs came up; what worked well (strengths); what didn't
   (weaknesses).
3. Append a new dated entry to the log in `SELF_IMPROVEMENT.md` — don't
   rewrite prior entries. Cover: task summary, challenges/issues/bugs,
   strengths, weaknesses, what (if anything) changed in `PROCESS.md`,
   what (if anything) changed in this file's own instructions block.
4. If a *durable* gap in the process surfaced (not one-off noise —
   something that would bite the next task too), revise `PROCESS.md` to
   close it and note the change in your log entry. If nothing durable
   surfaced, say so explicitly and don't edit `PROCESS.md`.
5. If the retro process itself needs to change (e.g. the log format isn't
   capturing something useful), revise this file's instructions block and
   note that too.
```

- [ ] **Step 5: Verify all four parse as valid frontmatter**

Run:
```bash
python3 -c "
import re, sys
files = [
    '.claude/agents/content-editor.md',
    '.claude/agents/ci-ops.md',
    '.claude/agents/reviewer.md',
    '.claude/agents/self-improvement.md',
]
for f in files:
    text = open(f).read()
    m = re.match(r'^---\n(.*?)\n---\n', text, re.DOTALL)
    assert m, f'{f}: missing frontmatter block'
    fm = m.group(1)
    for key in ('name:', 'description:', 'tools:', 'model:'):
        assert key in fm, f'{f}: missing {key}'
    if 'reviewer' in f:
        tools_line = [l for l in fm.splitlines() if l.startswith('tools:')][0]
        assert tools_line.strip() == 'tools: Read, Grep, Glob', f'{f}: reviewer tools must be exactly Read, Grep, Glob, got: {tools_line}'
    print(f, 'OK')
"
```
Expected: four `OK` lines, no assertion errors.

- [ ] **Step 6: Commit**

```bash
git add .claude/agents/content-editor.md .claude/agents/ci-ops.md .claude/agents/reviewer.md .claude/agents/self-improvement.md
git commit -m "feat: add project subagents for content, CI, review, and self-improvement"
```

---

## Task 2: `PROCESS.md`

**Files:**
- Create: `PROCESS.md`

**Interfaces:**
- Consumes: subagent names from Task 1 (`content-editor`, `ci-ops`, `reviewer`, `self-improvement`).
- Produces: the handoff protocol Task 6/7 follow, and the pipeline description `ci-ops`/`reviewer` read before touching CI files.

- [ ] **Step 1: Create `PROCESS.md`**

```markdown
# Process

How content and CI work happens in this repo, and how Claude Code
subagents hand work between each other. Read this before making any
change to `.github/workflows/**` or `scripts/**`.

## Current CI pipeline

Four workflows in `.github/workflows/`. `publish.yml` and `schedule.yml`
share the `devto-main-write` concurrency group with each other since both
can push to `main`. `audit.yml` also pushes to `main` (its weekly index
refresh) but has its own separate `devto-audit` group — it is not
serialized against `publish.yml`/`schedule.yml`. `validate.yml` has its
own `validate-${{ github.ref }}` group and never pushes.

- **`validate.yml`** — gates PRs and pushes. Diffs against a resolved base
  revision, then runs `validate_articles.py`, `lint_ratchet.py` (fails
  only on *new* markdownlint errors relative to base — old articles
  predating the linter are grandfathered), and `check_links.py`, scoped to
  changed files only. Also emits a repo-wide validation report to the job
  summary (`--all --format=md`), non-blocking.
- **`publish.yml`** — on push to `main` touching `articles/**/*.md` or
  `articles/assets/**` (or manual dispatch with `scope: changed|all`).
  Diffs the push range to find changed top-level articles *and* changed
  assets, runs `scripts/bump_asset_versions.py` to cache-bust any article
  whose asset changed (see "Asset republish fix" below), validates the
  merged list, runs one batched `dev push`, then commits any file changes
  it produced (frontmatter devto-cli wrote back, plus any version bumps)
  in one commit, retrying the push up to 3x with rebase-and-retry on
  conflict.
- **`schedule.yml`** — hourly cron. Runs `publish_scheduler.py`, which
  flips `published: true` on articles whose scheduled `date` has arrived,
  and commits (deliberately without `[skip ci]` — this commit is what
  triggers `publish.yml`).
- **`audit.yml`** — weekly, report-only: full-corpus validation,
  third-party link-rot check, `dev push --dry-run` drift check against
  live dev.to, refreshes `INDEX.md` and the README stats block.

`DEVTO_API_KEY` repo secret is required for publishing; passed to
devto-cli as the `DEVTO_TOKEN` env var (never a CLI flag, to keep it out
of the runner's process table).

## Asset republish fix

**The problem this closes:** `@sinedied/devto-cli` decides whether to call
the dev.to update API by strictly comparing the local article's full
frontmatter + body against what's already published (`date` excluded). If
only an asset file changes — a diagram PNG, a cover image — the article's
markdown text is byte-identical to what's live, so devto-cli silently
skips it. Adding an asset trigger to the workflow alone would not have
fixed this: the workflow would run, `dev push` would see no diff, and
nothing would happen.

**The fix:** `scripts/bump_asset_versions.py` runs in `publish.yml`'s
"Collect articles to push" step whenever the push range touched
`articles/assets/**`. For each changed asset, it finds the owning article
(`articles/assets/<slug>/...` → `articles/<slug>.md`) and rewrites the
matching image reference — an inline `![...](./assets/<slug>/...)` markdown
image, an `<img src="...">`, or the `cover_image` frontmatter field — to
carry a `?v=<short-git-blob-hash-of-the-asset>` query string. Query strings
survive devto-cli's relative→absolute URL rewrite untouched (confirmed by
reading `util.ts`'s `updateRelativeImageUrls`), so this both (a) changes
the markdown text enough for devto-cli's diff check to trip, and (b)
produces a new URL, so dev.to fetches fresh content instead of serving a
stale cached copy of the old one.

This is fully automated — the article author never writes a `?v=` token by
hand. It's the same spirit as the existing relative→absolute image URL
rewrite: you write `./assets/<slug>/foo.png`, tooling handles the rest.

## Agent handoff protocol

The orchestrator is the main Claude Code session a human is driving.
Subagents do not invoke each other — all handoff goes through the
orchestrator.

1. Classify an incoming task as content work or CI/script work.
2. Content work (anything under `articles/**` or `templates/**`) →
   delegate to `content-editor`.
3. CI/script work (anything touching `.github/workflows/**` or
   `scripts/**`) → delegate to `ci-ops`.
4. Any diff touching `.github/workflows/**` or `scripts/**` — regardless
   of which agent produced it — **must** go to `reviewer` before it is
   committed. Content-only changes to `articles/**/*.md` skip this gate.
   `reviewer` cannot edit anything (`Read, Grep, Glob` only, by design) —
   it reports findings, the orchestrator or `ci-ops` acts on them.
5. Reviewer findings loop back to `ci-ops` (or the orchestrator) for
   fixes. Re-review after a fix is orchestrator judgment, same as any
   code review loop — not automatically re-triggered.
6. **Last step, always, before the orchestrator ends the task**: invoke
   `self-improvement`. This is not optional and is not skipped for small
   tasks. See `SELF_IMPROVEMENT.md`.
```

- [ ] **Step 2: Verify required sections are present**

Run:
```bash
grep -c '^## ' PROCESS.md
```
Expected: `3` (Current CI pipeline, Asset republish fix, Agent handoff protocol — the leading `# Process` title doesn't count as `##`). If you added or removed a heading from the content in Step 1, adjust this expected count to match.

- [ ] **Step 3: Commit**

```bash
git add PROCESS.md
git commit -m "docs: add PROCESS.md documenting the CI pipeline and agent handoff protocol"
```

---

## Task 3: `SELF_IMPROVEMENT.md`

**Files:**
- Create: `SELF_IMPROVEMENT.md`

**Interfaces:**
- Produces: the log file Task 7's `self-improvement` invocation appends its first real entry to.

- [ ] **Step 1: Create `SELF_IMPROVEMENT.md`**

```markdown
# Self-Improvement Log

Instructions for the `self-improvement` agent (`.claude/agents/self-improvement.md`):

- Read this file's prior entries before writing a new one — don't repeat
  lessons already captured.
- Append a new dated entry per task. Never rewrite or delete a prior
  entry.
- Revise `PROCESS.md` when a *durable* process gap surfaced — something
  that would bite the next task too, not one-off noise. Note the change
  in your entry.
- Revise this instructions block itself when the retro process isn't
  capturing something useful. Note that change too.
- Only this agent edits `PROCESS.md` or this file. Every other agent that
  thinks either needs to change should say so, not do it.

Each entry: task summary, challenges/issues/bugs encountered, strengths
observed, weaknesses observed, what (if anything) changed in `PROCESS.md`,
what (if anything) changed in this file's instructions.

---

## Log
```

- [ ] **Step 2: Verify the file has the expected skeleton**

Run:
```bash
grep -q '^## Log$' SELF_IMPROVEMENT.md && grep -q 'Only this agent edits' SELF_IMPROVEMENT.md && echo OK
```
Expected: `OK`.

- [ ] **Step 3: Commit**

```bash
git add SELF_IMPROVEMENT.md
git commit -m "docs: add SELF_IMPROVEMENT.md log skeleton"
```

---

## Task 4: `scripts/bump_asset_versions.py`

**Files:**
- Create: `scripts/bump_asset_versions.py`

**Interfaces:**
- Produces:
  - `owning_article(asset_path: Path) -> Path | None`
  - `version_token(asset_path: Path) -> str`
  - `bump_references(text: str, asset_filename: str, token: str) -> tuple[str, bool]`
  - `main(argv: list[str]) -> int` — CLI: `python scripts/bump_asset_versions.py <asset-path> [<asset-path> ...]`, prints modified article paths (repo-relative, one per line) to stdout, prints a warning to stderr for any asset path with no owning article, returns `0`.
- Consumes: nothing from earlier tasks (standalone script). Task 5 invokes its CLI from `publish.yml`.

- [ ] **Step 1: Write the failing check**

```bash
mkdir -p /tmp/bump-check && cat > /tmp/bump-check/check.py <<'PY'
import sys
sys.path.insert(0, "scripts")
from bump_asset_versions import owning_article, bump_references
from pathlib import Path

assert owning_article(Path("articles/assets/subagenting/foo.png")) == Path("articles/subagenting.md")
assert owning_article(Path("articles/assets/does-not-exist-slug/foo.png")) is None

md_text = "## Title\n\n![alt](./assets/foo/diagram.png)\n"
new_text, changed = bump_references(md_text, "diagram.png", "abc123")
assert changed is True
assert new_text == "## Title\n\n![alt](./assets/foo/diagram.png?v=abc123)\n", new_text

new_text2, changed2 = bump_references(md_text, "other.png", "abc123")
assert changed2 is False
assert new_text2 == md_text

fm_text = (
    "---\n"
    "cover_image: https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/foo/cover.png\n"
    "---\n\n## Title\n"
)
new_fm, changed_fm = bump_references(fm_text, "cover.png", "def456")
assert changed_fm is True
assert "cover.png?v=def456" in new_fm, new_fm

# Re-bumping replaces the old token rather than stacking query strings.
twice, _ = bump_references(new_text, "diagram.png", "zzz999")
assert "diagram.png?v=zzz999" in twice
assert "?v=abc123" not in twice

html_text = '<img src="./assets/foo/shot.png" alt="x">\n'
new_html, changed_html = bump_references(html_text, "shot.png", "aaa111")
assert changed_html is True
assert 'src="./assets/foo/shot.png?v=aaa111"' in new_html, new_html

print("all pure-function checks passed")
PY
python3 /tmp/bump-check/check.py
```

Run this exactly as shown from the repo root. Expected: `ModuleNotFoundError: No module named 'bump_asset_versions'` (the file doesn't exist yet).

- [ ] **Step 2: Confirm which article slugs currently exist, for the `owning_article` assertion above**

Run:
```bash
ls articles/*.md | xargs -n1 basename | sed 's/\.md$//' | sort
ls articles/assets/ | sort
```
Confirm `subagenting` appears in both lists (it does as of this writing — every `articles/assets/<slug>/` has a matching `articles/<slug>.md` today). If the repo state has changed and `subagenting` no longer exists, swap the assertion in Step 1 for any slug that appears in both listings.

- [ ] **Step 3: Write `scripts/bump_asset_versions.py`**

```python
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

        token = version_token(asset_path)
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
```

- [ ] **Step 4: Run the pure-function check again**

Run:
```bash
python3 /tmp/bump-check/check.py
```
Expected: `all pure-function checks passed`, no assertion errors.

- [ ] **Step 5: Full CLI + git integration check in a throwaway sandbox**

```bash
sandbox=$(mktemp -d)
git -C "$sandbox" init -q
git -C "$sandbox" config user.email test@example.com
git -C "$sandbox" config user.name test
mkdir -p "$sandbox/articles/assets/demo-slug"
cp scripts/bump_asset_versions.py "$sandbox/bump_asset_versions.py"

cat > "$sandbox/articles/demo-slug.md" <<'MD'
---
cover_image: https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/demo-slug/cover.png
---

## Hello

![diagram](./assets/demo-slug/diagram.png)
MD
printf 'fake png v1' > "$sandbox/articles/assets/demo-slug/diagram.png"
printf 'fake cover v1' > "$sandbox/articles/assets/demo-slug/cover.png"
( cd "$sandbox" && git add -A && git commit -q -m seed )

# Simulate an asset-only edit: only the diagram changes.
printf 'fake png v2 - changed content' > "$sandbox/articles/assets/demo-slug/diagram.png"
( cd "$sandbox" && git add -A && git commit -q -m "update diagram" )

echo "--- run on the changed asset ---"
( cd "$sandbox" && python3 bump_asset_versions.py articles/assets/demo-slug/diagram.png )

echo "--- resulting article ---"
cat "$sandbox/articles/demo-slug.md"

echo "--- unreferenced asset: must not touch the article or print anything ---"
printf 'unused' > "$sandbox/articles/assets/demo-slug/unused.png"
( cd "$sandbox" && git add -A && git commit -q -m "add unused asset" )
( cd "$sandbox" && python3 bump_asset_versions.py articles/assets/demo-slug/unused.png )

echo "--- asset with no owning article: must warn on stderr, exit 0, print nothing on stdout ---"
mkdir -p "$sandbox/articles/assets/orphan-slug"
printf 'orphan' > "$sandbox/articles/assets/orphan-slug/img.png"
( cd "$sandbox" && git add -A && git commit -q -m "add orphan asset" )
( cd "$sandbox" && python3 bump_asset_versions.py articles/assets/orphan-slug/img.png )
echo "exit code: $?"
```

Expected:
- The first run prints exactly `articles/demo-slug.md`, and the article
  now shows `./assets/demo-slug/diagram.png?v=<7-char-hash>` in the body —
  `cover_image` is unchanged (only the diagram asset changed).
- The "unreferenced asset" run prints nothing (no article referenced
  `unused.png`), and `git status` in the sandbox shows no modification to
  `articles/demo-slug.md` from that run.
- The "no owning article" run prints a `warning: no owning article for
  articles/assets/orphan-slug/img.png` line on stderr, nothing on stdout,
  and exits `0`.

- [ ] **Step 6: Clean up the sandbox**

```bash
rm -rf "$sandbox" /tmp/bump-check
```

- [ ] **Step 7: Commit**

```bash
git add scripts/bump_asset_versions.py
git commit -m "feat: add bump_asset_versions.py to cache-bust image refs on asset changes"
```

---

## Task 5: Wire the fix into `publish.yml`

**Files:**
- Modify: `.github/workflows/publish.yml:7-8` (trigger paths)
- Modify: `.github/workflows/publish.yml:51-81` (Collect articles to push step)

**Interfaces:**
- Consumes: `scripts/bump_asset_versions.py`'s CLI from Task 4 (`python scripts/bump_asset_versions.py <paths...>` → modified article paths on stdout, one per line).

- [ ] **Step 1: Add the trigger path**

In `.github/workflows/publish.yml`, change:

```yaml
on:
  push:
    branches:
      - main
    paths:
      - 'articles/**/*.md'
```

to:

```yaml
on:
  push:
    branches:
      - main
    paths:
      - 'articles/**/*.md'
      - 'articles/assets/**'
```

- [ ] **Step 2: Extend the "Collect articles to push" step**

Replace the step's `run:` block (currently lines 58-81) with:

```yaml
        run: |
          set -euo pipefail
          list="${RUNNER_TEMP}/${ARTICLE_LIST}"

          # ':(glob)' stops '*' from matching '/', so this stays top-level only.
          # articles/TIL/ and any other subdirectory is intentionally not published.
          if [ "$EVENT" = "workflow_dispatch" ] && [ "$SCOPE" = "all" ]; then
            git ls-files -z -- ':(glob)articles/*.md' > "$list"
          else
            base="$BEFORE"
            if [ -z "$base" ] || [ "$base" = "0000000000000000000000000000000000000000" ] || ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
              # First push on a branch, or a force-push rewrote history.
              base="$(git rev-parse "${AFTER}^" 2>/dev/null || echo "$AFTER")"
            fi
            git diff -z --name-only --diff-filter=d "$base" "$AFTER" -- ':(glob)articles/*.md' > "$list"

            # Asset-only changes don't touch the article's markdown, but the
            # article still needs to be re-pushed so devto-cli's diff check
            # (full file content equality) picks up the cache-busted image
            # reference bump_asset_versions.py is about to write. See
            # docs/superpowers/specs/2026-08-24-agent-harness-design.md.
            assets_list="${RUNNER_TEMP}/articles-assets.nul"
            git diff -z --name-only --diff-filter=d "$base" "$AFTER" -- ':(glob)articles/assets/**' > "$assets_list"
            asset_files=()
            mapfile -d '' -t asset_files < "$assets_list"
            if [ "${#asset_files[@]}" -gt 0 ]; then
              bumped_articles=()
              mapfile -t bumped_articles < <(python scripts/bump_asset_versions.py "${asset_files[@]}")
              if [ "${#bumped_articles[@]}" -gt 0 ]; then
                files=()
                mapfile -d '' -t files < "$list"
                for a in "${bumped_articles[@]}"; do
                  files+=("$a")
                done
                printf '%s\0' "${files[@]}" | python3 -c "
import sys
seen = []
for chunk in sys.stdin.buffer.read().split(b'\0'):
    if chunk and chunk not in seen:
        seen.append(chunk)
sys.stdout.buffer.write(b'\0'.join(seen))
sys.stdout.buffer.write(b'\0' if seen else b'')
" > "$list"
              fi
            fi
          fi

          files=()
          mapfile -d '' -t files < "$list"
          echo "count=${#files[@]}" >> "$GITHUB_OUTPUT"
          echo "Articles to push: ${#files[@]}"
          if [ "${#files[@]}" -gt 0 ]; then
            printf '  %s\n' "${files[@]}"
          fi
```

- [ ] **Step 3: Verify the new collect logic in a standalone sandbox (no `act`, no live GitHub Actions run needed)**

```bash
sandbox=$(mktemp -d)
git -C "$sandbox" init -q -b main
git -C "$sandbox" config user.email test@example.com
git -C "$sandbox" config user.name test
mkdir -p "$sandbox/articles/assets/demo-slug" "$sandbox/scripts"
cp scripts/bump_asset_versions.py "$sandbox/scripts/bump_asset_versions.py"

cat > "$sandbox/articles/demo-slug.md" <<'MD'
---
cover_image: https://raw.githubusercontent.com/kasir-barati/dev.to/refs/heads/main/articles/assets/demo-slug/cover.png
---

## Hello

![diagram](./assets/demo-slug/diagram.png)
MD
printf 'v1' > "$sandbox/articles/assets/demo-slug/diagram.png"
( cd "$sandbox" && git add -A && git commit -q -m seed )
before_sha=$(git -C "$sandbox" rev-parse HEAD)

# Asset-only change — the markdown file itself is untouched.
printf 'v2 changed' > "$sandbox/articles/assets/demo-slug/diagram.png"
( cd "$sandbox" && git add -A && git commit -q -m "update diagram" )
after_sha=$(git -C "$sandbox" rev-parse HEAD)

runner_temp=$(mktemp -d)
cat > "$sandbox/collect.sh" <<'SCRIPT'
set -euo pipefail
list="${RUNNER_TEMP}/articles.nul"

if [ "$EVENT" = "workflow_dispatch" ] && [ "$SCOPE" = "all" ]; then
  git ls-files -z -- ':(glob)articles/*.md' > "$list"
else
  base="$BEFORE"
  if [ -z "$base" ] || [ "$base" = "0000000000000000000000000000000000000000" ] || ! git cat-file -e "${base}^{commit}" 2>/dev/null; then
    base="$(git rev-parse "${AFTER}^" 2>/dev/null || echo "$AFTER")"
  fi
  git diff -z --name-only --diff-filter=d "$base" "$AFTER" -- ':(glob)articles/*.md' > "$list"

  assets_list="${RUNNER_TEMP}/articles-assets.nul"
  git diff -z --name-only --diff-filter=d "$base" "$AFTER" -- ':(glob)articles/assets/**' > "$assets_list"
  asset_files=()
  mapfile -d '' -t asset_files < "$assets_list"
  if [ "${#asset_files[@]}" -gt 0 ]; then
    bumped_articles=()
    mapfile -t bumped_articles < <(python3 scripts/bump_asset_versions.py "${asset_files[@]}")
    if [ "${#bumped_articles[@]}" -gt 0 ]; then
      files=()
      mapfile -d '' -t files < "$list"
      for a in "${bumped_articles[@]}"; do
        files+=("$a")
      done
      printf '%s\0' "${files[@]}" | python3 -c "
import sys
seen = []
for chunk in sys.stdin.buffer.read().split(b'\0'):
    if chunk and chunk not in seen:
        seen.append(chunk)
sys.stdout.buffer.write(b'\0'.join(seen))
sys.stdout.buffer.write(b'\0' if seen else b'')
" > "$list"
    fi
  fi
fi

files=()
mapfile -d '' -t files < "$list"
echo "count=${#files[@]}"
printf '  %s\n' "${files[@]}"
SCRIPT

( cd "$sandbox" && EVENT=push SCOPE= BEFORE="$before_sha" AFTER="$after_sha" RUNNER_TEMP="$runner_temp" bash collect.sh )
```

Expected output:
```
count=1
  articles/demo-slug.md
```

This confirms an asset-only push range correctly resolves to the owning
article via `bump_asset_versions.py`, with no duplicate entries even
though the same file could theoretically appear from both diffs.

- [ ] **Step 4: Clean up the sandbox**

```bash
rm -rf "$sandbox" "$runner_temp"
```

- [ ] **Step 5: Commit**

```bash
git add .github/workflows/publish.yml
git commit -m "fix: republish an article when only its assets change, not just its markdown"
```

---

## Task 6: Reviewer gate on the Task 4 + Task 5 diff

This task has no code changes of its own — it dogfoods the handoff
protocol `PROCESS.md` (Task 2) defines: any diff touching
`.github/workflows/**` or `scripts/**` must go through `reviewer` before
it's considered done. This step is executed by the orchestrating session
directly (via the `Agent` tool), not by a fresh generic task-implementer —
the point is to invoke the real `reviewer` subagent from Task 1.

- [ ] **Step 1: Gather the diff to review**

```bash
git log --oneline -5
git show --stat HEAD~1  # Task 5's publish.yml commit
git show --stat HEAD~2  # Task 4's bump_asset_versions.py commit
```

- [ ] **Step 2: Invoke the `reviewer` subagent**

Use the `Agent` tool with `subagent_type: reviewer`. Prompt it with: the
purpose of the change (close the asset-republish gap), the full content of
`scripts/bump_asset_versions.py`, and the diff to `.github/workflows/publish.yml`
(trigger paths + the rewritten "Collect articles to push" step). Ask it to
review per its own instructions (correctness, secret handling, silent
failure modes, style consistency).

- [ ] **Step 3: Address findings**

If `reviewer` reports findings: fix them directly (this is CI/script work,
in scope for whoever is executing this plan), then create a **new** commit
(don't amend Task 4 or Task 5's commits) with message
`fix: address reviewer findings on asset republish fix`. If it reports
none, or only notes the stated tradeoffs (no `actionlint`/execution
verification), proceed with no new commit.

---

## Task 7: Mandatory self-improvement close-out

Dogfoods the other mandatory step from `PROCESS.md`: `self-improvement`
runs last, always. This is the final task of this plan — do not consider
the plan done until this task's commit lands.

- [ ] **Step 1: Invoke the `self-improvement` subagent**

Use the `Agent` tool with `subagent_type: self-improvement`. Tell it: this
was the task that built the entire agent harness described in
`docs/superpowers/specs/2026-08-24-agent-harness-design.md` and this plan
— summarize what was built (four subagents, `PROCESS.md`,
`SELF_IMPROVEMENT.md`, the asset cache-busting fix), and let it read
`SELF_IMPROVEMENT.md` and reflect per its own instructions on any
friction encountered while executing Tasks 1-6 (e.g. anything that came up
during the reviewer pass in Task 6, any assumption in the plan that turned
out wrong, anything about the sandbox verification approach worth noting
for next time).

- [ ] **Step 2: Verify it only touched the two files it's allowed to**

```bash
git status --porcelain
```
Expected: only `PROCESS.md` and/or `SELF_IMPROVEMENT.md` listed as
modified (staged or unstaged). If anything else changed, that's a bug in
the `self-improvement` agent's scope adherence — revert the unrelated
change and re-run Step 1 with a stronger reminder of its scope boundary.

- [ ] **Step 3: Commit**

```bash
git add PROCESS.md SELF_IMPROVEMENT.md
git commit -m "docs: self-improvement close-out for the agent harness task"
```
