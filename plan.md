# Plan: Directory-Based Series

## Goal

Series membership is currently declared by hand-typing a `series:` frontmatter key that must exactly match an existing name in `INDEX.md` (a near-miss creates a duplicate series on dev.to). Replace that with a directory-based convention:

- An article inside a subdirectory of `articles/` (one level deep) gets its `series` frontmatter derived automatically from the sanitized directory name.
- An article directly in `articles/` (today's flat layout) must **not** have a `series` key — if one is present, validation fails. Series membership is enforced structurally, not by convention.

No external dependency needs forking — `publish.yml`, `validate.yml`, and all the scripts under `scripts/` are already ours.

## Execution constraint

Every step below is scoped to editing files in the working tree and running
local read-only or scratch-copy commands. **No step creates a branch,
commits, or pushes — not to `main`, not to a feature branch, not to a temp
branch.** `git add`/`git commit`/`git push`/`git checkout -b` are not part of
any step's execution; committing and pushing this work, at whatever
granularity, is done by the user, on their own schedule, after reviewing
each diff.

## Design Decisions

1. **Sanitization rule.** Directory name → series string: `pipeline-pattern` → `Pipeline Pattern` (kebab-case → Title Case)
2. **Reserved directory names.** `TIL/`, `assets/`, `DRAFT/`, `JA/` (and any future gitignored language dirs) must be excluded from "this is a series directory" detection — they already have distinct meaning.
3. **Nesting depth.** Enforce exactly one level (`articles/<dir>/<slug>.md`). Reject anything deeper as a validation error rather than silently ignoring it.
4. **Migrating existing series.** Articles that already carry a hand-typed `series:` today (check `INDEX.md` for current series names) need a one-time move into a matching directory, or the sanitization needs to be picked so it reproduces the existing series strings exactly. Otherwise the migration itself creates duplicate series on dev.to.
5. **`INDEX.md` reconciliation.** `INDEX.md` becomes fully generated from directory structure going forward.

## Glob pattern (used throughout the steps below)

A file counts as a "series article" when it matches `articles/<dir>/*.md` where `<dir>` ∉ `{TIL, assets, DRAFT, JA}` (and any future reserved/gitignored dir), exactly one level deep. Anything deeper (e.g. `articles/assets/<slug>/diagrams/**`) never matches. `DRAFT/`/`JA/` are gitignored already, so they never reach git/CI regardless — the exclusion just protects the glob's intent if that ever changes.

## Implementation steps

Each step below is a self-contained diff with its own test — keep them as separate diffs (the user decides how to batch them into commits/PRs, since committing/pushing is theirs to do, not part of these steps). Steps 1–4 touch only `scripts/` and can be built and tested entirely locally, with no interaction with dev.to or git history. Steps 5–6 touch the workflows and need the `reviewer` agent gate before the user commits them. Step 7 is the data migration, kept separate so a bad sanitization choice doesn't get baked into a workflow change. `self-improvement` runs once at the very end of the whole effort, not per-step.

### Step 1 — Sanitization function (pure, no wiring)

Add a `sanitize_series_name(dirname: str) -> str` function (new module or top of `scripts/apply_series_from_dir.py`) implementing kebab-case → Title
Case, e.g. `pipeline-pattern` → `Pipeline Pattern`.

**Test:** run it directly against every existing series directory name you plan to migrate to (Step 7) and confirm the output string matches the existing `series:` value in `INDEX.md` byte-for-byte. This is the step that catches a bad sanitization choice before anything downstream depends on it.

### Step 2 — `scripts/apply_series_from_dir.py`

- Input: list of article paths (same CLI shape as other scripts in `scripts/`, e.g. `validate_articles.py`).
- For each path:
  - Directly under `articles/` → assert no `series` key; error if present.
  - One level under `articles/<dir>/`, `<dir>` not reserved → compute `sanitize_series_name(dir)`, write/overwrite `series:` in frontmatter. Error if an existing `series` value conflicts with the derived one (catches manual drift from the directory name).
  - Anything nested deeper than one level → error.

**Test:** run the script by hand against a scratch copy of `articles/` (copy a couple of real files into a temp dir under a fake series directory and a fake flat one), inspect the rewritten frontmatter, confirm both the happy path and both error cases (flat+series-present, nested+series-conflict) behave correctly. No CI wiring yet — plain `python scripts/apply_series_from_dir.py <paths>` on your machine.

### Step 3 — `scripts/validate_articles.py` enforcement rule

Add the same two error conditions Step 2 checks (flat article with `series` present; nested article with `series` missing or not matching its directory) as validation findings, independent of whether Step 2 has run — validation must catch a hand-edited frontmatter that skipped the apply step.

**Test:** `python scripts/validate_articles.py <path>` against hand-crafted fixture files (one flat+series, one nested+mismatched, one nested+correct, one flat+no-series) and confirm exit codes / error messages are right. This step doesn't require Step 2 to be merged first, since it operates on frontmatter that's already correct or already wrong.

### Step 4 — Confirm `gen_index.py` needs no change

`scripts/gen_index.py` already groups articles `by_series` off the frontmatter `series` field (`gen_index.py:132-135`) — once Step 2 has written that field, `INDEX.md` generation is automatically directory-driven with no code change.

**Test:** run `python scripts/gen_index.py` against the scratch `articles/` copy from Step 2 and confirm the generated series grouping matches the directory layout. If it doesn't, that's the one thing this step needs to fix — otherwise this step is verification-only, not a code change.

### Step 5 — Wire `apply_series_from_dir.py` into `publish.yml` & Glob changes in `publish.yml` and `validate.yml`

Add it as a step before "Validate articles", running against the same collected file list.

Update the three hardcoded `':(glob)articles/*.md'` call sites to also match one-level-deep series directories (pattern defined above):

1. `publish.yml` → "Collect articles to push" diff step.
2. `publish.yml` → "Commit and push metadata written back by devto-cli" step's `git add`.
3. `validate.yml` → changed-file scoping for PR/push gating.

**Test:** add a fake nested article (`articles/test-series/foo.md`) and run `BASE=main make validate-changed` locally to confirm it's picked up.

### Step 6 — Other tooling with the same flat-glob assumption

Check and update if needed:

- `scripts/lint_ratchet.py`
- `scripts/check_links.py`
- `scripts/bump_asset_versions.py`
- `.pre-commit-config.yaml` hook scope
- `audit.yml` full-corpus scan + README stats regeneration

**Test:** for each, run its existing invocation (`make` target or direct script call) against the scratch nested article from Step 5 and confirm it is included/handled the same way a flat article would be.

### Step 7 — Migrate existing series articles into directories

Move each article currently carrying a hand-typed `series:` into `articles/<sanitized-dirname>/`, choosing the directory name so `sanitize_series_name()` reproduces the existing series string exactly (verified already in Step 1). Kept as its own commit/PR, separate from the pipeline change, so a migration mistake doesn't get entangled with a workflow change.

**Test:** after moving, run `python scripts/validate_articles.py --all` and `python scripts/gen_index.py` and confirm `INDEX.md` output is byte-identical to before the migration (same series groupings, same article lists) — the directory move should be invisible to readers.

## Rollout order and gates

1. Steps 1–4 (local-only, `scripts/` changes) can be done and tested
   independently of each other and of the workflow changes, working
   directly in the checked-out tree — no branch or commit needed to test
   them.
2. Steps 5–6 touch `.github/workflows/**` and `scripts/**` — each of their
   diffs must go through the `reviewer` agent (read-only static review, no
   git action of its own) before the user commits and pushes it, per
   `PROCESS.md`.
3. Step 7 (data migration) happens last, once 1–6 are in place, and is
   validated locally (`validate_articles.py --all`, `gen_index.py` diff)
   before the user commits and pushes it — this repo's `publish.yml` pushes
   live to dev.to on a push to `main`, so nothing here should reach `main`
   except by the user's own deliberate commit/push.
4. Run the `self-improvement` agent once, as the last step of the whole
   effort, per `PROCESS.md` — it only edits `SELF_IMPROVEMENT.md`/
   `PROCESS.md`, no git action.

## Explicitly out of scope for this change

- No forking of any external GitHub Action — everything lives in this repo.
- Not touching `DRAFT/`/`JA/` handling — they stay gitignored and untouched
  by series logic.
