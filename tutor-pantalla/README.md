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

## Cómo hacer un curso

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
- **Botones sin nombre:** si un control solo trae el nombre de su clase interna (`Avalonia.Controls.Shapes.Path`) o ninguno, se usa su **tooltip** (primera línea: «Lápiz (2)»). Para los que no tienen ni eso, `"alias"` en `app`: `[{"nombre": "Reproducir", "es": "Avalonia.Controls.Shapes.Path", "n": 1, "ventana": "OpenUtau v"}]` (el n-ésimo con ese nombre, en el orden de UI Automation; los alias se aplican en orden, así que tras renombrar el primero, `n: 1` es el siguiente).
- **Apps con varias ventanas** (OpenUtau: principal y piano roll): `"ventanas": "todas"` en `app` y se leen todas las de ese exe, no solo la más reciente.
- **Revisar el archivo que guarda la app** (sin abrirla): tipo `ustx` para proyectos de OpenUtau (`ustx.py`, claves en su docstring: notas, ritmo, letras en romaji o kana, cantante, fonemizador, bpm, vibrato, curvas, audio, pistas). `archivo` es relativo a la carpeta del curso. En `--probar`, cada Tu turno con `ustx` se prueba con archivos de verdad: `solucion/<módulo>/bien/` (debe salir bien), `error<k>/` (el error típico k) y sin nada guardado (mal). Ejemplo completo: `openutau/`.

### Capacidades de los tutores (el asistente es la vara)

Todo lo que sabe el asistente lo saben también los tutores del modo curso, de Excel y de Dia. Lo común vive en **`capacidades.py`** (una sola fuente; los paneles lo llaman, no lo copian):

| Capacidad | Modo curso | Excel / Dia |
|---|---|---|
| Dibujos de `DIBUJOS.md` (también `svg` animado) sobre cualquier ventana aprobada | ya estaba | ya estaba |
| Ver otras ventanas (📷, `<pedir_ventana/>`, vista previa siempre) y marcar con `"tipo": "ventana"` | ya estaba | ya estaba |
| **Volver a mirar la misma ventana** (`<volver_a_mirar/>`, tarjeta Sí / No / Recortar) | **añadida** (2026-10-15): `ojos_panel` + `ojos_ui.js`, sin tocar las páginas | **añadida** (idéntica) |
| Adjuntos (clip, Ctrl+V, arrastrar), tarjetas `<preguntas>`, voz 🔊 | ya estaba (la página es la misma) | ya estaba |
| Investigar en la web (WebSearch y WebFetch, con «Buscando en la web…») | **añadida**: `capacidades.ConWeb` | por integrar (ver abajo) |
| El prompt «tus capacidades» (qué tiene y cuándo usarlo) | **añadida**: `capacidades.reglas(app, codigo)` | por integrar |
| Archivo abierto en VS Code en el contexto + objetivo `"linea"` | **añadida** (cursos de código) | opcional: solo si el curso tiene proyecto |
| **Leer archivos** (Read y Glob en las carpetas del curso; fuera o secretos, `<pedir_archivo/>` con tarjeta Sí / No) | **añadida** (2026-10-16): `archivos.py` | **añadida** (idéntica; también el asistente, solo con tarjeta) |
| **Modo práctica** (botón «Practicar»: la lección en pausa, ejercicios nuevos del tutor con permiso y Comprobar; al salir vuelve a donde iba) | **añadida** (2026-10-16): `practica.py` + `ejercicios_tutor.py` | **añadida** (`practica.py`; el ejercicio es el «Ejercicio del tutor» de siempre: hoja «Práctica N» / diagrama nuevo) |

**Lo que tiene que llamar otro panel** (Excel: `panel_web.py`; Dia: `panel_dia.py`):
1. `import capacidades` (con `tutor-pantalla/` en `sys.path`) y en el prompt del tutor, `capacidades.reglas("<app>")` en lugar de juntar a mano `REGLAS_OJOS + REGLAS_DIBUJOS + REGLAS_PREGUNTAS`; quitar «No uses herramientas» de sus reglas.
2. La clase del tutor: `class TutorX(capacidades.ConWeb, motor.Tutor)`. Pone `--tools WebSearch,WebFetch` y reutiliza el bucle de lectura del asistente. Si su `_arrancar`/`_turno` no son los de `motor.Tutor` de Excel, basta con llamar a `asistente.Sesion._turno(self, contenido, al_trozo, self.al_aviso)`.
3. En la API: `tutor.al_aviso = lambda t: self._empujar("window.avisoTrabajo && window.avisoTrabajo(" + json.dumps(t) + ")")` (`ojos_ui.js` ya trae `avisoTrabajo`).
4. Si el curso tiene proyecto de código: `ojos_panel.Ojos(..., raices=capacidades.raices_curso(curso.d))` (así los dibujos aceptan `"linea"`), `capacidades.contexto_editor(raices)` en el [Estado actual], `capacidades.reglas(app, True)` y, al final de cada respuesta, `capacidades.avisos_linea(self._ojos)` para añadir «Sube/Baja…».

#### Leer archivos (`archivos.py`, `<pedir_archivo/>`)

Para que no haga falta mandarle captura de un archivo (lo pidió así el 2026-10-16):
- **Dentro de las carpetas del curso** (la del `curso.json`, `proyecto`, `proyectos`, la que abre `app.abrir` y `datos` de Excel; ver `archivos.carpetas_de`): el tutor lee solo con **Read** y **Glob** de Claude Code. La sesión arranca en una carpeta vacía y cada carpeta va con `--add-dir`, así que fuera de ellas Claude Code se lo niega solo (y no carga ningún `CLAUDE.md`).
- **Secretos** (`.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa*`, `credentials*`… lista `SECRETOS`): negados aunque estén dentro, con reglas `Read(//**/…)` (tienen que ser absolutas: las relativas no alcanzan las carpetas de `--add-dir`). Probado con el `.env` real de `carrito-gt`.
- **Fuera o secreto:** el tutor escribe `<pedir_archivo ruta="C:/…"/>` → tarjeta **«¿Dejo que el tutor lea «x»?»** (Sí / No). El permiso es **por archivo, nunca por carpeta**, y dura la sesión: si lo vuelve a pedir, se lee solo. Con Sí, el panel lee el archivo (texto numerado con su ruta, PDF o imagen) y lo manda como adjunto en el mismo mensaje (`OjosApi.archivo_leer`, `Ojos.tarjetaArchivo` en `ojos_ui.js`).
- **Sin Grep:** en la prueba no quedó claro que la búsqueda de texto respetara la regla de los secretos. Solo lee: nunca escribe ni ejecuta.
- Pruebas: `python tutor-pantalla/archivos.py`.

#### Volver a mirar la misma ventana (`<volver_a_mirar/>`)

Si el estudiante ya enseñó una ventana (📷 → vista previa → Enviar) y luego pregunta algo de esa misma ventana, el tutor no le pide que la enseñe otra vez: termina con `<volver_a_mirar/>` (o `<volver_a_mirar ventana="parte del título"/>` si fueron varias). El panel pone en el chat la tarjeta **«¿Vuelvo a mirar «título»?»**:
- **Sí:** captura esa ventana (la ya aprobada) **sin vista previa**, la adjunta y la respuesta continúa sola (la tarjeta manda «Sí, vuelve a mirar…» con la captura dentro).
- **No:** no se captura; el tutor contesta sin imagen (o dice que no puede verla).
- **Recortar:** la vista previa de siempre sobre una captura nueva, con el recorte ya activo; al enviar sale solo ese trozo. Si cancela, la tarjeta queda para elegir otra vez.
- Solo ventanas aprobadas **en esta sesión del panel** (`Ojos.aprobadas`); si ya se cerró, la tarjeta lo dice y ofrece 📷. Nunca la pantalla entera ni sin el clic. Una vez por respuesta y solo si la pregunta es de esa ventana (regla `REGLAS_VOLVER` en `ojos_panel.py`; ya va dentro de `REGLAS_OJOS`, o sea en `capacidades.reglas()` de todos los tutores, y en el prompt del asistente).
- **Cómo está hecho (para no copiarlo):** `separar_pedido` quita la etiqueta y `separar_preguntas` (que los 4 paneles ya llaman) la convierte en una «pregunta» con `"volver": {token, titulo, hwnd, existe}`; `Preguntas.tarjeta` (preguntas_ui.js) la dibuja con `Ojos.tarjetaVolver` (ojos_ui.js). La captura viaja en el mismo mensaje porque ojos_ui.js envuelve `api.preguntar` de la página. La API es `OjosApi.ojos_volver(token, "si" | "recortar")` → `Ojos.volver`. Los paneles de Excel, Dia y curso comparten página y el asistente la suya: ninguno necesitó cambios. `ojos_panel.py --probar` y `capacidades.py` lo prueban sin ventanas.
- Falla conocida menor: mientras el texto del tutor va llegando a trozos, la etiqueta puede verse un instante antes de que la limpie la respuesta final.

#### Señalar una línea del editor (`"linea"`)

En cursos de código el tutor recibe, en cada pregunta, el **archivo abierto** en VS Code: se saca del título de la ventana («Prueba.java - Proyecto - Visual Studio Code»; con «●» = cambios sin guardar, y entonces se avisa de que el texto es el del disco) y de la pestaña del editor (UI Automation), se busca dentro de las carpetas del curso (`proyecto`, `proyectos` y lo que abre `app.abrir`; gana el más reciente) y se le pasa con números de línea (máximo 400 alrededor del cursor), el cursor y las líneas visibles. Con eso marca `{"tipo": "app", "linea": 21, "texto": "…"}` o un dibujo con `"linea": 14` (opcional `"archivo"`), y un `senalar` de lección también puede llevar `"linea"`.

Cómo se ubica (`editor_vscode.py`, solo lectura, sin clics ni teclas ni cambiar su foco ni su configuración): VS Code no expone el texto del editor a UI Automation mientras no haya lector de pantalla («The editor is not accessible at this time»; TextPattern no existe y no se cambia `editor.accessibilitySupport`). Sí expone el rectángulo del editor, la barra de estado («Ln 21, Col 2») y el cuadro de entrada del cursor. Con una captura **local** de esa ventana (PrintWindow, no sale a ningún sitio) se leen los números del margen como filas de tinta (cada fila es una línea real: ni el ajuste de ancho ni el «Run | Debug» cuentan), la fila del cursor da su número y las demás siguen; si el cursor no se ve, se alinea la forma del texto con el largo de las líneas del archivo en disco. Si la línea no está a la vista, el panel marca el borde del editor y dice «Sube/Baja en el editor hasta la línea N». Precisión medida: el recuadro cae sobre la línea exacta, con tema oscuro y 125 %, en un archivo con CodeLens (verificado por un revisor aparte); con regiones plegadas la numeración puede fallar (entonces dice que no la ve). Cuesta ≈ 2 s por pregunta (UI Automation del árbol completo).

### Modo práctica (`practica.py`) y ejercicios del tutor (`ejercicios_tutor.py`)

Lo pidió así el 2026-10-16: el tutor casi nunca proponía crear un archivo nuevo cuando pedía ejemplos, porque cuida el avance de la lección.
- **Botón «Practicar»** (cabecera de la Lección, en los paneles de modo curso, Excel y Dia; la interfaz está en `panel-excel/panel.html`). Al entrar se guarda el módulo y el paso (`<curso>/practica.json`, sobrevive a cerrar el panel), se ocultan el paso y su «Tu turno», se bloquean Anterior/Siguiente y el menú de módulos, y aparece la barra «Modo práctica · Tu lección te espera en Módulo X, paso Y» con «Dame un ejercicio» y «Salir y volver a la lección» (en el Tutor, el chip «Dame un ejercicio»).
- **El tutor** recibe `[MODO PRÁCTICA]` al inicio de cada [Estado actual] (`Practica.prefijo()`) y sus reglas (`practica.REGLAS`): no empuja a avanzar y, si pide ejemplos, crea un ejercicio de verdad con permiso, uno cada vez, sin dar la solución.
- **Al salir** vuelve al paso guardado y deja la app ahí: Excel en la hoja de la lección, Dia en la pestaña del módulo, VS Code con el archivo que tenía abierto al entrar (`code -r -g`).
- **Contrato** para un panel nuevo: docstring de `practica.py` (`PracticaApi`, `_pos()`, `_ir_pos(m, n)`, `"practica"` en el estado, prefijo y reglas).

**Ejercicios del tutor en el modo curso** (`ejercicios_tutor.py`; en Excel y Dia ya existían): el tutor termina con `<ejercicio>{...}</ejercicio>` → tarjeta Aplicar / No / Deshacer → tarjeta «Ejercicio del tutor» con su Comprobar, sin IA.
- **Código:** crea un archivo NUEVO en el proyecto (`"archivo"` relativo, nunca uno que exista ni fuera del proyecto; paquete `practica`), con un esqueleto que compila (enunciado arriba, `// TODO` y `throw new UnsupportedOperationException("TODO")`). Sus pruebas JUnit (en el JUnit del `pom.xml`: JUnit 4 en el curso de Java) quedan **ocultas** en `<curso>/practica/<fecha>-<id>/`. Comprobar = existe + compila + pasa esas pruebas, con Maven en una **copia temporal** (como los «Tu turno»). Al aplicar, el archivo se abre en VS Code; «Ir al archivo» lo vuelve a abrir. Deshacer borra el archivo (si ya escribió en él, pide «Borrar igual»). `"lo_crea": "estudiante"` cuando el ejercicio es crear el archivo: no se escribe nada.
- **App sin API:** el ejercicio trae `"pide"` (las comprobaciones de las lecciones) y Comprobar las revisa.
- Pruebas: `python tutor-pantalla/practica.py`, `python tutor-pantalla/ejercicios_tutor.py` y, con Maven de verdad sobre una copia de un proyecto, `python tutor-pantalla/ejercicios_tutor.py --maven <copia>` (con `JAVA_HOME`). Probado en vivo con el tutor de Java: pidió «un ejercicio de Optional» y creó `Ejercicio1.java` (esqueleto que compila) con sus pruebas; sin resolver, Comprobar dice «falta: pasa las pruebas del tutor».

### Cursos de código (con `"proyecto"`)

Si `curso.json` lleva `"proyecto": "<ruta absoluta de un proyecto Maven>"` (y, opcional, `"java_home"`: la carpeta del JDK que pide el proyecto; si falta, se usa la variable `JAVA_HOME` del sistema, y el JDK del PATH puede no ser el correcto), `pide` y los `si` de `errores` aceptan además estos tipos, que se revisan **sin IA** y sin abrir la app (la ventana de la app solo hace falta para los tipos de siempre). La ruta puede tener espacios.

```json
{"tipo": "compila", "texto": "Tu proyecto compila"}
{"tipo": "archivo", "ruta": "src/main/java/gt/x/Libro.java", "contiene": ["private int paginas", "public int getPaginas()"],
 "no_contiene": ["@Getter"], "regex": "IllegalArgument\\w+", "texto": "Libro está bien escrito"}
{"tipo": "pruebas", "clases": ["LibroProfeTest"], "ocultas": true, "texto": "Pasas las pruebas del profe"}
{"tipo": "pruebas", "clases": ["LibroTest"], "minimo": 3, "texto": "Tus 3 pruebas pasan"}
{"tipo": "http", "metodo": "POST", "url": "http://localhost:8080/prestamos", "cuerpo": {"usuario": "ana"},
 "codigo": 201, "json": {"usuario": "ana"}, "texto": "POST /prestamos responde 201"}
```

- **`compila`**: `mvnw compile` sobre una copia. Si no compila, «falta» lleva el primer error del compilador: `Libro.java línea 4: cannot find symbol` (si el archivo es una prueba oculta lo dice: «prueba del profe»).
- **`archivo`**: `ruta` relativa al proyecto. Sin `contiene`/`no_contiene`/`regex` basta con que exista. `contiene` y `no_contiene` comparan con los espacios colapsados (`private  int x` = `private int x`): todo `contiene` debe aparecer y ningún `no_contiene`. `regex` (Python) se busca en todo el archivo.
- **`pruebas`**: `clases` son nombres simples. Pasa si todas corrieron, sin fallos ni errores, y con al menos `minimo` pruebas (1 por defecto). Si falla, «falta» trae el primer mensaje de JUnit sin traza: `guardaTest: expected:<250> but was:<0>`. Con `"ocultas": true` se añaden las pruebas de `<carpeta del curso>/pruebas/<stem del módulo>/` (p. ej. `pruebas/m2_pruebas/`): si esa carpeta trae su propio `src/`, se copia tal cual; si no, su contenido cuelga de `src/test/java/`, así que `pruebas/m2_pruebas/gt/biblioteca/entity/LibroProfeTest.java` cae en su paquete.
- **`http`**: una petición a la API que el estudiante tiene corriendo. `metodo` (GET por defecto), `cuerpo` (JSON), `codigo` (200 por defecto) y `json` (la respuesta debe **contener** esos campos con esos valores; en listas, algún elemento). Sin servidor: «¿Está corriendo tu app? (./mvnw spring-boot:run)».
- **Cómo corre:** el proyecto se **copia a una carpeta temporal** (sin `target/`, `.git` ni `node_modules`; con su `.env`), se le añaden las ocultas y se corre `mvnw.cmd` (una sola vez por Comprobar, juntando las clases de `pide` y de `errores`); se leen `target/surefire-reports/`. Nunca se escribe en el proyecto del estudiante. La carpeta temporal se borra al terminar.
- **Segundo plano:** Comprobar muestra «Revisando… (corriendo tus pruebas, ~N s)» (N = lo que tardó la última vez; 20 al principio) y el panel y el tutor siguen vivos. Mientras corre, un segundo Comprobar avisa y espera. Si el turno es solo de código, no consulta la app.
- **`solucion/` y `--probar`:** en la carpeta del curso, `solucion/plantilla/` (el proyecto al empezar) y `solucion/<stem del módulo>/` (el proyecto completo tal como queda al terminar ese módulo, acumulado). `--probar` valida cada tipo nuevo (y que existan las ocultas) y corre cada «Tu turno» de código contra `solucion/<stem>/` (debe salir **bien**) y contra la del módulo anterior o `solucion/plantilla/` (debe **no** salir bien). Los `http` no se prueban ahí (se dan por buenos): se prueban a mano con la app corriendo. Una corrida de Maven tarda ≈10–16 s; `--probar` hace dos por «Tu turno».

#### Varios proyectos, comodines y «todas» (`"proyectos"`)

Un curso puede revisar **más de un proyecto** (p. ej. una práctica y el proyecto real del estudiante). En `curso.json`:

```json
"proyectos": {"carrito": {"ruta": "C:/Users/yo/mi repo", "maven": "api"}}
```

- `ruta`: la carpeta raíz del repo (puede tener espacios). `maven` (opcional): la subcarpeta donde está el `pom.xml` y el `mvnw` (si falta, es la raíz).
- Un `turno` con `"proyecto": "carrito"` revisa **todos** sus `pide` y `si` contra ese proyecto: `archivo` con rutas relativas a `ruta` (la raíz del repo, así que en el ejemplo se escribe `api/src/...`), `compila` y `pruebas` con Maven en `ruta/maven`, y `http` igual que siempre (la API que el estudiante tiene corriendo). Sin `"proyecto"` en el turno, todo sigue como antes (el `"proyecto"` de `curso.json`; un nombre que no esté en `proyectos` es un error al cargar el curso).
- **Cómo corre Maven aquí:** se copia el repo entero (sin `target/`, `.git` ni `node_modules`) a una carpeta temporal, se copia el `.env` de la raíz también a la subcarpeta `maven` (si esa no trae uno) y se corre ahí. Nunca se escribe en el repo del estudiante.
- **Comodines en `archivo.ruta`** (`*`, `?`, `**`): pasa si **algún** archivo que coincida cumple `contiene`/`no_contiene`/`regex`. Sirve cuando el nombre lo elige el estudiante. Si nada coincide: «busqué `api/src/**/entity/*.java` y no encontré ningún archivo así»; si coincide pero ninguno cumple: «busqué `…`: 2 archivos, ninguno cumple (en Libro.java falta «private int x»)». No busca dentro de `target/` ni `node_modules/`.
- **`"clases": "todas"`** en `pruebas`: corre todas sus pruebas (`mvnw test`, sin `-Dtest`) y exige **cero fallos** y al menos `minimo` pruebas en total (1 por defecto). Útil cuando no se conocen los nombres de sus clases de prueba.

```json
{"tipo": "archivo", "ruta": "api/src/main/java/**/entity/*.java", "contiene": ["@Entity", "@Id"], "texto": "Tienes una entidad con @Id"}
{"tipo": "pruebas", "clases": "todas", "minimo": 3, "texto": "Tus 3 pruebas pasan"}
```

- **`--probar`:** valida estos turnos (tipos, nombre de proyecto, comodines) y **no** los prueba contra `solucion/`; en cambio **informa con ℹ** (nunca ✘) cómo saldrían hoy contra el proyecto real, en una copia temporal, punto por punto. Los `http` no se corren.
- **Tutor:** en los turnos de código recibe una línea «Este Tu turno revisa «carrito» (ruta; Maven en api/)», para no confundir el proyecto de ese paso con el de otros.

#### Python, JavaScript, Git y la terminal (`revisores.py`)

Además de Maven, `pide` y los `si` de `errores` aceptan cuatro tipos más (también sin IA). El código vive en `revisores.py` y se prueba solo con `python tutor-pantalla/revisores.py --probar` (vitest, con `--probar --vitest <carpeta con node_modules>`).

```json
{"tipo": "pytest", "archivos": ["tests/test_profe.py"], "ocultas": true, "texto": "Pasas las pruebas del profe"}
{"tipo": "pytest", "archivos": "todas", "minimo": 3, "texto": "Tus pruebas pasan"}
{"tipo": "vitest", "archivos": ["src/Lista.test.jsx"], "ocultas": true, "texto": "La lista pasa las pruebas"}
{"tipo": "git", "en_curso": "ninguno", "sin_conflictos": true, "merge": true, "ancestro": "otra-rama", "texto": "Uniste la rama"}
{"tipo": "comando", "cmd": "bash contar.sh app.log", "codigo": 0, "salida": {"regex": "^2\\s*$"}, "texto": "Tu script cuenta 2"}
```

- **`pytest`** y **`vitest`**: como `pruebas`, pero por **archivo** (rutas relativas al proyecto) o `"todas"`, con `minimo` y `ocultas` (las de `<curso>/pruebas/<stem>/` se copian **respetando su ruta** dentro del proyecto). Una sola corrida por tipo y por Comprobar, en una **copia temporal**; si falla, «falta» trae la primera prueba que falló y su mensaje (`test_neg: AssertionError: suma con negativos`). Python: el `.venv` (o `venv`) del proyecto; si la copia no lo tiene (en `--probar`, la de `solucion/`), el del proyecto del estudiante; si no, `"python"` de `curso.json`, y si no, el del PATH. Vitest: `node node_modules/vitest/vitest.mjs run --reporter=json`, con el `node_modules` del proyecto **enlazado** (unión de Windows, no se copia; se quita antes de borrar la copia y el original queda intacto). Sin `node_modules/vitest`: «falta instalar las dependencias (npm install…)».
- **`git`**: lee el repositorio del proyecto **sin tocarlo** (comandos de lectura, `GIT_OPTIONAL_LOCKS=0`: ni siquiera refresca el índice). Todas las claves que pongas tienen que cumplirse: `rama`, `limpio` (sin cambios pendientes), `sin_conflictos` (ni archivos *unmerged* ni marcas `<<<<<<<`/`>>>>>>>`), `en_curso` (`ninguno`, `merge`, `rebase`, `cherry-pick`, `revert`), `merge` (el último commit es un merge), `commit` (regex o lista: algún commit de la historia lo dice en su mensaje), `desde` (limita `commit` y `commits` a `desde..HEAD`), `commits` (mínimo), `ancestro` (esa rama ya está unida), `existe_rama`, `igual_a` (HEAD igual que esa ref: p. ej. `origin/main` tras el push) y `salida` (`{"cmd": ["log", "origin/main", "--format=%s"], "contiene"/"no_contiene"/"regex"}`, solo subcomandos de lectura: `push`, `branch -D`, `branch <nueva>` y parecidos se rechazan al cargar el curso). En un `si`, todas sus claves juntas son la condición: `{"tipo": "git", "merge": true, "salida": {"cmd": ["show", "HEAD:recetas.py"], "no_contiene": "math.ceil"}}`.
- **`comando`**: corre `cmd` en una **copia temporal** del proyecto con `shell` `bash` (el de Git for Windows, no el de WSL; por defecto), `powershell`, `cmd` o `ninguno`; revisa `codigo` (0 por defecto; `null` = no mirar), `salida` y `stderr` (`contiene`/`no_contiene`/`regex`), `crea` (archivos que tienen que existir después), con `env`, `entrada` (stdin) y `timeout` (30 s). Lo escribe el autor del curso, nunca el estudiante.
- **`"armar"` en `curso.json`** (para lo que no cabe en `solucion/`, como un repositorio con su historia): un script `python <armar> <stem> <estado> <destino>` que arma el proyecto del módulo en `inicio`, `solucion`, o por turno `p<N>-inicio`, `p<N>-solucion` y `p<N>-error<k>` (el error típico k del Tu turno del paso N); sale con 2 si ese estado no existe. Con `armar`, `--probar` prueba cada Tu turno de código así: solución → **bien**, inicio → **no** bien, cada `error<k>` → **su** mensaje. Ejemplo típico: un curso de Git cuyo `armar.py` arma el taller con su historia y un remoto *bare* al lado (hace de GitHub).
- **`"lectura"` en `curso.json`**: carpetas solo para leer (p. ej. el repo real del estudiante). Cuentan como carpetas del curso para el tutor (Read y Glob, nunca secretos) y para ubicar la línea abierta en VS Code. Un `senalar` con `"archivo"` (absoluto o relativo a esas carpetas) y `"linea"` abre antes ese archivo en VS Code en esa línea (`code -r -g`) y la marca: sirve para pasos «En tu código».
- El aviso «Revisando… (corriendo tus pruebas, ~N s)» sale también con `pytest` y `vitest`.

## Marcas en SVG, 🎯 Reajustar, ✏️ Señalar e ilustraciones en el chat

Todo esto está en los 4 paneles (asistente, curso, Excel y Dia). El contrato entre las piezas está en `CONTRATO-MARCAS.md`.

- **Marcas en SVG:** las flechas ya no las dibuja `overlay_dia.py` con Pillow.
  - **Cómo se dibujan:** `marcador.py` (con la misma forma de uso) las convierte en la forma `"marca"` (`formas_marcas.js`), la página las dibuja y `capa.py` las proyecta en el grupo `marcas` (Dia: `marcas_dia`, para que no se borren con las del tutor).
  - **Cómo se ven:** entran dibujándose (350 ms), llevan el número en un círculo y tienen versión oscura si el fondo de la app es oscuro (lo mide `tema_detras` en la captura).
  - **Respaldo:** si la página no puede dibujarlas, vuelve `overlay_dia.py`.
  - **Diseño:** el «Kit de anotaciones» de Claude Design (`marcas.js`, funciones puras): notas sólidas con halo, marco con tinte del 7 %, flecha curva, pastilla al borde, resaltador, corchete, «mira aquí» y los íconos de los botones. `formas_marcas.js` lo adapta a la colocación; sin él, usa sus piezas provisionales.
- **🎯 Reajustar** (`reajustar.py`, botón de `marcas_ui.js`): tras un zoom, un scroll o cambiar el tamaño, cada marca y cada dibujo vuelve a donde está ahora lo que señalaba, y **se desliza** hasta allí (250 ms).
  - **Un control con nombre:** se vuelve a leer la lista de controles, sin imagen.
  - **Una celda, un paso del curso, la interfaz de Dia o una línea:** lo vuelve a ubicar el panel (`registrar_rehacer`).
  - **Lo que solo está en la imagen:** se busca el trozo de la captura vieja en la ventana con 12 escalas (correlación con FFT en numpy, unos 0.8 s por marca). La ventana se lee solo en la PC y solo al pulsar el botón, como la lupa (lo aprobó él).
  - **Lo que quedó fuera de la vista:** una pastilla al borde («↓ Negrita, más abajo»).
  - **Lo que no aparece** (liso, repetido o cortado): no se adivina; se esconde y sale la tarjeta «¿Vuelvo a mirar?».
  - **Solo con el botón:** no hay modo automático, porque para lo que está solo en la imagen haría falta leer la pantalla todo el tiempo.
- **Texto enlazado** (`marcas_ui.js`): la palabra de la respuesta que corresponde a una marca sale subrayada. Al pasar el ratón por encima, la marca late sobre la app (`capa.py`, orden `latir`).
- **✏️ Señalar** (`senalar.py` + `senalar_ui.js`): encierras algo de la app con el ratón y sale la vista previa de siempre con tu trazo pintado. El tutor recibe la zona y los controles que encerraste. Nada sale sin «Adjuntar» y sin enviar.
- **Ilustraciones en el chat** (`ilustraciones_ui.js`, reglas `REGLAS_ILUSTRACIONES` de `ojos_panel.py`):
  - `$…$` y `$$…$$` con MathJax (📋 LaTeX; copiar devuelve el LaTeX; «$5» y «$B$2» no son fórmulas).
  - Bloques ` ```svg Pie ` con colores por nombre que siguen el tema.
  - Bloques ` ```grafica {json} `: una gráfica exacta, con un intérprete de expresiones propio (sin `eval`).
  - Bloques ` ```3d {json} `: figura 3D exacta que se **gira arrastrando** (superficies, sólidos de revolución con disco o capa, curvas, vectores, planos, sólidos, cargas y campos). Motor: `motor_3d.js`; contrato y formato en `CONTRATO-3D.md`.
  - Cada figura trae Ampliar, Copiar SVG, Guardar PNG (a Descargas) y «Ponlo en la app». En 3D copian la vista que dejaste, «Ponlo en la app» la pone girando sola encima de la app (forma `"3d"`), «Editar en la tarjeta» la abre en Geometría como guion y **GIF** (vaivén o vuelta entera) la guarda en Descargas y la copia como archivo (`gif3d.py`).
  - En 3D también hay marcas de geometría (`angulo`, `marcaangulo`, `angulorecto`, `marcaigual`, `"angulos": true` en polígonos), anotaciones que se apagan (`ejes`, `numeros`, `nombres`, `medidas`) y `relleno` opaco o transparente para toda la figura.
  - Pruebas: `node tutor-pantalla/probar_ilustraciones.js` y `node tutor-pantalla/probar_3d.js`.

## Archivos

| Archivo | Qué es |
|---|---|
| `archivos.py` | Leer archivos: carpetas de lectura libre del curso, argumentos de `claude` (`--add-dir`, secretos negados), la tarjeta `<pedir_archivo/>` (permiso por archivo) y la lectura del archivo como adjunto. `python archivos.py` = pruebas. |
| `celular.py` | Fotos del celular (botón «Foto del celular» junto al clip, en todos los paneles): abre sesión (código + QR), recoge las fotos (el servicio las borra al entregarlas) y cierra al salir. Config en `.env` (`FOTOS_URL`, `FOTOS_CLAVE`; plantilla `.env.example`; `.env` no va al repo). `python celular.py --probar [url clave]`. |
| `fotos_celular.py` + `fotos_celular.html` | **Buzón de fotos**: una ventanita solo para recibir fotos del celular y **arrastrarlas** (a una guía, al chat de Claude). Las guarda en una carpeta temporal; **arrastrar es nativo** (WebView2 no deja sacar imágenes de la ventana, así que al empezar a arrastrar la ventana de Windows hace `DoDragDrop` con el archivo, como el Explorador; solo con el botón apretado), con «Copiar» (portapapeles, Ctrl+V), «Quitar» y «Abrir carpeta»; al cerrar borra la carpeta y la sesión. `python fotos_celular.py` / `--probar`. |
| `fotos-servidor/` | El servicio de las fotos (Node; ver su README). |
| `practica.py` | Modo práctica: estado (`practica.json`), reglas y prefijo del tutor, y `PracticaApi` (lo que llama la página). `python practica.py` = pruebas. |
| `ejercicios_tutor.py` | Ejercicios que crea el tutor del modo curso (`<ejercicio>`): archivo nuevo + pruebas ocultas en código, `pide` en apps; tarjeta de permiso y Comprobar. `python ejercicios_tutor.py [--maven <copia>]` = pruebas. |
| `ojos.py` | El núcleo: lista de ventanas, miniaturas, captura de una ventana (`Captura`: imagen reducida a 1400 px de lado largo, controles en píxeles de la imagen, recorte y conversión a la pantalla). `python ojos.py --lista` / `--capturar "texto" salida.png`. |
| `asistente.py` | La sesión `claude -p` (stream-json, sin MCP ni ajustes, como el tutor de Excel; con solo WebSearch y WebFetch), sus reglas y cómo se leen las marcas (`MARCAS: [...]` al final de la respuesta). |
| `ojos_panel.py` | Los ojos para cualquier panel: `Ojos` (capturas con permiso, adjuntos, contexto para el tutor, marcas `"ventana"` y flechas), `OjosApi` (lo que llama la página), `REGLAS_OJOS` (lo que se le explica al tutor), `inyectar_ui` y el proceso de las flechas. `python ojos_panel.py --probar` (sin ventanas ni IA). |
| `ojos_ui.js` | La lista de ventanas con miniaturas y la vista previa (Cancelar / Recortar / Adjuntar), para la página de cualquier panel. |
| `preguntas_ui.js` | Las tarjetas de preguntas del tutor en el chat (opción única o múltiple, abiertas, «Otra…», «No sé»), con la corrección al instante. |
| `panel_pantalla.py` | El panel del asistente (pywebview): la API que llama la página, el modo puente y la prueba `--probar`. |
| `capacidades.py` | Lo que comparten todos los tutores con el asistente: el bloque del prompt (`reglas`), `ConWeb` (WebSearch/WebFetch), `raices_curso`, `contexto_editor`, `ubicar_linea` y `marcas_linea`. `python capacidades.py` prueba sin ventanas. |
| `editor_vscode.py` | Leer el editor de VS Code sin tocarlo: archivo abierto, cursor y rectángulo de una línea (`rect_linea`). |
| `ustx.py` | Revisión sin IA de proyectos de OpenUtau (`.ustx`) para el tipo `ustx` del modo curso: lee notas, letras, pistas y curvas y dice lo primero que falla («la nota 3 está en F4 (fa) y va en G4 (sol)»); kana ↔ romaji. `python ustx.py --probar`. |
| `curso_pantalla.py` | El modo curso: cargar el curso, leer el estado de la app, revisar el «Tu turno» sin IA, buscar lo que se señala y el estado en texto para el tutor. También los cursos de código: `ContextoCodigo`, `correr_maven`, `peticion` (ver «Cursos de código»). |
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
| `muestras/*.json` | Lotes de ejemplo de cada forma, para `probar_dibujos.py` (`svg_animado.json`: SMIL, CSS y un SVG trampa que debe quedar filtrado; `marcas.json`: la forma «marca» en claro, oscuro y «fuera»). |
| `marcas.js` | El «Kit de anotaciones» de Claude Design, tal cual (no se edita a mano): `Marcas.piezas`, `Marcas.iconos`, `Marcas.tiempo`. |
| `formas_marcas.js` | La forma «marca» (las flechas de siempre, en SVG): marco, nota con número, flecha, entrada animada, versión oscura y pastilla «fuera». Las piezas de dibujo, en `Marcas.piezas`. |
| `marcador.py` | El sustituto de `overlay_dia.py` (misma forma de uso): pasa las marcas a la forma «marca» y las manda a la página; sin página, usa el overlay viejo. `python marcador.py --probar`. |
| `reajustar.py` | 🎯: vuelve a encontrar lo señalado (controles por nombre; o el trozo de imagen con varias escalas, correlación con FFT). `python reajustar.py --probar`. |
| `marcas_ui.js` | El botón 🎯 Reajustar y el texto enlazado (la palabra de la respuesta hace latir su marca). |
| `senalar.py` + `senalar_ui.js` | ✏️ Señalar: ventana que recoge el trazo con el ratón sobre la app, y el botón y el flujo hasta la vista previa. `python senalar.py --probar`. |
| `ilustraciones_ui.js` | Fórmulas, figuras SVG, gráficas exactas y figuras 3D girables dentro del chat, con sus botones. `node probar_ilustraciones.js` prueba el intérprete de expresiones y los bloques. |
| `motor_3d.js` | El motor 3D común (chat, Tarjeta SVG y forma `"3d"`): spec JSON y guion 3D → SVG, girable. Usa `motor_figuras.js` (intérprete con varias variables, estilo y texto). `node probar_3d.js` = pruebas. |
| `gif3d.py` | El GIF de una figura 3D: fotogramas PNG de la página → `.gif` en bucle (Pillow, paleta común con tramado), guardado en Descargas y copiado como archivo. `python gif3d.py --probar`. |
| `formas_3d.js` | La forma de dibujo `"3d"`: la figura encima de la app, girando sola (vaivén o vuelta entera), con fotogramas de `motor_3d.js`. Muestras: `muestras/3d.json` y `3d_vuelta.json`. |
| `CONTRATO-3D.md` | El contrato de las figuras 3D: API del motor, formato JSON, guion 3D, y qué hace cada pieza. |
| `barra_ventana.js` | La barra de la ventana de los cuatro paneles: van sin el marco de Windows (sin el logo de Python) y aquí se ponen minimizar y ✕, como en la Tarjeta SVG. Arrastrar desde la barra de arriba (pestañas o la fila del asistente); los botones y pestañas no arrastran. Python: `OjosApi.ventana_minimizar/ventana_cerrar`. |
| `CONTRATO-MARCAS.md` | El contrato entre las piezas de lo anterior (quién hace qué y con qué forma). |
| `para-claude-design/` | El encargo del kit de anotaciones a Claude Design, con capturas de cómo se veía antes; lo que entregue va a `recibido/`. |
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
