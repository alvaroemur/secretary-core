"""Persist material progress to the current daily brief."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

from secretary.config import load_config
from secretary.desk import publish_event

HAPTIC = Path.home() / ".claude" / "scripts" / "sec-haptic.sh"


def post_status(emoji: str, ref: str, note: str, *, state: str = "",
                evidence: str = "", next_step: str = "") -> tuple[int, str]:
    """Publish a signed, deduplicated update without changing the morning report."""
    heading = f"{emoji} {ref}".strip()
    lines = [f"### {heading}", "", f"**Avance:** {note}"]
    for label, value in [("Estado actual", state), ("Evidencia", evidence),
                         ("Siguiente paso / decisión", next_step)]:
        if value.strip():
            lines.append(f"**{label}:** {value}")
    result = publish_event(load_config(), "\n\n".join(lines), "sec-status")
    if result["state"] == "no-brief-today":
        raise RuntimeError(result["reason"])
    issue = int(result["issue"])
    if result["state"] == "published" and HAPTIC.is_file() and os.access(HAPTIC, os.X_OK):
        env = os.environ.copy()
        env["SEC_HAPTIC_SRC"] = "sec-status"
        subprocess.Popen([str(HAPTIC), "detecto"], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, env=env)
    verb = "ya registrado" if result["state"] == "already-published" else "persistido"
    return issue, f"✓ {verb} en brief #{issue}: {heading} — {note}"
