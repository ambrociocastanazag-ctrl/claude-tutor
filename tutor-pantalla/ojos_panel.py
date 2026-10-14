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

Permiso: ojos_capturar() solo guarda la captura en memoria y la enseña en la vista previa; ojos_adjuntar() la pasa a
la lista de adjuntos del mensaje (lo pulsa la persona) y solo sale cuando envía ese mensaje con ella dentro."""
import base64, io, json, os, re, subprocess, sys, threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ojos                                                             # noqa: E402

OVERLAY = AQUI.parent / "prueba-dia" / "overlay_dia.py"                 # las flechas: el mismo de Dia, sin cambios
CAPA = AQUI / "capa.py"                                                 # los dibujos ricos (DIBUJOS.md)
SCRIPTS_UI = ["ojos_ui.js", "preguntas_ui.js", "dibujante.js", "formas_fijas.js", "formas_animadas.js", "formas_formulas.js", "voz.js"]
VENDOR = {"mathjax": "tex-svg.js", "rough": "rough.js"}                 # se cargan cuando hacen falta (dib_recurso)
FORMAS = {"foco", "teclas", "mano", "lupa", "svg", "fantasma", "guia", "secuencia", "formula", "rayos_x", "desarmar"}
CON_OBJETIVO = {"foco", "mano", "lupa", "svg", "guia", "rayos_x"}       # sin objetivo no tienen sentido
CLAVES_OBJETIVO = {"tipo", "id", "caja", "celda", "hoja", "nombre", "hasta"}
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

REGLAS_DIBUJOS = r"""
DIBUJOS: además de las flechas, puedes dibujar ENCIMA de la app (junto a tus otras marcas) con "tipo": "dibujo" y una
"forma". Objetivo como en las demás marcas: "id"/"caja" de la última captura, "celda" en Excel, "nombre" en un curso.
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

PREGUNTAS_RE = re.compile(r"\s*<preguntas>\s*(.*?)\s*(?:</preguntas>|$)", re.S | re.I)
MAX_ADJUNTOS, MAX_MB, MAX_TEXTO = 5, 15, 60000
IMAGENES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


def separar_preguntas(texto):
    """(texto sin el bloque <preguntas>, lista de preguntas válidas para Preguntas.tarjeta). Lo que no se entiende se tira."""
    m = PREGUNTAS_RE.search(texto or "")
    if not m: return texto or "", []
    limpio = (texto[:m.start()] + " " + texto[m.end():]).strip()
    try: datos = json.loads(m.group(1))
    except ValueError: return limpio, []
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
    return limpio, out


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


def separar_pedido(texto):
    """(texto sin <pedir_ventana/>, si el tutor pidió ver una ventana)."""
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


class Ojos:
    """Capturas con permiso y flechas encima de la ventana capturada.
    apps: nombres de ejecutable (sin .exe) que van primero en la lista: las ventanas del curso."""

    def __init__(self, apps=(), panel_hwnd=lambda: None):
        self.apps = {a.lower() for a in apps}
        self.panel_hwnd = panel_hwnd                 # función: la ventana del panel (las flechas van justo debajo)
        self.ov = Overlay()
        self.capa = Overlay(CAPA)                    # los dibujos ricos
        self.aprobadas = set()                       # ventanas que la persona ya enseñó (la lupa solo va en ellas)
        self.capturas = {}                           # id → Captura (en vista previa o adjunta)
        self.pendiente = None                        # id de la que está en vista previa
        self.ultima = None                           # la última que vio el tutor: a ella se refieren las marcas "ventana"
        self.marcas = []                             # las flechas puestas ahora (cajas en píxeles de self.ultima)
        self.n = 0

    # --- lista y captura ---
    def ventanas(self, actual=None):
        vs = ojos.listar_ventanas(excluir_pids=[os.getpid()])
        for v in vs: v["curso"] = v["app"].lower() in self.apps; v["actual"] = v["hwnd"] == actual
        return sorted(vs, key=lambda v: not v["curso"])        # estable: dentro de cada grupo, la más reciente primero

    def capturar(self, hwnd):
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
        self._marco(cap)
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
        b = io.BytesIO(); cap.img.save(b, "PNG"); datos = base64.b64encode(b.getvalue()).decode()
        app = re.sub(r"[^\w-]+", "_", cap.app or "ventana")[:20]
        return {"ok": True, "ojos_id": cid, "nombre": f"{app}_{cid}.png", "tipo": "imagen", "media_type": "image/png",
                "datos": datos, "vista": "data:image/png;base64," + datos, "tam": f"{max(1, len(b.getvalue()) // 1000)} KB",
                "titulo": cap.titulo}

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

    def _poner(self):
        cap = self.ultima
        if not self.marcas or not cap or not ojos.u32.IsWindow(cap.hwnd):
            self.ov.orden({"cmd": "borrar"}); return 0
        c = ojos.cliente(cap.hwnd)
        evitar = [cap.a_pantalla(k["caja"]) for k in cap.controles]
        r = self.ov.orden({"cmd": "mostrar", "pids": [cap.pid, os.getpid()], "panel": self.panel_hwnd(), "marcas": [
            {"hwnd": cap.hwnd, "ventana": list(c), "rect": cap.a_pantalla(m["caja"]), "texto": m["texto"],
             "color": m["color"], "n": m.get("n"), "evitar": evitar} for m in self.marcas]})
        return r.get("dibujadas", 0)

    # --- dibujos ricos (DIBUJOS.md) ---
    def dibujos(self, marcas, resolver=None, ventana=None):
        """Saca de las marcas las "tipo": "dibujo" y arma el lote para la página (DIBUJOS.md §2).
        resolver(m) → {"hwnd", "r": caja de PANTALLA o None, ...campos extra} | None: ubica lo que los ojos no saben
        ("celda" de Excel, "nombre" de un curso); lanza ValueError si no puede. ventana: dónde dibujar lo que no
        tiene objetivo (si no, la de la última captura). Devuelve (las demás marcas, lote o None, avisos)."""
        mias = [m for m in marcas or [] if isinstance(m, dict) and m.get("tipo") == "dibujo"]
        resto = [m for m in marcas or [] if not (isinstance(m, dict) and m.get("tipo") == "dibujo")]
        lote, avisos = [], []
        for m in mias[:MAX_DIBUJOS]:
            try: d = self._dibujo(m, resolver, ventana)
            except ValueError as e: avisos.append(f"«{m.get('forma')}»: {e}"); continue
            except Exception as e: avisos.append(f"«{m.get('forma')}»: {type(e).__name__}: {e}"); continue
            d["id"] = f"d{len(lote) + 1}"; lote.append(d)
        return resto, ({"dibujos": lote} if lote else None), avisos

    def _donde(self, m, resolver, ventana):
        """(hwnd, caja en pantalla o None, campos extra) del objetivo de una marca o de un paso."""
        if resolver:
            r = resolver(m)
            if r: r = dict(r); return r.pop("hwnd", None), r.pop("r", None), r
        cap = self.ultima
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

    def poner_capas(self, capas):
        """Las capas que dibujó la página → capa.py (quita las de antes)."""
        capas = [c for c in capas or [] if isinstance(c, dict) and c.get("hwnd")]
        if not capas: return self.borrar_capas()
        pids = sorted({ojos.pid_de(int(c["hwnd"])) for c in capas} | {os.getpid()})
        return self.capa.orden({"cmd": "poner", "pids": pids, "panel": self.panel_hwnd(), "capas": capas})

    def borrar_capas(self):
        return self.capa.orden({"cmd": "borrar"}) if self.capa.vivo() else {"ok": True}

    def borrar(self):
        self.marcas = []
        self.ov.orden({"cmd": "borrar"})
        self.borrar_capas()

    def cerrar(self):
        self.ov.cerrar(); self.capa.cerrar()


class OjosApi:
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

    # --- dibujos (dibujante.js) ---
    def capa_poner(self, datos):
        return self._ojos.poner_capas((datos or {}).get("capas"))

    def capa_reproducir(self, cid, desde=None, hasta=None):
        if not self._ojos.capa.vivo(): return {"ok": False}
        return self._ojos.capa.orden({"cmd": "reproducir", "id": cid, "desde": desde, "hasta": hasta})

    def capa_borrar(self):
        return self._ojos.borrar_capas()

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
