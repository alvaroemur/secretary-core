# Fase 0 — Orientación

## Principios

1. **Mover y borrar lo regenerable sin preguntar. Confirmar todo lo demás.** Un cache, un
   instalador o un intermedio de pipeline ya verificado en Drive se puede recrear o ya está
   respaldado — no hace falta permiso. Una foto, un video, un libro, un dato de negocio: se
   pregunta, aunque parezca obvio.
2. **Verificar antes de borrar, nunca asumir.** Si algo "ya debería estar en Drive", confírmalo
   con `gog drive search` antes de borrar el local. Ver fase 4.
3. **No hay prisa por un GB extra.** El objetivo es un disco sano (>15-20% libre), no exprimir
   cada byte. Ante la duda entre proponer y ejecutar, proponer.
4. **Nunca reinicies la máquina sin OK explícito.** Cierra sesiones de trabajo, apps abiertas,
   terminales — es la acción más disruptiva del playbook. Ver fase 6.

## Guardrail de instrucción previa

Este playbook fue escrito a partir de una limpieza real (2026-07-06, ~27 GB liberados) y su
repetición un mes después (2026-08-07). Las decisiones que Álvaro ya tomó sobre categorías
completas **no se vuelven a preguntar cada vez** — quedan codificadas aquí y en
`~/.secretary/operational/orden-local.md`. Si aparece una categoría nueva, se pregunta una vez
y, si la respuesta es reutilizable, se documenta en el playbook o en la política.

## Nunca tocar sin instrucción explícita del usuario en esa sesión

- Juegos instalados (Steam, Battle.net, StarCraft II y similares) — decisión ya tomada: no se
  borran aunque pesen mucho.
- Docker Desktop y sus imágenes/containers.
- Historial de Cursor (`state.vscdb`) — es historial real, no espacio muerto; compactarlo pierde
  contexto. Ver hallazgo en memoria del drone (soul, 2026-07).
- `~/.secretary/`, cualquier repo de `~/Dev/` o `~/Cowork/` — estos son de `tidy-up`/sesiones de
  código, no de este skill.
- Librerías de producción activas (samples de música, presets, assets de DAW) aunque vivan en
  `~/Documents/` — no son basura, son herramienta de trabajo. Proponer reubicación si aplica
  (p. ej. a `~/Cowork/musicprod/`), nunca borrar.
- Cualquier app corriendo activamente (verificar `pgrep` antes de tocar su cache o base de datos).

## Alertas de seguridad (siempre, sin excepción)

Si en cualquier fase aparecen credenciales sueltas — `client_secret*.json`, `Backup-codes*`,
`.pem`, `.key`, tokens, contraseñas en texto plano — se **borran directo** (no tienen valor de
respaldo quedándose en Downloads/Desktop; el original vive en la consola del proveedor o en el
gestor de contraseñas) y se reporta con 🚨 en el cierre. No se preguntan porque dejarlas ahí es
el riesgo, no borrarlas.

## Disparadores

- `/desk-disco`, "limpieza de disco", "libera espacio", "el disco está lleno".
- desk-drone Phase 2 señala >25 archivos sueltos en Desktop/Downloads o disco <15% libre.
- "repite la limpieza" / "ha pasado un mes" — correr el playbook completo desde fase 1.
