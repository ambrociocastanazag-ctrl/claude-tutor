# Tarjeta SVG (`tarjeta-svg/`)

Una ventanita para sacar figuras matemáticas en SVG y pegarlas en **Miro** (o donde sea).

- **Plegada:** una pestaña de 44 × 150 px en el borde derecho, siempre encima, con la última figura y «Copiar».
- **Desplegada:** **Ctrl+Alt+L** o un clic la abre en 420 × 560 px; Esc o el mismo atajo la pliegan. La **✕** de arriba la cierra del todo (con ella se va Ctrl+Alt+L); se vuelve a abrir desde «Mis clases» o con el botón «Tarjeta».
- **Pestañas:**
  - **Escribir:** ecuaciones con MathLive y los atajos de MathStudio.
  - **Gráfica:** hasta 3 funciones, rango y área.
  - **Geometría:** un guion en el **mismo lenguaje de MathStudio**, así que se puede pegar allá tal cual.
  - **Asistente:** le pides la figura y la dibuja exacta.
- **Salidas:**
  - **Copiar SVG:** al pegar, Miro recibe el archivo `.svg`.
  - **PNG**.
  - **Arrastrar** la figura.
  - **Tamaño** S/M/L y **fondo** transparente o blanco.
  - Lo que se copia siempre sale en estilo claro: Miro es blanco.
- **Para lo complejo:** el botón ↗ abre MathStudio (la carpeta va en `config.json`) y, si estás en Geometría, deja el guion copiado.

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
| `tarjeta.py` | La ventana (pywebview: plegada o desplegada, siempre encima, Ctrl+Alt+L). Contiene la API de la página (copiar, MathStudio, estado, asistente) y el servidor local `127.0.0.1:4748`. Ese servidor da un solo ejemplar, recibe órdenes de fuera y sirve la página y los estáticos de `tarjeta-svg/` y `tutor-pantalla/`. `--probar`. |
| `abrir_tarjeta.py` | La abre o la trae al frente, y con `--figura '<json>'` le carga una figura. Lo usan «Mis clases» y los paneles. |
| `tarjeta.html` | La ventana con el diseño de Claude Design: pestañas, plegada, figura central con su cabecera (arrastrar, medidas, fondo, S/M/L, MathStudio), copiar, recordar lo escrito. |
| `pestana_escribir.js` · `atajos.js` | Escribir: MathLive con los atajos de MathStudio y la ecuación con MathJax, con la misma holgura del viewBox que MathStudio. |
| `pestana_grafica.js` · `pestana_geometria.js` | Gráfica y Geometría, sobre `tutor-pantalla/motor_figuras.js`. |
| `asistente_tarjeta.py` · `pestana_asistente.js` | El asistente (`claude -p`, solo WebSearch y WebFetch): responde con bloques que la tarjeta dibuja exactos. `--probar`, `--vivo "pedido"`. |
| `vendor/mathlive/` | MathLive 0.110.0 con sus fuentes y su licencia (MIT). No se edita. |
| `CONTRATO.md` | El contrato entre las piezas. |
| `para-claude-design/` | El encargo del diseño y sus capturas. |
| `estado.json` · `config.json` | Lo que escribió y la carpeta de MathStudio. Suyos; no van al repo. Se generan o se editan a mano (`config.json`). |

## Cómo cambiarlo

- **Probar:**
  - `python tarjeta-svg/tarjeta.py --probar` (deja una figura de prueba en el portapapeles);
  - `python tarjeta-svg/asistente_tarjeta.py --probar`;
  - `node tutor-pantalla/probar_figuras.js`.
- **El diseño:** cuando llegue, se reemplaza `tarjeta.html` y los estilos con prefijo de cada pestaña (`te-`, `tg-`, `tgeo-`, `ta-`) sin tocar la lógica. El estilo de las figuras va en `Figuras.estilo` (`tutor-pantalla/motor_figuras.js`).
- **Dependencias:**
  - `pywebview` y `pywin32` (el portapapeles);
  - MathLive (en `vendor/`);
  - MathJax (`tutor-pantalla/vendor/`).
