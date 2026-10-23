# Fase 5 — Datasets de pipelines en Documents

Aplica a carpetas tipo `~/Documents/aliantza-doc2struct-data/` — datasets de entrada/salida de
pipelines de procesamiento (doc2struct y similares) que acumulan intermedios pesados por mes.

## 5.1 Estructura esperada

```
<pipeline-data>/
  <proyecto>/
    input/       # crudos, a menudo re-descargables de Drive
    output/      # intermedios (chunks, JSON por doc) + consolidados finales
    archivo/     # ya procesado, bajo peso
```

## 5.2 Regla de borrado

Un intermedio de un **mes cerrado** (no el mes en curso) es candidato a borrado **solo después**
de verificar que el consolidado/entrega final ya vive en Drive:

```bash
gog drive search "<nombre del consolidado o del mes>" --max 10 --plain
```

Si aparece el archivo esperado (Sheet, xlsx, o carpeta "ENTREGA") en Drive con fecha razonable →
proponer borrado del intermedio local. Si no aparece → no tocar, el pipeline puede necesitar
reprocesar desde ahí.

**Conservar siempre:** CSVs consolidados (`_consolidado_*`, `*_output_concar.csv`), carpetas con
sufijo `ENTREGA`, y todo el mes en curso o el inmediatamente anterior (puede seguir en revisión).

**Candidatos típicos a borrar** (visto en corridas reales): carpetas de `chunks` intermedios,
subcarpetas por semana de compras ya consolidadas, versiones `v1x_gpt5x` superadas por una
versión posterior del mismo mes.

## 5.3 Zips re-descargados sueltos en Documents

Si aparece un zip tipo `drive-download-*` o `<N>TA SEMANA-*.zip` suelto en la raíz de `Documents`
(no dentro de la estructura del pipeline) y su contenido ya fue absorbido por el pipeline
(comparar nombres de archivo con lo que ya existe en `input/` o `output/` del proyecto
correspondiente) → proponer borrado directo, es una descarga duplicada.

## 5.4 Librerías de producción — no confundir con datasets

Si `Documents` tiene carpetas de librerías de trabajo activo (samples de audio, presets, assets
de una app que las espera ahí) **no son parte de esta fase** — ver guardrail en
`00-orientacion/playbook.md`. Proponer reubicación a `~/Cowork/<workspace>/` solo si el usuario
confirma que no rompe la integración con la app que las usa; por defecto, no tocar.
