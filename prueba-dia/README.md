# Panel de clase en vivo para Dia (cursos de diagramas UML)

Un panel para dar **cursos de verdad** en el editor **Dia** (0.97.2), como los de Excel: varios módulos, pasos que cambian Dia en vivo, un «Tu turno» que se revisa sin IA, flechas encima de la ventana de Dia que señalan dónde se hace cada cosa, un botón «Hazlo por mí» y un tutor que marca, crea y cambia diagramas con permiso. Empezó como el prototipo del módulo «La clase» (que sigue funcionando igual). Se abre con:

```
python prueba-dia/panel_dia.py                                  # el ejemplo de siempre: el módulo «La clase»
python prueba-dia/panel_dia.py prueba-dia/curso-ejemplo/curso.json   # un curso con módulos (el de ejemplo, que sirve de plantilla)
python prueba-dia/panel_dia.py <curso.json> --probar            # lo arma y lo comprueba todo sin abrir ventanas
```

Se abren **Dia en vivo** y **el panel**:
- **Dia**, con el plugin propio, en **una ventana con dos pestañas**: `clase_en_vivo.dia` (la lección: cada paso la cambia al instante, con lo nuevo del paso seleccionado y con un marco azul) y el diagrama de la persona en ese módulo (`mi_diagrama.dia` en el ejemplo; `mis_diagramas/mi_<módulo>.dia` en un curso). Al cambiar de módulo se abre la pestaña de su diagrama y se cierra la del anterior si está guardada.
- **El panel**, pegado a la derecha y a todo el alto, con dos pestañas: **Lección** (el menú de módulos, el paso a paso, el dibujo del diagrama, «En Dia: dónde se hace» y los botones del paso) y **Tutor**. Es la misma página que el panel de Excel (`../panel-excel/panel.html`). En el último paso de cada módulo, «Siguiente módulo».
- **«Señálamelo en Dia»** dibuja flechas y notas **encima de la ventana real de Dia** (la herramienta «Clase», la pestaña «Atributos» del diálogo, el botón «Nuevo», el campo «Nombre», un objeto del diagrama…). Pasan los clics, no roban el foco, siguen a Dia si se mueve y se borran al cambiar de paso. Si abres Propiedades, en un segundo aparecen también las del diálogo.
- **«Hazlo por mí»** hace la acción del paso delante de la persona (elegir la hoja y la herramienta, abrir Propiedades de una clase en la pestaña que toca…) sobre el ejemplo de la lección. En el «Tu turno» lo haría en su diagrama: entonces pide pulsar otra vez para confirmar.
- **«Tu turno»:** la persona dibuja en su diagrama, guarda (Ctrl+S) y pulsa **Comprobar**: se revisa sin IA (clases, objetos, conexiones con su tipo y sentido, mensajes en orden, guardas…) y, si coincide con un **error típico** del curso, sale su explicación. Si hay cambios sin guardar, pide guardar antes.
- **El tutor** marca su diagrama (en el panel y dentro de Dia), y crea y cambia diagramas de cualquier tipo **con permiso** (Aplicar / No / Deshacer), con ejercicios que se revisan con su propio Comprobar.
- **Recuerda dónde te quedaste** (módulo y paso) al volver a abrirlo (`progreso.json`, junto al curso).

## Cómo hacer un curso

1. Copia `curso-ejemplo/` a una carpeta nueva **en la raíz** de la carpeta del tutor, una por tema (por ejemplo `curso-uml/`, junto a `prueba-dia/`, no dentro), y cambia `curso.json` (`titulo`, `modelo_tutor`, `modulos`). Fuera de `prueba-dia/` el curso es de quien lo hizo: el repositorio no lo versiona y `git pull` no lo toca.
2. Cada módulo es un JSON (los de `curso-ejemplo/` sirven de plantilla):

```json
{"titulo": "Casos de uso", "titulo_codigo": "include", "id": "casos",
 "tema_tutor": "de qué va (para el tutor)", "notas_tutor": "lo que solo sabe el tutor: la solución y los errores típicos",
 "pasos": [
   {"titulo": "«include»", "texto": "Lo que dice el panel (**negrita**, `código`)", "en_dia": "Dónde se hace en Dia: **Dependencia**…",
    "cambios": [{"caso": "Validar carnet"}, {"relacion": "include", "de": "Pedir libro", "a": "Validar carnet"}],
    "senalar": ["Validar carnet"],
    "interfaz": [{"herramienta": "UML - Dependency", "tip": "Dependencia", "texto": "Dependencia"}, {"pestana": "Atributos"}],
    "hazlo": {"etiqueta": "Ábrelo por mí", "hacer": [{"propiedades": "Libro"}, {"pulsar": "Atributos"}]}},
   {"titulo": "Tu turno", "texto": "…", "turno": {
      "titulo": "El cajero", "al_empezar": "…", "al_terminar": "…",
      "conexiones": [{"tipo": "include", "de": "Sacar dinero", "a": "Validar PIN"}],
      "inicial": [{"sistema": "Cajero"}, {"actor": "Cliente"}, {"caso": "Sacar dinero"}, {"caso": "Validar PIN"}],
      "solucion": [{"relacion": "include", "de": "Sacar dinero", "a": "Validar PIN"}],
      "errores": [{"dice": "Eso pasa siempre: es un «include»…",
                   "patron": {"conexiones": [{"tipo": "extend", "de": "Validar PIN", "a": "Sacar dinero"}]},
                   "prueba": [{"relacion": "extend", "de": "Validar PIN", "a": "Sacar dinero"}]}]}}]}
```

   - `cambios`: el vocabulario del bloque `<acciones>` del tutor (cabecera de `dia_planes.py` y `cambios_dia.REGLAS_ACCIONES`). Se suman a los de los pasos anteriores; los objetos que ya están se nombran por su texto. Un mensaje puede llevar `despues_de` o `antes_de` para ir entre dos. El formato del prototipo (`diagrama` con la lista de clases del paso) también vale.
   - `senalar` (opcional): qué resaltar; por defecto, lo nuevo del paso.
   - `interfaz` (opcional): qué señalar encima de Dia: `herramienta` (el tipo de objeto que crea; `tip` la distingue si hay dos, como «Clase» y «Plantilla de clase»), `hoja`, `menu`, `pestana`, `boton`, `campo` (por su etiqueta) u `objeto` (un objeto del ejemplo). Con `texto` y `color` opcionales.
   - `hazlo` (opcional): `hoja`, `herramienta`, `seleccionar`, `propiedades`, `pulsar` (pestaña o botón por su texto), `accion` (solo las de `interfaz_dia.ACCIONES_OK`) y `esperar`.
   - `curso.json` además acepta `convenciones` (`{"nombre_negrita": false, "parametros": "solo_tipo" | "nombre_tipo", "estricto": true, "numeros": {...}, "codigos": {...}}`: cómo se dibuja todo lo del curso y qué exige Comprobar; ver `reglas_uml.py`) y `material_tutor` (`["material.md"]`: archivos de texto junto al `curso.json` que el tutor lee como conocimiento del curso).
   - **`dentro_de` con ruta:** `"service"` (solo si no hay otra capa con ese nombre), `"java/util/function"`, `"java › util"` o `"/util"` (desde la raíz). **Errores a propósito** en un `inicial`: `"negrita": true` dibuja el nombre en negrita y `"parametros": "nombre_tipo"` deja los parámetros con nombre (en esa clase), aunque el curso diga lo contrario.
   - Cambios para convenciones: `{"clase": "X", "dentro_de": "capa"}` y `{"paquete": "awt", "dentro_de": "java"}` (hijas de verdad), `"biblioteca": true` (clase vacía), `"enumerada": ["A", "B"]`, `"parametros": "nombre_tipo"` (esa clase, con nombres) y, en asociación, agregación y composición, `"nombre"` (verbo), `"lectura": "a" | "de"` (triángulo hacia esa clase) y `"direccion"`; la dependencia lleva `"nombre"`. En el «Tu turno», cada clase esperada admite `dentro_de`, `biblioteca`, `enumerada`, `interfaz` y ` {static}`; cada relación, `nombre`, `lectura`, `direccion` y `mult`; los paquetes (`objetos` de tipo `paquete`), `dentro_de`.
   - `turno`: la solución escondida con `clases`/`relaciones`/`objetos`/`conexiones`/`mensajes`/`sinonimos` (como los ejercicios del tutor; o `clase`, el formato del prototipo), `inicial`, `solucion` y `errores` (`dice`, `patron`, `prueba` y, si es solo un consejo, `"consejo": true`).
3. Pruébalo sin ventanas: `python prueba-dia/panel_dia.py <curso.json> --probar`. Trabaja sobre una copia (no toca la carpeta del curso): arma los pasos sin Dia y enseña el texto y lo nuevo de cada uno, revisa cada «Tu turno» con la solución (bien) y con cada error típico (su `dice`), prueba el menú de módulos, los botones y el progreso, y que los módulos mal escritos den un error claro. Termina en «Curso de Dia: todo bien». Tarda unos 10 s con el curso de ejemplo (y `--probar` sin curso, unos 17 s): por eso no tiene modo rápido como el de Excel.
4. Ábrelo con el panel y recórrelo: la primera vez arma cada módulo en Dia (unos segundos).

## Archivos

- `plugin-dia/`: el plugin de Dia para la clase en vivo (código, DLL, compilador y cliente Python). Tiene su propio README.
- `panel_dia.py`: el panel. `Api` (lo que llama la página: `estado`, `ir`, `modulo`, `boton` con `paso`, `mio`, `senalar` y `hazlo`, `comprobar`, `preguntar`, la tarjeta de permiso y el ejercicio del tutor), `DiaEnVivo` (Dia con el plugin y las dos pestañas; mueve la lección, resalta lo nuevo y dibuja o borra las marcas del tutor), `OverlayDia` (el proceso de las flechas), `DibujoDia` (el dibujo del panel: el SVG de Dia) y `TutorDia` (el tutor, que conoce todos los módulos). `--probar` sin curso prueba el ejemplo y todo lo del tutor (marcas, cambios, todos los diagramas, Fase 2 y arreglos); con un curso, `probar_curso`.
- `curso_dia.py`: los cursos: `Curso` y `Modulo` (rutas de cada cosa), la validación del JSON con errores claros, `construir` (los pasos con el plugin o sin él; `aplicar_offline` hace en XML lo que harían las órdenes del plugin), `crear_inicial` (el diagrama de la persona), `revisar_turno` (con errores típicos) y el progreso.
- `interfaz_dia.py`: la interfaz real de Dia: `leer_widgets` (la respuesta de `widgets`, con las ventanas y sus HWND), `resolver` (lo que declara un paso → marcas para el overlay, y lo que no se ve) y `ordenes_hazlo`.
- `overlay_dia.py`: las flechas encima de Dia (proceso aparte, órdenes JSON por stdin). Se puede probar suelto.
- `reglas_uml.py`: las reglas de estilo de «Comprobar» para cursos con convenciones (negrita, parentesco, enumerada, biblioteca, estático, mayúsculas, toString, multiplicidad, navegabilidad, verbo y triángulo de lectura), cada una con su número y dónde se arregla en Dia.
- `dia_uml.py`, `dia_objetos.py`, `dia_planes.py`, `cambios_dia.py`: leer y escribir `.dia`, cualquier objeto de Dia, los demás diagramas y lo que crea el tutor (como antes).
- `catalogo_dia.json`: **se genera** con `python plugin-dia/catalogo.py` (868 tipos de este Dia). No se edita a mano.
- `leccion_clase.json`: el ejemplo de siempre, «La clase» (formato del prototipo).
- `curso-ejemplo/`: el curso de ejemplo (`curso.json` y tres módulos), con su README.
- **Se generan** (no se editan a mano y no van al repositorio): `pasos/` (la pestaña de la lección y los pasos de cada módulo, con `indice.json`), `tutor/` (lo que crea el tutor), `progreso.json` y, en cada curso, lo mismo dentro de su carpeta. **Son de la persona**: `mi_diagrama.dia` y `mis_diagramas/`; el panel nunca los sobrescribe.

## Dependencias

Dia 0.97.2 de dia-installer.de (32 bits) en `C:\Program Files (x86)\Dia` (también su `dia.exe`, para dibujar sin plugin). Python con `pywebview`, `pywin32` y `Pillow` (las flechas encima de Dia; sin Pillow todo lo demás funciona). Claude Code (el comando `claude`) para el tutor. Para recompilar el plugin, MinGW en `C:\MinGW` (ver `plugin-dia/README.md`).
