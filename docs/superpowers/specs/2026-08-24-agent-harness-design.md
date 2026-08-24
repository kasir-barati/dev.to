# Agent harness for dev.to content repo

Date: 2026-08-24
Status: approved for implementation

## Problem

This repo has a CI pipeline (`validate.yml`, `publish.yml`, `schedule.yml`,
`audit.yml`) but no documented protocol for how Claude Code should be used to
do the actual work in it — content edits vs. CI/script edits carry very
different risk profiles and currently get no differentiated handling, there's
no read-only review gate before a CI/script change ships, and there's no
mechanism for carrying lessons from one task to the next. Separately, the
current pipeline has an undocumented gap: `publish.yml` only triggers on
`articles/**/*.md`, so an asset-only change (e.g. a diagram PNG under
`articles/assets/<slug>/`) never triggers a republish, even though asset URLs
(`cover_image`, inline images) are rewritten to `raw.githubusercontent.com`
URLs pinned to `refs/heads/main` (unpinned to a SHA) — so the *URL* doesn't
change on an asset edit, but the content behind it does, and dev.to's cached
copy may not pick that up without some kind of republish signal.

## Goals

- Document the existing CI pipeline accurately, as it behaves today.
- Close the asset-trigger gap for real: an asset-only change under
  `articles/assets/<slug>/` must result in dev.to actually receiving fresh
  content, not just a workflow run that no-ops.
- Define a repeatable handoff protocol for Claude Code work in this repo:
  which subagent handles what, when a read-only review gate is mandatory,
  and a mandatory close-out step that captures lessons learned.
- Ship four project-level subagents with tool access and models scoped to
  their risk/complexity.

## Non-goals

- Peer-to-peer subagent handoff (subagents invoking subagents). All handoff
  is orchestrator-mediated.
- Fine-grained read-only Bash for the reviewer agent. It gets no Bash at all.
- Any manual step for the article author. Cache-busting is fully automated;
  the author never writes a `?v=` token by hand, same spirit as never having
  to hand-write the `raw.githubusercontent.com` rewrite.

## Investigation: why a trigger alone doesn't work

Traced `@sinedied/devto-cli`'s source (`checkIfArticleNeedsUpdate` /
`areArticlesEqual` in `article.ts`) to confirm the actual failure mode.
Before calling the dev.to update API, devto-cli does a strict equality check
between the local article (frontmatter + body, `date` excluded) and the
remote one. If the markdown text is byte-identical to what's already
published — which it is when only an asset file changed — devto-cli silently
skips the API call. So merely adding `articles/assets/**` to `publish.yml`'s
trigger paths would run the workflow for nothing: `dev push` would see no
diff and do nothing.

Also confirmed from `util.ts` (`updateRelativeImageUrls` / `getImageUrls`):
relative image paths are rewritten to
`raw.githubusercontent.com/{owner}/{repo}/{branch}/...` (branch ref, not a
commit SHA — matches AGENTS.md), and **any existing query string on the
image path is preserved verbatim** through that rewrite. `cover_image` is
different: since it's already an absolute URL in this repo's frontmatter,
devto-cli's `!isUrl(...)` guard skips rewriting it entirely — whatever is on
disk is what's used.

This makes a cache-busting query token the actual fix: appending/bumping
`?v=<token>` on an image reference is (a) a real content change, so
devto-cli's equality check trips and it actually calls the update API, and
(b) a new URL, so dev.to (and any downstream cache) fetches fresh content
instead of serving a stale cached copy of the old URL.

## Design

### Files

- `PROCESS.md` (repo root)
- `SELF_IMPROVEMENT.md` (repo root)
- `.claude/agents/content-editor.md`
- `.claude/agents/ci-ops.md`
- `.claude/agents/reviewer.md`
- `.claude/agents/self-improvement.md`
- `scripts/bump_asset_versions.py` (new)
- `.github/workflows/publish.yml` (modified)

### PROCESS.md contents

1. **Current pipeline** — accurate description of `validate.yml` (PR/push
   gate: `validate_articles.py`, `lint_ratchet.py`, `check_links.py`, scoped
   to changed files), `publish.yml` (push-to-main on `articles/**/*.md`,
   diffs the push range, validates, one batched `dev push`, writes back
   frontmatter via a retrying commit), `schedule.yml` (hourly cron, flips
   `published: true` via `publish_scheduler.py`, commits without
   `[skip ci]` to trigger `publish.yml`), `audit.yml` (weekly, report-only:
   full validation, link-rot, dry-run drift check, refreshes `INDEX.md`).
2. **Asset republish fix** — describes the implemented mechanism (below):
   `publish.yml` now also triggers on `articles/assets/**`, maps changed
   asset dirs back to their owning article, and runs
   `scripts/bump_asset_versions.py` to cache-bust the affected image
   reference(s) before validate/push, fully automated — the author never
   writes a `?v=` token by hand.
3. **Agent handoff protocol**:
   - Orchestrator (the main Claude Code session) classifies an incoming task
     as content work or CI/script work.
   - Content work → delegate to `content-editor`.
   - CI/script work (anything touching `.github/workflows/**` or
     `scripts/**`) → delegate to `ci-ops`.
   - Any diff touching `.github/workflows/**` or `scripts/**` — regardless
     of which agent produced it — **must** go to `reviewer` before it is
     committed. Content-only changes to `articles/**/*.md` skip this gate.
   - Reviewer findings loop back to `ci-ops` (or the orchestrator) for
     fixes; re-review is not required to be re-triggered automatically —
     orchestrator judgment applies, same as any code review loop.
   - **Last step, always, before the orchestrator ends the task**: invoke
     `self-improvement`. This is not optional and is not skipped for small
     tasks.

### SELF_IMPROVEMENT.md contents

- Short instructions block at the top: read prior entries for context before
  writing a new one; append (don't rewrite) a new dated entry per task;
  revise `PROCESS.md` when a *durable* process gap surfaced (not one-off
  noise); revise this file's own instructions block when the retro process
  itself needs to change.
- An append-only dated log below, each entry covering: task summary,
  challenges/issues/bugs encountered, strengths observed, weaknesses
  observed, what (if anything) changed in `PROCESS.md`, what (if anything)
  changed in this file's instructions.
- Seeded with a first real entry: the creation of this harness itself,
  written by the `self-improvement` agent as the final step of this task.

### Asset republish fix (implementation)

**`publish.yml` trigger**: add `articles/assets/**` alongside the existing
`articles/**/*.md` in `on.push.paths`.

**`scripts/bump_asset_versions.py`** (new, follows the existing scripts'
style — argparse, PyYAML frontmatter, no test suite in this repo to match):

- Invoked with the list of changed asset file paths for the push range
  (computed the same way `publish.yml` already computes changed articles:
  `git diff --name-only --diff-filter=d "$base" "$AFTER" -- ':(glob)articles/assets/**'`).
- For each changed asset path `articles/assets/<slug>/...`, the owning
  article is `articles/<slug>.md` (confirmed 1:1 today: every
  `articles/assets/<slug>/` dir has a matching `articles/<slug>.md`). If no
  matching article file exists, skip with a warning — don't fail the run.
- Computes a version token per asset: short git blob hash of the asset file
  at the new commit (`git rev-parse --short HEAD:<path>`) — deterministic,
  so reverting an asset to prior content reverts the token too, and no
  spurious churn if the byte content didn't actually change.
- Within the owning article's content, finds image references whose path
  matches the changed asset's filename — reusing the same match style as
  `validate_articles.py`'s `MD_IMAGE_RE` / `HTML_IMAGE_RE` for markdown and
  HTML image syntax, plus the `cover_image` frontmatter field if it points
  at the changed asset — and rewrites the query string to `?v=<token>`
  (replacing any prior `?v=` if present, appending if not). If the changed
  asset isn't referenced anywhere in the article (e.g. an unused file, or a
  `.d2` source whose rendered `.png` didn't change), no-op for that asset —
  do not touch the file.
- Prints the set of article paths it actually modified, so `publish.yml`
  can merge them into the existing list of articles to validate/push.

**`publish.yml` "Collect articles to push" step**: after computing the
existing changed-`.md` list, additionally diff `articles/assets/**` for the
same push range, run `bump_asset_versions.py` on that list (only for the
default push-triggered path — `workflow_dispatch` with `scope: all` already
re-pushes everything and doesn't need this diff signal), and union the
articles it reports into the existing `$list` before the validate/push
steps run — so `dev push` sees the bumped query string as part of its
normal diff.

**Commit-back step**: no new commit machinery needed. The existing
"Commit and push metadata written back by devto-cli" step already does
`git add -- ':(glob)articles/*.md'` and commits whatever changed — since
`bump_asset_versions.py` runs *before* validate/push in the same job, its
edits are sitting in the working tree by the time that step runs and get
picked up together with any devto-cli frontmatter writeback, in one commit.

### Subagents

| Agent | Role | Tools | Model |
|---|---|---|---|
| `content-editor` | Scaffold/edit articles per AGENTS.md rules (template, frontmatter, tags, series, cover_image, asset re-pathing) | Read, Write, Edit, Grep, Glob, Bash | haiku |
| `ci-ops` | Edit `.github/workflows/**` and `scripts/**` | Read, Write, Edit, Grep, Glob, Bash | sonnet |
| `reviewer` | Read-only audit of Actions/scripts diffs; cannot change anything | Read, Grep, Glob | opus |
| `self-improvement` | Mandatory close-out: retro + log entry + PROCESS.md revision when warranted | Read, Edit, Grep, Glob (prompt-scoped to only touch PROCESS.md / SELF_IMPROVEMENT.md) | sonnet |

Reviewer's tool restriction excludes Write/Edit/NotebookEdit/Bash entirely
(not just discouraged in its prompt) because Bash can write files via shell
redirection — an allowlist is the only mechanism that actually guarantees
read-only behavior. Tradeoff, stated in the reviewer's own file: it cannot
run `actionlint`/`shellcheck`/tests, only static review.

## Testing / verification

- Docs/config: each `.claude/agents/*.md` has valid frontmatter Claude Code
  will parse (name/description/tools/model), `PROCESS.md` and
  `SELF_IMPROVEMENT.md` read correctly and don't contradict AGENTS.md.
- `scripts/bump_asset_versions.py`: exercise it directly against a real
  changed asset path in this repo (no test suite exists elsewhere in the
  repo to match — a manual/CI-style run is the verification, consistent
  with `validate_articles.py` etc.). Confirm it correctly rewrites a
  matching image ref, leaves non-matching articles untouched, and no-ops
  cleanly when the asset isn't referenced.
- `publish.yml`: cannot be exercised end-to-end without pushing to `main`
  and hitting the real dev.to API — validate via reading the workflow logic
  carefully (this is exactly what the `reviewer` gate is for) rather than a
  live run as part of this task.
- The harness gets exercised at least once for real: the `self-improvement`
  agent runs as the last step of implementing this very spec, producing the
  seed log entry, and the `reviewer` agent runs against the `publish.yml` /
  `bump_asset_versions.py` diff before it's committed.
