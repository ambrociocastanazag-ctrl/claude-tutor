# Tutor que mira la pantalla (`tutor-pantalla/`)

Un panel que **mira UNA ventana** de cualquier programa (solo cuando tú lo apruebas) y **señala con flechas encima de ella**. Sirve para apps sin COM ni API, o para cualquier duda en cualquier programa. Solo mira y señala: nunca mueve el ratón ni teclea.

## Cómo se usa

```
python tutor-pantalla/panel_pantalla.py
```

1. **Elegir**: lista de ventanas abiertas con miniatura. Solo esa ventana, nunca toda la pantalla.
2. **Que mire**: la captura aparece en una **vista previa**, con un borde naranja sobre la ventana. Ahí eliges **Adjuntar**, **Recortar** (arrastra para adjuntar solo una parte) o **Cancelar** (no sale nada). La captura adjunta queda en la caja del mensaje (con ✕ para quitarla) y sale solo cuando envías.
3. El asistente responde en el chat y dibuja flechas numeradas encima del programa. Las flechas dejan pasar los clics, siguen a la ventana y solo se ven con esa app o el panel al frente. **Borrar flechas** las quita.

**Modo puente** (`python tutor-pantalla/panel_pantalla.py --puente`): el mismo panel, pero responde **el chat de Claude Code** que lo abrió. Lo que escribes le llega al chat; la respuesta y las flechas vuelven al panel. Claude Code también puede pedirte una captura, que igual pasa por la vista previa. Cómo lo usa el chat: ver `puente.py`.

**Atajo:** **Ctrl+Alt+M** desde cualquier programa trae el panel al frente y abre «Que mire» (lo mismo que el botón). Lo tiene el primer panel que se abre (asistente o tutor); si otro programa ya usa ese atajo, el panel sigue igual sin él.

**Adjuntos:** además de las capturas, se le pueden pasar archivos con el clip, pegándolos (Ctrl+V) o arrastrándolos: imágenes, PDF y texto (como en los tutores de Excel y Dia). En el modo puente llegan al chat de Claude Code como archivos que lee con Read.

**Preguntas en el chat:** el asistente y todos los tutores pueden poner una tarjeta con botones cuando ayuda: opción única (un clic), varias opciones, abierta (caja de texto), con «Otra…» y «No sé». Si el tutor marca la correcta, se corrige al instante (✔/✘ y una explicación, sin IA); la respuesta le llega al tutor para que siga. Formato: bloque `<preguntas>[...]</preguntas>` (`REGLAS_PREGUNTAS` en `ojos_panel.py`).

Sin captura, también se le puede escribir como a un chat normal. **Investiga:** busca en internet y lee los enlaces que le pegues (WebSearch y WebFetch, solo lectura); mientras tanto el panel dice «Buscando en la web…» o «Leyendo la página…». Los enlaces de sus respuestas se abren en tu navegador.

## ¿Sirve con cualquier programa?

**Ver, sí:** la captura salió bien en todo lo probado (Word, Bloc de notas, Brave, VS Code, Antigravity). Lo que varía es **qué tan exacto apunta**:

| Tipo de app | Botones que lee | Cómo apunta |
|---|---|---|
| Office, Bloc de notas, apps normales de Windows (Win32, WPF, WinForms) | Muchos (Word: 150) | Exacto, por la lista |
| Chrome, Brave, Edge, apps Electron (VS Code, Antigravity, Discord…) | La primera lectura trae 3 y la siguiente unos 90: activan su accesibilidad al pedirla. `capturar()` relee sola si salen menos de 10. | Exacto |
| Apps que dibujan todo ellas mismas: lienzos (Dia, programas de diseño), juegos, figuras de MATLAB, apps Java sin Access Bridge | Pocos o ninguno | Por la imagen: buena en cosas grandes, aproximada en las pequeñas |
| Apps abiertas como administrador | Windows no deja leerlas desde un proceso normal | Habría que abrir el panel también como administrador |

## Alcance (acordado el 2026-10-14)

Un solo núcleo (los «ojos») con cuatro formas de usarlo. Cambia quién responde:

| Modo | Quién responde | Estado |
|---|---|---|
| **1. Asistente** | Una sesión de Claude que abre el panel; sin tarea fija | ✅ Hecho |
| **2. Puente** | El chat de Claude Code: lo que escribes en el panel llega al chat y la respuesta vuelve al panel (con un proceso en segundo plano) | ✅ Hecho |
| **3. Dentro de los tutores** | El tutor de Excel o de Dia, con ojos para lo que COM o el plugin no ven: diálogos, Power Query, el editor de VBA, un PDF. Botón de la cámara junto al clip; las ventanas de la app del curso salen primero; el tutor puede pedir ver una (botón «Mostrarle una ventana»). En Dia, lo del diagrama sigue dentro de Dia. | ✅ Hecho |
| **4. Curso** | Un tutor nuevo con temario para enseñar una app sin API: `python tutor-pantalla/panel_curso.py <curso.json>`. Ver «Cómo hacer un curso». | ✅ Hecho |

El **permiso vive en el núcleo**: ningún modo puede mandar una captura sin la vista previa, el clic en «Adjuntar» y el envío del mensaje.

## Dibujos encima de la app

Además de las flechas, el asistente y los tres tutores (Excel, Dia, curso) pueden **dibujar** encima de la app con
`{"tipo": "dibujo", "forma": ...}` en sus marcas. Formato completo en [`DIBUJOS.md`](DIBUJOS.md).

| Forma | Qué hace |
|---|---|
| `foco` | Oscurece la ventana menos lo importante, con un anillo que late |
| `mano` | Trazo de profe que se va dibujando: círculo, subrayado, flecha, tache o ✓, con letra a mano |
| `teclas` | Teclas en 3D que se pulsan (Ctrl + S) |
| `lupa` | Una zona pequeña aumentada al lado, **en vivo** (solo en una ventana que ya aprobaste) |
| `fantasma` | Cursor animado que hace los pasos: clic, doble clic, clic derecho, arrastrar y escribir |
| `guia` | Contorno punteado que se dibuja: «hazlo aquí» |
| `secuencia` | 1 → 2 → 3 sobre los botones, con flechas curvas |
| `formula` | La fórmula bien escrita (MathJax) junto a algo; en Excel, la de la celda y una mini gráfica de sus datos |
| `rayos_x` | Excel: de las celdas que usa la fórmula al resultado, con los valores viajando |
| `desarmar` | Copia ampliada de una fórmula, línea de código o comando con una llave y una nota por parte |
| `svg` | El dibujo propio del tutor (filtrado: solo formas y texto), **también animado** (SMIL o CSS): un punto que recorre una curva, barras que crecen, un engrane que gira |

**Voz:** botón 🔊 en el panel (apagado al empezar). Lee la respuesta y, si hay dibujos con `"decir"`, los narra al
ritmo de la animación (paso a paso en el fantasma y la secuencia). Usa una **voz natural** (edge-tts: Dalia de México;
`"voz": "es-MX-JorgeNeural"` en `panel-excel/preferencias.json` para Jorge). Necesita internet y el texto va al
servicio de Microsoft (nunca capturas); sin internet, vuelve a la voz de Windows.

**Cómo funciona:** la **página del panel dibuja** (SVG → PNG en `dibujante.js` y `formas_*.js`, el mismo motor Edge
del panel) y **`capa.py` proyecta**: una ventana transparente por capa que deja pasar los clics, sigue a la app y
anima a 30 fps solo lo que se mueve (fondo fijo + fotogramas + piezas con ruta). La lupa lee solo su zona de la
pantalla y nunca la guarda ni la manda.

Un curso es **una carpeta propia en la raíz** (nunca dentro de `tutor-pantalla/`) con `curso.json` y un JSON por módulo. El panel es el de los tutores de Excel y Dia (Lección | Tutor, progreso recordado en `progreso.json` de esa carpeta, botón 📷).

```json
{"titulo": "Paint desde cero",
 "app": {"nombre": "Paint", "exe": "mspaint", "abrir": "mspaint"},
 "modelo_tutor": "sonnet",
 "modulos": ["m1_conocer.json", "m2_formas.json"]}
```

`exe` es el ejecutable sin `.exe` (lo dice `python tutor-pantalla/ojos.py --lista`); `abrir`, el comando del botón «Abrir». Cada módulo:

```json
{"titulo": "Conocer Paint", "codigo": "M1",
 "tema_tutor": "de qué va el módulo (para el tutor)",
 "notas_tutor": "la solución del Tu turno y sus errores típicos (el tutor no la revela entera)",
 "pasos": [
   {"titulo": "Las herramientas", "texto": "Explicación con **negritas**.",
    "donde": "Dónde está en la app (sale en «En Paint»).",
    "antes": "Abre primero el diálogo con Resize and skew",
    "senalar": [{"nombre": ["Pencil", "Lápiz"], "tipo": "botón", "texto": "Lápiz", "n": 1},
                {"empieza": "Color 1", "texto": "Color 1"}]},
   {"titulo": "Tu turno", "texto": "Qué hacer.",
    "turno": {"titulo": "Lápiz rojo", "al_empezar": "Lo que dice la tarjeta antes de comprobar.",
      "pide": [{"tipo": "activo", "nombre": ["Pencil", "Lápiz"], "texto": "El Pencil está elegido"},
               {"tipo": "nombre", "empieza": "Color 1: ", "es": ["Red", "Rojo"], "texto": "El Color 1 es rojo"}],
      "errores": [{"si": {"tipo": "nombre", "empieza": "Color 1: ", "es": ["Dark red"]}, "mensaje": "Ese es el rojo oscuro."}],
      "tutor": {"revisar": "lo que tiene que verse en el dibujo (si no se puede leer sin imagen)"},
      "bien": "Mensaje si está bien.", "falta": "Todavía falta: {falta}."}}]}
```

- **Nombres de los controles:** como los muestra la app, y en lista para otros idiomas de Windows (`["Pencil", "Lápiz"]`); se comparan sin mayúsculas ni acentos. Para verlos: abre la app y `python tutor-pantalla/ojos.py --capturar "<app>" salida.png` (imprime la lista).
- **`senalar`:** `nombre` (o `empieza`, para nombres que cambian, como «Color 1: Red») y, si se repite, `tipo` (botón, elemento, opción, campo, casilla, menú, pestaña). Si solo existen con algo abierto (un diálogo), pon `antes` en el paso: «Señálamelo» lo dice y `--probar` no lo cuenta como fallo.
- **`dibujos`** (opcional, en el paso): dibujos encima de la app **sin IA**, con el botón «Muéstramelo». El objetivo, por `nombre` como en `senalar`:
  `"dibujos": [{"forma": "fantasma", "pasos": [{"accion": "clic", "nombre": ["Pencil", "Lápiz"], "decir": "Elige el lápiz"}]}, {"forma": "mano", "trazo": "circulo", "nombre": "Fill", "texto": "el relleno"}]`.
  Los dibujos usan **el mismo formato que los tutores** (`tutor-pantalla/DIBUJOS.md`): se escriben en una línea, sin medir posiciones ni hacer capturas; el panel los resuelve y los dibuja al pulsar «Muéstramelo», con la voz si está encendida (cada `decir`). Formas: foco, mano, teclas, fantasma, guia, secuencia, formula, desarmar, svg (también animado). `--probar` revisa que estén bien escritos.
- **`pide`** (se revisa sin IA al pulsar Comprobar): `activo` (herramienta u opción elegida), `nombre` (`empieza` + `es`), `texto` (de la ventana, p. ej. «800 × 600px»; `es` o `contiene`), `valor` (de un campo o deslizador), `titulo` (`contiene`: el archivo guardado), `existe` (un control o diálogo abierto).
- **`errores`:** el primero cuyo `si` se cumple da su mensaje (mismos tipos que `pide`).
- **`tutor`:** lo que solo se ve en la imagen. Si lo de `pide` está bien, Comprobar abre la vista previa de la app; con la captura adjunta, el tutor responde bien / casi / revisa.
- **Antes de darlo:** `python tutor-pantalla/panel_curso.py <curso.json> --probar` hasta «Curso: todo bien», con la app abierta para que busque cada `senalar`. Luego pruébalo de verdad con el panel.

## Archivos

| Archivo | Qué es |
|---|---|
| `ojos.py` | El núcleo: lista de ventanas, miniaturas, captura de una ventana (`Captura`: imagen reducida a 1400 px de lado largo, controles en píxeles de la imagen, recorte y conversión a la pantalla). `python ojos.py --lista` / `--capturar "texto" salida.png`. |
| `asistente.py` | La sesión `claude -p` (stream-json, sin MCP ni ajustes, como el tutor de Excel; con solo WebSearch y WebFetch), sus reglas y cómo se leen las marcas (`MARCAS: [...]` al final de la respuesta). |
| `ojos_panel.py` | Los ojos para cualquier panel: `Ojos` (capturas con permiso, adjuntos, contexto para el tutor, marcas `"ventana"` y flechas), `OjosApi` (lo que llama la página), `REGLAS_OJOS` (lo que se le explica al tutor), `inyectar_ui` y el proceso de las flechas. `python ojos_panel.py --probar` (sin ventanas ni IA). |
| `ojos_ui.js` | La lista de ventanas con miniaturas y la vista previa (Cancelar / Recortar / Adjuntar), para la página de cualquier panel. |
| `preguntas_ui.js` | Las tarjetas de preguntas del tutor en el chat (opción única o múltiple, abiertas, «Otra…», «No sé»), con la corrección al instante. |
| `panel_pantalla.py` | El panel del asistente (pywebview): la API que llama la página, el modo puente y la prueba `--probar`. |
| `curso_pantalla.py` | El modo curso: cargar el curso, leer el estado de la app, revisar el «Tu turno» sin IA, buscar lo que se señala y el estado en texto para el tutor. |
| `panel_curso.py` | El panel de un curso (la página de los tutores): pasos, «Señálamelo», Comprobar (sin IA y con el tutor), el tutor del curso y `--probar`. |
| `puente.py` | El modo puente: los dos lados se pasan mensajes por una carpeta temporal (`%TEMP%\tutor-pantalla-puente`, se borra al cerrar el panel, capturas incluidas). Desde el chat: `esperar` (en segundo plano: al llegar un mensaje termina y despierta al chat), `responder`, `pedir-captura`, `estado`. |
| `panel.html` | La página: mismo diseño y tema que los paneles de Excel y Dia (el tema sale de `panel-excel/preferencias.json`). |
| `DIBUJOS.md` | El contrato de los dibujos: la marca del tutor, el lote (Python → página), la capa (página → capa.py) y las utilidades de las formas. |
| `dibujante.js` | El núcleo de los dibujos en la página: `Dibujante.mostrar(lote, texto)`, SVG → PNG, notas que no tapan nada, flechas, MathJax y rough.js, y la narración con la voz. |
| `formas_fijas.js` | Foco, teclas, mano alzada, lupa y SVG libre (con su filtro). |
| `formas_animadas.js` | Ratón fantasma, forma guía y secuencia. |
| `formas_formulas.js` | Fórmula flotante (con mini gráfica), rayos X y desarmar. |
| `voz.js` | La voz y el botón 🔊: la natural (pide el audio a Python) y, si no hay, `speechSynthesis` de Windows. |
| `voz_natural.py` | El audio de cada frase con edge-tts (voz de `preferencias.json`, Dalia por defecto), en caché. `python voz_natural.py "texto" muestra.mp3 [voz]` para oír una. |
| `capa.py` | El proyector: ventanas transparentes que pegan las capas encima de la app, las animan y leen la zona de la lupa. `capa.fotograma()` compone un instante igual que en vivo. |
| `probar_dibujos.py` | Banco de pruebas sin panel: dibuja un lote de muestras en el Chrome instalado y guarda tiras de 6 momentos y el cuadro final. |
| `muestras/*.json` | Lotes de ejemplo de cada forma, para `probar_dibujos.py` (`svg_animado.json`: SMIL, CSS y un SVG trampa que debe quedar filtrado). |
| `vendor/` | MathJax 3.2.2 (`tex-svg.js`) y rough.js 4.6.6, con sus licencias (Apache 2.0 y MIT). No se editan. |
| `../panel-excel/rayos_x.py` | Lo que se lee de Excel para los dibujos (solo lectura): caja de una celda en pantalla, celdas que usa una fórmula, la fórmula en LaTeX y los datos de la mini gráfica. |

## Cómo cambiarlo

1. Edita `ojos.py` (captura o controles), `ojos_panel.py` / `ojos_ui.js` (lo compartido con los tutores: si los cambias, prueba también los paneles de Excel y Dia), `asistente.py` (reglas o formato de marcas) o `panel.html` (la página).
2. Prueba sin panel, con una ventana abierta: `python tutor-pantalla/panel_pantalla.py --probar "Word" salida.png`. Captura, pregunta dónde se guarda el archivo, dibuja las flechas y guarda la captura con ellas. Revisa la imagen.
3. `python tutor-pantalla/ojos_panel.py --probar` hasta «Ojos: todo bien».
4. Prueba con el panel abierto: Elegir → Que mire → Adjuntar → enviar, y Cancelar (que no salga nada).
5. **Dibujos:** edita la forma en `formas_*.js` (contrato en `DIBUJOS.md`) y pruébala sin panel con
   `python tutor-pantalla/probar_dibujos.py tutor-pantalla/muestras/<archivo>.json <carpeta> [--fondo captura.png]`; mira las tiras.
   Lo de Excel: `python panel-excel/rayos_x.py --probar` (y `--probar --excel`, que abre su propio Excel).

## Dependencias

Python 3.12 con `pywebview` (Edge WebView2), `Pillow` y `uiautomation` (`python -m pip install uiautomation`), Claude Code (`claude`) y `prueba-dia/overlay_dia.py`. Los dibujos: MathJax y rough.js (ya en `vendor/`, sin instalar nada), `edge-tts` para la voz natural (`python -m pip install edge-tts`; sin ella, la voz de Windows), `pywin32` y `openpyxl` para lo de Excel, y Node con `herramientas/` solo para `probar_dibujos.py`.
