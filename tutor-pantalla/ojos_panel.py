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
  5. Reglas del tutor: + REGLAS_OJOS. Al cerrar: ojos.cerrar().

Permiso: ojos_capturar() solo guarda la captura en memoria y la enseña en la vista previa; ojos_adjuntar() la pasa a
la lista de adjuntos del mensaje (lo pulsa la persona) y solo sale cuando envía ese mensaje con ella dentro."""
import base64, io, json, os, re, subprocess, sys, threading
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ojos                                                             # noqa: E402

OVERLAY = AQUI.parent / "prueba-dia" / "overlay_dia.py"                 # las flechas: el mismo de Dia, sin cambios
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

PEDIDO_RE = re.compile(r"\s*<pedir_ventana\s*/?>\s*", re.I)


def separar_pedido(texto):
    """(texto sin <pedir_ventana/>, si el tutor pidió ver una ventana)."""
    pide = bool(PEDIDO_RE.search(texto or ""))
    return PEDIDO_RE.sub(" ", texto or "").strip() if pide else (texto or ""), pide


def inyectar_ui(html):
    """La página del panel con ojos_ui.js dentro (antes de </body>)."""
    js = (AQUI / "ojos_ui.js").read_text(encoding="utf-8")
    i = html.rfind("</body>")
    return html[:i] + "<script>\n" + js + "\n</script>\n" + html[i:] if i >= 0 else html + "<script>\n" + js + "\n</script>"


class Overlay:
    """El proceso de las flechas (overlay_dia.py), con órdenes JSON por stdin. Si falla, el panel sigue sin flechas."""

    def __init__(self):
        self.p = None; self.cerrojo = threading.Lock()

    def orden(self, o):
        with self.cerrojo:
            try:
                if self.p is None or self.p.poll() is not None:
                    self.p = subprocess.Popen([sys.executable, str(OVERLAY)], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
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

    def borrar(self):
        self.marcas = []
        self.ov.orden({"cmd": "borrar"})

    def cerrar(self):
        self.ov.cerrar()


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


def probar():
    """python ojos_panel.py --probar: lo que no necesita ventanas ni IA (el reparto de marcas, el pedido y el contexto)."""
    ok = lambda c: "✔" if c else "✘"
    malos = 0

    def ver(c, txt):
        nonlocal malos
        malos += not c; print(ok(c), txt)

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
    html = inyectar_ui("<html><body><p>x</p></body></html>")
    ver("window.Ojos" in html and html.index("window.Ojos") < html.index("</body>"), "inyectar_ui mete ojos_ui.js antes de </body>")
    print("Ojos: todo bien" if not malos else f"Ojos: {malos} fallo(s)")
    return malos


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    sys.exit(probar() if sys.argv[1:] == ["--probar"] else print(__doc__))
