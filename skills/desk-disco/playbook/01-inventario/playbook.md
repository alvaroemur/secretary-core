# Fase 1 — Inventario

Objetivo: encontrar los focos grandes sin perder tiempo en `du` de todo el disco (lento e
innecesario). Medir de afuera hacia adentro, parar en cuanto un directorio explica el peso.

## 1.1 Estado general

```bash
df -h / /System/Volumes/Data
```

En macOS con volumen de datos separado, `/System/Volumes/Data` es el que importa para espacio de
usuario. Anotar el % libre — referencia: por debajo de 15% es zona de alerta.

## 1.2 Barrido top-level del home

```bash
du -xsh /Users/alvaromur/* 2>/dev/null | sort -rh | head -15
```

`-x` evita cruzar a otros filesystems (útil si hay volúmenes montados). Puede tardar 1-2 min si
`Library` está sucio — no bloquear el resto del playbook por esto, correr en background si hace
falta (`run_in_background: true`) y seguir con fase 2 mientras.

## 1.3 Desglose de los 3-4 focos más grandes

Típicamente: `Library` (apps + caches), `Documents` (si hay datasets de pipelines o librerías de
producción), `Downloads`, `Dev`. Para cada uno:

```bash
du -xsh "/Users/alvaromur/Library/Application Support"/* 2>/dev/null | sort -rh | head -15
du -xsh ~/Library/Caches/* 2>/dev/null | sort -rh | head -15
du -xsh /Users/alvaromur/Documents/* 2>/dev/null | sort -rh | head -10
du -xsh /Users/alvaromur/Downloads/* 2>/dev/null | sort -rh | head -15
```

Clasificar cada entrada grande en una de tres cajas antes de seguir:

- **Cache/regenerable** → fase 2.
- **Carpeta de tránsito o archivo suelto identificable** (screenshots, descargas, datasets) →
  fase 3 o 5.
- **Dato real sin home claro** (app nueva no vista antes, librería grande, proyecto) → anotar
  para preguntar en el cierre; no hay regla automática para lo desconocido.

## 1.4 Procedencia de archivos sueltos (Downloads/Desktop)

Para rutear con confianza en fase 3, usar la procedencia real, no solo el nombre:

```bash
mdls -raw -name kMDItemWhereFroms "<archivo>" 2>/dev/null
```

Devuelve la URL de descarga cuando macOS la registró (casi siempre, salvo archivos movidos o muy
viejos). Combinar con fecha de modificación (`stat -f '%Sm' -t '%Y-%m-%d' <archivo>`) para aplicar
retención.

## 1.5 Comparar contra la corrida anterior

Si existe un manifiesto de la limpieza previa (`scratchpad/downloads-manifest.tsv` o similar de
la sesión anterior), no hace falta reconstruir la clasificación desde cero — solo inventariar lo
**nuevo** desde esa fecha. Las carpetas transitorias (`_tmp`, `_fotos`, etc.) ya existentes se
tratan como estructura dada, no se re-crean.
