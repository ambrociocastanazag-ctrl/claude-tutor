"""El proyector de los dibujos: pega encima de la app las capas que dibuja la página (dibujante.js) y las anima.

Cada capa es una ventana Win32 transparente (como las flechas de prueba-dia/overlay_dia.py, que no se toca):
WS_EX_LAYERED | TRANSPARENT | TOPMOST | NOACTIVATE | TOOLWINDOW, deja pasar los clics, no roba el foco, sigue a su
ventana cada tic y solo se ve con la app o el panel al frente. La imagen se pasa con UpdateLayeredWindow (alfa por
píxel). Las capas fijas se pintan una vez; las animadas, unas 30 veces por segundo, y solo ellas.

La lupa lee de la pantalla SOLO su zona y la pinta aumentada. No se guarda ni sale de la PC. Si otra ventana tapa la
zona, se queda con la última imagen buena. En Windows 10/11 leer la pantalla también trae estas capas: mientras haya una
lupa, todas se marcan WDA_EXCLUDEFROMCAPTURE (no salen en las lecturas de pantalla) y al quitarla vuelven a la normalidad.

Órdenes por stdin, una línea JSON (responde una línea JSON), formato en DIBUJOS.md:
  {"cmd": "poner", "pids": [...], "panel": hwnd, "capas": [...]}   {"cmd": "reproducir", "id", "desde", "hasta"}
  {"cmd": "borrar"}   {"cmd": "estado"}   {"cmd": "volcar", "carpeta"}   {"cmd": "salir"}

fotograma(capa, t) compone una capa en el instante t (ms) igual que en vivo: lo usa probar_dibujos.py."""
import base64, ctypes, io, json, os, queue, sys, threading, time
from ctypes import wintypes as W

try:
    from PIL import Image, ImageDraw
except ImportError:
    Image = None

FPS = 30


# ---------- componer un fotograma (sin ventanas: sirve también para las pruebas) ----------
def imagen(data_url):
    if not data_url: return None
    datos = base64.b64decode(data_url.split(",", 1)[1] if "," in data_url else data_url)
    return Image.open(io.BytesIO(datos)).convert("RGBA")


class Imagenes:
    """Las imágenes de una capa, decodificadas una vez (y las piezas con alfa o escala ya aplicados, en caché)."""

    def __init__(self, c):
        self.fondo = imagen(c.get("fondo"))
        self.fotos = [imagen(f) for f in c.get("fotos") or []]
        self.piezas = [imagen(p.get("png")) for p in c.get("piezas") or []]
        self._cache = {}

    def pieza(self, i, alfa, escala):
        clave = (i, round(alfa, 2), round(escala, 2))
        im = self._cache.get(clave)
        if im is None:
            im = self.piezas[i]
            if abs(clave[2] - 1) > 0.005:
                im = im.resize((max(1, round(im.width * clave[2])), max(1, round(im.height * clave[2]))), Image.LANCZOS)
            if clave[1] < 0.995:
                a = clave[1]; im = im.copy(); im.putalpha(im.getchannel("A").point(lambda v: round(v * a)))
            if len(self._cache) > 400: self._cache.clear()
            self._cache[clave] = im
        return im


def en_ruta(ruta, t):
    """[x, y, alfa, escala] de una pieza en el instante t (interpolación lineal entre claves)."""
    if not ruta: return None
    if t <= ruta[0][0]: return ruta[0][1:5]
    for a, b in zip(ruta, ruta[1:]):
        if t <= b[0]:
            k = (t - a[0]) / max(1e-6, b[0] - a[0])
            return [a[i] + (b[i] - a[i]) * k for i in range(1, 5)]
    return ruta[-1][1:5]


def pegar(base, im, x, y):
    """alpha_composite que admite que la pieza salga por los bordes."""
    x, y = round(x), round(y)
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(base.width, x + im.width), min(base.height, y + im.height)
    if x1 <= x0 or y1 <= y0: return
    base.alpha_composite(im.crop((x0 - x, y0 - y, x1 - x, y1 - y)), (x0, y0))


def mascara_redonda(w, h, r):
    m = Image.new("L", (w * 2, h * 2), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, w * 2 - 1, h * 2 - 1], radius=max(0, r) * 2, fill=255)
    return m.resize((w, h), Image.LANCZOS)


def fotograma(c, t, imgs=None, lupa=None):
    """La capa c compuesta en el instante t (ms): fondo → fotos[i] → lupa → piezas. lupa: la imagen ya leída de la zona."""
    imgs = imgs or Imagenes(c)
    base = Image.new("RGBA", (int(c["w"]), int(c["h"])), (0, 0, 0, 0))
    if imgs.fondo: pegar(base, imgs.fondo, 0, 0)
    if imgs.fotos:
        i = min(len(imgs.fotos) - 1, int(t * (c.get("fps") or FPS) / 1000))
        if imgs.fotos[i]: pegar(base, imgs.fotos[i], 0, 0)
    lp = c.get("lupa")
    if lp and lupa is not None:
        x, y, w, h = [round(v) for v in lp["en"]]
        if w > 2 and h > 2:
            z = lupa.convert("RGBA").resize((w, h), Image.BICUBIC)
            base.paste(z, (x, y), mascara_redonda(w, h, round(lp.get("radio", 12))))
    for i, p in enumerate(c.get("piezas") or []):
        e = en_ruta(p.get("ruta"), t)
        if not e or e[2] <= 0.01 or imgs.piezas[i] is None: continue
        im = imgs.pieza(i, e[2], e[3])
        k = im.width / max(1, imgs.piezas[i].width)
        pegar(base, im, e[0] - p.get("ax", 0) * k, e[1] - p.get("ay", 0) * k)
    return base


def instante(c, transcurrido):
    """El t (ms) de la animación cuando lleva `transcurrido` ms andando en modo automático."""
    D = c.get("duracion") or 0
    if D <= 0: return 0
    if c.get("repetir"):
        ciclo = D + max(0, c.get("pausa") or 0)
        return min(D, transcurrido % ciclo)
    return min(D, transcurrido)


# ---------- las ventanas ----------
if os.name == "nt":
    u32, g32, k32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x8, 0x80, 0x08000000
WM_NCHITTEST, WM_MOUSEACTIVATE = 0x84, 0x21
HTTRANSPARENT, MA_NOACTIVATE = -1, 3
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
SWP_NOSIZE, SWP_NOACTIVATE = 0x1, 0x10
ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA = 2, 0, 1
PM_REMOVE, SRCCOPY, GA_ROOT = 1, 0x00CC0020, 2
WDA_NONE, WDA_EXCLUDEFROMCAPTURE = 0, 0x11


def _preparar():
    try: u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))     # por monitor v2: coordenadas físicas
    except Exception:
        try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception: pass
    LRESULT = ctypes.c_ssize_t
    global WNDPROC, BLENDFUNCTION, BITMAPINFOHEADER, _wc, _wndproc, HWND_TOPMOST
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    u32.DefWindowProcW.restype = LRESULT
    u32.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    u32.CreateWindowExW.restype = W.HWND
    u32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
    u32.GetForegroundWindow.restype = W.HWND
    u32.WindowFromPoint.restype = W.HWND
    u32.WindowFromPoint.argtypes = [W.POINT]
    u32.GetAncestor.restype = W.HWND
    u32.GetAncestor.argtypes = [W.HWND, W.UINT]
    u32.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]
    u32.GetDC.restype = W.HDC
    u32.GetDC.argtypes = [W.HWND]
    u32.ReleaseDC.argtypes = [W.HWND, W.HDC]
    u32.DestroyWindow.argtypes = [W.HWND]
    u32.ShowWindow.argtypes = [W.HWND, ctypes.c_int]
    u32.IsWindow.argtypes = [W.HWND]
    u32.IsWindowVisible.argtypes = [W.HWND]
    u32.IsIconic.argtypes = [W.HWND]
    u32.SetWindowDisplayAffinity.argtypes = [W.HWND, W.DWORD]
    g32.CreateDIBSection.restype = W.HBITMAP
    g32.CreateDIBSection.argtypes = [W.HDC, ctypes.c_void_p, W.UINT, ctypes.POINTER(ctypes.c_void_p), W.HANDLE, W.DWORD]
    g32.SelectObject.restype = W.HGDIOBJ
    g32.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
    g32.CreateCompatibleDC.restype = W.HDC
    g32.CreateCompatibleDC.argtypes = [W.HDC]
    g32.DeleteObject.argtypes = [W.HGDIOBJ]
    g32.DeleteDC.argtypes = [W.HDC]
    g32.BitBlt.argtypes = [W.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.HDC, ctypes.c_int, ctypes.c_int, W.DWORD]
    HWND_TOPMOST = W.HWND(-1)

    class _BF(ctypes.Structure):
        _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte), ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]

    class _BIH(ctypes.Structure):
        _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD), ("biBitCount", W.WORD),
                    ("biCompression", W.DWORD), ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG),
                    ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]

    class _WC(ctypes.Structure):
        _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                    ("hInstance", W.HINSTANCE), ("hIcon", W.HICON), ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH),
                    ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR)]

    BLENDFUNCTION, BITMAPINFOHEADER = _BF, _BIH
    u32.UpdateLayeredWindow.argtypes = [W.HWND, W.HDC, ctypes.POINTER(W.POINT), ctypes.POINTER(W.SIZE), W.HDC, ctypes.POINTER(W.POINT),
                                        W.COLORREF, ctypes.POINTER(BLENDFUNCTION), W.DWORD]

    @WNDPROC
    def proc(h, msg, wp, lp):
        if msg == WM_NCHITTEST: return HTTRANSPARENT             # los clics pasan a la app de debajo
        if msg == WM_MOUSEACTIVATE: return MA_NOACTIVATE         # nunca toma el foco
        return u32.DefWindowProcW(h, msg, wp, lp)
    _wndproc = proc
    _wc = _WC(); _wc.lpfnWndProc = _wndproc; _wc.hInstance = k32.GetModuleHandleW(None); _wc.lpszClassName = "TutorCapaDibujo"
    u32.RegisterClassW(ctypes.byref(_wc))


def cliente(hwnd):
    """(x, y, w, h) físicos del área de cliente, o None si ya no existe."""
    if not u32.IsWindow(hwnd): return None
    r = W.RECT(); u32.GetClientRect(hwnd, ctypes.byref(r))
    p = W.POINT(0, 0); u32.ClientToScreen(hwnd, ctypes.byref(p))
    return (p.x, p.y, r.right - r.left, r.bottom - r.top)


def pid_de(hwnd):
    p = W.DWORD(); u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p)); return p.value


def leer_pantalla(x, y, w, h):
    """Esa zona de la pantalla (las capas no salen: ver WDA_EXCLUDEFROMCAPTURE en Proyector.poner)."""
    pantalla = u32.GetDC(None); mem = g32.CreateCompatibleDC(pantalla)
    bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    bits = ctypes.c_void_p()
    bmp = g32.CreateDIBSection(mem, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0)
    viejo = g32.SelectObject(mem, bmp)
    try:
        g32.BitBlt(mem, 0, 0, w, h, pantalla, x, y, SRCCOPY)
        datos = ctypes.string_at(bits, w * h * 4)
        return Image.frombuffer("RGBA", (w, h), datos, "raw", "BGRA", 0, 1).convert("RGB")
    finally:
        g32.SelectObject(mem, viejo); g32.DeleteObject(bmp); g32.DeleteDC(mem); u32.ReleaseDC(None, pantalla)


def a_ventana(hwnd, img, x, y):
    """Pone la imagen RGBA en la ventana en capas, en (x, y) de la pantalla."""
    w, h = img.size
    datos = img.tobytes("raw", "BGRa")                  # BGRA premultiplicado, lo que pide UpdateLayeredWindow
    bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    pantalla = u32.GetDC(None); mem = g32.CreateCompatibleDC(pantalla)
    bits = ctypes.c_void_p()
    bmp = g32.CreateDIBSection(mem, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0)
    ctypes.memmove(bits, datos, len(datos))
    viejo = g32.SelectObject(mem, bmp)
    bl = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
    u32.UpdateLayeredWindow(hwnd, pantalla, ctypes.byref(W.POINT(x, y)), ctypes.byref(W.SIZE(w, h)), mem, ctypes.byref(W.POINT(0, 0)), 0, ctypes.byref(bl), ULW_ALPHA)
    g32.SelectObject(mem, viejo); g32.DeleteObject(bmp); g32.DeleteDC(mem); u32.ReleaseDC(None, pantalla)


class Lamina:
    """Una capa encima de su ventana."""

    def __init__(self, c):
        self.c, self.objetivo = c, int(c["hwnd"])
        self.imgs = Imagenes(c)
        self.hwnd = u32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                                        _wc.lpszClassName, "Tutor (dibujo)", WS_POPUP, 0, 0, 1, 1, None, None, _wc.hInstance, None)
        self.visible, self.donde = False, None
        self.t0 = time.monotonic()
        self.tramo = None if c.get("auto", True) else (0, 0)       # (desde, hasta): reproduciendo un tramo (la voz)
        self.t_tramo = self.t0
        self.ultimo_t, self.lupa_img, self.lupa_t = None, None, 0
        self.pintar(force=True)

    def anima(self):
        return (self.c.get("duracion") or 0) > 0 or bool(self.c.get("lupa"))

    def t(self):
        ahora = time.monotonic()
        if self.tramo is not None:
            desde, hasta = self.tramo
            return min(hasta, desde + (ahora - self.t_tramo) * 1000)
        return instante(self.c, (ahora - self.t0) * 1000)

    def reproducir(self, desde, hasta):
        """Reproduce el tramo [desde, hasta] y se queda en hasta. desde None: vuelve a andar sola (tras la voz)."""
        if desde is None: self.tramo = None; self.t0 = time.monotonic(); return
        self.tramo = (float(desde), float(hasta)); self.t_tramo = time.monotonic()

    def leer_lupa(self):
        lp = self.c.get("lupa")
        if not lp: return
        ahora = time.monotonic()
        if ahora - self.lupa_t < 1 / max(1, lp.get("fps", 8)): return
        self.lupa_t = ahora
        c = cliente(self.objetivo)
        if not c or not u32.IsWindowVisible(self.objetivo) or u32.IsIconic(self.objetivo): return
        zx, zy, zw, zh = [round(v) for v in lp["zona"]]
        x, y = c[0] + zx, c[1] + zy
        raiz = u32.GetAncestor(W.HWND(self.objetivo), GA_ROOT)
        for px, py in ((x + 2, y + 2), (x + zw - 3, y + 2), (x + zw // 2, y + zh // 2), (x + 2, y + zh - 3), (x + zw - 3, y + zh - 3)):
            h = u32.WindowFromPoint(W.POINT(px, py))
            if h and pid_de(h) == os.getpid(): continue                            # otra capa de dibujo: no sale en la lectura
            if not h or u32.GetAncestor(h, GA_ROOT) != raiz: return             # algo la tapa: queda la última imagen buena
        if zw > 1 and zh > 1: self.lupa_img = leer_pantalla(x, y, zw, zh)

    def pintar(self, force=False):
        """Compone y pone el fotograma si cambió (las fijas, solo una vez)."""
        c = cliente(self.objetivo)
        if not c: return
        t = self.t()
        antes = self.lupa_img
        self.leer_lupa()
        if not force and t == self.ultimo_t and self.lupa_img is antes: return
        self.ultimo_t = t
        img = fotograma(self.c, t, self.imgs, self.lupa_img)
        self.donde = (c[0] + int(self.c["x"]), c[1] + int(self.c["y"]))
        a_ventana(self.hwnd, img, *self.donde)
        self.img = img

    def seguir(self, mostrar, debajo_de=None):
        z = W.HWND(debajo_de) if debajo_de else HWND_TOPMOST
        c = cliente(self.objetivo)
        if not c: return False
        ver = bool(mostrar and u32.IsWindowVisible(self.objetivo) and not u32.IsIconic(self.objetivo))
        x, y = c[0] + int(self.c["x"]), c[1] + int(self.c["y"])
        if self.donde != (x, y):
            u32.SetWindowPos(self.hwnd, z, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE); self.donde = (x, y)
        if ver and not self.visible:
            u32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
            u32.SetWindowPos(self.hwnd, z, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE); self.visible = True
        elif not ver and self.visible:
            u32.ShowWindow(self.hwnd, SW_HIDE); self.visible = False
        if self.visible and self.anima(): self.pintar()
        return True

    def cerrar(self):
        u32.DestroyWindow(self.hwnd)


class Proyector:
    def __init__(self):
        self.laminas, self.pids, self.panel = {}, set(), None

    def poner(self, capas, pids=(), panel=None):
        self.pids = {int(p) for p in pids if p} or self.pids
        if panel: self.panel = int(panel)
        self.borrar()
        errores = []
        for c in capas or []:
            try:
                if not u32.IsWindow(int(c["hwnd"])): errores.append(f"{c.get('id')}: la ventana ya no existe"); continue
                self.laminas[str(c["id"])] = Lamina(c)
            except Exception as e:
                errores.append(f"{c.get('id')}: {e}")
        if any(l.c.get("lupa") for l in self.laminas.values()):     # que la lupa no se vea a sí misma ni a las demás
            for l in self.laminas.values(): u32.SetWindowDisplayAffinity(l.hwnd, WDA_EXCLUDEFROMCAPTURE)
            for l in self.laminas.values(): l.lupa_t = 0; l.pintar(force=True)
        self.tic()
        return {"ok": True, "capas": len(self.laminas), "errores": errores}

    def reproducir(self, cid, desde, hasta):
        l = self.laminas.get(str(cid))
        if not l: return {"ok": False, "error": f"no hay capa {cid}"}
        l.reproducir(desde, hasta); return {"ok": True}

    def borrar(self):
        for l in self.laminas.values(): l.cerrar()
        self.laminas = {}
        return {"ok": True}

    def tic(self):
        fg = u32.GetForegroundWindow()
        mostrar = not self.pids or (fg and pid_de(fg) in self.pids)
        debajo = self.panel if self.panel and u32.IsWindow(self.panel) else None
        for k in [k for k, l in self.laminas.items() if not l.seguir(mostrar, debajo)]: self.laminas.pop(k).cerrar()

    def estado(self):
        return {"ok": True, "capas": [{"id": k, "objetivo": l.objetivo, "visible": l.visible, "en": l.donde, "t": l.ultimo_t,
                                       "anima": l.anima()} for k, l in self.laminas.items()]}

    def volcar(self, carpeta):
        out = []
        for k, l in self.laminas.items():
            ruta = os.path.join(carpeta, f"capa_{k}.png"); getattr(l, "img", fotograma(l.c, l.t(), l.imgs)).save(ruta)
            out.append({"id": k, "png": ruta, "en": l.donde, "visible": l.visible})
        return {"ok": True, "capas": out}


def _leer(cola):
    for linea in sys.stdin: cola.put(linea)
    cola.put('{"cmd": "salir"}')


def main():
    try: sys.stdout.reconfigure(encoding="utf-8"); sys.stdin.reconfigure(encoding="utf-8")
    except Exception: pass
    if Image is None:
        print(json.dumps({"ok": False, "listo": True, "error": "falta Pillow (python -m pip install pillow)"}), flush=True); return
    _preparar()
    pr = Proyector(); cola = queue.Queue()
    threading.Thread(target=_leer, args=(cola,), daemon=True).start()
    msg = W.MSG()
    print(json.dumps({"ok": True, "listo": True}), flush=True)
    while True:
        while u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            u32.TranslateMessage(ctypes.byref(msg)); u32.DispatchMessageW(ctypes.byref(msg))
        try: linea = cola.get(timeout=1 / FPS)
        except queue.Empty: linea = None
        if linea:
            try:
                o = json.loads(linea); cmd = o.get("cmd")
                if cmd == "salir": pr.borrar(); print(json.dumps({"ok": True, "adios": True}), flush=True); return
                elif cmd == "poner": r = pr.poner(o.get("capas") or [], o.get("pids") or [], o.get("panel"))
                elif cmd == "reproducir": r = pr.reproducir(o.get("id"), o.get("desde"), o.get("hasta"))
                elif cmd == "borrar": r = pr.borrar()
                elif cmd == "estado": r = pr.estado()
                elif cmd == "volcar": r = pr.volcar(o["carpeta"])
                else: r = {"ok": False, "error": f"orden desconocida {cmd!r}"}
            except Exception as e:
                r = {"ok": False, "error": str(e)}
            try: print(json.dumps(r), flush=True)
            except (OSError, ValueError): pr.borrar(); return          # el panel se cerró: se van los dibujos con él
        pr.tic()


if __name__ == "__main__":
    main()
