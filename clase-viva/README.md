# Clase viva (`clase-viva/`)

Una guía de estudio (la misma que se publica como artifact) abierta **en una ventana de la PC**, con el tutor de los paneles pegado a su derecha. El tutor lee la clase por dentro, la señala y la dibuja encima, y **mueve sus deslizadores** para enseñar. Es la versión «solo local» de la regla «¿Artifact o solo local?» de `CLAUDE.md`.

```
python clase-viva/clase_viva.py <carpeta de la guía>             abre la clase y su tutor
python clase-viva/clase_viva.py <carpeta de la guía> --probar    sin IA: módulos, mapa, ubicación, manos, cambios y comportamientos
python clase-viva/clase_viva.py <carpeta de la guía> --probar --ver=m03   además imprime lo que le llega al tutor en m03
```

La guía tiene que ser del molde de las guías del tutor: `index.html` armado por `build.py` desde `fuente/` (`base.html`, `nucleo.js` con `FUNC`, `TIPOS_WIDGET`, `iniciarWidget` y `tipografiar`, `modulos/`, `widgets/`) y el tutor de la guía en `const REGLAS` de `inicio.js`.

## Cómo se usa

- **Tres formas del tutor**, a la derecha de la clase y siempre encima de ella (se minimiza con ella y la sigue si la mueves):
  - **abierto**: el chat entero; la clase le deja el hueco. Botón «Plegar» o «—».
  - **pastilla**: una lengüeta en el borde. Con un clic (o con **Ctrl+Espacio** en la clase) se abre la caja; al pasar el ratón no hace nada (lo pidió así).
  - **pregunta**: solo la caja y la última respuesta, flotando sobre la clase. «Abrir el chat» para ver todo; **Esc** la pliega. Si sales con el ratón y no hay nada escrito ni respuesta, se pliega sola.
- **Lo que hace el tutor**: responde corto y señala con flechas, dibuja (todo `tutor-pantalla/DIBUJOS.md`: foco, mano, SVG fijo o animado, fórmulas, 3D…), pone preguntas con botones, lee en voz alta y, con «Ponlo en la clase», pone encima las figuras del chat.
- **Manos de explicación** (sin pedir permiso, porque se pueden devolver): mueve un deslizador a un valor o en un recorrido con una notita en cada parada, y pulsa botones de los interactivos. Al pie de su respuesta queda «Moví «Precio» a 10 → 20 → 38 · **↺ Devolver**». Nunca toca deducciones, quizzes ni el «Tu turno».
- **Dibujar sobre lo que ya existe**: cada gráfica de Plotly sale en el mapa como pieza «gráfica», con sus ejes y el tamaño de su área de datos. Así el tutor dibuja un SVG con las unidades de la gráfica (el punto exacto, el área que sobra, algo que recorre la curva).
- Si te desplazas, las marcas vuelven a su sitio solas; al cambiar de módulo, se borran.

## Cambios del tutor (con tu permiso)

El tutor puede **añadir y cambiar piezas** de la clase. Propone con un bloque `<cambios>[...]</cambios>` y te sale la tarjeta **Aplicar / No**; ya aplicado, **Deshacer**.

| op | qué pone | campos |
|---|---|---|
| `nota` | una nota (estilo `nota`, `recuerda` o `error`) | `texto` |
| `formula` | un recuadro de fórmula | `latex` |
| `ejemplo` | un ejemplo resuelto en pasos | `titulo`, `pasos: [..]` |
| `ejercicio` | un «Tu turno · del tutor» que se revisa solo, sin IA | `enunciado`, `preguntas: [{texto, respuesta, tolerancia?}]`, `pista`, `solucion` |
| `interactivo` | otro interactivo de la guía con otros números | `widget`, `datos` (como el catálogo), `attrs` (sus `data-*`) |
| `texto` | cambia el texto de un párrafo o título | `texto` |
| `ocultar` | oculta una pieza | — |

- Dónde va: `despues` o `antes` con un ref del mapa; `texto` y `ocultar` usan `ref`. Nunca entra dentro de un interactivo, una deducción o un «Tu turno»: va después de él.
- **Números verificados:** los `datos` de un interactivo nuevo pasan por `verificar()` del `build.py` de la guía. Si no cuadran, no se propone y el tutor recibe el motivo.
- **Se guarda aparte:** en `capas/<guía>.json`, que es tuyo y no va al repo. Cada cambio se guarda con su **ancla** (el camino dentro del módulo), no con el ref, porque los refs cambian según lo que tengas abierto. Al abrir la clase vuelven solos, y el chat dice «En esta clase hay N cambios del tutor», cada uno con su «↺ Deshacer». La guía original nunca cambia.
- Las piezas del tutor llevan el sello «✦ del tutor» y un borde de su color. En el mapa salen con `[del tutor]`. Cuando aplicas, deshaces o resuelves uno de sus ejercicios, el tutor lo sabe (`[Del panel]`).
- Código: `PuenteClase.aplicarCambios` y `quitarCambios` en `puente_clase.js`; `_separar_cambios`, `aplicar`, `rechazar`, `deshacer` y `_reponer_capa` en `clase_viva.py`.

## Comportamientos (fase 3)

También van en `<cambios>`, con la misma tarjeta, la capa y el Deshacer.

- **Regla, sin código:** `{"op": "regla", "cuando": {"ref", "valor": {">": 20}}, "entonces": [acciones], "sino": [acciones]}`.
  - `valor` admite `<`, `>`, `<=`, `>=`, `=`, `distinto` o `{"entre": [a, b]}`. Sin `valor`, cada cambio dispara «entonces»; con `"evento": "pulsa"`, cada clic en un botón.
  - Acciones: `nota` (globo junto a la pieza), `resaltar` (lazo a mano), `mostrar`, `ocultar`, `mover`, `pulsar` y `texto` (este, solo en piezas del tutor).
  - En los textos, `{valor}` y `{= 100 - 2*x}` (calcula con el `compilar` de la guía, sin `eval`).
  - Sin `sino`, lo que puso la regla se va cuando deja de cumplirse.
- **Código aislado:** `{"op": "codigo", "despues", "titulo", "alto", "lee": {nombre: ref}, "toca": {nombre: ref}, "js"}`.
  - El JS va en un `<iframe sandbox="allow-scripts">` sin el mismo origen y con CSP `default-src 'none'`: no ve la página, ni su almacenamiento, ni internet.
  - Recibe `raiz` (su `<div>`) y `clase`: `valor`, `al`, `mover`, `nota`, `resaltar`, `mostrar`, `ocultar`, `pulsar`, `quitarNotas`, `reportar`, `tema` y `paleta` (los colores planos; usada como texto da su tinta). También tiene `Profe`.
  - Solo lee lo de `lee` y toca lo de `toca`. Lo demás, el puente lo rechaza y lo avisa en la caja.
  - El código se ve entero en la tarjeta antes de aplicarlo. Si falla, el tutor recibe el error.
- Código: `ponerRegla`, `ponerCaja`, `PUENTE_CAJA` y `quitarComportamientos` en `puente_clase.js`; `_revisar_regla` y `codigo_error` en `clase_viva.py`. `PuenteClase.comportamientos()` da su estado (para las pruebas).

## Cómo funciona

| Pieza | Qué hace |
|---|---|
| `clase_viva.py` | Abre las dos ventanas (pywebview). `Clase` lee la guía (título, módulos y las reglas de su tutor, de `const REGLAS` en `inicio.js`). `TutorClase` es la sesión de Claude (`motor.Tutor` + `capacidades.ConWeb`). `Acople` pega la ventana del tutor a la de la clase (dueña: `GWLP_HWNDPARENT`) y le da el tamaño de cada forma. `ApiTutor` es lo que llama el panel; `ApiPuente`, lo que avisa la clase. |
| `puente_clase.js` | Va **dentro** de la guía (se inyecta al cargar; la guía no cambia). `mapa()` da cada pieza del módulo con un ref estable (`m03-12`: títulos, textos, interactivos, gráficas, controles con su valor, lecturas). `rect(ref)` da su caja en pantalla (una gráfica, solo su área de datos), `encuadrar` desplaza hasta ella y `reservar` deja el hueco al tutor. Las manos: `validar`, `hacer`, `devolver` y `trabajando`. |
| `modo_clase.js` | Se inyecta en `../panel-excel/panel.html` (que no cambia): quita la pestaña Lección, pone la pastilla y la caja de pregunta y el «↺ Devolver». |

- Para el tutor la clase es «la app»: sus marcas van con `"ref"` (flechas `{"tipo": "clase"}`, dibujos `{"tipo": "dibujo"}`, manos `{"tipo": "mover" | "pulsar"}`). `ApiTutor._resolver` las pasa a cajas de pantalla para `ojos_panel.Ojos.dibujos` y `marcador.py`; `"ref"` está en `CLAVES_OBJETIVO` de `ojos_panel.py`.
- Contexto de cada pregunta: el estado (módulo, cuánto bajó, lo último que tocó) y el mapa **solo cuando cambia** (unas 6 000 letras); si no, «igual que antes» y lo que está a la vista.
- El tutor de claude.ai que trae la guía no aparece (no hay `window.claude`), y además el puente lo oculta.
- Lo que la guía guarda (su avance) queda en `.navegador/`, y la última forma del tutor, en `estado.json`. Los dos son de él y no van al repo.

## Dependencias

Las de los paneles: `pywebview` (Edge WebView2), `Pillow` y `pywin32`, más `tutor-pantalla/` y `panel-excel/` (`panel.html`, `motor.py`, `panel_web.py`) y Claude Code (`claude`). Ninguna nueva.
