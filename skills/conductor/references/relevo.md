# conductor — cross-harness handoff

Use this contract when changing sessions or harnesses. `handover` owns the
canonical payload and `jump` owns the paste-ready continuation block. Conductor
coordinates them; it does not create a second format or launch a session.

## Canonical payload

- Keep one `.briefs/YYYY-MM-DD-HHMM-<slug>.md` file. Reuse the active brief.
- The complete UTF-8 file, including frontmatter, must not exceed 4096 bytes.
- Keep metadata, decisions, pending work, blockers, and a verification-first check.
- Exclude transcripts, credentials, secrets, and private data.
- Ask for approval before writing the brief unless the enclosing workflow already
  obtained approval.

Use `handover` to produce and validate the compact schema. Do not copy the schema
here; `skills/handover/SKILL.md` is the single source of truth.

## Paste-ready continuation

Use `jump` to emit one fenced `text` block for the requested target: Claude Code,
Codex, or Cursor. The block must start by checking whether the work is already
done, cite the canonical brief, include a completion criterion, and be ready to
paste without edits. It references the brief instead of duplicating its contents.

Conductor proposes the block. Launching a session remains an explicit owner action.
