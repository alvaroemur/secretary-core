# Tidy-up condicional v1

El evaluador lee el repo habilitado en `dispatch.executor.repos`. No mueve archivos, abre PRs, publica comentarios ni cambia permisos. `eligible-for-pr` permite preparar una propuesta según el contrato aprobado, no mergear ni modificar el checkout activo. Las operaciones `--claim` son explícitas y solo mantienen un reclamo local compartido por repo.

## Solicitud

Issue abierto en el repo dueño, etiqueta `tag:tidyup`, exactamente un bloque JSON:

```html
<!-- tidy:request {"version":1,"action":"reorganize","targets":[{"from":"docs/old","to":"docs/new"}],"dependencies":["README.md"],"conditions":[]} -->
```

`dependencies` enumera índices, enlaces y configuración afectados. El evaluador añade archivos versionados que referencian el origen. Referencias por nombre sin ruta delimitada bloquean hasta aclarar el alcance. No certifica dependencias externas, referencias en binarios ni sentido semántico: si la revisión encuentra una dependencia incierta, se publica una propuesta sin preparar movimientos. No confundir un resultado técnico con permiso de ampliar el objetivo.

Condiciones: `{"type":"issue-completed","repo":"owner/repo","number":12}` exige `CLOSED` y `stateReason=COMPLETED`; `{"type":"not-before","at":"2026-11-01T09:00:00Z"}` exige fecha con zona. Condiciones de otros repos requieren que también estén habilitados. Falso: `waiting`; error o evidencia ausente: `blocked`. `archive` y `delete` siempre producen `proposal-only`: el evaluador no demuestra preservación de backups ni autoriza esas acciones.

## Consultas

```bash
python -m secretary.tidy --queue
python -m secretary.tidy --repo owner/repo --issue 12
python -m secretary.tidy --repo owner/repo --request request.json
```

La consulta devuelve alcance, bloqueos con procedencia, condiciones, estado, fingerprint del contrato, hash de evidencia y `report_key` estable para cambios materiales. La etiqueta descubre; no autoriza efectos. Nunca se ejecuta texto libre ni un comando del issue.

## Trabajo y frescura

Se inspeccionan todos los worktrees: cambios staged/unstaged/untracked, commits no integrados respecto a origin/main y stashes compartidos, incluido su contenido untracked. Los PRs incluyen nombres antiguos de archivos renombrados. Un PR truncado, worktree inaccesible o fallo de API bloquean. Se compara el SHA de origin/main con GitHub main; si difiere, actualizar metadatos y volver a evaluar. El evaluador no hace fetch. V1 requiere rama main remota.

Sin cobertura del harness, todos los worktrees deben estar limpios y no puede haber PR abierto. Los pendientes identificados se comparan por rutas. Un checkout estacionado no bloquea por existir.

`--activity activity.json` admite evidencia de un colector confiable de sesiones:

```json
{"captured_at":"2026-11-01T09:00:00Z","coverage":"known","source":"trusted-collector/run-id","active":[{"ref":"session-id","paths":["other-project"]}]}
```

Git y actividad caducan a los cinco minutos. No fabricar este archivo ni deducir `known` de una lista vacía. El CLI no autentica al proveedor del archivo; el operador debe conservar su procedencia real. Sin integración confiable, omitir `--activity` y usar el criterio conservador aprobado. Actividad sin rutas y cobertura inválida bloquean.

## Preparación por PR

1. Evaluar y revisar alcance, referencias y método de ordenamiento vigente.
2. Reclamar el repo con `--claim acquire --fingerprint <fingerprint>`. Guardar el token del intento. Un reclamo existente bloquea; nunca se toma por timeout.
3. Volver a evaluar con evidencia fresca; contrato y alcance deben coincidir. Una condición, cuerpo o autorización que cambie invalida el intento.
4. Preparar un worktree propio desde la base remota comprobada. Mover solo archivos versionados de esa copia aislada, actualizar referencias y validar. No mover archivos del checkout activo ni ignorados/untracked. Si el plan necesita esos archivos o cambiar permisos, publicar propuesta sin efectos.
5. Entregar un PR enlazado al issue, comprobar el conjunto de rutas real y registrar resultado. No reutilizar el permiso genérico de preparación para borrar, archivar backups, mutar Drive, cambiar reglas de autoridad ni desplegar.
6. Liberar con `--claim release --token <token>`, también ante fallo controlado. Un fallo incierto conserva el reclamo hasta comprobar el estado anterior. Nunca liberar un token ajeno ni ejecutar un intento que perdió el reclamo.

Reclamos: `~/.local/state/secretary/tidy/claims`, compartidos entre worktrees; `SECRETARY_TIDY_CLAIMS` permite un directorio común explícito. No compartir repos entre máquinas como si este bloqueo local fuera distribuido. La v1 opera en un solo host. El registro de evidencia/resultados se entrega por PR en la instancia, no por escritura directa a main. Un PR no demuestra que el merge ocurrió ni que una limpieza física terminó.

Antes de repetir, consultar PRs y comentarios de la solicitud. `report_key` sin cambios no genera otro aviso. Publicar el cambio material firmado y enlazarlo desde el brief del día; si falta, conservar el evento en el issue. No crear PRs vacíos de diagnóstico.

## Validación

`python -m unittest discover -s tests -p test_tidy.py` cubre rutas, referencias, worktrees reales, stashes, commits, PRs renombrados, actividad conocida/desconocida, condiciones, evidencia vencida y reclamos. El piloto operativo solo evalúa y registra; no activa el scheduler ni prepara movimientos.
