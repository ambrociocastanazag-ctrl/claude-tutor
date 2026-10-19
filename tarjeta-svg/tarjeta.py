"""La Tarjeta SVG: una ventanita pegada al borde derecho para sacar figuras en SVG y pegarlas en Miro (README.md).

Dos estados: plegada (una pestaña de 44 px, siempre encima) y desplegada (420 × 560). Ctrl+Alt+L o un clic la abren y
la pliegan. Un solo ejemplar: escucha en 127.0.0.1:4748, que también sirve la página y sus estáticos (CONTRATO.md §4):
  GET  /hola                  → {"ok": true}
  POST /mostrar               → la despliega al frente
  POST /figura {contenido}    → Tarjeta.ir(...) y la despliega
  GET  /tarjeta-svg/... y /tutor-pantalla/...   los archivos de la página (solo esas dos carpetas)

Copiar SVG pone a la vez el archivo .svg (CF_HDROP: Miro lo sube al pegar), image/svg+xml y PNG. El código como texto va
aparte («Copiar código»): si fuera junto, Miro podría pegar el texto en una nota en vez de la imagen.

python tarjeta.py            la abre (mejor: python abrir_tarjeta.py, que no abre dos)
python tarjeta.py --probar   portapapeles, servidor y rutas, sin ventana (ojo: deja una figura de prueba en el portapapeles)"""
import base64, ctypes, io, json, mimetypes, socket, struct, subprocess, sys, tempfile, threading, time, webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
sys.path.insert(0, str(AQUI)); sys.path.insert(0, str(RAIZ / "tutor-pantalla"))
PUERTO = 4748
ESTADO = AQUI / "estado.json"                                   # lo que la persona escribió; suyo, no va al repo
CONFIG = AQUI / "config.json"                                   # {"mathstudio": "carpeta de MathStudio"}; suyo, no va al repo
PREFERENCIAS = RAIZ / "panel-excel" / "preferencias.json"
SERVIDAS = ("tarjeta-svg", "tutor-pantalla")                    # las únicas carpetas que sirve el servidor
TEMP = Path(tempfile.gettempdir()) / "tarjeta-svg"
PLEGADA, DESPLEGADA = (44, 150), (420, 560)                    # los del diseño de Claude Design


def area_visible():
    """Área de la pantalla sin la barra de tareas, en píxeles lógicos (los de pywebview)."""
    import ctypes.wintypes
    r = ctypes.wintypes.RECT(); ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
    esc = ctypes.windll.user32.GetDpiForSystem() / 96
    return r.left / esc, r.top / esc, (r.right - r.left) / esc, (r.bottom - r.top) / esc


def tema():
    try: return json.loads(PREFERENCIAS.read_text(encoding="utf-8")).get("tema", "claro")
    except Exception: return "claro"


# ---------- portapapeles ----------
def _png_a_dib(png):
    """PNG → CF_DIB (BITMAPINFOHEADER + píxeles), para los programas que no leen el formato «PNG»."""
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGBA")
    fondo = Image.new("RGBA", im.size, (255, 255, 255, 255)); fondo.alpha_composite(im)
    b = io.BytesIO(); fondo.convert("RGB").save(b, "BMP")
    return b.getvalue()[14:]                                     # sin la cabecera de archivo BMP


def _hdrop(rutas):
    """CF_HDROP: DROPFILES (20 bytes, rutas anchas) + rutas separadas por nulo y terminadas en doble nulo."""
    datos = "".join(str(r) + "\0" for r in rutas).encode("utf-16-le") + b"\0\0"
    return struct.pack("<IiiII", 20, 0, 0, 0, 1) + datos


def nombre_archivo(nombre):
    limpio = "".join(c for c in str(nombre or "figura") if c.isalnum() or c in " -_").strip()[:50]
    return limpio or "figura"


def copiar(svg=None, png=None, texto=None, nombre="figura"):
    """Pone en el portapapeles lo que venga: svg (texto) → archivo .svg + image/svg+xml; png (bytes) → PNG + CF_DIB;
    texto → CF_UNICODETEXT. Devuelve la ruta del .svg temporal si lo hubo."""
    import win32clipboard as wc, win32con
    ruta = None
    if svg:
        TEMP.mkdir(exist_ok=True)
        ruta = TEMP / f"{nombre_archivo(nombre)}.svg"
        ruta.write_text(svg, encoding="utf-8")
    for intento in range(10):                                    # otro programa puede tenerlo abierto un instante
        try: wc.OpenClipboard(); break
        except Exception: time.sleep(0.05)
    else:
        raise RuntimeError("El portapapeles está ocupado por otro programa: inténtalo de nuevo.")
    try:
        wc.EmptyClipboard()
        if svg:
            wc.SetClipboardData(win32con.CF_HDROP, _hdrop([ruta]))
            wc.SetClipboardData(wc.RegisterClipboardFormat("image/svg+xml"), svg.encode("utf-8"))
        if png:
            wc.SetClipboardData(wc.RegisterClipboardFormat("PNG"), png)
            wc.SetClipboardData(win32con.CF_DIB, _png_a_dib(png))
        if texto: wc.SetClipboardData(win32con.CF_UNICODETEXT, texto)
    finally:
        wc.CloseClipboard()
    return ruta


# ---------- la API de la página ----------
class Api:
    def __init__(self):
        self._ventana = None
        self._plegada = True
        self._asis = None

    # estado de la ventana
    def _colocar(self, plegada):
        v = self._ventana
        if not v: return
        x0, y0, ancho, alto = area_visible()
        w, h = PLEGADA if plegada else DESPLEGADA
        y = y0 + (alto * 0.3 if plegada else max(0, (alto - h) * 0.35))
        v.resize(w, h); v.move(int(x0 + ancho - w), int(y))

    def plegar(self):
        self._plegada = True; self._colocar(True)
        self._js("window.Tarjeta && Tarjeta._plegada && Tarjeta._plegada(true)")
        return {"ok": True}

    def desplegar(self):
        self._plegada = False; self._colocar(False)
        self._js("window.Tarjeta && Tarjeta._plegada && Tarjeta._plegada(false)")
        self._al_frente()
        return {"ok": True}

    def cerrar(self):
        """La ✕: cierra la tarjeta del todo (y con ella su servidor y Ctrl+Alt+L). Se vuelve a abrir desde «Mis clases»
        o con el botón «Tarjeta» de los paneles."""
        v = self._ventana
        if v: threading.Timer(0.05, v.destroy).start()          # fuera de la llamada de la página, para que pueda responder
        return {"ok": True}

    def alternar(self):
        return self.desplegar() if self._plegada else self.plegar()

    def _al_frente(self):
        try:
            h = int(self._ventana.native.Handle.ToInt64())
            ctypes.windll.user32.ShowWindow(h, 5); ctypes.windll.user32.SetForegroundWindow(h)
        except Exception: pass

    def _js(self, codigo):
        try: return self._ventana.evaluate_js(codigo) if self._ventana else None
        except Exception: return None

    def tema(self): return tema()

    # copiar
    def copiar_svg(self, svg, nombre="figura", png_b64=None):
        try:
            png = base64.b64decode(png_b64.split(",", 1)[-1]) if png_b64 else None
            copiar(svg=svg, png=png, nombre=nombre)
            return {"ok": True}
        except Exception as e: return {"ok": False, "error": str(e)}

    def copiar_png(self, png_b64, nombre="figura"):
        try: copiar(png=base64.b64decode(png_b64.split(",", 1)[-1]), nombre=nombre); return {"ok": True}
        except Exception as e: return {"ok": False, "error": str(e)}

    def copiar_texto(self, texto):
        try: copiar(texto=texto); return {"ok": True}
        except Exception as e: return {"ok": False, "error": str(e)}

    def copiar_gif(self, fotos, ms, nombre="figura 3d"):
        """El GIF de una figura 3D: los fotogramas PNG de la página → .gif en Descargas y copiado como archivo (tutor-pantalla/gif3d.py)."""
        try:
            import gif3d
            return gif3d.guardar_y_copiar(fotos, ms, nombre)
        except Exception as e: return {"ok": False, "error": f"No pude hacer el GIF: {e}"}

    def archivo_svg(self, svg, nombre="figura"):
        """El .svg en una carpeta temporal (para arrastrarlo o abrirlo); devuelve la ruta."""
        TEMP.mkdir(exist_ok=True)
        ruta = TEMP / f"{nombre_archivo(nombre)}.svg"; ruta.write_text(svg, encoding="utf-8")
        return {"ok": True, "ruta": str(ruta)}

    # MathStudio (su app completa, para lo complejo: no se modifica, solo se abre)
    def abrir_mathstudio(self, guion=None):
        try: MATHSTUDIO = Path(json.loads(CONFIG.read_text(encoding="utf-8"))["mathstudio"])
        except Exception: MATHSTUDIO = None
        if not MATHSTUDIO or not (MATHSTUDIO / "index.html").exists():
            return {"ok": False, "error": "No sé dónde está MathStudio: pon su carpeta en tarjeta-svg/config.json."}
        if not _escucha(8000):
            subprocess.Popen([sys.executable, "-m", "http.server", "8000"], cwd=str(MATHSTUDIO),
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            for _ in range(30):
                if _escucha(8000): break
                time.sleep(0.1)
        webbrowser.open("http://localhost:8000/index.html")
        if guion: copiar(texto=guion)
        return {"ok": True, "copiado": bool(guion)}

    # recordar lo escrito
    def guardar_estado(self, obj):
        try: ESTADO.write_text(json.dumps(obj, ensure_ascii=False), encoding="utf-8"); return {"ok": True}
        except Exception as e: return {"ok": False, "error": str(e)}

    def leer_estado(self):
        try: return json.loads(ESTADO.read_text(encoding="utf-8"))
        except Exception: return {}

    # el asistente (asistente_tarjeta.py): responde a trozos con Tarjeta.trozo(t)
    def asistente_preguntar(self, texto, contexto=None):
        try:
            if self._asis is None:
                import asistente_tarjeta
                self._asis = asistente_tarjeta.Asistente()
            return {"ok": True, "texto": self._asis.preguntar(texto, contexto or {},
                                                              lambda t: self._js(f"window.Tarjeta && Tarjeta.trozo && Tarjeta.trozo({json.dumps(t)})"))}
        except Exception as e:
            return {"ok": False, "error": f"El asistente no respondió: {e}"}

    def asistente_reiniciar(self):
        if self._asis is not None:
            try: self._asis.reiniciar()
            except Exception: pass
        return {"ok": True}


# ---------- el servidor local (un solo ejemplar, órdenes de fuera y la página) ----------
def _escucha(puerto):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", puerto)) == 0


def servidor(api):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass

        def _json(self, obj, codigo=200):
            b = json.dumps(obj).encode(); self.send_response(codigo)
            self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(b))); self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            ruta = self.path.split("?", 1)[0]
            if ruta == "/hola": return self._json({"ok": True, "tarjeta": True})
            partes = [p for p in ruta.split("/") if p]
            if not partes or partes[0] not in SERVIDAS or any(p in ("..", ".") or ":" in p for p in partes) or partes[-1] in ("estado.json", "config.json"):
                return self._json({"ok": False}, 404)
            from urllib.parse import unquote
            f = (RAIZ.joinpath(*[unquote(p) for p in partes])).resolve()
            if not str(f).startswith(str(RAIZ / partes[0])) or not f.is_file(): return self._json({"ok": False}, 404)
            datos = f.read_bytes(); tipo = mimetypes.guess_type(f.name)[0] or "application/octet-stream"
            if f.suffix in (".js", ".mjs"): tipo = "text/javascript"
            self.send_response(200); self.send_header("Content-Type", tipo + ("; charset=utf-8" if tipo.startswith("text") else ""))
            self.send_header("Content-Length", str(len(datos))); self.send_header("Cache-Control", "no-cache"); self.end_headers()
            self.wfile.write(datos)

        def do_POST(self):
            if self.client_address[0] != "127.0.0.1": return self._json({"ok": False}, 403)
            n = int(self.headers.get("Content-Length") or 0)
            try: cuerpo = json.loads(self.rfile.read(n) or b"{}")
            except ValueError: cuerpo = {}
            if self.path == "/mostrar":
                api.desplegar(); return self._json({"ok": True})
            if self.path == "/figura":
                api.desplegar()
                api._js(f"window.Tarjeta && Tarjeta.ir && Tarjeta.ir(null, {json.dumps(cuerpo.get('contenido') or {}, ensure_ascii=False)})")
                return self._json({"ok": True})
            self._json({"ok": False}, 404)

    s = ThreadingHTTPServer(("127.0.0.1", PUERTO), H)
    threading.Thread(target=s.serve_forever, daemon=True).start()
    return s


# ---------- Ctrl+Alt+L ----------
def atajo(api):
    def hilo():
        from ctypes import wintypes as W
        u = ctypes.WinDLL("user32", use_last_error=True)
        MOD_ALT, MOD_CONTROL, MOD_NOREPEAT, WM_HOTKEY, ID = 0x1, 0x2, 0x4000, 0x0312, 0x4C4C
        if not u.RegisterHotKey(None, ID, MOD_ALT | MOD_CONTROL | MOD_NOREPEAT, ord("L")):
            print("Ctrl+Alt+L ya lo usa otro programa: la tarjeta sigue sin el atajo.", flush=True); return
        msg = W.MSG()
        try:
            while u.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == WM_HOTKEY: api.alternar()
        finally:
            u.UnregisterHotKey(None, ID)
    threading.Thread(target=hilo, daemon=True).start()


def abrir():
    import webview
    if _escucha(PUERTO): sys.exit("La tarjeta ya está abierta (usa abrir_tarjeta.py para traerla).")
    api = Api(); servidor(api)
    x0, y0, ancho, alto = area_visible(); w, h = PLEGADA
    api._ventana = webview.create_window("Tarjeta SVG", url=f"http://127.0.0.1:{PUERTO}/tarjeta-svg/tarjeta.html", js_api=api,
                                         width=w, height=h, x=int(x0 + ancho - w), y=int(y0 + alto * 0.3),
                                         frameless=True, easy_drag=False, on_top=True, resizable=False, min_size=(40, 100),   # sin esto, pywebview no baja de 200 px
                                         background_color="#15171B" if tema() == "oscuro" else "#F9F6F2")
    api._ventana.events.closed += lambda: setattr(api, "_ventana", None)
    atajo(api)
    try: webview.start(gui="edgechromium")
    finally:
        if api._asis is not None:
            try: api._asis.cerrar()
            except Exception: pass


# ---------- pruebas sin ventana ----------
def probar():
    import urllib.request
    fallos = 0

    def ver(c, txt):
        nonlocal fallos
        print(("  ✔ " if c else "  ✘ ") + txt); fallos += not c

    import win32clipboard as wc, win32con
    svg = '<svg xmlns="http://www.w3.org/2000/svg" width="40" height="20"><rect width="40" height="20" fill="#1e5ac8"/></svg>'
    from PIL import Image
    b = io.BytesIO(); Image.new("RGBA", (40, 20), (30, 90, 200, 255)).save(b, "PNG"); png = b.getvalue()
    ruta = copiar(svg=svg, png=png, nombre="prueba tarjeta")
    wc.OpenClipboard()
    try:
        formatos = []; f = 0
        while True:
            f = wc.EnumClipboardFormats(f)
            if not f: break
            formatos.append(f)
        archivos = wc.GetClipboardData(win32con.CF_HDROP) if win32con.CF_HDROP in formatos else ()
        svg_leido = wc.GetClipboardData(wc.RegisterClipboardFormat("image/svg+xml"))
        png_leido = wc.GetClipboardData(wc.RegisterClipboardFormat("PNG"))
        tiene_texto = win32con.CF_UNICODETEXT in formatos
    finally:
        wc.CloseClipboard()
    ver(list(archivos) == [str(ruta)] and ruta.read_text(encoding="utf-8") == svg, f"Copiar SVG: el archivo .svg va en el portapapeles ({ruta.name})")
    ver(bytes(svg_leido).rstrip(b"\0").decode() == svg, "Copiar SVG: también como image/svg+xml")
    ver(bytes(png_leido)[:8] == b"\x89PNG\r\n\x1a\n" and win32con.CF_DIB in formatos, "Copiar SVG: también como PNG y como imagen (CF_DIB)")
    ver(not tiene_texto, "Copiar SVG no pone el código como texto (Miro lo pegaría en una nota)")
    copiar(texto="hola"); wc.OpenClipboard()
    try: ver(wc.GetClipboardData(win32con.CF_UNICODETEXT) == "hola", "Copiar código: texto")
    finally: wc.CloseClipboard()
    ver(nombre_archivo('a/b:c*"d') == "abcd" and nombre_archivo("") == "figura", "nombres de archivo seguros")
    if _escucha(PUERTO):
        print("  (hay una tarjeta abierta: no pruebo el servidor)")
    else:
        api = Api(); s = servidor(api)
        try:
            def get(p):
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}{p}", timeout=3) as r: return r.status, r.read()
                except urllib.error.HTTPError as e: return e.code, b""
            ver(json.loads(get("/hola")[1]).get("tarjeta") is True, "servidor: /hola")
            ver(get("/tarjeta-svg/tarjeta.py")[0] == 200 and get("/tutor-pantalla/asistente.py")[0] == 200, "servidor: sirve tarjeta-svg/ y tutor-pantalla/")
            ver(get("/mis-clases/progreso.json")[0] == 404 and get("/tarjeta-svg/../contexto.md")[0] == 404
                and get("/tarjeta-svg/%2e%2e/contexto.md")[0] == 404 and get("/tarjeta-svg/estado.json")[0] == 404,
                "servidor: nada fuera de esas carpetas ni su estado")
        finally:
            s.shutdown()
    print("Tarjeta: todo bien" if not fallos else f"Tarjeta: {fallos} fallo(s)")
    return fallos


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    if sys.argv[1:2] == ["--probar"]: sys.exit(1 if probar() else 0)
    abrir()
