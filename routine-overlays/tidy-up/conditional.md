

## Tareas condicionales · tidy-up

Esta sección añade preparación de reorganizaciones mediante PR a los repos habilitados. Sustituye «proposals only» solo para una solicitud delimitada que cumpla estas condiciones. No cambia el barrido existente de tránsito ni sus permisos. Todo ledger versionado se entrega por worktree/PR; no escribir recurrencia directo a main. Heartbeat conserva su excepción.

### Compuerta y descubrimiento

Lee la configuración real. Si `tidy.conditional.enabled` no es `true`, no descubras ni prepares tareas condicionales; conserva el barrido previo y declara la función desactivada. No cambies esa bandera desde la rutina.

Con la función habilitada, ejecuta `python -m secretary.tidy --queue`. Usa solo `dispatch.executor.repos`. Un error de lectura no es cola vacía: registra y escala el fallo. Consume issues abiertos con `tag:tidyup`; la etiqueta no autoriza efectos. Lee `canon/operational/routines/tidy-up-condicional.md` de la instancia para el contrato y las solicitudes pendientes. La definición del engine vive en `docs/tidy.md` del core.

### Evaluación y preparación

1. Consulta la solicitud, sus comentarios y PRs enlazados; no repetir una preparación ya abierta o realizada. Evalúa `python -m secretary.tidy --repo <repo> --issue <n>`. No fabriques evidencia de sesiones; sin colector confiable, omite `--activity`.
2. `waiting`: conservar solicitud. `blocked`: publicar el motivo concreto y las rutas. `proposal-only`: preparar solo plan y evidencia; backups, borrados y Drive conservan aprobación específica. Ninguno permite movimientos. Sin cambio de `report_key`, no repetir el aviso ni abrir un PR vacío.
3. `eligible-for-pr`: revisar metodología vigente y dependencias externas/semánticas. Si el alcance no está delimitado, publicar propuesta sin preparar movimientos. La preparación reversible de esta clase se autoriza mediante el contrato específico aprobado, no mediante la etiqueta. No cambiar objetivos, autoridad, credenciales ni reglas de permisos.
4. Reclamar el repo: `python -m secretary.tidy --repo <repo> --claim acquire --fingerprint <fingerprint>`. Guardar el token; un reclamo previo bloquea sin caducidad automática. Revalidar la solicitud, condiciones, actividad y rutas inmediatamente después de reclamar. Cualquier diferencia de contrato o alcance exige reevaluación; no continuar con evidencia de más de cinco minutos.
5. Crear un worktree propio desde la base remota comprobada. Preparar solo archivos versionados, sin mover datos del checkout activo ni ignorados/untracked. Generar el manifiesto con `git ls-files` y mover por archivo; no mover una carpeta completa que pueda arrastrar archivos ignorados. Actualizar índices, enlaces y configuración que formen parte del alcance. Validar rutas reales del diff, referencias y checks del repo. Si aparecen cambios fuera del plan o un pendiente nuevo, detenerse y registrar la propuesta.
6. Abrir un PR enlazado al issue con explicación antes/después, manifiesto de movimientos y referencias, bloqueos descartados, evidencia y plan de reversión. Nunca mergear ni activar el cambio. No cerrar la solicitud como completada al abrir un PR.
7. Liberar el reclamo del propio intento con `--claim release --token <token>`, también ante un fallo controlado. Ante resultado incierto, comprobar PR/worktree/resultados antes de liberar y reintentar. Nunca usar un token de otro intento. El reclamo local solo coordina un host; no iniciar esta preparación desde dos máquinas.

### Visibilidad

Guardar el informe en `subsystem/housekeeping/conditional/` mediante el PR de la corrida. Comentario firmado en el issue con `<!-- tidy:report <report_key> -->` solo ante cambios materiales. Mostrar estado actual, rutas bloqueadas, evidencia, efecto de esperar y siguiente decisión. Para deduplicar, comparar la última evaluación, no cualquier coincidencia histórica.

Publicar el mismo avance en el brief de hoy con `secretary-desk publish-event --routine tidy-up --body-file <texto>`; conservarlo en la solicitud si hoy no existe brief. Los bloqueos que requieren decisión del propietario llevan `desk:decision` y siguen visibles en overview; retirar esa etiqueta solo al resolver esa decisión con evidencia. No marcar `dispatch:execute` ni derivar automáticamente a otro ejecutor.
