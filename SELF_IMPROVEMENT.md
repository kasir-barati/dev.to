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

### 2026-08-24 — Building the agent harness (subagents, PROCESS.md, asset-republish fix)

**Task summary:** Built the first version of this repo's Claude Code agent
harness end to end: four project subagents (`content-editor`, `ci-ops`,
`reviewer`, `self-improvement`), `PROCESS.md`, this log, and a real bug fix
(`scripts/bump_asset_versions.py` + `publish.yml` changes) closing a gap
where asset-only edits (e.g. a diagram PNG) never reached dev.to because
devto-cli only republishes on markdown-text diff. Executed via
subagent-driven development: a fresh implementer + independent reviewer per
task, fix-loop rounds when reviews found issues, with `reviewer` as a
mandatory final gate on the whole feature per `PROCESS.md` step 4.

**Challenges/issues/bugs:**
- A factual error about workflow concurrency groups (wrongly claiming all
  four workflows, including `audit.yml` and `validate.yml`, share
  `devto-main-write`) was written during planning and propagated
  unreviewed into three files — the plan doc, `ci-ops.md`, and
  `PROCESS.md` — before Task 2's review caught it by actually checking the
  real `.github/workflows/*.yml` files against the claim. Fixing it required
  two separate fix rounds (Task 1, Task 2) plus manual plan-doc cleanup, and
  even then a fourth location, `AGENTS.md`, was still stale with the same
  wrong claim until the final whole-feature `reviewer` pass caught it —
  `AGENTS.md` wasn't in any task's file list, so no per-task review looked
  at it. Verified as of this entry: `PROCESS.md`, `ci-ops.md`, and
  `AGENTS.md` now all state the correct grouping (`publish.yml` +
  `schedule.yml` share `devto-main-write`; `audit.yml` has its own
  `devto-audit`; `validate.yml` has its own `validate-${{ github.ref }}`).
- `publish.yml`'s asset-collection step originally piped
  `bump_asset_versions.py`'s output through process substitution
  (`mapfile -t x < <(python script ...)`), which hides the script's exit
  code from `set -euo pipefail` — a crash would silently yield `count=0`
  and skip Validate/Publish/Commit with the job reporting green. Caught by
  task-level review, fixed by redirecting to a temp file and mapfile-ing
  from that instead (confirmed still in place: `publish.yml` lines ~85-88
  use `python ... > "$bump_output"` then `mapfile -t bumped_articles <
  "$bump_output"`). This is exactly the "silent failure mode" class
  `reviewer`'s own brief calls out — good sign the brief's wording is
  concrete enough to be actionable, not just aspirational.
- The mandatory whole-feature `reviewer` gate (PROCESS.md step 4) earned
  its keep: it found three genuine, non-overlapping Important-severity
  issues in `bump_asset_versions.py` that **two separate prior per-task
  reviews had each already approved**. Root cause wasn't sloppy reviewing —
  it's that a per-task review is scoped to "does this diff satisfy this
  task's brief," and none of the three issues were in-scope for any single
  task's brief: a silent no-op when no image reference matches a changed
  asset (reintroducing the exact staleness bug the feature exists to fix,
  just quietly), regex substitution running over raw text including fenced
  code blocks (inconsistent with `validate_articles.py`/`check_links.py`,
  which both strip code first), and the stale `AGENTS.md` mentioned above.
  All three fixed and re-reviewed clean, confirmed present in the code read
  for this entry (`_sub_outside_code`/`CODE_RE` in
  `scripts/bump_asset_versions.py`, and the `warning: ... not republished`
  stderr line for the no-match case).
- Neither `reviewer` nor `self-improvement` could be dispatched by their
  own subagent name this session, including for this very entry — the
  harness's custom-agent list loads once at session start, before
  `.claude/agents/*.md` existed. Every dogfooded invocation had to work
  around it by briefing a generic agent with the target persona's literal
  system-prompt text and asking it to self-enforce tool restrictions
  (weaker than the real `tools:` frontmatter enforcement — a generically-
  typed agent retains full tool access even when told not to use it).

**Strengths observed:** independent reviewer instances re-checked concrete
claims (which workflow shares which concurrency group) against the literal
YAML files rather than trusting prior documentation, which is what caught
the concurrency-group error being re-introduced in a second location even
after a first fix landed. The fix-loop pattern (implementer → reviewer →
fix → re-review) worked as designed for both task-level and whole-feature
scope. `reviewer`'s brief explicitly naming "silent failure modes" and
"consistency with the rest of scripts/" as review dimensions produced two
real catches, not just generic commentary.

**Weaknesses observed:** nothing scoped per-task review to whole-repo
consistency (files outside a task's stated file list, like `AGENTS.md`,
were invisible to it) — only the final mandatory gate had that scope. A
documentation claim written once during planning propagated to multiple
files before any review checked it against source of truth; nothing forced
an "check this specific factual claim against the real files" step at
authoring time. The known-gap left in `bump_asset_versions.py`'s code-fence
detection (stray triple-backtick in prose can mis-pair fences; `\`\`\`\``-
wrapped fences and 4-space-indented code aren't excluded) is real and
undefended by any test — there's no test framework in this repo, so it
relies entirely on a future reviewer noticing if the article corpus ever
grows a case that trips it.

**What changed in `PROCESS.md`:** Added a fourth bullet to the "Agent
handoff protocol" section (below) closing the durable gap from the
same-session dispatch-by-name limitation (see next section). No other
`PROCESS.md` change — the concurrency-group text and the asset-republish-fix
section were already correct as of this entry's review, so no rewrite was
needed there.

**What changed in this file's instructions:** none. The existing format
(task summary / challenges / strengths / weaknesses / PROCESS.md change /
own-instructions change) captured everything needed for this entry without
friction; no gap in the retro process itself surfaced.

