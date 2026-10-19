"""GIF animado de una figura 3D: los fotogramas PNG que saca la página (Figuras3D.fotogramas, motor_3d.js) → un .gif que se
repite sin fin, guardado en Descargas y copiado como archivo (CF_HDROP: al pegar, la app recibe el .gif).
Lo usan los paneles (ojos_panel.py) y la Tarjeta SVG (tarjeta.py).

    hacer_gif(fotos, ms, nombre="figura 3d") → ruta     fotos: data URLs o base64 de PNG, todos del mismo tamaño
    copiar_archivo(ruta)                                 el archivo en el portapapeles (pegar = subir el .gif)
    guardar_y_copiar(fotos, ms, nombre) → {ok, ruta, kb} | {ok: False, error}

Una sola paleta para todos los fotogramas (sacada de una muestra de ellos), con tramado: así el tramado no «hierve» al girar.
Con fondo transparente, el GIF solo tiene transparencia de 1 bit: el borde se corta en alfa 50 %.
`python gif3d.py --probar` arma un GIF de prueba en la carpeta temporal (sin portapapeles)."""
import base64, io, re, struct, sys, tempfile, time
from pathlib import Path

MAX_FOTOS = 90
MAX_LADO = 1600


def _png(dato):
    s = str(dato)
    datos = base64.b64decode(s.split(",", 1)[-1] if s.startswith("data:") else s)
    if not datos.startswith(b"\x89PNG"): raise ValueError("un fotograma no es PNG")
    return datos


def hacer_gif(fotos, ms, nombre="figura 3d", carpeta=None):
    from PIL import Image
    if not fotos: raise ValueError("no hay fotogramas")
    if len(fotos) > MAX_FOTOS: raise ValueError(f"demasiados fotogramas (máximo {MAX_FOTOS})")
    ims = [Image.open(io.BytesIO(_png(f))).convert("RGBA") for f in fotos]
    w, h = ims[0].size
    if w > MAX_LADO or h > MAX_LADO: raise ValueError("la figura es demasiado grande para un GIF")
    ims = [im if im.size == (w, h) else im.resize((w, h)) for im in ims]
    transparente = any(im.getextrema()[3][0] < 128 for im in ims)
    # paleta común: un mosaico con 1 de cada 4 fotogramas (en RGB), 255 colores; el 255 queda para el transparente
    muestra = ims[::4] or ims
    mosaico = Image.new("RGB", (w, h * len(muestra)))
    for i, im in enumerate(muestra):
        fondo = Image.new("RGB", (w, h), (255, 255, 255)); fondo.paste(im, mask=im.getchannel("A"))
        mosaico.paste(fondo, (0, h * i))
    paleta = mosaico.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    pal = paleta.getpalette()[:255 * 3]
    pal += [0, 0, 0] * (256 - len(pal) // 3)
    paleta.putpalette(pal)
    salida = []
    for im in ims:
        rgb = Image.new("RGB", (w, h), (255, 255, 255)); rgb.paste(im, mask=im.getchannel("A"))
        q = rgb.quantize(palette=paleta, dither=Image.Dither.FLOYDSTEINBERG)
        if transparente:
            hueco = im.getchannel("A").point(lambda a: 255 if a < 128 else 0)
            q.paste(255, mask=hueco)
        salida.append(q)
    carpeta = Path(carpeta) if carpeta else Path.home() / "Downloads"
    carpeta.mkdir(parents=True, exist_ok=True)
    base = re.sub(r"[^\w\- ]+", "", str(nombre))[:60].strip() or "figura 3d"
    ruta = carpeta / f"{base}.gif"; n = 2
    while ruta.exists(): ruta = carpeta / f"{base} ({n}).gif"; n += 1
    extra = {"transparency": 255, "disposal": 2} if transparente else {"disposal": 1}
    salida[0].save(ruta, save_all=True, append_images=salida[1:], duration=max(20, int(ms)), loop=0, optimize=False, **extra)
    return ruta


def _hdrop(rutas):
    """CF_HDROP: DROPFILES (20 bytes, rutas anchas) + rutas separadas por nulo y terminadas en doble nulo."""
    datos = "".join(str(r) + "\0" for r in rutas).encode("utf-16-le") + b"\0\0"
    return struct.pack("<IiiII", 20, 0, 0, 0, 1) + datos


def copiar_archivo(ruta):
    import win32clipboard as wc, win32con
    for _ in range(10):                                          # otro programa puede tenerlo abierto un instante
        try: wc.OpenClipboard(); break
        except Exception: time.sleep(0.05)
    else:
        raise RuntimeError("El portapapeles está ocupado por otro programa: inténtalo de nuevo.")
    try:
        wc.EmptyClipboard()
        wc.SetClipboardData(win32con.CF_HDROP, _hdrop([ruta]))
    finally:
        wc.CloseClipboard()


def guardar_y_copiar(fotos, ms, nombre="figura 3d", copiar=True):
    try:
        ruta = hacer_gif(fotos, ms, nombre)
        if copiar: copiar_archivo(ruta)
        return {"ok": True, "ruta": str(ruta), "kb": round(ruta.stat().st_size / 1024)}
    except Exception as e:
        return {"ok": False, "error": f"No pude hacer el GIF: {e}"}


def probar():
    from PIL import Image, ImageDraw
    fotos = []
    for i in range(24):                                          # un cuadrado que gira, con fondo transparente
        im = Image.new("RGBA", (160, 120), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
        d.regular_polygon((80, 60, 40), 4, rotation=i * 360 / 24 / 4, fill=(60, 90, 200, 255), outline=(20, 20, 40, 255))
        b = io.BytesIO(); im.save(b, "PNG"); fotos.append("data:image/png;base64," + base64.b64encode(b.getvalue()).decode())
    ruta = hacer_gif(fotos, 60, "prueba gif3d", carpeta=tempfile.gettempdir())
    with Image.open(ruta) as g:
        n, info = g.n_frames, dict(g.info)
    bien = n == 24 and info.get("loop") == 0 and info.get("transparency") == 255
    ruta.unlink()
    try: hacer_gif(["no es png"], 60, carpeta=tempfile.gettempdir()); malo = False
    except Exception: malo = True
    print("gif3d: todo bien" if bien and malo else f"gif3d: MAL (fotos {n}, info {info}, malo {malo})")
    return bien and malo


if __name__ == "__main__":
    if "--probar" in sys.argv: sys.exit(0 if probar() else 1)
    print(__doc__)
