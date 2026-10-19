"""Señalar y preguntar: la persona encierra con el ratón algo de la app y le pregunta al tutor «¿qué es esto?».

Dos partes en este archivo:

1. El proceso (`python senalar.py <hwnd> [--volcar salida.png]`): una ventana en capas encima del ÁREA DE CLIENTE de esa
   ventana, casi transparente (alfa 1: no se ve, pero recibe el ratón mientras dura), con un aviso arriba. Arrastrar dibuja
   un trazo naranja tipo rotulador; al soltar imprime UNA línea JSON y se cierra:
     {"ok": true, "trazo": [[x, y], ...], "caja": [x, y, w, h]}      (píxeles físicos de CLIENTE de esa ventana)
     {"ok": false, "cancelado": true}                                  (Esc, clic derecho, trazo de menos de ~10 px o 60 s)
   No toma el foco ni guarda nada: solo devuelve el trazo. --volcar guarda además el último fotograma (para las pruebas).

2. El mixin `SenalarApi` (lo que la página llama; la API del panel lo hereda junto con OjosApi):
     senalar_ventana()                 → {ok, hwnd, titulo}: la última ventana que la persona ya enseñó (y sigue abierta)
     senalar_empezar(hwnd)             → la línea JSON de arriba (bloquea hasta que suelta o cancela)
     senalar_capturar(hwnd, trazo)     → lo mismo que ojos_capturar, pero con el trazo ya pintado en la imagen
   El permiso no cambia: la captura va a la vista previa de siempre (Adjuntar / Recortar / Cancelar) y solo sale cuando la
   persona envía el mensaje. La captura lleva `senalado = {"caja": [x, y, w, h] (píxeles de la captura), "trazo": ...}` y su
   texto_controles() añade «Encerró la zona x,y,w,h…; controles dentro: …», así que Ojos.contexto() lo dice sin cambios.

Pruebas: python senalar.py --probar      (sin ratón: pintar el trazo en una captura falsa, la caja y el recorte)"""
import ctypes, json, os, subprocess, sys, time
from ctypes import wintypes as W
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

TIEMPO = 60                         # segundos: a los 60 s se cierra sola
MIN_TRAZO = 10                      # px: un trazo más corto es un clic
NARANJA = (255, 140, 0)
AVISO = "Encierra lo que quieres preguntar  ·  Esc para cancelar"


# =====================================================================================================================
#  Pintar el trazo en una captura (sin ventanas: lo usan el mixin y las pruebas)
# =====================================================================================================================
def pintar_trazo(cap, trazo, cli):
    """Pinta `trazo` (puntos [x, y] de CLIENTE, píxeles físicos) sobre cap.img. cli = (x, y, w, h) físicos del cliente en la
    pantalla. Pasa de cliente a pantalla (+ cli) y de pantalla a la imagen ((p - cap.origen) * cap.k), que puede estar
    reducida y empezar en otro sitio que el cliente. Devuelve la caja encerrada [x, y, w, h] en píxeles de la captura (con un
    poco de margen y sin salirse de la imagen), o None si el trazo no cae dentro."""
    k, (ox, oy) = cap.k, cap.origen
    pts = [((cli[0] + float(p[0]) - ox) * k, (cli[1] + float(p[1]) - oy) * k) for p in trazo]
    if len(pts) < 2: return None
    S = 3                                                        # supersampling: el trazo sale suave
    W_, H_ = cap.img.size
    capa = Image.new("RGBA", (W_ * S, H_ * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(capa)
    ancho = max(3.0, 6 * k) * S
    r = ancho / 2
    sp = [(x * S, y * S) for x, y in pts]
    d.line(sp, fill=NARANJA + (225,), width=round(ancho), joint="curve")
    for x, y in (sp[0], sp[-1]): d.ellipse([x - r, y - r, x + r, y + r], fill=NARANJA + (225,))
    capa = capa.resize((W_, H_), Image.LANCZOS)
    base = cap.img.convert("RGBA"); base.alpha_composite(capa); cap.img = base.convert("RGB")
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    pad = 8
    x0, y0 = max(0, min(xs) - pad), max(0, min(ys) - pad)
    x1, y1 = min(W_, max(xs) + pad), min(H_, max(ys) + pad)
    if x1 - x0 < 4 or y1 - y0 < 4: return None
    return [round(x0), round(y0), round(x1 - x0), round(y1 - y0)]


def controles_dentro(cap, caja, limite=15):
    """Los controles de la captura que caen (al menos la mitad) dentro de la caja, los más chicos primero."""
    x, y, w, h = caja
    out = []
    for c in cap.controles:
        a, b, cw, ch = c["caja"]
        ix, iy = min(a + cw, x + w) - max(a, x), min(b + ch, y + h) - max(b, y)
        if ix > 0 and iy > 0 and ix * iy >= 0.5 * max(1, cw * ch): out.append(c)
    return sorted(out, key=lambda c: c["caja"][2] * c["caja"][3])[:limite]


def marcar_captura(cap, trazo, cli):
    """Pinta el trazo y deja la captura lista para el contexto (atributo `senalado` y texto_controles ampliado).
    Si luego la persona recorta en la vista previa, la caja se corre con el recorte. Devuelve la caja o None."""
    caja = pintar_trazo(cap, trazo, cli)
    if caja is None: return None
    cap.senalado = {"caja": caja, "trazo": [[round(float(p[0])), round(float(p[1]))] for p in trazo][::max(1, len(trazo) // 60)]}
    orig_rec, orig_tc, orig_cmd = cap.recortar, cap.texto_controles, None

    def recortar(x, y, w, h):
        k0, (o0x, o0y) = cap.k, cap.origen
        orig_rec(x, y, w, h)
        dx, dy = (cap.origen[0] - o0x) * k0, (cap.origen[1] - o0y) * k0         # cuánto se corrió el (0, 0) de la imagen
        if dx or dy:
            sx, sy, sw, sh = cap.senalado["caja"]
            nx, ny = max(0, sx - dx), max(0, sy - dy)
            cap.senalado["caja"] = [round(nx), round(ny), round(min(cap.img.width, sx - dx + sw) - nx), round(min(cap.img.height, sy - dy + sh) - ny)]

    def texto_controles(maximo=300):
        x, y, w, h = cap.senalado["caja"]
        dentro = controles_dentro(cap, cap.senalado["caja"])
        lista = ", ".join(f'{c["id"]} «{c["nombre"]}» ({c["tipo"]})' for c in dentro) or "ninguno con nombre (guíate por la imagen)"
        return (orig_tc(maximo) + f"\nSEÑALADO: encerró con el ratón (trazo naranja dibujado en la imagen) la zona {x},{y},{w},{h} "
                f"(píxeles de la captura) y pregunta por lo que hay dentro. Controles dentro: {lista}.")
    cap.recortar, cap.texto_controles = recortar, texto_controles
    return caja


# =====================================================================================================================
#  El mixin de la API
# =====================================================================================================================
class SenalarApi:
    """Lo que la página (senalar_ui.js) llama. Usa solo lo público de self._ojos: capturar, capturas, titulos, aprobadas."""

    def senalar_ventana(self):
        """La última ventana que la persona enseñó en esta sesión y sigue abierta (la que 📷 ya aprobó), o {"ok": False}."""
        import ojos
        o = self._ojos
        for h in reversed(list(getattr(o, "titulos", {}))):
            if h in o.aprobadas and ojos.u32.IsWindow(h):
                return {"ok": True, "hwnd": h, "titulo": o.titulos[h][0]}
        return {"ok": False}

    def senalar_empezar(self, hwnd):
        """Lanza la capa para encerrar y devuelve su línea JSON. Bloquea hasta que suelta, cancela o pasan 60 s."""
        import ojos
        hwnd = int(hwnd)
        if not ojos.u32.IsWindow(hwnd): return {"ok": False, "error": "Esa ventana ya se cerró: elige otra."}
        if ojos.u32.IsIconic(hwnd): return {"ok": False, "error": "La ventana está minimizada: ábrela para poder señalar en ella."}
        self.senalar_cancelar()
        try:
            self._senalar_p = p = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), str(hwnd)], stdout=subprocess.PIPE,
                                                   stderr=subprocess.DEVNULL, text=True, encoding="utf-8",
                                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            salida, _ = p.communicate(timeout=TIEMPO + 15)
        except subprocess.TimeoutExpired:
            p.kill(); return {"ok": False, "cancelado": True}
        except OSError as e:
            return {"ok": False, "error": f"No pude abrir la capa para señalar: {e}"}
        for linea in reversed((salida or "").strip().splitlines()):
            try: return json.loads(linea)
            except ValueError: continue
        return {"ok": False, "cancelado": True}

    def senalar_cancelar(self):
        p = getattr(self, "_senalar_p", None)
        if p is not None and p.poll() is None: p.kill()
        return {"ok": True}

    def senalar_capturar(self, hwnd, trazo):
        """Igual que ojos_capturar, pero con el trazo pintado en la imagen (y anotado lo encerrado para el contexto)."""
        import ojos
        hwnd = int(hwnd)
        try:
            trazo = [[float(p[0]), float(p[1])] for p in (trazo or [])][:6000]
        except (TypeError, ValueError, IndexError):
            trazo = []
        r = self._ojos.capturar(hwnd)
        if not r.get("ok") or len(trazo) < 2: return r
        cap = self._ojos.capturas.get(r["id"])
        cli = ojos.cliente(hwnd)
        if cap is None or not cli: return r
        if marcar_captura(cap, trazo, cli) is None: return r                    # el trazo cayó fuera: queda la captura limpia
        r["img"] = ojos.a_data_url(cap.img, "PNG"); r["w"], r["h"] = cap.img.width, cap.img.height
        r["senalado"] = cap.senalado["caja"]
        return r


# =====================================================================================================================
#  El proceso: la capa que recibe el ratón
# =====================================================================================================================
if os.name == "nt":
    u32, g32, k32 = ctypes.WinDLL("user32", use_last_error=True), ctypes.WinDLL("gdi32", use_last_error=True), ctypes.WinDLL("kernel32", use_last_error=True)

WS_POPUP = 0x80000000
WS_EX_LAYERED, WS_EX_TOPMOST, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = 0x80000, 0x8, 0x80, 0x08000000
WM_MOUSEACTIVATE, WM_MOUSEMOVE, WM_LBUTTONDOWN, WM_LBUTTONUP, WM_RBUTTONDOWN, WM_KEYDOWN, WM_CAPTURECHANGED = 0x21, 0x200, 0x201, 0x202, 0x204, 0x100, 0x215
MA_NOACTIVATE, VK_ESCAPE, IDC_CROSS = 3, 0x1B, 32515
SW_SHOWNOACTIVATE, SWP_NOACTIVATE, SWP_NOMOVE, SWP_NOSIZE, PM_REMOVE, ULW_ALPHA = 4, 0x10, 0x2, 0x1, 1, 2


def _preparar():
    try: u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))         # por monitor v2: píxeles físicos, como los ojos
    except Exception:
        try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception: pass
    LRESULT = ctypes.c_ssize_t
    global WNDPROC, BLENDFUNCTION, BITMAPINFOHEADER, _wc, _wndproc, ESTADO
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, W.HWND, W.UINT, W.WPARAM, W.LPARAM)
    u32.DefWindowProcW.restype = LRESULT
    u32.DefWindowProcW.argtypes = [W.HWND, W.UINT, W.WPARAM, W.LPARAM]
    u32.CreateWindowExW.restype = W.HWND
    u32.CreateWindowExW.argtypes = [W.DWORD, W.LPCWSTR, W.LPCWSTR, W.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                    W.HWND, W.HMENU, W.HINSTANCE, W.LPVOID]
    u32.LoadCursorW.restype = W.HANDLE
    u32.LoadCursorW.argtypes = [W.HINSTANCE, ctypes.c_void_p]
    u32.SetCapture.argtypes = [W.HWND]
    u32.GetDC.restype = W.HDC
    u32.GetDC.argtypes = [W.HWND]
    u32.ReleaseDC.argtypes = [W.HWND, W.HDC]
    u32.SetWindowPos.argtypes = [W.HWND, W.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, W.UINT]
    u32.DestroyWindow.argtypes = [W.HWND]
    u32.ShowWindow.argtypes = [W.HWND, ctypes.c_int]
    u32.IsWindow.argtypes = [W.HWND]
    u32.IsIconic.argtypes = [W.HWND]
    u32.SetForegroundWindow.argtypes = [W.HWND]
    g32.CreateDIBSection.restype = W.HBITMAP
    g32.CreateDIBSection.argtypes = [W.HDC, ctypes.c_void_p, W.UINT, ctypes.POINTER(ctypes.c_void_p), W.HANDLE, W.DWORD]
    g32.SelectObject.restype = W.HGDIOBJ
    g32.SelectObject.argtypes = [W.HDC, W.HGDIOBJ]
    g32.CreateCompatibleDC.restype = W.HDC
    g32.CreateCompatibleDC.argtypes = [W.HDC]
    g32.DeleteObject.argtypes = [W.HGDIOBJ]
    g32.DeleteDC.argtypes = [W.HDC]

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
    ESTADO = {"abajo": False, "trazo": [], "fin": None, "sucio": False, "pendiente": []}

    @WNDPROC
    def proc(h, msg, wp, lp):
        if msg == WM_MOUSEACTIVATE: return MA_NOACTIVATE                # nunca toma el foco
        if msg in (WM_LBUTTONDOWN, WM_MOUSEMOVE, WM_LBUTTONUP, WM_RBUTTONDOWN):
            x, y = ctypes.c_short(lp & 0xFFFF).value, ctypes.c_short((lp >> 16) & 0xFFFF).value
            if msg == WM_RBUTTONDOWN: ESTADO["fin"] = "cancelar"
            elif msg == WM_LBUTTONDOWN:
                ESTADO["abajo"] = True; ESTADO["trazo"] = [(x, y)]; ESTADO["pendiente"] = [(x, y, True)]; u32.SetCapture(h)
            elif msg == WM_MOUSEMOVE and ESTADO["abajo"]:
                ESTADO["trazo"].append((x, y)); ESTADO["pendiente"].append((x, y, False))
            elif msg == WM_LBUTTONUP and ESTADO["abajo"]:
                ESTADO["abajo"] = False; ESTADO["trazo"].append((x, y)); ESTADO["pendiente"].append((x, y, False))
                u32.ReleaseCapture(); ESTADO["fin"] = "soltar"
            return 0
        return u32.DefWindowProcW(h, msg, wp, lp)
    _wndproc = proc
    _wc = _WC(); _wc.lpfnWndProc = _wndproc; _wc.hInstance = k32.GetModuleHandleW(None); _wc.lpszClassName = "TutorSenalar"
    _wc.hCursor = u32.LoadCursorW(None, IDC_CROSS)
    u32.RegisterClassW(ctypes.byref(_wc))


def _fuente(px):
    for n in ("segoeui.ttf", "arial.ttf"):
        try: return ImageFont.truetype(n, px)
        except OSError: continue
    try: return ImageFont.load_default(px)
    except TypeError: return ImageFont.load_default()


def fondo(w, h, escala):
    """El fotograma inicial: todo con alfa 1 (invisible, pero recibe el ratón), un filo naranja fino alrededor y el aviso arriba."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 1))
    d = ImageDraw.Draw(img)
    g = max(2, round(2 * escala))
    d.rectangle([0, 0, w - 1, h - 1], outline=NARANJA + (170,), width=g)
    f = _fuente(round(15 * escala))
    tb = d.textbbox((0, 0), AVISO, font=f)
    tw, th = tb[2] - tb[0], tb[3] - tb[1]
    px, py = round(16 * escala), round(9 * escala)
    pw, ph = tw + 2 * px + round(14 * escala), th + 2 * py
    x0, y0 = (w - pw) // 2, round(14 * escala)
    d.rounded_rectangle([x0, y0, x0 + pw, y0 + ph], radius=ph // 2, fill=(28, 30, 38, 240), outline=NARANJA + (255,), width=max(1, round(1.5 * escala)))
    d.ellipse([x0 + px - round(2 * escala), y0 + ph // 2 - round(4 * escala), x0 + px + round(6 * escala), y0 + ph // 2 + round(4 * escala)], fill=NARANJA + (255,))
    d.text((x0 + px + round(14 * escala), y0 + py - tb[1]), AVISO, font=f, fill=(255, 255, 255, 255))
    return img


class Pantalla:
    """La ventana en capas y su bitmap (se crea una vez; cada fotograma solo copia los píxeles)."""

    def __init__(self, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.hwnd = u32.CreateWindowExW(WS_EX_LAYERED | WS_EX_TOPMOST | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE, _wc.lpszClassName,
                                        "Tutor (señalar)", WS_POPUP, x, y, w, h, None, None, _wc.hInstance, None)
        self.pantalla = u32.GetDC(None); self.mem = g32.CreateCompatibleDC(self.pantalla)
        bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
        self.bits = ctypes.c_void_p()
        self.bmp = g32.CreateDIBSection(self.mem, ctypes.byref(bi), 0, ctypes.byref(self.bits), None, 0)
        self.viejo = g32.SelectObject(self.mem, self.bmp)

    def poner(self, img):
        datos = img.tobytes("raw", "BGRa")                  # BGRA premultiplicado, lo que pide UpdateLayeredWindow
        ctypes.memmove(self.bits, datos, len(datos))
        bl = BLENDFUNCTION(0, 0, 255, 1)
        u32.UpdateLayeredWindow(self.hwnd, self.pantalla, ctypes.byref(W.POINT(self.x, self.y)), ctypes.byref(W.SIZE(self.w, self.h)),
                                self.mem, ctypes.byref(W.POINT(0, 0)), 0, ctypes.byref(bl), ULW_ALPHA)

    def mostrar(self):
        u32.ShowWindow(self.hwnd, SW_SHOWNOACTIVATE)
        u32.SetWindowPos(self.hwnd, W.HWND(-1), 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)

    def cerrar(self):
        g32.SelectObject(self.mem, self.viejo); g32.DeleteObject(self.bmp); g32.DeleteDC(self.mem); u32.ReleaseDC(None, self.pantalla)
        u32.DestroyWindow(self.hwnd)


def _cliente(hwnd):
    r = W.RECT(); u32.GetClientRect(hwnd, ctypes.byref(r))
    p = W.POINT(0, 0); u32.ClientToScreen(hwnd, ctypes.byref(p))
    return p.x, p.y, r.right - r.left, r.bottom - r.top


def resultado(trazo):
    """El trazo de la mano → la respuesta JSON (o cancelado si es un clic o casi)."""
    if len(trazo) < 2: return {"ok": False, "cancelado": True}
    xs, ys = [p[0] for p in trazo], [p[1] for p in trazo]
    if max(max(xs) - min(xs), max(ys) - min(ys)) < MIN_TRAZO: return {"ok": False, "cancelado": True}
    paso = max(1, len(trazo) // 400)                                       # a lo más ~400 puntos
    pts = [[int(x), int(y)] for x, y in trazo[::paso]]
    if pts[-1] != [int(trazo[-1][0]), int(trazo[-1][1])]: pts.append([int(trazo[-1][0]), int(trazo[-1][1])])
    return {"ok": True, "trazo": pts, "caja": [min(xs), min(ys), max(xs) - min(xs), max(ys) - min(ys)]}


def correr(hwnd, volcar=None):
    if Image is None: return {"ok": False, "error": "falta Pillow (python -m pip install pillow)"}
    _preparar()
    if not u32.IsWindow(hwnd): return {"ok": False, "error": "esa ventana ya no existe"}
    if u32.IsIconic(hwnd): return {"ok": False, "error": "la ventana está minimizada"}
    x, y, w, h = _cliente(hwnd)
    if w < 40 or h < 40: return {"ok": False, "error": "la ventana es muy chica"}
    try: escala = (u32.GetDpiForWindow(hwnd) or 96) / 96
    except Exception: escala = 1.0
    try: u32.SetForegroundWindow(hwnd)                                    # que la app quede delante de lo que la tape
    except Exception: pass
    time.sleep(0.15)
    x, y, w, h = _cliente(hwnd)
    frame = fondo(w, h, escala)
    pan = Pantalla(x, y, w, h)
    pan.poner(frame); pan.mostrar()
    d = ImageDraw.Draw(frame)
    ancho = max(4, round(6 * escala)); r = ancho / 2
    t0, msg, ultimo = time.monotonic(), W.MSG(), None
    try:
        while True:
            while u32.PeekMessageW(ctypes.byref(msg), None, 0, 0, PM_REMOVE):
                u32.TranslateMessage(ctypes.byref(msg)); u32.DispatchMessageW(ctypes.byref(msg))
            ahora = time.monotonic() - t0
            if ahora > TIEMPO: return {"ok": False, "cancelado": True, "tiempo": True}
            if not u32.IsWindow(hwnd): return {"ok": False, "cancelado": True}
            if ahora > 0.4 and (u32.GetAsyncKeyState(VK_ESCAPE) & 0x8000): return {"ok": False, "cancelado": True}
            pend, ESTADO["pendiente"] = ESTADO["pendiente"], []
            for x_, y_, inicio in pend:                                    # el trazo, segmento a segmento
                if ultimo is not None and not inicio:
                    d.line([ultimo, (x_, y_)], fill=NARANJA + (225,), width=round(ancho))
                d.ellipse([x_ - r, y_ - r, x_ + r, y_ + r], fill=NARANJA + (225,))
                ultimo = (x_, y_); ESTADO["sucio"] = True
            if ESTADO["sucio"]: pan.poner(frame); ESTADO["sucio"] = False
            if ESTADO["fin"] == "cancelar": return {"ok": False, "cancelado": True}
            if ESTADO["fin"] == "soltar": return resultado(ESTADO["trazo"])
            time.sleep(0.008)
    finally:
        if volcar:
            try: frame.save(volcar)
            except Exception: pass
        pan.cerrar()


# =====================================================================================================================
#  Pruebas
# =====================================================================================================================
def probar():
    """python senalar.py --probar: lo que no necesita ratón."""
    import ojos
    malos = 0

    def ver(c, txt):
        nonlocal malos
        malos += not c; print("✔" if c else "✘", txt)

    def nueva():
        c = object.__new__(ojos.Captura)                                  # una Captura sin ventana
        c.hwnd, c.pid, c.titulo, c.app, c.como = 0, 0, "Bloc de notas", "notepad", "printwindow"
        c.k, c.origen, c.marco0 = 0.5, (1000, 500), (1000, 500)           # imagen a la mitad, esquina corrida
        c.img = Image.new("RGB", (600, 400), (255, 255, 255))
        c.controles = [{"id": 1, "tipo": "botón", "nombre": "Guardar", "caja": [160, 90, 40, 30]},
                       {"id": 2, "tipo": "campo", "nombre": "Texto", "caja": [10, 300, 300, 60]},
                       {"id": 3, "tipo": "menú", "nombre": "Archivo", "caja": [150, 70, 80, 20]}]
        return c
    cli = (1100, 560, 800, 600)             # cliente en la pantalla: su (0, 0) cae en (50, 30) de la imagen (k = 0.5)
    rect = [[200, 100], [400, 100], [400, 300], [200, 300], [200, 100]]           # cliente → imagen: (150,80)-(250,180)

    c = nueva(); caja = pintar_trazo(c, rect, cli)
    px = lambda x, y: c.img.getpixel((x, y))
    naranja = lambda p: p[0] > 220 and 90 < p[1] < 190 and p[2] < 120
    ver(naranja(px(150, 130)) and naranja(px(250, 130)) and naranja(px(200, 80)) and naranja(px(200, 180)),
        "el trazo cae en la imagen donde debe (escala 0.5 y origen corrido): los cuatro lados del rectángulo")
    ver(px(50, 30) == (255, 255, 255) and px(200, 130) == (255, 255, 255) and px(400, 300) == (255, 255, 255),
        "…y no mancha ni la esquina del cliente, ni el centro, ni lo que queda fuera")
    ver(caja is not None and abs(caja[0] - 142) <= 1 and abs(caja[1] - 72) <= 1 and abs(caja[2] - 116) <= 1 and abs(caja[3] - 116) <= 1,
        f"la caja encerrada es [142, 72, 116, 116] (con margen): {caja}")
    ver(pintar_trazo(nueva(), [[5000, 5000], [5100, 5100]], cli) is None, "un trazo que cae fuera de la imagen no devuelve caja")

    c = nueva(); marcar_captura(c, rect, cli)
    t = c.texto_controles()
    ver("SEÑALADO" in t and "Guardar" in t and "Archivo" in t and "Texto" not in t.split("Controles dentro:")[1],
        "texto_controles() añade lo señalado y solo los controles de dentro (Guardar y Archivo, no el campo de abajo)")
    ver(c.senalado["caja"] == caja or c.senalado["caja"][2] == 116, "la captura guarda `senalado` con la caja")
    c.recortar(100, 50, 200, 150)                                          # la persona recorta en la vista previa
    x, y, w, h = c.senalado["caja"]
    ver(c.img.size == (200, 150) and abs(x - 42) <= 1 and abs(y - 22) <= 1 and w == 116 and h == 116,
        f"al recortar, la caja se corre con el recorte: {c.senalado['caja']}")
    ver(naranja(c.img.getpixel((50, 80))), "…y el trazo sigue pintado en la imagen recortada")
    ver("Guardar" in c.texto_controles(), "…y el contexto sigue diciendo los controles que quedaron dentro")

    ver(resultado([(5, 5), (8, 7)]) == {"ok": False, "cancelado": True} and resultado([(5, 5)]) == {"ok": False, "cancelado": True},
        "un clic o un trazo de menos de 10 px es cancelado")
    r = resultado([(10, 20), (60, 20), (60, 90)])
    ver(r["ok"] and r["caja"] == [10, 20, 50, 70] and r["trazo"][0] == [10, 20], "un trazo bueno devuelve trazo y caja en cliente")

    class OjosFalso:                                                      # lo que usa el mixin, sin ventanas
        aprobadas, titulos, capturas = set(), {}, {}
    class Api(SenalarApi): _ojos = OjosFalso()
    ver(Api().senalar_ventana() == {"ok": False}, "senalar_ventana(): sin ventana enseñada, no hay ninguna")
    js = (AQUI / "senalar_ui.js")
    ver(js.exists() and "senalar_empezar" in js.read_text(encoding="utf-8") and "senalar_capturar" in js.read_text(encoding="utf-8"),
        "senalar_ui.js llama a senalar_empezar y senalar_capturar")
    print("Señalar: todo bien" if not malos else f"Señalar: {malos} fallo(s)")
    return malos


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    a = sys.argv[1:]
    if a[:1] == ["--probar"]: sys.exit(probar())
    elif a and a[0].isdigit():
        volcar = a[a.index("--volcar") + 1] if "--volcar" in a and a.index("--volcar") + 1 < len(a) else None
        print(json.dumps(correr(int(a[0]), volcar)), flush=True)
    else: print(__doc__)
