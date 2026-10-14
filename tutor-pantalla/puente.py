"""Puente entre el panel y una sesión de Claude Code (modo puente): lo que la persona escribe en el panel le llega
al chat de Claude Code, y lo que Claude Code responde aparece en el panel (con flechas encima de la ventana).

Los dos lados se hablan por archivos en una carpeta temporal (CARPETA):
  entrada/  panel → chat: un .json por mensaje (texto, ventana, controles) y su .png si llevó captura aprobada
  leidos/   el chat mueve aquí lo que ya leyó (el panel lo ve y dice «Claude Code lo está leyendo…»)
  salida/   chat → panel: respuestas («respuesta») y peticiones de captura («pedir_captura»)
  panel.json  el pid del panel y cuándo arrancó, mientras está abierto
La captura solo llega a entrada/ después de la vista previa y el clic en «Enviar al tutor»: el permiso sigue en el panel.
pedir-captura no captura nada: solo abre la vista previa en el panel, y la persona decide.

Uso desde Claude Code (el chat):
  python tutor-pantalla/panel_pantalla.py --puente      abre el panel (lanzarlo en segundo plano)
  python tutor-pantalla/puente.py esperar               espera el próximo mensaje del panel, lo imprime y termina
                                                        (lanzarlo en segundo plano: al terminar despierta al chat)
  python tutor-pantalla/puente.py responder "texto"     responde en el panel ("-" lee el texto de stdin);
                                                        una línea final  MARCAS: [...]  dibuja flechas, igual que el asistente
  python tutor-pantalla/puente.py pedir-captura "texto" le pide una captura (sale la vista previa en el panel)
  python tutor-pantalla/puente.py estado                ¿hay panel abierto? ¿mensajes sin leer?"""
import base64, ctypes, json, os, re, shutil, sys, tempfile, time
from pathlib import Path

CARPETA = Path(tempfile.gettempdir()) / "tutor-pantalla-puente"
ENTRADA, LEIDOS, SALIDA, PANEL = CARPETA / "entrada", CARPETA / "leidos", CARPETA / "salida", CARPETA / "panel.json"


def _escribir(ruta, datos):
    """Escritura atómica: el otro lado nunca lee un .json a medias."""
    tmp = ruta.with_suffix(".tmp")
    tmp.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, ruta)


def _leer(ruta):
    try: return json.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError): return None


def inicio_de(pid):
    """Cuándo arrancó un proceso (FILETIME), o None si ya no existe. Con el pid solo no basta: Windows reutiliza
    los pids y otro programa podía «heredar» el del panel cerrado."""
    k32 = ctypes.WinDLL("kernel32")
    h = k32.OpenProcess(0x1000, False, int(pid))            # PROCESS_QUERY_LIMITED_INFORMATION
    if not h: return None
    try:
        codigo, t = ctypes.c_ulong(), [ctypes.c_ulonglong() for _ in range(4)]
        if not k32.GetExitCodeProcess(h, ctypes.byref(codigo)) or codigo.value != 259: return None    # STILL_ACTIVE
        if not k32.GetProcessTimes(h, *[ctypes.byref(x) for x in t]): return None
        return t[0].value
    finally: k32.CloseHandle(h)


def panel_abierto():
    d = _leer(PANEL)
    return bool(d and d.get("inicio") and inicio_de(d.get("pid", 0)) == d["inicio"])


# ---------- Lado del panel ----------
class LadoPanel:
    def __init__(self):
        if panel_abierto(): raise RuntimeError("Ya hay un panel en modo puente abierto.")
        shutil.rmtree(CARPETA, ignore_errors=True)           # restos de una vez anterior (capturas incluidas)
        for c in (ENTRADA, LEIDOS, SALIDA): c.mkdir(parents=True, exist_ok=True)
        _escribir(PANEL, {"pid": os.getpid(), "inicio": inicio_de(os.getpid())})
        self.n = 0

    def mandar(self, texto, ventana=None, cap=None, archivos=()):
        """Un mensaje para el chat. cap: la Captura ya aprobada en la vista previa (o None). archivos: los que adjuntó
        la persona ({"nombre", "tipo", "datos"}: base64, o el texto tal cual); se guardan junto al mensaje. Devuelve su id."""
        self.n += 1; mid = f"m{self.n:04d}"
        d = {"id": mid, "hora": time.strftime("%H:%M:%S"), "texto": texto, "ventana": ventana}
        rutas = []
        for k, a in enumerate(archivos or []):
            nombre = re.sub(r"[^\w.\-]+", "_", str(a.get("nombre") or "archivo"))[:80]
            f = ENTRADA / f"{mid}_{k}_{nombre}"
            if a.get("tipo") == "texto": f.write_text(str(a.get("datos") or ""), encoding="utf-8")
            else: f.write_bytes(base64.b64decode(a.get("datos") or ""))
            rutas.append({"ruta": str(f), "tipo": a.get("tipo")})
        if rutas: d["archivos"] = rutas
        if cap is not None:
            png = ENTRADA / f"{mid}.png"; cap.img.save(png)
            d.update(captura=str(png), tam=list(cap.img.size), controles=cap.texto_controles())
        _escribir(ENTRADA / f"{mid}.json", d)
        return mid

    def leido(self, mid):
        return (LEIDOS / f"{mid}.json").exists()

    def recibir(self):
        """Lo que mandó el chat, en orden; se borra al leerlo."""
        out = []
        for f in sorted(SALIDA.glob("*.json")):
            d = _leer(f)
            try: f.unlink()
            except OSError: pass
            if d: out.append(d)
        return out

    def cerrar(self):
        shutil.rmtree(CARPETA, ignore_errors=True)            # se van las capturas: no quedan en disco


# ---------- Lado del chat ----------
def _formatear(d):
    v = d.get("ventana") or {}
    partes = [f"[Mensaje {d['id']} del panel, {d.get('hora', '')}]" + (f" Ventana elegida: «{v.get('titulo')}» ({v.get('app')})" if v else "")]
    partes.append(f"Persona: {d.get('texto', '')}")
    if d.get("captura"):
        w, h = d.get("tam") or ("?", "?")
        partes.append(f"Captura aprobada: {d['captura']} ({w}×{h} px). Léela con Read.")
        partes.append("Controles de la ventana:\n" + (d.get("controles") or ""))
    for a in d.get("archivos") or []:
        partes.append(f"Archivo adjunto ({a.get('tipo')}): {a['ruta']}. Léelo con Read.")
    return "\n".join(partes)


def esperar(segundos=None):
    """Bloquea hasta que llegue algo del panel (o se cierre). Imprime todos los mensajes nuevos y los da por leídos."""
    fin = time.time() + segundos if segundos else None
    revisado = 0
    while True:
        nuevos = sorted(ENTRADA.glob("*.json")) if ENTRADA.exists() else []
        if nuevos:
            textos = []
            for f in nuevos:
                d = _leer(f)
                if not d: continue
                textos.append(_formatear(d))
                os.replace(f, LEIDOS / f.name)
            print("\n\n".join(textos))
            print("\n(Responde con: python tutor-pantalla/puente.py responder \"…\"; para señalar, una última línea "
                  "MARCAS: [{\"id\": N, \"texto\": \"…\"}] con ids de la lista o \"caja\": [x, y, w, h] en píxeles de la captura. "
                  "Después vuelve a lanzar «esperar» en segundo plano.)")
            return 0
        if time.time() - revisado > 3:
            revisado = time.time()
            if not panel_abierto(): print("El panel del puente está cerrado."); return 2
        if fin and time.time() > fin: print("Sin mensajes nuevos."); return 1
        time.sleep(0.4)


def _a_salida(d):
    if not panel_abierto(): print("El panel del puente está cerrado: no se mandó nada."); return 2
    _escribir(SALIDA / f"{time.time_ns()}.json", d)
    print("Enviado al panel."); return 0


def main(a):
    try: sys.stdout.reconfigure(encoding="utf-8"); sys.stdin.reconfigure(encoding="utf-8")
    except Exception: pass
    if a[:1] == ["esperar"]:
        return esperar(float(a[1]) if len(a) > 1 else None)
    if a[:1] in (["responder"], ["pedir-captura"]) and len(a) == 2:
        texto = sys.stdin.read() if a[1] == "-" else a[1]
        return _a_salida({"tipo": "respuesta" if a[0] == "responder" else "pedir_captura", "texto": texto.strip()})
    if a[:1] == ["estado"]:
        sin_leer = len(list(ENTRADA.glob("*.json"))) if ENTRADA.exists() else 0
        print(f"Panel {'abierto' if panel_abierto() else 'cerrado'}; mensajes sin leer: {sin_leer}."); return 0
    print(__doc__); return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
