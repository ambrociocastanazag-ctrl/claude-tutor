"""Flechas y notas ENCIMA de la ventana real de Dia («En Dia: dónde se hace», Fase 2 de plugin-dia/PROPUESTA.md).

Por cada ventana de Dia señalada (la principal, el diálogo Propiedades...) hay una ventana Win32 transparente
(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW) que:
  - deja pasar los clics a Dia (WS_EX_TRANSPARENT y WM_NCHITTEST = HTTRANSPARENT),
  - no roba el foco (se muestra con SW_SHOWNOACTIVATE y responde MA_NOACTIVATE),
  - sigue a su ventana si se mueve o cambia de tamaño (la mira cada 50 ms),
  - se esconde si la ventana se minimiza, se cierra o si la persona pasa a otra aplicación (solo se ve con Dia o el
    panel al frente: así no flota encima de otras ventanas).
El dibujo se hace con Pillow (antialias, colores del panel) y se pasa con UpdateLayeredWindow (alfa por píxel).

Se maneja por stdin, una línea JSON por orden (y responde una línea JSON por stdout):
  {"cmd": "mostrar", "pids": [pid de Dia, pid del panel], "panel": HWND del panel (opcional), "marcas": [
      {"hwnd": 123, "ventana": [x, y, w, h], "rect": [x, y, w, h], "texto": "Pestaña Atributos", "color": "azul", "n": 1}]}
  {"cmd": "borrar"}      {"cmd": "estado"}      {"cmd": "salir"}
"ventana" (el área de cliente de esa ventana) y "rect" (lo señalado) van en las coordenadas que da GTK (orden
«widgets» del plugin). Aquí se pasan a píxeles físicos con el rectángulo de cliente que da Windows: si Dia no
fuera consciente de la escala (otra PC), la proporción entre los dos sale sola (100 %, 125 %, 150 %).

Uso suelto (pruebas):  python overlay_dia.py   y escribirle las órdenes."""
import ctypes, json, os, queue, sys, threading
from ctypes import wintypes as W

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:                                  # sin Pillow no hay flechas encima de Dia (el panel sigue igual)
    Image = None

u32, g32, k32 = ctypes.windll.user32, ctypes.windll.gdi32, ctypes.windll.kernel32
try: u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))     # por monitor v2: coordenadas físicas
except Exception:
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception: pass

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x20, 0x8, 0x80, 0x08000000
WM_NCHITTEST, WM_MOUSEACTIVATE, WM_DESTROY = 0x84, 0x21, 0x2
HTTRANSPARENT, MA_NOACTIVATE = -1, 3
SW_HIDE, SW_SHOWNOACTIVATE = 0, 4
SWP_NOSIZE, SWP_NOACTIVATE, SWP_SHOWWINDOW = 0x1, 0x10, 0x40
HWND_TOPMOST = W.HWND(-1)
ULW_ALPHA, AC_SRC_OVER, AC_SRC_ALPHA = 2, 0, 1
PM_REMOVE, WAIT_TIMEOUT = 1, 258
COLORES = {"rojo": (192, 40, 40), "verde": (30, 140, 70), "amarillo": (215, 145, 0), "azul": (30, 90, 200), "naranja": (230, 110, 0)}

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
u32.DefWindowProcW.restype = LRESULT
u32.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
u32.CreateWindowExW.restype = W.HWND
u32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
u32.GetForegroundWindow.restype = W.HWND
u32.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]
g32.CreateDIBSection.restype = W.HBITMAP
g32.CreateDIBSection.argtypes = [W.HDC, ctypes.c_void_p, W.UINT, ctypes.POINTER(ctypes.c_void_p), W.HANDLE, W.DWORD]
g32.SelectObject.restype = W.HGDIOBJ
g32.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
g32.CreateCompatibleDC.restype = W.HDC
g32.CreateCompatibleDC.argtypes = [W.HDC]
g32.DeleteObject.argtypes = [W.HGDIOBJ]
g32.DeleteDC.argtypes = [W.HDC]
u32.GetDC.restype = W.HDC
u32.GetDC.argtypes = [W.HWND]
u32.ReleaseDC.argtypes = [W.HWND, W.HDC]


class BLENDFUNCTION(ctypes.Structure):
    _fields_ = [("BlendOp", ctypes.c_ubyte), ("BlendFlags", ctypes.c_ubyte), ("SourceConstantAlpha", ctypes.c_ubyte), ("AlphaFormat", ctypes.c_ubyte)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [("biSize", W.DWORD), ("biWidth", W.LONG), ("biHeight", W.LONG), ("biPlanes", W.WORD), ("biBitCount", W.WORD),
                ("biCompression", W.DWORD), ("biSizeImage", W.DWORD), ("biXPelsPerMeter", W.LONG), ("biYPelsPerMeter", W.LONG),
                ("biClrUsed", W.DWORD), ("biClrImportant", W.DWORD)]


class WNDCLASSW(ctypes.Structure):
    _fields_ = [("style", W.UINT), ("lpfnWndProc", WNDPROC), ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int),
                ("hInstance", W.HINSTANCE), ("hIcon", W.HICON), ("hCursor", W.HANDLE), ("hbrBackground", W.HBRUSH),
                ("lpszMenuName", W.LPCWSTR), ("lpszClassName", W.LPCWSTR)]


u32.UpdateLayeredWindow.argtypes = [W.HWND, W.HDC, ctypes.POINTER(W.POINT), ctypes.POINTER(W.SIZE), W.HDC, ctypes.POINTER(W.POINT),
                                    W.COLORREF, ctypes.POINTER(BLENDFUNCTION), W.DWORD]


@WNDPROC
def _wndproc(h, msg, wp, lp):
    if msg == WM_NCHITTEST: return HTTRANSPARENT             # los clics pasan a la ventana de debajo (Dia)
    if msg == WM_MOUSEACTIVATE: return MA_NOACTIVATE         # nunca toma el foco
    return u32.DefWindowProcW(h, msg, wp, lp)


CLASE = "TutorDiaOverlay"
_wc = WNDCLASSW(); _wc.lpfnWndProc = _wndproc; _wc.hInstance = k32.GetModuleHandleW(None); _wc.lpszClassName = CLASE
u32.RegisterClassW(ctypes.byref(_wc))


def cliente(hwnd):
    """(x, y, w, h) físicos del área de cliente de una ventana, o None si ya no existe."""
    if not u32.IsWindow(hwnd): return None
    r = W.RECT(); u32.GetClientRect(hwnd, ctypes.byref(r))
    p = W.POINT(0, 0); u32.ClientToScreen(hwnd, ctypes.byref(p))
    return (p.x, p.y, r.right - r.left, r.bottom - r.top)


def pid_de(hwnd):
    p = W.DWORD(); u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p)); return p.value


def _fuente(px, negrita=True):
    for f in (("segoeuib.ttf" if negrita else "segoeui.ttf"), "arialbd.ttf", "arial.ttf"):
        try: return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", f), px)
        except OSError: continue
    return ImageFont.load_default()


def _choca(a, b, m=0):
    return not (a[2] + m <= b[0] or b[2] + m <= a[0] or a[3] + m <= b[1] or b[3] + m <= a[1])


def componer(marcas, ancho, alto, s):
    """Dibuja las marcas de UNA ventana. marcas: [{"r": (x0, y0, x1, y1) en píxeles de su cliente, "texto", "color", "n"}].
    Devuelve (imagen RGBA recortada, (dx, dy) de su esquina en el cliente) o (None, None)."""
    if not marcas: return None, None
    S = 2                                             # se dibuja al doble y se reduce: bordes suaves
    f = _fuente(int(15 * s * S)); fn = _fuente(int(13 * s * S))
    pad, borde, grosor = 9 * s, 2.4 * s, 3.2 * s
    cajas, ocupado = [], [m["r"] for m in marcas]
    for m in marcas:                                  # lo que no hay que tapar con las notas: los demás botones, pestañas y campos
        for e in m.get("evitar") or []:
            if not _choca(e, m["r"]) and (e[2] - e[0]) * (e[3] - e[1]) < 0.2 * ancho * alto: ocupado.append(e)
    for m in marcas:
        x0, y0, x1, y1 = m["r"]; col = COLORES.get(m.get("color"), COLORES["azul"])
        texto = ((f"{m['n']}. " if m.get("n") else "") + (m.get("texto") or "")).strip()
        nota = None
        if texto:
            tw = f.getlength(texto) / S; th = 15 * s * 1.25
            w, h = tw + 2 * pad, th + 1.3 * pad
            cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
            cands = [c for k in (46, 110, 190, 300) for c in (
                (x1 + k * s, cy - h / 2), (cx - w / 2, y1 + k * 0.8 * s), (x0 - k * s - w, cy - h / 2), (cx - w / 2, y0 - k * 0.8 * s - h),
                (x1 + k * s, y1 + 20 * s), (x1 + k * s, y0 - 20 * s - h), (x0 - k * s - w, y1 + 20 * s), (x0 - k * s - w, y0 - 20 * s - h))]
            for nx, ny in cands:
                c = (nx, ny, nx + w, ny + h)
                if c[0] >= 2 and c[1] >= 2 and c[2] <= ancho - 2 and c[3] <= alto - 2 and not any(_choca(c, o, 6 * s) for o in ocupado):
                    nota = c; break
            if nota is None:                          # no hay hueco: a la derecha, recortado por la ventana
                nx = min(max(2, x1 + 46 * s), ancho - w - 2); ny = min(max(2, cy - h / 2), alto - h - 2); nota = (nx, ny, nx + w, ny + h)
            ocupado.append(nota)
        cajas.append((m, col, texto, nota))
    # el recorte: todo lo dibujado, con margen
    xs = [v for m, _, _, n in cajas for v in (m["r"][0], m["r"][2]) + ((n[0], n[2]) if n else ())]
    ys = [v for m, _, _, n in cajas for v in (m["r"][1], m["r"][3]) + ((n[1], n[3]) if n else ())]
    m0 = 14 * s
    bx0, by0 = max(0, int(min(xs) - m0)), max(0, int(min(ys) - m0))
    bx1, by1 = min(ancho, int(max(xs) + m0)), min(alto, int(max(ys) + m0))
    if bx1 <= bx0 or by1 <= by0: return None, None
    img = Image.new("RGBA", ((bx1 - bx0) * S, (by1 - by0) * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    T = lambda x, y: ((x - bx0) * S, (y - by0) * S)
    for m, col, texto, nota in cajas:
        x0, y0, x1, y1 = m["r"]; g = 4 * s
        a, b = T(x0 - g, y0 - g), T(x1 + g, y1 + g)
        d.rounded_rectangle([a, b], radius=6 * s * S, outline=col + (255,), width=max(1, int(grosor * S)))
        if not nota: continue
        nx0, ny0, nx1, ny1 = nota
        # flecha: del borde de la nota más cercano al objetivo hasta el borde del marco
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        px = min(max(cx, nx0), nx1); py = min(max(cy, ny0), ny1)
        if nx0 < cx < nx1 and ny0 < cy < ny1: px, py = nx0, (ny0 + ny1) / 2
        tx = min(max(px, x0 - g), x1 + g); ty = min(max(py, y0 - g), y1 + g)
        vx, vy = tx - px, ty - py; L = max(1e-6, (vx * vx + vy * vy) ** 0.5); ux, uy = vx / L, vy / L
        punta = 13 * s; ex, ey = tx - ux * 2 * s, ty - uy * 2 * s
        d.line([T(px, py), T(ex - ux * punta * 0.8, ey - uy * punta * 0.8)], fill=col + (255,), width=max(1, int(grosor * S)))
        izq = (ex - ux * punta - uy * punta * 0.55, ey - uy * punta + ux * punta * 0.55)
        der = (ex - ux * punta + uy * punta * 0.55, ey - uy * punta - ux * punta * 0.55)
        d.polygon([T(ex, ey), T(*izq), T(*der)], fill=col + (255,))
        fondo = tuple(int(255 - (255 - c) * 0.10) for c in col) + (246,)
        d.rounded_rectangle([T(nx0, ny0), T(nx1, ny1)], radius=7 * s * S, fill=fondo, outline=col + (255,), width=max(1, int(borde * S)))
        d.text(T(nx0 + pad, ny0 + 0.55 * pad), texto, font=f, fill=col + (255,))
    img = img.resize((bx1 - bx0, by1 - by0), Image.LANCZOS)
    return img, (bx0, by0)


class Capa:
    """La ventana transparente que va encima de UNA ventana de Dia."""

    def __init__(self, objetivo):
        self.objetivo, self.img, self.dxy, self.visible, self.donde = objetivo, None, None, False, None
        self.hwnd = u32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE,
                                        CLASE, "Tutor de Dia (flechas)", WS_POPUP, 0, 0, 1, 1, None, None, _wc.hInstance, None)

    def poner(self, img, dxy):
        self.img, self.dxy, self.donde = img, dxy, None
        self.pintar()

    def pintar(self):
        c = cliente(self.objetivo)
        if not c or self.img is None: return
        x, y = c[0] + self.dxy[0], c[1] + self.dxy[1]
        w, h = self.img.size
        datos = self.img.tobytes("raw", "BGRa")      # BGRA premultiplicado, lo que pide UpdateLayeredWindow
        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        pantalla = u32.GetDC(None); mem = g32.CreateCompatibleDC(pantalla)
        bits = ctypes.c_void_p()
        bmp = g32.CreateDIBSection(mem, ctypes.byref(bi), 0, ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, datos, len(datos))
        viejo = g32.SelectObject(mem, bmp)
        bl = BLENDFUNCTION(AC_SRC_OVER, 0, 255, AC_SRC_ALPHA)
        u32.UpdateLayeredWindow(self.hwnd, pantalla, ctypes.byref(W.POINT(x, y)), ctypes.byref(W.SIZE(w, h)), mem, ctypes.byref(W.POINT(0, 0)), 0, ctypes.byref(bl), ULW_ALPHA)
        g32.SelectObject(mem, viejo); g32.DeleteObject(bmp); g32.DeleteDC(mem); u32.ReleaseDC(None, pantalla)
        self.donde = (x, y)

    def seguir(self, mostrar, debajo_de=None):
        """Cada 50 ms: sigue a su ventana y se esconde o se muestra. `debajo_de`: la ventana del panel (también siempre
        encima): la capa se pone justo debajo de ella, para no tapar el panel si Dia queda por detrás."""
        z = W.HWND(debajo_de) if debajo_de else HWND_TOPMOST
        c = cliente(self.objetivo)
        ver = bool(mostrar and c and self.img is not None and u32.IsWindowVisible(self.objetivo) and not u32.IsIconic(self.objetivo))
        if c and self.img is not None:               # sigue a su ventana aunque esté escondida
            x, y = c[0] + self.dxy[0], c[1] + self.dxy[1]
            if self.donde != (x, y):
                u32.SetWindowPos(self.hwnd, z, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE); self.donde = (x, y)
        if ver:
            if not self.visible:
                u32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
                u32.SetWindowPos(self.hwnd, z, x, y, 0, 0, SWP_NOSIZE | SWP_NOACTIVATE); self.visible = True
        elif self.visible:
            u32.ShowWindow(self.hwnd, SW_HIDE); self.visible = False
        return c is not None

    def cerrar(self):
        u32.DestroyWindow(self.hwnd)


class Overlay:
    def __init__(self):
        self.capas, self.pids, self.cola, self.panel = {}, set(), queue.Queue(), None

    def mostrar(self, marcas, pids=(), panel=None):
        self.pids = {int(p) for p in pids if p} or self.pids
        if panel: self.panel = int(panel)
        por_ventana = {}
        for m in marcas:
            try: por_ventana.setdefault(int(m["hwnd"]), []).append(m)
            except (KeyError, TypeError, ValueError): continue
        for h in [h for h in self.capas if h not in por_ventana]: self.capas.pop(h).cerrar()
        dibujadas, escalas = 0, []
        for h, ms in por_ventana.items():
            c = cliente(h)
            if not c: continue
            gx, gy, gw, gh = ms[0]["ventana"]
            s = c[2] / gw if gw else 1.0                  # píxeles físicos por píxel de GTK (escala de Windows si Dia no la conoce)
            sy = c[3] / gh if gh else s
            escalas.append(round(s, 3))
            locales = []
            for m in ms:
                x, y, w, hh = m["rect"]
                locales.append({"r": ((x - gx) * s, (y - gy) * sy, (x - gx + w) * s, (y - gy + hh) * sy), "texto": m.get("texto", ""),
                                "color": m.get("color", "azul"), "n": m.get("n"),
                                "evitar": [((a - gx) * s, (b - gy) * sy, (a - gx + c) * s, (b - gy + e) * sy) for a, b, c, e in m.get("evitar") or []]})
            dpi = u32.GetDpiForWindow(h) if hasattr(u32, "GetDpiForWindow") else 96
            img, dxy = componer(locales, c[2], c[3], max(1.0, (dpi or 96) / 96))
            if img is None: continue
            capa = self.capas.get(h) or Capa(h)
            self.capas[h] = capa; capa.poner(img, dxy); dibujadas += len(ms)
        self.tic()
        return {"ok": True, "dibujadas": dibujadas, "ventanas": len(self.capas), "escalas": escalas,
                "capas": [{"objetivo": h, "overlay": c.hwnd, "en": c.donde, "tam": c.img.size if c.img else None} for h, c in self.capas.items()]}

    def borrar(self):
        for c in self.capas.values(): c.cerrar()
        self.capas = {}
        return {"ok": True}

    def tic(self):
        fg = u32.GetForegroundWindow()
        mostrar = not self.pids or (fg and pid_de(fg) in self.pids)
        debajo = self.panel if self.panel and u32.IsWindow(self.panel) else None
        for h in [h for h, c in self.capas.items() if not c.seguir(mostrar, debajo)]: self.capas.pop(h).cerrar()

    def estado(self):
        return {"ok": True, "capas": [{"objetivo": h, "overlay": c.hwnd, "visible": c.visible, "en": c.donde} for h, c in self.capas.items()]}

    def volcar(self, carpeta):
        """Para las pruebas: guarda el dibujo de cada capa (PNG) y dónde está en la pantalla."""
        out = []
        for h, c in self.capas.items():
            if c.img is None: continue
            ruta = os.path.join(carpeta, f"capa_{h}.png"); c.img.save(ruta)
            out.append({"objetivo": h, "png": ruta, "en": c.donde, "visible": c.visible})
        return {"ok": True, "capas": out}


def _leer(cola):
    for linea in sys.stdin:
        cola.put(linea)
    cola.put('{"cmd": "salir"}')


def main():
    try: sys.stdout.reconfigure(encoding="utf-8"); sys.stdin.reconfigure(encoding="utf-8")
    except Exception: pass
    ov = Overlay()
    threading.Thread(target=_leer, args=(ov.cola,), daemon=True).start()
    msg = W.MSG()
    print(json.dumps({"ok": True, "listo": True, "pillow": Image is not None}), flush=True)
    while True:
        while u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
            u32.TranslateMessage(ctypes.byref(msg)); u32.DispatchMessageW(ctypes.byref(msg))
        try: linea = ov.cola.get(timeout=0.05)
        except queue.Empty: linea = None
        if linea:
            try:
                o = json.loads(linea); cmd = o.get("cmd")
                if cmd == "salir": ov.borrar(); print(json.dumps({"ok": True, "adios": True}), flush=True); return
                if Image is None and cmd == "mostrar": r = {"ok": False, "error": "falta Pillow (python -m pip install pillow)"}
                elif cmd == "mostrar": r = ov.mostrar(o.get("marcas") or [], o.get("pids") or [], o.get("panel"))
                elif cmd == "borrar": r = ov.borrar()
                elif cmd == "estado": r = ov.estado()
                elif cmd == "volcar": r = ov.volcar(o["carpeta"])
                else: r = {"ok": False, "error": f"orden desconocida {cmd!r}"}
            except Exception as e:
                r = {"ok": False, "error": str(e)}
            try: print(json.dumps(r), flush=True)
            except (OSError, ValueError): ov.borrar(); return      # el panel se cerró: se van las flechas con él
        ov.tic()


if __name__ == "__main__":
    main()
