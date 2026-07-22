# Agent Discipline

Agents operating within `secretary-core` (e.g., Claude Code, routines, or subagents) must adhere to the following discipline:

## Workflow
- **Branching**: Agents must work on thread branches, never directly on `main`.
- **Delivery**: When work is completed or requires review, agents must deliver a PR and include a detailed report or `walkthrough.md`.
- **Blocking / Doubts**: If an agent encounters ambiguity, missing information, or is blocked, they must NOT guess or make sweeping assumptions. Instead, they should push doubts to `needs-triage` issues, ensuring deduplication and allowing for periodic triage by the human operator.
- **Artifacts**: Use markdown artifacts to present structured plans, walkthroughs, and checklists to the human operator.
