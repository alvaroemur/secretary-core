# Ajustes y correcciones del usuario

Última actualización: 2026-04-29

---

Este archivo registra correcciones que Álvaro hace a las decisiones de la rutina. La rutina debe leerlo antes de actuar y aplicar estos ajustes como reglas persistentes.

## Correcciones de clasificación

- 2026-04-29: No crear borradores para notificaciones de Google Drive (carpeta compartida). Nadie responde a eso. Excepción: si el contenido del correo incluye un mensaje personal explícito.
- 2026-04-29: Francisco Tizón (franciscotizon@gmail.com) es el tío de Álvaro (hermano de su mamá). Comunicación con él es por WhatsApp, no por email. No crear borradores para sus correos automáticos (Drive shares, etc.).
- 2026-04-29: Correos de DAVIbank (DAVIbankInforma@davibank.com) o cualquier mención a tarjeta *5876 → **NO archivar automáticamente**. Álvaro no usa esa tarjeta activamente. El incidente del 2026-04-28 (inscripción en Google Pay) se resolvió como actualización automática del banco, pero cualquier movimiento nuevo es sospechoso. Dejar en inbox y marcar como acción requerida.
- 2026-04-29: Cola/Eliminar debe **archivar** (no solo etiquetar). Los viernes la rutina hace un reporte extendido que resume todo lo archivado/eliminado de la semana, analiza qué podría ser relevante, y sugiere unsubscribes para lo que no lo es.
- 2026-04-29: **Oportunidades de trabajo y convocatorias NUNCA van a Cola/Eliminar.** La rutina debe revisar cada alerta de empleo (LinkedIn, etc.), evaluar relevancia vs. perfil de Álvaro (impacto social, sostenibilidad, IA, gestión de proyectos, Latam, dirección) y dejar en inbox las que encajen para que él priorice. Archivar solo las claramente irrelevantes. Ir mejorando el criterio con el feedback.

- 2026-05-09: **NUNCA mover correos a la papelera (TRASH).** La rutina NO tiene permiso de borrar correos bajo ninguna circunstancia. "Cola/Eliminar" significa archivar (`--remove INBOX`), NO `--add TRASH`. Se rescataron 23 correos de la papelera enviados erróneamente entre el 4 y 9 de mayo.

## Correcciones de tono / borradores

- Usar "Abrazo" como despedida.
- Tutear cuando sea apropiado.
- Ser conciso.

## Correcciones de comportamiento

- 2026-04-29: Álvaro siente que la rutina está siendo demasiado agresiva archivando/eliminando y se pierde de cosas. **Preferir dejar en inbox ante la duda** hasta que el usuario indique lo contrario. Solo archivar/eliminar cuando haya certeza alta de que el correo no requiere atención.
- 2026-04-29: **NUNCA aceptar, rechazar ni responder invitaciones de calendario automáticamente.** Solo reportarlas en el resumen. Actuar sobre el calendario únicamente cuando Álvaro lo pida explícitamente.
- 2026-04-29: **Borradores siempre dentro del hilo.** Usar `gog gmail drafts create --reply-to-message-id <messageId>`, nunca el MCP create_draft (que crea borradores huérfanos).
- 2026-04-29: Sobre pagos pendientes, **Netlify es urgente** (reactivar). Los demás (Google Play, Apple TV) no son prioridad por ahora.
- 2026-04-29: **Reporte semanal los viernes.** Además de la revisión diaria, los viernes hacer un reporte extendido que cubra todo lo archivado y flaggeado como Cola/Eliminar desde el viernes anterior. Incluir: resumen de lo que llegó, análisis de qué podría ser relevante, y para lo que no lo es, investigar si se puede hacer unsubscribe (link o instrucciones).
- 2026-05-05: **Eventos con deadline ≠ informativos.** Cuando un correo de un proyecto activo (kunan, escalonverde, agora2030, change-lab, etc.) menciona una fecha futura, leer el cuerpo completo y extraer toda acción implícita: registro, RSVP, formulario a completar, presencia esperada como miembro de comité, difusión de materiales. Marcarlas como "Acción requerida" en el reporte con deadline explícito, **no** como "evento próximo, sin acciones". Si sugieres una respuesta, crearla como borrador (no solo describirla). Contexto: Álvaro se perdió el lanzamiento del Desafío Kunan 5 mayo 2026 porque clasifiqué el correo del 22 abril como "informativo" cuando requería difusión + formulario + asistencia como miembro del Comité Técnico.

## Formato

Cuando Álvaro corrija algo, agregarlo aquí con fecha y contexto breve. Ejemplo:

```
- 2026-XX-XX: "No archives correos de [remitente], siempre los quiero ver" → mover a politica.md como regla de inbox
- 2026-XX-XX: "El tono del borrador para [persona] fue muy formal" → registrar preferencia de tono
```
