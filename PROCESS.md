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

**Known risk to watch, not yet confirmed:** dev.to may re-host or normalize
`cover_image` URLs on ingest. If devto-cli's equality check (see the
investigation above) ever compares against a dev.to-normalized
`cover_image` rather than the literal string in this repo's frontmatter, a
`?v=` suffix on a cover image could fail to converge and cause the article
to look "changed" (and get re-pushed) on every single run, forever. Body
images don't share this risk — dev.to stores `body_markdown` verbatim, so
those `?v=` bumps are compared byte-for-byte. Watch the first real
cover-image asset change in production for a repeat-push pattern in
`publish.yml`'s "Publish articles" step logs; if it happens, the fix is
likely to stop cache-busting `cover_image` specifically (inline image
cache-busting is unaffected either way).

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
7. **Same-session limitation**: a subagent defined in
   `.claude/agents/*.md` cannot be dispatched by name in the same session
   that created or edited its file — the harness loads the custom-agent
   list once at session start and does not rescan it. If dispatch by name
   fails for an agent you know exists on disk, don't treat that as the
   agent missing: brief a generic agent with the target persona's file
   contents verbatim (name, description, tools restriction, and full body)
   and have it self-enforce the tool restriction. This is weaker than real
   enforcement — a generically-typed agent keeps full tool access even
   when told not to use some of it — so scope the workaround prompt
   narrowly and call out anywhere the task depends on the restriction
   actually holding. A fresh session picks up the new agent file normally;
   this workaround is only needed within the session that authored it.
