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
- `articles/TIL/`, `articles/assets/<slug>/`: TIL notes and per-article assets (images, `diagrams/*.d2` sources + rendered PNGs). Assets referenced from an article must use `./assets/<slug>/...` relative paths in the repo but resolve to absolute `raw.githubusercontent.com` URLs after `dev push` rewrites them.
- `articles/DRAFT/`, `articles/JA/`: gitignored, local-only (drafts, Japanese translations. You can create new gitignored dirs for other languages the same way). Never reach dev.to or git history.
- `scripts/`: all repo tooling, plain Python (PyYAML + python-dateutil; Pillow only for `gen_cover_image.py`, kept out of `requirements.txt` so the hourly scheduler workflow doesn't pay for that wheel).
- `templates/article-template.md`: starting frontmatter/section skeleton for a new article.

## CI Mechanics -- `.github/workflows/`

Three workflows share the `devto-main-write` concurrency group with `schedule.yml` since all three can push to `main`, and pushes race otherwise:

- **`publish.yml`**: on push to `main` touching `articles/**/*.md` (or manual dispatch with `scope: changed|all`). Diffs the push range to find changed top-level articles, validates them, runs one batched `dev push` (devto-cli throttles internally: 30 updates/30s, 10 creates/30s, don't add per-file loops/sleeps around it), then commits any frontmatter it wrote back, retrying the push up to 3x with rebase-and-retry on conflict.
- **`schedule.yml`**: hourly cron. Runs `publish_scheduler.py`, which flips `published: true` on articles whose scheduled `date` has arrived, and commits (deliberately without `[skip ci]`, this commit is what triggers `publish.yml`).
- **`validate.yml`**: gates PRs and pushes. Diffs against a resolved base revision, then runs `validate_articles.py`, `lint_ratchet.py` (fails only on *new* markdownlint errors relative to base. Old articles predating the linter are grandfathered), and `check_links.py`, scoped to changed files only. Also emits a repo-wide validation report to the job summary (`--all --format=md`), non-blocking.
- **`audit.yml`**: weekly, report-only: full-corpus validation, third-party link-rot check, `dev push --dry-run` drift check against live dev.to, refreshes `INDEX.md` and the README stats block.

`DEVTO_API_KEY` repo secret is required for publishing; passed to devto-cli as the `DEVTO_TOKEN` env var (never a CLI flag, to keep it out of the runner's process table).

## Validation Rules (`scripts/validate_articles.py`)

Blocks on: more than 4 tags, non-lowercase tags, a relative or missing `cover_image`, a missing referenced image, an SVG reference, an `<img>` with a relative `src`, a duplicate dev.to `id` across articles.
