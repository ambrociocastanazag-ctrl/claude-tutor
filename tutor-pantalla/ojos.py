"""Los «ojos» del tutor: ver UNA ventana y saber dónde está cada botón.

- listar_ventanas(): las ventanas abiertas que se pueden elegir (título, app, si está minimizada).
- miniatura(hwnd): una vista chica para la lista (solo se muestra en el panel; nunca se manda a nadie).
- capturar(hwnd): una Captura de ESA ventana sola, con PrintWindow (sale bien aunque otra ventana la tape).
  Si la app sale en negro con PrintWindow, recorta su rectángulo de la pantalla, pero solo si nada la tapa
  (si algo la tapa, lanza Tapada: no se cuela lo que haya encima).
- Captura.controles: botones, menús, pestañas y campos que da UI Automation, con su caja en píxeles de la captura.

Todo en píxeles físicos (el proceso es consciente de la escala por monitor): con Windows al 125 % las cajas de
UI Automation, la captura y el overlay hablan las mismas coordenadas.

Pruebas sueltas:
  python ojos.py --lista
  python ojos.py --capturar "Word" salida.png     (la primera ventana cuyo título o app contenga el texto)"""
import base64, ctypes, io, sys, time
from ctypes import wintypes as W

from PIL import Image, ImageGrab

# DLL propias (no ctypes.windll): uiautomation cambia los argtypes de las compartidas y los HBITMAP de 64 bits fallaban.
u32, g32, k32, dwm = (ctypes.WinDLL(n, use_last_error=True) for n in ("user32", "gdi32", "kernel32", "dwmapi"))
try: u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))     # por monitor v2: coordenadas físicas
except Exception:
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception: pass

LADO_MAX = 1400            # lado largo de la imagen que se manda (más grande gasta más y no se ve mejor)
GW_OWNER, GA_ROOT, WS_EX_TOOLWINDOW, GWL_EXSTYLE = 4, 2, 0x80, -20
DWMWA_EXTENDED_FRAME_BOUNDS, DWMWA_CLOAKED, PW_RENDERFULLCONTENT = 9, 14, 2
EnumProc = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
u32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
u32.GetWindowLongPtrW.argtypes = [W.HWND, ctypes.c_int]
u32.GetWindow.restype = W.HWND
u32.GetAncestor.restype = W.HWND
u32.WindowFromPoint.restype = W.HWND
u32.WindowFromPoint.argtypes = [W.POINT]
u32.GetForegroundWindow.restype = W.HWND
u32.GetWindowDC.restype = W.HDC
g32.CreateCompatibleDC.restype = W.HDC
g32.CreateCompatibleBitmap.restype = W.HBITMAP
g32.SelectObject.restype = W.HGDIOBJ
g32.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
g32.CreateCompatibleDC.argtypes = [W.HDC]
g32.CreateCompatibleBitmap.argtypes = [W.HDC, ctypes.c_int, ctypes.c_int]
g32.GetDIBits.argtypes = [W.HDC, W.HBITMAP, W.UINT, W.UINT, ctypes.c_void_p, ctypes.c_void_p, W.UINT]
g32.DeleteObject.argtypes = [W.HGDIOBJ]
g32.DeleteDC.argtypes = [W.HDC]
u32.GetDC.restype = W.HDC
u32.GetDC.argtypes = [W.HWND]
u32.ReleaseDC.argtypes = [W.HWND, W.HDC]
u32.PrintWindow.argtypes = [W.HWND, W.HDC, W.UINT]

# Tipos de UI Automation que sirven para señalar, con su nombre corto en español.
TIPOS = {50000: "botón", 50031: "botón", 50011: "menú", 50019: "pestaña", 50004: "campo", 50003: "lista",
         50002: "casilla", 50013: "opción", 50007: "elemento", 50005: "enlace", 50024: "rama", 50030: "documento",
         50016: "contador", 50015: "deslizador", 50029: "celda", 50035: "encabezado"}
UIA_CAJA, UIA_TIPO, UIA_NOMBRE, UIA_OCULTO = 30001, 30003, 30005, 30022


class Tapada(Exception):
    """La ventana no se puede capturar sin que se cuele otra: hay que traerla al frente."""


class Minimizada(Exception):
    pass


# ---------- Ventanas ----------
def titulo(h):
    n = u32.GetWindowTextLengthW(h); b = ctypes.create_unicode_buffer(n + 1); u32.GetWindowTextW(h, b, n + 1); return b.value


def pid_de(h):
    p = W.DWORD(); u32.GetWindowThreadProcessId(h, ctypes.byref(p)); return p.value


def app_de(pid):
    """Nombre del ejecutable sin .exe (WINWORD, EXCEL, chrome...)."""
    hp = k32.OpenProcess(0x1000, False, pid)              # PROCESS_QUERY_LIMITED_INFORMATION
    if not hp: return ""
    try:
        b = ctypes.create_unicode_buffer(520); n = W.DWORD(520)
        if not k32.QueryFullProcessImageNameW(hp, 0, b, ctypes.byref(n)): return ""
        nombre = b.value.rsplit("\\", 1)[-1]
        return nombre[:-4] if nombre.lower().endswith(".exe") else nombre
    finally: k32.CloseHandle(hp)


def _oculta(h):
    """Las ventanas «cloaked» (apps de otro escritorio virtual, UWP suspendidas) no se ven aunque digan que sí."""
    v = ctypes.c_int(0)
    return dwm.DwmGetWindowAttribute(h, DWMWA_CLOAKED, ctypes.byref(v), ctypes.sizeof(v)) == 0 and v.value != 0


def marco(h):
    """(x0, y0, x1, y1) de lo que se ve de la ventana (sin el borde invisible de Windows 10/11)."""
    r = W.RECT()
    if dwm.DwmGetWindowAttribute(h, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r), ctypes.sizeof(r)) != 0:
        u32.GetWindowRect(h, ctypes.byref(r))
    return r.left, r.top, r.right, r.bottom


def cliente(h):
    """(x, y, w, h) físicos del área de cliente (lo que pide el overlay), o None si ya no existe."""
    if not u32.IsWindow(h): return None
    r = W.RECT(); u32.GetClientRect(h, ctypes.byref(r))
    p = W.POINT(0, 0); u32.ClientToScreen(h, ctypes.byref(p))
    return (p.x, p.y, r.right - r.left, r.bottom - r.top)


def listar_ventanas(excluir_pids=()):
    """Ventanas de primer nivel que la persona ve en la barra de tareas, de la más reciente a la más vieja."""
    excluir, out = set(excluir_pids), []

    def cada(h, _):
        if not u32.IsWindowVisible(h) or u32.GetWindow(h, GW_OWNER) or _oculta(h): return True
        if u32.GetWindowLongPtrW(h, GWL_EXSTYLE) & WS_EX_TOOLWINDOW: return True
        t = titulo(h); pid = pid_de(h)
        if not t.strip() or pid in excluir or t == "Program Manager": return True
        x0, y0, x1, y1 = marco(h); mini = bool(u32.IsIconic(h))
        if not mini and (x1 - x0 < 60 or y1 - y0 < 40): return True
        out.append({"hwnd": int(h), "titulo": t, "app": app_de(pid), "pid": pid, "minimizada": mini})
        return True

    u32.EnumWindows(EnumProc(cada), 0)
    return out


def ventanas_de(pid):
    """Todas las ventanas visibles de primer nivel de un proceso, sin filtros (el panel propio, por ejemplo)."""
    out = []
    u32.EnumWindows(EnumProc(lambda h, _: (u32.IsWindowVisible(h) and pid_de(h) == pid and out.append(int(h))) or True), 0)
    return out


# ---------- Captura ----------
def _printwindow(h):
    """Imagen de la ventana entera (su rectángulo de GetWindowRect) y la esquina de ese rectángulo."""
    r = W.RECT(); u32.GetWindowRect(h, ctypes.byref(r))
    w, hh = r.right - r.left, r.bottom - r.top
    if w <= 0 or hh <= 0: raise Minimizada("La ventana no tiene tamaño.")
    pantalla = u32.GetDC(None); mem = g32.CreateCompatibleDC(pantalla)
    bmp = g32.CreateCompatibleBitmap(pantalla, w, hh); viejo = g32.SelectObject(mem, bmp)
    try:
        u32.PrintWindow(h, mem, PW_RENDERFULLCONTENT)
        bi = (ctypes.c_uint32 * 10)(40, w, ctypes.c_uint32(-hh).value, 1 | (32 << 16), 0, 0, 0, 0, 0, 0)   # BITMAPINFOHEADER
        buf = ctypes.create_string_buffer(w * hh * 4)
        g32.GetDIBits(mem, bmp, 0, hh, buf, bi, 0)
        img = Image.frombuffer("RGB", (w, hh), buf, "raw", "BGRX", 0, 1)
    finally:
        g32.SelectObject(mem, viejo); g32.DeleteObject(bmp); g32.DeleteDC(mem); u32.ReleaseDC(None, pantalla)
    return img, (r.left, r.top)


def _negra(img):
    return img.resize((48, 48)).convert("L").getextrema()[1] < 14


def _tapada(h, caja, ignorar_pids=()):
    """¿Hay otra ventana encima de alguna parte de `caja`? Se mira una rejilla de 9×9 puntos."""
    x0, y0, x1, y1 = caja; ign = set(ignorar_pids)
    for i in range(9):
        for j in range(9):
            p = W.POINT(int(x0 + (i + .5) * (x1 - x0) / 9), int(y0 + (j + .5) * (y1 - y0) / 9))
            w = u32.WindowFromPoint(p)
            raiz = u32.GetAncestor(w, GA_ROOT) if w else None
            if raiz and int(raiz) != int(h) and pid_de(raiz) not in ign: return True
    return False


def imagen_de(h, ignorar_pids=()):
    """(imagen PIL de lo que se ve de la ventana, (x, y) de su esquina en la pantalla, cómo se sacó)."""
    if u32.IsIconic(h): raise Minimizada("La ventana está minimizada: ábrela para que el tutor la vea.")
    img, (l, t) = _printwindow(h)
    x0, y0, x1, y1 = marco(h)
    img = img.crop((x0 - l, y0 - t, x1 - l, y1 - t))
    if not _negra(img): return img, (x0, y0), "printwindow"
    # Algunas apps (juegos, vídeo, ciertas apps con GPU) salen en negro: se recorta su rectángulo de la pantalla,
    # solo si nada la tapa (el panel y el overlay propios no cuentan: el overlay no tapa clics y se ve encima igual).
    if _tapada(h, (x0, y0, x1, y1), ignorar_pids):
        raise Tapada("Esta app no deja capturarla por detrás: tráela al frente (que no la tape nada) y vuelve a intentarlo.")
    return ImageGrab.grab(bbox=(x0, y0, x1, y1), all_screens=True).convert("RGB"), (x0, y0), "pantalla"


def miniatura(h, ancho=280):
    """PNG en base64 (data URL) para la lista de ventanas, o None si está minimizada o no se puede."""
    try:
        if u32.IsIconic(h): return None
        img, _, _ = imagen_de(h)
    except Exception:
        return None
    img.thumbnail((ancho, ancho * 0.7))
    return a_data_url(img, "JPEG")


def a_data_url(img, formato="PNG"):
    b = io.BytesIO(); img.save(b, formato, **({"quality": 85} if formato == "JPEG" else {}))
    return f"data:image/{formato.lower()};base64," + base64.b64encode(b.getvalue()).decode()


def leer_controles(h, caja, limite=400):
    """[(tipo, nombre, (x0, y0, x1, y1) en la pantalla)] de UI Automation, solo lo visible dentro de `caja`.
    Se piden todos de una vez con una caché (nombre, tipo, caja, si está oculto): recorrer el árbol control por
    control tarda segundos por cada pocos botones (en Word, 6 s y ni llegaba a la cinta); así, unos 2 s."""
    try:
        import uiautomation as auto
        import uiautomation.uiautomation as uia
    except ImportError:
        return []
    x0, y0, x1, y1 = caja; out = []
    try:
        with auto.UIAutomationInitializerInThread():
            ia = uia._AutomationClient.instance().IUIAutomation
            cr = ia.CreateCacheRequest()
            for p in (UIA_NOMBRE, UIA_TIPO, UIA_CAJA, UIA_OCULTO): cr.AddProperty(p)
            raiz = ia.ElementFromHandle(h)
            els = raiz.FindAllBuildCache(4, ia.CreateTrueCondition(), cr)        # 4 = TreeScope_Descendants
            for i in range(els.Length):
                e = els.GetElement(i)
                tipo = TIPOS.get(e.CachedControlType)
                if not tipo or e.CachedIsOffscreen: continue
                nombre = (e.CachedName or "").strip().replace("\n", " ")
                if not nombre: continue
                r = e.CachedBoundingRectangle
                if r.right - r.left < 4 or r.bottom - r.top < 4: continue
                if r.right <= x0 or r.left >= x1 or r.bottom <= y0 or r.top >= y1: continue
                out.append((tipo, nombre[:70], (max(r.left, x0), max(r.top, y0), min(r.right, x1), min(r.bottom, y1))))
                if len(out) >= limite: break
    except Exception:
        pass
    return out


class Captura:
    """Lo que vio el tutor de una ventana: la imagen reducida y los controles en píxeles de esa imagen.
    k: píxeles de la imagen por píxel físico. origen: dónde cae el (0, 0) de la imagen en la pantalla."""

    def __init__(self, hwnd, img, origen, controles_pantalla, como):
        self.hwnd, self.como = int(hwnd), como
        self.titulo, self.pid = titulo(hwnd), pid_de(hwnd)
        self.app = app_de(self.pid)
        k = min(1.0, LADO_MAX / max(img.size))
        self.k, self.origen, self.marco0 = k, origen, marco(hwnd)[:2]
        self.img = img.resize((round(img.width * k), round(img.height * k)), Image.LANCZOS) if k < 1 else img
        ox, oy = origen
        self.controles = [{"id": i + 1, "tipo": t, "nombre": n,
                           "caja": [round((a - ox) * k), round((b - oy) * k), round((c - a) * k), round((d - b) * k)]}
                          for i, (t, n, (a, b, c, d)) in enumerate(controles_pantalla)]

    def a_pantalla(self, caja):
        """[x, y, w, h] en píxeles de la imagen → [x, y, w, h] físicos en la pantalla, donde está la ventana AHORA
        (si la movió mientras el tutor pensaba, la marca va con ella)."""
        x, y, w, h = caja
        mx, my = marco(self.hwnd)[:2] if u32.IsWindow(self.hwnd) else self.marco0
        dx, dy = mx - self.marco0[0], my - self.marco0[1]
        return [round(self.origen[0] + dx + x / self.k), round(self.origen[1] + dy + y / self.k), round(w / self.k), round(h / self.k)]

    def recortar(self, x, y, w, h):
        """Se queda solo con [x, y, w, h] (píxeles de la imagen). Los controles de fuera se van."""
        x, y = max(0, int(x)), max(0, int(y))
        w, h = min(int(w), self.img.width - x), min(int(h), self.img.height - y)
        if w < 8 or h < 8: return
        self.img = self.img.crop((x, y, x + w, y + h))
        self.origen = (self.origen[0] + x / self.k, self.origen[1] + y / self.k)
        dentro = []
        for c in self.controles:
            a, b, cw, ch = c["caja"]
            if a + cw <= x or a >= x + w or b + ch <= y or b >= y + h: continue
            a2, b2 = max(a, x), max(b, y)
            dentro.append(dict(c, caja=[a2 - x, b2 - y, min(a + cw, x + w) - a2, min(b + ch, y + h) - b2]))
        self.controles = dentro

    def control(self, cid):
        return next((c for c in self.controles if c["id"] == cid), None)

    def texto_controles(self, maximo=300):
        if not self.controles: return "(Esta ventana no da la lista de controles: guíate solo por la imagen.)"
        filas = [f'{c["id"]} | {c["tipo"]} | {c["nombre"]} | {",".join(map(str, c["caja"]))}' for c in self.controles[:maximo]]
        return "id | tipo | nombre | caja x,y,w,h (píxeles de la captura)\n" + "\n".join(filas)


def capturar(hwnd, ignorar_pids=()):
    img, origen, como = imagen_de(hwnd, ignorar_pids)
    caja = (origen[0], origen[1], origen[0] + img.width, origen[1] + img.height)
    controles = leer_controles(hwnd, caja)
    if len(controles) < 10:
        # Chrome, Brave, Edge y las apps Electron (VS Code...) encienden su accesibilidad la primera vez que alguien
        # la pide: esa primera lectura trae 3 botones y la siguiente, 90.
        time.sleep(0.7); controles = max(controles, leer_controles(hwnd, caja), key=len)
    return Captura(hwnd, img, origen, controles, como)


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    a = sys.argv[1:]
    if a[:1] == ["--lista"]:
        for v in listar_ventanas(): print(v)
    elif a[:1] == ["--capturar"] and len(a) == 3:
        q = a[1].lower()
        v = next((v for v in listar_ventanas() if q in v["titulo"].lower() or q in v["app"].lower()), None)
        if not v: sys.exit(f"No hay ninguna ventana con «{a[1]}».")
        t = time.time(); cap = capturar(v["hwnd"])
        cap.img.save(a[2])
        print(f"{cap.titulo} ({cap.app}): {cap.img.size}, k={cap.k:.3f}, {cap.como}, {len(cap.controles)} controles, {time.time() - t:.1f}s")
        print(cap.texto_controles(40))
    else:
        print(__doc__)
