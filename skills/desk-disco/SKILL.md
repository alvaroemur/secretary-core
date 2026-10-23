---
name: desk-disco
description: >-
  Limpieza de disco a demanda — inventario, caches regenerables, carpetas de tránsito (Escritorio,
  Downloads, Documents), migración a Drive y recomendación de reinicio. Ejecuta la misma doctrina
  que la rutina semanal `tidy-up`, pero interactiva y a fondo: para cuando Álvaro pide liberar
  espacio ahora, no esperar al domingo. Triggers: "/desk-disco", "limpieza de disco", "libera
  espacio", "el disco está lleno", "cuánto pesa mi disco", "repite la limpieza del mes pasado".
---

# desk-disco — limpieza de disco a demanda

Compañero de higiene de disco: inventaría, limpia lo regenerable sin preguntar, propone y
confirma lo que toca juicio humano, migra a Drive lo que corresponde, y cierra con el recordatorio
de reinicio. Es la versión **interactiva y a fondo** de la rutina `tidy-up` (semanal, solo
Escritorio/Downloads/Documents) — aquí se cubre todo el disco.

Doctrina base: `~/.secretary/operational/orden-local.md` (taxonomía de carpetas transitorias y
mapa de destinos) y `~/.secretary/rules/drive-cowork.md` (P1/P2 — qué va a Drive vs Cowork/Dev).

## Cuándo usar / no usar

- **Usar:** el usuario pide espacio, el disco está por debajo de ~15% libre, desk-drone señaló el
  gap de higiene (Phase 2), o "repite la limpieza" tras semanas sin correrla.
- **No usar:** el barrido semanal automático de Escritorio/Downloads/Documents ya lo cubre
  `tidy-up` — no dupliques ese trabajo si solo hace falta el triage ligero de esas tres carpetas
  sin tocar el resto del disco.

## Fases (playbook)

Cada fase vive en su propia carpeta numerada bajo `playbook/`, con un `playbook.md` estandarizado
dentro. Ejecutar en orden; las fases 3–5 pueden correr con hallazgos en paralelo pero las
confirmaciones de usuario (AskUserQuestion) se agrupan al final de cada fase, no al final de todo.

| Fase | Carpeta | Qué hace |
|---|---|---|
| 0 | [`playbook/00-orientacion/playbook.md`](playbook/00-orientacion/playbook.md) | Principios, guardrails, qué nunca se toca sin OK |
| 1 | [`playbook/01-inventario/playbook.md`](playbook/01-inventario/playbook.md) | Medir el disco, encontrar los focos grandes |
| 2 | [`playbook/02-caches-regenerables/playbook.md`](playbook/02-caches-regenerables/playbook.md) | Borrar caches de desarrollo/apps sin preguntar |
| 3 | [`playbook/03-carpetas-transitorias/playbook.md`](playbook/03-carpetas-transitorias/playbook.md) | Escritorio, Downloads, Documents — clasificar y rutear |
| 4 | [`playbook/04-migracion-drive/playbook.md`](playbook/04-migracion-drive/playbook.md) | Subir a Drive lo que corresponde, verificar, borrar local |
| 5 | [`playbook/05-documents-pipelines/playbook.md`](playbook/05-documents-pipelines/playbook.md) | Datasets de pipelines (doc2struct y similares) |
| 6 | [`playbook/06-cierre-reinicio/playbook.md`](playbook/06-cierre-reinicio/playbook.md) | Reporte, memoria del drone, recomendación de reinicio |

## Reporte

Mismo formato compacto que `desk-drone` (`~/.secretary/rules/sec-output.md`): estado del disco
antes/después, tabla de lo ejecutado vs lo propuesto, alertas de seguridad si aparecieron, y el
cierre de fase 6. No dumpear listados largos de `du`/`find` en el chat — resumir y linkear al
manifiesto si hace falta detalle.

## Automático vs requiere OK

| Acción | Automático | Requiere OK |
|---|---|---|
| Medir disco, inventariar | ✅ | |
| Borrar caches regenerables (fase 2) | ✅ | |
| Mover archivos dentro del disco (fase 3, según `orden-local.md`) | ✅ | |
| Borrar credenciales sueltas encontradas | ✅ (siempre, es 🚨) | |
| Subir a Drive | | 🚧 tamaño + destino |
| Borrar fotos, media personal, libros, cualquier dato no regenerable | | 🚧 siempre |
| Borrar intermedios de pipelines (Documents) | | 🚧 tras verificar entrega en Drive |
| Reiniciar la máquina | | 🚧 siempre — cierra sesiones y apps abiertas |
