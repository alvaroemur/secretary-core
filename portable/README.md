# Cierre y comprobaciones portables

`portable/skills/` es la fuente canónica de los cuatro skills compartidos. Las copias instaladas son destinos generados, no fuentes de edición. `portable_deploy` permite revisar destinos antes de aplicar y conserva backups por contenido. El exportador de ejemplos no modifica esta carpeta.

```bash
python -m secretary.portable_deploy --source <core> --target <skills-del-harness> --runtime <runtime>
# Añadir --apply después de revisar; repetir --target para otros harnesses.
python -m secretary.efficiency --help
# Con el core actualizado:
secretary efficiency --help
```

El runtime independiente usa el Python del CLI instalado (>=3.11) y su módulo de configuración. No usa el Python del sistema ni llama modelos. Las reglas privadas de la instancia y los pilotos se documentan fuera del repo público.

## Interfaces

- `close-snapshot --repo --session-id --path ... --decision ... --next ... --output`: captura solo archivos explícitos, rama y commit. El orquestador agrega resultado, bloqueos y PR a `close_context`. Un cierre sin archivos no toma el último commit como sustituto.
- `preflight <routine> --ticket <json>`: 0 = trabajo, 10 = no-op, 20 = error. El ticket contiene id de tarea, inventario por hash, día y resultado; no guarda cuerpos de correo.
- `complete --ticket --outcome completed|partial|error --reason`: solo completed confirma el inventario inicial. No consulta ni consume entradas posteriores.
- `import-usage --source <archivo-o-carpeta> ... --output <jsonl>`: reconstrucción atómica y deduplicada de transcripts locales de Claude y Codex. El formato Cursor sin usage verificable permanece desconocido; no se inventan cifras.
- `report --ledger <jsonl> --start YYYY-MM-DD --end YYYY-MM-DD`: fin exclusivo, totales por tarea y contadores de valores desconocidos. Reportar por separado consumo importado y resultados de gates para evitar doble conteo.

Los filtros son conservadores. Correo incluye seguimientos y drafts; wiki conserva mantenimiento diario. Una fuente ausente o una consulta fallida termina como error, nunca como falta de trabajo. No cambia autorizaciones, modelos, scheduler ni política de envíos/merge.

## Validación

```bash
python -m unittest discover -s tests -p test_efficiency.py -v
```

Para compatibilidad real, usar un repo de prueba con AGENTS.md raíz y subdirectorio, y un brief con decisión y siguiente acción. Pedir a cada harness los dos marcadores y la siguiente acción, en modo de lectura. Autenticación fallida es bloqueo, no éxito. No eliminar instrucciones antiguas hasta que la prueba pase.
