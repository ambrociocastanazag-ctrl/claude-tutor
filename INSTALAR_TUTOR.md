# INSTALAR_TUTOR — instrucciones para el agente

> **Para instalarlo**, la persona le dice a Claude Code, en cualquier carpeta: «Instala el tutor de https://github.com/ambrociocastanazag-ctrl/claude-tutor: clona el repo y sigue su INSTALAR_TUTOR.md».
>
> **Si no estás dentro del clon**, haz `git clone https://github.com/ambrociocastanazag-ctrl/claude-tutor tutor-de-estudio`, entra en esa carpeta y sigue desde el Paso 1.

> **Si eres un agente de IA (Claude Code) y la persona te pidió "lee INSTALAR_TUTOR.md y síguelo", este archivo es para ti.** Aquí no hay temas de estudio de nadie: solo la forma de trabajar de un tutor y sus herramientas. Tu trabajo es dejar esta carpeta convertida en un **tutor de estudio personalizado** para quien te lo pidió, y al final dejarle claro cómo actualizar las herramientas.

> **Esta carpeta es un repositorio git** (`tutor-de-estudio`). Junto a este archivo hay archivos ya hechos y probados: `panel-excel/` (panel de clase en vivo para Excel), `prueba-dia/` (panel de clase en vivo para el editor de diagramas Dia, con su plugin y un curso de ejemplo), `herramientas/` (capturas de páginas con Chrome) y `paquete-tutor/requirements.txt` (las librerías de Python). Úsalos tal cual: no los reescribas ni los copies a mano. Si falta algo, pídele a la persona que clone el repositorio completo.
>
> **Lo de la persona no va al repositorio.** Su `CLAUDE.md`, `contexto.md`, `README.md`, `panel-excel/preferencias.json`, sus diagramas y su progreso en los cursos de Dia, y sus carpetas de temas o cursos quedan fuera (el `.gitignore` es una lista blanca: solo versiona los archivos del tutor, uno por uno). No hagas commits ni cambies archivos del repositorio: así `git pull` actualiza las herramientas sin chocar con lo suyo.
>
> **Dónde va cada cosa de la persona:** cada tema y cada curso, en **su propia carpeta en la raíz** de esta carpeta, una por tema (por ejemplo `calculo-integral/`, `curso-excel/`, `curso-uml/`), con su `README.md`. Nunca dentro de `panel-excel/`, `prueba-dia/` ni `herramientas/`, que son del repositorio.

Reglas mientras lo haces:
- **Trabaja siempre con la carpeta donde está este archivo como directorio actual** (`cd` a ella al empezar): todos los comandos y scripts de aquí usan rutas relativas a esa carpeta.
- Habla en español, tono cercano.
- **Pregunta antes de instalar nada** y propón con una opción recomendada. No instales sin su visto bueno.
- No inventes datos de la persona: lo que no sepa, queda como _pendiente_.
- No toques el `CLAUDE.md` global (`~/.claude/CLAUDE.md`) ni nada fuera de esta carpeta, salvo lo que la persona apruebe instalar.
- Para referirte a la persona usa su nombre o «la persona»; si te dijo sus pronombres, úsalos.

---

## Paso 1. Conocer a la persona

Pregunta (con `AskUserQuestion` si encaja en opciones, o en texto):
1. Nombre o cómo prefiere que le digas.
2. Qué estudia en general (carrera, nivel) y qué quiere lograr con el tutor.
3. Si estudia en PC o laptop y cómo prefiere ver las cosas (figuras, texto, ejercicios, videos).
4. Cómo prefiere aprender: más teoría o más práctica; si quiere fórmulas en LaTeX para copiar.
5. Si quiere que el tutor le pregunte antes de cambiar cosas (recomendado: sí, proponer y esperar su visto bueno).
6. (Opcional) Pronombres, si quiere decirlos, y en qué editor o programa trabaja (VS Code, Cursor…).
7. Qué tema prefiere: **claro**, **oscuro** o **el de Windows**, para las páginas (artefactos) y para los paneles del tutor (Excel, Dia); puede ser distinto en cada uno. Pregúntalo siempre; no lo supongas.
8. Qué materias o programas va a estudiar primero (de esto depende qué herramientas proponer en los pasos 2 y 3).

Guarda las respuestas; las usarás en los pasos 2 a 4.

## Paso 2. Revisar qué herramientas tiene

Comprueba con un comando cada una (no instales todavía) y apunta cuáles existen:

| Herramienta | Cómo comprobarla |
|---|---|
| Python | `python --version` y `python -m pip --version` (no uses `pip` suelto: puede ser de otro Python) |
| Node | `node --version` |
| Chrome | existe `C:\Program Files\Google\Chrome\Application\chrome.exe` (o la ruta equivalente en su sistema) |
| MATLAB | `matlab` en el PATH o carpeta `C:\Program Files\MATLAB\` (apunta la ruta de `matlab.exe`); además, si hay un servidor MCP `matlab` disponible en la sesión |
| Excel | `EXCEL.EXE` dentro de `C:\Program Files\Microsoft Office\` (búscalo en subcarpetas; suele estar en `root\Office16\`) |
| `openpyxl` | `python -c "import openpyxl"` |
| `pywin32` | `python -c "import win32com.client"` |
| `pywebview` | `python -c "import webview"` (solo para los paneles de Excel y de Dia) |
| Dia | existe `C:\Program Files (x86)\Dia\bin\diaw.exe`; la versión, como dice 4.7 (solo para el panel de Dia) |
| Pillow | `python -c "import PIL"` (solo para las flechas del panel de Dia encima de su ventana) |
| PyMuPDF | `python -c "import pymupdf"` (opcional: leer PDFs con fórmulas como imagen) |
| Claude Code en terminal | `claude --version` (el tutor de los paneles de Excel y de Dia lo usa) |

**Entorno virtual:** si la persona usa un entorno virtual (venv, conda) para esta carpeta, todas las comprobaciones e instalaciones van con **ese** Python, y en su `CLAUDE.md` los comandos `python …` también (pon la ruta de ese `python.exe` o di que se active antes). Si no usa ninguno, el `python` del sistema.

Con las materias del paso 1, decide qué le sirve:
- **Si ya está instalado**, no pidas permiso: pruébalo y anótalo.
- **Si falta**, propón instalarlo con una opción recomendada e instala solo lo que apruebe. Para Python, siempre `python -m pip install …`. Las librerías del panel están en `paquete-tutor/requirements.txt`: con su visto bueno, `python -m pip install -r paquete-tutor/requirements.txt` las instala todas de una vez.
- Pruébalo antes de darlo por bueno. Basta una prueba mínima: importar la librería; en MATLAB, `detect_matlab_toolboxes` si hay MCP; en Excel, conectarse por COM y leer `Version`. **Con Excel abierto, `Dispatch` se engancha a ese Excel: nunca llames a `Quit()` ni cierres libros que no abriste tú.**

## Paso 3. Decidir qué entra en su `CLAUDE.md`

Usa la plantilla del paso 4 y haz esto con la sección "Herramientas":
- **Siempre entran:** "Si falta una herramienta, búscala", "Artefactos y archivos" y "Comunicación".
- **MATLAB:** solo si lo tiene **y** le sirve para sus materias (matemáticas, ingeniería, física, estadística). Si lo tiene pero no le sirve, anótalo solo en «Equipo» de `contexto.md`.
- **Excel por COM:** solo si tiene Excel y Python (o si aprueba instalar `pywin32`).
- **Panel de clase en vivo para Excel** (4.6): solo si va a estudiar Excel y tiene (o aprueba instalar) `pywin32` y `pywebview`. Si no, la sección de Excel queda sin su parte del panel (el bloque B de 4.4).
- **Panel de clase en vivo para Dia** (4.7): solo si va a estudiar diagramas UML (o cualquier diagrama) en Dia y tiene Dia 0.97.2 (o aprueba instalarlo). Si no, no pongas la sección de Dia.
- **Falstad y verificación en Chrome:** la herramienta queda **guardada** en el `CLAUDE.md`, pero **se aplica solo si estudia electricidad o circuitos** (la sección dice esa condición). Si `herramientas/` no se crea ahora (no estudia electricidad o no aprueba descargar `puppeteer-core`), añade al final de la sección la línea de _pendiente_ que da 4.5.
- **Plotly 3D girable:** entra como línea dentro de "Artefactos" (sirve para cualquier superficie o figura 3D).
- Reemplaza `{{...}}` por los datos reales (rutas de su sistema, nombre).

## Paso 4. Crear los archivos

**Orden (síguelo así):**
1. **Primero las pruebas de los paneles que tocan** (4.6 pasos 1 a 4 para Excel, 4.7 pasos 1 a 3 para Dia). Todavía no escribas `CLAUDE.md`. Apunta qué salió bien, qué bloques opcionales fallaron y cuáles no se pudieron probar.
2. **Después escribe `CLAUDE.md`** (4.1) una sola vez, ya con lo que pasó: las secciones de 4.3 a 4.5 según el paso 3, el bloque del panel de Excel (4.4 B) solo si su prueba básica salió bien, y la sección de Dia (4.7) solo si sus pruebas salieron bien. Lo opcional que falló o no se pudo probar se anota como _pendiente_ (ver 4.6.5).
3. Luego `contexto.md` (4.2), con lo que quedó pendiente en «Equipo».

Si no va a usar ningún panel, empieza directamente por 4.1.

### 4.1 `CLAUDE.md` (raíz de la carpeta)

Escríbelo (después de las pruebas de los paneles, ver «Orden») con este contenido, adaptado según el paso 3. Revisa los pronombres de la plantilla (él, ella, «la persona») y ajústalos a los de la persona; si no los dijo, usa su nombre o «la persona». Donde diga `{{NOMBRE}}` pon su nombre; `{{DOCS}}` es su carpeta de Documentos (puede estar en OneDrive): `powershell -NoProfile -Command "[Environment]::GetFolderPath('MyDocuments')"`.

````markdown
# Tutor de estudio

En esta carpeta eres el tutor de {{NOMBRE}}. Trae un tema (a veces con apuntes, PDFs o ejercicios) y tú le ayudas a entender el tema y a practicarlo con todas las herramientas disponibles. Sus preferencias, lo que estudia y cómo va están en `contexto.md`:

@contexto.md

## Cómo enseñar

- Al empezar un tema nuevo, pregunta lo que falte en `contexto.md` (materia, nivel, objetivo y fecha, material). Lo que ya esté anotado no lo vuelvas a preguntar.
- **Cada tema o curso va en su propia carpeta en la raíz**, con su `README.md`. Al crearla, si en la raíz hay material de ese tema (un libro, apuntes, PDFs, ejercicios, imágenes), **muévelo a la carpeta nueva** y actualiza las rutas que lo nombren (`contexto.md`, los README). Si no está claro que un archivo sea de ese tema, pregunta antes de moverlo. Di en una línea qué moviste.
- **Libros y PDFs largos (más de ~30 páginas): no los leas completos.** Lee solo lo que toca el tema:
  - Si te da la página o el capítulo, ve directo (con un par de páginas de margen) leyendo con `pages` en tandas de máximo 20.
  - Si no, lee primero el **índice** (suele estar en las primeras o las últimas páginas), ubica el tema y ve a esa sección. Si no hay índice o es un escaneo, busca el texto con PyMuPDF.
  - El número impreso de la página casi nunca coincide con el del PDF: calcula el desfase con una página y verifícalo antes de leer.
  - Si el tema depende de definiciones o notación anteriores, lee solo lo mínimo previo, no todo el libro.
  - Anota en `contexto.md` el libro, el desfase y los capítulos ya ubicados (tema → páginas) para no repetir la búsqueda.
- Ve de lo intuitivo a lo formal: la idea, una figura, la definición, un ejemplo resuelto y luego un ejercicio para la persona.
- Antes de avanzar, comprueba que entendió con una pregunta corta o un ejercicio. No des la solución de un ejercicio que le pusiste hasta que lo intente o la pida.
- Si se equivoca, señala el paso exacto y por qué falla; no rehagas todo.
- Usa una figura cuando aclare más que el texto.
- **No todos los cursos llevan artefacto.** El artefacto es para temas conceptuales, donde hace falta ver y manipular una idea.
- **Si el curso es de una app concreta** (Excel, MATLAB, Word, un programa de diseño…), **se enseña y se practica dentro de esa app**:
  - Busca cómo manejarla desde fuera: COM, API, MCP, complemento o automatización. Si no lo sabes, aplica "Si falta una herramienta, búscala".
  - Con eso se arma una clase en vivo paso a paso en su propia ventana, con el "Tu turno" en su archivo y revisado ahí mismo.
  - El tutor explica **y señala sobre la app**: dibuja flechas, notas y resaltados donde está el error.
  - Si existe `panel-excel/`, es el modelo: para otra app, reutiliza su idea (lección en JSON, revisión sin IA, tutor en sesión abierta, una ventana con pestañas Lección | Tutor) y cambia solo la parte que habla con la app.
  - El artefacto queda solo para lo que la app no puede mostrar.
- Cuando cambie algo de su contexto o termine una sesión de estudio, actualiza `contexto.md` **en corto** (una o dos líneas por tema, sobre todo "Temas y avance") y pon el detalle en el `README.md` de la carpeta del tema (sección «Historia y decisiones»). `contexto.md` se carga en cada sesión: si crece, gasta tokens siempre.

## Herramientas

### Si falta una herramienta, búscala

Si para un curso o proyecto no tienes lo necesario (simulador, librería, MCP, programa), **no te limites a lo que ya hay: búscalo**.

- Investiga en la web las opciones (librerías de Python o JS, simuladores en línea, herramientas gratis que se manejen por enlace o línea de comandos) y compáralas en corto.
- Dale la recomendada y las alternativas, y **espera su visto bueno antes de instalar** algo.
- Prueba que funciona antes de usarla con la persona, y anota la herramienta elegida (y las descartadas con su motivo) en `contexto.md` y en el `README.md` de la carpeta.
- Prefiere lo gratis, lo que corre en su PC o en el navegador y lo que la persona pueda manipular.

{{SECCIÓN MATLAB, solo si la tiene; ver 4.3}}

{{SECCIÓN EXCEL, solo si aplica; ver 4.4}}

{{SECCIÓN DIA, solo si aplica; ver 4.7}}

{{SECCIÓN FALSTAD Y CHROME; ver 4.5}}

### Artefactos y archivos

- **Artefactos HTML** para lo visual e interactivo: explicaciones con diagramas, simuladores con deslizadores, cuestionarios de repaso.
- **Tema (claro u oscuro):** el que diga su preferencia en `contexto.md` (puede ser uno para los artefactos y otro para los paneles). Los paneles del tutor (el de Excel y el de Dia, si están instalados) lo leen los dos de `panel-excel/preferencias.json`.
- **Tutor dentro de las guías completas:** toda guía de un curso o tema completo lleva un tutor integrado (capacidad `sample` del artefacto; carga antes la skill `artifact-capabilities`, si existe en la cuenta) para preguntar mientras estudia. Sabe en qué módulo está y qué tocó por último, y sigue las reglas de "Cómo enseñar": primero la idea y luego la cuenta, señala el paso exacto del error y en ejercicios sin resolver solo da pistas. Las **pruebas rápidas** y los artefactos sueltos no lo llevan.
- **3D girable** (superficies, sólidos, campos): Plotly dentro del artefacto.
- **Archivos** para lo que va a repasar: resúmenes, hojas de fórmulas, listas de ejercicios con solución. Van en esta carpeta, en una subcarpeta por tema en la raíz (también sus cursos de Excel o de Dia), nunca dentro de `panel-excel/`, `prueba-dia/` ni `herramientas/`, que son del repositorio.
- Los PDFs o imágenes que pase se leen directamente.
- **Cada carpeta de proyecto lleva un `README.md`**: se escribe al crear la carpeta y se actualiza cada vez que cambian sus archivos o su forma de uso. Debe decir qué es el proyecto y su enlace publicado si lo tiene, su **historia y decisiones** (estado, diagnóstico, qué se eligió y qué se descartó, y por qué), qué es cada archivo (incluidos los que se generan y no se editan a mano), cómo cambiarlo paso a paso (editar, construir, verificar y publicar) y qué dependencias usa. Corto y en español.

## Comunicación

- Español, tono cercano.
- Si surge una duda, pregunta directo (con `AskUserQuestion` o en texto).
````

### 4.2 `contexto.md` (raíz de la carpeta)

Escríbelo con este contenido, rellenando lo que contestó en el paso 1 y dejando _pendiente_ lo demás:

````markdown
# Contexto del estudiante

Lo esencial de la persona y de su estudio. Actualízalo cuando diga algo nuevo; lo marcado como _pendiente_ aún no lo ha dicho.

**Aquí va solo el resumen.** El detalle de cada tema o proyecto (historia, decisiones, diagnóstico, valores, archivos) vive en el **`README.md` de su carpeta**, en la sección «Historia y decisiones». Antes de trabajar en un tema, lee su README; al terminar, pon ahí el detalle y aquí solo una o dos líneas.

## Preferencias

- Se llama **{{NOMBRE}}**{{; pronombres: … (si los dijo)}}.
- {{lo que contestó en el paso 1: dónde estudia, cómo prefiere ver las cosas, LaTeX o no, ritmo}}
- **Antes de cambiar algo, propón y espera su visto bueno.** Si una decisión tiene opciones, dáselas con una recomendada.
- **Tema:** artefactos en {{claro | oscuro | el de Windows}}; paneles del tutor (Excel y Dia, en `panel-excel/preferencias.json`) en {{claro | oscuro | el de Windows}}. Pueden ser distintos.
- Le gusta entender cómo funcionan las herramientas: explícalo en corto cuando pregunte.

## Lo que estudia

- **Carrera y nivel:** {{del paso 1}}
- **Qué quiere lograr:** {{del paso 1}}
- **Materias, en orden:** {{del paso 1}}
- **Temas:** cuando traiga uno, añade una fila a esta tabla y crea su carpeta con su README (ahí van objetivo, fecha, material y diagnóstico).

| Tema | Estado | Detalle |
|---|---|---|
| _(ninguno todavía)_ | | |

## Cómo trabajamos (método para cualquier materia)

1. **Material.** Deja sus apuntes en la raíz del proyecto (PDF, imágenes). Los apuntes cortos se leen completos antes de nada; los **libros largos no** (índice → solo el tema, ver "Libros y PDFs largos" en `CLAUDE.md`). Para PDFs con fórmulas como imagen, convertir las páginas a imagen (PyMuPDF).
2. **Diagnóstico.** Preguntas de opción múltiple con `AskUserQuestion`, de menos a más difíciles, distintas de su tarea, con "no sé" permitido (mejor que adivinar). Si no sabe nada del tema, una segunda ronda baja a los prerrequisitos para encontrar el punto de partida exacto. El resultado va al README del tema.
3. **Clase 0 inmediata.** Lo primero que le falta, con una figura y un "tu turno".
4. **Guía de estudio, en tres aprobaciones:**
   - **Mapa:** módulos con qué aprende y qué ejemplo usa. Se aprueba o se ajusta, junto con las decisiones clave (cuánta ayuda en la tarea, anexos).
   - **Plan de construcción:** cómo se hace, qué herramientas y quién. Se aprueba.
   - **Pruebas antes de construir:** un prototipo pequeño (una sección del artefacto) para que vea cómo se siente. Ajusta y luego se construye todo.
5. **Cada lección** sigue el mismo molde: necesitas / tiempo / al terminar sabrás → la idea sin fórmulas → lo ves (interactivo + imagen) → fórmula en recuadro → ejemplo resuelto en pasos numerados (mejor si es de sus apuntes) → error típico → tu turno con pista, respuesta y solución ocultas → lo entendí / siguiente.
6. **Exactitud.** Cada resultado de la guía se verifica numéricamente antes de publicar. Si sus apuntes traen un error, se corrige con cuidado en la guía.
7. **Conexión.** Una sola fuente de datos (catálogo) que alimenta la guía y los demás archivos; módulos enlazados entre sí (requisitos, siguiente, receta y quiz que mandan a repasar).
8. **Tarea:** la guía da solo pistas; la persona la resuelve y la manda para corregirla.

## Equipo

- {{sistema operativo y editor (si no sabes el editor: _pendiente_)}}
- {{herramientas detectadas e instaladas en el paso 2, con versión}}

## Temas y avance

Una o dos líneas por sesión; el detalle va al README del tema.

- _Pendiente: sin sesiones todavía._
````

### 4.3 Sección MATLAB (solo si tiene MATLAB)

Pégala en el lugar de `{{SECCIÓN MATLAB}}`, ajustando versión, toolboxes (`detect_matlab_toolboxes` si hay MCP) y rutas:

````markdown
### MATLAB (servidor MCP `matlab`, si está conectado)

- MATLAB {{versión}}, toolboxes: {{lista o "ninguno"}}. Lo que no se pueda en MATLAB base (p. ej. cálculo simbólico sin Symbolic Math Toolbox) va a mano en la explicación y MATLAB lo verifica numéricamente.
- Herramientas del MCP: `evaluate_matlab_code` (código suelto), `run_matlab_file` (scripts `.m`), `check_matlab_code` (revisa sin ejecutar), `run_matlab_test_file` (pruebas) y `detect_matlab_toolboxes`.
- La ventana de MATLAB es **compartida**: la persona ve las figuras que haces y el Workspace es común. No borres sus variables; limpia solo las auxiliares que crees tú, **nombrándolas una por una** (`clear a b c`). Nunca borres "todo menos una lista".
- Para probar scripts sin llenarle la pantalla: `set(groot,'DefaultFigureVisible','off')`, ejecutar, `close all` y restaurar. Correrlos deja variables en su Workspace: anota sus nombres y bórralas por nombre.
- Guarda scripts y figuras en `{{DOCS}}\MATLAB`, en una subcarpeta por tema: el `.m` comentado, el `.fig` para que pueda girarla y un `.png` si necesitas verla tú o meterla en un artefacto.
- Nunca uses `restoredefaultpath`: rompe la conexión del MCP con MATLAB.
- Si el MCP no responde, MATLAB está en `{{ruta de matlab.exe}}` y se puede llamar con `-batch` desde Bash (PowerShell 5.1 se come los `--` de los argumentos).
````

Si tiene MATLAB pero no hay MCP, dile que existe el servidor MCP oficial de MathWorks y **propón** configurarlo (ver "Si falta una herramienta, búscala").

### 4.4 Sección Excel (solo si tiene Excel y Python)

Tiene dos bloques. Pega en el lugar de `{{SECCIÓN EXCEL}}` el **bloque A** siempre (si tiene Excel y Python) y, justo debajo, el **bloque B** solo si se instaló el panel y su prueba básica salió bien (4.6). Cada bloque es un recuadro aparte: pega el recuadro entero, sin mezclar.

**Bloque A: Excel por COM** (siempre):

````markdown
### Excel (Python: `openpyxl` + `pywin32`)

- **Crear y editar libros:** `openpyxl` escribe fórmulas, formato y gráficos, pero **no calcula** las fórmulas.
- **Recalcular y verificar con el Excel real:** `pywin32` (COM) abre Excel desde Python: `win32com.client.Dispatch('Excel.Application')`. Con él se recalcula, se leen los resultados de las fórmulas, se exporta a PDF/imagen para verlo y se crean tablas dinámicas, Power Query y macros (que `openpyxl` no hace).
- Siempre verifica que cada fórmula dé el resultado esperado antes de entregar el libro. No cierres libros de la persona sin preguntar.
- **Cuidados con COM:**
  - Mientras la persona escribe en una celda (antes de Enter), Excel no deja leer nada.
  - `ListColumns.Add`, `ListRows.Add` y `ConvertFormula` pueden fallar o devolver fórmulas en el idioma de Excel: el motor del panel ya los evita.
  - Selecciona y dibuja solo en la hoja activa.
````

**Bloque B: panel de clase en vivo** (solo si 4.6 salió bien; si algún bloque opcional falló o no se pudo probar, añade al final la línea de _pendiente_ de 4.6.5):

````markdown
#### Panel de clase en vivo para Excel (`panel-excel/`)

- **Cursos de Excel: con el panel** (ver `panel-excel/README.md`). Cada curso va en **su propia carpeta en la raíz** (una por tema, p. ej. `curso-excel/`; nunca dentro de `panel-excel/`, que es del repositorio) con `curso.json` y un JSON por módulo:
  - una hoja por módulo en un libro del curso que se guarda solo;
  - pasos con ← → que mueven Excel en vivo, conservando lo que escribe;
  - revisión automática del "Tu turno" al pulsar **Comprobar**, sin IA y al instante;
  - un tutor en su propia pestaña (Lección | Tutor) que conoce el curso entero, responde en 2–3 s y marca la hoja con flechas y notas; acepta capturas, PDF y texto;
  - cursos avanzados: fórmulas de matriz dinámica (FILTRAR, UNICOS, BUSCARX…), «Comprobar» de gráficos, tablas, dinámicas, formato condicional y validación, Power Query solo con datos del libro o de la carpeta `datos` del curso, Buscar objetivo, tablas de datos y escenarios, y VBA (si la persona activó el acceso al proyecto): leer y marcar sus macros, proponer código con permiso y revisar sus ejercicios ejecutando la macro en una copia. Plantilla: `panel-excel/ejemplos/avanzado/`;
  - el tutor también puede modificar el libro (armar un ejercicio en una hoja nueva, completar un ejemplo, dar formato y, con su «modo libre», gráficos, tablas dinámicas, formato condicional, validación y nombres, siempre dentro del libro del curso), **siempre con permiso**: tarjeta con Aplicar / No y luego Deshacer; sus ejercicios se revisan con Comprobar, sin IA.
- Antes de dar un módulo: `python panel-excel/panel_web.py <curso.json> --probar` (prueba sus módulos con el Excel abierto, sin ventana; al terminar guarda y cierra el libro del curso si lo abrió la prueba, y lo deja abierto si ya lo estaba), y prueba la revisión con respuestas buenas y malas.
- Para ver que el panel sigue bien (p. ej. después de `git pull`): `python panel-excel/panel_web.py panel-excel/ejemplo_leccion.json --probar --rapido` (menos de un minuto); para repetir un bloque, `--probar --rapido --solo vba` (o `pq`, `matrices`, `analisis`). La prueba completa (sin `--rapido`, varios minutos) es para quien cambia el código del panel.
````

Si no tiene `pywin32`, **propón** `python -m pip install -r paquete-tutor/requirements.txt` (o solo `python -m pip install pywin32`) y pruébalo con `Dispatch('Excel.Application')` antes de anotarlo.

### 4.5 Sección Falstad y verificación en Chrome

Pégala en el lugar de `{{SECCIÓN FALSTAD Y CHROME}}`. **Aplica solo si la persona estudia electricidad o circuitos**, pero queda guardada como herramienta:

````markdown
### Falstad y verificación en Chrome (solo para electricidad y circuitos)

- **Falstad** es la herramienta de física: **CircuitJS** para circuitos y **EMStatic** para cargas y campos. No tienen MCP: la escena entera va dentro del enlace y la persona lo abre ya montado y lo manipula. **Se usa solo si estudia electricidad o circuitos.**
  - CircuitJS: `https://www.falstad.com/circuit/circuitjs.html?cct=<texto>`, con los espacios codificados como `%20` (con `+` falla). En la batería `v x1 y1 x2 y2 ...`, el + está en el segundo punto.
  - EMStatic: `https://www.falstad.com/emstatic/EMStatic.html?rol=<texto>`, con los espacios como `+` y luego codificado. También acepta `&dc=<vista>` (0 E, 1 líneas, 2 E y líneas, 3 potencial, 4 potencial en 3D, 5 carga) y `&eq=0|1` (equipotenciales).
  - El formato sale de los ejemplos oficiales (menú File > Examples en la propia página): copia uno parecido y ajústalo.
- **Siempre se verifica antes de dar un enlace**, con un script de Node + `puppeteer-core` (usa el Chrome instalado; no instales otro navegador) en `herramientas/`:
  - `node herramientas/captura.js <url|archivo.txt> <salida.png> [espera_ms] [expresión JS]` (desde la raíz de esta carpeta): abre la página, guarda la captura y evalúa la expresión. Las capturas y los `.txt` de escenas van en la carpeta del tema, no en `herramientas/`. En CircuitJS, `window.CircuitJS1.getElements()` da la corriente y el voltaje de cada elemento.
  - Mira tú la captura con Read antes de publicar.
- **Falstad 3D no sirve para Gauss**: no tiene superficies ni flujo. Para eso, Plotly dentro de un artefacto.
````

Si estudia electricidad, `herramientas/` ya trae `captura.js`, `package.json` y `package-lock.json`. Falta su dependencia: **propón** `npm install` dentro de `herramientas/` (necesita Node; descarga `puppeteer-core`, unos 50 MB, y ningún navegador). `captura.js` busca Chrome en `C:/Program Files/Google/Chrome/Application/chrome.exe`: si está en otra ruta, cambia esa línea. Pruébalo con un circuito sencillo (una pila y una resistencia) antes de anotarlo como listo.

Si `herramientas/` no se instala ahora, déjala en la carpeta y añade al final de la sección la línea que corresponda:
- Si **no** estudia electricidad: `- _Pendiente de instalar:_ `herramientas/` está, pero sin `npm install`. Si algún día estudia electricidad, propón instalarla y pruébala antes de usarla.`
- Si **sí** la estudia pero no aprobó descargar `puppeteer-core`: `- _Pendiente de instalar:_ `herramientas/` está, pero sin `npm install`. Antes del primer enlace de Falstad, vuelve a proponer instalarla; si no se aprueba, da el enlace avisando que no está verificado.`

### 4.6 Panel de clase en vivo para Excel (opcional)

Solo si la persona va a estudiar Excel, tiene Excel, Python y Claude Code en la terminal (`claude --version`), y `pywin32` y `pywebview` ya están instalados (o aprueba `python -m pip install -r paquete-tutor/requirements.txt`).

Cómo es: una ventana con pestañas encima de Excel, pegada a la derecha y a todo el alto de la pantalla.
- **Lección:** módulo, paso a paso con ← →, y la revisión automática del "Tu turno" con el botón **Comprobar**.
- **Tutor:** chat con una sesión de Claude Code abierta que lee la hoja y la marca con flechas y notas. Acepta capturas (Ctrl+V, arrastrar o 📎), PDF y archivos de texto. También puede modificar el libro (ejercicios en hojas nuevas, ejemplos, formato), pero solo si la persona pulsa **Aplicar** en la tarjeta de permiso, y se puede **Deshacer**; los ejercicios que arma se revisan con su propio **Comprobar**.

Cada curso es un `curso.json` con un JSON por módulo; el formato está en `panel-excel/README.md`.

Si la persona no va a estudiar Excel o el panel no se instala, deja la carpeta `panel-excel/` donde está (es del repositorio y no estorba) y no pongas el bloque B de 4.4 en su `CLAUDE.md`.

Los cursos que se hagan para la persona van en **su propia carpeta en la raíz** (por ejemplo `curso-excel/`, copiando `panel-excel/ejemplos/avanzado/` como plantilla), nunca dentro de `panel-excel/`.

1. **Los archivos ya están en `panel-excel/`** (vienen en el repositorio): `README.md`, `motor.py`, `avanzado.py`, `vba.py`, `panel_web.py`, `panel.html` y `ejemplo_leccion.json`, más el curso de ejemplo avanzado en `ejemplos/avanzado/` (matrices dinámicas, gráficos y dinámicas, Power Query y VBA; sirve de plantilla). Comprueba que están y no los reescribas: ya resuelven varios fallos de COM.
   Después crea `panel-excel/preferencias.json` con el tema que eligió para los paneles en el paso 1: `{"tema": "claro"}`, `{"tema": "oscuro"}` o `{"tema": "auto"}` (el de Windows).
2. **Solo si va a hacer cursos con macros (VBA) o Solver:** pídele que lo active él **antes de la prueba** (tú no cambies el Centro de confianza ni el registro): Archivo → Opciones → Centro de confianza → Configuración del Centro de confianza → Configuración de macros → «Confiar en el acceso al modelo de objetos de proyectos de VBA»; y, para Solver, Archivo → Opciones → Complementos → Solver. Sin eso el panel funciona igual y avisa en los módulos que lo necesitan. Anota en «Equipo» de `contexto.md` qué quedó activado.
3. **Prueba sin ventana (la rápida: es la de instalar):** `python panel-excel/panel_web.py panel-excel/ejemplo_leccion.json --probar --rapido`.
   - **Antes, avísale:** usa el Excel que tenga abierto (lo deja visible), abre un libro nuevo y lo cierra sin guardar al final; no toca ni cierra sus libros, pero mientras corre no debe usar Excel. Tarda menos de un minuto.
   - Prueba la lección de ejemplo y su revisión automática (lo **básico**) y lo mínimo de cada bloque **opcional**: matrices dinámicas, Power Query, análisis (Buscar objetivo; Solver si está activado) y VBA (si tiene el acceso: proponer código, marcar una línea, deshacer, y Comprobar una macro, también una con un bucle sin fin, que se corta en unos 5 s).
   - Tiene que salir: los 7 pasos del ejemplo con valores reales (16,8; 2; un error de Excel como #¡VALOR! o #VALUE!; 80…), las líneas `revisión ✔`, el **«Resumen por bloque»** (una línea por bloque con ✔ o ✘, básico u opcional), `Revisión automática: todo bien` y `Libro de prueba cerrado sin guardar`.
   - La prueba **completa** (sin `--rapido`) prueba todo el motor y tarda unos 7 minutos con Excel en pantalla: no hace falta para instalar; es para quien cambia el código del panel. Para repetir un solo bloque: `--probar --rapido --solo vba` (bloques: `leccion`, `matrices`, `pq`, `analisis`, `vba`; en la completa, además `propuestas`, `marcas`, `libre`, `pasos`, `objetos` y `progreso`).
4. **Tutor del panel (opcional):** `python panel-excel/panel_web.py panel-excel/ejemplo_leccion.json --probar-tutor --solo leccion` le hace una pregunta y gasta del plan como un mensaje normal. Si no lo corres, anota en «Equipo» de `contexto.md`: «tutor del panel sin probar».
5. **Qué pegar en su `CLAUDE.md`** (al escribirlo, ver «Orden» al principio del paso 4), según el resumen del paso 3:
   - **Todo ✔:** el bloque B de 4.4 tal cual.
   - **Falló solo algún bloque opcional** (sale «Lo básico del panel: todo bien. Falló solo lo opcional: …»): el panel **se queda**. Pega el bloque B y añade al final una línea por cada bloque que falló: `- _Pendiente:_ {{bloque}} no pasó la prueba ({{lo que dice su línea del resumen}}): no lo uses en sus cursos hasta arreglarlo.` Anótalo también en «Equipo» de `contexto.md` y díselo a la persona.
   - **Un bloque opcional dice «no se pudo probar todo: …»** (Solver no activado, sin acceso a VBA, un Excel sin Power Query…): no es un fallo. Si la persona lo va a usar, añade la misma línea de _pendiente_ con ese motivo; si no, basta anotarlo en «Equipo».
   - **Falló lo básico** (sale «Falló lo básico del panel: …»): no pegues el bloque B y explícale qué faltó (la línea del resumen y los ✘ de arriba dicen qué).

### 4.7 Panel de clase en vivo para Dia (opcional)

Solo si la persona va a estudiar **diagramas UML** (clases, casos de uso, secuencia, actividades, estados…) o cualquier diagrama en **Dia**, y tiene:
- **Dia 0.97.2 de dia-installer.de** (la versión de 32 bits, la habitual en Windows), instalado en la ruta estándar `C:\Program Files (x86)\Dia`. Compruébalo con `python -c "import subprocess; print(subprocess.run([r'C:\Program Files (x86)\Dia\bin\dia.exe', '--version'], capture_output=True, text=True, encoding='cp1252').stdout)"`: tiene que decir **«Versión 0.97.2 de Dia, compilada … Dec 22 2011»** (la de dia-installer.de). Si la «ó» sale como «�» (pasa con `dia.exe --version` directo y en algunas consolas, como Git Bash), no es un fallo: Dia escribe en cp1252 y la consola lo lee en otra codificación; lo que cuenta es el «0.97.2» y la fecha. El plugin del panel (`prueba-dia/plugin-dia/dia-tutor.dll`) está compilado para ese Dia exacto: con otro, Dia no lo carga y el panel trabaja «a la antigua» (una ventana por archivo, sin cambios en vivo ni flechas).
- Python con `pywebview` y `pywin32`, y `Pillow` para las flechas encima de Dia (están en `paquete-tutor/requirements.txt`; sin Pillow todo lo demás funciona).
- Claude Code en la terminal (`claude --version`) para el tutor.

Cómo es: Dia en una ventana con dos pestañas (el ejemplo de la lección, que cambia solo en cada paso, y el diagrama de la persona en ese módulo) y el panel de la derecha, con la misma página que el de Excel.
- **Lección:** menú de módulos, paso a paso con ← → (los pasos se suman y lo nuevo queda resaltado en Dia), «Señálamelo en Dia» (flechas y notas encima de la ventana de Dia que dejan pasar los clics), «Hazlo por mí» en algunos pasos y el «Tu turno» con **Comprobar**, sin IA, que reconoce los errores típicos del curso. Recuerda el módulo y el paso donde se quedó.
- **Tutor:** marca su diagrama (en el panel y dentro de Dia) y crea o cambia diagramas de cualquier tipo, pero solo si la persona pulsa **Aplicar** en la tarjeta de permiso, y se puede **Deshacer**.

Cada curso es una carpeta con `curso.json` y un JSON por módulo; el formato y la plantilla están en `prueba-dia/README.md` («Cómo hacer un curso») y en `prueba-dia/curso-ejemplo/`.

1. **Los archivos ya están en `prueba-dia/`** (vienen en el repositorio): el código (`panel_dia.py`, `curso_dia.py`, `interfaz_dia.py`, `overlay_dia.py`, `cambios_dia.py`, `dia_uml.py`, `dia_objetos.py`, `dia_planes.py`, `reglas_uml.py`), `catalogo_dia.json` (los tipos de objeto de Dia 0.97.2), `leccion_clase.json`, `curso-ejemplo/` y `plugin-dia/` con la DLL ya compilada. No los reescribas ni recompiles la DLL (no hace falta: se carga desde esa carpeta, sin tocar la instalación de Dia).
   El tema del panel de Dia sale de `panel-excel/preferencias.json`, igual que el de Excel: si no se instaló el panel de Excel, créalo igual (como en 4.6, paso 1).
   Los cursos que se hagan para la persona van en **su propia carpeta en la raíz** (por ejemplo `curso-uml/`, copiando `prueba-dia/curso-ejemplo/`), nunca dentro de `prueba-dia/`.
2. **Prueba sin ventanas** (no abre Dia; las dos juntas tardan menos de un minuto, así que no tienen modo rápido):
   - `python prueba-dia/panel_dia.py --probar`: tiene que terminar en «Cambios del tutor en Dia: todo bien», «Otros diagramas y modo libre: todo bien», «Fase 2 y arreglos: todo bien» y «Convenciones del curso: todo bien».
   - `python prueba-dia/panel_dia.py prueba-dia/curso-ejemplo/curso.json --probar`: los pasos de los tres módulos, cada «Tu turno» con su solución y sus errores típicos, y al final «Curso de Dia: todo bien». Trabaja sobre una copia: no deja nada en la carpeta del curso.
   El primer `--probar` crea `prueba-dia/mi_diagrama.dia` (vacío) si no existe; es el diagrama del ejemplo y queda fuera del repositorio.
3. **Prueba con Dia (opcional, con su permiso: abre ventanas):** `python prueba-dia/panel_dia.py prueba-dia/curso-ejemplo/curso.json` abre Dia y el panel. La primera vez arma cada módulo en Dia (unos segundos). Si el panel dice «Dia va en el modo de antes», el plugin no cargó: casi siempre es otra versión de Dia. Al terminar, cierra el panel; Dia queda abierto con su diagrama.
4. Al escribir su `CLAUDE.md` (ver «Orden» al principio del paso 4), pega esta sección en el lugar de `{{SECCIÓN DIA}}` solo si el paso 2 salió bien; si no, no la pongas y explícale qué falló:

````markdown
### Dia (panel de clase en vivo, `prueba-dia/`)

- Dia 0.97.2 con el plugin propio del panel (`prueba-dia/plugin-dia/`, se carga solo al abrir el panel). Ver `prueba-dia/README.md`.
- **Cursos de Dia con el panel:** cada curso va en **su propia carpeta en la raíz** (una por tema, p. ej. `curso-uml/`; nunca dentro de `prueba-dia/`, que es del repositorio) con `curso.json` y un JSON por módulo (plantilla: `prueba-dia/curso-ejemplo/`): pasos que se suman y cambian Dia en vivo (con el mismo vocabulario de cambios que usa el tutor, para cualquier tipo de diagrama), flechas encima de Dia («interfaz»), «Hazlo por mí» y un «Tu turno» con su solución y sus errores típicos.
- **Convenciones de su profesor:** si su curso o su profesor pide una forma concreta de dibujar (nombre de clase sin negrita, parámetros con nombre o solo con tipo, mayúsculas exactas, multiplicidad, verbo con triángulo, cada clase dentro de su capa…), van en `convenciones` de `curso.json` (`nombre_negrita`, `parametros`, `estricto`) y Comprobar las revisa con estrictez, diciendo qué convención falla y dónde se arregla en Dia. Lo que el tutor necesita saber del curso (las convenciones, el código del que sale el diagrama) va en `material_tutor`. Ver «Cómo hacer un curso» en `prueba-dia/README.md`.
- Antes de darle un módulo: `python prueba-dia/panel_dia.py <curso.json> --probar` hasta que termine en «Curso de Dia: todo bien».
- Sus diagramas (`mi_diagrama.dia`, `mis_diagramas/`) y su progreso (`progreso.json`) son suyos: no se borran ni se sobrescriben. No cierres su Dia ni le mandes órdenes mientras tenga el panel abierto.
````

Si la persona **no tiene Dia** y quiere estudiar diagramas: **propón** instalar Dia 0.97.2 desde dia-installer.de (la versión de Windows de 32 bits, en la ruta que trae por defecto) y espera su visto bueno; luego vuelve al paso 1. Si no lo quiere o no va a estudiar diagramas, deja la carpeta `prueba-dia/` donde está (es del repositorio y no estorba) y no pongas la sección de Dia en su `CLAUDE.md`. Si tiene **otra versión de Dia**, explícale que el panel funcionará sin lo «en vivo» y propón instalar la 0.97.2.

## Paso 5. README de la carpeta

Crea un `README.md` corto con: qué es la carpeta (un tutor de estudio con `CLAUDE.md` y `contexto.md`), qué hace cada archivo (incluido lo que se genera solo, como `panel-excel/__pycache__/`, `herramientas/node_modules/` o, en `prueba-dia/`, `pasos/`, `tutor/`, `mis_diagramas/`, `progreso.json`, `mi_diagrama.dia` y `__pycache__/`), que `contexto.md` se actualiza solo con cada sesión, y las dependencias instaladas. Añade cómo actualizar las herramientas: `git pull` en esta carpeta (si dice que hay cambios locales en archivos del repositorio, no los fuerces: avisa).

## Paso 6. Verificar

Antes de terminar, comprueba y arregla:
- [ ] `CLAUDE.md` y `contexto.md` existen, y `CLAUDE.md` tiene la línea `@contexto.md`.
- [ ] No queda ningún `{{...}}` ni texto de plantilla en ellos (búscalos).
- [ ] No hay datos de otra persona: ningún correo, ruta de usuario ajena ni curso que la persona no haya mencionado.
- [ ] Cada herramienta anotada en `CLAUDE.md` fue probada o está marcada como _pendiente de instalar_.
- [ ] Si se instaló el panel de Excel: los archivos de `panel-excel/` están, `--probar --rapido` terminó con «Revisión automática: todo bien» (o con «Lo básico del panel: todo bien» y cada bloque opcional que falló anotado como _pendiente_ en `CLAUDE.md` y en `contexto.md`) y con «Libro de prueba cerrado sin guardar», y Excel no quedó con libros de la prueba abiertos.
- [ ] Sus temas y cursos (si ya hay alguno) están en carpetas propias en la raíz, no dentro de `panel-excel/`, `prueba-dia/` ni `herramientas/`, y `git status` sale limpio.
- [ ] Si se instaló el panel de Dia: los dos `--probar` de 4.7 terminaron en «todo bien» y su `CLAUDE.md` tiene la sección de Dia.

## Paso 7. Despedirte

1. **No borres este archivo**: es parte del repositorio y `git pull` lo actualiza junto con las herramientas.
2. Comprueba con `git status` que no cambiaste ningún archivo del repositorio (lo de la persona no aparece: el `.gitignore` solo deja ver los archivos del tutor, así que tampoco avisaría de un curso guardado por error dentro de `panel-excel/` o `prueba-dia/`; eso se mira en el paso 6). Si algo del repositorio cambió, déjalo como estaba con su visto bueno (`git checkout -- <archivo>`).
3. Dile, en pocas líneas: qué quedó creado, qué herramientas están listas y cuáles pendientes, que **debe abrir una sesión nueva en esta carpeta** para que el tutor cargue el `CLAUDE.md`, y que para actualizar las herramientas basta `git pull`.
4. Si algún paso falló y la verificación del paso 6 no pasó, explica qué falta para que pueda retomarlo.
