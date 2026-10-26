<!-- secretary-core:codex:start -->
# Adaptación de skills al harness Codex

Estas reglas solo se aplican a Codex. Conserva el contrato de los skills compartidos.

## Avance de frontier después de una respuesta

- Tras recibir respuestas del propietario, cierra las decisiones resueltas y actualiza el árbol.
- Ejecuta en este turno las lecturas necesarias para resolver hechos verificables. No vuelvas a preguntar hechos acordados.
- La investigación factual y el avance de rondas están permitidos durante grilling. La aprobación final sigue siendo necesaria para ejecutar cambios.
- Presenta todas las preguntas desbloqueadas juntas, numeradas, con una recomendación por pregunta y el árbol actualizado.
- Si la frontera está vacía, presenta el resumen final y el árbol. Pide confirmación explícita antes de diseñar o ejecutar el trabajo.
- No emitas final con una promesa de lectura o preparación inmediata pendiente. Primero ejecuta la lectura y presenta la ronda o la confirmación.
- Si una dependencia externa real impide avanzar, identifica qué falta, qué intentaste y cómo se desbloquea. No confundas una lectura disponible con una dependencia externa.
- Antes de finalizar, comprueba: lecturas anunciadas realizadas; preguntas desbloqueadas presentadas con recomendaciones y árbol; o resumen final con solicitud de confirmación explícita; o dependencia externa documentada.

## Preguntas y espera

- Usa request_user_input_async solo si existe y su contrato permite la pregunta. accepted=true no confirma visibilidad ni respuesta.
- Mientras el formulario esté pendiente, conserva el turno activo. Continúa solo trabajo independiente y espera en intervalos de hasta 60 segundos, interrumpibles por entrada.
- Si el formulario falla, el propietario no lo ve o no puedes mantener la espera, presenta las preguntas completas en texto. Si cierras el turno, incluye las preguntas pendientes en final.
- No deduzcas una respuesta ni aprobación del tiempo transcurrido. Una respuesta de ronda no aprueba la ejecución.
- Si hay más preguntas que las admitidas por la herramienta, presenta toda la ronda en texto. No reduzcas la frontera para acomodar la UI.

## Capacidad de dispatch

- Cuando el propietario pide dispatch a una sesión nueva y hay un hilo activo que proteger, usa una sesión continuable. No uses subagentes como destino.
- Selecciona por capacidad: spawn_task si existe; si no existe, create_thread si existe; sin ambas capacidades, usa issue y prompt de reinicio.
- Para create_thread, consulta list_projects primero. Usa el projectId devuelto si el repo está registrado. Respeta el contrato de create_thread y la autorización para crear una sesión nueva.
- Si el repo no está registrado, crea una sesión projectless con un prompt autocontenido que indique el repo destino, la lectura de sus reglas y el pedido del propietario. No inventes projectId ni un parámetro cwd.
- Conserva STARTUP: si no hay hilo activo que proteger, esta sesión sigue siendo el destino. No crees otra sesión.
- Mantén el registro durable mediante issue o PR según el triage. Si la publicación se rechaza, registra el bloqueo sin reintentar con contenido privado. La falta de issue no implica falta de capacidad para crear la sesión autorizada.
- No anuncies una sesión creada sin resultado exitoso de la herramienta. Comprueba el progreso con la capacidad de espera disponible y entrega el identificador o enlace que corresponda al contrato del harness.
<!-- secretary-core:codex:end -->
