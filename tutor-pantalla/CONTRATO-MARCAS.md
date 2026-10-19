# Contrato: marcas en SVG, Reajustar 🎯, señalar y preguntar (2026-10-18)

Lo que cada pieza promete a las demás. Nadie cambia una firma de aquí sin avisar al orquestador.

## Dueños (un archivo, un dueño)

| Quién | Archivos |
|---|---|
| **Orquestador (Opus)** | `ojos_panel.py`, `reajustar.py` (nuevo), `marcador.py` (nuevo), este contrato, `para-claude-design/` |
| **Sonnet A — dibujo y movimiento** | `dibujante.js`, `formas_marcas.js` (nuevo), `capa.py`, `muestras/marcas.json` (nuevo), `probar_dibujos.py` |
| **Sonnet B — paneles** | `panel.html`, `panel_pantalla.py`, `panel_curso.py` (tutor-pantalla), `panel-excel/panel.html`, `panel-excel/panel_web.py`, `prueba-dia/panel_dia.py`, `marcas_ui.js` (nuevo) |
| **Sonnet C — señalar y preguntar** | `senalar.py` (nuevo), `senalar_ui.js` (nuevo) |

`ojos_ui.js`, `preguntas_ui.js`, `prueba-dia/overlay_dia.py` y `DIBUJOS.md`/`README.md` no los toca nadie hasta el final (el orquestador los actualiza al juntar).

## 1. Capas por grupo (`capa.py`, Sonnet A)

- `{"cmd": "poner", "grupo": "marcas" | "dibujos", "pids", "panel", "capas", "deslizar": bool}`: reemplaza **solo las capas de ese grupo** (sin `grupo` = `"dibujos"`, como hoy). Los `pids` (cuándo se ven) se guardan por grupo.
- `deslizar: true`: si una capa nueva tiene el mismo `id` que una del mismo grupo que ya estaba, aparece en la posición vieja y llega a la nueva en ~250 ms (con suavizado). Las capas nuevas sin pareja entran normal.
- `{"cmd": "borrar", "grupo": "marcas"}` borra un grupo; sin `grupo`, todo.
- `{"cmd": "latir", "id"}`: esa capa late ~1.2 s (opacidad o brillo) y vuelve a la normalidad. No recompone si no hace falta.
- Lo de hoy (`reproducir`, `estado`, `volcar`, lupa, `WDA_EXCLUDEFROMCAPTURE`) sigue igual.

## 2. La forma `"marca"` (`formas_marcas.js`, Sonnet A)

La flecha de siempre (marco redondeado alrededor del objetivo + nota que no tapa botones + flecha de la nota al marco), ahora en SVG. Entrada `d`:

```
{"forma": "marca", "id": "m1", "hwnd": 123, "cliente": [w, h], "escala": 1.25,
 "r": [x, y, w, h],              // coordenadas de CLIENTE; null si "fuera"
 "texto": "Negrita", "n": 2, "color": "azul|verde|rojo|naranja|amarillo|morado",
 "tema": "claro" | "oscuro" | null,       // fondo de la app detrás: oscuro → nota en versión oscura
 "fuera": null | "arriba" | "abajo" | "izquierda" | "derecha",   // lo señalado quedó fuera de la vista
 "entrada": true,                // anima la entrada (~350 ms, no se repite)
 "evitar": [[x, y, w, h], ...]}  // botones que la nota no debe tapar (cliente)
```

- Devuelve **una capa por marca** con `id = d.id` (para que `deslizar` y `latir` funcionen por marca) y `ocupa` con la caja de la nota.
- `n` va dentro de un círculo delante del texto (no «2.»).
- `fuera`: una pastilla pegada a ese borde del cliente con una flecha hacia fuera y el texto «↓ Negrita, más abajo» (arriba/izquierda/derecha igual).
- Las piezas visuales van en funciones aparte (`Marcas.piezas.nota/marco/numero/flecha/borde`) con parámetros `{color, tema, escala, texto}` → `{svg, w, h}`: ahí entrará luego el diseño de Claude Design sin tocar la colocación.
- `Dibujante.ponerMarcas(lote, opc)`: renderiza un lote de `"marca"` y llama `api.capa_poner({capas, grupo: "marcas", deslizar: opc.deslizar})`. Devuelve `{capas, errores}`. Lote vacío → `api.capa_borrar("marcas")`.
- `Dibujante.mostrar(lote, texto, opc)` acepta `opc.deslizar` (y `opc.sinVoz`) y pone sus capas con `grupo: "dibujos"`.
- `Dibujante.marcasPuestas()` → `[{id, texto}]` de las marcas y dibujos con texto que hay ahora (para el texto enlazado).

## 3. `marcador.py` (orquestador): el sustituto de `overlay_dia.py`

Misma forma de uso que el `Overlay` de hoy, así nadie más cambia: `orden({"cmd": "mostrar", "pids", "panel", "marcas": [{hwnd, ventana, rect, texto, color, n, evitar}]})`, `orden({"cmd": "borrar"})`, `vivo()`, `cerrar()`; y `mostrar(marcas, pids, panel)` / `borrar()` como `OverlayDia` de Dia. Convierte a la forma `"marca"` (con la escala `ventana`→cliente de overlay_dia) y las manda a la página con `js("Dibujante.ponerMarcas(...)")`.

- `js` es una función que recibe código y lo corre en la página del panel: `Ojos(..., js=None)`; el panel la da con `ojos.poner_js(lambda c: self._ventana.evaluate_js(c))`. **Sin `js` (o sin `Dibujante` en la página) usa `overlay_dia.py` como hoy**: nada se rompe a medio camino.
- Campos extra opcionales por marca: `"tema"`, `"fuera"`, `"id"`.

## 4. Reajustar (orquestador: `ojos_panel.py` + `reajustar.py`)

- `Ojos.reajustar()` → `{"ok", "movidas": n, "fuera": n, "perdidas": ["Negrita", ...], "dibujos": lote | None, "tarjeta": tarjeta_volver | None, "mensaje": "Reajusté 3 marcas; no encontré «Negrita»."}`. Las marcas las vuelve a poner él mismo (con `deslizar`); los dibujos los devuelve en `dibujos` para que la página los muestre con `Dibujante.mostrar(lote, "", {deslizar: true, sinVoz: true})`.
- `OjosApi.reajustar()` (lo llama la página) = `self._ojos.reajustar()`. **Cada panel que tenga lo suyo** (Dia: «En Dia: dónde se hace»; curso: «Señálamelo»; Excel: nada extra) lo registra: `ojos.registrar_rehacer("senalar", fn)`, con `fn()` → `{"movidas", "fuera", "perdidas"}` que vuelve a ubicar y llama a `ojos.ov.orden(... "deslizar": True)` o `marcador.mostrar(..., deslizar=True)`. `ojos.quitar_rehacer("senalar")` al borrar.
- Cómo ubica: control con nombre → se vuelve a leer la lista (sin imagen); celda/nombre/en/línea → el `resolver` de siempre; solo imagen → busca el trozo en la ventana, leída solo en la PC (nunca se guarda ni sale).

## 5. Botón 🎯 y texto enlazado (`marcas_ui.js`, Sonnet B)

- `marcas_ui.js` va en `SCRIPTS_UI` (el orquestador lo añade): pone el botón **🎯 Reajustar** junto a «Borrar flechas»/la cámara en los dos HTML (`panel.html` del asistente y `panel-excel/panel.html`, que usan Excel, Dia y el curso). Al pulsar: `api.reajustar()` → `Dibujante.mostrar(r.dibujos, "", {deslizar: true, sinVoz: true})` si hay → `r.mensaje` como nota corta en el chat → `r.tarjeta` con la tarjeta de «¿Vuelvo a mirar?» que ya existe. Desactivado (gris) si no hay marcas ni dibujos.
- **Texto enlazado**: al terminar de pintar una respuesta, `MarcasUI.enlazar(nodoRespuesta)` busca en el texto la primera aparición de cada `texto` de `Dibujante.marcasPuestas()` (sin mayúsculas ni acentos) y la envuelve en `<span class="ancla-marca" data-capa="m1">`; al pasar el ratón → `api.capa_latir(id)`.
- Python de cada panel: `ojos.poner_js(...)`, `registrar_rehacer` donde toque, y `capa_latir` en `OjosApi` (lo pone el orquestador).

## 6. Señalar y preguntar (`senalar.py` + `senalar_ui.js`, Sonnet C)

- Botón ✏️ «Señalar» junto a 📷 (lo pone `senalar_ui.js`). Elige la ventana igual que 📷 (la lista de `ojos_ui.js`: `api.ojos_ventanas`), o la última aprobada si la hay.
- `senalar.py`: proceso aparte con una ventana en capas **encima del cliente de esa ventana** que, solo mientras dura, sí recibe el ratón: se arrastra para encerrar (trazo a mano visible), Esc o clic derecho cancela, al soltar devuelve `{"ok", "trazo": [[x, y], ...] en cliente, "caja": [x, y, w, h]}`. Se cierra sola al terminar o a los 60 s.
- Luego **la vista previa de siempre** (`ojos_capturar` → Adjuntar / Recortar / Cancelar) con el trazo dibujado en la imagen; el adjunto lleva la imagen con el trazo y en el contexto «Encerró la zona x,y,w,h; controles dentro: …». Nada sale sin su clic en Adjuntar y sin enviar.
- Lo que la página llama: `api.senalar_empezar(hwnd)` → `{ok, trazo, caja}` (bloquea hasta que suelta) y `api.senalar_capturar(hwnd, trazo)` → lo mismo que `ojos_capturar` pero con el trazo pintado. Clase mixin `senalar.SenalarApi` que usa solo lo público de `self._ojos` (`capturar`, `capturas`, `pendiente`); el orquestador la añade a `OjosApi` y `senalar_ui.js` a `SCRIPTS_UI`.

## Verificación (todas las piezas)

- Cada Sonnet lanza **un solo Haiku**, sin contexto, que revisa **capturas** de lo hecho (tiras de `probar_dibujos.py`, capturas del panel con `herramientas/captura.js` o `--probar`), y lo reutiliza con SendMessage. El informe dice qué miró el Haiku.
- Pruebas en vivo **solo con ventanas propias** (un Word, Bloc de notas o Paint que abra el agente), nunca las del usuario. Nada de capturas de la pantalla entera.

## 7. Ilustraciones en el chat (Sonnet D, añadido el 2026-10-18)

- **Dueño:** Sonnet D: `ilustraciones_ui.js` (nuevo), `formas_fijas.js` (solo para exponer su filtro de SVG, sin cambiar lo demás) y la función `limpiar` de `dibujante.js` (la voz). En `panel.html` y `panel-excel/panel.html`, solo después de que el orquestador avise que Sonnet B terminó.
- **Formato:** el que escriben los tutores, en `REGLAS_ILUSTRACIONES` de `ojos_panel.py` (léelo: es el contrato con los tutores):
  - `$...$` y `$$...$$`: MathJax, que ya está en `vendor/` y se carga con `Dibujante.U.cargar('mathjax')`. El botón 📋 LaTeX en las grandes y clic para copiar en las pequeñas, con `$...$`/`$$...$$` (preferencia de él).
  - ` ```svg Pie ` → la figura filtrada, con colores por nombre que siguen el tema del panel.
  - ` ```grafica {json} ` → una gráfica exacta en SVG, hecha por el panel con un intérprete de expresiones propio (nunca `eval`/`Function`).
- **Botones en cada figura:** Ampliar (a pantalla completa, Esc cierra), Copiar SVG, Guardar PNG (descarga) y «Ponlo en la app»: `Dibujante.mostrar({dibujos: [{forma: "svg", ...}]})` sobre la última ventana. Esto necesita un `api.ilustracion_en_app(svg)` en Python, que da el orquestador: devuelve el lote o `{ok: false, error}` si no hay ventana vista.
- **Página:** `Ilustraciones.procesar(nodo)` tras pintar cada respuesta del tutor. Si la respuesta llega a trozos, con el bloque a medias se ve «dibujando…», nunca el código crudo. Las dos páginas deben dar el mismo resultado. Claro y oscuro (los dos paneles usan `light-dark()` y `data-theme`).
- **Voz:** no lee el SVG ni el JSON. Una fórmula se lee como «(fórmula)».
