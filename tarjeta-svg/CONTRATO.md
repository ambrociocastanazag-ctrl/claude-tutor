# Contrato de la Tarjeta SVG (2026-10-18)

Lo que cada pieza promete a las demás. Nadie cambia una firma sin avisar al orquestador. El diseño de Claude Design llegará después: la interfaz de ahora es **provisional**, y todo lo visual pasa por `Figuras.estilo` y por la clase de cada pestaña, para poder cambiarlo sin tocar la lógica.

## Dueños

| Quién | Archivos |
|---|---|
| **Orquestador (Opus)** | `tarjeta-svg/tarjeta.py` (ventana, estados, atajo, portapapeles, servidor local), `tarjeta-svg/abrir_tarjeta.py`, `tarjeta-svg/tarjeta.html` (cáscara provisional), este contrato, `README.md`, y `tutor-pantalla/ojos_panel.py` |
| **Sonnet A · motor** | `tutor-pantalla/motor_figuras.js` (nuevo, común), `tutor-pantalla/probar_figuras.js`, `tutor-pantalla/ilustraciones_ui.js` (pasa a usar el motor y añade ` ```geometria ` y «Editar en la tarjeta»), `tutor-pantalla/probar_ilustraciones.js`, `tarjeta-svg/pestana_grafica.js`, `tarjeta-svg/pestana_geometria.js` |
| **Sonnet B · escribir** | `tarjeta-svg/vendor/mathlive/` (MathLive 0.110.0 guardado, con sus fuentes y licencia), `tarjeta-svg/atajos.js`, `tarjeta-svg/pestana_escribir.js` |
| **Sonnet C · asistente y accesos** | `tarjeta-svg/asistente_tarjeta.py`, `tarjeta-svg/pestana_asistente.js`, `mis-clases/servidor.py` (solo la herramienta nueva), y el botón «Tarjeta» en `tutor-pantalla/panel.html` y `panel-excel/panel.html` |

MathStudio (su carpeta va en `tarjeta-svg/config.json`) **no se toca**: solo se lee para copiar ideas y atajos.

## 1. Motor de figuras (`tutor-pantalla/motor_figuras.js`, JS puro, también en node)

```js
Figuras.estilo                          // tokens por tema: {claro: {...}, oscuro: {...}} (los reemplazará el diseño)
Figuras.compilar(expr)                  // → f(x) (el intérprete seguro que hoy está en ilustraciones_ui.js; sin eval)
Figuras.grafica(spec, {tema, tam})      // → {svg, w, h} | lanza Error con mensaje en español
Figuras.geometria(guion, {tema, tam})   // → {svg, w, h, errores: [{linea, mensaje}], objetos: [...]}  (con errores igual dibuja lo válido)
Figuras.plano({x, y, ...}, {tema, tam}) // → {svg, w, h}: solo el plano cartesiano (ejes, rejilla, números)
```

- **`spec` de gráfica:** el mismo de `REGLAS_ILUSTRACIONES` (`titulo`, `x`, `y`, `funciones[{f, nombre, color}]`, `area{f, g, x, color}`, `puntos`). Con `y` omitido, el rango sale solo.
- **Guion de geometría:** el lenguaje de MathStudio (ver su `DOCUMENTACION_PROYECTO.md`, §8, y `js/geo-comandos.js`).
  - **Mismos nombres, alias con tilde y en inglés, anidación y atajo `AB`:** el mismo guion tiene que poder pegarse en MathStudio.
  - **Mínimo obligatorio:** punto `A=(x,y)`, `segmento`, `recta`, `semirrecta`, `circunferencia` (centro y radio, centro y punto, tres puntos), `poligono`, `triangulo`, `arco`, `sector`, `puntomedio`, `interseccion` (recta–recta; recta o circunferencia con circunferencia, con índice 1|2), `paralela`, `perpendicular`, `mediatriz`, `bisectriz`, `altura`, `mediana`, `tan(P,c,i)`, `distancia`, `angulo`, `area`, `perimetro`, `marcaigual`, `marcaangulo`, `angulorecto`, `marcaparalela`, `etiqueta`.
  - **Lo que no sepa hacer:** devuelve el error «esto, en MathStudio» en esa línea, nunca un dibujo equivocado.
- **El SVG que sale:**
  - `width`/`height` en px y `viewBox` con margen (la lección de MathStudio: nunca la tinta pegada al borde);
  - fondo transparente o blanco según `{fondo}`;
  - letra `'Segoe UI', system-ui`;
  - sin `<script>` ni enlaces;
  - debe verse igual pegado en Miro.
- `tam`: `"S" | "M" | "L"` (por ejemplo 320, 480 y 720 px de ancho).

## 2. La cáscara y las pestañas (`tarjeta.html` + `pestana_*.js`)

Cada pestaña se registra así, y la cáscara pone las pestañas, la barra de acciones y el estado:

```js
Tarjeta.registrar(id, {titulo, icono,                 // id: 'escribir' | 'grafica' | 'geometria' | 'asistente'
  montar(contenedor),                                  // dibuja su interfaz dentro de contenedor (una sola vez)
  figura() → {svg, nombre} | null,                     // lo que se copia o arrastra ahora (null: nada que copiar),
                                                       // SIEMPRE con el estilo Tarjeta.temaFigura ('claro': Miro es blanco)
  cargar(contenido),                                   // pone algo que llega de fuera (del asistente o de un tutor)
  estado() → objeto, restaurar(objeto)})               // para recordar lo escrito entre sesiones
Tarjeta.cambio()                                       // la pestaña avisa que su figura cambió (miniatura y botones)
Tarjeta.ir(id, contenido?)                             // cambia de pestaña (y le pasa contenido)
Tarjeta.aviso(texto)                                   // la confirmación breve («Copiado»)
Tarjeta.tema                                           // 'claro' | 'oscuro'
```

`contenido` de `cargar` / `Tarjeta.ir`: `{tipo: 'grafica', spec}`, `{tipo: 'geometria', guion}`, `{tipo: 'latex', latex}`, `{tipo: 'svg', svg}` o (2026-10-19) `{tipo: '3d', spec, vista}` (una figura 3D del chat sin guion: va a Geometría, girable, con el aviso «viene del chat»).

**Figuras girables (3D, 2026-10-19; contrato en `tutor-pantalla/CONTRATO-3D.md` §5):**
- Una pestaña puede devolver en `figura(tema)` (solo con tema, el de enseñarla) un campo `vivo(lienzo)`: la cáscara no escribe el SVG, le da el lienzo y la pestaña dibuja y gira ahí (`Figuras3D.girable`). Debe ser idempotente (la cáscara lo llama en cada `cambio()`). Sin tema, `figura()` es lo que se copia: la vista actual, encuadre justo, estilo claro.
- Una pestaña con `vivo` puede traer `soltar()`: la cáscara la llama al mostrar otra cosa (quita los eventos de giro).
- Con `vivo`: el arrastre del lienzo gira (se saca la figura por «Arrastra la figura»), ↗ MathStudio se apaga con el título «MathStudio no tiene 3D» y las medidas son las de lo que se copia.
- **Anotaciones, relleno y GIF (segunda tanda):** la cáscara tiene `Tarjeta.opciones = {tam, fondo, anot: {ejes, numeros, nombres, medidas} (booleanos, true por defecto), relleno: 'auto'|'opaco'|'transparente'}`, se guarda en `estado.json` con `opc`. Con `vivo` y una pestaña con `fotogramas(giro)` (`'vaiven'|'vuelta'` → `Promise<{fotos, ms, w, h}>`, con tamaño, fondo, anotaciones y relleno de `Tarjeta.opciones`, estilo claro y la vista actual) la cáscara enseña la fila de chips y el botón GIF; sin ellas, los oculta o apaga. La pestaña pasa a `Figuras3D` solo lo que apaga (`anotaciones: {ejes:false…}`) o fuerza (`relleno`) y rehace con `girable.cambiar(...)` si solo cambian esas opciones.
- Geometría: `estado()` → `{guion, vista}` (`vista` es la que giró la persona, o null); una `vista(az, el)` nueva en el guion manda sobre la girada.

## 3. Python de la ventana (`tarjeta.py`, la API que llama la página)

- `copiar_svg(svg, nombre)` pone a la vez varios formatos en el portapapeles de Windows:
  - el archivo `.svg` temporal (CF_HDROP: Miro lo sube como imagen vectorial al pegar);
  - `image/svg+xml`;
  - el texto;
  - PNG.
- `copiar_png(b64)`.
- `copiar_gif(fotos, ms, nombre)` → `{ok, ruta, kb}`: `gif3d.guardar_y_copiar` (`tutor-pantalla/gif3d.py`): GIF en Descargas y copiado como archivo.
- `abrir_mathstudio(guion?)`: arranca su servidor en el puerto 8000 si no está y abre el navegador.
- `guardar_estado(obj)` / `leer_estado()`: en `tarjeta-svg/estado.json`, que es suyo y no va al repo.
- `plegar()` / `desplegar()`.
- **El asistente:** `asistente_preguntar(texto, contexto)`, que va a `asistente_tarjeta.py` y responde a trozos con `window.Tarjeta.trozo(t)`; y `asistente_reiniciar()`.

## 4. Servidor local y abrir desde fuera (`abrir_tarjeta.py`)

- **La página no se carga como HTML suelto:** `tarjeta.py` la sirve en `http://127.0.0.1:4748/tarjeta-svg/tarjeta.html`, con los estáticos de `tarjeta-svg/` y `tutor-pantalla/` desde la raíz de Cursos (`/tutor-pantalla/motor_figuras.js`, `/tarjeta-svg/vendor/mathlive/...`). Solo escucha en 127.0.0.1.
- **El asistente:** `asistente_tarjeta.Asistente()` con `.preguntar(texto, contexto, al_trozo)` → texto completo, más `.reiniciar()` y `.cerrar()`.
- `tarjeta.py` escucha en `127.0.0.1:4748`:
  - `GET /hola` → `{ok}`;
  - `POST /mostrar` → la despliega al frente;
  - `POST /figura {contenido}` → `Tarjeta.ir(...)` y la despliega.
- Un solo ejemplar: si el puerto ya responde, no se abre otra.
- `python tarjeta-svg/abrir_tarjeta.py [--figura '<json contenido>']`: si la tarjeta vive, le manda la orden; si no, la arranca suelta (sin consola) y luego se la manda. **Todos los accesos usan esto:**
  - «Mis clases», como herramienta `tarjeta`;
  - el botón de los paneles: `api.tarjeta_abrir(contenido?)` en `OjosApi`, que lo pone el orquestador;
  - «Editar en la tarjeta» de cada figura del chat.

## 5. El asistente de la tarjeta (`asistente_tarjeta.py`)

- Usa `tutor-pantalla/asistente.Sesion` con sus propias reglas: responde muy corto y **siempre con la figura en bloques** (` ```grafica {json} `, ` ```geometria ` con un guion del lenguaje de §1, `$$…$$`, o ` ```svg ` solo si nada de lo anterior sirve), y la tarjeta los dibuja exactos.
- Recibe como contexto la pestaña activa y lo que hay en ella, para poder «retocar esto».
- Herramientas: solo WebSearch y WebFetch, como el asistente.

## Verificación

- **Haiku:** cada Sonnet lanza un solo Haiku, sin contexto, que revisa **capturas**, y lo reutiliza con SendMessage. El informe dice qué miró.
- **Ventanas:** las pruebas en vivo, solo con ventanas propias; nunca la pantalla entera ni ventanas o archivos del usuario. MathStudio no se modifica.
- **Pruebas mínimas:**
  - `node tutor-pantalla/probar_figuras.js` (incluye guiones de MathStudio de su documentación);
  - `node tutor-pantalla/probar_ilustraciones.js`;
  - `python tarjeta-svg/tarjeta.py --probar`.
