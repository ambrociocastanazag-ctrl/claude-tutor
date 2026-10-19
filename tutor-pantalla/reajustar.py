"""Reajustar 🎯: vuelve a encontrar lo que señalaba cada marca después de que la persona hizo zoom, scroll o cambió el
tamaño de la ventana (moverla no hace falta: las capas ya la siguen solas).

Dos caminos, según lo que se sabía de la marca:
  - Un control con nombre (Office, Windows, Chrome, VS Code...): se vuelve a leer la lista de controles de la ventana
    (UI Automation, SIN imagen) y se busca el mismo por nombre y tipo. Si quedó fuera de la vista, se dice hacia dónde.
  - Solo la imagen (lienzos, figuras, PDF): se busca el trozo de la captura vieja en la ventana actual, con varias
    escalas (zoom). La ventana se lee SOLO en la PC, al pulsar el botón: no se guarda ni se le manda al tutor
    (como la lupa). Si el trozo es liso o se repite, no se adivina: queda como perdida.

Buscador(cap).ubicar(caja, control) → {"estado": "ok" | "fuera" | "perdida", "pantalla": [x, y, w, h], "fuera": "abajo"...}
python reajustar.py --probar: la búsqueda en imágenes hechas aquí mismo (sin ventanas)."""
import os, sys, unicodedata
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ojos                                                                     # noqa: E402

ESCALAS = (0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.12, 1.25, 1.4, 1.6, 1.8, 2.0)   # zoom de la app respecto a la captura
MINIMO, VENTAJA = 0.72, 0.04                    # parecido mínimo, y cuánto debe ganarle al segundo sitio más parecido
LADO_GRUESO = 520                               # la búsqueda gruesa, en una imagen de este lado: rápida


def _norm(s):
    s = unicodedata.normalize("NFD", str(s or "").lower())
    return " ".join("".join(c for c in s if unicodedata.category(c) != "Mn").split())


# ---------- controles: lo mismo que ojos.leer_controles, pero también los que quedaron fuera de la vista ----------
def controles_todos(h, limite=1500):
    """[(tipo, nombre, (x0, y0, x1, y1) en la pantalla, fuera_de_vista)] sin recortar a la ventana."""
    try:
        import uiautomation as auto
        import uiautomation.uiautomation as uia
    except ImportError:
        return []
    out = []
    try:
        with auto.UIAutomationInitializerInThread():
            ia = uia._AutomationClient.instance().IUIAutomation
            cr = ia.CreateCacheRequest()
            for p in (ojos.UIA_NOMBRE, ojos.UIA_TIPO, ojos.UIA_CAJA, ojos.UIA_OCULTO): cr.AddProperty(p)
            els = ia.ElementFromHandle(h).FindAllBuildCache(4, ia.CreateTrueCondition(), cr)
            for i in range(min(els.Length, limite)):
                e = els.GetElement(i)
                tipo = ojos.TIPOS.get(e.CachedControlType)
                nombre = (e.CachedName or "").strip().replace("\n", " ")
                if not tipo or not nombre: continue
                r = e.CachedBoundingRectangle
                out.append((tipo, nombre[:70], (r.left, r.top, r.right, r.bottom), bool(e.CachedIsOffscreen)))
    except Exception:
        pass
    return out


# ---------- búsqueda de un trozo de imagen (correlación normalizada con FFT) ----------
def _gris(img):
    return np.asarray(img.convert("L"), dtype=np.float64)


def _sumas(a, h, w):
    """Suma de cada ventana h×w de `a` (imagen integral): forma (H-h+1, W-w+1)."""
    s = np.pad(a, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    return s[h:, w:] - s[:-h, w:] - s[h:, :-w] + s[:-h, :-w]


def _rapido(n):
    """El tamaño de FFT más chico >= n con solo factores 2, 3 y 5 (los tamaños raros son varias veces más lentos)."""
    while True:
        m = n
        for p in (2, 3, 5):
            while m % p == 0: m //= p
        if m == 1: return n
        n += 1


class Imagen:
    """Una imagen en gris con su FFT y sus sumas al cuadrado guardadas: se compara con muchos trozos sin rehacerlas."""

    def __init__(self, a):
        self.a = a; self.H, self.W = a.shape
        self.s = (_rapido(self.H), _rapido(self.W))
        self.F = np.fft.rfft2(a, s=self.s); self.a2 = a * a


def ncc(img, tpl):
    """Mapa de parecido (-1..1) de `tpl` en cada posición de `img` (arrays en gris o Imagen), o None si el trozo es liso."""
    im = img if isinstance(img, Imagen) else Imagen(img)
    H, W = im.H, im.W; h, w = tpl.shape
    if h > H or w > W or h < 4 or w < 4: return None
    t = tpl - tpl.mean(); tn = np.sqrt((t * t).sum())
    if tn < 1e-6 * h * w or t.std() < 4: return None                 # liso: cualquier sitio se le parece
    corr = np.fft.irfft2(im.F * np.conj(np.fft.rfft2(t, s=im.s)), s=im.s)[:H - h + 1, :W - w + 1]
    s1, s2 = _sumas(im.a, h, w), _sumas(im.a2, h, w)
    var = np.maximum(s2 - s1 * s1 / (h * w), 1e-9)
    out = corr / (np.sqrt(var) * tn)
    out[var < (2.0 ** 2) * h * w] = 0                                 # zonas lisas de la imagen no cuentan
    return out


def _dos_mejores(m, h, w):
    """(valor, (y, x)) del mejor sitio y valor del segundo, lejos del primero (al menos medio trozo)."""
    y, x = np.unravel_index(int(np.argmax(m)), m.shape); mejor = float(m[y, x])
    m2 = m.copy()
    m2[max(0, y - h // 2):y + h // 2 + 1, max(0, x - w // 2):x + w // 2 + 1] = -1
    return mejor, (int(y), int(x)), float(m2.max()) if m2.size else -1.0


def buscar(nueva, vieja, caja):
    """Dónde está ahora `caja` [x, y, w, h] de la imagen `vieja` dentro de `nueva` (mismas unidades: píxeles por
    píxel físico iguales). Devuelve ([x, y, w, h] en `nueva`, parecido, zoom) o None si no está claro.
    Primero con contexto alrededor (un botón solo puede ser liso; con lo de al lado se distingue); si no aparece
    (tras el zoom ese contexto puede quedar fuera de la ventana), con el trozo justo."""
    w, h = caja[2], caja[3]
    for lado in (max(64, min(220, 2.2 * max(w, h))), 0):
        r = _buscar(nueva, vieja, caja, lado)
        if r: return r
    return None


def _buscar(nueva, vieja, caja, lado):
    x, y, w, h = caja
    px0 = max(0, int(x + w / 2 - max(w, lado) / 2)); py0 = max(0, int(y + h / 2 - max(h, lado) / 2))
    px1 = min(vieja.width, int(x + w / 2 + max(w, lado) / 2)); py1 = min(vieja.height, int(y + h / 2 + max(h, lado) / 2))
    if px1 - px0 < 8 or py1 - py0 < 8: return None
    trozo = vieja.crop((px0, py0, px1, py1)); dx, dy = x - px0, y - py0
    # 1) gruesa: todas las escalas en pequeño
    f = min(1.0, LADO_GRUESO / max(nueva.size))
    g_nueva = Imagen(_gris(nueva.resize((max(8, round(nueva.width * f)), max(8, round(nueva.height * f))), Image.BILINEAR)))
    gruesos = []
    for z in ESCALAS:
        tw, th = round(trozo.width * z * f), round(trozo.height * z * f)
        if tw < 6 or th < 6: continue
        m = ncc(g_nueva, _gris(trozo.resize((tw, th), Image.BILINEAR)))
        if m is None: continue
        v, (yy, xx), _ = _dos_mejores(m, th, tw)
        gruesos.append((v, z, xx / f, yy / f))
    # en pequeño los trazos finos se parecen poco: no se decide aquí, pasan las tres mejores a la búsqueda fina
    gruesos = [g for g in sorted(gruesos, reverse=True)[:3] if g[0] > 0.15]
    # 2) fina: tamaño real, alrededor de cada sitio grueso y escalas vecinas
    fino = None
    for _, z0, gx, gy in gruesos:
        mg = int(12 / f) + 8                                   # una zona para las cinco escalas (cabe la más grande)
        rx0, ry0 = max(0, int(gx) - mg), max(0, int(gy) - mg)
        rx1 = min(nueva.width, int(gx) + round(trozo.width * z0 * 1.06) + mg)
        ry1 = min(nueva.height, int(gy) + round(trozo.height * z0 * 1.06) + mg)
        zona = Imagen(_gris(nueva.crop((rx0, ry0, rx1, ry1))))
        for z in (z0 * 0.94, z0 * 0.97, z0, z0 * 1.03, z0 * 1.06):
            tw, th = round(trozo.width * z), round(trozo.height * z)
            if tw < 6 or th < 6: continue
            m = ncc(zona, _gris(trozo.resize((tw, th), Image.BILINEAR)))
            if m is None: continue
            v, (yy, xx), _ = _dos_mejores(m, th, tw)
            if fino is None or v > fino[0]: fino = (v, z, rx0 + xx, ry0 + yy)
    if fino is None or fino[0] < MINIMO: return None
    v, z, fx, fy = fino
    # 3) ¿hay otro sitio casi igual de parecido en toda la ventana? (algo que se repite): mejor no adivinar
    tw, th = round(trozo.width * z), round(trozo.height * z)
    m = ncc(_gris(nueva), _gris(trozo.resize((tw, th), Image.BILINEAR)))
    if m is not None:
        yy, xx = min(m.shape[0] - 1, int(fy)), min(m.shape[1] - 1, int(fx))
        m[max(0, yy - th // 2):yy + th // 2 + 1, max(0, xx - tw // 2):xx + tw // 2 + 1] = -1
        if m.max() > v - VENTAJA: return None
    return [fx + dx * z, fy + dy * z, w * z, h * z], v, z


# ---------- el buscador de una captura ----------
def _lado_fuera(c, cli):
    """Hacia dónde quedó la caja (x0, y0, x1, y1) respecto al cliente (x, y, w, h), o None si se ve."""
    x0, y0, x1, y1 = c; cx, cy, cw, ch = cli
    if y1 <= cy: return "arriba"
    if y0 >= cy + ch: return "abajo"
    if x1 <= cx: return "izquierda"
    if x0 >= cx + cw: return "derecha"
    return None


class Buscador:
    """Ubica de nuevo cajas de la captura `cap` (ojos.Captura) en la ventana como está AHORA. Lee la lista de
    controles y la imagen una sola vez, y solo si hace falta."""

    def __init__(self, cap):
        self.cap, self.hwnd = cap, cap.hwnd
        self._controles = None; self._imagen = None; self._img_falla = None

    def controles(self):
        if self._controles is None: self._controles = controles_todos(self.hwnd)
        return self._controles

    def imagen(self):
        """(imagen de la ventana a la escala de la captura, origen en pantalla) o None. Solo en memoria."""
        if self._imagen is None and self._img_falla is None:
            try:
                img, origen, _ = ojos.imagen_de(self.hwnd, ignorar_pids=[os.getpid()])
                k = self.cap.k
                if k < 1: img = img.resize((max(1, round(img.width * k)), max(1, round(img.height * k))), Image.LANCZOS)
                self._imagen = (img, origen)
            except Exception as e:
                self._img_falla = str(e)
        return self._imagen

    def control_de(self, caja):
        """El control de la captura cuya caja es esta (las marcas por id copian su caja), o None."""
        for c in self.cap.controles:
            if [round(v) for v in c["caja"]] == [round(v) for v in caja]: return c
        return None

    def ubicar(self, caja, control=None):
        """caja [x, y, w, h] en píxeles de la captura → dónde está ahora (ver la cabecera)."""
        if not ojos.u32.IsWindow(self.hwnd): return {"estado": "perdida", "motivo": "la ventana se cerró"}
        control = control or self.control_de(caja)
        if control: return self._por_control(control, caja)
        return self._por_imagen(caja)

    def _por_control(self, c, caja):
        cli = ojos.cliente(self.hwnd)
        nombre, tipo = _norm(c["nombre"]), c["tipo"]
        todos = self.controles()
        iguales = [x for x in todos if _norm(x[1]) == nombre and x[0] == tipo] or [x for x in todos if _norm(x[1]) == nombre]
        if not iguales: return self._por_imagen(caja)          # el control ya no existe con ese nombre: por la imagen
        # entre varios con el mismo nombre: el mismo puesto que tenía entre los suyos en la captura, o el más cercano
        viejos = [k for k in self.cap.controles if _norm(k["nombre"]) == nombre and k["tipo"] == tipo]
        antes = self.cap.a_pantalla(caja); acx, acy = antes[0] + antes[2] / 2, antes[1] + antes[3] / 2
        if len(viejos) == len(iguales) > 1 and c in viejos:
            elegido = iguales[viejos.index(c)]
        else:
            elegido = min(iguales, key=lambda x: ((x[2][0] + x[2][2]) / 2 - acx) ** 2 + ((x[2][1] + x[2][3]) / 2 - acy) ** 2)
        r = elegido[2]
        lado = _lado_fuera(r, cli) if cli else None
        if lado: return {"estado": "fuera", "fuera": lado}
        if elegido[3] or r[2] - r[0] < 2 or r[3] - r[1] < 2: return {"estado": "perdida", "motivo": "está escondido"}
        x0, y0 = max(r[0], cli[0]), max(r[1], cli[1]); x1, y1 = min(r[2], cli[0] + cli[2]), min(r[3], cli[1] + cli[3])
        return {"estado": "ok", "pantalla": [x0, y0, x1 - x0, y1 - y0], "como": "control"}

    def _por_imagen(self, caja):
        im = self.imagen()
        if not im: return {"estado": "perdida", "motivo": self._img_falla or "no pude leer la ventana"}
        img, origen = im
        r = buscar(img, self.cap.img, caja)
        if not r: return {"estado": "perdida", "motivo": "no la encuentro en la imagen"}
        (x, y, w, h), _, _ = r
        k = self.cap.k
        return {"estado": "ok", "pantalla": [round(origen[0] + x / k), round(origen[1] + y / k), round(w / k), round(h / k)], "como": "imagen"}


# ---------- pruebas sin ventanas ----------
from PIL import ImageDraw, ImageFont                                           # noqa: E402


def _fuente(px):
    try: return ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf"), px)
    except OSError: return ImageFont.load_default()

def _lienzo(z=1.0, dx=0, dy=0):
    """Un «documento» con texto, una figura y zonas lisas, dibujado con zoom z y corrido dx, dy."""
    im = Image.new("RGB", (900, 600), "white"); d = ImageDraw.Draw(im)
    for i, t in enumerate(["Volumen de revolución", "Método de discos", "Área superficial", "Centroide de una lámina"]):
        d.text((dx + 40 * z, dy + (40 + 60 * i) * z), t, fill=(20, 20, 20), font=_fuente(round(22 * z)))
    d.ellipse([dx + 520 * z, dy + 80 * z, dx + 680 * z, dy + 240 * z], outline=(200, 30, 30), width=max(1, round(4 * z)))
    d.polygon([(dx + 560 * z, dy + 380 * z), (dx + 700 * z, dy + 300 * z), (dx + 740 * z, dy + 470 * z)], fill=(30, 90, 200))
    return im


def probar():
    fallos = 0

    def ver(c, txt):
        nonlocal fallos
        print(("  ✔ " if c else "  ✘ ") + txt); fallos += not c

    vieja = _lienzo()
    casos = [("mismo zoom, corrido", 1.0, -30, 25), ("zoom 125 %", 1.25, -60, -40), ("zoom 80 %", 0.8, 20, 10), ("zoom 150 %", 1.5, -200, -100)]
    objetivos = {"texto «Método de discos»": [40, 100, 170, 30], "círculo rojo": [520, 80, 160, 160], "triángulo azul": [560, 300, 180, 170]}
    for nombre_caso, z, dx, dy in casos:
        nueva = _lienzo(z, dx, dy)
        for nombre, c in objetivos.items():
            esperado = [dx + c[0] * z, dy + c[1] * z, c[2] * z, c[3] * z]
            r = buscar(nueva, vieja, c)
            if esperado[0] < 0 or esperado[1] < 0 or esperado[0] + esperado[2] > nueva.width or esperado[1] + esperado[3] > nueva.height:
                continue                                    # medio fuera de la ventana: ahí manda «fuera» o «vuelvo a mirar»
            ok = r is not None and abs(r[0][0] - esperado[0]) <= 6 and abs(r[0][1] - esperado[1]) <= 6 and abs(r[0][2] - esperado[2]) <= 8
            ver(ok, f"{nombre_caso}: {nombre} → {[round(v) for v in r[0]] if r else None} (esperado {[round(v) for v in esperado]})")
    # lo liso y lo repetido no se adivina
    ver(buscar(_lienzo(), vieja, [300, 500, 60, 40]) is None, "zona lisa (fondo blanco): no se adivina")
    rep = Image.new("RGB", (900, 600), "white"); d = ImageDraw.Draw(rep)
    for i in range(6): d.rectangle([60 + i * 130, 200, 160 + i * 130, 260], outline=(0, 0, 0), width=3)
    ver(buscar(rep, rep, [190, 200, 100, 60]) is None, "una entre seis cajas iguales: no se adivina")
    ver(_lado_fuera((10, 900, 50, 930), (0, 0, 800, 600)) == "abajo" and _lado_fuera((10, 10, 50, 40), (0, 0, 800, 600)) is None,
        "fuera de la vista: dice hacia dónde")
    print("Reajustar: todo bien" if not fallos else f"Reajustar: {fallos} fallo(s)")
    return fallos


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    if sys.argv[1:2] == ["--probar"]: sys.exit(1 if probar() else 0)
    print(__doc__)
