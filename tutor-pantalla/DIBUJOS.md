# Dibujos encima de la app (contrato)

Cómo viaja un dibujo, desde lo que escribe el tutor hasta lo que se ve encima de la app:

```
tutor / asistente           Python (ojos_panel.Ojos.dibujos)        página (dibujante.js + formas_*.js)       capa.py
{"tipo": "dibujo", ...}  →  resuelve el objetivo a píxeles      →   dibuja en SVG y lo pasa a PNG        →   lo pega encima
                            de la ventana (lote)                     (capas)                                  de la ventana y anima
```

Todas las coordenadas van en **píxeles físicos del área de cliente** de la ventana objetivo (`ojos.cliente(hwnd)`),
con (0, 0) arriba a la izquierda del área de cliente. `escala` = ppp de la ventana / 96 (1.25 en su PC): los tamaños
de letra y grosores se multiplican por ella.

## 1. La marca (lo que escribe el tutor)

En el asistente va en la línea `MARCAS: [...]`; en los tutores, dentro de `<marcas>`. Siempre `"tipo": "dibujo"`:

```json
{"tipo": "dibujo", "forma": "foco", "id": 12, "texto": "Aquí", "decir": "Fíjate en este botón", "color": "azul"}
```

Objetivo (uno de estos; lo resuelve Python):
- `"id": 12` — control de la última captura que mandó la persona;
- `"caja": [x, y, w, h]` — píxeles de esa captura;
- `"celda": "D5"` (y `"hoja"` opcional) — Excel: la celda en pantalla (por COM, solo lectura);
- `"nombre": "Lápiz"` — modo curso: el control por su nombre (UI Automation en vivo).

Comunes: `"color"` (azul, verde, rojo, naranja, amarillo, morado), `"texto"` (nota corta), `"decir"` (lo que dice la
voz; si falta, se usa `texto`), `"n"` (número de orden).

| forma | qué es | parámetros propios |
|---|---|---|
| `foco` | oscurece la ventana menos el objetivo | `oscuro` (0–1, 0.55) |
| `teclas` | teclas que se pulsan | `teclas`: `["Ctrl", "S"]` (objetivo opcional: salen junto a él; si no, abajo al centro) |
| `mano` | trazo a mano alzada que se va dibujando | `trazo`: `circulo` \| `subrayado` \| `flecha` \| `tache` \| `check` |
| `lupa` | la zona, aumentada al lado y **en vivo** | `aumento` (2.5). Solo en una ventana que la persona ya aprobó |
| `svg` | el dibujo propio del tutor, encajado en el objetivo; puede ir **animado** (SMIL o CSS `@keyframes`) | `svg`: `"<svg viewBox=...>...</svg>"` (se filtra) |
| `fantasma` | cursor animado que hace los pasos | `pasos`: `[{"accion": "mover"\|"clic"\|"doble"\|"derecho"\|"arrastrar"\|"escribir", objetivo, "hasta": objetivo (arrastrar), "texto": (escribir), "decir"}]` |
| `guia` | contorno punteado que se dibuja: «hazlo aquí» | `figura`: `rect` \| `elipse` \| `linea` \| `flecha` |
| `secuencia` | 1 → 2 → 3 en orden, con flechas curvas | `pasos`: `[{objetivo, "texto", "decir"}]` |
| `formula` | la fórmula bien escrita, flotando junto al objetivo | `latex`; en Excel con `celda` sola sale de la celda, y `grafica: true` añade la mini gráfica |
| `rayos_x` | Excel: de las celdas que usa la fórmula al resultado, con los valores viajando | `celda` |
| `desarmar` | copia ampliada del texto con una llave y una explicación por parte | `original` (en Excel, con `celda`, sale de la celda), `partes`: `[{"texto", "nota"}]` |

**Objetivo `"linea"` (cursos de código).** Además de `id`, `caja`, `celda` y `nombre`, un dibujo (o un paso de `fantasma`/`secuencia`) puede apuntar a una línea del editor de VS Code: `{"tipo": "dibujo", "forma": "foco", "linea": 14, "archivo": "Prueba.java", "texto": "Aquí"}`. `archivo` es opcional (si no es el abierto, el dibujo no sale y el tutor lo sabe). El panel lo ubica con `editor_vscode.rect_linea` (ver README, «Señalar una línea del editor»); si la línea no se ve, se dibuja en el borde del editor y se añade «Sube/Baja…» a la respuesta. Necesita `Ojos(raices=[carpetas del curso])`.

## 2. El lote (Python → página)

`Ojos.dibujos(marcas, resolver)` devuelve `(resto, lote)`; la respuesta del panel lleva `"dibujos": lote` y la página
llama `Dibujante.mostrar(lote, texto_respuesta)`. Cada dibujo del lote:

```json
{"id": "d1", "hwnd": 123, "cliente": [1600, 900], "escala": 1.25, "forma": "foco",
 "r": [410, 62, 48, 46], "color": "azul", "texto": "Aquí", "decir": "Fíjate en este botón", "n": null,
 "evitar": [[x, y, w, h], ...]}
```

- `r`: el objetivo ya en píxeles de cliente (o `null` si no tiene).
- `evitar`: cajas de los demás controles (las notas no deben taparlos).
- Los pasos (`fantasma`, `secuencia`) llevan cada uno su `r` (y `hasta_r` en arrastrar).
- `lupa`: además `"en_vivo": true` (Python solo la deja pasar si la ventana está aprobada).
- `rayos_x`: `"valor"` (texto de la celda), `"formula"` (local), `"fuentes": [{"ref": "B2", "r": [...] | null, "valor": "15"}]` (`r` null si la celda no se ve).
- `formula`: `"latex"`, y con `grafica`: `"grafica": {"valores": [..], "etiquetas": [..], "linea": {"valor": 56.2, "texto": "promedio"} | null}`.
- `desarmar`: `"original"`, `"partes"`.

## 3. La capa (página → Python → capa.py)

La página devuelve una o más capas por dibujo. `api.capa_poner({"capas": [...]})` las pone todas (y quita las de
antes):

```json
{"id": "d1", "hwnd": 123, "x": 380, "y": 30, "w": 300, "h": 200,
 "fondo": "data:image/png;base64,...",
 "fotos": ["data:image/png;base64,...", ...], "fps": 30,
 "piezas": [{"png": "data:image/png;base64,...", "ax": 3, "ay": 2,
             "ruta": [[0, 10, 10, 1, 1], [600, 120, 80, 1, 0.9], [800, 120, 80, 0, 1]]}],
 "duracion": 1600, "repetir": true, "pausa": 900, "tramos": [[0, 800], [800, 1600]],
 "lupa": {"zona": [410, 62, 48, 46], "en": [10, 10, 120, 115], "radio": 14, "fps": 8}}
```

- `x, y, w, h`: dónde va la capa, en píxeles de cliente (la página ya la recorta al área de cliente).
- Se dibuja en este orden en cada fotograma: `fondo` → `fotos[i]` → `lupa` → `piezas`.
- `fotos`: fotogramas del mismo tamaño que la capa; el `i` es `floor(t · fps / 1000)` y al acabarse queda el último.
- `piezas`: imágenes pequeñas que siguen su `ruta` (`[t_ms, x, y, alfa 0–1, escala]`, interpoladas en línea recta
  entre claves; antes de la primera y después de la última, quieta en esa clave). `(ax, ay)` es el punto de la pieza
  que va en `(x, y)` (la punta del cursor).
- `duracion` 0 = fija. `repetir`: al terminar vuelve a empezar tras `pausa` ms.
- `tramos`: partes de la animación para la voz (`api.capa_reproducir(id, desde, hasta)`).
- `lupa`: capa.py lee esa zona de la pantalla (solo esa) unas `fps` veces por segundo y la pinta aumentada en `en`
  con esquinas redondeadas de `radio`. Nunca se guarda ni sale de la PC.

Órdenes de capa.py (una línea JSON por stdin, responde una por stdout):
`{"cmd": "poner", "pids": [...], "panel": hwnd, "capas": [...]}` · `{"cmd": "reproducir", "id", "desde", "hasta"}` ·
`{"cmd": "borrar"}` · `{"cmd": "estado"}` · `{"cmd": "volcar", "carpeta"}` · `{"cmd": "salir"}`.
Con `"auto": false` en la capa, espera quieta en t = 0 hasta un `reproducir` (lo usa la voz); `reproducir` con
`"desde": null` la deja andar sola otra vez (al terminar la narración).

## 4. Las formas (página)

`dibujante.js` es el núcleo; cada `formas_*.js` registra sus formas:

```js
Dibujante.registrar('foco', async function(d, U){ ... return capa | [capas]; });
```

Utilidades `U` (todas en píxeles de cliente; `d.escala` para tamaños):
- `U.color(nombre)` → `"#rrggbb"`; `U.esc(texto)` → texto seguro para SVG.
- `U.medir(texto, px, negrita)` → ancho en px (Segoe UI, igual que en el SVG).
- `U.svg(w, h, contenido)` → `<svg>` completo con las fuentes del panel.
- `U.png(svg, w, h)` → `Promise<dataURL>`.
- `U.capa(d, caja, contenido, extra)` → `Promise<capa>`: rasteriza `contenido` (SVG en coordenadas de cliente) dentro de
  `caja` [x, y, w, h], la recorta al cliente y devuelve la capa con `extra` mezclado (piezas, fotos, duracion…).
  **En `extra`, las rutas de las piezas y `lupa.en` van en coordenadas de cliente**: U.capa las pasa a las de la capa.
  `contenido` puede ser `''` (capa sin fondo, solo fotos o piezas).
- `U.fotos(d, caja, n, f)` → `Promise<[dataURL]>`: `f(k, n)` devuelve el SVG (coordenadas de cliente) del fotograma `k`.
- `U.pieza(contenido, w, h)` → `Promise<{png, w, h}>`: una imagen suelta (contenido en coordenadas 0..w, 0..h).
- `U.nota(d, texto, opc)` → `{svg, caja}`: la nota con flecha hacia `d.r`, en un hueco que no tape `d.evitar` ni otras
  notas del mismo lote (`opc`: `{color, cerca: [x, y, w, h], flecha: false}` para una nota sin flecha).
- `U.flecha(x1, y1, x2, y2, {color, grosor, curva})` → SVG de una flecha (curva > 0 la dobla).
- `U.ocupar(d, caja)`: las notas siguientes no caen ahí. El núcleo ya ocupa la caja de cada capa devuelta (salvo las que
  cubren casi todo el cliente, como el foco); si la capa trae `ocupa: [[x, y, w, h], ...]` (coordenadas de cliente: la
  tarjeta, las notas), ocupa solo eso. Cada forma recibe en `d.evitar` también lo que ocupan los dibujos anteriores
  del lote (menos lo que cubre su propio objetivo), marcado con la propiedad `fuerte` (pisarlo pesa mucho más que tapar
  un botón): si respeta `d.evitar`, no los pisa.
- `U.cargar('rough' | 'mathjax')` → `Promise` (las librerías de `vendor/`).
- `U.tex(latex, {px, color})` → `Promise<{svg, w, h}>` (MathJax a SVG, ya con tamaño en px).

`Dibujante.renderizar(lote)` → `Promise<{capas, narracion, errores}>` (sin tocar nada: lo usa el banco de pruebas).
`Dibujante.mostrar(lote, texto)` → renderiza, llama `api.capa_poner` y, con la voz encendida, narra.

**SVG animado:** si el SVG trae `<animate>`, `<animateTransform>`, `<animateMotion>`, `<set>` o CSS con `@keyframes`,
la forma `svg` lo pasa a fotogramas (≤ 60, a ~15 por segundo) y capa.py los repite. SMIL: para el instante t, cada
animación empieza t segundos antes (el SVG pasado a imagen se pinta en su instante 0). CSS: Chrome no anima el CSS de
un SVG pasado a imagen, así que se mete escondido (en un shadow root) en la página, se lleva cada animación a t con
Web Animations y sus valores quedan fijos en el estilo. Lo que se repite se graba un ciclo (mínimo común múltiplo de
sus duraciones, tope 6 s) desde que ya empezaron todas, para que el bucle no salte. No se animan `href` ni `on*`.

## 5. Probar sin panel

`python probar_dibujos.py <muestras.json> <carpeta> [--fondo captura.png]` abre las formas en el Chrome instalado,
compone los fotogramas igual que capa.py (`capa.fotograma`) y guarda por cada muestra `<id>_tira.png` (6 momentos)
y `<id>_final.png`. Las muestras son un lote (sección 2) con `"cliente"` del tamaño del fondo.
