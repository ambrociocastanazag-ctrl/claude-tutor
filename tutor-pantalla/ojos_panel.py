"""Los «ojos» para cualquier panel (asistente, tutor de Excel, tutor de Dia): elegir una ventana, verla en una vista
previa con permiso, adjuntarla al mensaje y señalar encima de ella.

Cómo se usa en un panel:
  1. ojos = Ojos(apps=["EXCEL"])           (las ventanas de esas apps salen primero en la lista)
     y que la clase de la API herede de OjosApi (con self._ojos = ojos): la página llama ojos_ventanas, ojos_miniatura,
     ojos_capturar, ojos_descartar y ojos_adjuntar.
  2. html = inyectar_ui(html)               (mete ojos_ui.js: la lista con miniaturas y la vista previa)
  3. Al preguntar: ctx += ojos.contexto(adjuntos)  (la lista de controles de cada captura adjunta y viva)
  4. Al responder: marcas = ojos.marcar(marcas)    (las de "tipo": "ventana" se dibujan encima de la ventana
     y se devuelven las demás); texto, pide = separar_pedido(texto)  (<pedir_ventana/> → botón en la página).
  5. Reglas del tutor: + REGLAS_OJOS (+ REGLAS_DIBUJOS). Al cerrar: ojos.cerrar().
  6. Dibujos ricos (DIBUJOS.md): resto, lote, avisos = ojos.dibujos(marcas, resolver) saca las "tipo": "dibujo"; la
     respuesta lleva "dibujos": lote y la página llama Dibujante.mostrar(lote, texto) → api.capa_poner() → capa.py.
  7. Marcas en SVG y Reajustar 🎯 (CONTRATO-MARCAS.md): ojos.poner_js(lambda c: ventana.evaluate_js(c)) para que las
     flechas las dibuje la página (marcador.py); lo que el panel señala por su cuenta (Dia, «Señálamelo» del curso) lo
     registra con ojos.registrar_rehacer(clave, fn) para que el botón 🎯 (OjosApi.reajustar) también lo vuelva a ubicar.

Permiso: ojos_capturar() solo guarda la captura en memoria y la enseña en la vista previa; ojos_adjuntar() la pasa a
la lista de adjuntos del mensaje (lo pulsa la persona) y solo sale cuando envía ese mensaje con ella dentro."""
import base64, io, json, os, re, subprocess, sys, threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ojos, archivos, marcador                                                 # noqa: E402

OVERLAY = AQUI.parent / "prueba-dia" / "overlay_dia.py"                 # las flechas: el mismo de Dia, sin cambios
CAPA = AQUI / "capa.py"                                                 # los dibujos ricos (DIBUJOS.md)
SCRIPTS_UI = ["ojos_ui.js", "preguntas_ui.js", "dibujante.js", "formas_fijas.js", "formas_animadas.js", "formas_formulas.js",
              "marcas.js", "formas_marcas.js", "voz.js", "marcas_ui.js", "senalar_ui.js", "motor_figuras.js", "ilustraciones_ui.js"]
VENDOR = {"mathjax": "tex-svg.js", "rough": "rough.js"}                 # se cargan cuando hacen falta (dib_recurso)
FORMAS = {"foco", "teclas", "mano", "lupa", "svg", "fantasma", "guia", "secuencia", "formula", "rayos_x", "desarmar"}
CON_OBJETIVO = {"foco", "mano", "lupa", "svg", "guia", "rayos_x"}       # sin objetivo no tienen sentido
CLAVES_OBJETIVO = {"tipo", "id", "caja", "celda", "hoja", "nombre", "hasta", "en", "linea", "archivo"}    # "en": objetivo de la interfaz de Dia
MAX_DIBUJOS = 6
MAX_CAPTURAS = 6                                                        # las que se guardan en memoria (adjuntas o en espera)

REGLAS_OJOS = """
VER OTRAS VENTANAS: a veces el estudiante te adjunta, con su permiso, la captura de UNA ventana (un diálogo, un editor, un
mensaje de error, un PDF...) y el [Estado actual] trae la lista de sus controles (id | tipo | nombre | caja x,y,w,h en
píxeles de la captura). Para señalar algo EN ESA VENTANA, añade a tu bloque <marcas> objetos así:
  {"tipo": "ventana", "id": 12, "texto": "Aceptar"}      (o "caja": [x, y, w, h] si el control no está en la lista)
con "texto" de 1 a 4 palabras, "n" si hay orden y "color" opcional (azul, verde, rojo, naranja). Se dibujan como flechas
encima de esa ventana. Lo demás se sigue marcando como siempre.
Si para ayudar necesitas VER algo que no está en tu contexto (un diálogo abierto, un mensaje de error, otra ventana),
pídeselo en una frase y escribe al final <pedir_ventana/>: el panel le dará un botón para enseñártela (él decide). No lo
pidas si no hace falta."""

REGLAS_VOLVER = """
VOLVER A MIRAR LA MISMA VENTANA: si él ya te enseñó una ventana en esta sesión (hay una «Captura adjunta» arriba) y ahora
pregunta algo sobre ESA ventana, y para contestar necesitas ver cómo está AHORA (cambió, hay un error nuevo, un paso que
hizo), no le pidas que la enseñe de nuevo: escribe al final <volver_a_mirar/> (o <volver_a_mirar ventana="parte del
título"/> si fueron varias). Le sale una tarjeta «¿Vuelvo a mirar «título»?» con Sí (captura esa ventana sin vista
previa), No (contestas sin la imagen) y Recortar (elige una zona). Pon antes una frase corta de por qué la necesitas y
nada más: la respuesta con la imagen llega sola cuando él elige. Úsalo UNA sola vez por respuesta, nunca si la pregunta no
tiene que ver con esa ventana, y si dijo que No no insistas: contesta con lo que sabes o di que no la puedes ver. Si
nunca te enseñó esa ventana, usa <pedir_ventana/>."""
REGLAS_OJOS += REGLAS_VOLVER

REGLAS_DIBUJOS = r"""
DIBUJOS: además de las flechas, puedes dibujar ENCIMA de la app (junto a tus otras marcas) con "tipo": "dibujo" y una
"forma". Objetivo como en las demás marcas: "id"/"caja" de la última captura, "celda" en Excel, "nombre" en un curso, "linea": N (y "archivo") en un curso de código.
Comunes: "texto" (1 a 5 palabras), "decir" (frase corta que se lee en voz alta si la voz está encendida), "color".
  {"tipo": "dibujo", "forma": "foco", "id": 12, "texto": "Aquí"}            oscurece todo menos eso
  {"tipo": "dibujo", "forma": "mano", "trazo": "circulo", "id": 12, "texto": "¡Este!"}   trazo de profe: circulo |
        subrayado | flecha | tache | check
  {"tipo": "dibujo", "forma": "teclas", "teclas": ["Ctrl", "S"], "id": 12}  atajo de teclado (objetivo opcional)
  {"tipo": "dibujo", "forma": "lupa", "caja": [x, y, w, h], "aumento": 3}   aumenta algo pequeño (en vivo)
  {"tipo": "dibujo", "forma": "fantasma", "pasos": [{"accion": "clic", "id": 5, "decir": "Primero aquí"},
        {"accion": "arrastrar", "caja": [...], "hasta": {"caja": [...]}}, {"accion": "escribir", "id": 9, "texto": "=SUMA("}]}
        cursor animado que hace los pasos (mover | clic | doble | derecho | arrastrar | escribir)
  {"tipo": "dibujo", "forma": "guia", "figura": "rect", "caja": [...], "texto": "Dibújalo aquí"}   rect | elipse | linea | flecha
  {"tipo": "dibujo", "forma": "secuencia", "pasos": [{"id": 3, "texto": "Inicio"}, {"id": 8, "texto": "Insertar"}]}
  {"tipo": "dibujo", "forma": "formula", "latex": "\frac{a}{b}", "id": 4}  fórmula bien escrita junto al objetivo
  {"tipo": "dibujo", "forma": "desarmar", "original": "=SUMA(B2:B9)/8", "partes": [{"texto": "SUMA(B2:B9)",
        "nota": "suma las ventas"}, {"texto": "/8", "nota": "entre 8 días"}], "id": 4}   explica un texto por partes
  {"tipo": "dibujo", "forma": "svg", "caja": [...], "svg": "<svg viewBox='0 0 100 40'>...</svg>"}   tu propio dibujo
        (solo formas y texto; sin scripts ni imágenes), encajado en la caja. PUEDE IR ANIMADO: <animate>,
        <animateTransform>, <animateMotion> (con <mpath href='#id'/>) o CSS con @keyframes en un <style>; ciclos de
        hasta 6 s y repeatCount='indefinite' para que se repita (p. ej. un punto que recorre una curva, barras que crecen)
En Excel, con "celda": "formula" sin latex escribe la de la celda ("grafica": true añade una mini gráfica de sus
datos), "rayos_x" anima de dónde salen los valores de la fórmula y "desarmar" sin "original" usa su fórmula.
Úsalos cuando aclaren más que una flecha (máximo 2 o 3 por respuesta); para señalar un botón basta la flecha."""

REGLAS_PREGUNTAS = """
PREGUNTAS EN EL CHAT: cuando ayude, en vez de preguntar en texto, añade al final un bloque que el panel convierte en una
tarjeta con botones:
<preguntas>[{"pregunta": "¿Qué hace SUMA(B2:B9)?", "opciones": ["Suma esas celdas", "Las cuenta", "Las promedia"],
  "correcta": 0, "explicacion": "SUMA suma los números del rango."}]</preguntas>
- Opción única: "opciones" (2 a 6, cortas). Con "correcta" (índice desde 0) se corrige al instante y se muestra
  "explicacion" (una frase). Sin "correcta" es una encuesta: para que elija (qué quiere hacer, cómo lo prefiere).
- Varias respuestas: "multiple": true (y "correcta": [0, 2] si la hay).
- Abierta: sin "opciones" (sale una caja de texto), para una respuesta corta, un número o una fórmula.
- "otra": true añade «Otra…» con caja de texto; "no_se": true añade «No sé» (úsalo en diagnósticos).
- Hasta 4 preguntas por bloque. No repitas en tu texto lo que ya dice la tarjeta.
Úsalo para comprobar que entendió (una pregunta corta después de explicar), para un diagnóstico o para que elija entre
caminos; no en cada respuesta. Sus respuestas te llegan en un mensaje que empieza por «Mi respuesta» o «Mis respuestas»:
corrige o sigue desde ahí."""

REGLAS_ILUSTRACIONES = r"""
ILUSTRACIONES EN EL CHAT (se ven dentro de tu respuesta, no encima de la app):
- Fórmulas: $...$ dentro del texto y $$...$$ en su propia línea, en LaTeX. El panel las dibuja bien escritas y él puede
  copiarlas. Fuera de las fórmulas, el texto normal.
- Figura propia: un bloque de código "svg"; lo que sigue a svg en la primera línea es el pie de la figura:
  ```svg Discos apilados bajo y = √x
  <svg viewBox="0 0 320 180">...</svg>
  ```
  Solo formas y texto (sin scripts, imágenes ni enlaces). Colores con NOMBRES para que se vea en claro y en oscuro:
  tinta (texto y ejes), suave (rejilla, guías), fondo, acento, azul, verde, rojo, naranja, morado, amarillo
  (fill="acento", stroke="tinta"). Puede ir animado (<animate>, <animateTransform>, <animateMotion>, @keyframes).
  viewBox de hasta unos 640×400; letra de 12 a 16.
- Gráfica de funciones (exacta, la dibuja el panel; mejor que trazar la curva tú en SVG):
  ```grafica
  {"titulo": "Área bajo √x", "x": [0, 4], "y": [0, 2.5],
   "funciones": [{"f": "sqrt(x)", "nombre": "y = √x", "color": "azul"}],
   "area": {"f": "sqrt(x)", "g": "0", "x": [0, 4], "color": "azul"}, "puntos": [[4, 2, "(4, 2)"]]}
  ```
  f usa x, + - * / ^, sqrt, sin, cos, tan, asin, acos, atan, exp, ln, log, abs, pi, e. "y", "area" y "puntos" son
  opcionales; "g" es la otra curva del área (por defecto el eje x).
- Geometría exacta: un bloque "geometria" con un guion (el lenguaje de MathStudio: un objeto por línea, nombre
  obligatorio, en orden; claves sin tilde):
  ```geometria
  A=(0,0)
  B=(4,0)
  C=(0,3)
  t=triangulo(A,B,C)
  h=altura(A,BC)
  H=interseccion(h,recta(B,C))
  angulorecto(B,A,C)
  ```
  Las notaciones (angulorecto, marcaigual, marcaangulo, marcaparalela, etiqueta) van SIN nombre ni =.
  Comandos: segmento, recta, semirrecta, circunferencia(A,r | A,B | A,B,C), poligono, triangulo, arco(c,A,B),
  sector(c,A,B), puntomedio, interseccion(o1,o2[,1|2]), paralela(P,r), perpendicular(P,r), mediatriz(A,B),
  bisectriz(A,B,C), altura(A,BC), mediana(A,BC), tan(P,c,i) | tan(c1,c2,i), distancia, angulo(A,B,C), area,
  perimetro, marcaigual(AB,n), marcaangulo(A,B,C,n), angulorecto(A,B,C), marcaparalela(AB,n), etiqueta(AB,"texto").
  Cada figura del chat trae «Editar en la tarjeta»: la Tarjeta SVG la abre para retocarla y copiarla a Miro.
Úsalas cuando una figura aclare más que el texto (una forma, una función, un proceso): máximo 1 o 2 por respuesta y
con poco texto alrededor. Para señalar algo de la app sigue usando las marcas y los dibujos encima de ella."""

PREGUNTAS_RE = re.compile(r"\s*<preguntas>\s*(.*?)\s*(?:</preguntas>|$)", re.S | re.I)
MAX_ADJUNTOS, MAX_MB, MAX_TEXTO = 5, 15, 60000
IMAGENES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def validar_dibujos(lista, donde="paso"):
    """Los «dibujos» de un paso de lección (cursos de Excel, Dia y modo curso): se muestran sin IA con «Muéstramelo».
    Devuelve la lista limpia (cada uno con "tipo": "dibujo") o lanza ValueError con el motivo."""
    if not isinstance(lista, list) or not lista: raise ValueError(f"{donde}: «dibujos» es una lista de dibujos [{{\"forma\": ...}}]")
    if len(lista) > MAX_DIBUJOS: raise ValueError(f"{donde}: máximo {MAX_DIBUJOS} dibujos por paso")
    out = []
    for k, m in enumerate(lista, 1):
        if not isinstance(m, dict) or m.get("forma") not in FORMAS:
            raise ValueError(f"{donde}, dibujo {k}: «forma» tiene que ser una de: {', '.join(sorted(FORMAS))}")
        out.append(dict(m, tipo="dibujo"))
    return out


def atajo(ventana, hwnd, accion="window.atajoMirar && window.atajoMirar()"):
    """Ctrl+Alt+M desde cualquier programa: trae el panel al frente y abre «Que mire» (lo mismo que pulsar el botón).
    ventana(): la ventana de pywebview; hwnd(): su HWND. Si otro programa (u otro panel abierto) ya tiene el atajo, no hace
    nada: el panel sigue igual sin él. Devuelve el hilo."""
    def hilo():
        import ctypes
        from ctypes import wintypes as W
        u = ctypes.WinDLL("user32", use_last_error=True)
        MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY, ID = 0x1, 0x2, 0x4000, 0x0312, 0x4D4D
        if not u.RegisterHotKey(None, ID, MOD_ALT | MOD_CONTROL | MOD_NOREPEAT, ord("M")):
            print("Ctrl+Alt+M ya lo usa otro programa o panel: el atajo queda sin activar.", flush=True); return
        msg = W.MSG()
        try:
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message != WM_HOTKEY: continue
                v, h = ventana(), hwnd()
                if v is None: continue
                if h:
                    u.ShowWindow(W.HWND(h), 9 if u.IsIconic(W.HWND(h)) else 5)      # restaurar si está minimizado
                    u.SetForegroundWindow(W.HWND(h))                               # el atajo da permiso para pasar al frente
                try: v.evaluate_js(accion)
                except Exception: pass
        finally:
            u.UnregisterHotKey(None, ID)
    t = threading.Thread(target=hilo, daemon=True); t.start()
    return t


def separar_preguntas(texto):
    """(texto sin el bloque <preguntas>, lista de preguntas válidas para Preguntas.tarjeta). Lo que no se entiende se tira."""
    texto, v = separar_volver(texto)
    if v: _VOLVER_PEND[:] = [v]
    pend = _VOLVER_PEND[:]; _VOLVER_PEND.clear()
    tarjeta = _ACTIVO.tarjeta_volver(pend[0][0]) if pend and _ACTIVO else None      # <volver_a_mirar/> → tarjeta Sí / No / Recortar
    texto, t_arch = archivos.separar(texto)                    # <pedir_archivo ruta="…"/> → tarjeta Sí / No (o se lee solo)
    if t_arch and not tarjeta: tarjeta = t_arch
    m = PREGUNTAS_RE.search(texto or "")
    if not m: return texto or "", [tarjeta] if tarjeta else []
    limpio = (texto[:m.start()] + " " + texto[m.end():]).strip()
    try: datos = json.loads(m.group(1))
    except ValueError: return limpio, [tarjeta] if tarjeta else []
    out = []
    for q in (datos if isinstance(datos, list) else [datos])[:4]:
        if not isinstance(q, dict) or not str(q.get("pregunta") or "").strip(): continue
        ops = [str(o)[:160] for o in (q.get("opciones") or []) if str(o).strip()][:8] if isinstance(q.get("opciones"), list) else []
        d = {"pregunta": str(q["pregunta"])[:400], "opciones": ops, "multiple": bool(q.get("multiple")) and len(ops) > 1,
             "otra": bool(q.get("otra")) and bool(ops), "no_se": bool(q.get("no_se")) and bool(ops),
             "explicacion": str(q.get("explicacion") or "")[:400]}
        corr = q.get("correcta")
        corr = [c for c in (corr if isinstance(corr, list) else [corr]) if isinstance(c, int) and not isinstance(c, bool) and 0 <= c < len(ops)]
        if corr: d["correcta"] = corr if d["multiple"] else corr[0]
        out.append(d)
    return limpio, ([tarjeta] if tarjeta else []) + out


def bloques_adjuntos(adjuntos):
    """Los archivos que manda la página ({"nombre", "tipo": "imagen" | "pdf" | "texto", "media_type", "datos"}) → (bloques
    image/document para Claude, texto de los archivos de texto, nombres). Como motor.mensaje del panel de Excel.
    Lanza ValueError con un mensaje para la persona si algo no se admite."""
    if len(adjuntos or []) > MAX_ADJUNTOS: raise ValueError(f"Máximo {MAX_ADJUNTOS} adjuntos por mensaje.")
    bloques, textos, nombres = [], [], []
    for a in adjuntos or []:
        tipo, nombre, datos = a.get("tipo"), str(a.get("nombre") or "archivo")[:120], a.get("datos") or ""
        if not isinstance(datos, str) or not datos: raise ValueError(f"«{nombre}» llegó vacío.")
        if tipo == "texto":
            textos.append(f"\n\n[Archivo adjunto: {nombre}]\n{datos[:MAX_TEXTO]}"); continue
        if len(datos) * 3 / 4 > MAX_MB * 1024 * 1024: raise ValueError(f"«{nombre}» pesa demasiado (máximo {MAX_MB} MB).")
        if tipo == "imagen" and a.get("media_type") in IMAGENES:
            bloques.append({"type": "image", "source": {"type": "base64", "media_type": a["media_type"], "data": datos}})
        elif tipo == "pdf":
            bloques.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": datos}, "title": nombre})
        else: raise ValueError(f"«{nombre}»: no se admite ese tipo de archivo (solo imágenes, PDF y texto).")
        nombres.append(nombre)
    return bloques, "".join(textos), nombres


PEDIDO_RE = re.compile(r"\s*<pedir_ventana\s*/?>\s*", re.I)
VOLVER_RE = re.compile(r"\s*<volver_a_mirar(?:\s+ventana\s*=\s*[\"\u201c'\u2018]([^\"\u201d'\u2019>]*)[\"\u201d'\u2019])?\s*/?>\s*", re.I)
_ACTIVO = None                       # el Ojos del panel abierto (uno por proceso): a él se refiere <volver_a_mirar/>
_VOLVER_PEND = []                    # lo que separar_pedido sacó del texto y separar_preguntas convierte en tarjeta


def separar_volver(texto):
    """(texto sin <volver_a_mirar/>, [ventana pedida o ""] o None si no hay etiqueta). Solo cuenta la primera: una vez por respuesta."""
    ms = list(VOLVER_RE.finditer(texto or ""))
    if not ms: return texto or "", None
    return VOLVER_RE.sub(" ", texto).strip(), [ms[0].group(1) or ""]


def separar_pedido(texto):
    """(texto sin <pedir_ventana/>, si el tutor pidió ver una ventana). También quita <volver_a_mirar/> y lo deja anotado:
    separar_preguntas (que todos los paneles llaman justo después) lo convierte en la tarjeta «¿Vuelvo a mirar…?»."""
    texto, v = separar_volver(texto)
    if v: _VOLVER_PEND[:] = [v]
    pide = bool(PEDIDO_RE.search(texto or ""))
    return PEDIDO_RE.sub(" ", texto or "").strip() if pide else (texto or ""), pide


def inyectar_ui(html):
    """La página del panel con ojos_ui.js, el dibujante, sus formas y la voz dentro (antes de </body>)."""
    js = "\n".join((AQUI / n).read_text(encoding="utf-8") for n in SCRIPTS_UI if (AQUI / n).exists())
    i = html.rfind("</body>")
    return html[:i] + "<script>\n" + js + "\n</script>\n" + html[i:] if i >= 0 else html + "<script>\n" + js + "\n</script>"


class Overlay:
    """Un proceso de dibujo (overlay_dia.py: las flechas; capa.py: los dibujos), con órdenes JSON por stdin.
    Si falla, el panel sigue sin ellos."""

    def __init__(self, script=OVERLAY):
        self.script = script; self.p = None; self.cerrojo = threading.Lock()

    def vivo(self):
        return self.p is not None and self.p.poll() is None

    def orden(self, o):
        with self.cerrojo:
            try:
                if self.p is None or self.p.poll() is not None:
                    self.p = subprocess.Popen([sys.executable, str(self.script)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                              stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                              creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                    self.p.stdout.readline()                                    # {"listo": true}
                self.p.stdin.write(json.dumps(o) + "\n"); self.p.stdin.flush()
                return json.loads(self.p.stdout.readline() or "{}")
            except (OSError, ValueError) as e:
                self.p = None
                return {"ok": False, "error": str(e)}

    def cerrar(self):
        if self.p and self.p.poll() is None:
            try: self.orden({"cmd": "salir"}); self.p.wait(timeout=3)
            except Exception: self.p.kill()


def tema_detras(cap, caja):
    """"oscuro" si lo que hay alrededor de la caja (en la captura, que ya está en la PC) es oscuro; si no, None."""
    try:
        x, y, w, h = caja; m = 90
        zona = cap.img.crop((max(0, int(x - m)), max(0, int(y - m)), min(cap.img.width, int(x + w + m)), min(cap.img.height, int(y + h + m))))
        if zona.width < 4 or zona.height < 4: return None
        luz = sum(zona.convert("L").resize((24, 24)).getdata()) / 576
        return "oscuro" if luz < 95 else None
    except Exception:
        return None


class Ojos:
    """Capturas con permiso y flechas encima de la ventana capturada.
    apps: nombres de ejecutable (sin .exe) que van primero en la lista: las ventanas del curso."""

    def __init__(self, apps=(), panel_hwnd=lambda: None, raices=(), js=None):
        self.apps = {a.lower() for a in apps}
        self.raices = list(raices)                   # carpetas del curso: con ellas, los objetivos «linea» ubican líneas del editor
        self.avisos_linea = []                       # «Sube/Baja hasta la línea N» de los objetivos «linea» (capacidades.avisos_linea)
        self.panel_hwnd = panel_hwnd                 # función: la ventana del panel (las flechas van justo debajo)
        self.js = js                                 # corre código en la página del panel (poner_js): las flechas en SVG
        self.ov = marcador.Marcador(js=lambda c: self.js(c) if self.js else None)
        self.capa = Overlay(CAPA)                    # los dibujos ricos
        self.aprobadas = set()                       # ventanas que la persona ya enseñó (la lupa solo va en ellas)
        self.capturas = {}                           # id → Captura (en vista previa o adjunta)
        self.pendiente = None                        # id de la que está en vista previa
        self.ultima = None                           # la última que vio el tutor: a ella se refieren las marcas "ventana"
        self.marcas = []                             # las flechas puestas ahora (cajas en píxeles de self.ultima)
        self.n = 0
        self.titulos = {}                            # hwnd → (título, app) de las ventanas aprobadas en esta sesión (la más reciente al final)
        self.volver_tokens = {}                      # token de una tarjeta «¿Vuelvo a mirar…?» → hwnd
        self.rehacer = {}                            # clave → fn() que vuelve a ubicar lo que el panel señaló por su cuenta (🎯)
        self.ult_dibujos = None                      # (marcas, resolver, ventana) de los últimos dibujos: 🎯 los rehace
        self._buscador = None                        # durante un reajuste: ubica las "id"/"caja" de la captura en la ventana de ahora
        self.n_volver = 0
        global _ACTIVO
        _ACTIVO = self

    # --- lista y captura ---
    def ventanas(self, actual=None):
        vs = ojos.listar_ventanas(excluir_pids=[os.getpid()])
        for v in vs: v["curso"] = v["app"].lower() in self.apps; v["actual"] = v["hwnd"] == actual
        return sorted(vs, key=lambda v: not v["curso"])        # estable: dentro de cada grupo, la más reciente primero

    def capturar(self, hwnd, marco=True):
        hwnd = int(hwnd)
        if not ojos.u32.IsWindow(hwnd): return {"ok": False, "error": "Esa ventana ya se cerró: elige otra."}
        try:
            cap = ojos.capturar(hwnd, ignorar_pids=[os.getpid()])
        except (ojos.Tapada, ojos.Minimizada) as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"No se pudo capturar: {e}"}
        self.n += 1; cid = f"v{self.n}"
        self.capturas[cid] = cap; self.pendiente = cid
        while len(self.capturas) > MAX_CAPTURAS: self.capturas.pop(next(iter(self.capturas)))
        if marco: self._marco(cap)
        return {"ok": True, "id": cid, "img": ojos.a_data_url(cap.img, "PNG"), "w": cap.img.width, "h": cap.img.height,
                "titulo": cap.titulo, "app": cap.app, "controles": len(cap.controles), "como": cap.como}

    def _marco(self, cap):
        """Borde naranja alrededor de la ventana mientras está la vista previa: «esta es la que se ve»."""
        c = ojos.cliente(cap.hwnd)
        if not c: return
        x, y, w, h = c
        self.ov.orden({"cmd": "mostrar", "pids": [cap.pid, os.getpid()], "panel": self.panel_hwnd(),
                       "marcas": [{"hwnd": cap.hwnd, "ventana": list(c), "rect": [x + 8, y + 8, w - 16, h - 16], "color": "naranja"}]})

    def descartar(self):
        if self.pendiente: self.capturas.pop(self.pendiente, None)
        self.pendiente = None
        self._poner()                                # vuelven las flechas que hubiera (o nada)
        return {"ok": True}

    def adjuntar(self, recorte=None):
        """La captura de la vista previa pasa a ser un adjunto del mensaje (formato de los adjuntos de la página)."""
        cid, self.pendiente = self.pendiente, None
        cap = self.capturas.get(cid)
        self._poner()
        if cap is None: return {"ok": False, "error": "No hay captura en la vista previa."}
        if recorte: cap.recortar(*recorte)
        self.aprobadas.add(cap.hwnd)
        self.titulos.pop(cap.hwnd, None); self.titulos[cap.hwnd] = (cap.titulo, cap.app)
        b = io.BytesIO(); cap.img.save(b, "PNG"); datos = base64.b64encode(b.getvalue()).decode()
        app = re.sub(r"[^\w-]+", "_", cap.app or "ventana")[:20]
        return {"ok": True, "ojos_id": cid, "nombre": f"{app}_{cid}.png", "tipo": "imagen", "media_type": "image/png",
                "datos": datos, "vista": "data:image/png;base64," + datos, "tam": f"{max(1, len(b.getvalue()) // 1000)} KB",
                "titulo": cap.titulo}

    # --- volver a mirar una ventana ya aprobada (<volver_a_mirar/>) ---
    def tarjeta_volver(self, ventana=""):
        """La «pregunta» especial que la página dibuja como tarjeta Sí / No / Recortar, o None si el tutor no tiene a qué
        volver (nunca se enseñó nada en esta sesión). ventana: parte del título, si pidió una concreta; si no, la última vista."""
        vivas = [h for h in self.titulos if h in self.aprobadas]
        if not vivas: return None
        hwnd = None
        if ventana:
            for h in reversed(vivas):
                if ventana.lower() in self.titulos[h][0].lower() or ventana.lower() in self.titulos[h][1].lower(): hwnd = h; break
        if hwnd is None:
            hwnd = self.ultima.hwnd if self.ultima is not None and self.ultima.hwnd in vivas else vivas[-1]
        existe = bool(ojos.u32.IsWindow(hwnd))
        titulo = (ojos.titulo(hwnd) if existe else "") or self.titulos[hwnd][0]
        self.n_volver += 1; tok = f"r{self.n_volver}"; self.volver_tokens[tok] = hwnd
        return {"pregunta": f"¿Vuelvo a mirar «{titulo}»?", "opciones": [], "volver": {"token": tok, "titulo": titulo, "hwnd": hwnd, "existe": existe}}

    def volver(self, token, modo):
        """Sí → captura esa ventana (ya aprobada) sin vista previa y devuelve el adjunto. Recortar → captura nueva y devuelve lo
        mismo que capturar() (la página abre la vista previa con el recorte activo). Solo ventanas de esta sesión; jamás la pantalla."""
        hwnd = self.volver_tokens.get(token)
        if hwnd is None or hwnd not in self.aprobadas:
            return {"ok": False, "error": "Esa ventana no es una de las que me enseñaste en esta sesión: usa la cámara (📷)."}
        titulo = self.titulos.get(hwnd, ("la ventana",))[0]
        if not ojos.u32.IsWindow(hwnd):
            return {"ok": False, "cerrada": True, "error": f"«{titulo}» ya no está abierta. Si quieres, enséñame otra con la cámara (📷)."}
        if modo == "recortar": return self.capturar(hwnd)
        r = self.capturar(hwnd, marco=False)
        if not r.get("ok"): return r
        a = self.adjuntar()
        if a.get("ok"): a["ventana"] = titulo
        return a

    # --- al preguntar y al responder ---
    def contexto(self, adjuntos):
        """El texto para el tutor sobre las capturas adjuntas (su ventana y sus controles). La última pasa a ser
        la de las marcas "ventana"."""
        partes = []
        for a in adjuntos or []:
            cap = self.capturas.get(a.get("ojos_id") or "")
            if not cap: continue
            self.ultima = cap
            partes.append(f"[Captura adjunta «{a.get('nombre')}»: la ventana «{cap.titulo}» ({cap.app}), "
                          f"{cap.img.width}×{cap.img.height} px]\nControles de esa ventana:\n{cap.texto_controles()}")
        return "\n\n".join(partes)

    def marcar(self, marcas):
        """Dibuja encima de la ventana las marcas "tipo": "ventana" y devuelve (las demás, cuántas dibujó)."""
        mias = [m for m in marcas or [] if isinstance(m, dict) and m.get("tipo") == "ventana"]
        resto = [m for m in marcas or [] if not (isinstance(m, dict) and m.get("tipo") == "ventana")]
        if not mias or not self.ultima: return resto, 0
        import asistente
        ms = asistente.marcas(mias, self.ultima)
        if ms: self.mostrar(ms)
        return resto, len(ms)

    def mostrar(self, ms):
        """Pone estas flechas (cajas en píxeles de self.ultima) en lugar de las de antes."""
        self.marcas = ms
        return self._poner()

    def _poner(self, deslizar=False):
        cap = self.ultima
        vivas = [(i, m) for i, m in enumerate(self.marcas) if not m.get("perdida")]
        if not vivas or not cap or not ojos.u32.IsWindow(cap.hwnd):
            self.ov.orden({"cmd": "borrar"}); return 0
        c = ojos.cliente(cap.hwnd)
        evitar = [cap.a_pantalla(k["caja"]) for k in cap.controles]
        r = self.ov.orden({"cmd": "mostrar", "pids": [cap.pid, os.getpid()], "panel": self.panel_hwnd(), "deslizar": deslizar, "marcas": [
            {"id": f"m{i + 1}", "hwnd": cap.hwnd, "ventana": list(c), "rect": m.get("pantalla") or cap.a_pantalla(m["caja"]),
             "texto": m["texto"], "color": m["color"], "n": m.get("n"), "evitar": evitar, "fuera": m.get("fuera"),
             "tema": tema_detras(cap, m["caja"]), "entrada": not deslizar} for i, m in vivas]})
        return r.get("dibujadas", 0)

    # --- dibujos ricos (DIBUJOS.md) ---
    def dibujos(self, marcas, resolver=None, ventana=None):
        """Saca de las marcas las "tipo": "dibujo" y arma el lote para la página (DIBUJOS.md §2).
        resolver(m) → {"hwnd", "r": caja de PANTALLA o None, ...campos extra} | None: ubica lo que los ojos no saben
        ("celda" de Excel, "nombre" de un curso); lanza ValueError si no puede. ventana: dónde dibujar lo que no
        tiene objetivo (si no, la de la última captura). Devuelve (las demás marcas, lote o None, avisos)."""
        mias = [m for m in marcas or [] if isinstance(m, dict) and m.get("tipo") == "dibujo"]
        resto = [m for m in marcas or [] if not (isinstance(m, dict) and m.get("tipo") == "dibujo")]
        if mias and self._buscador is None: self.ult_dibujos = (json.loads(json.dumps(mias)), resolver, ventana)
        lote, avisos = [], []
        for m in mias[:MAX_DIBUJOS]:
            try: d = self._dibujo(m, resolver, ventana)
            except ValueError as e: avisos.append(f"«{m.get('texto') or m.get('forma')}»: {e}"); continue
            except Exception as e: avisos.append(f"«{m.get('forma')}»: {type(e).__name__}: {e}"); continue
            d["id"] = f"d{len(lote) + 1}"; lote.append(d)
        return resto, ({"dibujos": lote} if lote else None), avisos

    def _donde(self, m, resolver, ventana):
        """(hwnd, caja en pantalla o None, campos extra) del objetivo de una marca o de un paso."""
        if resolver:
            r = resolver(m)
            if r: r = dict(r); return r.pop("hwnd", None), r.pop("r", None), r
        cap = self.ultima
        if m.get("linea") is not None:                      # una línea del editor de código (editor_vscode.py)
            import capacidades
            h, caja, aviso = capacidades.ubicar_linea(m, self.raices, ventana)
            if aviso: self.avisos_linea.append(aviso)
            return h, caja, {}
        if "id" in m or "caja" in m:
            if not cap: raise ValueError("no hay ninguna captura a la que se refiera")
            caja = None
            if "id" in m:
                try: c = cap.control(int(m["id"]))
                except (TypeError, ValueError): c = None
                if c: caja = c["caja"]
            if caja is None and isinstance(m.get("caja"), list) and len(m["caja"]) == 4:
                try: caja = [float(v) for v in m["caja"]]
                except (TypeError, ValueError): caja = None
            if caja is None or caja[2] <= 0 or caja[3] <= 0: raise ValueError("ese control no está en la última captura")
            if self._buscador is not None:                  # 🎯: dónde está AHORA (zoom, scroll, otro tamaño)
                u = self._buscador.ubicar(caja)
                if u["estado"] != "ok": raise ValueError("ya no lo veo" + (f" (quedó más {u['fuera']})" if u.get("fuera") else ""))
                return cap.hwnd, u["pantalla"], {}
            return cap.hwnd, cap.a_pantalla(caja), {}
        if m.get("celda") or m.get("nombre"): raise ValueError(f"no sé ubicar «{m.get('celda') or m.get('nombre')}» aquí")
        h = ventana or (cap.hwnd if cap else None)
        return h, None, {}

    def _dibujo(self, m, resolver, ventana):
        forma = str(m.get("forma") or "")
        if forma not in FORMAS: raise ValueError("esa forma no existe")
        hwnd, caja, extra = self._donde(m, resolver, ventana)
        pasos = []
        for p in (m.get("pasos") or [])[:8]:
            if not isinstance(p, dict): continue
            ph, pc, _ = self._donde(p, resolver, ventana)
            hwnd = hwnd or ph
            q = {k: v for k, v in p.items() if k not in CLAVES_OBJETIVO}; q["_r"] = pc
            if p.get("hasta") is not None:
                h2 = p["hasta"] if isinstance(p["hasta"], dict) else {"caja": p["hasta"]}
                q["_hasta"] = self._donde(h2, resolver, ventana)[1]
            pasos.append(q)
        if not hwnd or not ojos.u32.IsWindow(hwnd): raise ValueError("no hay ventana donde dibujarlo: pídele que te la enseñe")
        cli = ojos.cliente(hwnd)
        a_cli = lambda b: None if b is None else [round(b[0] - cli[0]), round(b[1] - cli[1]), round(b[2]), round(b[3])]
        d = dict(extra)
        for k, v in m.items():                       # lo que escribió el tutor gana, salvo la gráfica ya calculada
            if k in CLAVES_OBJETIVO or (k == "grafica" and isinstance(d.get("grafica"), dict)): continue
            d[k] = v
        for f in d.get("fuentes") or []: f["r"] = a_cli(f.get("r"))
        try: dpi = ojos.u32.GetDpiForWindow(hwnd) or 96
        except Exception: dpi = 96
        d.update(forma=forma, hwnd=hwnd, cliente=[cli[2], cli[3]], escala=round(dpi / 96, 3), r=a_cli(caja),
                 color=m.get("color") if m.get("color") in ("azul", "verde", "rojo", "naranja", "amarillo", "morado") else "azul",
                 texto=str(m.get("texto") or "")[:60], decir=str(m.get("decir") or "")[:300])
        for q in pasos:
            q["r"] = a_cli(q.pop("_r"))
            if "_hasta" in q: q["hasta_r"] = a_cli(q.pop("_hasta"))
        if pasos: d["pasos"] = pasos
        elif forma in ("fantasma", "secuencia"): raise ValueError("le faltan los pasos")
        if forma in CON_OBJETIVO and not d["r"]: raise ValueError("le falta el objetivo (id, caja, celda o nombre)")
        if forma == "lupa":
            if hwnd not in self.aprobadas: raise ValueError("la lupa solo va en una ventana que ya te enseñó con su permiso")
            d["en_vivo"] = True
        cap = self.ultima
        d["evitar"] = [a_cli(b) for b in extra.get("evitar") or []]          # p. ej. las celdas con datos de Excel
        if cap and cap.hwnd == hwnd: d["evitar"] += [a_cli(cap.a_pantalla(c["caja"])) for c in cap.controles[:300]]
        return d

    def poner_capas(self, capas, grupo=None, deslizar=False):
        """Las capas que dibujó la página → capa.py (quita las de antes de ese grupo: "marcas" o "dibujos")."""
        grupo = grupo if grupo == "dibujos" or re.fullmatch(r"marcas[\w-]{0,20}", str(grupo or "")) else "dibujos"
        capas = [c for c in capas or [] if isinstance(c, dict) and c.get("hwnd")]
        if not capas: return self.borrar_capas(grupo)
        pids = sorted({ojos.pid_de(int(c["hwnd"])) for c in capas} | {os.getpid()})
        return self.capa.orden({"cmd": "poner", "grupo": grupo, "deslizar": bool(deslizar), "pids": pids,
                                "panel": self.panel_hwnd(), "capas": capas})

    def borrar_capas(self, grupo=None):
        if not self.capa.vivo(): return {"ok": True}
        return self.capa.orden({"cmd": "borrar", "grupo": grupo} if grupo else {"cmd": "borrar"})

    def borrar(self):
        self.marcas = []; self.rehacer = {}; self.ult_dibujos = None
        self.ov.orden({"cmd": "borrar"})
        self.borrar_capas()

    # --- Reajustar 🎯 (reajustar.py) ---
    def poner_js(self, fn):
        """fn(código) corre código en la página del panel (pywebview: ventana.evaluate_js): las flechas pasan a SVG."""
        self.js = fn

    def registrar_rehacer(self, clave, fn):
        """fn() → {"movidas", "fuera", "perdidas": [textos]}: vuelve a ubicar lo que el panel señaló por su cuenta."""
        self.rehacer[clave] = fn

    def quitar_rehacer(self, clave):
        self.rehacer.pop(clave, None)

    def hay_que_reajustar(self):
        return bool(self.marcas or self.ult_dibujos or self.rehacer)

    def reajustar(self):
        """Vuelve a poner cada marca y cada dibujo donde está ahora lo que señalaba (CONTRATO-MARCAS.md §4)."""
        import reajustar
        movidas, fuera, perdidas = 0, 0, []
        cap = self.ultima
        vivo = cap is not None and bool(ojos.u32.IsWindow(cap.hwnd))
        buscador = reajustar.Buscador(cap) if vivo else None
        if self.marcas and buscador:
            for m in self.marcas:
                u = buscador.ubicar(m["caja"])
                m["perdida"] = u["estado"] == "perdida"; m["fuera"] = u.get("fuera"); m["pantalla"] = u.get("pantalla")
                if u["estado"] == "ok": movidas += 1
                elif u["estado"] == "fuera": fuera += 1
                else: perdidas.append(m["texto"] or "una marca")
            self._poner(deslizar=True)
        elif self.marcas:                                   # la ventana se cerró
            perdidas += [m["texto"] or "una marca" for m in self.marcas]; self.marcas = []; self._poner()
        lote = None
        if self.ult_dibujos:
            mias, resolver, ventana = self.ult_dibujos
            self._buscador = buscador
            try: _, lote, avisos = self.dibujos(json.loads(json.dumps(mias)), resolver, ventana)
            finally: self._buscador = None
            hechos = len((lote or {}).get("dibujos") or [])
            movidas += hechos
            perdidas += [re.sub(r"^«([^»]*)».*", r"\1", a) for a in avisos]          # «el método»: ya no lo veo → el método
            if not lote: self.borrar_capas("dibujos")
        for clave, fn in list(self.rehacer.items()):
            try: r = fn() or {}
            except Exception as e: r = {"perdidas": [f"{clave} ({e})"]}
            movidas += r.get("movidas", 0); fuera += r.get("fuera", 0); perdidas += r.get("perdidas") or []
        partes = []
        if movidas: partes.append(f"reajusté {movidas} marca{'s' if movidas != 1 else ''}")
        if fuera: partes.append("1 quedó fuera de la vista (te dejé una flecha en el borde)" if fuera == 1
                                else f"{fuera} quedaron fuera de la vista (te dejé flechas en el borde)")
        if perdidas: partes.append("no encontré " + ", ".join(f"«{t}»" for t in perdidas[:4]))
        texto = ", ".join(partes) or "no había nada que reajustar"
        tarjeta = self.tarjeta_volver(cap.titulo) if perdidas and vivo and cap.hwnd in self.aprobadas else None
        return {"ok": True, "movidas": movidas, "fuera": fuera, "perdidas": perdidas, "dibujos": lote, "tarjeta": tarjeta,
                "mensaje": texto[0].upper() + texto[1:] + "."}

    def cerrar(self):
        self.ov.cerrar(); self.capa.cerrar()


try:
    from senalar import SenalarApi                  # ✏️ «Señalar»: encerrar algo con el ratón y preguntar (senalar.py)
except Exception:
    class SenalarApi: pass


class OjosApi(SenalarApi):
    """Lo que la página (ojos_ui.js) llama. La API del panel hereda de esta clase y pone self._ojos."""

    def ojos_ventanas(self, actual=None):
        return self._ojos.ventanas(actual)

    def ojos_miniatura(self, hwnd):
        return ojos.miniatura(int(hwnd))

    def ojos_capturar(self, hwnd):
        return self._ojos.capturar(hwnd)

    def ojos_descartar(self):
        return self._ojos.descartar()

    def ojos_adjuntar(self, recorte=None):
        return self._ojos.adjuntar(recorte)

    # --- 📱 fotos del celular (celular.py) ---
    def _cel(self):
        if getattr(self, "_celular_obj", None) is None:
            import celular; self._celular_obj = celular.Celular()
        return self._celular_obj

    def celular_estado(self): return {"configurado": self._cel().configurado}
    def celular_abrir(self): return self._cel().abrir()
    def celular_recoger(self): return self._cel().recoger()

    def archivo_leer(self, token):
        """Tarjeta «¿Dejo que el tutor lea…?» (o lectura sola si es del curso): el archivo como adjunto (archivos.Lector)."""
        return archivos.leer(token)

    def ojos_volver(self, token, modo="si"):
        """Tarjeta «¿Vuelvo a mirar…?»: modo "si" (adjunto sin vista previa) o "recortar" (captura para la vista previa)."""
        return self._ojos.volver(token, modo)

    # --- dibujos (dibujante.js) ---
    def capa_poner(self, datos):
        d = datos or {}
        return self._ojos.poner_capas(d.get("capas"), d.get("grupo"), d.get("deslizar", False))

    def capa_latir(self, cid):
        """El texto enlazado: al pasar el ratón por «Negrita» en la respuesta, su marca late encima de la app."""
        if not self._ojos.capa.vivo(): return {"ok": False}
        return self._ojos.capa.orden({"cmd": "latir", "id": cid})

    def reajustar(self):
        """El botón 🎯: cada marca y dibujo vuelve a donde está ahora lo que señalaba."""
        try: return self._ojos.reajustar()
        except Exception as e: return {"ok": False, "mensaje": f"No pude reajustar: {e}"}

    def hay_que_reajustar(self):
        return self._ojos.hay_que_reajustar()

    def ilustracion_en_app(self, svg):
        """«Ponlo en la app» de una figura del chat (ilustraciones_ui.js): el lote de un dibujo "svg" centrado en la última
        ventana que vio el tutor (la página lo muestra con Dibujante.mostrar)."""
        cap = self._ojos.ultima
        if cap is None or not ojos.u32.IsWindow(cap.hwnd):
            return {"ok": False, "error": "Primero enséñame la ventana con la cámara (📷) para saber dónde ponerla."}
        m = re.search(r'viewBox\s*=\s*["\']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg or "")
        vw, vh = (float(m.group(1)), float(m.group(2))) if m else (320.0, 180.0)
        W, H = cap.img.size
        w = min(W * 0.6, 640 * cap.k, H * 0.6 * vw / max(vh, 1)); h = w * vh / max(vw, 1)
        _, lote, avisos = self._ojos.dibujos([{"tipo": "dibujo", "forma": "svg", "svg": svg, "caja": [(W - w) / 2, (H - h) / 2, w, h]}])
        return {"ok": True, "dibujos": lote} if lote else {"ok": False, "error": "; ".join(avisos) or "No pude ponerla en la app."}

    def tarjeta_abrir(self, contenido=None):
        """El botón «Tarjeta» y «Editar en la tarjeta» de cada figura del chat: abre la Tarjeta SVG (../tarjeta-svg) o la
        trae al frente, con esa figura cargada. En otro hilo: arrancarla tarda unos segundos y el panel no se congela."""
        ruta = AQUI.parent / "tarjeta-svg" / "abrir_tarjeta.py"
        if not ruta.exists(): return {"ok": False, "error": "No encuentro la Tarjeta SVG."}
        def hilo():
            sys.path.insert(0, str(ruta.parent))
            import abrir_tarjeta
            abrir_tarjeta.abrir(contenido if isinstance(contenido, dict) else None)
        threading.Thread(target=hilo, daemon=True).start()
        return {"ok": True}

    def guardar_imagen(self, b64, nombre="figura"):
        """«Guardar PNG» de una figura del chat: en pywebview no hay descargas, así que va a su carpeta Descargas."""
        try:
            datos = base64.b64decode(str(b64).split(",", 1)[-1])
            if not datos.startswith(b"\x89PNG"): return {"ok": False, "error": "No es una imagen PNG."}
            carpeta = Path.home() / "Downloads"; carpeta.mkdir(exist_ok=True)
            base = re.sub(r"[^\w\- ]+", "", str(nombre))[:60].strip() or "figura"
            ruta = carpeta / f"{base}.png"; n = 2
            while ruta.exists(): ruta = carpeta / f"{base} ({n}).png"; n += 1
            ruta.write_bytes(datos)
            return {"ok": True, "ruta": str(ruta)}
        except Exception as e:
            return {"ok": False, "error": f"No pude guardarla: {e}"}

    def capa_reproducir(self, cid, desde=None, hasta=None):
        if not self._ojos.capa.vivo(): return {"ok": False}
        return self._ojos.capa.orden({"cmd": "reproducir", "id": cid, "desde": desde, "hasta": hasta})

    def capa_borrar(self, grupo=None):
        return self._ojos.borrar_capas(grupo)

    def voz_audio(self, texto):
        """Una frase con la voz natural (voz_natural.py, edge-tts) como data URL; ok False → voz.js usa la de Windows."""
        try:
            import voz_natural
            url = voz_natural.audio(texto)
        except Exception:
            url = None
        return {"ok": bool(url), "audio": url}

    def dib_recurso(self, nombre):
        """El código de una librería de vendor/ (MathJax pesa 2 MB: no cabe en la página, se carga al usarla)."""
        f = VENDOR.get(nombre)
        return (AQUI / "vendor" / f).read_text(encoding="utf-8") if f and (AQUI / "vendor" / f).exists() else ""


def resolver_excel(xl, m):
    """Una marca con "celda" en un Excel (COM, solo lectura) → {"hwnd", "r" (pantalla), ...} para Ojos.dibujos.
    rayos_x, formula y desarmar traen además sus datos (panel-excel/rayos_x.py). Sin "celda": None."""
    if not m.get("celda"): return None
    rx = rayos_x()
    if m.get("forma") in ("rayos_x", "formula", "desarmar"):
        d = dict(rx.resolver(xl, m))
    else:
        d = {"r": rx.caja_celda(xl, str(m["celda"]), m.get("hoja"))}
    if not d.get("r") and m.get("forma") != "formula": raise ValueError(f"{m['celda']} no se ve en la pantalla")
    d["hwnd"] = int(xl.Hwnd)
    d["evitar"] = rx.celdas_con_datos(xl)                    # que las tarjetas y notas no tapen los datos
    return d


def rayos_x():
    """panel-excel/rayos_x.py (lo que lee de Excel para los dibujos)."""
    sys.path.insert(0, str(AQUI.parent / "panel-excel"))
    import rayos_x as rx
    return rx


def probar():
    """python ojos_panel.py --probar: lo que no necesita ventanas ni IA (el reparto de marcas, el pedido y el contexto)."""
    ok = lambda c: "✔" if c else "✘"
    malos = 0

    def ver(c, txt):
        nonlocal malos
        malos += not c; print(ok(c), txt)

    t, qs = separar_preguntas('Mira. <preguntas>[{"pregunta": "¿2+2?", "opciones": ["3", "4"], "correcta": 1, "explicacion": "Suma."},'
                              '{"pregunta": "¿Qué prefieres?", "opciones": ["A", "B", "C"], "multiple": true, "correcta": [0, 9]},'
                              '{"pregunta": "Escribe la fórmula", "opciones": "nada"}, {"sin": 1}]</preguntas>')
    ver(t == "Mira." and len(qs) == 3 and qs[0]["correcta"] == 1 and qs[1]["correcta"] == [0] and qs[1]["multiple"]
        and qs[2]["opciones"] == [] and "correcta" not in qs[2], "separar_preguntas: bloque fuera del texto, correcta válida, abierta y lo raro descartado")
    ver(separar_preguntas("Hola <preguntas>[roto") == ("Hola", []), "un bloque roto se quita sin romper la respuesta")
    b, tx, ns = bloques_adjuntos([{"tipo": "imagen", "media_type": "image/png", "datos": "iVBO", "nombre": "a.png"},
                                  {"tipo": "pdf", "datos": "JVBE", "nombre": "b.pdf"}, {"tipo": "texto", "datos": "hola", "nombre": "c.txt"}])
    ver([x["type"] for x in b] == ["image", "document"] and "c.txt" in tx and ns == ["a.png", "b.pdf"], "bloques_adjuntos: imagen, PDF y texto")
    try: bloques_adjuntos([{"tipo": "exe", "datos": "x", "nombre": "v.exe"}]); malo = False
    except ValueError: malo = True
    ver(malo, "un tipo de archivo que no se admite da un aviso claro")
    t, p = separar_pedido("¿Me enseñas el diálogo?\n<pedir_ventana/>")
    ver(p and t == "¿Me enseñas el diálogo?", "separar_pedido quita <pedir_ventana/> y avisa")
    ver(separar_pedido("Sin pedido") == ("Sin pedido", False), "sin pedido, el texto queda igual")

    class CapFalsa:                                   # una Captura sin ventana real
        hwnd, pid, titulo, app, controles = 0, 0, "Formato de celdas", "EXCEL", [{"id": 3, "tipo": "botón", "nombre": "Aceptar", "caja": [10, 20, 30, 40]}]
        img = type("I", (), {"width": 400, "height": 300})()
        def control(self, cid): return next((c for c in self.controles if c["id"] == cid), None)
        def texto_controles(self): return "3 | botón | Aceptar | 10,20,30,40"

    o = Ojos(apps=["EXCEL"]); o.ov.orden = lambda d: {"ok": True}       # sin proceso de flechas
    resto, n = o.marcar([{"tipo": "ventana", "id": 3, "texto": "Aceptar"}, {"tipo": "nota", "celda": "B2"}])
    ver(n == 0 and resto == [{"tipo": "nota", "celda": "B2"}], "sin captura vista, las marcas «ventana» se descartan (no van a la hoja) y las demás siguen")
    o.capturas["v1"] = CapFalsa()
    ctx = o.contexto([{"ojos_id": "v1", "nombre": "EXCEL_v1.png"}, {"nombre": "otra.png"}])
    ver("Formato de celdas" in ctx and "Aceptar" in ctx and o.ultima is o.capturas["v1"], "contexto(): ventana y controles de la captura adjunta; pasa a ser la de las marcas")
    resto, n = o.marcar([{"tipo": "ventana", "id": 3, "texto": "Aceptar", "n": 1}, {"tipo": "nota", "celda": "B2"}, {"tipo": "ventana", "id": 99}])
    ver(n == 1 and resto == [{"tipo": "nota", "celda": "B2"}] and o.marcas[0]["caja"] == [10, 20, 30, 40],
        "marcar(): la «ventana» con id que existe se dibuja; la de id inexistente se descarta; la nota sigue para la hoja")
    ver(o.contexto([{"ojos_id": "v9"}]) == "", "una captura que no está (cancelada o vieja) no añade nada")
    o.pendiente = None; ver(not o.adjuntar()["ok"], "adjuntar() sin vista previa no adjunta nada")
    # dibujos: con una ventana de verdad (el escritorio: cliente en (0, 0)) y una captura falsa encima
    esc = ojos.u32.GetDesktopWindow()
    class CapEsc(CapFalsa):
        hwnd = esc
        def a_pantalla(self, caja): return [caja[0] * 2, caja[1] * 2, caja[2] * 2, caja[3] * 2]     # k = 0.5
    o2 = Ojos(); o2.ov.orden = lambda d: {"ok": True}; o2.ultima = CapEsc()
    resto, lote, av = o2.dibujos([{"tipo": "dibujo", "forma": "foco", "id": 3, "texto": "Aceptar", "color": "rojo"},
                                  {"tipo": "nota", "celda": "B2"}])
    d = lote["dibujos"][0] if lote else {}
    ver(resto == [{"tipo": "nota", "celda": "B2"}] and d.get("forma") == "foco" and d.get("r") == [20, 40, 60, 80]
        and d.get("hwnd") == esc and d.get("color") == "rojo" and d.get("id") == "d1" and d.get("evitar") == [[20, 40, 60, 80]] and not av,
        "dibujos(): el «dibujo» sale del resto con su objetivo en píxeles de cliente, sus datos y lo que debe evitar")
    _, lote, av = o2.dibujos([{"tipo": "dibujo", "forma": "lupa", "caja": [0, 0, 10, 10]}])
    ver(lote is None and av and "permiso" in av[0], "la lupa no va en una ventana que no se aprobó")
    o2.aprobadas.add(esc)
    _, lote, av = o2.dibujos([{"tipo": "dibujo", "forma": "lupa", "caja": [0, 0, 10, 10]}])
    ver(lote and lote["dibujos"][0].get("en_vivo") and not av, "…y sí en una aprobada (en vivo)")
    _, lote, av = o2.dibujos([{"tipo": "dibujo", "forma": "fantasma", "pasos": [{"accion": "clic", "id": 3},
        {"accion": "arrastrar", "caja": [0, 0, 5, 5], "hasta": {"caja": [10, 10, 5, 5]}}]},
        {"tipo": "dibujo", "forma": "rayo_laser", "id": 3}, {"tipo": "dibujo", "forma": "foco", "id": 99}, {"tipo": "dibujo", "forma": "secuencia"}])
    ps = lote["dibujos"][0]["pasos"] if lote else []
    ver(len(ps) == 2 and ps[0]["r"] == [20, 40, 60, 80] and ps[1]["hasta_r"] == [20, 20, 10, 10] and "caja" not in ps[1] and len(av) == 3,
        "pasos con su r (y hasta_r al arrastrar); forma desconocida, id inexistente y secuencia sin pasos → avisos")
    _, lote, av = o2.dibujos([{"tipo": "dibujo", "forma": "rayos_x", "celda": "D5"}],
                             resolver=lambda m: {"hwnd": esc, "r": [100, 50, 60, 20], "valor": "45", "fuentes": [{"ref": "B2", "r": [10, 10, 5, 5]}, {"ref": "H!A1", "r": None}]} if m.get("celda") else None)
    d = lote["dibujos"][0] if lote else {}
    ver(d.get("r") == [100, 50, 60, 20] and d.get("valor") == "45" and d["fuentes"][1]["r"] is None and "celda" not in d and not av,
        "el resolver ubica la «celda» y trae sus datos (fuentes en coordenadas de cliente)")
    _, lote, av = o2.dibujos([{"tipo": "dibujo", "forma": "teclas", "teclas": ["Ctrl", "S"]}], ventana=esc)
    ver(lote and lote["dibujos"][0]["r"] is None and lote["dibujos"][0]["hwnd"] == esc, "sin objetivo, en la ventana dada")
    ver(validar_dibujos([{"forma": "foco", "celda": "B2"}])[0]["tipo"] == "dibujo", "validar_dibujos: los de una lección quedan como «dibujo»")
    try: validar_dibujos([{"forma": "rayo"}], "m1, paso 2"); malo = ""
    except ValueError as e: malo = str(e)
    ver("m1, paso 2, dibujo 1" in malo, "validar_dibujos: una forma que no existe da un error claro con el paso")
    # volver a mirar la misma ventana (<volver_a_mirar/>): etiqueta, tarjeta y permisos
    t, v = separar_volver('Cambió algo. <volver_a_mirar ventana="Bloc"/> <volver_a_mirar/>')
    ver(v == ["Bloc"] and "volver_a_mirar" not in t and t == "Cambió algo.", "separar_volver: quita la etiqueta y solo cuenta la primera (una vez por respuesta)")
    ver(separar_volver("Nada") == ("Nada", None), "sin etiqueta, el texto queda igual")
    o3 = Ojos(); o3.ov.orden = lambda d: {"ok": True}
    t, qs = separar_preguntas("Mira otra vez. <volver_a_mirar/>")
    ver(t == "Mira otra vez." and qs == [], "sin ventana aprobada en la sesión, la etiqueta se quita y no sale tarjeta")
    class CapV(CapFalsa):
        hwnd, titulo = esc, "Documento - Bloc de notas"; app = "notepad"
        def a_pantalla(self, caja): return caja
    o3.aprobadas.add(esc); o3.titulos[esc] = ("Documento - Bloc de notas", "notepad"); o3.ultima = CapV()
    t, pide = separar_pedido("Veo que cambió. <volver_a_mirar/>")
    t, qs = separar_preguntas(t + ' <preguntas>[{"pregunta": "¿Listo?", "opciones": ["Sí", "No"]}]</preguntas>')
    vol = qs[0].get("volver") if qs else None
    ver(t == "Veo que cambió." and len(qs) == 2 and vol and vol["existe"] and vol["hwnd"] == esc and vol["token"] in o3.volver_tokens
        and qs[0]["pregunta"].startswith("¿Vuelvo a mirar «") and qs[1]["pregunta"] == "¿Listo?",
        "separar_pedido + separar_preguntas: la tarjeta «¿Vuelvo a mirar…?» sale primero y las preguntas normales siguen")
    ver(o3.tarjeta_volver("Excel") ["volver"]["hwnd"] == esc, "una ventana pedida por título que no coincide cae en la última aprobada")
    r = o3.volver("r999", "si")
    ver(not r["ok"] and "sesión" in r["error"], "volver(): un token que no existe (o una ventana no aprobada) no captura nada")
    o3.aprobadas.discard(esc)
    ver(not o3.volver(vol["token"], "si")["ok"], "volver(): si la ventana ya no está aprobada, no captura")
    o3.aprobadas.add(esc); o3.titulos[9999999] = ("Cerrada", "x"); o3.aprobadas.add(9999999); o3.volver_tokens["rx"] = 9999999
    r = o3.volver("rx", "si")
    ver(not r["ok"] and r.get("cerrada") and "📷" in r["error"], "volver(): ventana que ya no existe → aviso que ofrece la cámara")
    ver("<volver_a_mirar" in REGLAS_OJOS and "UNA sola vez" in REGLAS_VOLVER, "el prompt compartido trae la regla de volver a mirar")
    ujs = (AQUI / "ojos_ui.js").read_text(encoding="utf-8"); pjs = (AQUI / "preguntas_ui.js").read_text(encoding="utf-8")
    ver("tarjetaVolver" in ujs and "ojos_volver" in ujs and "Recortar" in ujs and "tarjetaVolver" in pjs, "la página trae la tarjeta (ojos_ui.js) y Preguntas.tarjeta la dibuja")
    html = inyectar_ui("<html><body><p>x</p></body></html>")
    ver("window.Ojos" in html and "window.Dibujante" in html and html.index("window.Dibujante") < html.index("</body>"),
        "inyectar_ui mete ojos_ui.js y el dibujante antes de </body>")
    ver(len(html) < 1_500_000, f"la página sigue cabiendo en WebView2 ({len(html) // 1000} KB; MathJax va aparte)")
    print("Ojos: todo bien" if not malos else f"Ojos: {malos} fallo(s)")
    return malos


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    sys.exit(probar() if sys.argv[1:] == ["--probar"] else print(__doc__))
