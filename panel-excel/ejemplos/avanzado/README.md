# Curso de ejemplo: Excel avanzado

Curso corto para probar y copiar lo avanzado del panel (`../../README.md`). Cuatro módulos:

| Módulo | Qué muestra | «Tu turno» |
|---|---|---|
| `m1_matrices.json` | UNICOS + ORDENAR que se desbordan | FILTRAR en G2 (se compara todo lo desbordado; `#¡DESBORDAMIENTO!` con su mensaje) |
| `m2_graficos.json` | un gráfico de líneas puesto por la lección con el modo libre | gráfico de columnas con título y sin leyenda, y escala de colores (`pide`; error típico: circular o líneas) |
| `m3_power_query.json` | una consulta que limpia la tabla Clientes y otra que lee `datos/ventas.csv` | filtrar Lima en la tabla de la consulta (`pide` → `filtro`) |
| `m4_vba.json` | una macro de ejemplo (`EjemploM4`) puesta por la lección | la macro NegritaTotales (`macro` + `solucion_vba`, error típico) |

```
python panel-excel/panel_web.py panel-excel/ejemplos/avanzado/curso.json            # abrir el panel
python panel-excel/panel_web.py panel-excel/ejemplos/avanzado/curso.json --probar    # probarlo sin ventana
```

## Historia y decisiones

- **2026-10-08:** creado junto con lo avanzado del panel, para que sirva de plantilla. Usa `"macros": true` (libro `.xlsm`) y `"datos": "datos"` (la única carpeta de fuera del libro que pueden leer sus consultas). El módulo 4 pide «Confiar en el acceso al modelo de objetos de proyectos de VBA»: sin él, el panel lo explica en la pestaña Lección, el ejemplo de la macro no se pone y Comprobar no ejecuta nada.

## Archivos

- `curso.json`: el curso (título, libro, macros, carpeta de datos y módulos).
- `m1_matrices.json` … `m4_vba.json`: los módulos (formato en el README del panel).
- `datos/ventas.csv`: datos de ejemplo para Power Query.
- Se generan solos (no se editan ni van al repositorio): `Curso_Avanzado.xlsm` (el libro del curso) y `progreso_panel.json` (dónde se quedó).

## Cómo cambiarlo

1. Edita el JSON del módulo (o copia uno para un curso nuevo y añádelo a `modulos`).
2. Prueba sin ventana con `--probar` (texto de cada paso, la revisión de FILTRAR con la solución y los errores, y que los ejercicios de objetos y de VBA digan «vacío» sin hacer nada).
3. Ábrelo con el panel y prueba el «Tu turno» con respuestas buenas y malas.

Depende de lo mismo que el panel (Excel, `pywin32`, `pywebview` y Claude Code para el tutor).
