# Plugin «Tutor» para Dia 0.97.2 (prototipo)

Una DLL de unos 100 KB que Dia carga al arrancar y que recibe órdenes desde Python mientras la ventana está abierta: añadir objetos de cualquier tipo y sus líneas (y cambiarlos o quitarlos, con Ctrl+Z de Dia), cambiar cualquier propiedad, medir y exportar el dibujo, abrir y cerrar pestañas, crear una clase, sustituir el diagrama por el de un archivo, resaltar un objeto, abrir el diálogo de Propiedades, pulsar un botón o una pestaña por su texto, decir **dónde está en pantalla** cada botón, menú o campo, **dibujar las marcas del tutor** (recuadros, flechas y notas de color) en una capa propia encima del diagrama y, desde la versión 5, dar el HWND de cada ventana, decir dónde se ve cada objeto del diagrama en la pantalla y cambiar la hoja de la caja de herramientas (para las flechas del panel encima de Dia y «Hazlo por mí»). Es la base de la «clase en vivo» de los cursos de Dia (`../README.md`).

## Archivos

- `dia-tutor.c`: el plugin. Las órdenes están documentadas en la cabecera.
- `dia-tutor.dll`: **se genera** con `compilar.py`. Es la que se copia a otras PCs (necesitan el mismo Dia 0.97.2 de dia-installer.de, 32 bits).
- `compilar.py`: compila con `C:\MinGW\bin\gcc.exe`. La primera vez descarga a `%LOCALAPPDATA%\dia-tutor-sdk` las cabeceras de Dia 0.97.2, GTK 2.24.10 y libxml2 (≈45 MB). Enlaza directamente contra `libdia.dll` y `dia-app.dll` del Dia instalado.
- `catalogo.py`: genera `../catalogo_dia.json` con un Dia aparte (órdenes `tipos`, `plantilla`, `propiedades`). Tarda unos 4 minutos.
- `tutor_dia.py`: cliente Python (`Dia().abrir()`, `.orden()`, `.widgets()`, `.buscar()`). La respuesta de `widgets` con sus ventanas y HWND la lee `../interfaz_dia.py` (`leer_widgets`). Las marcas del tutor del panel se traducen a órdenes en `../dia_uml.py` (`ordenes_marcas`, `cajas_de_plugin`); lo que el tutor crea o cambia, en `../cambios_dia.py` (`Cambios.aplicar` / `deshacer`).

## Cómo cambiarlo

1. Editar `dia-tutor.c` (añadir una orden = una función `cmd_…` y una rama en `ejecutar_linea`).
2. `python compilar.py` (cierra antes cualquier Dia que tenga cargado el plugin: Windows no deja sobrescribir una DLL en uso).
3. Probar con `tutor_dia.Dia` en un intérprete. El plugin escribe un `log.txt` en la carpeta de órdenes.
4. Si una orden rompe Dia, el fallo aparece como cierre de la ventana: probar siempre con un diagrama de prueba, nunca con el del alumno.

## Dependencias

Dia 0.97.2 (dia-installer.de) en `C:\Program Files (x86)\Dia`. Python 3 con `pywin32` (solo para el panel). Para **recompilar**: MinGW.org gcc 6.3 en `C:\MinGW` y conexión para la descarga inicial de cabeceras.
