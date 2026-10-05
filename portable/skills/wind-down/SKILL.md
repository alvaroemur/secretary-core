---
name: wind-down
description: Cierra la sesión con una sola recogida de estado, instrucciones estables y un brief de continuidad portable. Resuelve solo los pendientes de esta sesión.
user-invocable: true
---

# wind-down

Al cerrar una sesión, reutiliza su contexto. No abras una sesión auxiliar ni un subagente para reconstruirlo. No implementes ideas nuevas durante el cierre.

## Una sola recogida

1. Identifica los repos y archivos que esta sesión tocó. Recoge decisiones, trabajo terminado, bloqueos y siguiente acción de la conversación. Si el historial no permite identificar un archivo, declara la incertidumbre; no atribuyas cambios ajenos.
2. Para cada repo, crea una sola instantánea temporal mediante `secretary-portable close-snapshot --repo <checkout-real> --session-id <id> --path <archivo> --decision <decisión> --next <acción> --output <temporal.json>`. Repite las opciones según haga falta. En instalaciones del core que ya incluyan el comando, `secretary efficiency` es equivalente. Sin archivos tocados, omite `--path`; nunca uses el último commit como sustituto.
3. Consulta una vez el PR de la rama y los commits sin publicar. No recorras otros worktrees ni repos ajenos a la sesión. Menciona cambios ajenos conocidos una vez, sin modificarlos.
4. Entrega el mismo objeto `close_context` a `sec-project-sync`, `handover` y `jump`. No deben volver a recopilar git ni la conversación.

`close_context` contiene: id de sesión, checkout real, rama, commit, archivos tocados con estado, decisiones, resultado, bloqueos, siguiente acción, PR, ruta del brief y referencias. El snapshot mecánico aporta git; el agente agrega la información de la sesión. No contiene transcripciones ni credenciales.

## Propuesta única

- `sec-project-sync`: revisar solo archivos tocados y decisiones estables; actualizar `AGENTS.md` cuando cambie una regla, comando, fuente canónica o convención.
- `handover`: escribir o actualizar un único brief para la continuidad. `jump` reutiliza ese brief para ofrecer una continuación; no crea otro.
- Ideas sueltas: capturar mediante el skill disponible de dispatch/offload. No ejecutarlas.
- Hechos durables y hitos: enrutar a memoria/wiki mediante el skill correspondiente; no incorporarlos como estado transitorio en `AGENTS.md`.
- Avance comunicado por el usuario: persistir lo pendiente con `secretary status`.
- Issues afectados: comprobar las relaciones en ambas direcciones antes de declarar cierre.

Muestra una lista breve de acciones concretas y bloqueos. Si el usuario ya autorizó una acción, no pidas otra confirmación. Para las decisiones pendientes, reúne las preguntas en una sola propuesta. Un cierre sin trabajo material no necesita un brief vacío.

## Git y cierre

- Sigue las convenciones del `AGENTS.md` aplicable. No fuerces pushes ni escribas código en main. Respeta la política de worktrees de la instancia.
- Avanza los PRs de esta sesión: push, crear PR si falta y pasar a revisión cuando el trabajo esté listo. Aplica la firma de agente configurada antes de crear o comentar artefactos de GitHub.
- Merge de datos/prosa: puede integrarse en la confirmación única del cierre. Merge de código/configuración ejecutable: requiere decisión específica sobre el cambio concreto. Cambios mixtos cuentan como ejecutables. No mergees con conflictos, comentarios humanos pendientes ni fallos reales de CI.
- Si un PR necesita atención, usa el skill de mantenimiento configurado. Comentarios generados por agentes no cuentan como feedback humano.
- Fallos: registra el bloqueo y continúa con las acciones independientes.
- Si cambió el estado material, actualiza heartbeat una sola vez según la política de la instancia.
- Mantén el brief de esta sesión en el repo correspondiente. Para Cowork/Dev usa `<checkout>/.briefs/`; nunca la carpeta de briefs de la instancia.

Reporte final: resultado, instrucciones estables actualizadas (o ninguna), enlace al brief único, PR/issue y bloqueos. Omite secciones vacías. No declares verificaciones que no se ejecutaron.
