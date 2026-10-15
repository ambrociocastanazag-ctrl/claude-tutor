"""Leer el editor de VS Code (y los de su familia: Antigravity, Cursor...) SIN tocarlo: ni clics, ni teclas, ni foco.

Lo usan los tres tutores (Excel, Dia y el modo curso) a través de capacidades.py:
- archivo_abierto(hwnd, raices): qué archivo hay abierto (título de la ventana + UI Automation), su ruta dentro de las
  carpetas del curso, su contenido con números de línea y si hay cambios sin guardar.
- rect_linea(hwnd, n, archivo): el rectángulo EN PANTALLA de la línea n del editor, o por qué no se puede.

Cómo se ubica una línea (probado en VS Code 2026, tema oscuro, Windows al 125 %):
  VS Code no enseña el texto del editor a UI Automation mientras no haya un lector de pantalla («The editor is not
  accessible at this time») y cambiar su configuración no es nuestro. Sí enseña: el rectángulo del editor, la barra de
  estado («Ln 21, Col 2») y el cuadro de entrada del cursor (que está justo en la línea del cursor). Con eso y UNA
  captura LOCAL (PrintWindow de esa ventana; no sale a ningún sitio) se hace:
    1. los números de línea del margen son filas de tinta: cada fila es una línea REAL (las líneas partidas por el
       ajuste de ancho, el «Run | Debug» de las pruebas y los avisos no llevan número, así que no cuentan);
    2. la fila del cursor, que se conoce (barra de estado + cuadro de entrada), da el número de línea de una fila y
       las demás siguen en orden;
    3. si el cursor no se ve, se alinea la forma del texto de las filas (hasta dónde llega la tinta) con el largo de
       las líneas del archivo en disco, y se acepta solo si el parecido es claro.
  Limitaciones: con regiones plegadas (la numeración salta) el paso 2 puede fallar; el paso 3 lo detecta casi siempre."""
import ctypes, glob, os, re, time
from pathlib import Path

import numpy as np

import ojos

UIA_NOMBRE, UIA_TIPO, UIA_CAJA, UIA_OCULTO, UIA_CLASE = 30005, 30003, 30001, 30022, 30012
RE_TITULO = re.compile(r"^(?P<mod>[●•*]\s*)?(?P<nombre>.+?)\s+-\s+.*$")
RE_LN = re.compile(r"\bLn\s+(\d+),\s*Col\s+(\d+)")
CARPETAS_FUERA = {".git", "node_modules", "target", "__pycache__", ".idea", "build", "dist", ".venv", ".mvn"}
MAX_LINEAS = 400
FAMILIA = {"code", "code - insiders", "antigravity ide", "cursor", "windsurf", "vscodium"}


def es_vscode(app): return (app or "").lower() in FAMILIA


def _elementos(hwnd):
    """[(tipo, clase, nombre, (l, t, r, b), fuera_de_pantalla)] de toda la ventana, de una vez (con caché)."""
    import uiautomation as auto
    import uiautomation.uiautomation as uia
    out = []
    with auto.UIAutomationInitializerInThread():
        ia = uia._AutomationClient.instance().IUIAutomation
        cr = ia.CreateCacheRequest()
        for p in (UIA_NOMBRE, UIA_TIPO, UIA_CAJA, UIA_OCULTO, UIA_CLASE): cr.AddProperty(p)
        els = ia.ElementFromHandle(hwnd).FindAllBuildCache(4, ia.CreateTrueCondition(), cr)
        for i in range(els.Length):
            e = els.GetElement(i)
            try:
                r = e.CachedBoundingRectangle
                out.append((e.CachedControlType, e.CachedClassName or "", (e.CachedName or ""), (r.left, r.top, r.right, r.bottom), bool(e.CachedIsOffscreen)))
            except Exception:
                continue
    return out


def _area(c): return max(0, c[2] - c[0]) * max(0, c[3] - c[1])


def leer_editor(hwnd):
    """{"nombre": pestaña del editor activo, "caja": (l, t, r, b) del editor, "cursor": (ln, col) de la barra de estado,
    "entrada": caja del cuadro de entrada del cursor o None} — solo lectura. None si la ventana no tiene editor."""
    els = _elementos(hwnd)
    editores = [e for e in els if "editor-instance" in e[1] and not e[4] and _area(e[3]) > 200 * 100]
    if not editores: return None
    # varios (editores divididos): el que contiene el cuadro de entrada enfocado; si no, el más grande
    entradas = [e for e in els if ("native-edit-context" in e[1] or "inputarea" in e[1]) and not e[4] and _area(e[3]) > 0]
    def contiene(a, b): return a[0] <= b[0] + 2 and a[1] <= b[1] + 2 and a[2] >= b[2] - 2 and a[3] >= b[3] - 2
    elegido, entrada = None, None
    for ed in sorted(editores, key=lambda e: -_area(e[3])):
        en = next((x for x in entradas if contiene(ed[3], x[3])), None)
        if en: elegido, entrada = ed, en; break
    if elegido is None: elegido = max(editores, key=lambda e: _area(e[3]))
    cursor = None
    for e in els:
        m = RE_LN.search(e[2])
        if m and not e[4]: cursor = (int(m.group(1)), int(m.group(2))); break
    return {"nombre": elegido[2].strip(), "caja": elegido[3], "cursor": cursor, "entrada": entrada[3] if entrada else None}


# ---------- el archivo abierto ----------
def nombre_del_titulo(titulo):
    """('Prueba.java', sin_guardar) del título «● Prueba.java - Proyecto - Visual Studio Code»."""
    m = RE_TITULO.match(titulo or "")
    if not m: return None, False
    return m.group("nombre").strip(), bool(m.group("mod"))


def buscar_archivo(nombre, raices):
    """La ruta más reciente con ese nombre dentro de las carpetas `raices` (admite nombres cortados con «…»)."""
    if not nombre: return None
    nombre = nombre.rstrip("…").rstrip(".") if ("…" in nombre or "�" in nombre) else nombre
    corte = "…" in nombre or "�" in nombre
    nombre = re.split(r"[…�]", nombre)[0]
    hallados = []
    for raiz in raices:
        raiz = Path(raiz)
        if not raiz.is_dir(): continue
        for dp, dn, fn in os.walk(raiz):
            dn[:] = [d for d in dn if d not in CARPETAS_FUERA]
            for f in fn:
                if f == nombre or (corte and f.startswith(nombre)):
                    hallados.append(Path(dp) / f)
        if len(hallados) > 200: break
    if not hallados: return None
    return max(hallados, key=lambda p: p.stat().st_mtime)


def archivo_abierto(hwnd, raices, ed=None):
    """Dict con lo del archivo abierto en esa ventana de VS Code, o None. Claves: nombre, sin_guardar, ruta, rel, lineas
    (lista de str o None si no está en las carpetas), cursor, editor."""
    titulo = ojos.titulo(hwnd)
    t_nombre, sin_guardar = nombre_del_titulo(titulo)
    try: ed = ed or leer_editor(hwnd)
    except Exception: ed = None
    nombre = (ed or {}).get("nombre") or t_nombre
    if not nombre: return None
    ruta = buscar_archivo(nombre, raices)
    lineas = None
    if ruta:
        try: lineas = ruta.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError: lineas = None
    rel = None
    if ruta:
        for r in raices:
            try: rel = ruta.relative_to(Path(r)).as_posix(); break
            except ValueError: continue
    return {"nombre": nombre, "sin_guardar": sin_guardar, "ruta": ruta, "rel": rel or (ruta.name if ruta else None),
            "lineas": lineas, "cursor": (ed or {}).get("cursor"), "editor": ed}


def contexto_archivo(hwnd, raices, visibles=None):
    """El texto para el tutor: archivo abierto con números de línea (máximo MAX_LINEAS alrededor del cursor), si hay
    cambios sin guardar y qué líneas se ven. '' si no hay ventana de editor."""
    try:
        v = vista_editor(hwnd, raices); a = v.get("archivo")
        if v.get("num") and not visibles: visibles = (v["num"][0][0], v["num"][-1][0])
    except Exception: return ""
    if not a: return ""
    partes = [f"[Archivo abierto en el editor] «{a['nombre']}»" + (f" (ruta del proyecto: {a['rel']})" if a["rel"] else " (no está en las carpetas del curso)")]
    if a["sin_guardar"]:
        partes.append("OJO: tiene cambios SIN GUARDAR; el texto de abajo es el del disco y puede ir atrasado respecto a lo que él ve.")
    if a["cursor"]: partes.append(f"Cursor en la línea {a['cursor'][0]}, columna {a['cursor'][1]}.")
    if visibles: partes.append(f"Líneas visibles ahora en el editor: {visibles[0]} a {visibles[1]}.")
    ls = a["lineas"]
    if ls is not None:
        centro = (a["cursor"][0] if a["cursor"] else (visibles[0] if visibles else 1))
        if len(ls) <= MAX_LINEAS: ini, fin = 1, len(ls)
        else: ini = max(1, min(len(ls) - MAX_LINEAS + 1, centro - MAX_LINEAS // 2)); fin = ini + MAX_LINEAS - 1
        partes.append(f"Contenido (líneas {ini} a {fin} de {len(ls)}):")
        ancho = len(str(fin))
        partes.append("\n".join(f"{n:>{ancho}}| {ls[n - 1]}" for n in range(ini, fin + 1)))
        partes.append("Para señalar una línea de este archivo en el editor usa «linea»: N en tus marcas o dibujos.")
    return "\n".join(partes)


# ---------- ubicar una línea ----------
def _runs(mask):
    """[(ini, fin)] de las rachas de True (fin exclusivo)."""
    d = np.diff(np.concatenate(([0], mask.astype(np.int8), [0])))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0]))


def filas_de_numeros(img, caja_ed, entrada=None):
    """Lee los números del margen en una captura. Devuelve (filas, x_texto, x_fin_margen): filas = [(y_centro, alto)]
    de cada línea real, de arriba abajo, en píxeles de la imagen."""
    g = np.asarray(img.convert("L"), dtype=np.int16)
    l, t, r, b = [int(v) for v in caja_ed]
    l, t = max(l, 0), max(t, 0); r, b = min(r, g.shape[1]), min(b, g.shape[0])
    x_texto = int(entrada[0]) if entrada and l < entrada[0] < l + 260 else None
    x1 = (x_texto - 24) if x_texto else min(r, l + 260)
    zona = g[t:b, l:x1]
    if zona.size == 0: return [], x_texto, x1
    fondo = int(np.median(zona))
    tinta = np.abs(zona - fondo) > 45
    grupos = _runs(tinta.sum(axis=0) > 0)
    # une los grupos separados por menos de 14 px (los dígitos de un número)
    fus = []
    for a, c in grupos:
        if fus and a - fus[-1][1] < 14: fus[-1] = (fus[-1][0], c)
        else: fus.append((a, c))
    if not fus: return [], x_texto, x1
    # los números son un grupo angosto (≤ 70 px) con tinta de sobra; el texto del código es un grupo ancho que viene después
    angostos = []
    for g_ in fus:
        if g_[1] - g_[0] > 70: break
        angostos.append(g_)
    if not angostos: return [], x_texto, x1
    a, c = max(angostos, key=lambda g_: int(tinta[:, g_[0]:g_[1]].sum()))
    filas = _runs(tinta[:, a:c].sum(axis=1) > 0)
    # une trozos pegados (≤2 px) y descarta lo que no mide como un dígito
    fus_f = []
    for ya, yb in filas:
        if fus_f and ya - fus_f[-1][1] <= 2: fus_f[-1] = (fus_f[-1][0], yb)
        else: fus_f.append((ya, yb))
    altos = [yb - ya for ya, yb in fus_f]
    if not altos: return [], x_texto, x1
    tipico = float(np.median(altos))
    filas = [(t + (ya + yb) / 2, yb - ya) for ya, yb in fus_f if 0.6 * tipico <= yb - ya <= 1.6 * tipico]
    if x_texto is None:                                  # sin cuadro de entrada: donde empieza la tinta del texto
        resto = np.abs(g[t:b, l + c + 12:r - 30] - fondo) > 45
        cs = np.where(resto.any(axis=0))[0]
        if len(cs): x_texto = l + c + 12 + int(cs.min())
    return filas, x_texto, l + c


def _largos_visibles(img, caja_ed, filas, x_texto):
    """Hasta dónde llega la tinta del texto en cada fila (en píxeles desde x_texto): la «forma» de la línea."""
    g = np.asarray(img.convert("L"), dtype=np.int16)
    l, t, r, b = [int(v) for v in caja_ed]
    xt = int(x_texto or (l + 60)); xr = max(xt + 20, r - 40)          # sin la barra de desplazamiento ni el minimapa
    fondo = int(np.median(g[t:b, xt:xr]))
    out = []
    for y, h in filas:
        y0, y1 = int(y - h), int(y + h)
        franja = np.abs(g[max(y0, 0):y1, xt:xr] - fondo) > 45
        cols = np.where(franja.any(axis=0))[0]
        out.append(int(cols.max()) if len(cols) else 0)
    return out


def _largo_linea(s):
    return len(s.expandtabs(4).rstrip())


def alinear_con_archivo(largos_px, lineas):
    """Qué número de línea es la primera fila: la alineación (correlación) de la forma de las filas con el largo de las
    líneas del archivo. Devuelve (primera_linea, confianza 0..1) o (None, 0)."""
    n = len(largos_px)
    if n < 4 or not lineas or len(lineas) < n: return None, 0.0
    x = np.array(largos_px, dtype=float)
    if x.std() < 1e-6: return None, 0.0
    L = np.array([_largo_linea(s) for s in lineas], dtype=float)
    mejor, seg, ini = -2.0, -2.0, None
    for s in range(0, len(lineas) - n + 1):
        y = L[s:s + n]
        if y.std() < 1e-6: continue
        c = float(np.corrcoef(x, y)[0, 1])
        if c > mejor: seg, mejor, ini = mejor, c, s
        elif c > seg: seg = c
    if ini is None or mejor < 0.85 or (mejor - seg) < 0.02: return None, max(0.0, mejor)
    return ini + 1, mejor


def numerar(img, caja_ed, entrada, cursor, lineas):
    """[(n_linea, y_centro, alto)] de las líneas visibles y la confianza ("cursor" | "archivo" | None)."""
    filas, x_texto, x_fin = filas_de_numeros(img, caja_ed, entrada)
    if not filas: return [], None, x_texto, x_fin
    primera, como = None, None
    if cursor and entrada:
        yc = (entrada[1] + entrada[3]) / 2
        i = min(range(len(filas)), key=lambda k: abs(filas[k][0] - yc))
        if abs(filas[i][0] - yc) <= max(filas[i][1] * 2, 14):
            primera, como = cursor[0] - i, "cursor"
    if primera is None and lineas:
        p, conf = alinear_con_archivo(_largos_visibles(img, caja_ed, filas, x_texto), lineas)
        if p: primera, como = p, "archivo"
    if primera is None: return [], None, x_texto, x_fin
    return [(primera + k, y, h) for k, (y, h) in enumerate(filas)], como, x_texto, x_fin


_cache = {}


def vista_editor(hwnd, raices=(), ttl=2.0):
    """Todo lo que se sabe del editor ahora, leído UNA vez (UI Automation + una captura local; cache de `ttl` s):
    {"ed", "archivo", "num": [(n, y, alto)], "como", "x_texto", "x_fin", "img", "origen"} o {"error": motivo}."""
    k = (hwnd, tuple(map(str, raices)))
    hit = _cache.get(k)
    if hit and time.time() - hit[0] < ttl: return hit[1]
    v = _vista(hwnd, raices)
    _cache[k] = (time.time(), v)
    return v


def _vista(hwnd, raices):
    try: ed = leer_editor(hwnd)
    except Exception as e: return {"error": f"no pude leer el editor ({type(e).__name__})"}
    if not ed: return {"error": "no veo ningún archivo abierto en el editor"}
    if ojos.u32.IsIconic(hwnd): return {"error": "la ventana del editor está minimizada", "ed": ed}
    try: img, origen = ojos.imagen_de(hwnd, ())[:2]
    except Exception as e: return {"error": f"no pude ver la ventana del editor ({type(e).__name__})", "ed": ed}
    ox, oy = origen
    l, t, r, b = ed["caja"]
    caja_img = (l - ox, t - oy, r - ox, b - oy)
    entrada = None
    if ed["entrada"]:
        e = ed["entrada"]; entrada = (e[0] - ox, e[1] - oy, e[2] - ox, e[3] - oy)
    try: arch = archivo_abierto(hwnd, raices, ed)
    except Exception: arch = None
    num, como, x_texto, x_fin = numerar(img, caja_img, entrada, ed["cursor"], arch["lineas"] if arch else None)
    return {"ed": ed, "archivo": arch, "num": num, "como": como, "x_texto": x_texto, "x_fin": x_fin,
            "img": img, "origen": origen, "caja_img": caja_img}


def rect_linea(hwnd, n, raices=(), vista=None):
    """Dónde cae la línea n (1 = la primera) del editor de esa ventana. Devuelve un dict:
      {"estado": "visible", "caja": [x, y, w, h] EN PANTALLA, "primera", "ultima", "como": "cursor"|"archivo"}
      {"estado": "arriba"|"abajo", "caja": [...] borde del editor, "primera", "ultima", "mensaje": «sube/baja hasta la línea N»}
      {"estado": "no_se", "mensaje": por qué}"""
    v = vista or vista_editor(hwnd, raices)
    if v.get("error"): return {"estado": "no_se", "mensaje": v["error"]}
    if not v["num"]: return {"estado": "no_se", "mensaje": "no logré leer los números de línea del editor (¿hay una región plegada, o el cursor no se ve y el archivo no está en las carpetas del curso?)"}
    num, ox, oy = v["num"], v["origen"][0], v["origen"][1]
    l, t, r, b = v["ed"]["caja"]
    primera, ultima = num[0][0], num[-1][0]
    n = int(n)
    if n < primera or n > ultima:
        lado = "arriba" if n < primera else "abajo"
        caja = [l, t, r - l, 6] if lado == "arriba" else [l, b - 6, r - l, 6]
        return {"estado": lado, "caja": caja, "primera": primera, "ultima": ultima,
                "mensaje": f"{'Sube' if lado == 'arriba' else 'Baja'} en el editor hasta la línea {n} (ahora se ven la {primera} a la {ultima})"}
    y, h = next((y, h) for k, y, h in num if k == n)
    seguidas = [num[k + 1][1] - num[k][1] for k in range(len(num) - 1)]       # distancia entre líneas vecinas (sin avisos en medio)
    alto = min(seguidas) if seguidas else h * 1.9
    xt = v["x_texto"] if v["x_texto"] else v["x_fin"] + 20
    fin = _largos_visibles(v["img"], v["caja_img"], [(y, h)], xt)[0] + xt + 6      # hasta donde llega el texto de esa línea
    xr = min(max(xt + 24, fin), v["caja_img"][2] - 20)
    caja = [round(xt - 4 + ox), round(y - alto / 2 + oy), round(xr - xt + 8), round(alto)]
    return {"estado": "visible", "caja": caja, "primera": primera, "ultima": ultima, "como": v["como"]}


def ventana_editor(exe_lista=FAMILIA):
    """El hwnd de la ventana de editor más reciente (la primera de la lista de ventanas)."""
    for v in ojos.listar_ventanas():
        if es_vscode(v["app"]): return v
    return None
