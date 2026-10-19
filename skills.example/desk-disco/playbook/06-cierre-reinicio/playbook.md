# Fase 6 — Cierre, memoria y reinicio

## 6.1 Reporte final

Formato `desk-drone`-style (`~/.secretary/rules/sec-output.md`): espacio antes → después,
tabla de lo ejecutado (fases 2-5) vs lo pendiente/propuesto, alertas de seguridad si las hubo.

```bash
df -h /System/Volumes/Data | tail -1
```

## 6.2 RAM cacheada — el disco no es el único recurso

macOS mantiene páginas de apps, buffers y espacio "purgeable" en RAM/disco que solo se liberan
del todo con un reinicio — el `df` de la fase 1 ya cuenta lo purgeable como "libre", así que esto
**no es espacio de disco adicional a recuperar por limpieza de archivos**, es memoria RAM que
queda ocupada por procesos/caches del sistema tras muchas apps abiertas, updates instalados y
sesiones largas (Chrome, Cursor, Docker, IDEs).

**Heurística:** un reinicio típicamente libera **10-20 GB entre RAM y espacio purgeable** cuando
han pasado semanas sin reiniciar y hay muchas apps pesadas abiertas (Chrome con decenas de tabs,
Cursor, Docker, IDEs). Verificar antes de recomendarlo:

```bash
sysctl hw.memsize
vm_stat | head -10
uptime
```

`uptime` con semanas sin reiniciar + `vm_stat` mostrando "Pages wired" o "Pages compressed" alto
es la señal. **Siempre proponer, nunca ejecutar** — reiniciar cierra todas las sesiones, apps y
terminales abiertos, incluida esta.

```
🔁 Recomendado reiniciar la máquina — llevas <N días> sin hacerlo y sueles recuperar 10-20 GB
entre RAM y espacio purgeable. ¿Reinicio ahora o lo dejamos para cuando cierres el día?
```

## 6.3 Memoria del sistema (soul del drone)

Si esta corrida encontró un patrón nuevo (una categoría de archivo no cubierta por
`orden-local.md`, una app nueva generando cache pesado, un hallazgo de seguridad) — apéndalo a
`~/.secretary/subsystem/drone/soul.md` §memory con fecha, siguiendo el mismo criterio que
`desk-drone`: conclusiones durables sobre el sistema, no hechos de negocio del usuario (esos van a
`desk-write`).

## 6.4 Actualizar la política si el mapa de destinos cambió

Si en fase 3/4 apareció un proyecto nuevo con su propia carpeta de descargas, o una carpeta Drive
nueva que debería reutilizarse en la próxima corrida, actualizar
`~/.secretary/operational/orden-local.md` §2 en un PR (worktree + `gh pr create`, mismo patrón
que `tidy-up`) — no dejar el conocimiento solo en el chat de esta sesión.

## 6.5 Qué NO hacer en el cierre

- No reiniciar sin OK explícito, incluso si el usuario preguntó "¿hace falta reiniciar?" — eso es
  una pregunta, no una autorización.
- No commitear cambios en `.secretary` sin que el usuario lo pida (salvo el patrón estándar de
  PR + revisión, igual que cualquier otro cambio de política).
- No borrar nada marcado como "pendiente" en fase 3 solo porque la sesión está por cerrar —
  queda pendiente para la próxima corrida o para que el usuario decida fuera de esta sesión.
