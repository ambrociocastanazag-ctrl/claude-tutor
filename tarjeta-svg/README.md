# Tarjeta SVG (`tarjeta-svg/`)

Una ventanita para sacar figuras matemáticas en SVG y pegarlas en **Miro** (o donde sea).

- **Plegada:** una pestaña de 44 × 150 px en el borde derecho, siempre encima, con la última figura y «Copiar».
- **Desplegada:** **Ctrl+Alt+L** o un clic la abre en 420 × 560 px; Esc o el mismo atajo la pliegan. La **✕** de arriba la cierra del todo (con ella se va Ctrl+Alt+L); se vuelve a abrir desde «Mis clases» o con el botón «Tarjeta».
- **Pestañas:**
  - **Escribir:** ecuaciones con MathLive y los atajos de MathStudio.
  - **Gráfica:** hasta 3 funciones, rango y área.
  - **Geometría:** un guion en el **mismo lenguaje de MathStudio**, así que se puede pegar allá tal cual. Si el guion es **3D** (un punto `(x, y, z)` o `esfera`, `cubo`, `revolucion`, `superficie`…), la figura pasa sola a 3D y se **gira con el ratón** (ver «3D» abajo).
  - **Asistente:** le pides la figura y la dibuja exacta.
- **Salidas:**
  - **Copiar SVG:** al pegar, Miro recibe el archivo `.svg`.
  - **PNG**.
  - **Arrastrar** la figura.
  - **Tamaño** S/M/L y **fondo** transparente o blanco.
  - Lo que se copia siempre sale en estilo claro: Miro es blanco.
- **Para lo complejo:** el botón ↗ abre MathStudio (la carpeta va en `config.json`) y, si estás en Geometría, deja el guion copiado.

**3D en Geometría:** escribe un guion con un punto de tres coordenadas o un comando de sólido y la figura se vuelve girable: arrastra para girar, doble clic vuelve a la vista inicial. Lo que se copia, el PNG y lo que se arrastra salen de la vista que dejaste (encuadre justo, estilo claro, tamaño S/M/L y fondo como siempre). ↗ MathStudio se apaga en 3D (no tiene 3D). El asistente responde con guiones 3D cuando le piden un sólido, una superficie o una revolución, y «Editar en la tarjeta» del chat trae las figuras ` ```3d `. Ejemplo:

```
A = (0, 0, 0)
c = cubo(A, 2, opacidad=0.4)
e = esfera((3, 1, 1), 1, color=rojo)
R = revolucion(sqrt(x), 0, 4, angulo=300, corte=2)
vista(30, 20)
```

Los comandos están en `tutor-pantalla/CONTRATO-3D.md` §3.

**Con figura 3D, la tarjeta añade (2026-10-19, segunda tanda):**
- **Chips Ejes · Números · Nombres · Medidas** y **Relleno** (Auto = la opacidad de cada objeto → Opaco → Transparente), en una fila bajo la cabecera de la figura. Se recuerdan en `estado.json` y afectan a lo que se ve y a Copiar SVG, PNG y arrastrar (la vista girada no se pierde). Apagar un chip manda sobre el guion; encendido, manda el guion (`ejes(no)` sigue apagando).
- **Botón «GIF»** junto a «Copiar PNG»: menú con **Vaivén** o **Vuelta entera**. Usa el tamaño S/M/L, el fondo (Sin fondo → GIF con transparencia de 1 bit; Blanco → blanco), las anotaciones y el relleno elegidos, estilo claro y la vista actual. Guarda en Descargas y copia el `.gif` como archivo. En 2D queda apagado («El GIF es para figuras 3D») y los chips no aparecen.

**Cómo se abre:**
- desde **«Mis clases»** (pie del menú, «Tarjeta SVG»);
- con el botón **«Tarjeta»** de los paneles (asistente, Excel, Dia, curso);
- con **«Editar en la tarjeta»** de cada figura del chat de los tutores;
- con `python tarjeta-svg/abrir_tarjeta.py`.

Es un solo ejemplar: si ya está abierta, la trae al frente.

**Estado:** funciona, con el diseño de Claude Design (2026-10-18). Ctrl+C copia el SVG y Ctrl+Mayús+C el PNG cuando no estás escribiendo en un campo. Falta que la pruebe pegando en Miro.

## Archivos

| Archivo | Qué es |
|---|---|
| `tarjeta.py` | La ventana (pywebview: plegada o desplegada, siempre encima, Ctrl+Alt+L). Contiene la API de la página (copiar, `copiar_gif`, MathStudio, estado, asistente) y el servidor local `127.0.0.1:4748`. Ese servidor da un solo ejemplar, recibe órdenes de fuera y sirve la página y los estáticos de `tarjeta-svg/` y `tutor-pantalla/`. `--probar`. |
| `abrir_tarjeta.py` | La abre o la trae al frente, y con `--figura '<json>'` le carga una figura. Lo usan «Mis clases» y los paneles. |
| `tarjeta.html` | La ventana con el diseño de Claude Design: pestañas, plegada, figura central con su cabecera (arrastrar, medidas, fondo, S/M/L, MathStudio), la fila de chips 3D (anotaciones y relleno), copiar, el botón GIF con su menú, recordar lo escrito. Carga `motor_3d.js` y deja a una pestaña llevar el lienzo girable (`vivo`). |
| `pestana_escribir.js` · `atajos.js` | Escribir: MathLive con los atajos de MathStudio y la ecuación con MathJax, con la misma holgura del viewBox que MathStudio. |
| `pestana_grafica.js` · `pestana_geometria.js` | Gráfica y Geometría, sobre `tutor-pantalla/motor_figuras.js`; Geometría también hace 3D girable con `tutor-pantalla/motor_3d.js` (resaltado de `color=`, `eje=`… incluido). |
| `asistente_tarjeta.py` · `pestana_asistente.js` | El asistente (`claude -p`, solo WebSearch y WebFetch): responde con bloques que la tarjeta dibuja exactos. `--probar`, `--vivo "pedido"`. |
| `vendor/mathlive/` | MathLive 0.110.0 con sus fuentes y su licencia (MIT). No se edita. |
| `CONTRATO.md` | El contrato entre las piezas. |
| `para-claude-design/` | El encargo del diseño y sus capturas. |
| `estado.json` · `config.json` | Lo que escribió y la carpeta de MathStudio. Suyos; no van al repo. Se generan o se editan a mano (`config.json`). |

## Cómo cambiarlo

- **Probar:**
  - `python tarjeta-svg/tarjeta.py --probar` (deja una figura de prueba en el portapapeles);
  - `python tarjeta-svg/asistente_tarjeta.py --probar`;
  - `node tutor-pantalla/probar_figuras.js` y `node tutor-pantalla/probar_3d.js`;
  - 3D en el navegador sin tocar la tarjeta abierta: sirve la raíz de Cursos con `python -m http.server 4799 --bind 127.0.0.1` y abre `http://127.0.0.1:4799/tarjeta-svg/tarjeta.html` con puppeteer simulando `window.pywebview.api` (`tema`, `leer_estado`, `guardar_estado`, `copiar_svg`, `copiar_png`…); `Tarjeta._plegada(false)` la despliega y `Tarjeta.ir('geometria', {tipo: 'geometria', guion})` carga un guion;
  - con IA: `python tarjeta-svg/asistente_tarjeta.py --vivo "un cono dentro de un cilindro"`.
- **Probar el 3D nuevo (chips y GIF):** con la misma página en el navegador y `pywebview.api` simulado, añade `copiar_gif(fotos, ms, nombre)` que guarde los fotogramas; arma el .gif con `gif3d.hacer_gif(fotos, ms, nombre, carpeta=...)` (en una carpeta tuya, no en Descargas). `python tutor-pantalla/gif3d.py --probar` prueba el GIF sin la página.
- **El diseño:** cuando llegue, se reemplaza `tarjeta.html` y los estilos con prefijo de cada pestaña (`te-`, `tg-`, `tgeo-`, `ta-`) sin tocar la lógica. El estilo de las figuras va en `Figuras.estilo` (`tutor-pantalla/motor_figuras.js`).
- **Dependencias:**
  - `pywebview` y `pywin32` (el portapapeles);
  - MathLive (en `vendor/`);
  - MathJax (`tutor-pantalla/vendor/`).
