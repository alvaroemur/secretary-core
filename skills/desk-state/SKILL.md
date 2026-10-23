---
name: desk-state
description: Lee notas WIP guardadas con su fecha; úsalo para recuperar el estado registrado, no para comprobar sesiones o repos en vivo.
---

# desk-state

Lector interno, de solo lectura, del store WIP resuelto por `.secretary.yml`. Enumera entradas, título, fecha, pendientes y referencias a ramas o PR. No modifica el store ni afirma que sus notas sean estado actual. Un store vacío significa que no hay notas registradas, no que no exista trabajo.

Para comprobar sesiones, worktrees, PR, dirty, commits o stash actuales, usa desk-overview. No vuelve a hacer ese barrido si overview ya reunió la evidencia. Señala antigüedad y huecos del registro sin inventar datos.
