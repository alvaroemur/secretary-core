# Voice bridge scout: n5 review decisions (scope record, draft)

Parent plan: `docs/plans/voice-bridge-scout.md` (graph unchanged by this record).
Status: round 1 answered and confirmed by the owner; applied in commit on core/voice-bridge-context.

## Goal

Decide what the first real summary (13 items, ~1000 chars, generated 2026-11-19) must change before node n4 is considered final. Only the producer is in scope.

## Findings (first real summary)

- 5 of 13 items are sessions, and 4 of those restate this very workstream or a one-off request ("se pidió arrancar n4"). Low value for a voice assistant.
- 5 commitments are useful but have no deadline and repeat the prefix "Pendiente en".
- 3 briefs are useful; one is 20 days old.
- The bridge already gives Gemini a note listing its own sessions (server.js:569), so session lines add little there.

## Decision tree

```text
N5-0 ✅ goal: tune the producer from the first real summary
├─ SES-1 ✅ one line per active project, max 3, work topic not last order
│  └─ SES-2 ✅ skip sessions whose last request is under 20 chars (deterministic)
├─ CMP-1 ✅ "<project>: <action>", due date in `date`, deadline first then newest, max 5
├─ BRF-1 ✅ skip briefs older than 21 days, max 3
└─ ORD-1 ✅ order: commitments, briefs, sessions
```

## Log

| round | event |
|-------|-------|
| 1 | owner reviewed the summary; questions SES-1, SES-2, CMP-1, BRF-1, ORD-1 opened |
| 1 | owner accepted all recommendations (SES-1: 1, SES-2: yes, CMP-1: yes, BRF-1: yes, ORD-1: commitments, briefs, sessions); frontier empty |
