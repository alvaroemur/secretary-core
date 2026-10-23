<!-- agent-generated:sesion runtime=sesion branch=skills/desk-reorganizacion -->
# Desk: skills, decisiones y rutinas

Los skills dependientes de Secretary usan `desk-*`. `delegate` captura y deriva encargos. Los nombres anteriores son alias que cargan el procedimiento vigente. No se renombran scripts, claves de configuración ni IDs históricos por sustitución de texto.

`secretary/data/desk_names.json` separa nombres de skills y nombres operativos de rutinas. Los IDs nativos se conservan: no se registran tareas duplicadas ni se alteran horarios, modelos o harnesses.

## Instalación

`python -m secretary.desk_deploy --source <core> --target ~/.agents/skills --link ~/.claude/skills --prune ~/.codex/skills --prune ~/.cursor/skills --instance-skills <instancia>/canon/skills --runtime <runtime> --scheduled <playbooks-instalados> --bin-dir <bin>` muestra el plan. `--target` recibe la única copia física; `--link` crea un symlink por skill para el harness que no lee `~/.agents/skills` (Claude Code); `--prune` quita las copias del core en harnesses que ya leen `~/.agents/skills`. `--apply` instala con backups por hash y crea `secretary-desk`.

Una sola fuente versionada en `skills/` y `playbooks/`, sin datos personales; los valores de instancia se leen con `secretary config get <clave>`. Los skills y playbooks propios de la instancia viven en su `canon/skills/` y `canon/playbooks/`; un nombre repetido con core es error. Los playbooks privados de ventas reciben solo `routine-overlays/`: no se reemplazan sus procedimientos de negocio o scripts.

## Interfaces

- `secretary-desk overview --context <checkout>`: git y PR por proyecto/contenedor, incluidos worktrees administrados. Los stashes son compartidos por repo; no sumarlos por checkout. Las cifras de upstream son caché y se identifican como tales.
- `secretary-desk decisions`: inventario compatible con desk:decision, para-alvaro y etiquetas históricas. Los errores de lectura permanecen visibles.
- `secretary-desk signals`: evidencia candidata de reportes de rutinas. No declara un bloqueo por detectar una palabra; el skill reconcilia fuente, fecha, decisiones y reglas vigentes.
- `secretary-desk check --repo <repo> --issue <n>`: autoridad para el body actual. Una etiqueta no basta. Una autorización registrada desde una sesión exige recuperar y verificar el mensaje humano original.
- `secretary-desk guard-diff --repo-path <worktree>`: detecta cambios protegidos, incluidos archivos nuevos, que exceden la regla de preparación. No reemplaza la revisión de efectos.
- `secretary-desk publish-event --routine <id> --body-file <texto>`: comentario firmado e idempotente en el brief de hoy, sin otra corrida de modelo. Si falta el brief de hoy, no publica en el anterior; el issue/reporte original conserva el evento.
- `secretary-desk notify-brief --repo <repo> --issue <n> --body-file <texto>`: correo habilitado explícitamente, solo a la cuenta personal y una vez por día. Puede enviarse desde otra cuenta registrada y una dirección "Enviar como" (`send_account`, `from`); el destinatario no cambia. Un resultado incierto bloquea reintentos hasta reconciliar Enviados.

Configuración opcional de la instancia:

```yaml
desk:
  autonomy:
    id: prepare-pr-v1
    enabled: true  # Solo tras aprobación del propietario.
  notifications:
    brief_email: true  # Solo tras aprobación del propietario.
    send_account: your.work.email@company.com  # Opcional: email de una cuenta de `accounts`.
    from: dest@example.com  # Opcional: alias verificado en esa cuenta.
```

La regla permite preparar código, pruebas, análisis y documentos reversibles en un worktree y entregar un PR para revisión. No permite merge, main, despliegue, envíos, gastos, permisos ni ampliar objetivos. Cambios de contratos, skills, autoridad o credenciales requieren autorización específica. Las autorizaciones particulares de otras rutinas conservan sus límites.

## Comprobaciones

`python -m unittest discover -s tests -p test_desk.py -v` verifica alcance, consentimiento, cambios del body, preparación segura, destinatario único, idempotencia, fallos inciertos y despliegue reproducible. Valida también frontmatter de skills y ausencia de datos personales (leak-guard) antes de publicar.

---
🤖 _Claude Code · sesion → skills/desk-reorganizacion · 2026-10-16_

## Avances durante el día

`secretary status` mantiene sus tres argumentos y añade `--state`, `--evidence` y `--next`. Publica un comentario firmado y deduplicado en el brief de la fecha local. Si no existe el brief de hoy, falla explícitamente: no escribe en el de ayer. Los consumidores toman el avance con evidencia más reciente para cada asunto, sin confundir preparación, PR abierto y merge. El reporte de la mañana conserva su fecha; los comentarios describen el avance posterior.

Ejemplo: `secretary status "✅" "proyecto" "informe subido para revisión" --state "presentación pendiente" --evidence "<enlace>" --next "ajustar presentación"`.

## Distribución del cierre

Los cuatro procedimientos de cierre declaran `metadata.close-contract`. El distribuidor
exige el contrato mínimo en la fuente versionada antes de escribir. No hay fuente
privada ni export: lo que se instala es lo que está en git.

Una instalación con un contrato superior también bloquea el lote completo. El plan
incluye fuente efectiva, commit de origen (o `null` fuera de Git), hash y contrato.
La segunda aplicación no cambia los archivos. Los backups conservan el contenido anterior.
Esta protección pertenece al distribuidor actualizado: un ejecutable antiguo no conoce
el contrato. No mezcles versiones del motor ni despliegues desde ramas pendientes sin
revisar su plan. `routines setup` comprueba el cierre antes de su fase de copia heredada
y contempla `.agents`, `.codex`, `.claude` y `.cursor`.

El snapshot sigue siendo opcional. `secretary efficiency --help` lista sus comandos;
`secretary efficiency close-snapshot --help` muestra los argumentos reales.
`secretary signature wind-down --runtime codex` genera una firma que identifica Codex.
`--mark` y `--footer` permiten obtener cada parte. El runtime explícito prevalece;
sin él se consulta `SECRETARY_RUNTIME` y después `CODEX_THREAD_ID`. Si no hay evidencia
del harness, se identifica como sesión. Un runtime desconocido es un error.

Este comando no reemplaza helpers instalados ni modifica las políticas de la instancia.
`status` utiliza la misma firma nativa por defecto. Una configuración explícita de
`SECRETARY_SIGNATURE` conserva el helper de la instancia y falla si este no existe.
Desk copia `signatures.py` junto al runtime, como `brief_html.py`.
