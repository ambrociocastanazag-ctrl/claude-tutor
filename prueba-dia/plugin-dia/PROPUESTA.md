# Cómo controlar Dia 0.97.2 en vivo: análisis y propuesta

Fecha: 2026-10-08. PC: Windows 11, Dia 0.97.2 (dia-installer.de, 32 bits, español), Python 3.12, MinGW.org gcc 6.3 (32 bits) en `C:\MinGW`.

## 1. Tabla de opciones

| Opción | Cómo funciona | Confirmada aquí | Esfuerzo | En vivo | Otras PCs | Instalar | Riesgos |
|---|---|---|---|---|---|---|---|
| **1. Plugin propio en C** (`dia-tutor.dll`) | Dia carga DLL de plugin de las carpetas de `DIA_LIB_PATH`, de `%USERPROFILE%\.dia\objects` y de su carpeta `dia`. La DLL sondea cada 100 ms un archivo de órdenes y actúa sobre el diagrama abierto con `libdia.dll` (623 funciones) y `dia-app.dll` (43: diagrama activo, cargar, redibujar, seleccionar…). | **Sí.** Compilado y probado: crear clase, seleccionar, sustituir contenido (`cargar`, 0,15 s), acción de menú (abre Propiedades), pulsar botón/pestaña por texto, posiciones en pantalla de menús, herramientas, pestañas y campos (coinciden con la captura). Ctrl+Z después no rompe. Lo guardado se lee bien. Capturas en `capturas/`. | Medio: 2–3 días para la versión completa (más órdenes, overlay, empaquetado). | **Total**: instantáneo, misma ventana, sin parpadeo. | **Alta**: se copia la DLL (60 KB) con el curso; el lanzador fija la variable; sin admin. Exige el mismo Dia 0.97.2 de dia-installer (32 bits). Si es otro Dia, el plugin no carga y Dia sigue; el panel lo nota y pasa al respaldo. | Nada (el compilador ya estaba). | Una orden mal hecha puede cerrar Dia: se mitiga con pocas órdenes, probadas, y nunca sobre el diagrama del alumno sin guardar. Los cambios del plugin no entran en Deshacer. `pluginrc` anota la ruta del plugin. |
| **2. Plugin de Python de 0.97** | El instalador oficial lo ofrecía como componente opcional (`dia-python.dll` + `dia.pyd`) compilado contra **Python 2.3** (`plug-ins/python/makefile.msc`: `python23.lib`). Aquí no está instalado (`uninstall.log` no lo lista). | Parcial: fuentes e instalador leídos; no probado. | Alto e inútil: Python 2.3 (2003) en cada PC, y aun así solo haría lo mismo que la opción 1 (sondear un archivo desde dentro). | Total, en teoría. | Mala. | Python 2.3 32 bits + el componente del instalador en cada PC. | Descartada. |
| **3. `dia-win-remote.exe`** | `dia-win-remote.exe diaw.exe --integrated archivo.dia` busca una ventana `gdkWindowToplevel` de Dia y le «suelta» el archivo (`WM_DROPFILES`): se abre en la instancia que ya corre, como pestaña si es integrada. Si no hay Dia, lo lanza leyendo `App Paths` del registro. Es el manejador de la asociación `.dia` del instalador. | **Sí.** Abrió el segundo archivo en la misma ventana sin proceso nuevo (0,0 s). Llamarlo otra vez con el mismo archivo no hace nada: **no recarga**. `--help` se cuelga porque intenta abrir «--help» como archivo y muestra un cuadro de error. | Nulo. | Parcial: abre, no cambia lo abierto. | Alta (viene con Dia). | Nada. | Elige la primera ventana de Dia que encuentra. |
| **4. Teclado y ratón** | `keybd_event`/`SendInput` con la ventana al frente; mnemónicos Alt+letra; ratón a coordenadas. | **Sí (teclado).** Ctrl+A, Supr, Ctrl+S en 2,8 s y el archivo quedó vacío. Ratón no probado: las coordenadas exactas las da el plugin (`widgets`), así que no hace falta calibrar por capturas. | Medio-alto por la fragilidad. | Media: lento y visible (roba foco y ratón). | Media: depende de idioma y atajos (`menurc` permite fijarlos). | Nada. | Falla si el alumno toca algo a la vez o hay un diálogo abierto; sin forma de comprobar salvo guardar y leer el `.dia`. Solo como respaldo. |
| **5. Dia más nuevo** | 0.97.3 (2014): solo fuentes, sin instalador Windows oficial (dia-installer.de se quedó en 0.97.2-2, 2012). 0.98 (git): GTK3 + meson, Python 3/PyGObject opcional; «Windows build under heavy development». MSYS2 empaqueta un git de 2022, solo 64 bits (ucrt64/clang64), sin Python y con CVE abiertas. | Parcial: solo web. Formato `.dia`: mismo XML, no verificado aquí. | Alto. | Desconocido. | Mala para repartirlo: instalar MSYS2 (cientos de MB), sin instalador, inestable. | MSYS2 + paquete. | Descartada. |
| **6. Recargar o revertir en la misma ventana** | Dia 0.97.2 no tiene «Revertir» (no hay acción en `ui/*.xml`; las cadenas «Revert» de `dia-app.dll` son del deshacer y de capas) y no detecta cambios del archivo. | **Sí, vía plugin**: `cargar` sustituye los objetos de la capa activa por los del archivo. Sin plugin, imposible. | — | Total con plugin. | — | — | — |
| **7. Animación en el panel, Dia solo para practicar** | Lo que hay hoy: SVG en el panel, archivos por paso. | Sí (ya funciona). | Nulo. | Ninguno en Dia. | Alta. | Nada. | No cumple «ver Dia cambiar» ni «dónde se hace». Queda como **respaldo** si el plugin no carga. |

Otras vías vistas y descartadas: módulo GTK inyectado por `GTK_MODULES` (es lo mismo que el plugin pero cargado por GTK, sin ventaja); inyección de DLL en el proceso (lo mismo con más riesgo y antivirus); UI Automation (GTK2 no expone nada, ya comprobado).

## 2. Recomendación

**Plugin en C (opción 1) como motor, `dia-win-remote` (3) para abrir archivos en la misma ventana, y el panel actual (7) como respaldo automático.** Es la única vía realmente en vivo, ya está probada en esta PC, no necesita instalar nada en ninguna máquina (la DLL viaja con el curso) y da las tres cosas que pediste:

- **Ver Dia cambiar:** cada paso de la lección es un `.dia` generado por `dia_uml.escribir` (como hoy) y un `cargar`: el diagrama cambia en 0,15 s en la misma ventana. Para efectos finos (aparece una clase, se resalta algo) hay órdenes directas (`clase`, `seleccionar`).
- **Enseñar dónde:** `widgets` devuelve la posición exacta en pantalla de cada herramienta de la caja (con el tipo de objeto que crea), de cada menú, pestaña, botón y campo de los diálogos. Con eso un overlay transparente (ventana por encima, que deja pasar los clics) dibuja flechas y notas sobre Dia, como las formas en Excel, sin calibrar por capturas y en cualquier PC.
- **Hazlo por mí:** `accion` dispara cualquier acción de menú por nombre (`ObjectsProperties`, `FileSave`, `ViewShowall`…) y `pulsar` pulsa botones o pestañas por su texto, de modo que el alumno ve cómo se hace en los propios diálogos de Dia. Además `accion FileSave` deja al tutor forzar el guardado antes de revisar.

Cuándo no: si el alumno tiene otro Dia (otra compilación o 64 bits), el plugin no carga; el cliente lo detecta en el `ping` y el panel vuelve al modo de hoy.

## 3. Plan por fases

**Fase 0 (hecha): prototipo.** `python prueba-dia/plugin-dia/demo.py` abre Dia y en un minuto muestra la clase apareciendo, atributos, visibilidad, métodos, resaltado, Propiedades en la pestaña Atributos, posiciones del botón «Nuevo» y de la herramienta «Clase», y crea otra clase. Código y cliente en `plugin-dia/`.

**Fase 1 (medio día): clase en vivo en el panel.** `panel_dia.py` lanza Dia con el plugin (`tutor_dia.Dia`), cada paso hace `cargar` en vez de abrir ventana, `seleccionar` para señalar, y si el `ping` falla usa el modo actual. El diagrama del alumno se abre como pestaña en la misma ventana (`dia-win-remote` o `accion`/`diagram_load`).
Decisiones: (a) ¿misma ventana con pestañas, lección y «mi diagrama», o dos ventanas? Recomiendo pestañas. (b) ¿El plugin vive en la carpeta del curso con `DIA_LIB_PATH` (recomendado) o se copia a `~/.dia/objects`?

**Fase 2 (1 día): «En Dia: dónde» y «hazlo por mí».** Overlay transparente con flechas y notas sobre las coordenadas de `widgets` (con una comprobación de escala: comparar el rectángulo de la ventana que da Windows con el que da GTK; aquí coinciden al 125 %). Órdenes nuevas para atributos y métodos sobre el diagrama del alumno (o, mejor, hacerlo con `accion ObjectsProperties` + `pulsar` para que lo vea en el diálogo). El tutor (Claude) recibe las posiciones y decide dónde apuntar. **Hecha (2026-10-08, versión 5 del plugin):** decisión (c) = la ventana Win32 en capas, en un proceso aparte (`../overlay_dia.py`), con lo que señala cada paso declarado en la lección (`interfaz`) y «Hazlo por mí» con `accion` + `pulsar` + la orden nueva `hoja` (ver `../README.md`). La escala se comprobó: aquí Windows y GTK dan el mismo rectángulo (Dia es consciente de la escala); el overlay calcula la proporción de todos modos.
Decisiones: (c) tecnología del overlay: ventana tkinter/Win32 en capas (click-through, recomendado) o pywebview; (d) ¿las marcas sobre el diagrama siguen en el panel (como hoy) o se dibujan dentro de Dia en una capa «tutor» con objetos Standard (líneas y texto), que `cargar` puede poner y quitar? **Decidido y hecho (2026-10-08): en los dos sitios**, con las órdenes `recuadro`, `flecha`, `nota`, `borrar_marcas` y `cajas` (ver README).

**Fase 3 (medio día): repartirlo.** Carpeta del curso con `dia-tutor.dll`, comprobación de la versión de Dia (tamaño o hash de `libdia.dll` y `dia-app.dll`) antes de cargar, pasos en `INSTALAR_TUTOR.md`, prueba en una PC limpia con Dia recién instalado.
Decisión: (e) ¿fijamos «Dia 0.97.2 de dia-installer.de» como requisito del curso? Es lo que hay en casi todas las PCs con Dia en Windows.

**Fase 4 (opcional): generalizar.** Mismo motor de clase para Excel y Dia (lección JSON, pasos, revisión, tutor), con un adaptador por app.

## 4. Lo que no pude comprobar

- Que no exista instalador Windows de 0.97.3 ni de 0.98: solo por web (dia-installer.de no respondió por SSL; la lista de correo y MSYS2 sí).
- Que 0.98 lea y escriba el mismo `.dia`: por conocimiento del formato, no probado.
- La carga desde `~/.dia/objects`: está en el código (`dia_config_filename("objects")`), no la probé para no tocar tu configuración.
- El comportamiento en otra PC (otra escala de pantalla, otro idioma de Dia).

## 5. Lo que tocó la investigación

- Nada en `Program Files`. Nada instalado. Descargas solo en la carpeta temporal de la sesión (fuentes de Dia 5,5 MB, GTK 2.24 25 MB, libxml2 1,3 MB); `compilar.py` las vuelve a bajar a `%LOCALAPPDATA%\dia-tutor-sdk` cuando haga falta.
- Dia se abrió seis veces con archivos míos y se cerró cada vez. Al salir, Dia anotó el plugin de prueba en `%USERPROFILE%\.dia\pluginrc`; borré esa entrada. Si abres Dia con el plugin volverá a aparecer: es inofensiva.
