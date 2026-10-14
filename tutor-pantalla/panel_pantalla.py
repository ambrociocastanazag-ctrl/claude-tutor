"""Panel del asistente que mira UNA ventana (con permiso) y señala encima de ella.

  python panel_pantalla.py                          abre el panel (modo asistente)
  python panel_pantalla.py --probar "Word" [png]    prueba sin ventana: captura la primera ventana con ese texto en
                                                   el título o la app, pregunta dónde se guarda el archivo, dibuja las
                                                   flechas y guarda la captura con ellas (png) para revisarla

Permiso: nada sale de la PC sin pasar por la vista previa. capturar() solo guarda la imagen en memoria y la muestra
en el panel; enviar() es lo único que la manda, y solo lo llama el botón «Enviar al tutor». descartar() la tira.
Las flechas las dibuja ../prueba-dia/overlay_dia.py (el mismo de Dia, sin cambios): ventana transparente encima de
la app, que deja pasar los clics y solo se ve con la app o el panel al frente."""
import json, os, subprocess, sys, threading, time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ojos, asistente                                                  # noqa: E402

OVERLAY = AQUI.parent / "prueba-dia" / "overlay_dia.py"
PREFERENCIAS = AQUI.parent / "panel-excel" / "preferencias.json"         # el tema de los paneles del tutor


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


class Api:
    """Lo que llama la página (window.pywebview.api.*). Los métodos con _ no se ven desde la página."""

    def __init__(self, sesion, overlay):
        self._sesion, self._ov = sesion, overlay
        self._ventana = None            # la ventana de pywebview
        self._hwnd = None               # la ventana elegida
        self._pendiente = None          # captura en vista previa (aún no enviada)
        self._ultima = None             # la última captura que vio el asistente (a ella se refieren las marcas)
        self._marcas = []               # las flechas puestas ahora
        self._mi_hwnd = None

    # --- ventanas ---
    def _panel_hwnd(self):
        """La ventana del panel (para poner las flechas justo debajo de ella y no taparlo)."""
        if not self._mi_hwnd and self._ventana:
            try: self._mi_hwnd = int(self._ventana.native.Handle.ToInt64())      # el Form de WinForms de pywebview
            except Exception: self._mi_hwnd = next(iter(ojos.ventanas_de(os.getpid())), None)
        return self._mi_hwnd

    def ventanas(self):
        return [dict(v, actual=v["hwnd"] == self._hwnd) for v in ojos.listar_ventanas(excluir_pids=[os.getpid()])]

    def miniatura(self, hwnd):
        return ojos.miniatura(int(hwnd))

    def elegir(self, hwnd):
        hwnd = int(hwnd)
        if not ojos.u32.IsWindow(hwnd): return {"ok": False, "error": "Esa ventana ya no existe."}
        if hwnd != self._hwnd: self.borrar_flechas()
        self._hwnd = hwnd
        return {"ok": True, "titulo": ojos.titulo(hwnd), "app": ojos.app_de(ojos.pid_de(hwnd))}

    # --- captura con permiso ---
    def capturar(self):
        if not self._hwnd or not ojos.u32.IsWindow(self._hwnd):
            self._hwnd = None
            return {"ok": False, "error": "Elige primero una ventana (la anterior se cerró)."}
        try:
            cap = ojos.capturar(self._hwnd, ignorar_pids=[os.getpid()])
        except (ojos.Tapada, ojos.Minimizada) as e:
            return {"ok": False, "error": str(e)}
        except Exception as e:
            return {"ok": False, "error": f"No se pudo capturar: {e}"}
        self._pendiente = cap
        self._marco_ventana(cap)
        return {"ok": True, "img": ojos.a_data_url(cap.img, "PNG"), "w": cap.img.width, "h": cap.img.height,
                "titulo": cap.titulo, "app": cap.app, "controles": len(cap.controles), "como": cap.como}

    def _marco_ventana(self, cap):
        """Un borde naranja alrededor de la ventana mientras está la vista previa: «esta es la que se ve»."""
        c = ojos.cliente(cap.hwnd)
        if not c: return
        x, y, w, h = c
        self._ov.orden({"cmd": "mostrar", "pids": [cap.pid, os.getpid()], "panel": self._panel_hwnd(),
                        "marcas": [{"hwnd": cap.hwnd, "ventana": list(c), "rect": [x + 8, y + 8, w - 16, h - 16], "color": "naranja"}]})

    def descartar(self):
        self._pendiente = None
        self._poner(self._marcas)          # vuelven las flechas que hubiera (o nada)
        return {"ok": True}

    def enviar(self, texto, recorte=None):
        """El único camino por el que sale una captura: lo llama el botón «Enviar al tutor» de la vista previa."""
        cap, self._pendiente = self._pendiente, None
        if cap is None: return {"ok": False, "error": "No hay captura en la vista previa."}
        if recorte: cap.recortar(*recorte)
        self._ultima = cap
        texto = (texto or "").strip() or "¿Qué ves? Ayúdame con esto."
        ctx = (f"[Captura de la ventana «{cap.titulo}» ({cap.app}), {cap.img.width}×{cap.img.height} px]\n"
               f"Controles de la ventana:\n{cap.texto_controles()}\n\nPersona: {texto}")
        contenido = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                  "data": ojos.a_data_url(cap.img).split(",", 1)[1]}},
                     {"type": "text", "text": ctx}]
        return self._responder(contenido)

    def preguntar(self, texto):
        texto = (texto or "").strip()
        if not texto: return {"ok": False, "error": "Escribe algo."}
        v = f"(Ventana elegida: «{ojos.titulo(self._hwnd)}»; sin captura nueva.)\n" if self._hwnd and ojos.u32.IsWindow(self._hwnd) else ""
        return self._responder(f"{v}Persona: {texto}")

    def _responder(self, contenido):
        def trozo(t):
            if self._ventana: self._ventana.evaluate_js(f"trozo({json.dumps(t)})")
        def aviso(t):
            if self._ventana: self._ventana.evaluate_js(f"avisoTrabajo({json.dumps(t)})")
        try:
            r = self._sesion.preguntar(contenido, trozo, aviso)
        except Exception as e:
            self._poner(self._marcas)
            return {"ok": False, "error": f"El asistente no respondió: {e}"}
        limpio, lista = asistente.separar(r)
        ms = asistente.marcas(lista, self._ultima) if self._ultima else []
        if ms: self._marcas = ms
        self._poner(self._marcas)
        return {"ok": True, "texto": limpio, "marcas": len(ms)}

    # --- flechas ---
    def _poner(self, ms):
        cap = self._ultima
        if not ms or not cap or not ojos.u32.IsWindow(cap.hwnd):
            self._ov.orden({"cmd": "borrar"}); return {"ok": True, "dibujadas": 0}
        c = ojos.cliente(cap.hwnd)
        evitar = [cap.a_pantalla(k["caja"]) for k in cap.controles]
        marcas = [{"hwnd": cap.hwnd, "ventana": list(c), "rect": cap.a_pantalla(m["caja"]), "texto": m["texto"],
                   "color": m["color"], "n": m.get("n"), "evitar": evitar} for m in ms]
        return self._ov.orden({"cmd": "mostrar", "pids": [cap.pid, os.getpid()], "panel": self._panel_hwnd(), "marcas": marcas})

    def borrar_flechas(self):
        self._marcas = []
        self._ov.orden({"cmd": "borrar"})
        return {"ok": True}

    def abrir_enlace(self, url):
        """Los enlaces de las respuestas se abren en el navegador de siempre (el panel no navega)."""
        if not str(url).startswith(("https://", "http://")): return {"ok": False}
        import webbrowser
        webbrowser.open(url)
        return {"ok": True}

    def nueva(self):
        self.borrar_flechas(); self._ultima = None
        self._sesion.reiniciar(); self._sesion.calentar()
        return {"ok": True}


def area_visible():
    """Área de la pantalla sin la barra de tareas, en píxeles lógicos (los de pywebview); como en panel-excel."""
    import ctypes.wintypes
    r = ctypes.wintypes.RECT(); ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
    esc = ctypes.windll.user32.GetDpiForSystem() / 96
    return r.left / esc, r.top / esc, (r.right - r.left) / esc, (r.bottom - r.top) / esc


def tema():
    try: return json.loads(PREFERENCIAS.read_text(encoding="utf-8")).get("tema", "claro")
    except Exception: return "claro"


def abrir(api):
    import webview
    x0, y0, ancho, alto = area_visible(); ancho_v = 460; t = tema()
    html = (AQUI / "panel.html").read_text(encoding="utf-8").replace(
        "<head>", f"<head><script>window.TEMA_PANEL = {json.dumps(t)};</script>", 1)
    api._ventana = webview.create_window("Asistente", html=html, js_api=api, width=ancho_v, height=int(alto),
                                         x=int(x0 + ancho - ancho_v), y=int(y0), on_top=True, min_size=(360, 300),
                                         background_color="#232631" if t == "oscuro" else "#F8F6F1")
    webview.start(gui="edgechromium")


def probar(texto, png=None):
    """Prueba de punta a punta sin el panel (no envía nada a la persona: es para quien desarrolla)."""
    v = next((v for v in ojos.listar_ventanas(excluir_pids=[os.getpid()])
              if texto.lower() in v["titulo"].lower() or texto.lower() in v["app"].lower()), None)
    if not v: sys.exit(f"No hay ninguna ventana con «{texto}».")
    ses, ov = asistente.Sesion(), Overlay(); api = Api(ses, ov)
    try:
        t = time.time(); ses.calentar(); ses.preguntar("Responde solo: ok"); print(f"Arranque de la sesión: {time.time() - t:.1f}s")
        print(api.elegir(v["hwnd"]))
        t = time.time(); c = api.capturar(); print(f"Captura: {c.get('w')}×{c.get('h')}, {c.get('controles')} controles, {c.get('como')} ({time.time() - t:.1f}s)" if c["ok"] else c)
        if not c["ok"]: return
        t = time.time(); r = api.enviar("¿Dónde está la opción para guardar este archivo? Señálamela.")
        print(f"Respuesta ({time.time() - t:.1f}s): {r}")
        print("Marcas:", api._marcas)
        if png:
            img, origen, _ = ojos.imagen_de(v["hwnd"])
            d = ov.orden({"cmd": "volcar", "carpeta": str(Path(png).resolve().parent)})
            from PIL import Image
            for capa in d.get("capas", []):
                im = Image.open(capa["png"]); x, y = capa["en"]
                img.paste(im, (x - origen[0], y - origen[1]), im); os.remove(capa["png"])
            img.save(png); print("Guardada:", png)
    finally:
        ov.cerrar(); ses.cerrar()


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    a = sys.argv[1:]
    if a[:1] == ["--probar"] and len(a) >= 2:
        probar(a[1], a[2] if len(a) > 2 else None)
    elif not a:
        ses, ov = asistente.Sesion(), Overlay()
        ses.calentar()                              # la sesión arranca mientras eliges la ventana
        try: abrir(Api(ses, ov))
        finally: ov.cerrar(); ses.cerrar()
    else:
        print(__doc__)
