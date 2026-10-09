# Panel de curso en vivo para Excel

Un panel que flota encima de Excel para dar un curso paso a paso:
- **← Anterior / Siguiente →** mueve Excel en vivo.
- Un selector cambia de **módulo**. Cada módulo vive en su propia hoja de un libro del curso, que se guarda en disco.
- La zona **"Tu turno"** se revisa con el botón **Comprobar**: sin IA, al instante y sin gastar. Mientras trabajas no te marca nada.
- Un **tutor** que conoce el curso entero lee tu hoja, contesta y la marca con flechas y notas (en la hoja que tienes al frente o en la que él elija; ver «Marcas del tutor»). Acepta **capturas, PDF y archivos de texto**.
- El tutor también puede **cambiar el libro** (armar un ejercicio parecido en una hoja nueva, completar un ejemplo, dar formato, crear una tabla y, con el **modo libre**, casi cualquier cosa de Excel: gráficos, tablas dinámicas, formato condicional, validación, nombres, segmentaciones…), pero **siempre pide permiso**: muestra una tarjeta con **Aplicar / No** y, después, **Deshacer**. Los ejercicios que arma se revisan con su propio **Comprobar**, sin IA.
- Todo va en **una ventana** pegada a la derecha, a todo el alto de la pantalla, con dos pestañas: **Lección | Tutor**.
- **Para cursos avanzados:** fórmulas de **matriz dinámica** (FILTRAR, ORDENAR, UNICOS, SECUENCIA, BUSCARX, LET…) que se desbordan, ejercicios de **objetos** (gráfico, tabla, dinámica, formato condicional, validación, nombres, orden, filtros, inmovilizar, formato de número) revisados sin IA, **Power Query** con orígenes seguros, **Buscar objetivo, tablas de datos, escenarios** (y Solver si está activado) y **VBA** con cuidado (leer, marcar y proponer código; Comprobar ejecuta la macro de la persona en una copia). El panel **recuerda el módulo y el paso** donde te quedaste.

```
python panel-excel/panel_web.py <carpeta-del-curso>/curso.json      # un curso con módulos
python panel-excel/panel_web.py panel-excel/ejemplo_leccion.json     # una lección suelta (ejemplo)
python panel-excel/panel_web.py panel-excel/ejemplos/avanzado/curso.json   # curso de ejemplo avanzado (plantilla)
python panel-excel/panel_web.py panel-excel/ejemplo_leccion.json --probar --rapido   # comprobar que todo va (menos de un minuto)
```

Los cursos van en **su propia carpeta en la raíz** del tutor (una por tema, por ejemplo `curso-excel/`, con su README), nunca dentro de `panel-excel/`: aquí solo vive el motor, y el repositorio del tutor no versiona nada más de esta carpeta.

## Archivos

- `panel_web.py`: abre el panel (pywebview, motor de Edge) y conecta la página con Excel y el tutor. Al cerrar, borra las copias ocultas del modo libre (`Libro.limpiar_copias`) y guarda.
  - Todo lo de Excel pasa por un solo hilo (`HiloExcel`), porque COM no se puede usar desde otros.
  - Entre trabajo y trabajo, ese hilo vigila cada 0,7 s la zona del "Tu turno". No la revisa: solo avisa a la página si cambió después de pulsar Comprobar.
  - El libro se guarda al cambiar de paso y al cerrar.
  - `preguntar` dibuja las marcas del tutor cada una en su hoja (`Libro.dibujar_marcas`) y, si alguna no se pudo, lo dice en el chat y se lo cuenta al tutor. `borrar_marcas` las quita en todas las hojas. Al cambiar de paso, `ir` olvida las de la hoja del módulo (se rehízo).
  - Para las propuestas del tutor, la página llama a `aplicar`, `rechazar`, `deshacer(id, forzar)`, y para su ejercicio a `comprobar_ejercicio`, `ir_ejercicio` y `quitar_ejercicio`. El vigía también avisa si cambió la zona del ejercicio del tutor después de comprobar.
- `motor.py`: la lógica.
  - `Curso`: lee `curso.json` o una lección suelta.
  - `Libro`: abre o crea el libro del curso y la hoja de cada módulo. También dónde caen las marcas del tutor (`destino_marcas`, `dibujar_marcas`, `borrar_marcas`, `frente`) y qué le cuenta del libro (`contexto_extra`).
  - `Clase`: construye cada paso y guarda lo que escribe el estudiante, incluso columnas que agrega a una tabla. También revisa el "Tu turno" y dibuja las marcas.
  - `Hoja`: lo común a cualquier hoja (revisar un «Tu turno», marcas). `Clase` es una `Hoja`; las hojas que crea el tutor también.
  - Propuestas del tutor (`separar_acciones`, `validar_propuesta`, `Libro.preparar / aplicar / deshacer / rechazar`) y su ejercicio (`Libro.ejercicio`, `comprobar_ejercicio`). Ver «Cambios que propone el tutor».
  - Modo libre: `ModoLibre` (ejecuta los pasos y revisa cada objeto), `_validar_libre` (revisión sin Excel), `describir_paso` / `resumen_libre` / `codigo_paso` (lo que muestra la tarjeta) y, en `Libro`, la copia para deshacer (`_tomar_copia`, `_restaurar_copia`, `limpiar_copias`), los nombres y segmentaciones (`_estado_libro`, `_revertir_libro`) y la hoja interna para traducir fórmulas (`_celda_aux`). Ver «Modo libre».
  - `Hoja.objetos()`: lo que hay en una hoja además de celdas (tablas, gráficos, dinámicas, formato condicional, validación), para el [Estado actual] del tutor.
  - `Tutor`: deja abierta una sesión de Claude Code (`claude -p` con stream-json) que conoce todos los módulos. Arranca una vez, en unos 6–11 s y en segundo plano, sin herramientas ni ajustes (`--setting-sources ""`: no carga hooks ni avisos de nadie). Después responde en unos 2–3 s y el texto va apareciendo. Se reinicia cada 15 preguntas, y también después de un error (por ejemplo, un adjunto que la API rechaza), para que ese mensaje no rompa los siguientes.
  - `mensaje()`: arma el mensaje con adjuntos (ver «Adjuntos del tutor»).
- `avanzado.py`: lo avanzado que usa `motor.py`: el **Comprobar de objetos** (`revisar_objetos`, un `chk_…` por tipo), el **inventario** de la hoja (lo que hay además de celdas, para conservar lo de la persona al cambiar de paso: `inventario`, `recrear`, `base_objetos`), **Power Query** (`validar_m`, `crear_consulta`, `quitar_consulta`, `revertir_consultas`) y las **herramientas de análisis** (`ejecutar`, `validar_accion`, `describir`).
- `vba.py`: **VBA**: acceso (`acceso`, `ACCESO`), análisis estático (`problemas`, `analizar`), leer y marcar módulos (`modulos`, `contexto`, `marcar`, `borrar_marcas`), proponer y deshacer código (`aplicar`, `restaurar`) y el Comprobar de una macro (`revisar`, `instrumentar`, `comparar`).
- `ejemplos/avanzado/`: curso de ejemplo avanzado y plantilla (4 módulos cortos: matrices dinámicas, gráficos y formato condicional, Power Query con `datos/ventas.csv`, VBA). Ver su README. Su libro (`Curso_Avanzado.xlsm`) y `progreso_panel.json` se generan al abrirlo.
- `progreso_panel.json` (junto a cada `curso.json`, se genera): módulo y paso donde se quedó la persona. No va al repositorio.
- `ejemplo_leccion.json`: lección de ejemplo (referencias absolutas `$`: 7 pasos y un «Tu turno» con 8 errores típicos). Sirve de plantilla y para probar el motor. Se abre en un libro sin guardar.
- `panel.html`: la página del panel. **Diseño de Claude Design** (proyecto «Panel.dc.html», pasado a JavaScript sin React), con letra Atkinson Hyperlegible. Se abre en **una sola ventana** de 460 px, pegada a la derecha y a todo el alto del área visible (sin la barra de tareas; respeta la escala de Windows, 125 % o 150 %).
  - Arriba, dos **pestañas tipo carpeta**: **Lección** (módulo, pasos y revisión automática) y **Tutor** (el chat). Cada una ocupa todo el alto que queda.
  - Si estás en Lección y el tutor contesta, la pestaña Tutor muestra un **puntito**. Se borra al abrir la pestaña.
  - «Pregúntale al tutor» (en la revisión automática) cambia a la pestaña Tutor y hace la pregunta allí.
  - Las flechas ← → del teclado mueven los pasos solo con la pestaña Lección abierta.
  - Al cargar, la página llama a `api.listo()` y Python imprime `ventana lista` (sirve para comprobar que abrió bien).
  - Lección: cabecera con el curso, el **menú de módulos**, el título con su etiqueta (`$`, `Ctrl+T`…) y la barra de pasos; la tarjeta del paso (con su título), el recuadro **«En Excel»** (dónde se hace), el «Tu turno» con su botón **Comprobar** y Anterior / Siguiente (en el último paso, «Siguiente módulo»).
  - Lección, debajo del «Tu turno»: la tarjeta **«Ejercicio del tutor»** (hoja y rango, su **Comprobar**, «Ir a la hoja» y una ✕ que quita la tarjeta sin borrar la hoja). Si la revisión trae `puntos` (una lista `{ok, texto}`, como la de Dia), los muestra como lista con ✔ y ✘, igual que el «Tu turno».
  - Tutor: la **tarjeta de permiso** cuando el tutor propone un cambio (ver «Cambios que propone el tutor»).
  - Tutor: mensajes sin globo y con bloques (párrafos, listas numeradas, bloques de código con **Copiar** y el aviso «Marqué N cosas en tu hoja»), «Pensando… N s» mientras espera, el texto llegando con un cursor, y la caja de escribir con adjuntos.
  - **Tema:** lo pone `preferencias.json` (`claro`, `oscuro` o `auto` = el de Windows). Sin ese archivo, claro.
  - Abierta en un navegador como `panel.html?demo` (también `&pestana=tutor` y `&tema=oscuro`), muestra el diseño con datos de ejemplo: una conversación con una propuesta aplicada (hoja nueva con ejercicio) y otra pendiente con avisos, y el ejercicio del tutor en Lección. Los botones funcionan (simulados).
  - Todo lo nuevo es opcional: si la Api no tiene `aplicar` (el panel de Dia), no se muestran tarjetas de permiso.
  - **La usa también Dia** (`../prueba-dia/panel_dia.py`), que pone dos variables antes de cargarla. `window.OBJETO_PANEL` es «hoja» en Excel y «diagrama» en Dia, y sale en los textos: «Leyendo tu diagrama…», «Marqué N cosas en tu diagrama». `window.APP_PANEL` es la app («Excel» o «Dia»); también llegan por `estado().objeto` y `estado().app`.
  - Con «diagrama», el botón del ejercicio dice **«Ir al diagrama»**, y la confirmación de Deshacer, **«¿Deshacer igual?»** con el botón **«Deshacer igual»** (en Excel, «¿Borrar la hoja?» y «Borrar igual»).
  - La tarjeta puede traer `confirmar_titulo` y `confirmar_boton` para ese momento. El modo libre los usa cuando la hoja cambió después de aplicar: «¿Deshacer igual?», porque ahí la hoja vuelve a como estaba y no se borra.
  - `panel.html?demo&app=dia` muestra el demo con los textos y datos de Dia.
  - **Recuadro amarillo en Lección** (`estado().requisito`): lo que le falta a Excel para el módulo (acceso al código VBA, Solver) y cómo activarlo.
  - **Código en la tarjeta** (`codigos`: `[{titulo, texto}]`): el código VBA que propone el tutor, entero y con «Copiar»; «Ver los cambios» sale abierto.
  - **Botones del paso** (`botones`, los usa Dia): si un botón trae `"confirmar": "texto"` (y opcional `"confirmar_boton"`), la página pide confirmación en un recuadro antes de llamar a `api.boton`; sin eso, igual que antes. Mientras corre, el botón queda desactivado con «…». Al cambiar de módulo dice «Preparando el módulo en Excel…» o «en Dia» (la app de `APP_PANEL`).
  - El demo (`?demo&pestana=tutor`) trae también una propuesta de código VBA; el de Dia, un botón «Hazlo por mí» con confirmación.
- `preferencias.json`: preferencias de la persona para el panel. Hoy solo `{"tema": "claro"}`. Lo crea el instalador según lo que conteste.

## Adjuntos del tutor

En el chat se pueden mandar **capturas, PDF y archivos de texto** junto a la pregunta (o solos):
- **Pegar** una imagen con Ctrl+V en el cuadro de texto (una captura con Win+Shift+S). Si lo copiado también trae texto (por ejemplo, celdas de Excel, que se copian con texto y dibujo), se pega el texto y no se adjunta nada.
- **Arrastrar y soltar** archivos en cualquier parte del panel: se abre la pestaña Tutor y quedan adjuntos.
- El botón **📎** para elegirlos.

Antes de enviar se ven las miniaturas, cada una con una ✕ para quitarla; en la burbuja del mensaje queda la miniatura o el nombre del archivo.

| Tipo | Cómo llega al tutor | Límite |
|---|---|---|
| Imagen (png, jpg, gif, webp) | bloque `image` en base64. Si el lado mayor pasa de 1600 px, la página la reduce con un canvas (PNG para capturas, JPEG si queda muy pesada) | 15 MB al elegirla |
| PDF | bloque `document` en base64 (Claude Code lo acepta por stream-json: comprobado) | 5 MB |
| Texto (.txt, .md, .csv, .json, .py, .m…) | se pega al texto del mensaje con su nombre | 300 KB |
| Otros | no se envían: aviso «no se admite» | — |

Máximo 5 adjuntos por mensaje. `motor.mensaje()` vuelve a revisar tipos y tamaños (máximo 8 MB por imagen o PDF) y arma el mensaje con `content` como lista de bloques, en el formato de la API de Anthropic. Lo comprobado (2026-10-08, Claude Code 2.1.284): con una imagen de prueba (un cuadrado rojo con «HOLA») el tutor responde «cuadrado rojo con la palabra HOLA en blanco», y con un PDF lee su texto.

Ojo con el gasto: las imágenes se quedan en la conversación y cuentan en cada pregunta siguiente hasta que la sesión se reinicia (cada 15 preguntas).

## `curso.json`

```json
{ "titulo": "Excel desde cero", "libro": "Curso_Excel.xlsx", "modelo_tutor": "sonnet",
  "modulos": ["m1_referencias.json", "m2_tablas.json"],    // archivos junto a curso.json
  "macros": true,      // opcional: el libro es .xlsm (si había un .xlsx, se guarda una copia .xlsm y se sigue con ella)
  "datos": "datos" }   // opcional: carpeta de datos (lo único de fuera del libro que puede leer Power Query: {datos}/archivo.csv)
```

El libro se crea junto a `curso.json`. El panel recuerda dónde te quedaste en `progreso_panel.json`, junto a `curso.json` (si el archivo no cuadra con el curso, empieza desde el principio). Si en vez de un curso se le pasa una lección suelta, la abre **siempre en un libro nuevo sin guardar** (nunca reutiliza un libro abierto: podría ser de la persona y se vaciaría).

## Una lección (módulo)

```json
{
  "titulo": "Tablas", "titulo_codigo": "Ctrl+T", "hoja": "M2 Tablas",
  "tema_tutor": "de qué va el módulo (para el tutor)",
  "notas_tutor": "lo que el tutor sabe y no revela entero: objetivo y solución del Tu turno",
  "pasos": [ { "titulo": "Fijar con $", "acciones": [ ... ], "texto": "Lo que dice el panel. {C5} = valor que muestra C5; {f:C5} = su fórmula.",
               "donde": "Dónde se hace en Excel: **Fórmulas** → **Rastrear precedentes**", "turno": { "titulo": "Descuento e IVA · E4:E7", ... } } ]
}
```

`titulo` (del paso y del «Tu turno») y `donde` son opcionales: si faltan, el panel no los muestra. En `donde`, lo que va entre `**` sale como una tecla o un botón. `"requiere": ["vba"]` (o `"solver"`) en la lección hace que el panel avise en Lección, con un recuadro amarillo, si a este Excel le falta eso y cómo activarlo (también se deduce de los pasos).

Cada paso **se suma** a los anteriores: el paso 3 es la hoja vacía más las acciones de los pasos 1, 2 y 3.

### Acciones (una por objeto)

| Acción | Ejemplo |
|---|---|
| Poner un valor o una fórmula | `{"poner": "B1", "valor": 0.12, "formato": "0%"}` · `{"poner": "C4", "valor": "=B4*(1+B1)"}` |
| Poner un bloque | `{"poner": "A4:B5", "valores": [["Cuaderno", 15], ["Lápiz", 2]]}` |
| Copiar (como arrastrar) | `{"copiar": "C4", "a": "C5:C7"}` |
| Color de fondo | `{"color": "C5:C7", "es": "rojo"}` (rojo, verde, amarillo, azul o ninguno) |
| Negrita / ancho | `{"negrita": "A3:C3"}` · `{"ancho": "A:D", "valor": 14}` |
| Escribir las fórmulas como texto | `{"mostrar_formulas": "C4:C7", "en": "D4:D7"}` |
| Seleccionar / precedentes | `{"seleccionar": "C4"}` · `{"precedentes": "C7"}` |
| Crear una tabla | `{"tabla": "A1:D7", "nombre": "Ventas", "estilo": "TableStyleMedium2"}` |
| Columna calculada | `{"columna_tabla": "Ventas", "nombre": "Total", "formula": "=[@Precio]*[@Cantidad]"}` |
| Añadir una fila | `{"fila_tabla": "Ventas", "valores": ["Tijeras", "Útiles", 12, 3]}` (**antes** de activar los totales) |
| Fila de totales | `{"totales": "Ventas", "columna": "Total", "funcion": "suma"}` (suma, promedio, contar, minimo, maximo) |
| Filtrar / quitar filtros | `{"filtrar": "Ventas", "columna": "Categoría", "igual_a": "Útiles"}` · `{"quitar_filtros": "Ventas"}` |
| Borrar | `{"borrar": "A1:C5"}` (solo el contenido) · `{"borrar": "A1:C5", "formato": true}` (también el formato) |
| Formato de número | `{"formato_numero": "E1", "es": "porcentaje"}` (porcentaje, porcentaje_decimal, moneda, entero, decimal, miles, fecha, hora, texto, general, o un código en inglés como `"0.0%"`) |
| Cursiva / color de letra | `{"cursiva": "A2"}` · `{"color_letra": "B1", "es": "rojo"}` (rojo, verde, amarillo, azul, negro); `negrita` y `cursiva` aceptan `"valor": false` para quitarla |
| Bordes / alinear | `{"bordes": "A1:C5"}` (`"es": "ninguno"` los quita) · `{"alinear": "A1:C1", "es": "centro"}` (izquierda, centro, derecha) |
| Ajustar el ancho | `{"ajustar_ancho": "A:C"}` |
| Ordenar | `{"ordenar": "A1:C9", "por": "C", "orden": "desc"}` (con encabezados; `"encabezado": false` si no los hay) |
| Inmovilizar paneles | `{"inmovilizar": "B2"}` (fija las filas de arriba y las columnas de la izquierda de B2) · `{"inmovilizar": "no"}` |

Las fórmulas van en inglés y con coma (`=SUM(A1,B1)`), que es como las entiende Excel por dentro; luego las muestra traducidas. Se escriben con `Formula2`: las de matriz dinámica (`=FILTER(...)`, `=SORT(UNIQUE(...))`) se desbordan como si las tecleara la persona. Los formatos de número también en inglés (`"0.0%"`, `"dd/mm/yyyy"`): el motor los traduce al idioma de Excel.

Más acciones (las de las lecciones y las del tutor; las del tutor siempre con permiso):

| Acción | Ejemplo |
|---|---|
| Modo libre (ver «Modo libre») | `{"com": [{"ruta": "ChartObjects.Add", "args": [300, 10, 380, 230], "guardar": "g"}, …]}` |
| Consulta de Power Query | `{"consulta": "VentasLimpias", "m": "let … in …", "cargar_en": "E1"}` (sin `cargar_en`: solo conexión; si ya existe, cambia su M) · `{"actualizar": "VentasLimpias"}` (`"todo"`) |
| Buscar objetivo | `{"buscar_objetivo": "B5", "valor": 100, "cambiando": "B2"}` |
| Tabla de datos | `{"tabla_datos": "D1:E8", "columna": "B2"}` (`"fila"` para la entrada de arriba; la fórmula en la esquina) |
| Escenarios | `{"escenario": "Optimista", "celdas": "B2:B3", "valores": [120, 0.1]}` · `{"mostrar_escenario": "Optimista"}` |
| Solver (si está activado) | `{"solver": "B10", "tipo": "max", "cambiando": "B2:B5", "metodo": "simplex", "restricciones": [{"celda": "B2:B5", "es": ">=", "valor": 0}]}` |
| Código VBA | `{"vba": "Macros", "codigo": "Sub X()\n…\nEnd Sub", "modo": "reemplazar"}` (`"agregar"` lo añade al final; módulo normal) |

### Cambiar de paso: qué se quita y qué se conserva

Cada paso se rehace desde la hoja vacía (`Clase._limpiar` y `_construir`): se quitan las celdas, las tablas, los gráficos y formas que pusieron los pasos (se renombran `lec_N` para reconocerlos aunque se reabra el panel), las dinámicas, el formato condicional, la validación, los nombres que crearon los pasos, sus consultas de Power Query, escenarios y módulos de VBA, los filtros y los anchos de columna. Así, al volver a un paso, cada cosa está una sola vez y nada de pasos posteriores.

Lo de la persona:
- **Sus celdas** se conservan como antes (`suyo`).
- **Sus gráficos y formas** no se tocan: siguen ahí y apuntando a sus celdas.
- **Sus tablas, dinámicas, formato condicional y validación** se reconocen porque aparecieron después de rehacer el paso (`avanzado.inventario`, por su sitio y su regla) y se rehacen igual después (`avanzado.recrear`). Si algo no se puede rehacer (p. ej. su tabla quedaría encima de una de la lección), el tutor lo sabe por el [Estado actual].
- Si borra algo suyo, se olvida. No se conservan el formato de sus celdas, los anchos, los filtros de un rango y sus segmentaciones.
- Lo que el tutor puso con permiso en la hoja del módulo cuenta igual que lo de la persona; Deshacer quita sus tablas aunque se hayan rehecho.

## Marcas del tutor

El tutor termina su respuesta con `<marcas>[...]</marcas>`: `flecha` y `nota` (formas, fuera de las celdas), `resaltar` y `marco` (formato condicional) y `precedentes` (las flechas azules de Excel).

- **En qué hoja caen:** cada marca puede llevar `"hoja"`. Sin ella, va a la hoja que la persona tiene al frente en el libro del curso si es la del módulo o una que creó el tutor; si no (una hoja suya, otro módulo), a la del módulo. Con `"hoja"` vale la del módulo actual u otra hoja visible del libro del curso; la de otro módulo, la de otro libro o una que no existe se rechazan.
- Se dibujan **sin cambiar la hoja que tienes delante** (formas, formato condicional y `ShowPrecedents` funcionan en una hoja que no se ve). Si quedaron en otra hoja, el chat añade «(Las marcas están en la hoja «Práctica 1»: ábrela para verlas.)».
- **Cuándo se borran** (lo que hace el código): al llegar nuevas marcas del tutor se borran antes todas las anteriores, en todas las hojas; «Borrar marcas» las quita en todas las hojas; y las de la hoja del módulo se van al cambiar de paso, porque esa hoja se rehace. Una respuesta sin marcas no borra nada, Comprobar no las toca, y en las demás hojas se quedan hasta entonces (también si cambias de módulo).
- Nada se pierde en silencio: si una marca no se puede dibujar, el chat lo dice («No pude poner N de las marcas: …») y el tutor lo recibe en «[Del panel]». El aviso «Marqué N cosas» cuenta solo las que se dibujaron.

## Modo libre (el modelo de objetos de Excel, con permiso)

Para lo que no está en la lista de acciones, el tutor manda, dentro de `cambios`, un `{"com": [pasos]}`. Cada paso lee o pone una propiedad o llama un método, como en VBA pero en JSON y **sin código**:

```json
{"com": [
  {"ruta": "ChartObjects.Add", "args": [300, 10, 380, 230], "guardar": "g"},
  {"en": "$g", "ruta": "Chart.SetSourceData", "args": [{"rango": "A1:B6"}]},
  {"en": "$g", "ruta": "Chart.ChartType", "valor": "xlColumnClustered"},
  {"en": "$g", "ruta": "Chart.Axes(1).AxisTitle.Text", "valor": "Mes"}]}
```

- `en`: de dónde parte. `"hoja"` es la hoja de la propuesta (lo normal); `"libro"` da solo `PivotCaches`, `Names`, `SlicerCaches` e `IconSets`; `"$g"` es algo guardado antes con `"guardar": "g"`.
- `ruta`: propiedades y métodos separados por puntos, con argumentos fijos entre paréntesis (`Range('C2:C9')`, `Axes(1)`, `PivotFields('Ventas')`).
- `args` llama al último método, con los argumentos en orden; `valor` asigna la última propiedad.
- Valores posibles: números, textos, `true`/`false`, `null` (argumento omitido), constantes por nombre (`xlColumnClustered`, `xlRowField`, `xlSum`, `xlValidateList`…; tabla `motor.CONSTANTES`) o por número, `"$g"`, `"$hoja"` y `{"rango": "A1:B6"}`.
- `{"rango": "A1:C9", "hoja": "Datos"}` es un rango de otra hoja del curso. Solo sirve para **leer** datos: `SetSourceData`, `PivotCaches.Create`, `Values` y `XValues`.
- Hay más ejemplos en `motor.REGLAS`: tabla dinámica, escala de colores, formato con fórmula, lista desplegable y nombre.

**Seguridad.** Hay tres capas:

1. **Lista blanca de miembros** (`MIEMBROS`); lo que no está, se rechaza. Además hay una lista negra (`VETADOS`) para dar un mensaje claro: Application, Parent, Workbooks, Worksheets, guardar o abrir o cerrar, Quit, Run, ExecuteExcel4Macro, Evaluate, VBProject, OnAction, hipervínculos, QueryTables y conexiones, OLEObjects, AddPicture, Export y ExportAsFixedFormat, Copy, Move, Paste, Location, ShowDetail, SourceData y Protect.
2. **Revisión sin Excel** (`_validar_libre`): cada texto pasa la misma revisión que las fórmulas de siempre (sin WEBSERVICE ni HYPERLINK) y, además, no puede llevar rutas de archivo, internet ni otros libros (`[Libro]Hoja!`).
3. **Revisión al ejecutar** (`ModoLibre`): se mira el tipo de cada objeto que aparece.
   - Nunca valen un libro, Application, ventanas, conexiones ni hipervínculos.
   - Una hoja tiene que ser la de la propuesta, y cada `Range` tiene que ser de esa hoja.
   - Sobre la hoja solo se puede usar lo de `EN_HOJA`: no se puede renombrar, borrar ni ocultar.
   - Unos pocos métodos tienen reglas propias: `PivotCaches.Create` solo con `xlDatabase` (nada externo) y `CreatePivotTable` con destino en la hoja, nunca en la del módulo. `ListObjects.Add` solo acepta un rango y `Slicers.Add` va en la hoja de la propuesta.
   - Las llamadas van por IDispatch (`_invocar`), sin el atajo de pywin32, que ejecuta métodos al leerlos.
   - Si se rechaza algo al ejecutar, todo vuelve atrás (ver abajo).

**Idioma.** Este Excel en español lee algunas cosas en español: las fórmulas de `FormatConditions.Add`, `Validation.Add` y `Names.Add`, `Name.RefersTo` y las uniones de rangos (`A1:A5;C1:C5`). El tutor las escribe siempre en inglés y con coma, y el motor las traduce:
- las fórmulas, escribiéndolas en una celda de una hoja interna muy oculta y leyendo su `FormulaLocal`;
- los números (0.5 → 0,5) y las listas («Sí,No» → «Sí;No»), cambiando los separadores;
- `NumberFormat`, con `formato_local`.

**Tarjeta.**
- El resumen sale de los pasos, no del texto del tutor: «crear un gráfico de barras con B1:C9», «crear la tabla dinámica «VentasPorCategoria» en A3», «poner formato condicional en C2:C9»…
- «Ver los cambios» muestra cada paso en palabras y su código: «Título del gráfico: «Ventas» · `$g.Chart.ChartTitle.Text = "Ventas"`».
- Una nota avisa que se guarda una copia y que Deshacer la deja exacta mientras el panel siga abierto. Si es la hoja del módulo, dice qué pasa al cambiar de paso, y un aviso salta si la hoja tiene cosas que escribió la persona.

**Deshacer exacto.** Antes de aplicar, `Libro._tomar_copia` hace una copia muy oculta de la hoja (`zzpanel_…`; `Copy(None, hoja)`), sin los nombres locales que Excel añade al copiar. También se guardan los nombres definidos y las segmentaciones del libro. Deshacer (`_restaurar_copia`) hace esto:
1. Aparta la hoja con un nombre temporal, y también sus tablas, para que lo que la usaba desde otras hojas la siga.
2. Pone la copia en su sitio, con su nombre y el de sus tablas.
3. Redirige a la hoja restaurada las fórmulas de otras hojas (`Cells.Replace`), las series de gráficos, las dinámicas (`ChangePivotCache`) y los nombres definidos, y borra la vieja.
4. Vuelve a enlazar `Clase.ws` y deja la hoja activa como estaba. Si la hoja del módulo cambió de paso desde entonces, rehace el paso actual.
5. Los nombres y segmentaciones que creó o cambió la propuesta vuelven a como estaban; los que cambió la persona no se tocan.

Si la hoja cambió después de aplicar, la tarjeta pregunta «¿Deshacer igual?», porque vuelve entera. Si un paso falla a mitad, se restaura la copia, todo queda como estaba y el tutor recibe en «[Del panel]» el error de Excel, legible (`motivo`). Las copias se borran al deshacer, al cerrar el panel y al abrirlo (por si quedó alguna de una sesión anterior). Con el panel cerrado, Deshacer del modo libre ya no existe; la nota de la tarjeta lo dice.

**Lo que ve el tutor.** El [Estado actual] cuenta, además de las celdas, lo que hay en la hoja: tablas, gráficos (tipo, título, series), tablas dinámicas (rango, datos, filas, columnas, valores), formato condicional, validación, tablas de Power Query, filtros, escenarios y los nombres definidos. Así puede cambiar lo que ya existe. También: las fórmulas que se desbordan con su rango y primeros valores («[se desborda en E2:G4: …]»), las consultas de Power Query con su M y dónde están cargadas, los archivos de la carpeta de datos, el código VBA con líneas numeradas (si hay acceso), los puntos ✔/✘ de la última revisión (primero lo que falla) y una línea con lo que tiene este Excel (matrices dinámicas, LAMBDA, Power Query, Solver, acceso a VBA, si el libro guarda macros), para que no proponga lo que no se puede.

## Cambios que propone el tutor (con permiso)

El tutor, además de `<marcas>`, puede terminar su respuesta con un bloque `<acciones>` (JSON) **por hoja**; lo normal es uno. Sus reglas están en `motor.REGLAS`.

```json
<acciones>{"para": "un ejercicio parecido", "hoja": "Práctica 1",
  "cambios": [{"poner": "A1:B2", "valores": [["Producto", "Precio"], ["Lápiz", 2]]}, {"negrita": "A1:B1"}],
  "turno": {"titulo": "Con IVA · C2:C5", "rango": "C2:C5", "solucion": "=B2*(1+$F$1)",
            "errores": [{"formula": "=B2*(1+F1)", "dice": "Al copiar se corre F1: fíjala con $."}]}}</acciones>
```

- `hoja`: si falta, la hoja del módulo (aunque la persona tenga otra al frente; las marcas no: ver «Marcas del tutor»); si no existe, se crea al final, con la propiedad `panel_tutor` para reconocerla aunque se reabra el panel. Nunca la hoja de otro módulo. `cambios`: las mismas acciones de las lecciones (tabla de arriba). `turno`: opcional, con el formato de «Revisión automática».
- **Validación estricta** (`motor.separar_acciones` → `validar_propuesta`, sin tocar Excel; luego `Libro.preparar`, con el libro): acciones y campos conocidos, referencias válidas (hasta la fila 5000 y la columna GR), `valores` del tamaño exacto del rango, máximo **40 cambios y 300 celdas**, nombres de hoja válidos, tablas que existen (o que crea la misma propuesta) y nombres de tabla libres, y las celdas del ejercicio vacías. Se rechazan fórmulas que salen de Excel: `WEBSERVICE`, `HYPERLINK`, `CALL`, `EXEC`, `RTD`, `IMAGE`, DDE (`|`), otros libros o rutas. Si algo no vale, el chat lo dice («El tutor propuso un cambio que no se puede usar…») y el tutor se entera en la próxima pregunta.
- **Varios bloques en una respuesta** (`separar_acciones` → `{"para", "partes": [...]}`): se juntan en **una sola tarjeta**, con una parte por hoja (dos bloques para la misma hoja se unen). Máximo 4 y un solo `turno`. La tarjeta tiene el mismo formato que la de un bloque (la página no cambió): `hoja` dice «Ejemplo + Práctica 2 (nueva)», el resumen va «en «Ejemplo», …; en «Práctica 2», …» y cada cambio del detalle lleva su hoja. Un bloque que no vale (JSON roto, otro módulo, un segundo `turno`) **no se usa, pero no se pierde en silencio**: la tarjeta trae el resto, el chat dice «Parte de lo que propuso el tutor no se puede usar (…)» y el tutor lo recibe en «[Del panel]». Aplicar y Deshacer van con todas las hojas a la vez; si una acción falla en una hoja, también vuelven atrás las que ya se habían hecho.
- **Tarjeta de permiso** (en el chat): «El tutor quiere: crear la hoja «Práctica 1», escribir 12 celdas y dejarte un ejercicio en C2:C5», la hoja (y si es nueva), el «para», **avisos** en amarillo si toca celdas que escribió la persona o la zona del «Tu turno» (o del ejercicio del tutor), una nota si es la hoja del módulo, y «Ver los N cambios». Botones **Aplicar** / **No**. Hasta pulsar Aplicar no se cambia nada.
- **Aplicar** (`Libro.aplicar`): primero guarda lo que había en cada rango que se toca (fórmulas, valores y formato: número, relleno, negrita, cursiva, tamaño, fuente, color de letra, alineación y bordes), los anchos de columna y el estado de las tablas. Si una acción falla a medias, deja todo como estaba y lo dice. Lo que escribe el tutor queda anotado (`del_tutor`) y el tutor lo ve como «[la escribiste tú, el tutor]», no como de la persona.
- **Deshacer** (en la misma tarjeta; Ctrl+Z de Excel no deshace lo hecho por COM):
  - Hoja creada: se borra (sin el aviso de Excel). Si la persona escribió en ella después, la tarjeta pregunta antes: **Borrar igual** / **Cancelar**.
  - Hoja que ya existía: cada celda que sigue como la dejó el tutor vuelve a como estaba (contenido y formato), las tablas nuevas vuelven a ser rango y las de antes recuperan su tamaño, totales y filtros. Las celdas que la persona cambió después **no se tocan** y la tarjeta dice cuáles.
  - **En la hoja del módulo y después de cambiar de paso:** la hoja se rehízo, así que el formato del tutor ya no está; los valores que escribió se conservaron como los de la persona (`Clase.ir` guarda como «suyo» todo lo que no puso la lección) y sus tablas se rehicieron como las de ella. Deshacer quita esos valores (vuelve lo que había o, si era de la lección, la celda queda vacía, para que no aparezca en otro paso) y sus tablas vuelven a ser rango. Lo comprueba `--probar`.
  - **Código VBA:** el módulo vuelve a como estaba (o se quita, si lo creó el tutor); si la persona lo cambió después, pregunta «¿Deshacer igual?».
  - **Power Query:** se quitan las consultas que creó (con su tabla y su conexión) y las que cambió vuelven a su M y se actualizan.
- **Ejercicio del tutor**: si la propuesta trae `turno`, al aplicarla aparece en la pestaña Lección la tarjeta «Ejercicio del tutor», con su **Comprobar** (revisa en la hoja del ejercicio con `Hoja.revisar`: marcos de formato condicional, nunca formas), el aviso «Cambiaste algo desde que comprobaste» y «Pregúntale al tutor». Hay uno a la vez (uno nuevo reemplaza al anterior). Si la solución da error en Excel, no se crea y se avisa. Si está en la hoja del módulo, al cambiar de paso vuelve a «sin comprobar» (la hoja se rehízo).
- El tutor recibe en cada pregunta qué hoja tiene la persona al frente (y adónde irían sus marcas), dónde están sus marcas, las hojas del libro, su ejercicio con la revisión del momento y el contenido de la hoja aparte que tenga al frente, y un «[Del panel]» con lo que hizo la persona con su última propuesta (aplicó, no aplicó, deshizo, o por qué no se pudo usar).
- Las hojas que crea el tutor **no** las toca `_construir`; se guardan con el libro del curso.

### Revisión automática (`"turno"` en el paso)

```json
"turno": {
  "rango": "E4:E7",
  "solucion": "=B4*(1-$E$1)*(1+$B$1)",
  "al_empezar": "…", "al_terminar": "…",
  "errores": [
    {"formula": "=B4*(1-$E$1)", "dice": "El descuento está bien, pero falta el IVA…"},
    {"formula_sin": "[@", "consejo": true, "dice": "En una tabla se lee mejor [@Total]…"}
  ]
}
```

- `solucion` se escribe **para la primera celda** del rango, con referencias normales (no `[@…]`). El motor la "copia" a cada celda, moviendo lo que no lleva `$`, y calcula lo que debería dar.
- **Solo revisa al pulsar Comprobar.** Antes, el recuadro dice «sin comprobar» y el texto de `al_empezar`. Al pulsarlo, cada celda escrita lleva un **marco verde o rojo** en la hoja y el panel dice `bien`, `casi`, `vas bien` (bien pero sin terminar) o `revisa`.
- Si después cambias algo en la zona, el resultado se atenúa con «Cambiaste algo desde que comprobaste: vuelve a pulsar Comprobar». Los marcos se quitan al cambiar de paso.
- Si pulsas Comprobar mientras escribes en una celda (antes de Enter), avisa que termines de escribir.
- El tutor sí recibe la revisión del momento (sin dibujar nada) cuando le preguntas.
- **Cómo reconoce los errores típicos:** cada uno es una fórmula equivocada. Si lo que escribiste da lo mismo que ella en todas las celdas, se muestra su `dice`.
  - `formula_sin` revisa que la fórmula contenga un texto.
  - Con `"consejo": true` solo se avisa cuando el resultado ya da bien.
- **Además detecta solo:** un número escrito a mano en vez de fórmula, y filas con fórmulas distintas (no la copió).
- Si no reconoce el error, ofrece "Pregúntale al tutor".

**Fórmulas que se desbordan** (FILTRAR, ORDENAR, UNICOS…): `{"rango": "G2", "solucion": "=FILTER(A2:C9,C2:C9>20)"}`. Se reconoce sola (o con `"desborda": true`): la fórmula va solo en la primera celda y se compara todo lo desbordado (puntos `ok/total` por celda). Detecta sola `#¡DESBORDAMIENTO!` (algo estorba o la copió hacia abajo), el resultado escrito a mano, la `@` y el tamaño distinto; un error típico `{"desbordamiento": true, "dice": "…"}` cambia el mensaje del desbordamiento.

**Ejercicios de objetos** (`"pide"`, también en los del tutor; pueden ir junto a una fórmula):
```json
"turno": {"titulo": "Gráfico de ventas", "pide": [
    {"grafico": {"tipo": "columnas", "datos": "A1:B7", "titulo": "Ventas por mes", "leyenda": false}},
    {"formato_condicional": {"rango": "B2:B7", "tipo": "escala"}}],
  "errores": [{"si": {"grafico": {"tipo": "circular"}}, "dice": "Un circular no compara meses: usa columnas."}]}
```
| Qué | Campos |
|---|---|
| `grafico` | `tipo` (columnas, barras, lineas, circular, anillo, dispersion, area, radial, burbujas, o una lista), `datos`, `series`, `titulo` (texto o `true`), `eje_x`, `eje_y`, `leyenda`, `existente` |
| `tabla` | `rango` (sin la fila de totales), `nombre`, `columnas`, `totales` (`true` o `{"Total": "suma"}`), `estilo` |
| `dinamica` | `origen` (rango o tabla), `filas`, `columnas`, `filtros`, `valores` (`"Ventas"` o `{"campo": "Ventas", "funcion": "suma"}`), `en`, `nombre` |
| `formato_condicional` | `rango`, `tipo` (valor, formula, escala, barras, iconos, superiores, duplicados, texto, promedio), `operador` (mayor, menor, igual, entre, `>`…), `valor`, `valor2`, `formula` (en inglés), `texto` |
| `validacion` | `rango`, `tipo` (lista, entero, decimal, fecha, hora, longitud, personalizada), `lista` (`["Sí", "No"]` o `"=$F$1:$F$3"`), `operador`, `min`, `max`, `formula` |
| `nombre` | `nombre`, `refiere`, `valor` |
| `orden` | `rango` (con encabezados), `por` (letra), `orden` (asc/desc): mira el orden y que las filas sigan enteras |
| `filtro` | `tabla` o `rango`, `columna` (encabezado o letra), `igual_a` (valor o lista), `mayor_que`, `menor_que`: mira qué filas se ven |
| `inmovilizar` | `celda` |
| `formato_numero` | `rango`, `es` (porcentaje, moneda, fecha, hora, texto, general, entero, decimal, miles), `codigo`, `decimales` |

Cada cosa da sus puntos ✔/✘ («El gráfico es circular: aquí va uno de columnas.»), que salen en la tarjeta como en Dia. Si no hay nada hecho: «vacío». Un error típico `{"si": {...}, "dice": "…"}` pone su mensaje si lo de la persona cumple el `si`. Lo que ya estaba al empezar (el gráfico del ejemplo, lo que armó el tutor) no cuenta, salvo con `"existente": true`. Las marcas son formato condicional sobre el rango de cada cosa, nunca formas.

**Ejercicios de VBA** (`"macro"`):
```json
"turno": {"titulo": "Macro NegritaTotales", "macro": "NegritaTotales", "rango": "A1:B9",
  "solucion_vba": "Sub NegritaTotales()\n  ...\nEnd Sub", "entradas": ["respuesta para InputBox"], "limite": 4,
  "errores": [{"vba": "Sub NegritaTotales()\n  Range(\"A2:B9\").Font.Bold = True\nEnd Sub", "dice": "Pusiste en negrita toda la tabla."}]}
```
Solo al pulsar Comprobar (nunca el tutor): revisa el código de la persona (análisis estático), copia la hoja a un libro temporal, ejecuta su macro allí con el vigía (ver «VBA») y hace lo mismo con `solucion_vba` en otra copia; compara valores, negrita, cursiva, relleno, color de letra, formato de número, alineación y cuántos gráficos, tablas y reglas hay. Cada diferencia es un ✘ («B4 debería quedar en negrita.») y se marca en su hoja. También puede llevar `pide`. Sin el acceso al proyecto de VBA, dice cómo activarlo.

## Power Query (con límite)

- Solo con las acciones `consulta` y `actualizar` (el modo libre no llega a `Queries` ni a conexiones). `cargar_en` crea una tabla con la consulta en esa celda (sobrescribe, no mueve celdas) y nombra la conexión «Consulta - X».
- **Orígenes:** solo `Excel.CurrentWorkbook()` (tablas y rangos con nombre del libro) y `File.Contents("{datos}/archivo.csv")` con la ruta escrita tal cual, dentro de la carpeta `datos` de `curso.json` (`{datos}` se cambia por la carpeta: así la lección sirve en otra PC). `avanzado.validar_m` revisa el M sin ejecutarlo: cada nombre con punto tiene que ser de una lista blanca (Table, List, Text, Number, Date, Csv, Json, Xml, Excel.CurrentWorkbook, Excel.Workbook, File.Contents, parte de Value…), también los `#"..."`; se rechazan `#shared`, `#sections`, `section`, `Expression.Evaluate`, `Value.NativeQuery`, Web, Sql, Odbc, OleDb, Folder, SharePoint…, rutas fuera de la carpeta, rutas armadas juntando textos y archivos que no existen.
- **Deshacer:** en una hoja nueva, se borra la hoja y la consulta con su conexión; en una hoja que ya existía, se pone su copia (ver «Modo libre») y se quitan la consulta y la conexión. Exacto (lo comprueba `--probar`). En una hoja que ya tiene datos de Power Query no se puede hacer nada que copie la hoja (modo libre, consultas, análisis): Excel duplicaría sus consultas. Cambiar el M de una consulta que ya existía se deshace devolviéndole su M y actualizándola (la tarjeta avisa que no es exacto) y `actualizar` no se deshace (la nota lo dice).
- En las lecciones, las consultas de los pasos se quitan y se vuelven a crear al cambiar de paso (cargar tarda 1–4 s). Las del tutor van en una hoja aparte.

## Herramientas de análisis

Buscar objetivo, tablas de datos y escenarios se aplican con la copia de la hoja (Deshacer exacto, también los escenarios). Solver: acción cerrada que solo llama a `Solver.xlam!SolverReset/SolverOk/SolverAdd/SolverSolve/SolverFinish` (sin `Application.Run` libre: el nombre de la macro es fijo y las celdas se revisan), con la hoja activa, y solo si el complemento está activado (`avanzado.solver_disponible`). El panel no lo activa: si un módulo usa Solver y no está, Lección dice cómo (Archivo → Opciones → Complementos → Ir… → Solver). La parte de Solver solo se prueba si el complemento está activado (el resumen de `--probar` lo dice).

## VBA

- **Requisito:** «Confiar en el acceso al modelo de objetos de proyectos de VBA» (Archivo → Opciones → Centro de confianza → Configuración del Centro de confianza → Configuración de macros). El panel lo detecta (`vba.acceso`) y, si falta, lo explica en Lección (módulos con VBA), en el chat y en la tarjeta. Nunca lo cambia.
- **Leer:** el [Estado actual] trae los módulos con sus líneas numeradas (si el curso tiene macros o el libro ya tiene código).
- **Marcar:** `{"tipo": "linea", "modulo": "Module1", "linea": 5, "texto": "falta End If"}` inserta encima de esa sentencia una línea `' <- tutor: falta End If` (con su sangría). Se quitan con Borrar marcas, al llegar marcas nuevas, antes de Comprobar y al abrir y cerrar el panel. No cambian su código: son líneas aparte. La marca es **solo ASCII** porque el editor de VBA guarda en ANSI (la página de códigos de Windows): una «←» quedaba como «?» y la marca ya no se reconocía. `vba.es_marca` reconoce también las de versiones anteriores (`' ← tutor:` y `' ? tutor:`) y las quita igual. Lo que va al editor (el texto de las marcas, el código que propone el tutor y el de Comprobar) pasa por `vba.ansi`, que cambia lo que no cabe en ANSI por algo parecido («→» por «->», «✔» por «OK»).
- **Proponer:** `{"vba": "Macros", "codigo": "...", "modo": "reemplazar" | "agregar"}`, solo en módulos normales y en libros que guardan macros (.xlsm o sin guardar). La tarjeta muestra el código entero. Deshacer deja el módulo como estaba (o lo quita); si la persona lo cambió después, pregunta antes. El panel nunca ejecuta lo que propone el tutor.
- **Análisis estático** (`vba.problemas`), antes de insertar y antes de ejecutar: palabras vetadas (Shell, Kill, RmDir, MkDir, FileCopy, Environ, SendKeys, Declare, PtrSafe, CallByName, GetObject, Workbooks, Run, Evaluate, ExecuteExcel4Macro, OnTime, Wait, SaveAs, Export, AddIns, SaveSetting/GetSetting, VBProject, Stop, Quit…), sentencias de archivos (`Open … For`, `Print #`, `Name … As`), `.Close`/`.Save`, `.Show`, `Dir(`, `[…]`, CreateObject salvo `"Scripting.Dictionary"` y `"VBScript.RegExp"`, y en lo del tutor, eventos y `Auto_Open`. Las líneas partidas con « _» se juntan antes; los comentarios y textos no cuentan.
- **Comprobar** de una macro (ver «Revisión automática»): `vba.instrumentar` pone `Call tutorVigia` antes de cada `Next`, `Loop`, `Wend`, `GoTo` y `Resume` (también tras `Then`/`Else` y en `Do: Loop` de una línea; si pasa el límite, `End` corta todo), cambia MsgBox e InputBox por funciones que no esperan, y la macro corre en un libro temporal (copia de la hoja) con los eventos apagados. Los libros temporales se cierran sin guardar.
  - Va con **`Call`**: `tutorVigia: Loop` al empezar una sentencia es una **etiqueta** (el editor la manda a la columna 1) y el vigía nunca se llamaba.
  - El vigía vive en el módulo `zzTutorPanel`: si el módulo se llamara como su procedimiento (`tutorVigia`), `Call tutorVigia` sería un error de compilación («se esperaba un procedimiento, no un módulo»).
  - Un hilo vigila mientras corre (`_vigilar_dialogos`, con el `pid` de Excel y Excel pasado de hilo con `CoMarshalInterThreadInterfaceInStream`): si salta un aviso de Visual Basic, pulsa «Finalizar/Aceptar» y guarda su texto; si VBA queda en **modo interrupción** (error de compilación, `Debug.Assert`), pulsa «Restablecer» y esconde el editor si estaba cerrado. Así un error de compilación sale como «Visual Basic no pudo ejecutarla: Error de compilación: …» y Excel no se queda esperando.

## Cómo hacer un módulo nuevo

1. Copia `ejemplo_leccion.json` a la carpeta del curso, cambia los pasos y añádelo a `modulos` en `curso.json`.
2. Pruébalo sin ventana: `python panel-excel/panel_web.py <curso.json> --probar`. Imprime el texto de cada paso con los valores reales y **prueba la revisión automática**: escribe la solución y cada error típico en la zona del «Tu turno» (y la deja como estaba) y marca ✔ o ✘. También comprueba que antes de pulsar Comprobar no se ve ningún error y que ninguna marca deja formas encima de las celdas. Además prueba, sin IA, los **cambios del tutor** en el primer módulo (`probar_propuestas`): aplicar y deshacer en la hoja del módulo (con tabla y columna calculada) y en una hoja nueva, que todo quede **exactamente** igual (celda por celda, anchos, tablas y hojas), los avisos, «No», deshacer después de cambiar de paso, propuestas inválidas y un ejercicio del tutor con Comprobar (bien y mal). Termina en «Cambios del tutor: todo bien». Luego `probar_hojas_y_bloques` (con un tutor falso, sin IA) prueba las **marcas por hoja** (con `"hoja"`, con la práctica al frente, con una hoja de la persona al frente, varias hojas a la vez, «Borrar marcas» en todas, cambio de paso, hojas rechazadas y el aviso al tutor) y **varios bloques** `<acciones>` (una tarjeta, aplicar y deshacer enteros, bloques que no valen, misma hoja, dos `turno`, y vuelta atrás si falla una hoja); termina en «Marcas y bloques: todo bien». Por último, `probar_modo_libre` (sin IA) prueba el **modo libre** en una práctica con datos, y una hoja «Resumen» que la usa con fórmula, gráfico y dinámica, más un nombre definido:
   - un gráfico de columnas con títulos, una tabla dinámica, formato condicional (escala de colores y una fórmula en inglés que debe quedar en español), validación (lista y decimal), nombres, `ordenar` e `inmovilizar`, en una sola propuesta;
   - que aplicar dé los valores esperados, que el [Estado actual] los cuente y que **deshacer deje el libro exactamente igual** (`foto_libro` compara todas las hojas, gráficos, dinámicas, formato condicional, validación, inmovilizar y nombres), y que lo de «Resumen» siga apuntando a la hoja;
   - el «¿Deshacer igual?» y un fallo en el paso 5 que vuelve todo atrás y avisa al tutor;
   - 18 intentos peligrosos rechazados (abrir libros, SaveAs, Run, VBProject, Application.Quit, hipervínculos, WEBSERVICE, QueryTables, dinámica externa, otro libro, Export, AddPicture, otra hoja, renombrar o borrar la hoja, Copy, llegar al libro, rutas);
   - y en la hoja del módulo: sin dinámicas, y que deshacer la deje igual, también después de cambiar de paso.

   Termina en «Modo libre: todo bien».

   Con la lección suelta (o con `--completo` en un curso), además, sin IA y cada una con su «todo bien»: **matrices dinámicas** (`probar_matrices`: se desborda lo que escribe el motor; Comprobar bien, error típico, #¡DESBORDAMIENTO!, copiada, a mano y con @; [Estado actual]; una fórmula suya que sobrevive al cambio de paso; Evaluate en inglés), **pasos con modo libre y limpieza** (`probar_pasos`: una lección temporal con gráfico, dinámica, escala de colores y nombre; nada amontonado al ir y volver; su gráfico, tabla, formato condicional y validación se conservan; una lección peligrosa no se abre), **Comprobar de objetos** (`probar_objetos`: diez cosas a la vez; vacío, 28/28 y tres errores con el típico), **Power Query** (`probar_power_query`: tabla del libro y archivo de datos, Deshacer exacto en hoja nueva y existente, cambiar una consulta, 10 consultas peligrosas y otros rechazos), **análisis** (`probar_analisis`), **VBA** (`probar_vba`: 24 macros peligrosas rechazadas y lo normal pasa; el vigía con `Call` y el módulo `zzTutorPanel`; marcas ASCII y las de antes; sin acceso, los mensajes; con acceso, insertar, marcar la línea y comprobar cómo queda en el editor, borrar marcas (el módulo queda idéntico), deshacer y Comprobar bien, error típico, cinco bucles sin fin sin contador (`Do: Loop`, `While True: Wend`, un `For` que se reinicia, `GoTo` hacia atrás…) cortados en ~5 s con Excel respondiendo, un error de compilación sin quedar en interrupción, un error al ejecutar y una macro peligrosa) y **progreso** (`probar_progreso`). Si una prueba se corta, sale su error y cuenta como fallo.

   **Al final, un resumen por bloque** (`correr_pruebas`): una línea por bloque con ✔/✘, si es **básico** (lección y revisión, cambios del tutor, marcas, modo libre, pasos, objetos, progreso) u **opcional** (depende de lo que tenga el Excel: matrices dinámicas, Power Query, análisis y Solver, VBA), sus segundos y lo que no se pudo probar (Solver no activado, sin acceso a VBA). Luego «Revisión automática: todo bien» o, si fallan solo opcionales, «Lo básico del panel: todo bien. Falló solo lo opcional: …» (el panel sirve; esos bloques quedan pendientes), y el tiempo total.

   **Pruebas más cortas:**
   - `--probar --rapido`: la lección (pasos y revisión automática) y lo mínimo de cada bloque opcional en hojas nuevas (`rapida_matrices`, `rapida_power_query`, `rapida_analisis`, `rapida_vba`: proponer código, marcar y borrar, deshacer, Comprobar bien y un `Do: Loop` cortado). **Unos 25 s** con la lección suelta (40 s con el curso avanzado). Es la que usa el instalador y la de después de un `git pull`.
   - `--probar --solo vba,pq`: solo esos bloques (nombres: `leccion`, `propuestas`, `marcas`, `libre`, `pasos`, `objetos`, `progreso`, `matrices`, `pq`, `analisis`, `vba`); con `--rapido`, sus versiones rápidas.
   - La completa (sin `--rapido`) tarda **unos 7 minutos** (unos 411 s) y usa el Excel abierto, visible: va **antes de publicar cambios del panel**.

   **En un curso, `--probar` prueba solo sus módulos**: las pruebas del motor de arriba (propuestas, marcas, modo libre y lo avanzado) suponen el primer módulo como el de `ejemplo_leccion.json` y en otro curso fallaban por eso; van con la lección suelta o con `--completo`. Además mira que el libro sea .xlsm si el curso pide macros, muestra lo que le falta a Excel por módulo y, en los ejercicios de objetos o de VBA, que Comprobar sin hacer nada diga «vacío» (lo del ejemplo no cuenta). `--probar` no cambia dónde se quedó la persona.

   **Al terminar cierra el libro que abrió** (`Libro.cerrar_si_lo_abri`): con una lección suelta, sin guardar («Libro de prueba cerrado sin guardar.»); con un curso, lo guarda (como al usar el panel) y lo cierra, para que no quede abierto con su `~$` («Libro del curso (…) guardado y cerrado»). Si el libro del curso ya estaba abierto antes de la prueba, lo deja abierto y lo dice. Nunca toca otros libros. `--probar-tutor` además le hace una pregunta al tutor (gasta del plan; es opcional; con `--solo leccion` no corre el resto).
3. Prueba la revisión escribiendo respuestas buenas y malas en la zona del "Tu turno" y pulsando **Comprobar** con el panel abierto.

## Notas de este Excel

- Por COM fallan `ListColumns.Add` y `ListRows.Add`: el motor agranda la tabla (`Resize`), que hace lo mismo.
- `FormatConditions.Add` falla con argumentos con nombre: hay que pasarlos en orden (`Add(2, None, "=1=1")`).
- Nada de formas encima de las celdas donde escribe la persona: se llevan el clic. Para marcar celdas, formato condicional.
- `NumberFormat` funciona como si fuera local (`"0.0%"` → `"#.#00%"`, `"General"` da error): se usa `NumberFormatLocal` con lo que dice `Application.International` (separadores, letras de fecha y el nombre de «Estándar»).
- Cada llamada COM tarda unos 2 ms: leer el formato celda por celda es lento. Para deshacer se lee cada propiedad del rango entero y solo se baja a filas o celdas si es distinta por dentro.
- Para borrar una hoja sin el aviso «¿Seguro?», `DisplayAlerts = False` un momento.
- **Argumentos con nombre por COM (pywin32):** se pierden en silencio. `Worksheet.Copy(After=x)` crea un libro nuevo y `Worksheets.Add(After=x)` pone la hoja en otro sitio. Hay que pasarlos en orden (`Copy(None, x)`, `Add(None, x)`). Para un argumento omitido en medio vale `pythoncom.Empty`: `None` falla en `Sort` y `AutoFilter`, y `pythoncom.Missing` en `FormatConditions.Add`.
- **El libro solo se abre minimizado:** si es el único libro abierto, su ventana queda minimizada dentro de Excel, y así `Validation.Add` falla con un error genérico. El motor la maximiza al abrir el libro del curso.
- Fórmulas en español por COM: en `FormatConditions.Add`, `Validation.Add` (también los números: `0,5`), `Names.Add`, `Name.RefersTo` y las uniones de rangos (`A1:A5;C1:C5`). En inglés: `Range.Formula` y `Series.Formula`. El modo libre lo traduce (ver «Modo libre»).
- Si la celda activa está dentro de una tabla dinámica, un gráfico nuevo nace como gráfico dinámico. El modo libre mueve la selección fuera antes de crear un gráfico.
- `SourceData` de una dinámica y `RefersTo` de algunos nombres vuelven en R1C1 en español (`Hoja!F1C1:F7C3`): `motor._a1` los pasa a `A1:C7`.
- Si un `Select` se hace en una hoja que no está activa, falla. Las formas, el formato condicional, `ShowPrecedents` y los gráficos sí funcionan en una hoja que no se ve.
- `ConvertFormula` devuelve las fórmulas R1C1 en español (`F[3]C[-4]`) y no sirve para copiar fórmulas: el motor las mueve él mismo (`copiar_formula`).
- **`Formula` añade `@`:** en este Excel 365, `Range.Formula = "=UNIQUE(...)"` queda `=@UNIQUE(...)` (un solo valor), y `Range.Value = "=SORT(...)"` también. Con `Formula2` se desborda. `Formula2` acepta una matriz de fórmulas y valores. Las celdas desbordadas tienen `Formula2` vacía; `HasSpill` y `SpillingToRange` dicen dónde se desborda. `#¡DESBORDAMIENTO!` llega como -2146826243.
- **`Evaluate` va en el idioma de Excel:** por pywin32, `ws.Evaluate("=SUM(A1:A5)")` da `#¿NOMBRE?` (entiende `SUMA`). Llamándolo por IDispatch con el LCID 0x0409 entiende inglés y devuelve las matrices dinámicas enteras (`motor.evaluar_en`). BUSCARX devuelve un rango (se lee su valor).
- LAMBDA no existe en esta versión (16.0, build 14430); LET, FILTRAR, ORDENAR, UNICOS, SECUENCIA y BUSCARX sí.
- `Cells.Clear` borra tablas dinámicas, formato condicional, validación, minigráficos y comentarios, pero no gráficos ni formas.
- **Power Query por COM:** `Workbook.Queries.Add(nombre, m)` y `ListObjects.Add(0, "OLEDB;Provider=Microsoft.Mashup.OleDb.1;Data Source=$Workbook$;Location=X;…", Empty, 1, celda)` con `CommandType = 2` y `CommandText = ["SELECT * FROM [X]"]`; la conexión sale como «Conexión» (el motor la renombra). Cargar tarda 1–4 s. **Copiar una hoja con una tabla de Power Query duplica la consulta** («X (2)»). Borrar la consulta deja la tabla como datos sueltos.
- Las tablas de datos se leen en español (`=TABLA(,B2)`) y no se puede escribir en una parte: por eso se deshacen con la copia de la hoja.
- `ws.Scenarios` es un método (`ws.Scenarios()`); `Scenario.Values` es una tupla.
- En una tabla con fila de totales, `ListObject.Range` incluye esa fila.
- Al leer un filtro de varios valores, `Criteria1` no es fiable: para revisar filtros se mira qué filas están ocultas.
- Copiar una hoja sin argumentos (`ws.Copy()`) la lleva a un libro nuevo (así corre el Comprobar de VBA). Sin «Confiar en el acceso al modelo de objetos de proyectos de VBA», `wb.VBProject` da error («no es de confianza»).
- Una vez, `Validation.Add` del modo libre falló con un error genérico en mitad de `--probar` y no se repitió; por si es la ventana minimizada, `Libro.aplicar` la maximiza antes.

## Dependencias

Excel, Python con `pywin32` y `pywebview` (usa WebView2, que ya viene en Windows 11), y Claude Code instalado y con sesión iniciada (el comando `claude`). El tutor gasta del plan como un mensaje normal (más si lleva imágenes o PDF); la revisión automática no gasta nada.
