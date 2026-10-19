# Adaptación de Codex

Fuente revisable de instrucciones específicas de Codex. No modifica los skills compartidos ni instala scripts de Claude Code.

- [Fragmento de instrucciones](AGENTS.fragment.md)
- [Diagnóstico, instalación y regresión](walkthrough.md)

El instalador requiere un destino explícito y preserva las instrucciones fuera de su bloque:

```sh
python3 scripts/codex/install_rules.py --target /ruta/de/codex/AGENTS.md
```
