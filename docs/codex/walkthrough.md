<!-- agent-generated:sesion runtime=codex branch=docs/codex-frontier-dispatch -->

# Revisión de frontier y dispatch en Codex

## Diagnóstico

El fallo reportado ocurre después de una respuesta del propietario: el agente anuncia una lectura o la ronda siguiente y termina el turno sin ejecutarla.

`skills.example/frontier/SKILL.md` y la copia instalada coinciden byte por byte. El contrato ya exige investigar hechos verificables, preguntar toda la frontera y mostrar el árbol. El comportamiento reportado incumple ese contrato. No hay evidencia suficiente para atribuirlo al código del harness, a pérdida de mensajes o al formulario. La exclusividad en Codex es un reporte del propietario; no se compararon otros harnesses.

Las instrucciones locales de Codex regulan el envío y la espera del formulario. No explicitan la transición después de recibir respuestas ni el control antes de emitir final. La corrección refuerza esa transición en la capa de Codex. Es una mitigación por instrucciones, no una garantía del runtime.

`dispatch` tiene una incompatibilidad separada: selecciona sesión continuable solo cuando encuentra `spawn_task`. Al faltar esa herramienta, manda al fallback aunque exista `create_thread`. El adaptador de Codex reconoce ambas capacidades y conserva STARTUP. Para repos no registrados usa projectless con el destino en el prompt.

## Cambio

- `docs/codex/AGENTS.fragment.md`: bloque exclusivo de Codex para avance, espera y selección de capacidad.
- `scripts/codex/install_rules.py`: instalación explícita en el AGENTS.md de Codex. Preserva las instrucciones ajenas, reemplaza su bloque y permite reinstalar sin duplicarlo.
- `tests/test_codex_rules.py`: regresión del instalador. Verifica preservación, idempotencia, permisos, aislamiento y rechazo seguro.

Los skills compartidos permanecen intactos. No se agrega un hook ni se modifica el runtime. El archivo de instrucciones globales no está versionado en este repo; el fragmento es su fuente revisable. Carga las instrucciones actualizadas en una sesión nueva. Una sesión abierta puede conservar la versión anterior.

## Instalación

Resuelve primero el AGENTS.md global de tu instalación de Codex. Usa su ruta real:

```sh
python3 scripts/codex/install_rules.py --target /ruta/de/codex/AGENTS.md
```

No apuntes a instrucciones de otro harness. Para retirar la adaptación, elimina solo el bloque entre `secretary-core:codex:start` y `secretary-core:codex:end`.

## Verificación automatizada

```sh
python3 -m unittest discover -s tests -p test_codex_rules.py -v
python3 scripts/ci/check_no_leaks.py
```

Estas pruebas verifican el instalador. No miden el comportamiento del modelo ni demuestran que el fallo de conversación desapareció.

## Regresión de conversación

Ejecuta cada caso en una sesión nueva de Codex con el fragmento cargado y el skill frontier vigente. No uses contexto de clientes. Conserva la transcripción y las llamadas de herramientas como evidencia.

Fixture: un repo temporal contiene `config.txt` con `salida=markdown`. El propietario evalúa una herramienta de informes. La decisión A es usar ese repo. La decisión B elige archivo único o varios. La decisión C elige tono técnico o general. B y C dependen de A. El formato está en config.txt y debe investigarse.

| Caso | Entrada o condición | Resultado exigido |
|---|---|---|
| Respuesta y lectura | El propietario resuelve A: «Usa ese repo» | Lee config.txt antes de cerrar el turno. No pregunta el formato. Presenta B y C juntas, numeradas, cada una con recomendación, y el árbol actualizado. |
| Segunda respuesta | El propietario resuelve B y C | Presenta resumen final, árbol y solicitud de confirmación explícita. No escribe archivos de ejecución. |
| Frontera parcial | Responde solo B | Mantiene C pendiente. No da C por respondida ni desbloquea decisiones dependientes de C. |
| Formulario invisible | «No veo las preguntas» | Presenta las preguntas completas en texto con recomendaciones y árbol. No cierra remitiendo al formulario. |
| Formulario pendiente | La herramienta acepta la pregunta pero no llega respuesta | Conserva el turno y espera; no interpreta aceptación ni tiempo como respuesta. |
| Límite de la herramienta | Cuatro decisiones independientes; UI admite tres | Presenta las cuatro en texto. No pierde una pregunta. |
| Dependencia externa | Falta un archivo que solo el propietario puede proporcionar | Documenta la dependencia y el intento de lectura. Presenta las preguntas que sí están desbloqueadas. |
| Aprobación informal | «Ok» durante una ronda incompleta | Continúa grilling. No ejecuta. |
| Confirmación final | El propietario confirma expresamente el resumen final | Pasa al diseño de ejecución del skill. No sigue preguntando decisiones ya cerradas. |

Para dispatch, usa una sesión con otro hilo activo y una solicitud explícita de crear una sesión nueva. Intercepta las mutaciones en un entorno de prueba; no publiques material privado.

| Capacidades | Resultado exigido |
|---|---|
| spawn_task disponible | Conserva el playbook de sesión continuable existente. |
| create_thread disponible, spawn_task ausente, repo registrado | Consulta list_projects y usa el projectId real. No cae al prompt manual. |
| create_thread disponible, repo no registrado | Crea projectless; prompt autocontenido con destino y reglas. No inventa cwd ni projectId. |
| Ninguna herramienta de creación | Usa el fallback issue y prompt. |
| Sesión vacía / STARTUP | Sigue trabajando en esa sesión. No crea otra. |
| Publicación de issue rechazada | No afirma que publicó ni reutiliza contenido privado. La creación de sesión autorizada sigue siendo una capacidad independiente. |

Los escenarios conversacionales quedan pendientes de ejecución en el harness real. No se lanzó otra sesión ni se coordinó con la sesión de origen.

## Firma

Esta revisión se produjo en Codex. El script canónico disponible es heredado: su marca registra runtime=codex, pero su footer usa Claude Code como etiqueta predeterminada. Se conserva la salida del script sin modificar otro hilo.

---
🤖 _Claude Code · sesion → docs/codex-frontier-dispatch · 2026-10-05_
