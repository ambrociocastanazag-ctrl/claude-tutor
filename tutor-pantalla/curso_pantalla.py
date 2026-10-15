"""Cursos de una app sin API (modo curso de tutor-pantalla): cargar el curso, leer el estado de la app, revisar el
«Tu turno» sin IA y encontrar lo que cada paso señala. La página y el tutor van en panel_curso.py.

Un curso es una carpeta con curso.json y un JSON por módulo (formato en el README, «Cómo hacer un curso»).
Los nombres de los controles van como en la app; como cambian con el idioma de Windows, cada nombre puede ser una
lista: ["Pencil", "Lápiz"]. Se comparan sin mayúsculas ni acentos."""
import json, os, re, shutil, subprocess, tempfile, time, unicodedata, urllib.error, urllib.request
import xml.etree.ElementTree as ET
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
# Cursos de código (curso.json con "proyecto"): se revisan con Maven, sin IA (README, «Cursos de código»)
TIPOS_CODIGO = {
    "compila": "el proyecto compila: {\"tipo\": \"compila\"}",
    "archivo": "un archivo del proyecto (la ruta admite comodines * y **): {\"tipo\": \"archivo\", \"ruta\": \"src/**/entity/*.java\", \"contiene\": [...], \"no_contiene\": [...], \"regex\": \"...\"}",
    "pruebas": "pruebas JUnit: {\"tipo\": \"pruebas\", \"clases\": [...] o \"todas\", \"ocultas\": true, \"minimo\": 3}",
    "http":    "una petición a la API que corre el estudiante: {\"tipo\": \"http\", \"metodo\": \"POST\", \"url\": \"...\", \"cuerpo\": {...}, \"codigo\": 201, \"json\": {...}}",
}
IGNORAR_COPIA = ("target", ".git", "node_modules")
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
def es_todas(q):
    """¿Este «pruebas» pide correr todas las pruebas del proyecto ("clases": "todas")?"""
    c = q.get("clases")
    return isinstance(c, str) and c.strip().lower() == "todas"


def tiene_comodin(ruta): return any(ch in str(ruta) for ch in "*?[")


def validar_codigo(q, donde, con_proyecto):
    """Valida un «pide» (o «si») de los tipos de código; lanza ValueError con la causa."""
    t = q.get("tipo")
    if not con_proyecto: raise ValueError(f"{donde}: «{t}» solo existe en cursos con «proyecto» en curso.json")
    if t == "archivo":
        if not q.get("ruta"): raise ValueError(f"{donde}: «archivo» necesita «ruta» (relativa al proyecto)")
        if os.path.isabs(str(q["ruta"])) or ".." in Path(str(q["ruta"])).parts: raise ValueError(f"{donde}: «ruta» tiene que ser relativa al proyecto (sin «..»)")
        for k in ("contiene", "no_contiene"):
            if k in q and not all(isinstance(x, str) for x in lista(q[k])): raise ValueError(f"{donde}: «{k}» es un texto o una lista de textos")
        if q.get("regex"):
            try: re.compile(q["regex"])
            except re.error as e: raise ValueError(f"{donde}: «regex» mal escrita ({e})")
    elif t == "pruebas":
        if not es_todas(q) and not lista(q.get("clases")): raise ValueError(f"{donde}: «pruebas» necesita «clases»: [\"MiTest\"] (o \"todas\")")
        if "minimo" in q and not (isinstance(q["minimo"], int) and q["minimo"] >= 0): raise ValueError(f"{donde}: «minimo» es un número entero")
    elif t == "http":
        if not str(q.get("url", "")).startswith("http"): raise ValueError(f"{donde}: «http» necesita «url» (http://…)")
        if str(q.get("metodo", "GET")).upper() not in ("GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"): raise ValueError(f"{donde}: «metodo» raro: {q.get('metodo')}")
        if "codigo" in q and not isinstance(q["codigo"], int): raise ValueError(f"{donde}: «codigo» es un número (200, 201…)")


def valida_q(q, donde, con_proyecto):
    if q.get("tipo") in TIPOS_CODIGO: validar_codigo(q, donde, con_proyecto)
    elif q.get("tipo") not in TIPOS_PIDE:
        raise ValueError(f"{donde}: «{q.get('tipo')}» no es un tipo de comprobación ({', '.join(list(TIPOS_PIDE) + (list(TIPOS_CODIGO) if con_proyecto else []))})")


class Modulo:
    def __init__(self, ruta, d, con_proyecto=False, proyectos=()):
        """con_proyecto: el curso tiene «proyecto» (el de siempre); proyectos: los nombres de «proyectos» (los turnos que lo piden)."""
        self.ruta, self.d = ruta, d
        self.titulo, self.codigo = d.get("titulo", ruta.stem), d.get("codigo", "")
        self.pasos = d.get("pasos") or []
        if not self.pasos: raise ValueError(f"{ruta.name}: no tiene pasos")
        for i, p in enumerate(self.pasos):
            donde = f"{ruta.name}, paso {i + 1}"
            if not p.get("texto"): raise ValueError(f"{donde}: le falta «texto»")
            for s in p.get("senalar") or []:
                if not s.get("nombre") and not s.get("empieza") and s.get("linea") is None: raise ValueError(f"{donde}: cada «senalar» lleva «nombre» (o «empieza», o «linea» en un curso de código)")
            t = p.get("turno")
            if t:
                qs = (t.get("pide") or []) + [e.get("si") or {} for e in t.get("errores") or []]
                if t.get("proyecto") is not None and t["proyecto"] not in proyectos:
                    raise ValueError(f"{donde}: «proyecto» «{t['proyecto']}» no está en «proyectos» de curso.json ({', '.join(proyectos) or 'no hay ninguno'})")
                if any(q.get("tipo") in TIPOS_CODIGO for q in qs) and not t.get("proyecto") and not con_proyecto:
                    raise ValueError(f"{donde}: este turno revisa código: pon «proyecto»: \"<nombre>\" (de «proyectos») o «proyecto» en curso.json")
                for q in qs:
                    valida_q(q, donde, bool(con_proyecto or proyectos))
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
        self.proyecto = Path(self.d["proyecto"]) if self.d.get("proyecto") else None       # proyecto Maven del estudiante (curso de código)
        if self.proyecto and not self.proyecto.is_dir(): raise ValueError(f"curso.json: «proyecto» no existe: {self.proyecto}")
        self.proyectos = {}                                        # nombre → {"ruta": Path, "maven": subcarpeta con el pom ("" = la raíz)}
        for nombre, info in (self.d.get("proyectos") or {}).items():
            if not isinstance(info, dict) or not info.get("ruta"): raise ValueError(f"curso.json: «proyectos.{nombre}» necesita «ruta»")
            mv = str(info.get("maven") or "").strip("/\\")
            if os.path.isabs(mv) or ".." in Path(mv).parts: raise ValueError(f"curso.json: «proyectos.{nombre}.maven» es una subcarpeta de «ruta» (sin «..»)")
            self.proyectos[nombre] = {"ruta": Path(info["ruta"]), "maven": mv}
        self.java_home = self.d.get("java_home") or os.environ.get("JAVA_HOME", "")    # el JDK del curso; si no, el del sistema
        self.modulos = [Modulo(self.carpeta / m, json.loads((self.carpeta / m).read_text(encoding="utf-8")), bool(self.proyecto), set(self.proyectos)) for m in self.d.get("modulos") or []]
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


def cumple(est, q, ctx=None):
    """¿El estado cumple esta comprobación ("pide" o "si")? Las de código (compila, archivo, pruebas, http) las resuelve `ctx`."""
    if q["tipo"] in TIPOS_CODIGO: return bool(ctx and ctx.evalua(q)[0])
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


def minuscula_inicial(t):
    """«El Color 1 es rojo» → «el Color 1 es rojo»; un nombre propio de código (PrestamoService.java, Libro) se queda igual."""
    primera = t.split(" ", 1)[0]
    if re.search(r"[A-Z]", primera[1:]) or "." in primera or "(" in primera: return t
    return t[:1].lower() + t[1:]


def revisar_turno(est, turno, ctx=None):
    """La revisión sin IA: {"estado": bien | parcial | mal | vacio, "ok", "total", "mensaje", "puntos"}.
    Si el turno también lleva "tutor", "bien" aquí significa que falta la revisión del tutor (la pide el panel)."""
    pide = turno.get("pide") or []
    if est is None and (ctx is None or any(q["tipo"] not in TIPOS_CODIGO for q in pide)):
        return {"estado": "vacio", "ok": 0, "total": len(pide), "puntos": [],
                "mensaje": "No encuentro la app abierta: ábrela y vuelve a pulsar Comprobar."}
    puntos = []
    for q in pide:
        ok, detalle = ctx.evalua(q) if q["tipo"] in TIPOS_CODIGO and ctx else (cumple(est, q, ctx), "")
        puntos.append({"ok": ok, "texto": q.get("texto") or q.get("nombre") or q["tipo"], "detalle": detalle})
    ok = sum(p["ok"] for p in puntos)
    if ok == len(pide):
        return {"estado": "bien", "ok": ok, "total": len(pide), "puntos": puntos, "mensaje": turno.get("bien", "¡Bien hecho!")}
    for e in turno.get("errores") or []:                 # el primer error típico que se reconoce
        if cumple(est, e["si"], ctx):
            return {"estado": "mal", "ok": ok, "total": len(pide), "puntos": puntos, "mensaje": e["mensaje"]}
    mal = next(p for p in puntos if not p["ok"])
    falta = mal["texto"] + (f" ({mal['detalle']})" if mal.get("detalle") else "")
    return {"estado": "parcial" if ok else "mal", "ok": ok, "total": len(pide), "puntos": puntos,
            "mensaje": turno.get("falta", "Todavía falta: {falta}.").replace("{falta}", minuscula_inicial(falta))}


def buscar(est_o_controles, objetivo):
    """El control que señala un «senalar» ({"nombre": [...]} o {"empieza": "Color 1"}, "tipo" opcional): el visible más
    pequeño con ese nombre (en Paint, «Line» es a la vez el elemento de la lista y su botón: se queda el botón, el de dentro)."""
    cs = est_o_controles["controles"] if isinstance(est_o_controles, dict) else est_o_controles
    def nombre_ok(n):
        if objetivo.get("empieza"): return any(norm(n).startswith(norm(e)) for e in lista(objetivo["empieza"]))
        return es_uno(n, objetivo["nombre"])
    def con_estado(n):   # algunas apps añaden un estado al nombre: «Explorer (Ctrl+Shift+E) - 1 unsaved file» en VS Code
        return any(norm(n).startswith(norm(e) + " - ") for e in lista(objetivo.get("nombre")))
    def candidatos(ok):
        return [c for c in cs if c.get("caja") and c["tipo"] != "texto" and ok(c["nombre"])
                and (not objetivo.get("tipo") or c["tipo"] == objetivo["tipo"])]
    cand = candidatos(nombre_ok) or (candidatos(con_estado) if not objetivo.get("empieza") else [])
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


# ---------- Cursos de código: Maven, archivos y la API del estudiante ----------
def copiar_proyecto(raiz, destino):
    """Copia el proyecto (sin target/, .git ni node_modules; con su .env) a `destino`. Nunca escribe en `raiz`."""
    shutil.copytree(raiz, destino, ignore=shutil.ignore_patterns(*IGNORAR_COPIA), dirs_exist_ok=True)


def anadir_ocultas(carpeta, destino):
    """Las pruebas ocultas de `carpeta` (<curso>/pruebas/<stem>/) al proyecto copiado. Si traen su propio `src/`, se
    respeta tal cual; si no, su contenido cuelga de src/test/java/ (la ruta de paquetes se conserva). Devuelve los .java añadidos."""
    base = Path(carpeta)
    if not base.is_dir(): return []
    sal = Path(destino) if (base / "src").is_dir() else Path(destino) / "src" / "test" / "java"
    shutil.copytree(base, sal, dirs_exist_ok=True)
    return [f.name for f in base.rglob("*.java")]


def _compila_error(salida, ocultos):
    """El primer error del compilador: «Archivo.java línea 12: cannot find symbol», o None si no hay."""
    lineas = salida.splitlines()
    for i, l in enumerate(lineas):
        m = re.search(r"\[ERROR\]\s+(?:/)?(.+?\.java):\[(\d+),\d+\]\s*(.*)", l)
        if m:
            nombre = Path(m.group(1)).name
            extra = next((x.split("]", 1)[1].strip() for x in lineas[i + 1:i + 4] if re.match(r"\[ERROR\]\s+(symbol|location|required|found)", x.strip())), "")
            quien = f"{nombre}{' (prueba del profe)' if nombre in ocultos else ''} línea {m.group(2)}"
            return f"{quien}: {m.group(3).strip()}" + (f" ({extra})" if extra else "")
    return None


def _primer_error_build(salida):
    for l in salida.splitlines():
        l = l.strip()
        if l.startswith("[ERROR]") and "Failed to execute goal" not in l and "->" not in l and len(l) > 10 and "Help" not in l:
            return l[7:].strip()[:300]
    for l in salida.splitlines():
        if "[ERROR]" in l: return l.split("[ERROR]", 1)[1].strip()[:300]
    return (salida.strip().splitlines() or ["Maven falló sin decir por qué"])[-1][:300]


def _lee_reportes(carpeta):
    """{ClaseSimple: {"tests", "fallos", "primer"}} de target/surefire-reports/TEST-*.xml; «primer» = el primer mensaje de JUnit sin traza."""
    res = {}
    for f in Path(carpeta).glob("TEST-*.xml"):
        try: raiz = ET.parse(f).getroot()
        except ET.ParseError: continue
        for suite in ([raiz] if raiz.tag == "testsuite" else raiz.iter("testsuite")):
            simple = suite.get("name", f.stem[5:]).rsplit(".", 1)[-1]
            r = res.setdefault(simple, {"tests": 0, "fallos": 0, "primer": ""})
            r["tests"] += int(suite.get("tests", 0)) - int(suite.get("skipped", 0))
            for tc in suite.iter("testcase"):
                bad = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
                if bad is None: continue
                r["fallos"] += 1
                if not r["primer"]:
                    msg = (bad.get("message") or "").strip().splitlines()
                    msg = msg[0] if msg else (bad.get("type") or "error").rsplit(".", 1)[-1]
                    r["primer"] = f"{tc.get('name', '')}: {msg}"[:300]
    return res


def correr_maven(raiz, java_home, clases=(), ocultas_de=None, timeout=600, maven="", todas=False):
    """UNA corrida de Maven Wrapper sobre una copia temporal de `raiz` (la copia se borra al terminar).
    clases: simples (si hay, `test -Dtest=A,B`; si no, solo `compile`); todas: `test` sin -Dtest (todas las pruebas);
    ocultas_de: carpeta con las pruebas ocultas a añadir; maven: subcarpeta de `raiz` donde está el pom (se copia el
    repo entero y Maven corre ahí; el .env de la raíz también se copia a esa subcarpeta si no tiene uno).
    Devuelve {"compila": bool, "error": str, "clases": {...}, "seg": float}."""
    raiz = Path(raiz); t0 = time.time()
    if not raiz.is_dir():
        return {"compila": False, "error": f"No encuentro la carpeta del proyecto ({raiz}).", "clases": {}, "seg": 0.0}
    tmp = Path(tempfile.mkdtemp(prefix="curso_mvn_"))
    try:
        copiar_proyecto(raiz, tmp)
        base = tmp / maven if maven else tmp
        if maven and (raiz / ".env").is_file() and not (base / ".env").exists() and base.is_dir():
            shutil.copy2(raiz / ".env", base / ".env")
        ocultos = anadir_ocultas(ocultas_de, base) if ocultas_de else []
        mvnw = base / ("mvnw.cmd" if os.name == "nt" else "mvnw")
        if not mvnw.exists():
            donde = f" en {maven}/" if maven else ""
            return {"compila": False, "error": f"El proyecto no tiene Maven Wrapper (mvnw.cmd){donde}.", "clases": {}, "seg": time.time() - t0}
        env = dict(os.environ)
        if java_home:
            env["JAVA_HOME"] = str(java_home); env["PATH"] = str(Path(java_home) / "bin") + os.pathsep + env.get("PATH", "")
        cmd = [str(mvnw), "-B", "-q"] + (["test"] if todas else ["test", "-Dtest=" + ",".join(clases), "-Dsurefire.failIfNoSpecifiedTests=false"] if clases else ["compile"])
        try:
            p = subprocess.run(cmd, cwd=str(base), env=env, capture_output=True, timeout=timeout,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            salida = (p.stdout + b"\n" + p.stderr).decode("utf-8", "replace")
        except subprocess.TimeoutExpired:
            return {"compila": False, "error": f"Maven tardó más de {timeout} s.", "clases": {}, "seg": time.time() - t0}
        reps = _lee_reportes(base / "target" / "surefire-reports")
        err = _compila_error(salida, ocultos)
        build = None
        if err is None and p.returncode != 0 and not reps:                # no compiló por otra razón, o Maven ni arrancó
            build = _primer_error_build(salida)
        return {"compila": err is None and build is None, "error": err or build or "", "clases": reps, "seg": time.time() - t0,
                "salida": salida[-3000:]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _colapsa(s): return re.sub(r"\s+", " ", s)


def contiene_json(resp, esperado):
    """¿`resp` contiene `esperado`? Subconjunto: en dicts, esas claves con esos valores; en listas, algún elemento lo contiene."""
    if isinstance(esperado, dict):
        if isinstance(resp, list): return any(contiene_json(x, esperado) for x in resp)
        return isinstance(resp, dict) and all(k in resp and contiene_json(resp[k], v) for k, v in esperado.items())
    if isinstance(esperado, list):
        return isinstance(resp, list) and all(any(contiene_json(x, e) for x in resp) for e in esperado)
    if isinstance(esperado, (int, float)) and isinstance(resp, (int, float)) and not isinstance(esperado, bool) and not isinstance(resp, bool):
        return float(esperado) == float(resp)
    return resp == esperado


def peticion(q, timeout=8):
    """Una petición HTTP de un «pide». Devuelve (ok, detalle)."""
    cuerpo = json.dumps(q["cuerpo"]).encode("utf-8") if "cuerpo" in q else None
    req = urllib.request.Request(q["url"], data=cuerpo, method=str(q.get("metodo", "GET")).upper(),
                                 headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: codigo, texto = r.status, r.read()
    except urllib.error.HTTPError as e:
        codigo, texto = e.code, e.read()
    except (urllib.error.URLError, OSError, ValueError):
        return False, "¿Está corriendo tu app? (./mvnw spring-boot:run)"
    esperado = q.get("codigo", 200)
    if codigo != esperado: return False, f"respondió {codigo} y debía responder {esperado}"
    if "json" in q:
        try: dato = json.loads(texto.decode("utf-8", "replace"))
        except ValueError: return False, "la respuesta no es JSON"
        if not contiene_json(dato, q["json"]):
            return False, f"la respuesta no trae {json.dumps(q['json'], ensure_ascii=False)[:100]}"
    return True, ""


def _qs(turno):
    return list(turno.get("pide") or []) + [e.get("si") or {} for e in turno.get("errores") or []]


class ContextoCodigo:
    """Todo lo que un Comprobar de código necesita, calculado una sola vez: una corrida de Maven que junta las clases
    de `pide` y de los `si` de `errores`. `raiz`: el proyecto a revisar (por defecto el del estudiante).
    `sin_http`: en --probar los http no se prueban (se dan por buenos)."""

    def __init__(self, curso, modulo, turno, raiz=None, sin_http=False):
        self.curso, self.mod = curso, modulo
        self.nombre = turno.get("proyecto")                          # un proyecto de «proyectos» (si no, el «proyecto» de siempre)
        info = curso.proyectos[self.nombre] if self.nombre else {"ruta": curso.proyecto, "maven": ""}
        self.raiz, self.maven_sub = Path(raiz or info["ruta"]), info["maven"]
        self.sin_http = sin_http
        pr = [q for q in _qs(turno) if q.get("tipo") == "pruebas"]
        self.todas = any(es_todas(q) for q in pr)
        self.clases = sorted({c for q in pr if not es_todas(q) for c in lista(q["clases"])})
        self.ocultas = any(q.get("ocultas") for q in pr)
        self._mvn = None

    @staticmethod
    def usa_codigo(turno): return any(q.get("tipo") in TIPOS_CODIGO for q in _qs(turno))

    @staticmethod
    def usa_maven(turno): return any(q.get("tipo") in ("compila", "pruebas") for q in _qs(turno))

    def maven(self):
        if self._mvn is None:
            ocultas = self.curso.carpeta / "pruebas" / self.mod.ruta.stem if self.ocultas else None
            self._mvn = correr_maven(self.raiz, self.curso.java_home, self.clases, ocultas, maven=self.maven_sub, todas=self.todas)
        return self._mvn

    def evalua(self, q):
        """(ok, detalle) de un «pide» o «si» de código."""
        t = q["tipo"]
        if t == "http": return (True, "") if self.sin_http else peticion(q)
        if t == "archivo": return self._archivo(q)
        r = self.maven()
        if not r["compila"]: return False, r["error"]
        if t == "compila": return True, ""
        total = 0
        if es_todas(q):                                   # todas las pruebas del proyecto: cero fallos y al menos `minimo`
            for c, rc in sorted(r["clases"].items()):
                if rc["fallos"]: return False, rc["primer"] or f"{c} tiene pruebas que fallan"
                total += rc["tests"]
            minimo = q.get("minimo", 1)
            if total < minimo: return False, f"corrieron {total} prueba(s) en todo el proyecto y se piden al menos {minimo}"
            return True, ""
        for c in lista(q["clases"]):
            rc = r["clases"].get(c)
            if rc is None: return False, f"no encuentro la clase de pruebas {c} (¿está en src/test/java y con el nombre exacto?)"
            if rc["fallos"]: return False, rc["primer"] or f"{c} tiene pruebas que fallan"
            total += rc["tests"]
        minimo = q.get("minimo", 1)
        if total < minimo: return False, f"corrieron {total} prueba(s) y se piden al menos {minimo}"
        return True, ""

    def descripcion(self):
        """Qué proyecto revisa este turno, en una línea (para el tutor y los avisos)."""
        r = f"«{self.nombre}» ({self.raiz}" if self.nombre else f"el proyecto del curso ({self.raiz}"
        return r + (f"; Maven en {self.maven_sub}/)" if self.maven_sub else ")")

    def _archivo(self, q):
        raiz = self.raiz.resolve()
        if not raiz.is_dir(): return False, f"no encuentro la carpeta del proyecto ({self.raiz})"
        if tiene_comodin(q["ruta"]):
            try:
                hallados = sorted(f for f in raiz.glob(str(q["ruta"]).replace("\\", "/")) if f.is_file()
                                  and not any(x in IGNORAR_COPIA for x in f.relative_to(raiz).parts))
            except (NotImplementedError, ValueError, OSError): return False, f"la ruta «{q['ruta']}» no se puede buscar"
            if not hallados: return False, f"busqué «{q['ruta']}» y no encontré ningún archivo así"
            fallos = []
            for f in hallados:
                ok, det = self._revisa_archivo(f, q)
                if ok: return True, ""
                fallos.append(det)
            n = len(hallados)
            return False, f"busqué «{q['ruta']}»: {n} archivo{'s' if n != 1 else ''}, ninguno cumple ({fallos[0]})"
        ruta = (raiz / q["ruta"]).resolve()
        try: ruta.relative_to(raiz)
        except ValueError: return False, "ruta fuera del proyecto"
        if not ruta.is_file(): return False, f"no existe {q['ruta']}"
        return self._revisa_archivo(ruta, q)

    @staticmethod
    def _revisa_archivo(ruta, q):
        txt = ruta.read_text(encoding="utf-8", errors="replace"); plano = _colapsa(txt)
        for c in lista(q.get("contiene")):
            if _colapsa(c).strip() not in plano: return False, f"en {ruta.name} falta «{c}»"
        for c in lista(q.get("no_contiene")):
            if _colapsa(c).strip() in plano: return False, f"en {ruta.name} sobra «{c}»"
        if q.get("regex") and not re.search(q["regex"], txt, re.S | re.M): return False, f"en {ruta.name} no aparece lo que se pide"
        return True, ""
