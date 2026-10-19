# Contrato de las figuras 3D (2026-10-19)

Figuras 3D en SVG, exactas y girables, en tres sitios: el **chat de todos los tutores** (bloque ` ```3d `), la **Tarjeta SVG** (el guion de Geometría acepta 3D) y **encima de la app** (forma de dibujo `"3d"`, girando sola despacio). Un solo motor para los tres: `motor_3d.js`.

Nadie cambia una firma de este contrato sin avisar al orquestador.

## Dueños

| Quién | Archivos |
|---|---|
| **Orquestador (Opus)** | `motor_3d.js`, `probar_3d.js`, `motor_figuras.js` (el intérprete ya acepta varias variables), este contrato, `SCRIPTS_UI` y `FORMAS` en `ojos_panel.py` (ya llevan `motor_3d.js`, `formas_3d.js` y `"3d"`) |
| **Sonnet A · chat** | `ilustraciones_ui.js`, `probar_ilustraciones.js`, la constante `REGLAS_ILUSTRACIONES` de `ojos_panel.py` (solo ese bloque) |
| **Sonnet B · tarjeta** | `tarjeta-svg/pestana_geometria.js`, `tarjeta-svg/tarjeta.html` (solo lo que toca el lienzo girable y el botón de MathStudio en 3D), `tarjeta-svg/asistente_tarjeta.py` y `pestana_asistente.js` (que el asistente sepa pedir 3D), `tarjeta-svg/CONTRATO.md` y `tarjeta-svg/README.md` |
| **Sonnet C · pantalla** | `formas_3d.js` (nuevo), `DIBUJOS.md`, `probar_dibujos.py`, `muestras/3d*.json`, y en `ojos_panel.py` solo: la constante `REGLAS_DIBUJOS`, `CON_OBJETIVO` si hace falta, la validación de la forma `"3d"` y el método nuevo `ilustracion3d_en_app` |

`ojos_panel.py` lo tocan A y C en bloques distintos: **solo con Edit** (reemplazos puntuales), nunca reescribiendo el archivo entero. El README de `tutor-pantalla/` lo actualiza el orquestador con lo que cada uno entregue en su informe.

## 1. El motor (`motor_3d.js`, ya hecho y probado: `node tutor-pantalla/probar_3d.js`)

Se carga **después** de `motor_figuras.js` (en los paneles ya va en `SCRIPTS_UI`; en la tarjeta, añadir `<script src="/tutor-pantalla/motor_3d.js">` tras el de `motor_figuras.js`). En node: `require('./motor_3d.js')`.

```js
Figuras3D.figura(spec, opts)    // → {svg, w, h, vista:[az, el], errores:[{objeto, mensaje}]}   (con errores dibuja lo válido; svg '' si nada)
Figuras3D.escena(spec, opts)    // → {dibujar(vista, opts2), vista, errores}: se arma una vez y se gira barato
Figuras3D.guion(texto, opts)    // → {svg, w, h, vista, errores:[{linea, mensaje}], spec}   (el guion 3D de Geometría)
Figuras3D.aSpec(texto)          // → {spec, errores}
Figuras3D.aGuion(spec)          // → el guion equivalente (para «Editar en la tarjeta»), o null si algo no tiene comando
Figuras3D.es3d(texto)           // → ¿el guion de Geometría es 3D? (un punto (x,y,z) o un comando que solo existe en 3D)
Figuras3D.girable(el, spec | {guion}, opts)
  // dibuja dentro de `el` y lo gira arrastrando (doble clic: vuelve a la vista inicial). Usa encuadre 'esfera' (el tamaño
  // no cambia al girar) y el modo rápido mientras arrastras. opts.alGirar(vista, rapido) avisa de cada cambio.
  // → {vista(), poner([az, el]), svg(opts2) → figura de la vista actual con encuadre 'justo' (para copiar), errores, ultimo(), destruir(),
  //    cambiar(opts2) → rehace con otras opciones (anotaciones, relleno, tema…) en la misma vista, opciones()}
Figuras3D.vistasGiro(vista, 'vaiven' | 'vuelta', n)   // → n vistas de una animación (vaivén ±30° suave; vuelta 360°)
Figuras3D.fotogramas(spec | {guion} | escena, opts)  // solo navegador → Promise<{fotos: [dataURL PNG], ms, w, h}>
  // opts: los de la figura (tema, tam, fondo, anotaciones, relleno…) + vista, giro ('vaiven' | 'vuelta'), n (8–72, 48 por defecto).
  // Tamaño fijo (encuadre 'esfera'). Vaivén: 4 s por ciclo; vuelta: 6 s. Con fondo '' los PNG son transparentes.
```

`opts`: los de `Figuras` (`tema: 'claro'|'oscuro'`, `tam: 'S'|'M'|'L'`, `ancho`, `fondo: 'transparente'|'blanco'|'tema'|'#hex'`, `paleta` del panel) y además `vista: [az, el]` en grados, `encuadre: 'justo'|'esfera'`, `rapido`,
`anotaciones: {ejes, numeros, nombres, medidas}` (false apaga; manda sobre la spec; se aplican al dibujar) y `relleno: 'opaco'|'transparente'` (manda sobre la `opacidad` de cada objeto; sin él, cada objeto la suya).
- **ejes:** ejes, flechas y rótulos x, y, z (sin ejes, la figura se encuadra sin ellos). **numeros:** los números de los ejes. **nombres:** nombres de puntos y vectores y las `etiqueta`. **medidas:** cotas y `distancia`, ángulos (arcos, valores, cuadradito) y marcas de lados iguales.

**Cómo dibuja:** proyección ortográfica y pintor (caras de atrás hacia adelante). Cada sólido convexo opaco tapa: sus aristas ocultas y lo que pasa detrás de él (un eje, una recta) salen **a trazos**; los puntos tapados salen **huecos**. Un polígono dentro de un plano se pinta con el plano sin pelearse.

## 2. La spec JSON (lo que escribe el tutor en ` ```3d `)

```json
{"titulo": "…", "pie": "…", "vista": [30, 22], "ejes": true, "numeros": true, "proporcion": "auto",
 "x": [-2, 2], "y": [-2, 2], "z": [-1, 3],
 "objetos": [ {"tipo": "…", …}, … ]}
```

- `vista`: [giro, altura] en grados. Por defecto [30, 22] (x hacia ti, y a la derecha, z arriba); con una revolución, [-70, 18] (eje x horizontal).
- `proporcion`: `auto` estira los ejes solo si hay una superficie z = f(x, y) muy alta o muy plana; `igual` o `cubo` a mano.
- `ejes`, `numeros`, `nombres`, `medidas` (true por defecto) y `relleno` (`"opaco"` | `"transparente"`): lo mismo que las opciones de arriba, escrito en la figura.
- `x`, `y`, `z` (opcionales): la caja de la escena (los planos, rectas y campos se recortan a ella).
- **Atajos:** `{"superficie": "x^2-y^2", "x": [-2, 2], "y": [-2, 2]}` y `{"revolucion": "sqrt(x)", "x": [0, 4], "angulo": 300}`.
- Todo objeto acepta `color` (azul, rojo, verde, morado, naranja, turquesa, amarillo, tinta, acento o #hex), `opacidad` (0.05–1) y `nombre`. Los números pueden ser expresiones (`"2*pi"`, `"sqrt(2)"`).

| tipo | campos |
|---|---|
| `superficie` | `f` (en x, y), `x`, `y`, `z` (recorte opcional), `n` (rejilla, 4–60), `malla` (true), `color` (por defecto `"altura"`: color según z) |
| `parametrica` | `x`, `y`, `z` (en u, v), `u`, `v` |
| `revolucion` | `f`, `g` (opcional: la otra curva; arandelas), `x: [a, b]`, `eje` (`"x"`, `"y"`, `"y=2"`, `"x=-1"`), `angulo` (360; menos deja ver el corte), `corte` (disco o arandela en ese valor), `capa` (casquete cilíndrico en ese valor). Los ejes se rotulan x, y (arriba), z (fondo), como en el libro |
| `curva` | `x`, `y`, `z` (en t), `t: [a, b]`, `flecha` |
| `punto` | `en`, `nombre` |
| `segmento` | `de`, `a`, `guion` (bool) |
| `recta` | `por: [A, B]` |
| `vector` | `de` (origen por defecto), `a` o `v` |
| `poligono` (`triangulo`) | `puntos` |
| `plano` | `por: [A, B, C]` · `ecuacion: "2x + y - z = 3"` · `normal` + `punto` |
| `cubo` | `en` (esquina) o `centro`, `lado` |
| `caja` | `de`, `a` (esquinas opuestas) |
| `prisma` | `base: [puntos]`, `altura` (número, perpendicular a la base, o vector) |
| `piramide` (`tetraedro`) | `base`, `apice` |
| `cilindro` | `de`, `a` (centros de las bases), `radio` |
| `cono` | `base` (centro), `apice`, `radio` |
| `esfera` | `centro`, `radio`, `ecuador` (true) |
| `malla` | `vertices`, `caras` (índices) |
| `carga` | `en`, `q` (signo y valor) |
| `campo` | `E: ["ex", "ey", "ez"]` (en x, y, z) o nada (lo calcula de las cargas; si están en un plano, lo dibuja en ese plano), `n` |
| `etiqueta` | `en`, `texto` |
| `cota` | `de`, `a`, `texto` (por defecto la longitud) |
| `angulo` | `a`, `b` (vértice), `c`: arco y valor en grados (si es recto, el cuadradito) |
| `marcaangulo` | `a`, `b`, `c`, `n` (1–3 arcos, para ángulos iguales; sin número) |
| `angulorecto` | `a`, `b`, `c` (el cuadradito; error si no mide 90°) |
| `marcaigual` | `de`, `a`, `n` (1–3 rayitas: lados iguales) |

`poligono` (y `triangulo`) acepta además `"angulos": true`: marca todos sus ángulos con su valor.

## 3. El guion 3D (pestaña Geometría de la tarjeta)

Mismas reglas que el de MathStudio: una instrucción por línea, `nombre = comando(…)`, comentarios con `#` o `//`. **Los puntos llevan nombre**; los sólidos y superficies pueden ir sin él. Al final de cualquier comando: `color=…`, `opacidad=…` y, en revolución, `eje=…`, `angulo=…`, `corte=…`, `capa=…`.

```
A = (0, 0, 0)            B = (2, 0, 0)            M = puntomedio(A, B)
s = segmento(A, B)       r = recta(A, B)          v = vector(A, B) · vector((1, 2, 3))
t = triangulo(A, B, C)   p = poligono(A, B, C, D)
pl = plano(A, B, C) · plano(A, (0, 0, 1)) · plano(2x + y - z = 3)
e = esfera(C, r)         c = cubo(A, lado)        k = caja(A, B)
pr = prisma(A, B, C, altura)        pi = piramide(A, B, C, D, V)        te = tetraedro(A, B, C, D)
ci = cilindro(A, B, radio)          co = cono(centro, ápice, radio)
S = superficie(x^2 - y^2) · superficie(x^2 - y^2, xmin, xmax, ymin, ymax)
C = curva(cos(t), sin(t), t/4, 0, 4pi)
R = revolucion(sqrt(x), 0, 4) · revolucion(x, x^2, 0, 1, corte=0.5) · revolucion(4 - x^2, 0, 2, eje=y, capa=1)
q = carga(A, 1)          E = campo()
d = distancia(A, B)      ang = angulo(A, B, C)
t = triangulo(A, B, C, angulos=si)       marcaangulo(A, B, C, 2)       angulorecto(A, B, C)       marcaigual(AB, 2) · marcaigual(A, B, 1)
etiqueta(A, "texto")     vista(30, 20)     ejes(no)     numeros(no)     nombres(no)     medidas(no)     relleno(opaco | transparente)
proporcion(igual | cubo)
```

`Figuras3D.es3d(guion)` decide si la figura es 3D: basta un punto con tres coordenadas o un comando que solo existe en 3D. Un comando de geometría plana en un guion 3D (circunferencia, arco…) da su error en su línea.

## 4. Chat (Sonnet A)

- Bloque ` ```3d ` (también ` ```3D `) con la spec JSON; `pie` como en ` ```grafica `. Se dibuja con `Figuras3D.girable` en la burbuja, con los colores del panel (`paleta`, como `graficaTexto`) y el ancho del chat. Al cambiar el tema, se redibuja en la misma vista.
- Errores: como los de ` ```grafica ` (aviso corto bajo la figura; lo válido se ve).
- Botones de siempre: **Copiar** (la vista actual, `svg({encuadre: 'justo'})`), **Ponlo en la app** (`api.ilustracion3d_en_app(JSON.stringify(spec), vista)`; si el panel no lo tiene, el de siempre con el SVG de la vista actual) y **Editar en la tarjeta** (`{tipo: 'geometria', guion: Figuras3D.aGuion(spec)}` con `vista(…)` al final del guion; si `aGuion` da null, `{tipo: '3d', spec, vista}`).
- Una pista pequeña y discreta en la figura: «arrastra para girar».
- `REGLAS_ILUSTRACIONES`: un apartado **corto** de ` ```3d ` con 2 ejemplos (una revolución con `corte` y unos sólidos) y la lista de tipos en una línea; cuándo usarlo (volumen, superficies, vectores en el espacio, sólidos) y que mejor ` ```3d ` que dibujar 3D a mano en SVG.

## 5. Tarjeta (Sonnet B)

- En Geometría, si `Figuras3D.es3d(guion)`, la figura es 3D: el lienzo central se gira arrastrando (`girable`) y **Copiar / PNG / arrastrar** salen de la vista actual (en estilo claro, como todo lo que se copia). El botón ↗ MathStudio se apaga en 3D, con un título que diga por qué.
- Resaltado de los comandos 3D en el editor; errores en su línea como en 2D.
- `cargar({tipo: 'geometria', guion})` sigue igual; `cargar({tipo: '3d', spec, vista})` enseña la figura girable sin guion (aviso corto: «viene del chat; puedes girarla y copiarla»).
- El asistente de la tarjeta sabe pedir 3D (el guion de §3) cuando le piden un sólido, una superficie o algo en el espacio.
- Ninguna palabra «Miro» en la interfaz.

## 6. Encima de la app (Sonnet C)

```json
{"tipo": "dibujo", "forma": "3d", "spec": { …la spec de §2… }, "vista": [30, 22], "giro": "vaiven", "caja": [x, y, w, h] | otro objetivo}
```

- `giro`: `"vaiven"` (por defecto: ±30° alrededor de la vista, ida y vuelta, suave), `"vuelta"` (una vuelta entera en bucle) o `"no"`. Despacio: que se vea el volumen sin marear. Fotogramas con `U.fotos` (≤ 60, como el SVG animado).
- Sin objetivo: centrada en la ventana, como `ilustracion_en_app`. Fondo de la figura: el del tema con un borde suave, para que se lea encima de cualquier app.
- `ilustracion3d_en_app(spec_json, vista)` en `ojos_panel.py`: igual que `ilustracion_en_app`, pero con la forma `"3d"`.
- `REGLAS_DIBUJOS` y `DIBUJOS.md`: la forma nueva, corta.

## 7. GIF (2026-10-19, segunda tanda)

- La página saca los fotogramas con `Figuras3D.fotogramas(…)` (con las mismas opciones que se ven: tamaño S/M/L, fondo, anotaciones, relleno, tema claro para copiar) y se los pasa a Python.
- `tutor-pantalla/gif3d.py` (hecho): `guardar_y_copiar(fotos, ms, nombre)` → `{ok, ruta, kb}`: una paleta común con tramado, bucle infinito, guardado en **Descargas** y copiado como archivo (CF_HDROP: al pegar, la app recibe el `.gif`). Con fondo transparente, transparencia de 1 bit. `python tutor-pantalla/gif3d.py --probar`.
- **Botón «GIF»** con dos opciones, **vaivén** o **vuelta entera** (un menú pequeño o un botón partido), en la Tarjeta (junto a «Copiar PNG») y en las figuras 3D del chat. Mientras se arma: «Haciendo el GIF…»; al terminar: «GIF copiado y guardado en Descargas (N KB)».

## 8. Cómo se prueba (cada uno lo suyo, antes de entregar)

- `node tutor-pantalla/probar_3d.js` y `node tutor-pantalla/probar_figuras.js` siguen en «todo bien».
- A: `node tutor-pantalla/probar_ilustraciones.js` + capturas del chat con ` ```3d ` en claro y oscuro, y una de después de arrastrar (puppeteer: el ratón arrastra y la vista cambia).
- B: `python tarjeta-svg/tarjeta.py --probar` + capturas de la tarjeta con un guion 3D (antes y después de girar) y con uno 2D (sigue igual).
- C: `python tutor-pantalla/probar_dibujos.py tutor-pantalla/muestras/3d.json <carpeta>` y la tira de fotogramas.
- **Revisión visual:** cada uno entrega en su informe las rutas de sus capturas y qué debe verse en cada una; el orquestador se las pasa a un Haiku.
- Ventanas: nunca las del usuario. Si abres un panel o la tarjeta para probar, que sea un ejemplar tuyo, y ciérralo al terminar. La tarjeta es de un solo ejemplar: si ya está abierta, no la cierres; pruébala en el navegador (puppeteer) con su servidor o con la página suelta.
