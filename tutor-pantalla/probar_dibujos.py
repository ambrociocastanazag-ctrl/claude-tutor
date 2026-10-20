"""Banco de pruebas de los dibujos, sin panel ni ventanas: las formas se dibujan en el Chrome instalado (el mismo
motor que el panel) y los fotogramas se componen con capa.fotograma, igual que encima de la app.

  python probar_dibujos.py <muestras.json> <carpeta> [--fondo captura.png] [--solo id1,id2] [--js extra.js]

muestras.json: un lote (DIBUJOS.md, sección 2) {"dibujos": [...]}; "cliente" de cada dibujo = tamaño del fondo.
Fondo de mentira: con "fondo_demo": "claro" | "oscuro" en un dibujo se pinta una ventana llena de botones (3 filas × 10) y
"boton": [fila, col] pone ese botón como objetivo (r) y todos los botones como "evitar". Sirve para probar las marcas
(formas_marcas.js, CONTRATO-MARCAS.md) sin una app.
Tema: cada dibujo puede traer "tema": "claro" | "oscuro" (como lo pone Python); si falta y tiene "fondo_demo", vale ese; si no, claro.
Por cada dibujo guarda <id>_tira.png (6 momentos de la animación, recortados a lo dibujado) y <id>_final.png
(el fondo entero con el dibujo al final); con varios dibujos, también _todos_final.png. La lupa lee la zona del fondo, como leería la pantalla.
Necesita Node y herramientas/ (puppeteer-core con el Chrome instalado)."""
import json, os, subprocess, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
HERRAMIENTAS = AQUI.parent / "herramientas"
sys.path.insert(0, str(AQUI))
import capa                                                     # noqa: E402
from PIL import Image, ImageDraw, ImageFont                     # noqa: E402

SCRIPTS = ["profe.js", "dibujante.js", "formas_fijas.js", "formas_animadas.js", "formas_formulas.js", "motor_figuras.js", "motor_3d.js", "formas_3d.js", "formas_profe.js",
           "marcas.js", "formas_marcas.js", "voz.js"]


def renderizar(lote, carpeta, extra=()):
    """Las capas que devuelve Dibujante.renderizar(lote) en Chrome (extra: más scripts, p. ej. una forma en pruebas)."""
    url = lambda p: Path(p).resolve().as_uri()
    rutas = [AQUI / s for s in SCRIPTS if (AQUI / s).exists()] + [Path(e) for e in extra]
    scripts = "".join(f'<script src="{url(s)}"></script>\n' for s in rutas)
    datos = json.dumps(lote, ensure_ascii=False).replace("<", "\\u003c")     # un </script> dentro de una muestra no corta el script
    html = (f'<!doctype html><html><head><meta charset="utf-8"><script>window.DIB_VENDOR = {json.dumps(url(AQUI / "vendor") + "/")};'
            f'window.MUESTRAS = {datos};</script>\n{scripts}</head><body></body></html>')
    Path(carpeta).mkdir(parents=True, exist_ok=True)
    banco = Path(carpeta) / "banco.html"; banco.write_text(html, encoding="utf-8")
    expr = "Dibujante.renderizar(window.MUESTRAS).then(function(r){ return JSON.stringify(r); })"
    p = subprocess.run(["node", str(HERRAMIENTAS / "captura.js"), banco.resolve().as_uri(), str(Path(carpeta) / "_banco.png"), "300", expr],
                       capture_output=True, text=True, encoding="utf-8", timeout=180)
    if p.returncode: raise RuntimeError("Chrome falló: " + (p.stderr or p.stdout)[-800:])
    res = json.loads(p.stdout.strip().splitlines()[-1])
    if res.get("errores"): print("  errores de la página:", " | ".join(res["errores"]))
    v = res.get("valor")
    if not isinstance(v, str) or v.startswith("ERROR"): raise RuntimeError(f"renderizar falló: {v}")
    return json.loads(v)


def botones_demo(w, h, oscuro):
    """Una ventana de mentira llena de botones: (imagen, {(fila, col): [x, y, w, h]})."""
    bg, bt, bd, tx = ((30, 34, 46), (52, 58, 76), (84, 92, 116), (205, 210, 225)) if oscuro else ((244, 245, 248), (255, 255, 255), (186, 190, 204), (60, 64, 80))
    im = Image.new("RGBA", (w, h), bg + (255,)); dr = ImageDraw.Draw(im); rects = {}
    try: f = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeui.ttf"), 14)
    except OSError: f = ImageFont.load_default()
    nombres = ["Archivo", "Editar", "Ver", "Insertar", "Formato", "Negrita", "Cursiva", "Subrayar", "Color", "Ayuda"]
    bw, bh, sep = 96, 38, 18
    for fi in range(3):
        for ci in range(10):
            x, y = 40 + ci * (bw + sep), 70 + fi * 74
            if x + bw > w - 20: continue
            dr.rounded_rectangle([x, y, x + bw, y + bh], radius=6, fill=bt + (255,), outline=bd + (255,), width=2)
            dr.text((x + 10, y + 10), nombres[(ci + fi * 3) % 10], font=f, fill=tx + (255,)); rects[(fi, ci)] = [x, y, bw, bh]
    for k in range(8):
        y = 330 + k * 36
        dr.rounded_rectangle([40, y, w - 60, y + 22], radius=4, fill=bt + (255,), outline=bd + (255,))
        dr.text((52, y + 3), "Línea de texto de la ventana " + "·" * (10 + k * 5), font=f, fill=tx + (255,))
    return im, rects


def preparar_demo(lote):
    """Pone r y evitar a los dibujos con «boton» / «fondo_demo». Devuelve {id: (imagen)} del fondo de cada uno."""
    fondos = {}
    for d in lote["dibujos"]:
        modo = d.get("fondo_demo")
        if modo and not d.get("tema"): d["tema"] = modo           # el fondo de mentira dice el tema de la app de detrás
        if not modo: continue
        w, h = d.get("cliente") or (1280, 720); d["cliente"] = [w, h]
        im, rects = botones_demo(w, h, modo == "oscuro"); fondos[d["id"]] = im
        d["evitar"] = [r for r in rects.values()]
        if d.get("boton") is not None:
            d["r"] = rects[tuple(d["boton"])]; d["evitar"] = [r for r in rects.values() if r != d["r"]]
    return fondos


def fondo_de(d, fondo):
    w, h = d.get("cliente") or (fondo.size if fondo else (1400, 850))
    if fondo: return fondo.convert("RGBA").resize((w, h)) if fondo.size != (w, h) else fondo.convert("RGBA")
    osc = d.get("tema") == "oscuro"
    im = Image.new("RGBA", (w, h), (30, 34, 46, 255) if osc else (246, 246, 248, 255)); dr = ImageDraw.Draw(im)
    for x in range(0, w, 40): dr.line([(x, 0), (x, h)], fill=(44, 49, 64, 255) if osc else (228, 228, 234, 255))
    for y in range(0, h, 40): dr.line([(0, y), (w, y)], fill=(44, 49, 64, 255) if osc else (228, 228, 234, 255))
    return im


def componer(base, capas, t, lupas):
    im = base.copy()
    for c in capas:
        f = capa.fotograma(c, t if (c.get("duracion") or 0) else 0, None, lupas.get(c["id"]))
        im.alpha_composite(f, (int(c["x"]), int(c["y"])))
    return im


def main(a):
    if len(a) < 2: sys.exit(__doc__)
    lote = json.loads(Path(a[0]).read_text(encoding="utf-8")); carpeta = Path(a[1]); carpeta.mkdir(parents=True, exist_ok=True)
    fondo = Image.open(a[a.index("--fondo") + 1]) if "--fondo" in a else None
    solo = set(a[a.index("--solo") + 1].split(",")) if "--solo" in a else None
    if solo: lote = {"dibujos": [d for d in lote["dibujos"] if d["id"] in solo]}
    demos = preparar_demo(lote)
    r = renderizar(lote, carpeta, [a[i + 1] for i, x in enumerate(a) if x == "--js"])
    for e in r.get("errores") or []: print("✘", e)
    try: fuente = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "segoeuib.ttf"), 15)
    except OSError: fuente = ImageFont.load_default()
    for d in lote["dibujos"]:
        capas = [c for c in r["capas"] if c["id"] == d["id"] or c["id"].startswith(d["id"] + "_")]
        if not capas: print(f"✘ {d['id']} ({d['forma']}): no devolvió capas"); continue
        base = demos[d["id"]] if d["id"] in demos else fondo_de(d, fondo)
        lupas = {}
        for c in capas:
            if c.get("lupa"):
                x, y, w, h = [round(v) for v in c["lupa"]["zona"]]; lupas[c["id"]] = base.crop((x, y, x + w, y + h)).convert("RGB")
        D = max(c.get("duracion") or 0 for c in capas)
        tiempos = [round(D * k / 5) for k in range(6)] if D else [0]
        x0 = max(0, min(c["x"] for c in capas) - 40); y0 = max(0, min(c["y"] for c in capas) - 40)
        x1 = min(base.width, max(c["x"] + c["w"] for c in capas) + 40); y1 = min(base.height, max(c["y"] + c["h"] for c in capas) + 40)
        cuadros = [componer(base, capas, t, lupas).crop((x0, y0, x1, y1)) for t in tiempos]
        cw, ch = cuadros[0].size; k = min(1.0, 700 / cw)
        cuadros = [c.resize((max(1, round(cw * k)), max(1, round(ch * k)))) for c in cuadros]
        cw, ch = cuadros[0].size; cols = 3 if len(cuadros) > 1 else 1; filas = (len(cuadros) + cols - 1) // cols
        tira = Image.new("RGB", (cols * (cw + 10) + 10, filas * (ch + 34) + 10), (255, 255, 255)); dr = ImageDraw.Draw(tira)
        for i, (c, t) in enumerate(zip(cuadros, tiempos)):
            px, py = 10 + (i % cols) * (cw + 10), 10 + (i // cols) * (ch + 34)
            dr.text((px, py), f"t = {t} ms", font=fuente, fill=(60, 60, 70)); tira.paste(c.convert("RGB"), (px, py + 22))
        tira.save(carpeta / f"{d['id']}_tira.png")
        componer(base, capas, D, lupas).convert("RGB").save(carpeta / f"{d['id']}_final.png")
        info = ", ".join(f"{c['id']}: {c['w']}×{c['h']} en ({c['x']},{c['y']})" + (f", {len(c.get('fotos') or [])} fotos" if c.get("fotos") else "") +
                         (f", {len(c.get('piezas') or [])} piezas" if c.get("piezas") else "") for c in capas)
        print(f"✔ {d['id']} ({d['forma']}): {len(capas)} capa(s), {D} ms — {info}")
    por_ventana = {}                                            # los dibujos de una misma ventana (hwnd), juntos
    for d in lote["dibujos"]: por_ventana.setdefault(d.get("hwnd"), []).append(d)
    for hwnd, ds in por_ventana.items():                         # todos juntos, como se verían en la app (¿se pisan?)
        ids = {d["id"] for d in ds}
        capas = [c for c in r["capas"] if c["id"] in ids or c["id"].rsplit("_", 1)[0] in ids]
        if len(ds) < 2 or not capas: continue
        d0 = ds[0]; base = demos[d0["id"]] if d0["id"] in demos else fondo_de(d0, fondo)
        lupas = {c["id"]: base.crop(tuple(round(v) for v in (c["lupa"]["zona"][0], c["lupa"]["zona"][1], c["lupa"]["zona"][0] + c["lupa"]["zona"][2],
                                                              c["lupa"]["zona"][1] + c["lupa"]["zona"][3]))).convert("RGB") for c in capas if c.get("lupa")}
        nombre = "_todos_final.png" if len(por_ventana) == 1 else f"_todos_{hwnd}_final.png"
        componer(base, capas, 10 ** 7, lupas).convert("RGB").save(carpeta / nombre)
        print("Todos juntos:", nombre)
    narr = [n for n in r.get("narracion") or [] if n.get("texto")]
    if narr: print("Narración:", " | ".join(f"{','.join(n['ids'])} [{n['desde']}-{n['hasta']}]: {n['texto']}" for n in narr))


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    main(sys.argv[1:])
