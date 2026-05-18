# Ajustes y correcciones del usuario

Última actualización: YYYY-MM-DD

---

> Plantilla de ejemplo. Reemplaza los placeholders y los ejemplos
> fechados con correcciones reales del usuario a medida que ocurran.

Este archivo registra correcciones que `<USER_NAME>` hace a las decisiones de la rutina. La rutina debe leerlo antes de actuar y aplicar estos ajustes como reglas persistentes.

## Correcciones de clasificación

- YYYY-MM-DD: No crear borradores para notificaciones automáticas de servicios de almacenamiento compartido (ej. shares de Drive). Nadie responde a eso. Excepción: si el contenido del correo incluye un mensaje personal explícito.
- YYYY-MM-DD: `<CONTACT_NAME>` (`<sender@example.com>`) es un familiar/contacto cercano del usuario. La comunicación con él/ella ocurre por otro canal (no por email). No crear borradores para sus correos automáticos (Drive shares, etc.).
- YYYY-MM-DD: Correos del banco/servicio sensible (`<sender@example.com>`) o cualquier mención a la tarjeta/cuenta `<ACCOUNT_REF>` → **NO archivar automáticamente**. El usuario no la utiliza activamente. Dejar en inbox y marcar como acción requerida.
- YYYY-MM-DD: Cola/Eliminar debe **archivar** (no solo etiquetar). Periódicamente (ej. los viernes) la rutina hace un reporte extendido que resume todo lo archivado/eliminado del periodo, analiza qué podría ser relevante, y sugiere unsubscribes para lo que no lo es.
- YYYY-MM-DD: **Oportunidades de trabajo y convocatorias NUNCA van a Cola/Eliminar.** La rutina debe revisar cada alerta de empleo y evaluar relevancia vs. el perfil del usuario (áreas temáticas, geografía, seniority) y dejar en inbox las que encajen para que él/ella priorice. Archivar solo las claramente irrelevantes. Ir mejorando el criterio con el feedback.

- YYYY-MM-DD: **NUNCA mover correos a la papelera (TRASH).** La rutina NO tiene permiso de borrar correos bajo ninguna circunstancia. "Cola/Eliminar" significa archivar (`--remove INBOX`), NO `--add TRASH`.

## Correcciones de tono / borradores

- Despedida preferida: `<SIGN_OFF>` (ej. "Saludos", "Abrazo").
- Trato preferido: `<tuteo | usted | voseo>` cuando sea apropiado.
- Estilo: ser conciso.

## Correcciones de comportamiento

- YYYY-MM-DD: Si el usuario reporta que la rutina está siendo demasiado agresiva archivando/eliminando, **preferir dejar en inbox ante la duda** hasta que indique lo contrario. Solo archivar/eliminar cuando haya certeza alta de que el correo no requiere atención.
- YYYY-MM-DD: **NUNCA aceptar, rechazar ni responder invitaciones de calendario automáticamente.** Solo reportarlas en el resumen. Actuar sobre el calendario únicamente cuando el usuario lo pida explícitamente.
- YYYY-MM-DD: **Borradores siempre dentro del hilo.** Usar el comando del CLI que permite responder al messageId original (`--reply-to-message-id <messageId>`), nunca crear borradores huérfanos vía APIs que no soporten reply-to.
- YYYY-MM-DD: Sobre pagos pendientes, definir prioridad por servicio: marcar urgentes los que afecten producción/operación; los demás pueden esperar.
- YYYY-MM-DD: **Reporte semanal periódico.** Además de la revisión diaria, hacer un reporte extendido que cubra todo lo archivado y flaggeado como Cola/Eliminar desde el reporte anterior. Incluir: resumen de lo que llegó, análisis de qué podría ser relevante, y para lo que no lo es, investigar si se puede hacer unsubscribe (link o instrucciones).
- YYYY-MM-DD: **Eventos con deadline ≠ informativos.** Cuando un correo de un proyecto activo menciona una fecha futura, leer el cuerpo completo y extraer toda acción implícita: registro, RSVP, formulario a completar, presencia esperada, difusión de materiales. Marcarlas como "Acción requerida" en el reporte con deadline explícito, **no** como "evento próximo, sin acciones". Si sugieres una respuesta, crearla como borrador (no solo describirla).

## Formato

Cuando el usuario corrija algo, agregarlo aquí con fecha y contexto breve. Ejemplo:

```
- YYYY-MM-DD: "No archives correos de <sender>, siempre los quiero ver" → mover a policy.md como regla de inbox
- YYYY-MM-DD: "El tono del borrador para <persona> fue muy formal" → registrar preferencia de tono
```
