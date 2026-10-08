# Panel de curso en vivo para Excel

Un panel que flota encima de Excel para dar un curso paso a paso:
- **← Anterior / Siguiente →** mueve Excel en vivo.
- Un selector cambia de **módulo**. Cada módulo vive en su propia hoja de un libro del curso, que se guarda en disco.
- La zona **"Tu turno"** se revisa con el botón **Comprobar**: sin IA, al instante y sin gastar. Mientras trabajas no te marca nada.
- Un **tutor** que conoce el curso entero lee tu hoja, contesta y la marca con flechas y notas (en la hoja que tienes al frente o en la que él elija; ver «Marcas del tutor»). Acepta **capturas, PDF y archivos de texto**.
- El tutor también puede **cambiar el libro** (armar un ejercicio parecido en una hoja nueva, completar un ejemplo, dar formato, crear una tabla y, con el **modo libre**, casi cualquier cosa de Excel: gráficos, tablas dinámicas, formato condicional, validación, nombres, segmentaciones…), pero **siempre pide permiso**: muestra una tarjeta con **Aplicar / No** y, después, **Deshacer**. Los ejercicios que arma se revisan con su propio **Comprobar**, sin IA.
- Todo va en **una ventana** pegada a la derecha, a todo el alto de la pantalla, con dos pestañas: **Lección | Tutor**.

```
python panel-excel/panel_web.py <carpeta-del-curso>/curso.json      # un curso con módulos
python panel-excel/panel_web.py panel-excel/ejemplo_leccion.json     # una lección suelta (ejemplo)
```

Los cursos van en su propia carpeta (por ejemplo `curso-excel/`, con su README); aquí solo vive el motor.

## Historia y decisiones

- **2026-10-08 (noche):** para cursos avanzados, el usuario quiere que el tutor pueda hacer «lo que sea» en Excel. Eligió el **modo mixto**:
  - Las acciones de siempre, validadas, para lo común. Se sumaron `ordenar` e `inmovilizar`.
  - Un **modo libre** para lo demás: el modelo de objetos de Excel en JSON (ver «Modo libre»), con lista blanca de lo que se puede usar y revisión de cada objeto que aparece.
  - Se descartó dejarle escribir código Python o VBA: no se puede revisar de forma segura y no se puede deshacer.
  - Para deshacer lo que haga el modo libre sin saber qué hizo, antes de aplicar se guarda una **copia muy oculta de la hoja**. Deshacer la pone en su lugar y redirige lo que la usaba desde otras hojas (fórmulas, tablas, gráficos, dinámicas, nombres). Comprobado celda por celda, con formato condicional, validación, tablas, gráficos, dinámicas, inmovilizar y nombres: 0 diferencias.
  - Se descartaron dos vías: guardar el libro con SaveCopyAs y traer la hoja de vuelta (lo que viene de otro libro queda como vínculo externo, y las dinámicas pierden su origen), y restaurar las celdas copiándolas encima (los gráficos seguirían apuntando a la copia).
  - Al probarlo salieron varias trampas de este Excel por COM; están en «Notas de este Excel».
- **2026-10-08 (tarde):** al probar la «Práctica 1» salieron tres fallos, y el propio tutor los resumió: (1) sus marcas pensadas para la práctica se dibujaban siempre en la hoja del módulo, así que acabó escribiendo los avisos en celdas; (2) mandó dos bloques `<acciones>` (uno por hoja) y solo se usó el primero, el de la hoja equivocada, sin decir nada del otro; (3) afirmó que las marcas «se quitan solas» sin saberlo. Arreglos:
  - Cada marca admite `"hoja"`; sin ella va a la hoja que tienes al frente si es la del módulo o una del tutor, y si no, a la del módulo. Nunca la de otro módulo ni de otro libro. Se dibuja sin cambiarte de hoja (formas, formato condicional y precedentes funcionan en una hoja que no se ve: comprobado) y el chat dice en qué hoja quedaron. «Borrar marcas» limpia todas las hojas.
  - Varios bloques `<acciones>` se juntan en **una** tarjeta, con una parte por hoja, que se aplica y se deshace entera. Se eligió así (y no un formato nuevo con varias hojas en un bloque) porque es lo que el tutor hace solo y la página no cambia. Lo que no se puede usar no se pierde en silencio: el chat lo dice y el tutor se entera en la próxima pregunta.
  - `REGLAS` dice en qué hoja caen las marcas y cuándo se borran (lo que hace el código de verdad), que use un bloque por hoja y que no afirme cosas del panel que no sepa. El [Estado actual] le dice qué hoja tienes al frente, adónde irían sus marcas, dónde están las de ahora y el contenido de esa hoja si no es la del módulo.

- **2026-10-08:** la persona le pidió al tutor hacer algo con una celda y no pudo: solo sabía marcar. Ahora **puede modificar el libro**. Lo que se decidió (lo eligió el usuario):
  - **Escribir en cualquier parte**: en la hoja del módulo o en **hojas nuevas que crea** (p. ej. «Práctica 1»). Nunca en la hoja de otro módulo.
  - **Pedir permiso siempre**: nada se aplica sin pulsar **Aplicar**; la tarjeta avisa si toca celdas que escribió la persona o la zona del «Tu turno».
  - **Deshacer** en la misma tarjeta, porque Ctrl+Z de Excel no deshace lo hecho por COM: antes de aplicar se guarda lo que había (fórmulas y formato básico); una hoja creada se borra.
  - **Ejercicios con Comprobar**: el tutor puede dejar un «turno» con el mismo formato que las lecciones y se revisa sin IA, con la misma `revisar`.
  - Se descartó guardar la copia de seguridad en una hoja oculta (con tablas no queda exacto) y con `Value(11)` en XML (cambia los formatos y desplaza las celdas). Se guarda propiedad por propiedad, leyendo de una vez cada rango que es igual por dentro (cada llamada COM tarda ~2 ms).
  - En este Excel en español, `NumberFormat` no entiende los códigos en inglés (`"0.0%"` quedaba `"#.#00%"` y `"General"` daba error). Los formatos se traducen con `Application.International` y se ponen con `NumberFormatLocal` (`motor.formato_local`), también los de las lecciones.

- **2026-10-08:** la revisión del «Tu turno» salía sola en cuanto escribías y te marcaba el error sin dejarte trabajar. Ahora **solo revisa al pulsar Comprobar**, dentro del ejercicio (no con el tutor). Se eligió así antes que esperar unos segundos sin cambios, porque así decides tú cuándo terminaste.
- **2026-10-08:** tras pulsar Comprobar ya no dejaba escribir en la celda (alerta «Esta fórmula no tiene una referencia de rango o un nombre definido»). El marco era una **forma** encima de la celda: el clic la seleccionaba y lo escrito iba a la forma. Ahora los marcos de Comprobar y el «resaltar» y el «marco» del tutor son **formato condicional** (relleno suave y borde de color), que se ve igual y no se puede seleccionar. Las reglas propias se reconocen por su fórmula (`=1=1` las de Comprobar, `=2=2` las del tutor) y se borran sin tocar otras. Las notas y flechas del tutor siguen siendo formas, pero van fuera de la zona de trabajo.
- **2026-10-08:** en la pestaña Lección el contenido no cabía y no dejaba bajar: los bloques se encogían en vez de desbordar. Ahora no se encogen, el cuerpo se desplaza y el diagrama (en Dia) se ve entero, sin una segunda barra dentro.

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
  "modulos": ["m1_referencias.json", "m2_tablas.json"] }   // archivos junto a curso.json
```

El libro se crea junto a `curso.json`. Si en vez de un curso se le pasa una lección suelta, la abre **siempre en un libro nuevo sin guardar** (nunca reutiliza un libro abierto: podría ser de la persona y se vaciaría).

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

`titulo` (del paso y del «Tu turno») y `donde` son opcionales: si faltan, el panel no los muestra. En `donde`, lo que va entre `**` sale como una tecla o un botón.

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

Las fórmulas van en inglés y con coma (`=SUM(A1,B1)`), que es como las entiende Excel por dentro; luego las muestra traducidas. Los formatos de número también en inglés (`"0.0%"`, `"dd/mm/yyyy"`): el motor los traduce al idioma de Excel.

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

**Lo que ve el tutor.** El [Estado actual] cuenta, además de las celdas, lo que hay en la hoja: tablas, gráficos (tipo, título, series), tablas dinámicas (rango, datos, filas, columnas, valores), formato condicional, validación y los nombres definidos. Así puede cambiar lo que ya existe.

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
  - **En la hoja del módulo y después de cambiar de paso:** la hoja se rehízo, así que el formato y las tablas del tutor ya no están; los valores que escribió se conservaron como los de la persona (`Clase.ir` guarda como «suyo» todo lo que no puso la lección). Deshacer quita esos valores: vuelve lo que había o, si era de la lección, la celda queda vacía (para que no aparezca en otro paso). Lo comprueba `--probar`.
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

## Cómo hacer un módulo nuevo

1. Copia `ejemplo_leccion.json` a la carpeta del curso, cambia los pasos y añádelo a `modulos` en `curso.json`.
2. Pruébalo sin ventana: `python panel-excel/panel_web.py <curso.json> --probar`. Imprime el texto de cada paso con los valores reales y **prueba la revisión automática**: escribe la solución y cada error típico en la zona del «Tu turno» (y la deja como estaba) y marca ✔ o ✘. También comprueba que antes de pulsar Comprobar no se ve ningún error y que ninguna marca deja formas encima de las celdas. Además prueba, sin IA, los **cambios del tutor** en el primer módulo (`probar_propuestas`): aplicar y deshacer en la hoja del módulo (con tabla y columna calculada) y en una hoja nueva, que todo quede **exactamente** igual (celda por celda, anchos, tablas y hojas), los avisos, «No», deshacer después de cambiar de paso, propuestas inválidas y un ejercicio del tutor con Comprobar (bien y mal). Termina en «Cambios del tutor: todo bien». Luego `probar_hojas_y_bloques` (con un tutor falso, sin IA) prueba las **marcas por hoja** (con `"hoja"`, con la práctica al frente, con una hoja de la persona al frente, varias hojas a la vez, «Borrar marcas» en todas, cambio de paso, hojas rechazadas y el aviso al tutor) y **varios bloques** `<acciones>` (una tarjeta, aplicar y deshacer enteros, bloques que no valen, misma hoja, dos `turno`, y vuelta atrás si falla una hoja); termina en «Marcas y bloques: todo bien». Por último, `probar_modo_libre` (sin IA) prueba el **modo libre** en una práctica con datos, y una hoja «Resumen» que la usa con fórmula, gráfico y dinámica, más un nombre definido:
   - un gráfico de columnas con títulos, una tabla dinámica, formato condicional (escala de colores y una fórmula en inglés que debe quedar en español), validación (lista y decimal), nombres, `ordenar` e `inmovilizar`, en una sola propuesta;
   - que aplicar dé los valores esperados, que el [Estado actual] los cuente y que **deshacer deje el libro exactamente igual** (`foto_libro` compara todas las hojas, gráficos, dinámicas, formato condicional, validación, inmovilizar y nombres), y que lo de «Resumen» siga apuntando a la hoja;
   - el «¿Deshacer igual?» y un fallo en el paso 5 que vuelve todo atrás y avisa al tutor;
   - 18 intentos peligrosos rechazados (abrir libros, SaveAs, Run, VBProject, Application.Quit, hipervínculos, WEBSERVICE, QueryTables, dinámica externa, otro libro, Export, AddPicture, otra hoja, renombrar o borrar la hoja, Copy, llegar al libro, rutas);
   - y en la hoja del módulo: sin dinámicas, y que deshacer la deje igual, también después de cambiar de paso.

   Termina en «Modo libre: todo bien». Con una lección suelta, al final cierra sin guardar el libro que abrió. `--probar-tutor` además le hace una pregunta al tutor (gasta del plan; es opcional).
3. Prueba la revisión escribiendo respuestas buenas y malas en la zona del "Tu turno" y pulsando **Comprobar** con el panel abierto.

## Pasarlo a otra PC

Estos cinco archivos van en el repositorio del tutor (`../paquete-tutor/`). Después de cambiar cualquiera, sincronízalo con `python paquete-tutor/construir.py "qué cambió"`.

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

## Dependencias

Excel, Python con `pywin32` y `pywebview` (usa WebView2, que ya viene en Windows 11), y Claude Code instalado y con sesión iniciada (el comando `claude`). El tutor gasta del plan como un mensaje normal (más si lleva imágenes o PDF); la revisión automática no gasta nada.
