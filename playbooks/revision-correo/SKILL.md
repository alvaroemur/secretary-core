---
name: revision-correo
description: Run the complete revision-correo procedure on every scheduled invocation, without an inventory preflight.
---

# revision-correo

Read the instance AGENTS.md and `procedure.md` beside this file, then run the complete procedure.

Do not use `secretary-portable`, an inventory checkpoint or a no-op filter to skip it.
Keep the existing procedure's authorization boundaries, idempotency checks and required deliveries.
Do not change the scheduler, model or harness. Report partial completion and failures honestly.
