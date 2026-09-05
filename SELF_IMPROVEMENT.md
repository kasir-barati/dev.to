# Self-Improvement

Instructions for the `self-improvement` agent (`.claude/agents/self-improvement.md`):

- Read this file's prior entries before writing a new one — don't repeat
  lessons already captured. And revise it if necessary.
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

### Strength & Weaknesses

- `publish.yml`'s asset-collection step originally piped `bump_asset_versions.py`'s output through process substitution (`mapfile -t x < <(python script ...)`), which hides the script's exit code from `set -euo pipefail` — a crash would silently yield `count=0` and skip Validate/Publish/Commit with the job reporting green. Caught by task-level review, fixed by redirecting to a temp file and mapfile-ing from that instead (confirmed still in place: `publish.yml` lines ~85-88 use `python ... > "$bump_output"` then `mapfile -t bumped_articles < "$bump_output"`). This is exactly the "silent failure mode" class `reviewer`'s own brief calls out — good sign the brief's wording is concrete enough to be actionable, not just aspirational.
- The mandatory whole-feature `reviewer` gate (PROCESS.md step 4) earned its keep: it found three genuine, non-overlapping Important-severity issues in `bump_asset_versions.py` that **two separate prior per-task reviews had each already approved**. Root cause wasn't sloppy reviewing — it's that a per-task review is scoped to "does this diff satisfy this task's brief", and none of the three issues were in-scope for any single task's brief: a silent no-op when no image reference matches a changed asset (reintroducing the exact staleness bug the feature exists to fix, just quietly), regex substitution running over raw text including fenced code blocks (inconsistent with `validate_articles.py`/`check_links.py`, which both strip code first), and the stale `AGENTS.md` mentioned above. All three fixed and re-reviewed clean, confirmed present in the code read for this entry (`_sub_outside_code`/`CODE_RE` in `scripts/bump_asset_versions.py`, and the `warning: ... not republished` stderr line for the no-match case).

### 2026-09-05 — Directory-Based Series (`plan.md` implementation)

Task summary: replace hand-typed `series:` frontmatter with a
directory-based convention (`articles/<series-slug>/<slug>.md`), adding
`scripts/series_dirs.py` and updating every script/workflow that globs
`articles/*.md` to also walk one level of series subdirectories, plus
migrating existing series articles into the new layout. Nothing committed;
left for the user to review.

Challenges/issues/bugs: three `reviewer` passes were needed. Pass 1 caught
two flat-glob misses the initial implementation skipped entirely
(`scripts/publish_scheduler.py` + `schedule.yml` — would have silently
no-op'd scheduled publishing for series articles forever) and one script
written but never wired into `publish.yml` per the plan's own Step 5. Pass
2 caught a doc-consistency miss introduced by the pass-1 fixes (updated
the series rule but left the sibling asset-path rule stale in the same
three files) plus a live-content risk needing verification straight from
`devto-cli`'s own source (not indexed in Context7, so had to be
`npm pack`ed and read directly). Pass 3 caught a `re.sub`
replacement-template injection risk (using a matched string as a
replacement template instead of a lambda — directory names can contain
`\` on Linux, which `re.sub` would interpret as a backslash escape).
Separately, the plan itself asserted `gen_index.py` "needs no change" in
Step 4 — false on direct testing, its glob was flat-only too — but the
plan's own phrasing ("test: if it doesn't, that's the one thing this step
needs to fix") is what licensed catching it instead of taking the
assertion at face value. During the actual file migration (Step 7),
moving an article one directory level deeper broke its own relative asset
references (`./assets/...` needing `../assets/...`); no static review
pass caught this, only re-running `validate_articles.py --all` against
the post-migration tree and reading the new errors did.

Strengths: the mandatory `reviewer` gate again found issues genuinely
outside a per-task-brief's scope (the scheduler miss, the wiring miss),
consistent with the prior entry's finding that this is a structural gap a
single-diff review can't self-correct for. The plan's self-falsifying
phrasing on its riskiest assumption saved it from that assumption going
unchecked.

Weaknesses: the plan otherwise-confident "needs no change" step being
wrong is a reminder that plans, even carefully written ones, encode
untested assumptions as near-certainties. A stale doc-consistency issue
reappeared in the *fix* round for a documentation change already in
flight, not just in the original diff — grepping for all references to a
changed rule up front would have caught it in one pass instead of two.

Changed in `PROCESS.md`: added items 9–12 to the agent handoff protocol —
(9) grep the whole repo for a changed rule's old pattern before calling a
task done, not just the plan-named files; (10) treat "confirm X needs no
change" plan steps as a hypothesis to test via the step's own proposed
check, not a formality; (11) after any file-restructuring task, run the
full-corpus validator against the post-move tree and read its output,
since directory-depth changes can silently break relative references in
ways invisible to diff review; (12) multiple `reviewer` passes on one
diff are normal for larger tasks, not a process failure — keep
re-reviewing until a pass comes back clean.

Changed in this file's instructions: none — the existing format (task
summary / challenges / strengths / weaknesses / what changed) captured
this task's lessons adequately.
