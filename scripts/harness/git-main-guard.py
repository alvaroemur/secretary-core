#!/usr/bin/env python3
"""
PreToolUse hook (Bash) — guard de rama main.

Cuándo dispara:
  - el comando es un `git commit` real, y
  - el repo vive bajo ~/Dev/ (código; los workspaces de notas en ~/Cowork/
    y las rutinas quedan fuera a propósito), y
  - la rama actual es main o master.

Qué hace:
  - NO bloquea. Devuelve permissionDecision="ask" para que Claude Code te
    pregunte y vos decidas: te recuerda abrir una rama de hilo + draft PR.

Un hook no puede saber si el trabajo es "trivial" — eso lo decidís vos al
responder el prompt. Para cambios triviales, confirmás y seguís.
"""
import sys, json, os, re, subprocess


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    if data.get("tool_name") != "Bash":
        sys.exit(0)

    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    # ¿es un git commit real? (evita --help, mensajes que mencionan "commit", etc.)
    if not re.search(r"\bgit\s+commit\b", cmd) or "--help" in cmd:
        sys.exit(0)

    cwd = data.get("cwd") or os.getcwd()
    cwd_abs = os.path.abspath(cwd)

    # solo repos de código bajo ~/Dev/
    dev_root = os.path.join(os.path.expanduser("~"), "Dev") + os.sep
    if not (cwd_abs + os.sep).startswith(dev_root):
        sys.exit(0)

    # rama actual
    try:
        branch = subprocess.check_output(
            ["git", "-C", cwd_abs, "rev-parse", "--abbrev-ref", "HEAD"],
            stderr=subprocess.DEVNULL, text=True,
        ).strip()
    except Exception:
        sys.exit(0)

    if branch not in ("main", "master"):
        sys.exit(0)

    repo = os.path.basename(cwd_abs)
    reason = (
        f"Estás por commitear en `{branch}` de un repo de código en ~/Dev ({repo}). "
        f"Tu convención es una rama por hilo. Si esto NO es trivial, considerá primero:\n"
        f"    git switch -c <scope>/<descripcion>\n"
        f"y luego abrir un draft PR:  gh pr create --draft --fill  "
        f"(te corre CI sin marcar 'listo').\n"
        f"Si es un cambio trivial, confirmá y seguí. ¿Commitear directo en {branch}?"
    )

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


main()
