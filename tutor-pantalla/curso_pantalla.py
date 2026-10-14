"""Cursos de una app sin API (modo curso de tutor-pantalla): cargar el curso, leer el estado de la app, revisar el
«Tu turno» sin IA y encontrar lo que cada paso señala. La página y el tutor van en panel_curso.py.

Un curso es una carpeta con curso.json y un JSON por módulo (formato en el README, «Cómo hacer un curso»).
Los nombres de los controles van como en la app; como cambian con el idioma de Windows, cada nombre puede ser una
lista: ["Pencil", "Lápiz"]. Se comparan sin mayúsculas ni acentos."""
import json, re, subprocess, time, unicodedata
from pathlib import Path

import ojos

# Lo que se comprueba sin IA en un «Tu turno» (cada objeto de "pide" y cada "si" de un error típico)
TIPOS_PIDE = {
    "activo":  "un control activado o elegido (herramienta, opción, pestaña): {\"tipo\": \"activo\", \"nombre\": [...]}",
    "nombre":  "un control cuyo nombre empieza así (\"Color 1: \" + lo que sigue): {\"tipo\": \"nombre\", \"empieza\": \"Color 1: \", \"es\": [...]}",
    "texto":   "un texto de la ventana (la barra de estado): {\"tipo\": \"texto\", \"es\": [...]} o \"contiene\"",
    "valor":   "el valor de un campo, lista o deslizador: {\"tipo\": \"valor\", \"nombre\": [...], \"es\": [...]} o \"contiene\"",
    "titulo":  "el título de la ventana (p. ej. el archivo guardado): {\"tipo\": \"titulo\", \"contiene\": [...]}",
    "existe":  "un control o una ventana de la app con ese nombre (un diálogo abierto): {\"tipo\": \"existe\", \"nombre\": [...]}",
}
PRIVADO = re.compile(r"^(signed in as|iniciaste sesi|sesi[oó]n iniciada|account|cuenta)", re.I)    # el botón de la cuenta lleva su nombre


def norm(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s.replace("×", "x")).strip()


def lista(v):
    return [v] if isinstance(v, str) else list(v or [])


def es_uno(texto, opciones, modo="es"):
    t = norm(texto)
    return any((t == norm(o)) if modo == "es" else (norm(o) in t) for o in lista(opciones))


# ---------- El curso ----------
class Modulo:
    def __init__(self, ruta, d):
        self.ruta, self.d = ruta, d
        self.titulo, self.codigo = d.get("titulo", ruta.stem), d.get("codigo", "")
        self.pasos = d.get("pasos") or []
        if not self.pasos: raise ValueError(f"{ruta.name}: no tiene pasos")
        for i, p in enumerate(self.pasos):
            donde = f"{ruta.name}, paso {i + 1}"
            if not p.get("texto"): raise ValueError(f"{donde}: le falta «texto»")
            for s in p.get("senalar") or []:
                if not s.get("nombre") and not s.get("empieza"): raise ValueError(f"{donde}: cada «senalar» lleva «nombre» (o «empieza»)")
            t = p.get("turno")
            if t:
                for q in (t.get("pide") or []) + [e.get("si") or {} for e in t.get("errores") or []]:
                    if q.get("tipo") not in TIPOS_PIDE: raise ValueError(f"{donde}: «{q.get('tipo')}» no es un tipo de comprobación ({', '.join(TIPOS_PIDE)})")
                if not t.get("pide") and not t.get("tutor"): raise ValueError(f"{donde}: el «turno» necesita «pide» (sin IA) o «tutor» (con captura)")
                if t.get("tutor") and not isinstance(t["tutor"], dict): raise ValueError(f"{donde}: «tutor» va así: {{\"revisar\": \"qué tiene que verse\"}}")


class Curso:
    def __init__(self, ruta):
        self.ruta = Path(ruta).resolve()
        self.carpeta = self.ruta.parent
        self.d = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.titulo = self.d.get("titulo", "")
        self.app = self.d.get("app") or {}
        if not self.app.get("exe"): raise ValueError("curso.json: falta «app»: {\"nombre\": \"Paint\", \"exe\": \"mspaint\"}")
        self.app_nombre = self.app.get("nombre") or self.app["exe"]
        self.modulos = [Modulo(self.carpeta / m, json.loads((self.carpeta / m).read_text(encoding="utf-8"))) for m in self.d.get("modulos") or []]
        if not self.modulos: raise ValueError("curso.json: «modulos» está vacío")
        self.progreso_ruta = self.carpeta / "progreso.json"

    def progreso(self):
        try:
            d = json.loads(self.progreso_ruta.read_text(encoding="utf-8"))
            m = max(0, min(len(self.modulos) - 1, int(d["m"])))
            return m, max(0, min(len(self.modulos[m].pasos) - 1, int(d["n"])))
        except Exception:
            return 0, 0

    def guardar_progreso(self, m, n):
        try: self.progreso_ruta.write_text(json.dumps({"m": m, "n": n, "cuando": time.strftime("%Y-%m-%d %H:%M")}), encoding="utf-8")
        except OSError: pass


# ---------- La app ----------
def ventana_app(exe):
    """La ventana principal de la app (la más reciente de ese ejecutable), o None."""
    return next((v for v in ojos.listar_ventanas() if v["app"].lower() == exe.lower() and not v["minimizada"]), None) \
        or next((v for v in ojos.listar_ventanas() if v["app"].lower() == exe.lower()), None)


def ventanas_app(exe):
    return [v for v in ojos.listar_ventanas() if v["app"].lower() == exe.lower()]


def abrir_app(app):
    subprocess.Popen(app.get("abrir") or app["exe"], shell=True)


def estado(exe):
    """{"titulo", "titulos", "controles": [...]} de la ventana de la app con la que trabaja (la más reciente; en las apps
    modernas los diálogos van dentro de ella), o None si no está abierta. Solo una: con dos Paint abiertos, mezclar el
    lienzo de uno con el título del otro daría por buena una mezcla."""
    v = ventana_app(exe)
    if not v: return None
    vs = [v]
    ctrl = []
    for v in vs:
        ctrl += [dict(c, ventana=v["titulo"]) for c in ojos.leer_estado(v["hwnd"])]
        ctrl.append({"tipo": "ventana", "nombre": v["titulo"], "caja": None, "activo": False, "valor": "", "ventana": v["titulo"]})
    return {"titulo": vs[0]["titulo"], "titulos": [v["titulo"] for v in vs], "controles": ctrl}


def cumple(est, q):
    """¿El estado cumple esta comprobación ("pide" o "si")?"""
    if est is None: return False
    tipo, cs = q["tipo"], est["controles"]
    if tipo == "activo":
        return any(c["activo"] and es_uno(c["nombre"], q["nombre"]) for c in cs)
    if tipo == "nombre":
        pre = norm(q["empieza"])
        return any(norm(c["nombre"]).startswith(pre) and es_uno(c["nombre"][len(q["empieza"]):], q["es"]) for c in cs)
    if tipo == "texto":
        modo = "contiene" if "contiene" in q else "es"
        return any(c["tipo"] == "texto" and es_uno(c["nombre"], q.get(modo), modo) for c in cs)
    if tipo == "valor":
        modo = "contiene" if "contiene" in q else "es"
        return any(es_uno(c["nombre"], q["nombre"]) and c["valor"] and es_uno(c["valor"], q.get(modo), modo) for c in cs)
    if tipo == "titulo":
        return any(es_uno(t, q["contiene"], "contiene") for t in est["titulos"])
    if tipo == "existe":
        return any(es_uno(c["nombre"], q["nombre"]) for c in cs)
    return False


def revisar_turno(est, turno):
    """La revisión sin IA: {"estado": bien | parcial | mal | vacio, "ok", "total", "mensaje", "puntos"}.
    Si el turno también lleva "tutor", "bien" aquí significa que falta la revisión del tutor (la pide el panel)."""
    if est is None:
        return {"estado": "vacio", "ok": 0, "total": len(turno.get("pide") or []), "puntos": [],
                "mensaje": "No encuentro la app abierta: ábrela y vuelve a pulsar Comprobar."}
    pide = turno.get("pide") or []
    puntos = [{"ok": cumple(est, q), "texto": q.get("texto") or q.get("nombre") or q["tipo"]} for q in pide]
    ok = sum(p["ok"] for p in puntos)
    if ok == len(pide):
        return {"estado": "bien", "ok": ok, "total": len(pide), "puntos": puntos, "mensaje": turno.get("bien", "¡Bien hecho!")}
    for e in turno.get("errores") or []:                 # el primer error típico que se reconoce
        if cumple(est, e["si"]):
            return {"estado": "mal", "ok": ok, "total": len(pide), "puntos": puntos, "mensaje": e["mensaje"]}
    falta = next(p["texto"] for p in puntos if not p["ok"])
    return {"estado": "parcial" if ok else "mal", "ok": ok, "total": len(pide), "puntos": puntos,
            "mensaje": turno.get("falta", "Todavía falta: {falta}.").replace("{falta}", falta[:1].lower() + falta[1:])}


def buscar(est_o_controles, objetivo):
    """El control que señala un «senalar» ({"nombre": [...]} o {"empieza": "Color 1"}, "tipo" opcional): el visible más
    pequeño con ese nombre (en Paint, «Line» es a la vez el elemento de la lista y su botón: se queda el botón, el de dentro)."""
    cs = est_o_controles["controles"] if isinstance(est_o_controles, dict) else est_o_controles
    def nombre_ok(n):
        if objetivo.get("empieza"): return any(norm(n).startswith(norm(e)) for e in lista(objetivo["empieza"]))
        return es_uno(n, objetivo["nombre"])
    cand = [c for c in cs if c.get("caja") and c["tipo"] != "texto" and nombre_ok(c["nombre"])
            and (not objetivo.get("tipo") or c["tipo"] == objetivo["tipo"])]
    if not cand: return None
    return min(cand, key=lambda c: (c["caja"][2] - c["caja"][0]) * (c["caja"][3] - c["caja"][1]))


def contexto_tutor(est, app):
    """El estado de la app en texto para el tutor (sin imagen): lo activo, los valores, los textos con números y las
    ventanas abiertas. Nunca el botón de la cuenta (lleva el nombre de la persona)."""
    if est is None: return f"{app} no está abierta."
    cs = [c for c in est["controles"] if not PRIVADO.search(c["nombre"])]
    activos = sorted({c["nombre"] for c in cs if c["activo"]})
    valores = sorted({f"{c['nombre']} = {c['valor']}" for c in cs if c["valor"] and c["nombre"]})
    textos = [c["nombre"] for c in cs if c["tipo"] == "texto" and re.search(r"\d", c["nombre"])][:8]
    partes = [f"Ventanas de {app}: " + "; ".join(est["titulos"]),
              "Activo o elegido: " + (", ".join(activos) or "(nada)"),
              "Valores: " + (", ".join(valores[:15]) or "(ninguno)")]
    if textos: partes.append("Textos: " + ", ".join(textos))
    nombres = sorted({c["nombre"] for c in cs if c["tipo"] in ("botón", "menú", "pestaña", "opción", "elemento", "casilla") and c["nombre"]})
    partes.append("Controles que se pueden señalar por nombre: " + ", ".join(nombres[:160]))
    return "\n".join(partes)


def simular(pide=(), extra=()):
    """Un estado de mentira para las pruebas: cumple justo lo de `pide` (y lo de `extra`), con el primer nombre de cada lista."""
    cs, titulos = [], ["Sin título - app"]
    for q in list(pide) + list(extra):
        t = q["tipo"]
        if t == "activo": cs.append({"tipo": "botón", "nombre": lista(q["nombre"])[0], "caja": (0, 0, 1, 1), "activo": True, "valor": ""})
        elif t == "nombre": cs.append({"tipo": "opción", "nombre": q["empieza"] + lista(q["es"])[0], "caja": (0, 0, 1, 1), "activo": True, "valor": ""})
        elif t == "texto": cs.append({"tipo": "texto", "nombre": lista(q.get("es") or q.get("contiene"))[0], "caja": (0, 0, 1, 1), "activo": False, "valor": ""})
        elif t == "valor": cs.append({"tipo": "campo", "nombre": lista(q["nombre"])[0], "caja": (0, 0, 1, 1), "activo": False, "valor": lista(q.get("es") or q.get("contiene"))[0]})
        elif t == "titulo": titulos.insert(0, lista(q["contiene"])[0] + " - app")
        elif t == "existe": cs.append({"tipo": "ventana", "nombre": lista(q["nombre"])[0], "caja": None, "activo": False, "valor": ""})
    return {"titulo": titulos[0], "titulos": titulos, "controles": cs}
