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
