# Contrato · Figuras de Claude Design en los tutores (fase 2, parte 1)

Las figuras de una exploración de Claude Design («Figuras del tutor»), en sus variantes recomendadas, para **todos los tutores**, con la **paleta plana** de `profe.js` (nunca colores chillones).

## La librería

- `tutor-pantalla/profe.js`: la librería de la exploración de Claude Design, **sin cambios**. Expone `window.Profe`.
  - Sus funciones son puras: datos → `{svg, g, x, y, w, h}`. `g` va en coordenadas de la ventana (px), y `t` va de 0 a 1 en la entrada.
  - Tiene `Profe.paleta(color, tema)` → `{tinta, sobre, fuerte, tenue, fondo, papel, borde, texto, suave, relleno, …}` y `Profe.colores` (azul, verde, rojo, naranja, amarillo, morado).
- Se carga en la página de **todos** los paneles (va primero en `SCRIPTS_UI` de `ojos_panel.py`) y también dentro de la página de la clase viva (lo inyecta `clase_viva.py` antes de `puente_clase.js`).
- **Paleta única:** todo color de cualquier dibujo sale de `Profe.paleta(nombre, tema).tinta` (o de `fuerte`, `tenue`… según la pieza). No quedan hex sueltos como `#1e5ac8` o `#c02828`.
- **Tema** (`'claro' | 'oscuro'`): cada dibujo del lote trae `d.tema`. Lo pone Python. Si falta, vale `'claro'`.

## Formas nuevas del dibujante (`formas_profe.js`)

Las marcas del tutor siguen siendo `{"tipo": "dibujo", "forma": …}`. Formas nuevas (o reemplazadas):

| forma | variante | datos propios |
|---|---|---|
| `globo` | 1a con hilo (en piezas de texto, 1c pestaña) | `texto` (1–3 frases), `formula` (opcional, texto plano) |
| `pasos` | 2a | `pasos: [{objetivo, texto, formula}]`; un paso cada ≈ 4 s y al final quedan todos |
| `punto` | 5a | objetivo = una «gráfica»; `q`, `p`, `letra`, `texto` (`''` = solo la letra), `lado` |
| `medida` | 6a cota | gráfica; `p`, `q1`, `q2`, `texto` |
| `guias` | 7a | gráfica; `q`, `p`, `textoQ`, `textoP` |
| `area` | 8a | gráfica; `rect: {q: [a, b], p: [a, b]}` o `poli: [[q, p], …]`, `texto`, `detalle` |
| `desplazar` | 9a | gráfica; `de: [[q, p], [q, p]]`, `a: [[q, p], [q, p]]`, `nombre`, `nota` |
| `recorrido` | 10a | gráfica; `camino: [[q, p], …]` (ciclo de 4 s, se repite) |
| `mano` (reemplaza) | 11a auto + 12a | `trazo`: `circulo` (rodear, auto) \| `subrayado` \| `tache` \| `check` \| `flecha`; `texto` = nota a mano |
| `foco` (reemplaza) | 16a velo | objetivo |

- **Valores, no píxeles:** en una gráfica el tutor da `q` y `p` con las unidades de los ejes. Python le pasa a la forma `d.ejes = {q: [q0, q1], p: [p0, p1]}` y `d.r` = el área de datos en px de cliente. `formas_profe.js` arma `{x0: r.x, x1: r.x + r.w, y0: r.y + r.h, y1: r.y, q, p}` para `Profe`.
- Las entradas van en fotogramas (`U.fotos`, 8 a 12 cuadros, `repetir: false`) y se quedan en el último.

## La clase viva: la parte en la página

Va en `puente_clase.js`, dentro de la guía, con `window.Profe` ya cargado. Dibuja en **una capa SVG propia de la página** (absoluta, `pointer-events: none` salvo lo clicable), con escala 1 (px CSS), y la redibuja al desplazarse o cambiar de tamaño.

1. **Manos (13a, 14a):** `PuenteClase.hacer` ya existe. Ahora además dibuja:
   - al mover, el **cursor «Tutor»** (`Profe.deslizador`, variante `cursor`) con las paradas marcadas en el riel, que se rellenan al llegar;
   - al pulsar, la **onda** (`Profe.pulsado`, 900 ms).
   - Si ella toca el control mientras tanto, el tutor suelta: se corta el recorrido (como `devolver`) y el cursor se va.
   - La notita azul de ahora se reemplaza por la ficha de `Profe.deslizador`.
2. **«↺ Devolver» (15a, 15b):** al terminar `hacer`, una ficha gris clicable junto a la pieza tocada (si tocó varias, una sola en la esquina). Al pulsarla corre `devolver()` y avisa a Python con `window.pywebview.api.devuelto()`. Se va sola si ella mueve la pieza.
3. **Pregunta flotante (3a chips; 3c sobre la gráfica):** `PuenteClase.pregunta(spec)` con `spec = {pregunta, opciones: [..], correcta (índice, opcional), explicacion, ref, puntos?: [{q, p, letra}] }`.
   - Sale junto a la pieza `ref`. Con `puntos` (y `ref` de una gráfica) usa la variante `grafica`; los puntos llegan en valores y se convierten con los ejes de la gráfica (los mismos que da `ejes()` del puente).
   - Al elegir: si hay `correcta`, pinta acierto o fallo como en la exploración. Luego llama `window.pywebview.api.pregunta_respondida(textoOpcion, acerto)` (`acerto` puede ser `null`). Se cierra a los 2,5 s del acierto; tras un fallo se puede volver a elegir.
   - `PuenteClase.quitarPregunta()` la quita.
4. **Tema:** `PuenteClase.tema()` → `'claro' | 'oscuro'` (el `data-theme` de `<html>`, o si no `prefers-color-scheme`). Todo lo de la página se dibuja con ese tema y se redibuja al cambiar.
5. **Ejes:** `PuenteClase.ejes(ref)` → `{q: [q0, q1], p: [p0, p1]}` de una pieza «gráfica» (de `_fullLayout.xaxis.range` y `yaxis.range`), o `null`. Python lo usa para `d.ejes`.

## La clase viva: el panel (`modo_clase.js`)

- **Pastilla 4a:** la ventana en forma pastilla mide **34 × 64 px lógicos** (lo pone `Acople`). Dentro, el SVG de `Profe.pastilla` (variante `marca`): `reposo`; `nuevo` cuando llega una respuesta estando plegada (un latido y quieto); `abierta` en la forma pregunta. Se abre solo con clic.
- **Cajita:** el borde se vuelve azul al escribir y, mientras el tutor piensa, el botón de enviar se cambia por el **garabato** de `Profe.cajita` (estado `pensando`, en bucle de 1,6 s).
- **Plegado = explica en la pantalla:** en la forma pregunta no se ven la respuesta del tutor ni la tarjeta de preguntas. Bajo la caja queda una sola línea: «✦ Te lo expliqué en la clase · Abrir el chat». En el chat abierto todo sigue como siempre.

## Lo que pone Python (`clase_viva.py` y `ojos_panel.py`)

- `d.tema`: en la clase viva, `PuenteClase.tema()`; en las demás apps, `tema_detras` de la última captura si la hay, y si no, `'claro'`.
- `d.ejes` para los objetivos «gráfica». También avisa si el dibujo va sobre una pieza de texto (`d.pieza_texto = true`, y entonces el globo usa la pestaña).
- **Plegado:** el contexto avisa al tutor de que está plegado y debe explicar sobre la clase con `globo` o `pasos`. Si no lo hace, Python convierte su texto en un `globo` anclado a la primera pieza que señaló. Sus `<preguntas>` van a `PuenteClase.pregunta`, no al chat.
- `ApiPuente.devuelto()` y `ApiPuente.pregunta_respondida(texto, acerto)`. La respuesta le llega al tutor como un mensaje suyo: `preguntarDesdeFuera`.
