"""Leer archivos: lo que todos los tutores (curso, Excel, Dia) y el asistente pueden leer, y con qué permiso.

  Dentro de las carpetas del curso: el tutor lee solo (herramientas Read y Glob de Claude Code, con --add-dir), sin
  preguntar. Fuera de ellas, o si es un archivo de secretos (.env, claves…) aunque esté dentro, Claude Code se lo niega
  y el tutor escribe <pedir_archivo ruta="C:/…"/>: sale la tarjeta «¿Dejo que el tutor lea «x»?» (Sí / No). El permiso
  es por ARCHIVO, nunca por carpeta (lo pidió así el 2026-10-16: una carpeta puede tener un .env), y dura la sesión.
  Sin Grep: la búsqueda de texto no respetaba con seguridad la regla de los secretos.

  archivos.carpetas_de(curso)        las carpetas de lectura libre de un curso (de modo curso, Excel o Dia)
  archivos.args_claude(carpetas)     (cwd, herramientas extra, argumentos) para el `claude -p` del tutor
  archivos.REGLAS / lista(carpetas)  lo que va en el prompt
  archivos.activar(carpetas)         el Lector del panel abierto (uno por proceso), al que se refiere <pedir_archivo/>
  archivos.separar(texto)            (texto sin la etiqueta, tarjeta o None) — lo llama ojos_panel.separar_preguntas
  archivos.leer(token)               el adjunto para el mensaje (lo llama la tarjeta de la página por OjosApi)"""
import base64, fnmatch, json, os, re, tempfile
from pathlib import Path

# Lo que nunca se lee sin su clic, aunque esté en la carpeta del curso
SECRETOS = [".env", ".env.*", "*.pem", "*.key", "*.p12", "*.pfx", "*.jks", "*.keystore", "id_rsa*", "id_ed25519*",
            "credentials*", "secrets*", "*.secret", ".npmrc", ".pypirc", ".netrc", ".git-credentials"]
HERRAMIENTAS = "Read,Glob"
AVISOS = {"Read": "Leyendo un archivo…", "Glob": "Buscando archivos…"}
IMAGENES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".gif": "image/gif", ".webp": "image/webp"}
MAX_TEXTO, MAX_MB = 60000, 15                         # como los adjuntos (ojos_panel)

REGLAS = """
LEER ARCHIVOS: nunca le pidas una captura para leer un archivo. Con Read (leer) y Glob (buscar por nombre) lees tú los
archivos de las carpetas del curso, sin pedir permiso (están en la lista «Carpetas que puedes leer»; si no hay lista,
no tienes ninguna). Para un archivo FUERA de esas carpetas, o si Read te lo niega (los de secretos, como .env o claves,
siempre se niegan), escribe en una frase para qué lo quieres y termina con
<pedir_archivo ruta="C:/ruta/completa/archivo.ext"/>
(UNA vez por respuesta, la ruta completa; si no la sabes, pregúntasela). Le sale una tarjeta Sí / No: si dice que sí, te
llega el archivo en el siguiente mensaje. Solo lees: nunca digas que cambiaste un archivo. Si te llega un .env o una clave,
no repitas los valores secretos."""

ETIQUETA_RE = re.compile(r"\s*<pedir_archivo\s+ruta\s*=\s*[\"\u201c'\u2018]([^\"\u201d'\u2019>]+)[\"\u201d'\u2019]\s*/?>\s*", re.I)
_ACTIVO = None


def _norm(p):
    return os.path.normcase(os.path.abspath(str(p)))


def carpetas_de(curso):
    """Las carpetas del curso: la del curso.json, las de su proyecto (código) y la de datos (Excel). Sin repetir."""
    if curso is None: return []
    import capacidades
    r = []
    c = getattr(curso, "carpeta", None)
    if c: r.append(str(c))
    ruta = getattr(curso, "ruta", None)
    if ruta and Path(ruta).is_file(): r.append(str(Path(ruta).parent))
    r += capacidades.raices_curso(getattr(curso, "d", None) or {})
    if getattr(curso, "datos", None): r.append(str(curso.datos))
    vistos, out = set(), []
    for x in r:
        if not Path(x).is_dir() or _norm(x) in vistos: continue
        vistos.add(_norm(x)); out.append(str(Path(x)))
    return out


def es_secreto(ruta):
    n = Path(str(ruta)).name.lower()
    return any(fnmatch.fnmatch(n, s) for s in SECRETOS)


def dentro(ruta, carpetas):
    r = _norm(ruta)
    return any(r == _norm(c) or r.startswith(_norm(c).rstrip("\\/") + os.sep) for c in carpetas)


def args_claude(carpetas):
    """(cwd, herramientas para --tools además de la web, argumentos extra). Arranca en una carpeta vacía (así no carga
    ningún CLAUDE.md ni lee nada por estar en ella) y da cada carpeta con --add-dir; los secretos se niegan con reglas
    absolutas («//**/…»: las relativas no alcanzan las carpetas de --add-dir). Sin carpetas: sin Read ni Glob."""
    cwd = tempfile.mkdtemp(prefix="tutor-sin-archivos-")
    if not carpetas: return cwd, "", []
    extra = []
    for c in carpetas: extra += ["--add-dir", str(c)]
    deny = [f"Read(//**/{s})" for s in SECRETOS]       # las reglas de Read valen también para Glob
    extra += ["--settings", json.dumps({"permissions": {"deny": deny}})]
    return cwd, HERRAMIENTAS, extra


def lista(carpetas):
    """La línea del prompt con las carpetas de lectura libre."""
    if not carpetas: return "Carpetas que puedes leer: ninguna (cualquier archivo, con <pedir_archivo/>)."
    return "Carpetas que puedes leer (Read y Glob, sin pedir permiso):\n" + "\n".join(f"- {c}" for c in carpetas)


class Lector:
    """Los permisos de una sesión del panel: tokens de las tarjetas y archivos ya aprobados (uno por uno)."""

    def __init__(self, carpetas=()):
        self.carpetas = [str(c) for c in carpetas or ()]
        self.aprobados, self.tokens, self.n = set(), {}, 0

    def libre(self, ruta):
        """True si se lee sin preguntar: dentro del curso y no es de secretos, o ya lo aprobó en esta sesión."""
        return _norm(ruta) in self.aprobados or (dentro(ruta, self.carpetas) and not es_secreto(ruta))

    def tarjeta(self, ruta):
        """La «pregunta» que la página dibuja como tarjeta Sí / No (o, si es libre, lee y manda sola)."""
        ruta = str(Path(ruta.strip().strip('"').replace("/", os.sep))).strip()
        p = Path(ruta)
        self.n += 1; tok = f"a{self.n}"; self.tokens[tok] = ruta
        info = {"token": tok, "ruta": ruta, "nombre": p.name, "auto": self.libre(ruta), "secreto": es_secreto(ruta)}
        if not p.is_absolute(): info.update(auto=False, error=f"«{ruta}» no es una ruta completa: pídele la ruta entera.")
        elif not p.is_file(): info.update(auto=False, error=f"No encuentro «{ruta}» en esta PC.")
        return {"pregunta": f"¿Dejo que el tutor lea «{p.name}»?", "opciones": [], "archivo": info}

    def leer(self, token):
        """El adjunto ({ok, nombre, tipo, media_type, datos}) del archivo de esa tarjeta. Pulsar Sí = aprobar ese archivo."""
        ruta = self.tokens.get(token)
        if not ruta: return {"ok": False, "error": "Esa tarjeta ya no vale: pídele al tutor que lo vuelva a pedir."}
        p = Path(ruta)
        if not p.is_file(): return {"ok": False, "error": f"No encuentro «{ruta}»."}
        try: datos = p.read_bytes()
        except OSError as e: return {"ok": False, "error": f"No pude abrir «{p.name}» ({e.strerror or e})."}
        ext = p.suffix.lower()
        self.aprobados.add(_norm(ruta))
        if ext in IMAGENES or ext == ".pdf":
            if len(datos) > MAX_MB * 1024 * 1024: return {"ok": False, "error": f"«{p.name}» pesa demasiado (máximo {MAX_MB} MB)."}
            return {"ok": True, "nombre": p.name, "ruta": ruta, "tipo": "pdf" if ext == ".pdf" else "imagen",
                    "media_type": IMAGENES.get(ext, "application/pdf"), "datos": base64.b64encode(datos).decode()}
        if b"\0" in datos[:8192]:
            return {"ok": False, "error": f"«{p.name}» no es de texto: solo sé leer texto, PDF e imágenes (un .docx o .xlsx, ábrelo y mándame captura o expórtalo)."}
        texto = datos.decode("utf-8", errors="replace").replace("\r\n", "\n")
        ls = texto.split("\n"); ancho = len(str(len(ls)))
        numerado = f"Ruta: {ruta}\n" + "\n".join(f"{k:>{ancho}}| {l}" for k, l in enumerate(ls, 1))
        if len(numerado) > MAX_TEXTO: numerado = numerado[:MAX_TEXTO] + f"\n[… cortado: el archivo tiene {len(ls)} líneas]"
        return {"ok": True, "nombre": p.name, "ruta": ruta, "tipo": "texto", "media_type": "text/plain", "datos": numerado}


def activar(carpetas):
    """El Lector del panel de este proceso (lo llama el tutor al arrancar su sesión). Conserva lo ya aprobado."""
    global _ACTIVO
    previos = _ACTIVO.aprobados if _ACTIVO else set()
    _ACTIVO = Lector(carpetas); _ACTIVO.aprobados |= previos
    return _ACTIVO


def separar(texto):
    """(texto sin <pedir_archivo/>, tarjeta o None). Solo cuenta la primera etiqueta."""
    ms = list(ETIQUETA_RE.finditer(texto or ""))
    if not ms: return texto or "", None
    limpio = ETIQUETA_RE.sub(" ", texto).strip()
    return limpio, (_ACTIVO or activar(())).tarjeta(ms[0].group(1))


def leer(token):
    if not _ACTIVO: return {"ok": False, "error": "No hay ningún tutor activo."}
    return _ACTIVO.leer(token)


def probar():
    """python archivos.py: pruebas sin ventanas ni IA."""
    malos = 0
    def ver(c, t):
        nonlocal malos
        print(("  ok " if c else "  ✘ MAL ") + t)
        if not c: malos += 1
    with tempfile.TemporaryDirectory() as t:
        cur = Path(t) / "curso"; (cur / "src").mkdir(parents=True); fuera = Path(t) / "fuera"; fuera.mkdir()
        (cur / "src" / "A.java").write_text("class A {}\nint x;\n", encoding="utf-8")
        (cur / ".env").write_text("CLAVE=1\n", encoding="utf-8")
        (fuera / "notas.txt").write_text("hola\n", encoding="utf-8")
        (fuera / "x.bin").write_bytes(b"\0\1\2")
        L = activar([str(cur)])
        ver(L.libre(cur / "src" / "A.java") and not L.libre(cur / ".env") and not L.libre(fuera / "notas.txt"), "dentro libre; .env y fuera, no")
        ver(es_secreto("C:/x/.env.local") and es_secreto("id_rsa.pub") and not es_secreto("application.properties"), "qué es de secretos")
        txt, tj = separar(f'Necesito tus notas. <pedir_archivo ruta="{fuera / "notas.txt"}"/>')
        ver(txt == "Necesito tus notas." and tj and tj["archivo"]["auto"] is False and "notas.txt" in tj["pregunta"], "la etiqueta → tarjeta Sí / No")
        a = leer(tj["archivo"]["token"])
        ver(a["ok"] and a["tipo"] == "texto" and "1| hola" in a["datos"] and str(fuera) in a["datos"], "Sí → adjunto de texto numerado con la ruta")
        _, tj2 = separar(f'<pedir_archivo ruta="{fuera / "notas.txt"}"/>')
        ver(tj2["archivo"]["auto"] is True, "ya aprobado en la sesión: se lee solo")
        _, tj3 = separar(f'<pedir_archivo ruta="{fuera / "otro.txt"}"/>')
        ver(tj3["archivo"]["auto"] is False and "otro.txt" not in L.aprobados, "aprobar un archivo no aprueba otros de su carpeta")
        _, tj4 = separar(f'<pedir_archivo ruta="{cur / ".env"}"/>')
        ver(tj4["archivo"]["auto"] is False and tj4["archivo"]["secreto"], "un .env del curso también pregunta")
        ver(not leer(separar(f'<pedir_archivo ruta="{fuera / "x.bin"}"/>')[1]["archivo"]["token"])["ok"], "un binario no se manda")
        ver("error" in separar('<pedir_archivo ruta="notas.txt"/>')[1]["archivo"], "ruta incompleta → aviso")
        cwd, h, extra = args_claude([str(cur)])
        ver(h == "Read,Glob" and extra[:2] == ["--add-dir", str(cur)] and "Read(//**/.env)" in extra[-1] and not os.listdir(cwd), "argumentos de claude: add-dir, deny absoluto y carpeta vacía")
        ver(args_claude([])[1] == "" and args_claude([])[2] == [], "sin carpetas no hay Read ni Glob")
    print("Archivos: todo bien" if not malos else f"Archivos: {malos} MAL")
    return not malos


if __name__ == "__main__":
    import sys
    sys.exit(0 if probar() else 1)
