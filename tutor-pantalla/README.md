# Tutor que mira la pantalla (`tutor-pantalla/`)

Un panel que **mira UNA ventana** de cualquier programa (solo cuando tú lo apruebas) y **señala con flechas encima de ella**. Sirve para apps sin COM ni API, o para cualquier duda en cualquier programa. Solo mira y señala: nunca mueve el ratón ni teclea.

## Cómo se usa

```
python tutor-pantalla/panel_pantalla.py
```

1. **Elegir**: lista de ventanas abiertas con miniatura. Solo esa ventana, nunca toda la pantalla.
2. **Que mire**: la captura aparece en una **vista previa**, con un borde naranja sobre la ventana. Ahí eliges **Enviar al tutor**, **Recortar** (arrastra para mandar solo una parte) o **Cancelar** (no sale nada).
3. El asistente responde en el chat y dibuja flechas numeradas encima del programa. Las flechas dejan pasar los clics, siguen a la ventana y solo se ven con esa app o el panel al frente. **Borrar flechas** las quita.

**Modo puente** (`python tutor-pantalla/panel_pantalla.py --puente`): el mismo panel, pero responde **el chat de Claude Code** que lo abrió. Lo que escribes le llega al chat; la respuesta y las flechas vuelven al panel. Claude Code también puede pedirte una captura, que igual pasa por la vista previa. Cómo lo usa el chat: ver `puente.py`.

Sin captura, también se le puede escribir como a un chat normal. **Investiga:** busca en internet y lee los enlaces que le pegues (WebSearch y WebFetch, solo lectura); mientras tanto el panel dice «Buscando en la web…» o «Leyendo la página…». Los enlaces de sus respuestas se abren en tu navegador.

## ¿Sirve con cualquier programa?

**Ver, sí:** la captura salió bien en todo lo probado (Word, Bloc de notas, Brave, VS Code, Antigravity). Lo que varía es **qué tan exacto apunta**:

| Tipo de app | Botones que lee | Cómo apunta |
|---|---|---|
| Office, Bloc de notas, apps normales de Windows (Win32, WPF, WinForms) | Muchos (Word: 150) | Exacto, por la lista |
| Chrome, Brave, Edge, apps Electron (VS Code, Antigravity, Discord…) | La primera lectura trae 3 y la siguiente unos 90: activan su accesibilidad al pedirla. `capturar()` relee sola si salen menos de 10. | Exacto |
| Apps que dibujan todo ellas mismas: lienzos (Dia, programas de diseño), juegos, figuras de MATLAB, apps Java sin Access Bridge | Pocos o ninguno | Por la imagen: buena en cosas grandes, aproximada en las pequeñas |
| Apps abiertas como administrador | Windows no deja leerlas desde un proceso normal | Habría que abrir el panel también como administrador |

## Alcance (acordado el 2026-10-14)

Un solo núcleo (los «ojos») con cuatro formas de usarlo. Cambia quién responde:

| Modo | Quién responde | Estado |
|---|---|---|
| **1. Asistente** | Una sesión de Claude que abre el panel; sin tarea fija | ✅ Hecho |
| **2. Puente** | El chat de Claude Code: lo que escribes en el panel llega al chat y la respuesta vuelve al panel (con un proceso en segundo plano) | ✅ Hecho |
| **3. Dentro de los tutores** | El tutor de Excel o de Dia, con ojos para lo que COM o el plugin no ven: diálogos, Power Query, el editor de VBA, un PDF. En Dia las marcas siguen dentro de Dia. | Después |
| **4. Curso** | Un tutor nuevo con temario (lecciones en JSON, como Excel y Dia) para enseñar una app sin API | Al final |

El **permiso vive en el núcleo**: ningún modo puede mandar una captura sin la vista previa y el clic en «Enviar al tutor».

## Archivos

| Archivo | Qué es |
|---|---|
| `ojos.py` | El núcleo: lista de ventanas, miniaturas, captura de una ventana (`Captura`: imagen reducida a 1400 px de lado largo, controles en píxeles de la imagen, recorte y conversión a la pantalla). `python ojos.py --lista` / `--capturar "texto" salida.png`. |
| `asistente.py` | La sesión `claude -p` (stream-json, sin MCP ni ajustes, como el tutor de Excel; con solo WebSearch y WebFetch), sus reglas y cómo se leen las marcas (`MARCAS: [...]` al final de la respuesta). |
| `panel_pantalla.py` | El panel (pywebview): la API que llama la página, el proceso de las flechas y la prueba `--probar`. |
| `puente.py` | El modo puente: los dos lados se pasan mensajes por una carpeta temporal (`%TEMP%	utor-pantalla-puente`, se borra al cerrar el panel, capturas incluidas). Desde el chat: `esperar` (en segundo plano: al llegar un mensaje termina y despierta al chat), `responder`, `pedir-captura`, `estado`. |
| `panel.html` | La página: mismo diseño y tema que los paneles de Excel y Dia (el tema sale de `panel-excel/preferencias.json`). |

## Cómo cambiarlo

1. Edita `ojos.py` (captura o controles), `asistente.py` (reglas o formato de marcas) o `panel.html` (la página).
2. Prueba sin panel, con una ventana abierta: `python tutor-pantalla/panel_pantalla.py --probar "Word" salida.png`. Captura, pregunta dónde se guarda el archivo, dibuja las flechas y guarda la captura con ellas. Revisa la imagen.
3. Prueba con el panel abierto: Elegir → Que mire → Enviar, y Cancelar (que no salga nada).

## Dependencias

Python 3.12 con `pywebview` (Edge WebView2), `Pillow` y `uiautomation` (`python -m pip install uiautomation`), Claude Code (`claude`) y `prueba-dia/overlay_dia.py`.
