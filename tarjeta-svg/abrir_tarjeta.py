"""Abre la Tarjeta SVG o, si ya está abierta, la trae al frente (un solo ejemplar). Lo usan «Mis clases», el botón de
los paneles y «Editar en la tarjeta» de las figuras del chat (CONTRATO.md §4).

python abrir_tarjeta.py                      la despliega
python abrir_tarjeta.py --figura '<json>'    además le carga una figura: {"tipo": "grafica", "spec": {...}} |
                                             {"tipo": "geometria", "guion": "..."} | {"tipo": "latex", "latex": "..."} | {"tipo": "svg", "svg": "..."}"""
import json, subprocess, sys, time, urllib.request
from pathlib import Path

AQUI = Path(__file__).resolve().parent
PUERTO = 4748


def _post(ruta, datos=None):
    req = urllib.request.Request(f"http://127.0.0.1:{PUERTO}{ruta}", data=json.dumps(datos or {}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=5) as r: return json.loads(r.read() or b"{}")


def viva():
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PUERTO}/hola", timeout=1) as r: return json.loads(r.read()).get("tarjeta") is True
    except Exception:
        return False


def abrir(contenido=None, esperar=20):
    """Despliega la tarjeta (arrancándola si hace falta) y, si hay contenido, se lo carga. Devuelve {"ok", ...}."""
    if not viva():
        exe = Path(sys.executable)
        sinconsola = exe.with_name("pythonw.exe") if exe.with_name("pythonw.exe").exists() else exe
        subprocess.Popen([str(sinconsola), str(AQUI / "tarjeta.py")], cwd=str(AQUI),
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NO_WINDOW", 0))
        t = time.time()
        while not viva():
            if time.time() - t > esperar: return {"ok": False, "error": "La tarjeta no arrancó."}
            time.sleep(0.2)
        time.sleep(1.5)                                        # que la página termine de cargar antes de mandarle la figura
    try:
        return _post("/figura", {"contenido": contenido}) if contenido else _post("/mostrar")
    except Exception as e:
        return {"ok": False, "error": f"No pude hablar con la tarjeta: {e}"}


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    a = sys.argv[1:]
    contenido = json.loads(a[a.index("--figura") + 1]) if "--figura" in a else None
    r = abrir(contenido)
    print(json.dumps(r, ensure_ascii=False))
    sys.exit(0 if r.get("ok") else 1)
