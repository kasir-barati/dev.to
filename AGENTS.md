# Project Summary

- Source of truth for articles auto-published to [dev.to/kasir-barati](https://dev.to/kasir-barati).
- Articles live as markdown in `articles/`; pushing to `main` publishes changed articles via `@sinedied/devto-cli`.
- This is a content repo with a small Python tooling layer, not an application.

# Standards & Guidelines

## Writing an Article

```bash
cp templates/article-template.md articles/<slug>.md
```

- The filename slug becomes part of the dev.to URL slug (dev.to appends a random suffix on first publish).
- Frontmatter renders as the dev.to page H1, the body must start at `##`, never `#` (a body `#` produces a second H1 and trips MD025).
- `tags`: at most 4, lowercase alphanumeric only. dev.to silently drops the 5th and lowercases the rest.
- `cover_image`: must be an absolute `raw.githubusercontent.com` URL, not a relative path. devto-cli does not rewrite it. Generate the canonical 1000x420 size with `scripts/gen_cover_image.py`.
- `series`: unquoted, must match an existing series name exactly (check `INDEX.md`). A near-miss creates a second series on dev.to.
- `date` + `published: false`: schedules the article; the hourly `schedule.yml` cron flips `published: true` once the UTC time arrives (see `scripts/publish_scheduler.py`).
- After publishing, devto-cli writes the dev.to `id`/`date` back into frontmatter and a bot commit (`chore: update article metadata from dev.to [skip ci]`) lands on `main`, pull before editing again to avoid diverging from that writeback.
- One paragraph = one unwrapped line (house style; see `.markdownlint-cli2.jsonc`, which disables MD013 for this reason. An unconfigured runner would otherwise wrap-enforce and break the lint ratchet on every new article).

## Commands

Run `make help` to see all available commands

Run a single script directly for narrower checks, e.g. `python scripts/validate_articles.py articles/foo.md` or `BASE=main make validate-changed`.

## Directory Structure

- `articles/*.md`: top-level, published articles. Only these are synced to dev.to (`git diff ... -- ':(glob)articles/*.md'` in the workflows deliberately excludes subdirectories).
- `articles/TIL/`, `articles/assets/<slug>/`: TIL notes and per-article assets (images, `diagrams/*.d2` sources + rendered PNGs). Assets referenced from an article must use `./assets/<slug>/...` relative paths in the repo but resolve to absolute `raw.githubusercontent.com` URLs after `dev push` rewrites them. A `?v=<token>` query string sometimes appended to an image reference is written automatically by `scripts/bump_asset_versions.py` when its asset changes — never hand-author or hand-edit one.
- `articles/DRAFT/`, `articles/JA/`: gitignored, local-only (drafts, Japanese translations. You can create new gitignored dirs for other languages the same way). Never reach dev.to or git history.
- `scripts/`: all repo tooling, plain Python (PyYAML + python-dateutil; Pillow only for `gen_cover_image.py`, kept out of `requirements.txt` so the hourly scheduler workflow doesn't pay for that wheel; `pre-commit` itself lives in `requirements-dev.txt`, same reasoning — no workflow installs it).
- `make setup` also runs `pre-commit install`, registering a git hook (`.pre-commit-config.yaml`) that runs `validate_articles.py` against staged top-level articles before each commit — the same check `validate.yml` gates on, just earlier. It only covers article files staged in the commit; it doesn't catch an asset-only edit or a reference to an unstaged asset (CI still catches both).
- `templates/article-template.md`: starting frontmatter/section skeleton for a new article.

## CI Mechanics -- `.github/workflows/`

`publish.yml` and `schedule.yml` share the `devto-main-write` concurrency group since both can push to `main`, and pushes would race otherwise. `audit.yml` also pushes to `main` (its weekly index refresh) but has its own separate `devto-audit` group. `validate.yml` has its own `validate-${{ github.ref }}` group and never pushes:

- **`publish.yml`**: on push to `main` touching `articles/**/*.md` or `articles/assets/**` (or manual dispatch with `scope: changed|all`). Diffs the push range to find changed top-level articles and any articles whose assets changed; for asset-only changes, `scripts/bump_asset_versions.py` cache-busts the affected image reference with a `?v=<token>` query string first (devto-cli only republishes when an article's markdown content differs from what's already live, so an asset-only edit needs a real content change to actually reach dev.to — see `PROCESS.md` for the full explanation). Validates the merged list, runs one batched `dev push` (devto-cli throttles internally: 30 updates/30s, 10 creates/30s, don't add per-file loops/sleeps around it), then commits any frontmatter devto-cli wrote back plus any version-bump edits, retrying the push up to 3x with rebase-and-retry on conflict.
- **`schedule.yml`**: hourly cron. Runs `publish_scheduler.py`, which flips `published: true` on articles whose scheduled `date` has arrived, and commits (deliberately without `[skip ci]`, this commit is what triggers `publish.yml`).
- **`validate.yml`**: gates PRs and pushes. Diffs against a resolved base revision, then runs `validate_articles.py`, `lint_ratchet.py` (fails only on *new* markdownlint errors relative to base. Old articles predating the linter are grandfathered), and `check_links.py`, scoped to changed files only. Also emits a repo-wide validation report to the job summary (`--all --format=md`), non-blocking.
- **`audit.yml`**: weekly, report-only: full-corpus validation, third-party link-rot check, `dev push --dry-run` drift check against live dev.to, refreshes `INDEX.md` and the README stats block.

`DEVTO_API_KEY` repo secret is required for publishing; passed to devto-cli as the `DEVTO_TOKEN` env var (never a CLI flag, to keep it out of the runner's process table).

## Process

`PROCESS.md` documents the CI pipeline in detail and defines the agent
handoff protocol for Claude Code work in this repo. Two gates in it are
mandatory, not optional:

- Any diff touching `.github/workflows/**` or `scripts/**` must go through
  the read-only `reviewer` agent (`.claude/agents/reviewer.md`) before it's
  committed.
- The `self-improvement` agent (`.claude/agents/self-improvement.md`) must
  run as the last step of any task that went through this protocol, before
  the task is considered done.

## Validation Rules (`scripts/validate_articles.py`)

Blocks on: more than 4 tags, non-lowercase tags, a relative or missing `cover_image`, a missing referenced image, an SVG reference, an `<img>` with a relative `src`, a duplicate dev.to `id` across articles.
