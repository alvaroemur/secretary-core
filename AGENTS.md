# Instrucciones para agentes de secretary-core

Este repo contiene el engine reutilizable. Los datos, políticas y configuración privada pertenecen a la instancia. No commitees rutas personales, emails reales, claves, nombres de clientes ni datasets privados.

## Desarrollo

- Python >=3.11; CLI Typer en `secretary/main.py`. Instala con `pip install -e .` o `uv pip install -e .`.
- El builder de wiki usa solo la biblioteca estándar de Python.
- Node usa ES Modules. Instala el daemon con `npm install --prefix secd`; el motor WhatsApp con `npm install --prefix whatsapp/src`.
- El daemon escucha únicamente en `127.0.0.1:8910` y exige Bearer token, salvo `/health`. Ejecuta con `node secd/server.mjs`.
- CLI: `secretary --help`, `secretary validate`; wiki: `python3 wiki/serve.py`.
- Pruebas: `python -m unittest discover -s tests`; daemon: `npm --prefix secd test`. Ejecuta las apropiadas al cambio.

## Trabajo y entrega

- Trabaja en rama del hilo; nunca commitees código directamente a main. Respeta las instrucciones globales de commits y PRs.
- Scopes existentes: `wiki`, `routines`, `whatsapp`, `mail`, `core`, `docs`, `skills`. Una rama por PR y un hilo por entrega.
- Entrega por PR con problema, comportamiento resultante, verificaciones y bloqueos. No inventes resultados.
- Ante una ambigüedad material, registra una pregunta concreta en un issue `needs-triage`, comprobando duplicados. No hagas suposiciones amplias.

## Contexto portable

- `AGENTS.md` guarda instrucciones estables; el estado transitorio vive en un brief de continuidad del repo.
- Los skills se editan en `skills/` (fuente privada); `skills.example/` contiene sus exports sanitizados. No mantengas una segunda fuente de cierre.
- `wind-down` recoge una vez el contexto y produce un brief único. No inicia otra sesión de reflexión ni inspecciona worktrees ajenos.
- `secretary efficiency` ofrece snapshot y métricas opcionales dentro del CLI; ningún skill requiere un runtime adicional.
- `skills.example/` y `playbooks.example/` son exports sanitizados; conserva la separación público/privado documentada en `cli/README.md`.
