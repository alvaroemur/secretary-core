# Fase 4 — Migración a Drive

Aplica a: grabaciones (OBS, Riverside), fotos que se decida conservar, y cualquier archivo local
sin espejo en Drive que el usuario confirme migrar. Doctrina P1/P2 completa:
`~/.secretary/rules/drive-cowork.md`.

## 4.1 Nunca automático

Subir a Drive y borrar el local **siempre** pasa por confirmación del usuario primero (categoría
completa, no archivo por archivo — ver batching en fase 3.4). Es contenido no regenerable: el
error de subir mal o borrar antes de verificar es costoso.

## 4.2 Buscar o crear la carpeta destino

```bash
# Buscar si ya existe una carpeta de la corrida anterior (ej. "Grabaciones OBS", "Riverside")
gog drive search "<nombre>" --max 10 --plain

# Si no existe, crear bajo la raíz temática correspondiente (ver taxonomía drive-cowork.md)
gog drive mkdir "<nombre carpeta>" --parent <folder-id-padre> --plain
```

**Reutilizar carpetas existentes** entre corridas — no crear una carpeta nueva por mes para el
mismo tipo de contenido (ej. "Riverside — entre rutas y horizontes" ya existe desde julio; los
videos de agosto van ahí mismo, no a una carpeta "Riverside agosto").

## 4.3 Subir en background y verificar antes de borrar

```bash
gog drive upload "<archivo>" --parent <folder-id> --plain
```

- Archivos grandes (>500M) o varios en lote → correr con `run_in_background: true`.
- **Verificar** con `gog drive ls --parent <folder-id> --plain` que el conteo de archivos subidos
  coincide con lo esperado, o revisar el output por línea `link` (una por archivo) antes de
  cualquier `rm` del local.
- Nunca encadenar upload + rm en el mismo comando sin el paso de verificación entre medio.

## 4.4 Cuándo usar subagente para clasificar antes de subir

Si hay más de ~20 archivos a clasificar visualmente (screenshots, fotos sin nombre descriptivo)
antes de decidir destino, delegar a un subagente con modelo económico (`haiku`) en vez de leer
cada imagen en la sesión principal — libera contexto y es más barato. Ver precedente: sesión
2026-07-06, subagente clasificó 81 screenshots del Escritorio contra el mapa de proyectos.

Prompt del subagente debe incluir: el mapa de proyectos completo (fase 3.2 / `orden-local.md`
§2), la regla de "ante la duda, `_tmp`", y la instrucción de mover con `mv` (nunca borrar) más un
manifiesto CSV de salida para que la sesión principal pueda auditar el resultado.

## 4.5 Registrar la carpeta usada

Si se crea una carpeta nueva en Drive, anotar su nombre y propósito en la política
`orden-local.md` §2 (o en la memoria del drone si es un caso puntual) para que la próxima corrida
la reutilice en vez de buscarla de cero.
