---
name: secretary-briefing
description: Publica el reporte diario del sistema y sus decisiones pendientes; notifica al propietario cuando está habilitado.
---

# secretary-briefing

Lee AGENTS, la política de briefing y `desk-context/references/control.md`. El brief reporta; no detecta y ejecuta trabajo nuevo, crea drafts ni habilita issues. Sus salidas son el brief y la notificación al propietario habilitada en config. No cambia permisos de otras rutinas.

En corridas programadas no uses las herramientas de seguimiento de la app (lista de tareas ni cuadro de cierre): nadie las ve y cuestan tokens. Reporta solo en el issue y en el mensaje final.

## Entradas recolectadas

Primero corre `python3 "${SECRETARY_CORE:-$HOME/Dev/secretary-core}/secretary/routines/ops/briefing-collect.py" --dry-run`. Solo lee: escribe un JSON en un directorio temporal, imprime su ruta y nunca publica ni notifica. Trae config relevante, briefs recientes (el de hoy y el anterior abierto, con comentarios), decisiones de `secretary-desk decisions`, señales, conversaciones, PR abiertos y fusionados por repo habilitado, heartbeat, frescura de extractores, corridas de rutinas, loops, commits de la instancia y agenda personal del día. Trabaja sobre ese JSON. Consulta a mano solo lo que falte o figure en `failed_sources`.

Validación (3 corridas, decisión N6): en el mensaje final anota si el JSON cubrió lo que necesitaste y qué consultaste aparte, con comando y motivo.

## Fuentes y reconciliación

Toma instance, timezone y brief.repo/label de `config` del JSON (respaldo: `secretary config get <clave>`). Lee heartbeat con fecha/frescura; últimos briefs y comentarios sec-status; PR abiertos y recién fusionados; reportes existentes de captura y loops. Si falta una fuente, informa el hueco y la rutina responsable; no dispara extractores desde este reporte. Usa `decisions` y `signals` del JSON (salida de `secretary-desk`) como inventario, luego comprueba las fuentes originales.

Incluye decisiones que una rutina necesita para seguir siendo útil: fuentes agotadas, rachas sin resultado, estrategia, accesos y cola de ventas sin reposición. Consulta `para-alvaro`, `secretary:proponer` y `desk:decision`. Deduplica por issue/fingerprint, comprueba posposiciones y decisiones ya resueltas. No sustituye una decisión previa de cambiar feeds por otra pregunta de pausar. Las señales históricas contradictorias se presentan con fecha y fuente actual, sin inventar urgencia.

## Reporte y entrega

Busca el issue de hoy por etiqueta y fecha en timezone configurada: si existe, actualízalo conservando comentarios; si no, créalo. Lee pendientes del anterior y enlaza el nuevo antes de cerrar el anterior. BRIEF_REFRESH_ISSUE apunta al issue existente; valida etiqueta. Firma con el helper de la instancia.

Secciones, en este orden. Se mantiene la estructura; los emojis marcan sección y estado. Doctrina de plantillas: `canon/rules/skills/skills-contract.md` § Output templates.
1. Requiere tu decisión: hasta tres principales, numeradas (`1.`, `2.`, `3.`), con rutina/proyecto, evidencia/antigüedad, consecuencia de esperar, recomendación y enlace; contador/enlaces de las restantes. Urgencias concretas primero; pospuestas no vencidas aparte. Cierra la sección con un bloque cercado ```text, prellenado con la recomendación de cada número, listo para copiar y editar como comentario del issue (`1: sí`, `2: posponer 7 días`). Un solo bloque, sin fences anidados.
2. Trabajo en marcha: sesiones conocidas, repo/rama, PR, cambios pendientes, bloqueos; cobertura/frescura.
3. Avances y entregas: PR preparado/en revisión/fusionado distinguidos, acciones de negocio con evidencia. No afirma terminado por dispatch:done.
4. 🤖 Dream entregó: PR abiertos o fusionados en la ventana cuya rama empieza con `dream/` (en `repo_prs` del JSON), sin contar los reportes `chore(dream)`. Una línea por PR: enlace · compromiso que avanza · por qué sirve · cómo verificarlo en menos de 2 minutos. Toma el compromiso y la verificación del body del PR (`gh pr view`); si faltan, dilo en la línea. Sin entregas, omite la sección.
5. Agenda y asuntos: correo, reuniones, Drive, pendientes relevantes de fuentes existentes.
6. 🗂️ Compromisos caducados esta semana (solo los lunes, en la timezone configurada): en `$(secretary config path meetings.memory)/acciones.md`, entradas que pasaron a `caducada` o `cancelada` en los últimos 7 días, agrupadas por proyecto con su ID `acc-…` y motivo. Aparte, las propuestas de caducar que esperan decisión (proyectos con reunión reciente): esas van como decisión en la sección 1. En lo que lee el propietario, el sistema se llama "compromisos".
7. Salud y utilidad de rutinas: última evidencia, problemas abiertos, acción o decisión requerida. No confundir invocación, consumo y éxito.

No crea encargos ejecutables ni modifica su autorización. Notificar no equivale a autorizar.

## Correo al propietario

Si `desk.notifications.brief_email` está habilitado, prepara texto breve con decisiones, urgencias/bloqueos, avances y URL real del brief; firma con helper y guarda cuerpo temporal. Ejecuta `secretary-desk notify-brief --repo <brief.repo> --issue <n> --body-file <archivo>`. El helper solo permite la cuenta personal configurada, el brief de hoy y una notificación diaria; no admite destinatarios arbitrarios. Un resultado incierto se reconcilia en Enviados, no se reintenta a ciegas. Reporta fallo de notificación sin ocultar que el brief sí existe. Esta autorización no se extiende a terceros, otros correos o WhatsApp.
