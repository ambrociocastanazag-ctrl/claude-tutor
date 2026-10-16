"""Fotos del celular para cualquier tutor (botón 📱 de ojos_ui.js): el cliente del servicio fotos-servidor/.

  Celular().abrir()    abre una sesión: {codigo, url, qr (SVG)}; la misma mientras el panel siga abierto
  Celular().recoger()  las fotos que llegaron (el servidor las BORRA al entregarlas), como adjuntos de imagen
  Celular().cerrar()   borra la sesión del servidor (al cerrar el panel; también con atexit)

La configuración va en tutor-pantalla/.env (NO se sube al repo; plantilla en .env.example):
  FOTOS_URL=https://<servicio>.up.railway.app
  FOTOS_CLAVE=<la misma TUTOR_CLAVE del servicio>
Las fotos nunca van directo al tutor: quedan como adjunto pendiente en el chat (con miniatura y ✕) y salen solo si él
envía el mensaje, igual que una imagen pegada."""
import atexit, base64, json, os, threading, time, urllib.error, urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
ENV = AQUI / ".env"


def config(ruta=ENV):
    """{FOTOS_URL, FOTOS_CLAVE} del .env (y de las variables de entorno, que mandan)."""
    c = {}
    try:
        for l in Path(ruta).read_text(encoding="utf-8").splitlines():
            l = l.strip()
            if l and not l.startswith("#") and "=" in l:
                k, v = l.split("=", 1); c[k.strip()] = v.strip().strip('"').strip("'")
    except OSError: pass
    for k in ("FOTOS_URL", "FOTOS_CLAVE"):
        if os.environ.get(k): c[k] = os.environ[k]
    return c


class Celular:
    def __init__(self, url=None, clave=None):
        c = config()
        self.url = (url or c.get("FOTOS_URL") or "").rstrip("/")
        self.clave = clave or c.get("FOTOS_CLAVE") or ""
        self.sesion, self.n, self.cerrojo = None, 0, threading.Lock()
        atexit.register(self.cerrar)

    @property
    def configurado(self): return bool(self.url and len(self.clave) >= 24)

    def _pedir(self, metodo, ruta, timeout=10):
        req = urllib.request.Request(self.url + ruta, method=metodo, data=b"" if metodo == "POST" else None,
                                     headers={"Authorization": "Bearer " + self.clave, "Accept": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r: return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try: return json.loads(e.read().decode("utf-8")) | {"_codigo": e.code}
            except ValueError: return {"ok": False, "error": f"El servicio respondió {e.code}.", "_codigo": e.code}
        except (urllib.error.URLError, OSError, ValueError) as e:
            return {"ok": False, "error": f"No pude hablar con el servicio de fotos ({getattr(e, 'reason', e)})."}

    def abrir(self):
        if not self.configurado:
            return {"ok": False, "error": "Falta configurar las fotos del celular (tutor-pantalla/.env: FOTOS_URL y FOTOS_CLAVE)."}
        with self.cerrojo:
            if self.sesion: return {"ok": True} | self.sesion
            r = self._pedir("POST", "/api/sesion")
            if r.get("ok"): self.sesion = {k: r[k] for k in ("codigo", "url", "inicio", "qr", "vida_min")}
            return r

    def recoger(self):
        """{"ok", "fotos": [adjuntos de imagen]}; si la sesión caducó, abre otra y lo dice ("nueva": True)."""
        with self.cerrojo:
            if not self.sesion: return {"ok": False, "error": "No hay sesión abierta."}
            r = self._pedir("GET", f"/api/fotos/{self.sesion['codigo']}")
        if r.get("_codigo") == 404:
            self.sesion = None
            n = self.abrir()
            return {"ok": n.get("ok", False), "fotos": [], "nueva": True, "error": n.get("error")} | ({k: n[k] for k in ("codigo", "url", "qr")} if n.get("ok") else {})
        if not r.get("ok"): return {"ok": False, "fotos": [], "error": r.get("error")}
        out = []
        for f in r.get("fotos") or []:
            self.n += 1
            mt = f.get("media_type") or "image/jpeg"
            ext = {"image/png": "png", "image/webp": "webp"}.get(mt, "jpg")
            out.append({"nombre": f"celular_{time.strftime('%H-%M')}_{self.n}.{ext}", "tipo": "imagen", "media_type": mt,
                        "datos": f["datos"], "vista": f"data:{mt};base64,{f['datos']}",
                        "tam": f"{max(1, round(len(f['datos']) * 3 / 4 / 1024))} KB"})
        return {"ok": True, "fotos": out}

    def cerrar(self):
        s, self.sesion = self.sesion, None
        if s and self.configurado: self._pedir("DELETE", f"/api/sesion/{s['codigo']}", timeout=4)


def probar(url=None, clave=None):
    """python celular.py --probar [url clave]: con el servicio corriendo (local o el de Railway), una vuelta completa."""
    malos = 0
    def ver(c, t):
        nonlocal malos
        print(("  ok " if c else "  ✘ MAL ") + t)
        if not c: malos += 1
    cel = Celular(url, clave)
    ver(cel.configurado, f"configurado ({cel.url or 'sin URL'})")
    a = cel.abrir()
    ver(a.get("ok") and len(a.get("codigo", "")) == 6 and "<svg" in a.get("qr", ""), f"abre sesión con código y QR ({a.get('error') or a.get('codigo')})")
    if not a.get("ok"): print("Celular: no se pudo probar"); return False
    ver(cel.abrir()["codigo"] == a["codigo"], "abrir otra vez devuelve la misma sesión (varias fotos)")
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==")
    def subir(codigo, datos, tipo="image/png"):
        req = urllib.request.Request(f"{cel.url}/api/subir/{codigo}", data=datos, method="POST", headers={"Content-Type": tipo})
        try:
            with urllib.request.urlopen(req, timeout=10) as r: return r.status
        except urllib.error.HTTPError as e: return e.code
    ver(subir(a["codigo"], png) == 200, "el celular sube una foto con el código")
    ver(subir(a["codigo"], b"hola", "text/plain") == 415, "no acepta lo que no es foto")
    otro = "000000" if a["codigo"] != "000000" else "000001"
    ver(subir(otro, png) == 404, "con un código que no existe no sube nada")
    r = cel.recoger()
    ver(r["ok"] and len(r["fotos"]) == 1 and r["fotos"][0]["vista"].startswith("data:image/png"), "el panel la recoge como adjunto")
    ver(cel.recoger()["fotos"] == [], "al entregarla se borró del servidor")
    req = urllib.request.Request(f"{cel.url}/api/fotos/{a['codigo']}", headers={"Authorization": "Bearer clave-falsa-de-prueba-0000000000"})
    try: urllib.request.urlopen(req, timeout=10); cod = 200
    except urllib.error.HTTPError as e: cod = e.code
    ver(cod == 401, "sin la clave no se puede leer nada")
    codigo = a["codigo"]; cel.cerrar()
    ver(subir(codigo, png) == 404, "al cerrar, la sesión se borra (el código ya no sirve)")
    print("Celular: todo bien" if not malos else f"Celular: {malos} MAL")
    return not malos


if __name__ == "__main__":
    import sys
    if "--probar" in sys.argv:
        a = [x for x in sys.argv[1:] if not x.startswith("--")]
        sys.exit(0 if probar(*(a[:2] if len(a) >= 2 else [])) else 1)
    print(__doc__)
