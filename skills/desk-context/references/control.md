# Decisiones, autonomía y visibilidad

Los issues existentes son el registro durable. Usa `desk:decision` y conserva la lectura de `para-alvaro` y `secretary:proponer`. La etiqueta `dispatch:execute` solo enruta; no demuestra autorización. Estado del PR: preparado, en revisión, fusionado; abrir un PR no completa el trabajo.

## Dos vías de autorización

1. Específica: aprobación explícita del propietario para el alcance actual. Calcula SHA-256 del body del issue. Un comentario humano `desk:authorize <sha256>` autoriza ese body; `desk:reject <sha256>` lo rechaza. Excluye marcas de agente al interpretar comentarios como humanos.
2. Regla previa `prepare-pr-v1`: si está habilitada en `.secretary.yml` → `desk.autonomy`, permite preparar un único entregable aislado por corrida en un repo de la allowlist, abrir un PR y esperar revisión. Incluye código, pruebas, análisis y documentos reversibles. No permite merges, tocar main, publicar, desplegar, cambiar permisos, gastar, enviar mensajes, acceder a credenciales ni ampliar un objetivo comercial. Solo ejecuta comprobaciones locales conocidas; no instala dependencias ni ejecuta scripts no revisados. Un cambio de contratos, políticas de autonomía, skills, workflows o credenciales exige autorización específica. Comprueba efectos antes de actuar y diff completo, incluidos untracked, antes de publicar. Duda → decisión.

Cualquier productor puede proponer la clasificación; la corrida de desk-dream que ejecuta el encargo (contrato absorbido de work-runner) la verifica de nuevo. Una propuesta elegible incluye en el body:

`<!-- desk:proposal {"kind":"prepare-pr","policy":"prepare-pr-v1","effects":["local-edit","branch","open-pr"],"requires_decision":false} -->`

El marker es metadato del alcance, no prueba de que el trabajo sea seguro. Las autorizaciones previas específicas de otras rutinas siguen vigentes; esta regla no las amplía ni las revoca.

## Decisiones en conversación

Overview puede recoger una aprobación explícita para una propuesta presentada. Registra un comentario firmado con `<!-- desk:authorization {"scope_sha256":"...","source":"codex:<thread-id> o transcript local verificable","owner_quote":"instrucción exacta"} -->`. No inventes citas ni consideres silencio, lectura o un aviso como consentimiento. Si la fuente no es recuperable, conserva la propuesta pendiente y explica el bloqueo. Work-runner debe consultar esa fuente mediante herramientas del harness y verificar el mensaje del usuario, su contexto, identidad, alcance y ausencia de revocación posterior. El recibo por sí solo no autoriza. `secretary-desk check` devuelve `verify-owner-source` en este caso. Cambiar el body invalida el recibo.

## Decisiones pendientes y utilidad de rutinas

Cada propuesta dice: problema, evidencia con fecha, efecto de esperar, opciones, recomendación y respuesta requerida. Incluye rutina, proyecto, prioridad, fingerprint estable y fecha de próxima consulta. No crees un issue nuevo por día para el mismo problema: busca primero abierto/cerrado y actualiza el canónico con evidencia nueva. Posponer conserva la decisión y la fecha; si no cambió, no la repitas en cada consulta. Una urgencia nueva o vencida se vuelve a mostrar.

Cuando una rutina ya no puede aportar valor —fuentes agotadas, estrategia sin resultados, acceso caído, cola sin reposición— debe registrar una decisión, no esconderla solo en un log o PR. Una corrida vacía aislada no demuestra estrategia agotada. Reconciliar reportes históricos con reglas ya aprobadas: no pedir otra vez una decisión resuelta. Si una regla permite resolver el problema, actúa dentro de ella y reporta resultado; si se agota o no aplica, escala. Preserva los límites de envío y fuentes de cada rutina.

Overview y briefing leen los mismos issues y reportes, incluidos `para-alvaro`. Heartbeat conserva evidencia y frescura; no autoriza. Briefing reporta: no detecta y ejecuta trabajo nuevo. Brief-update publica cambios materiales, finalizaciones, fallos o decisiones; no comentarios vacíos. Wind-down reutiliza su snapshot para registrar avance.
