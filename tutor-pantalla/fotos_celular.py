"""Buzón de fotos del celular: una ventanita SOLO para recibir fotos y arrastrarlas (a una guía, al chat de Claude…).

  python tutor-pantalla/fotos_celular.py            abre la ventana (QR + código; las fotos van llegando)
  python tutor-pantalla/fotos_celular.py --probar   sin ventana: una vuelta completa contra el servicio del .env

Usa el mismo servicio que el botón del celular de los tutores (celular.py + fotos-servidor/). Las fotos no van a ningún
chat: se guardan en una carpeta temporal y la ventana las muestra desde ahí. Arrastrar es NATIVO (WebView2 no deja
sacar imágenes): la ventana de Windows hace DoDragDrop con el archivo, como el Explorador. También: «Copiar» (portapapeles, para Ctrl+V), «Quitar» y «Abrir
carpeta» (arrastrar desde el Explorador). Al cerrar la ventana se borran la carpeta y la sesión del servicio."""
import io, json, os, shutil, sys, tempfile, time, base64
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import celular                                                           # noqa: E402

PREFERENCIAS = AQUI.parent / "panel-excel" / "preferencias.json"


class Buzon:
    """Lo que llama la página (js_api). `carpeta`: la temporal donde viven la página y las fotos."""

    def __init__(self, carpeta, cel=None):
        self._carpeta, self._cel, self.n = Path(carpeta), cel or celular.Celular(), 0
        self._ventana = None                  # la ventana de pywebview (con guion bajo: pywebview no la expone a la página)

    def sesion(self):
        r = self._cel.abrir()
        return {k: r.get(k) for k in ("ok", "error", "codigo", "qr", "inicio")}

    def recoger(self):
        """Las fotos nuevas, ya guardadas como archivo: [{nombre}] (la página las pide por su nombre)."""
        r = self._cel.recoger()
        nuevas = []
        for f in r.get("fotos") or []:
            self.n += 1
            ext = Path(f["nombre"]).suffix or ".jpg"
            nombre = f"foto_{time.strftime('%H-%M-%S')}_{self.n}{ext}"
            (self._carpeta / nombre).write_bytes(base64.b64decode(f["datos"]))
            nuevas.append({"nombre": nombre})
        out = {"ok": r.get("ok", False), "fotos": nuevas, "error": r.get("error")}
        if r.get("nueva") and r.get("codigo"): out.update(codigo=r["codigo"], qr=r.get("qr"))
        return out

    def _ruta(self, nombre):
        p = (self._carpeta / Path(str(nombre)).name).resolve()
        if p.parent != self._carpeta.resolve() or not p.name.startswith("foto_") or not p.is_file(): raise FileNotFoundError(nombre)
        return p

    def copiar(self, nombre):
        """La foto al portapapeles (CF_DIB y PNG): se pega con Ctrl+V en el navegador o en cualquier programa."""
        try:
            from PIL import Image
            import win32clipboard
            img = Image.open(self._ruta(nombre)).convert("RGB")
            bmp, png = io.BytesIO(), io.BytesIO()
            img.save(bmp, "BMP"); img.save(png, "PNG")
            win32clipboard.OpenClipboard()
            try:
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardData(win32clipboard.CF_DIB, bmp.getvalue()[14:])
                win32clipboard.SetClipboardData(win32clipboard.RegisterClipboardFormat("PNG"), png.getvalue())
            finally: win32clipboard.CloseClipboard()
            return {"ok": True}
        except FileNotFoundError: return {"ok": False, "error": "Esa foto ya no está."}
        except Exception as e: return {"ok": False, "error": f"No pude copiarla ({e})."}

    def quitar(self, nombre):
        try: self._ruta(nombre).unlink(); return {"ok": True}
        except FileNotFoundError: return {"ok": True}

    def arrastrar(self, nombre):
        """Arrastre NATIVO: el motor de Edge (WebView2) no deja sacar imágenes de la ventana, así que al empezar a
        arrastrar la página llama aquí y la ventana de Windows (WinForms) hace DoDragDrop con el ARCHIVO, como el
        Explorador. Solo si el botón izquierdo sigue apretado (si no, soltaría la foto donde esté el ratón)."""
        try: p = str(self._ruta(nombre))
        except FileNotFoundError: return {"ok": False, "error": "Esa foto ya no está."}
        form = getattr(self._ventana, "native", None)
        if form is None: return {"ok": False, "error": "No puedo arrastrar desde aquí: usa Copiar."}
        from System import Action, Array, String
        from System.Windows.Forms import Control, DataFormats, DataObject, DragDropEffects, MouseButtons
        hecho = {}
        def hacer():
            if not Control.MouseButtons.HasFlag(MouseButtons.Left): hecho["r"] = "suelto"; return
            d = DataObject(); d.SetData(DataFormats.FileDrop, Array[String]([p]))
            hecho["r"] = str(form.DoDragDrop(d, DragDropEffects.Copy))
        try: form.Invoke(Action(hacer))
        except Exception as e: return {"ok": False, "error": f"No pude arrastrarla ({e}); usa Copiar."}
        return {"ok": True, "efecto": hecho.get("r")}

    def abrir_carpeta(self):
        os.startfile(str(self._carpeta)); return {"ok": True}

    def cerrar(self):
        self._cel.cerrar()
        shutil.rmtree(self._carpeta, ignore_errors=True)


def tema():
    try: return json.loads(PREFERENCIAS.read_text(encoding="utf-8")).get("tema", "claro")
    except Exception: return "claro"


def abrir():
    import webview
    carpeta = Path(tempfile.mkdtemp(prefix="tutor-fotos-celular-"))
    t = tema()
    html = (AQUI / "fotos_celular.html").read_text(encoding="utf-8").replace(
        "<head>", f"<head><script>window.TEMA_PANEL = {json.dumps(t)};</script>", 1)
    (carpeta / "index.html").write_text(html, encoding="utf-8")
    buzon = Buzon(carpeta)
    if not buzon._cel.configurado:
        shutil.rmtree(carpeta, ignore_errors=True)
        sys.exit("Falta configurar las fotos del celular: tutor-pantalla/.env con FOTOS_URL y FOTOS_CLAVE (ver .env.example).")
    try:
        import panel_pantalla
        x0, y0, ancho, alto = panel_pantalla.area_visible()
    except Exception: x0, y0, ancho, alto = 0, 0, 1536, 820
    ancho_v, alto_v = 360, min(int(alto), 760)
    buzon._ventana = webview.create_window("Fotos del celular", url=str(carpeta / "index.html"), js_api=buzon, width=ancho_v, height=alto_v,
                          x=int(x0 + ancho - ancho_v), y=int(y0 + alto - alto_v), on_top=True, min_size=(300, 360),
                          background_color="#161B1E" if t == "oscuro" else "#F4EFE6")
    try: webview.start(http_server=True, gui="edgechromium")
    finally: buzon.cerrar()


def probar():
    """Sin ventana: abre sesión, «sube» una foto como el celular, la recoge como archivo, la copia, la quita y cierra."""
    import urllib.request
    malos = 0
    def ver(c, t):
        nonlocal malos
        print(("  ok " if c else "  ✘ MAL ") + t)
        if not c: malos += 1
    carpeta = Path(tempfile.mkdtemp(prefix="tutor-fotos-celular-"))
    b = Buzon(carpeta)
    ver(b._cel.configurado, "el .env está configurado")
    s = b.sesion(); ver(s["ok"] and s["codigo"] and "<svg" in (s["qr"] or ""), f"sesión con código y QR ({s.get('error') or s.get('codigo')})")
    if s["ok"]:
        from PIL import Image
        jpg = io.BytesIO(); Image.new("RGB", (64, 48), (194, 74, 34)).save(jpg, "JPEG")
        req = urllib.request.Request(f"{b._cel.url}/api/subir/{s['codigo']}", data=jpg.getvalue(), method="POST", headers={"Content-Type": "image/jpeg"})
        with urllib.request.urlopen(req, timeout=10) as r: ver(r.status == 200, "el celular sube una foto")
        r = b.recoger()
        ver(len(r["fotos"]) == 1 and (carpeta / r["fotos"][0]["nombre"]).is_file(), "llega como archivo en la carpeta temporal")
        n = r["fotos"][0]["nombre"]
        ver(b.copiar(n)["ok"], "Copiar la deja en el portapapeles")
        ver(not b.copiar("../fuera.jpg")["ok"], "no copia nada fuera de la carpeta")
        b.quitar(n); ver(not (carpeta / n).exists(), "Quitar borra el archivo")
    b.cerrar()
    ver(not carpeta.exists(), "al cerrar se borra la carpeta (y la sesión del servicio)")
    print("Buzón: todo bien" if not malos else f"Buzón: {malos} MAL")
    return not malos


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    if "--probar" in sys.argv: sys.exit(0 if probar() else 1)
    abrir()
