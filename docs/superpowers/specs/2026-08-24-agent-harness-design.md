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
- Document the asset-trigger gap as a known limitation / future work item —
  explicitly *not* implemented in this pass (confirmed with user).
- Define a repeatable handoff protocol for Claude Code work in this repo:
  which subagent handles what, when a read-only review gate is mandatory,
  and a mandatory close-out step that captures lessons learned.
- Ship four project-level subagents with tool access and models scoped to
  their risk/complexity.

## Non-goals

- Modifying `publish.yml` (or any workflow) to actually trigger on asset
  changes. Documented only.
- Peer-to-peer subagent handoff (subagents invoking subagents). All handoff
  is orchestrator-mediated.
- Fine-grained read-only Bash for the reviewer agent. It gets no Bash at all.

## Design

### Files

- `PROCESS.md` (repo root)
- `SELF_IMPROVEMENT.md` (repo root)
- `.claude/agents/content-editor.md`
- `.claude/agents/ci-ops.md`
- `.claude/agents/reviewer.md`
- `.claude/agents/self-improvement.md`

### PROCESS.md contents

1. **Current pipeline** — accurate description of `validate.yml` (PR/push
   gate: `validate_articles.py`, `lint_ratchet.py`, `check_links.py`, scoped
   to changed files), `publish.yml` (push-to-main on `articles/**/*.md`,
   diffs the push range, validates, one batched `dev push`, writes back
   frontmatter via a retrying commit), `schedule.yml` (hourly cron, flips
   `published: true` via `publish_scheduler.py`, commits without
   `[skip ci]` to trigger `publish.yml`), `audit.yml` (weekly, report-only:
   full validation, link-rot, dry-run drift check, refreshes `INDEX.md`).
2. **Known limitation** — the asset-trigger gap described above, labeled
   clearly as *not implemented*, with a one-paragraph sketch of what closing
   it would require (trigger path `articles/assets/**`, map changed asset
   dirs back to the article(s) referencing them, since diffing by top-level
   `articles/*.md` alone won't catch it) so a future task can pick it up
   without re-deriving the problem.
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

This is documentation + subagent config, not application code. Verification
is: each `.claude/agents/*.md` has valid frontmatter Claude Code will parse
(name/description/tools/model), `PROCESS.md` and `SELF_IMPROVEMENT.md` read
correctly and don't contradict AGENTS.md, and the harness gets exercised at
least once — the `self-improvement` agent runs for real as the last step of
implementing this very spec, producing the seed log entry.
