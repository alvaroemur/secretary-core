# CLAUDE.md — Developer Guidelines

Guidelines and commands for developing in `secretary-core`.

## Commands

### Setup & Install
- Install Python CLI (Editable mode): `pip install -e .` or `uv pip install -e .`
- Install Node.js Daemon dependencies: `npm install --prefix secd`
- Install WhatsApp engine dependencies: `npm install --prefix whatsapp/src`

### Run Commands
- Run CLI app: `secretary --help`
- Run local daemon: `node secd/server.mjs` (listens on `http://127.0.0.1:8910`)
- Serve local wiki: `python3 wiki/serve.py`

### Test Commands
- Run daemon tests: `npm --prefix secd test`
- Verify CLI paths: `secretary paths`
- Run config validation: `secretary validate`

---

## Code Guidelines

### Python (CLI & Wiki)
- Use **Python >= 3.11**.
- CLI commands are defined using `typer` in `secretary/main.py`.
- Static site builder (`wiki/build/build.py`) must have **zero external dependencies** (standard library only).
- Keep code clean, type-annotated, and well-structured.

### Node.js (secd Daemon & WhatsApp Engine)
- Written in modern ES Modules (`.mjs` or `"type": "module"`).
- The daemon (`secd`) is loopback-only (`127.0.0.1`) and requires `Authorization: Bearer <token>` for endpoints (except `/health`).
- Keep daemon dependencies minimal.

### Git & Workflow
- **Branching**: Do NOT commit directly to `main`. Always work on thread feature branches (`feat/*`, `fix/*`).
- **Commits**: Follow Conventional Commits format: `<type>(<scope>): <message>`.
  - Valid scopes: `wiki`, `routines`, `whatsapp`, `mail`, `core`, `docs`, `skills`.
- **Anonymity**: The core repository (`secretary-core`) is public-ready. Do NOT commit private paths, personal emails, keys, or business/personal names. Use `.example` files and keep custom configs gitignored.
