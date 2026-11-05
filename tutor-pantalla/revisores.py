"""Revisores de código sin IA para el modo curso, además de Maven: pytest, vitest, git y comando.

Los usa curso_pantalla.ContextoCodigo (formato en el README, «Cursos de código»). Igual que Maven, pytest, vitest y
comando corren sobre una COPIA temporal del proyecto (nunca escriben en la carpeta del estudiante); git solo lee
(comandos de lectura, sin tocar el índice).

    {"tipo": "pytest",  "archivos": ["tests/test_x.py"] | "todas", "ocultas": true, "minimo": 3}
    {"tipo": "vitest",  "archivos": ["src/Lista.test.jsx"] | "todas", "ocultas": true, "minimo": 1}
    {"tipo": "git",     "rama": "main", "limpio": true, "sin_conflictos": true, "en_curso": "ninguno",
                        "merge": true, "commit": "regex" | [...], "desde": "ref", "commits": 2, "ancestro": "rama",
                        "existe_rama": "x", "igual_a": "origin/main", "salida": {"cmd": ["log", "--oneline"], "contiene": [...], "regex": "..."}}
    {"tipo": "comando", "cmd": "bash contar.sh app.log", "shell": "bash | powershell | cmd | ninguno",
                        "codigo": 0, "salida": {"contiene": [...], "no_contiene": [...], "regex": "..."},
                        "stderr": {...}, "crea": ["salida.txt"], "env": {"X": "1"}, "timeout": 30}

python revisores.py --probar   pruebas con proyectos hechos aquí mismo (pytest, git, comando; vitest si se le da
                               una carpeta con node_modules: --probar --vitest <carpeta>)."""
import json, os, re, shutil, subprocess, sys, tempfile, time
import xml.etree.ElementTree as ET
from pathlib import Path

TIPOS = {
    "pytest":  "pruebas de Python con pytest: {\"tipo\": \"pytest\", \"archivos\": [\"tests/test_x.py\"] o \"todas\", \"ocultas\": true, \"minimo\": 3}",
    "vitest":  "pruebas de JS/React con Vitest: {\"tipo\": \"vitest\", \"archivos\": [\"src/x.test.jsx\"] o \"todas\", \"ocultas\": true, \"minimo\": 1}",
    "git":     "el estado de un repositorio git (solo lectura): {\"tipo\": \"git\", \"rama\": \"main\", \"sin_conflictos\": true, \"commit\": \"regex\", ...}",
    "comando": "un comando en una copia del proyecto: {\"tipo\": \"comando\", \"cmd\": \"bash contar.sh\", \"codigo\": 0, \"salida\": {\"contiene\": [...]}}",
}
IGNORAR = ("target", ".git", "node_modules", ".venv", "venv", "__pycache__", ".pytest_cache", "dist")
SIN_VENTANA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
CLAVES_GIT = {"igual_a", "rama", "limpio", "sin_conflictos", "en_curso", "merge", "commit", "desde", "commits", "ancestro", "existe_rama", "salida"}
EN_CURSO = ("ninguno", "merge", "rebase", "cherry-pick", "revert")
# git de solo lectura: subcomando → flags permitidos (None = cualquier argumento que no empiece por «-» y estos flags)
GIT_LECTURA = {
    "log": None, "show": None, "status": None, "diff": None, "rev-parse": None, "rev-list": None, "ls-files": None,
    "merge-base": None, "cat-file": None, "describe": None, "shortlog": None, "reflog": {"show", "--oneline", "-n", "--format"},
    "branch": {"-a", "-r", "-v", "-vv", "--list", "--merged", "--no-merged", "--show-current", "--contains"},
    "tag": {"-l", "--list", "--contains", "-n"}, "remote": {"-v", "get-url"}, "config": {"--get", "--list", "-l"},
    "stash": {"list", "show"},
}
PELIGROSOS = {"--output", "-o", "--exec", "--upload-pack", "--receive-pack", "--ext-diff", "-D", "-d", "-m", "-M", "--delete"}


def lista(v): return [v] if isinstance(v, str) else list(v or [])
def es_todas(q): return isinstance(q.get("archivos"), str) and q["archivos"].strip().lower() == "todas"
def _colapsa(s): return re.sub(r"\s+", " ", s)


# ---------- validar (al cargar el curso) ----------
def _valida_texto(q, k, donde):
    v = q.get(k)
    if v is None: return
    if not isinstance(v, dict): raise ValueError(f"{donde}: «{k}» va así: {{\"contiene\": [...], \"no_contiene\": [...], \"regex\": \"...\"}}")
    for c in ("contiene", "no_contiene"):
        if c in v and not all(isinstance(x, str) for x in lista(v[c])): raise ValueError(f"{donde}: «{k}.{c}» es un texto o una lista de textos")
    if v.get("regex"):
        try: re.compile(v["regex"])
        except re.error as e: raise ValueError(f"{donde}: «{k}.regex» mal escrita ({e})")


def _relativa(r, donde, k):
    if os.path.isabs(str(r)) or ".." in Path(str(r)).parts: raise ValueError(f"{donde}: «{k}» tiene que ser relativa al proyecto (sin «..»): {r}")


def git_permitido(cmd):
    """¿Es un git de solo lectura? cmd: lista de argumentos sin «git». Devuelve el motivo si no, o None."""
    if not cmd or not isinstance(cmd, list) or not all(isinstance(x, str) for x in cmd): return "«cmd» es una lista de textos: [\"log\", \"--oneline\"]"
    sub, args = cmd[0], cmd[1:]
    if sub not in GIT_LECTURA: return f"«git {sub}» no es de solo lectura (vale: {', '.join(sorted(GIT_LECTURA))})"
    for a in args:
        base = a.split("=", 1)[0]
        if base in PELIGROSOS: return f"«{a}» no se permite en «git {sub}»"
        permitidos = GIT_LECTURA[sub]
        if permitidos is not None and base.startswith("-") and base not in permitidos: return f"«{a}» no se permite en «git {sub}»"
        if permitidos is not None and not base.startswith("-") and sub in ("stash", "remote") and a not in permitidos: return f"«git {sub} {a}» no es de lectura"
    if sub in ("branch", "tag") and any(not a.startswith("-") for a in args) and not any(a in ("--list", "-l", "--contains", "--merged", "--no-merged") for a in args):
        return f"«git {sub} <nombre>» crea una {sub}: usa «--list <nombre>»"
    return None


def validar(q, donde):
    t = q.get("tipo")
    if t in ("pytest", "vitest"):
        if not es_todas(q):
            if not lista(q.get("archivos")): raise ValueError(f"{donde}: «{t}» necesita «archivos»: [\"tests/test_x.py\"] (o \"todas\")")
            for a in lista(q["archivos"]): _relativa(a, donde, "archivos")
        if "minimo" in q and not (isinstance(q["minimo"], int) and q["minimo"] >= 0): raise ValueError(f"{donde}: «minimo» es un número entero")
    elif t == "git":
        sobra = set(q) - CLAVES_GIT - {"tipo", "texto"}
        if sobra: raise ValueError(f"{donde}: «git» no entiende {', '.join(sorted(sobra))} (vale: {', '.join(sorted(CLAVES_GIT))})")
        if not set(q) & CLAVES_GIT: raise ValueError(f"{donde}: «git» necesita al menos una comprobación ({', '.join(sorted(CLAVES_GIT))})")
        if "en_curso" in q and q["en_curso"] not in EN_CURSO: raise ValueError(f"{donde}: «en_curso» es uno de {', '.join(EN_CURSO)}")
        for r in lista(q.get("commit")):
            try: re.compile(r)
            except re.error as e: raise ValueError(f"{donde}: «commit» mal escrita ({e})")
        if "commits" in q and not (isinstance(q["commits"], int) and q["commits"] >= 0): raise ValueError(f"{donde}: «commits» es un número entero")
        if "salida" in q:
            if not isinstance(q["salida"], dict): raise ValueError(f"{donde}: «salida» va así: {{\"cmd\": [\"log\"], \"contiene\": [...]}}")
            m = git_permitido(q["salida"].get("cmd"))
            if m: raise ValueError(f"{donde}: {m}")
            _valida_texto({"s": {k: v for k, v in q["salida"].items() if k != "cmd"}}, "s", donde)
    elif t == "comando":
        if not q.get("cmd") or not isinstance(q["cmd"], (str, list)): raise ValueError(f"{donde}: «comando» necesita «cmd» (texto o lista)")
        if q.get("shell", "bash") not in ("bash", "powershell", "cmd", "ninguno"): raise ValueError(f"{donde}: «shell» es bash, powershell, cmd o ninguno")
        if "codigo" in q and q["codigo"] is not None and not isinstance(q["codigo"], int): raise ValueError(f"{donde}: «codigo» es un número (o null para no mirarlo)")
        for k in ("salida", "stderr"): _valida_texto(q, k, donde)
        for c in lista(q.get("crea")): _relativa(c, donde, "crea")
        if "env" in q and not (isinstance(q["env"], dict) and all(isinstance(v, str) for v in q["env"].values())): raise ValueError(f"{donde}: «env» es {{\"NOMBRE\": \"valor\"}}")


# ---------- utilidades ----------
def copiar(raiz, destino):
    shutil.copytree(raiz, destino, ignore=shutil.ignore_patterns(*IGNORAR), dirs_exist_ok=True)


def anadir_ocultas(carpeta, destino):
    """Copia las pruebas ocultas (respetando su ruta) dentro del proyecto copiado. Devuelve sus rutas relativas (posix)."""
    base = Path(carpeta) if carpeta else None
    if not base or not base.is_dir(): return []
    shutil.copytree(base, destino, dirs_exist_ok=True)
    return [f.relative_to(base).as_posix() for f in base.rglob("*") if f.is_file()]


def revisa_texto(txt, spec, que):
    """(ok, detalle) de {"contiene", "no_contiene", "regex"} sobre un texto."""
    if not spec: return True, ""
    plano = _colapsa(txt)
    for c in lista(spec.get("contiene")):
        if _colapsa(c).strip() not in plano: return False, f"{que} no trae «{c}»"
    for c in lista(spec.get("no_contiene")):
        if _colapsa(c).strip() in plano: return False, f"{que} trae «{c}» y no debería"
    if spec.get("regex") and not re.search(spec["regex"], txt, re.S | re.M): return False, f"{que} no trae lo que se pide"
    return True, ""


def bash_de_git():
    """El bash de Git for Windows (no el de WSL de System32)."""
    for c in (r"C:\Program Files\Git\bin\bash.exe", r"C:\Program Files\Git\usr\bin\bash.exe"):
        if Path(c).is_file(): return c
    g = shutil.which("git")
    if g:
        for up in Path(g).resolve().parents:
            b = up / "bin" / "bash.exe"
            if b.is_file(): return str(b)
    return shutil.which("bash") or "bash"


def python_para(raices, preferido=""):
    """El python del proyecto (.venv o venv en alguna de las raíces), el de curso.json o el del PATH."""
    for r in raices:
        if not r: continue
        for v in (".venv", "venv"):
            p = Path(r) / v / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            if p.is_file(): return str(p)
    return preferido or shutil.which("python") or sys.executable


def node_modules_de(raices):
    for r in raices:
        if r and (Path(r) / "node_modules" / "vitest").is_dir(): return Path(r) / "node_modules"
    return None


def enlazar(src, dst):
    """node_modules del proyecto dentro de la copia, sin copiarlo: unión (junction) en Windows, enlace en lo demás."""
    if os.name == "nt":
        import _winapi
        _winapi.CreateJunction(str(src), str(dst))
    else:
        os.symlink(src, dst, target_is_directory=True)


def quitar_enlace(dst):
    """Quita solo el enlace (nunca lo que hay detrás). Llamarlo SIEMPRE antes de borrar la copia."""
    p = Path(dst)
    if not os.path.lexists(p): return
    if os.name == "nt": os.rmdir(p)            # en una unión, rmdir quita el enlace y deja el destino intacto
    else: os.unlink(p)


def _rel(f, base):
    try: return Path(f).resolve().relative_to(Path(base).resolve()).as_posix()
    except ValueError: return Path(f).as_posix()


def _resume(por_archivo, q, que):
    """(ok, detalle) de un «pytest»/«vitest» a partir de {archivo: {"tests", "fallos", "primer"}}."""
    if es_todas(q):
        elegidos = sorted(por_archivo)
    else:
        elegidos = []
        for a in lista(q["archivos"]):
            a = a.replace("\\", "/")
            if a not in por_archivo: return False, f"no corrió {a} (¿existe, con ese nombre exacto, y tiene pruebas?)"
            elegidos.append(a)
    total = 0
    for a in elegidos:
        r = por_archivo[a]
        if r["fallos"]: return False, r["primer"] or f"{a} tiene pruebas que fallan"
        total += r["tests"]
    minimo = q.get("minimo", 1)
    if total < minimo:
        donde = "en todo el proyecto" if es_todas(q) else ""
        return False, f"corrieron {total} prueba(s) {donde} y se piden al menos {minimo}".replace("  ", " ")
    return True, ""


# ---------- pytest ----------
def _lee_junit(xml, base):
    res = {}
    try: raiz = ET.parse(xml).getroot()
    except (ET.ParseError, OSError): return res
    for tc in raiz.iter("testcase"):
        f = tc.get("file") or (tc.get("classname", "").rsplit(".", 1)[0].replace(".", "/") + ".py")
        a = _rel(Path(base) / f, base) if not os.path.isabs(f) else _rel(f, base)
        r = res.setdefault(a, {"tests": 0, "fallos": 0, "primer": ""})
        if tc.find("skipped") is not None: continue
        r["tests"] += 1
        bad = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
        if bad is None: continue
        r["fallos"] += 1
        if not r["primer"]:
            msg = (bad.get("message") or "").strip().splitlines()
            r["primer"] = f"{tc.get('name', '')}: {msg[0] if msg else 'error'}"[:300]
    return res


def correr_pytest(raiz, archivos=(), ocultas_de=None, python="", timeout=300):
    """UNA corrida de pytest en una copia temporal de `raiz`. archivos: rutas relativas (vacío = todas).
    Devuelve {"ok_corrio": bool, "error": str, "archivos": {ruta: {...}}, "seg"}."""
    raiz, t0 = Path(raiz), time.time()
    if not raiz.is_dir(): return {"ok_corrio": False, "error": f"No encuentro la carpeta del proyecto ({raiz}).", "archivos": {}, "seg": 0}
    tmp = Path(tempfile.mkdtemp(prefix="curso_py_"))
    try:
        base = tmp / "p"; copiar(raiz, base); anadir_ocultas(ocultas_de, base)
        faltan = [a for a in archivos if not (base / a).is_file()]
        if faltan: return {"ok_corrio": False, "error": f"no existe {faltan[0]}", "archivos": {}, "seg": time.time() - t0}
        xml = tmp / "r.xml"
        cmd = [python or sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-o", "junit_family=xunit1",
               f"--junitxml={xml}", *archivos]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
        try:
            p = subprocess.run(cmd, cwd=str(base), env=env, capture_output=True, timeout=timeout, creationflags=SIN_VENTANA)
        except subprocess.TimeoutExpired:
            return {"ok_corrio": False, "error": f"pytest tardó más de {timeout} s.", "archivos": {}, "seg": time.time() - t0}
        except OSError as e:
            return {"ok_corrio": False, "error": f"no pude correr pytest ({e})", "archivos": {}, "seg": time.time() - t0}
        salida = (p.stdout + b"\n" + p.stderr).decode("utf-8", "replace")
        res = _lee_junit(xml, base)
        if "No module named pytest" in salida: return {"ok_corrio": False, "error": "falta pytest (pip install pytest en tu .venv)", "archivos": {}, "seg": time.time() - t0}
        if p.returncode in (2, 3, 4) and not any(r["tests"] for r in res.values()):
            linea = next((l.strip() for l in salida.splitlines() if re.match(r"\s*E\s", l) or "Error" in l), "")
            return {"ok_corrio": False, "error": ("pytest no pudo cargar las pruebas" + (f": {linea[:200]}" if linea else "")), "archivos": res, "seg": time.time() - t0, "salida": salida[-3000:]}
        return {"ok_corrio": True, "error": "", "archivos": res, "seg": time.time() - t0, "salida": salida[-3000:]}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- vitest ----------
def correr_vitest(raiz, archivos=(), ocultas_de=None, node_modules=None, timeout=300):
    """UNA corrida de `vitest run` en una copia temporal, con el node_modules enlazado (no copiado)."""
    raiz, t0 = Path(raiz), time.time()
    if not raiz.is_dir(): return {"ok_corrio": False, "error": f"No encuentro la carpeta del proyecto ({raiz}).", "archivos": {}, "seg": 0}
    nm = Path(node_modules) if node_modules else None
    if not nm or not (nm / "vitest").is_dir():
        return {"ok_corrio": False, "error": "falta instalar las dependencias (npm install en tu proyecto)", "archivos": {}, "seg": 0}
    node = shutil.which("node") or "node"
    tmp = Path(tempfile.mkdtemp(prefix="curso_vt_"))
    enlace = tmp / "p" / "node_modules"
    try:
        base = tmp / "p"; copiar(raiz, base); anadir_ocultas(ocultas_de, base)
        faltan = [a for a in archivos if not (base / a).is_file()]
        if faltan: return {"ok_corrio": False, "error": f"no existe {faltan[0]}", "archivos": {}, "seg": time.time() - t0}
        enlazar(nm, enlace)
        out = tmp / "r.json"
        cli = nm / "vitest" / "vitest.mjs"
        cmd = [node, str(cli), "run", "--reporter=json", f"--outputFile={out}", *archivos]
        env = dict(os.environ, CI="1", FORCE_COLOR="0")
        try:
            p = subprocess.run(cmd, cwd=str(base), env=env, capture_output=True, timeout=timeout, creationflags=SIN_VENTANA)
        except subprocess.TimeoutExpired:
            return {"ok_corrio": False, "error": f"vitest tardó más de {timeout} s.", "archivos": {}, "seg": time.time() - t0}
        salida = (p.stdout + b"\n" + p.stderr).decode("utf-8", "replace")
        try: dato = json.loads(out.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            linea = next((l.strip() for l in salida.splitlines() if "Error" in l), salida.strip().splitlines()[-1] if salida.strip() else "")
            return {"ok_corrio": False, "error": f"vitest no terminó: {linea[:200]}", "archivos": {}, "seg": time.time() - t0, "salida": salida[-3000:]}
        res = {}
        for tr in dato.get("testResults") or []:
            a = _rel(tr.get("name", ""), base)
            r = res.setdefault(a, {"tests": 0, "fallos": 0, "primer": ""})
            for ar in tr.get("assertionResults") or []:
                if ar.get("status") in ("skipped", "pending", "todo"): continue
                r["tests"] += 1
                if ar.get("status") != "passed":
                    r["fallos"] += 1
                    if not r["primer"]:
                        msg = (ar.get("failureMessages") or [""])[0].strip().splitlines()
                        r["primer"] = f"{ar.get('title', '')}: {msg[0] if msg else 'falló'}"[:300]
            if tr.get("status") == "failed" and not tr.get("assertionResults"):
                r["fallos"] += 1
                r["primer"] = r["primer"] or ("el archivo no carga: " + (tr.get("message") or "").strip().splitlines()[0][:250] if tr.get("message") else "el archivo no carga")
        return {"ok_corrio": True, "error": "", "archivos": res, "seg": time.time() - t0, "salida": salida[-3000:]}
    finally:
        try: quitar_enlace(enlace)
        finally: shutil.rmtree(tmp, ignore_errors=True)


# ---------- git (solo lectura) ----------
def _git(raiz, *args):
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", LC_ALL="C", GIT_TERMINAL_PROMPT="0")
    p = subprocess.run(["git", "-C", str(raiz), "--no-pager", "-c", "core.quotepath=off", *args], env=env,
                       capture_output=True, timeout=30, creationflags=SIN_VENTANA)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def _en_curso(raiz):
    _, gd, _ = _git(raiz, "rev-parse", "--absolute-git-dir")
    g = Path(gd.strip())
    if (g / "rebase-merge").is_dir() or (g / "rebase-apply").is_dir(): return "rebase"
    if (g / "MERGE_HEAD").is_file(): return "merge"
    if (g / "CHERRY_PICK_HEAD").is_file(): return "cherry-pick"
    if (g / "REVERT_HEAD").is_file(): return "revert"
    return "ninguno"


EN_CURSO_TXT = {"merge": "un merge a medias", "rebase": "un rebase a medias", "cherry-pick": "un cherry-pick a medias", "revert": "un revert a medias", "ninguno": "nada a medias"}


def revisar_git(raiz, q):
    """(ok, detalle) de un «git». Todas las claves tienen que cumplirse; el detalle es la primera que no."""
    raiz = Path(raiz)
    c, _, err = _git(raiz, "rev-parse", "--is-inside-work-tree")
    if c != 0: return False, f"{raiz.name} no es un repositorio git" + (" (¿corriste el preparar del módulo?)" if "not a git" in err else "")
    if "en_curso" in q:
        e = _en_curso(raiz)
        if e != q["en_curso"]: return False, f"el repositorio tiene {EN_CURSO_TXT[e]} y se espera {EN_CURSO_TXT[q['en_curso']]}"
    if "rama" in q:
        _, b, _ = _git(raiz, "branch", "--show-current")
        if b.strip() not in lista(q["rama"]): return False, f"estás en la rama «{b.strip() or '(ninguna: HEAD suelto)'}» y se espera «{lista(q['rama'])[0]}»"
    if q.get("sin_conflictos"):
        _, u, _ = _git(raiz, "diff", "--name-only", "--diff-filter=U")
        if u.strip(): return False, f"hay archivos en conflicto sin resolver: {', '.join(u.split()[:3])}"
        c, m, _ = _git(raiz, "grep", "-n", "-I", "-E", "^(<<<<<<<|>>>>>>>)( |$)|^=======$", "--", ".")
        if c == 0 and m.strip():
            f, n = m.splitlines()[0].split(":")[:2]
            return False, f"quedan marcas de conflicto en {f} (línea {n})"
    if "limpio" in q:
        _, s, _ = _git(raiz, "status", "--porcelain")
        if bool(q["limpio"]) != (not s.strip()):
            return False, ("hay cambios sin guardar en un commit: " + ", ".join(l[3:] for l in s.splitlines()[:3])) if q["limpio"] else "no hay cambios pendientes y se esperaban"
    if q.get("merge") is not None:
        _, pa, _ = _git(raiz, "rev-list", "--parents", "-n", "1", "HEAD")
        es = len(pa.split()) > 2
        if es != bool(q["merge"]): return False, "el último commit no es un commit de merge" if q["merge"] else "el último commit es un merge y no debería"
    rango = [f"{q['desde']}..HEAD"] if q.get("desde") else ["HEAD"]
    if q.get("commit"):
        c, log, _ = _git(raiz, "log", "--format=%H%x00%B%x01", *rango)
        if c != 0: return False, f"no pude leer la historia ({q.get('desde', 'HEAD')} existe?)"
        mensajes = [x.split("\x00", 1)[-1] for x in log.split("\x01") if x.strip()]
        for r in lista(q["commit"]):
            if not any(re.search(r, m, re.I | re.M) for m in mensajes): return False, f"no encuentro en la historia un commit cuyo mensaje diga /{r}/"
    if "commits" in q:
        _, n, _ = _git(raiz, "rev-list", "--count", *rango)
        if int(n.strip() or 0) < q["commits"]: return False, f"hay {n.strip() or 0} commit(s) {'desde ' + q['desde'] if q.get('desde') else ''} y se esperan al menos {q['commits']}".replace("  ", " ")
    if q.get("ancestro"):
        c, _, _ = _git(raiz, "merge-base", "--is-ancestor", q["ancestro"], "HEAD")
        if c != 0: return False, f"«{q['ancestro']}» todavía no está unida a tu rama actual"
    if q.get("igual_a"):                                 # p. ej. "origin/main": lo tuyo ya está subido y al día
        _, h, _ = _git(raiz, "rev-parse", "HEAD")
        c, o, _ = _git(raiz, "rev-parse", "--verify", "--quiet", q["igual_a"])
        if c != 0: return False, f"no existe «{q['igual_a']}»"
        if h.strip() != o.strip():
            _, ad, _ = _git(raiz, "rev-list", "--left-right", "--count", f"HEAD...{q['igual_a']}")
            a, b = (ad.split() + ["0", "0"])[:2]
            return False, f"tu rama no está igual que {q['igual_a']} (tienes {a} commit(s) que no tiene y te faltan {b})"
    for r in lista(q.get("existe_rama")):
        c, _, _ = _git(raiz, "rev-parse", "--verify", "--quiet", f"refs/heads/{r}")
        if c != 0: return False, f"no existe la rama «{r}»"
    if q.get("salida"):
        s = q["salida"]
        m = git_permitido(s.get("cmd"))
        if m: return False, m
        _, out, _ = _git(raiz, *s["cmd"])
        ok, det = revisa_texto(out, s, f"«git {' '.join(s['cmd'])}»")
        if not ok: return False, det
    return True, ""


# ---------- comando ----------
def correr_comando(raiz, q, en_copia=True):
    """(ok, detalle) de un «comando». Corre en una copia temporal de `raiz` (o en una carpeta temporal vacía si no hay)."""
    t = q.get("timeout", 30)
    tmp = Path(tempfile.mkdtemp(prefix="curso_cmd_"))
    try:
        base = tmp / "p"
        if raiz and Path(raiz).is_dir() and en_copia: copiar(raiz, base)
        else: base.mkdir()
        shell, cmd = q.get("shell", "bash"), q["cmd"]
        texto = cmd if isinstance(cmd, str) else subprocess.list2cmdline(cmd)
        if shell == "bash": args = [bash_de_git(), "-c", texto if isinstance(cmd, str) else " ".join(_sh(x) for x in cmd)]
        elif shell == "powershell": args = ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", texto]
        elif shell == "cmd": args = ["cmd", "/d", "/c", texto]
        else: args = cmd if isinstance(cmd, list) else cmd.split()
        env = dict(os.environ, **(q.get("env") or {}), PYTHONIOENCODING="utf-8", LC_ALL="C.UTF-8")
        try:
            p = subprocess.run(args, cwd=str(base), env=env, capture_output=True, timeout=t, input=q.get("entrada", "").encode("utf-8"),
                               creationflags=SIN_VENTANA)
        except subprocess.TimeoutExpired:
            return False, f"«{texto[:60]}» tardó más de {t} s"
        except OSError as e:
            return False, f"no pude correr «{texto[:60]}» ({e})"
        out, err = p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")
        esperado = q.get("codigo", 0)
        if esperado is not None and p.returncode != esperado:
            pista = (err.strip() or out.strip()).splitlines()[-1:] or [""]
            return False, f"«{texto[:60]}» terminó con código {p.returncode} y se esperaba {esperado}" + (f" ({pista[0][:120]})" if pista[0] else "")
        ok, det = revisa_texto(out, q.get("salida"), "la salida")
        if not ok: return False, det
        ok, det = revisa_texto(err, q.get("stderr"), "la salida de error")
        if not ok: return False, det
        for c in lista(q.get("crea")):
            if not (base / c).exists(): return False, f"«{texto[:60]}» no creó {c}"
        return True, ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _sh(x): return x if re.fullmatch(r"[\w./:=@%+,-]+", x) else "'" + x.replace("'", "'\\''") + "'"


# ---------- --probar ----------
def probar(carpeta_vitest=None):
    malos = 0

    def ver(c, t):
        nonlocal malos
        malos += not c; print("✔" if c else "✘", t)

    with tempfile.TemporaryDirectory() as d:
        d = Path(d)
        # validar
        for q, bien in [({"tipo": "pytest", "archivos": "todas"}, True), ({"tipo": "pytest"}, False),
                        ({"tipo": "git", "rama": "main"}, True), ({"tipo": "git", "rara": 1}, False),
                        ({"tipo": "git", "salida": {"cmd": ["push"]}}, False), ({"tipo": "git", "salida": {"cmd": ["branch", "-D", "x"]}}, False),
                        ({"tipo": "git", "salida": {"cmd": ["branch", "nueva"]}}, False), ({"tipo": "git", "salida": {"cmd": ["log", "--oneline"]}}, True),
                        ({"tipo": "comando", "cmd": "ls", "shell": "zsh"}, False), ({"tipo": "vitest", "archivos": ["../x.test.js"]}, False)]:
            try: validar(q, "x"); r = True
            except ValueError: r = False
            ver(r == bien, f"validar {json.dumps(q)[:70]} → {'acepta' if bien else 'rechaza'}")

        # pytest
        py = d / "py"; (py / "tests").mkdir(parents=True)
        (py / "calc.py").write_text("def suma(a, b):\n    return a + b\n", encoding="utf-8")
        (py / "tests" / "test_mias.py").write_text("from calc import suma\n\ndef test_a():\n    assert suma(1, 1) == 2\n\ndef test_b():\n    assert suma(2, 2) == 4\n", encoding="utf-8")
        (py / "conftest.py").write_text("", encoding="utf-8")
        ocultas = d / "ocultas"; (ocultas / "tests").mkdir(parents=True)
        (ocultas / "tests" / "test_profe.py").write_text("from calc import suma\n\ndef test_neg():\n    assert suma(-1, -1) == -2, 'suma con negativos'\n", encoding="utf-8")
        exe = python_para([py])
        r = correr_pytest(py, ["tests/test_mias.py", "tests/test_profe.py"], ocultas, exe)
        ver(r["ok_corrio"] and _resume(r["archivos"], {"archivos": ["tests/test_profe.py"]}, "pytest")[0], f"pytest: las ocultas pasan ({r['seg']:.1f} s)")
        ver(_resume(r["archivos"], {"archivos": ["tests/test_mias.py"], "minimo": 3}, "")[0] is False, "pytest: «minimo» 3 con 2 pruebas → falta")
        ver(not (py / "tests" / "test_profe.py").exists() and not (py / ".pytest_cache").exists(), "pytest: no escribe en el proyecto")
        (py / "calc.py").write_text("def suma(a, b):\n    return a - b\n", encoding="utf-8")
        r = correr_pytest(py, ["tests/test_profe.py"], ocultas, exe)
        ok, det = _resume(r["archivos"], {"archivos": ["tests/test_profe.py"]}, "")
        ver(not ok and "test_neg" in det, f"pytest: con el error, el mensaje dice cuál falla ({det[:70]})")
        r = correr_pytest(py, ["tests/no_existe.py"], None, exe)
        ver(not r["ok_corrio"] and "no existe" in r["error"], "pytest: un archivo que no existe se dice")

        # git
        g = d / "repo"; g.mkdir()
        def sh(*a): subprocess.run(["git", "-C", str(g), *a], capture_output=True, check=True, creationflags=SIN_VENTANA)
        sh("init", "-q", "-b", "main"); sh("config", "user.email", "a@b.c"); sh("config", "user.name", "Prueba")
        (g / "a.txt").write_text("hola\n", encoding="utf-8"); sh("add", "."); sh("commit", "-qm", "primero")
        sh("checkout", "-qb", "otra"); (g / "a.txt").write_text("de otra\n", encoding="utf-8"); sh("commit", "-qam", "cambio en otra")
        sh("checkout", "-q", "main"); (g / "a.txt").write_text("de main\n", encoding="utf-8"); sh("commit", "-qam", "cambio en main")
        subprocess.run(["git", "-C", str(g), "merge", "otra"], capture_output=True, creationflags=SIN_VENTANA)
        ok, det = revisar_git(g, {"en_curso": "ninguno"}); ver(not ok and "merge" in det, f"git: merge a medias se ve ({det})")
        ok, det = revisar_git(g, {"sin_conflictos": True}); ver(not ok and "conflicto" in det, f"git: conflicto sin resolver ({det})")
        ver(revisar_git(g, {"rama": "main"})[0], "git: rama actual")
        (g / "a.txt").write_text("de main y de otra\n", encoding="utf-8"); sh("add", "a.txt"); sh("commit", "-qm", "Merge branch 'otra'")
        ver(revisar_git(g, {"en_curso": "ninguno", "sin_conflictos": True, "limpio": True, "merge": True, "ancestro": "otra",
                            "commit": ["cambio en otra", "cambio en main"], "existe_rama": "otra",
                            "salida": {"cmd": ["log", "--oneline"], "contiene": "Merge"}})[0], "git: resuelto → todo bien")
        (g / "a.txt").write_text("<<<<<<< HEAD\nx\n=======\ny\n>>>>>>> otra\n", encoding="utf-8"); sh("commit", "-qam", "con marcas")
        ok, det = revisar_git(g, {"sin_conflictos": True}); ver(not ok and "marcas" in det, f"git: marcas guardadas en un commit ({det})")
        ok, det = revisar_git(g, {"limpio": True}); ver(ok, "git: limpio")
        (g / "b.txt").write_text("x", encoding="utf-8")
        ok, det = revisar_git(g, {"limpio": True}); ver(not ok and "b.txt" in det, f"git: cambios sin commit ({det})")
        ok, det = revisar_git(g, {"commit": "no existe nada así"}); ver(not ok, "git: commit que no está")
        ver(revisar_git(g, {"igual_a": "main"})[0] and not revisar_git(g, {"igual_a": "otra"})[0], "git: «igual_a»")
        ok, det = revisar_git(d, {"rama": "main"}); ver(not ok and "no es un repositorio" in det, "git: carpeta sin repositorio")
        ver(not (Path(subprocess.run(["git", "-C", str(g), "rev-parse", "--git-dir"], capture_output=True, text=True).stdout.strip()) / "index.lock").exists(), "git: no deja index.lock")

        # comando
        c = d / "cmd"; c.mkdir(); (c / "app.log").write_text("INFO a\nERROR b\nERROR c\nINFO d\n", encoding="utf-8")
        (c / "contar.sh").write_text("#!/usr/bin/env bash\ngrep -c ERROR \"$1\"\n", encoding="utf-8", newline="\n")
        ver(correr_comando(c, {"cmd": "bash contar.sh app.log", "salida": {"regex": r"^2\s*$"}})[0], "comando: bash corre el script y la salida cuadra")
        ok, det = correr_comando(c, {"cmd": "bash contar.sh app.log", "salida": {"contiene": "3"}}); ver(not ok and "3" in det, f"comando: salida que no cuadra ({det})")
        ok, det = correr_comando(c, {"cmd": "exit 3", "codigo": 0}); ver(not ok and "código 3" in det, f"comando: código de salida ({det})")
        ver(correr_comando(c, {"cmd": "echo $env:SALUDO", "shell": "powershell", "env": {"SALUDO": "hola"}, "salida": {"contiene": "hola"}})[0], "comando: powershell con env")
        ver(correr_comando(c, {"cmd": "cat app.log | grep ERROR > errores.txt", "crea": ["errores.txt"]})[0], "comando: «crea»")
        ver(not (c / "errores.txt").exists(), "comando: no escribe en el proyecto")

        # vitest (opcional: necesita una carpeta con node_modules/vitest)
        if carpeta_vitest:
            nm = node_modules_de([carpeta_vitest])
            r = correr_vitest(carpeta_vitest, (), None, nm)
            n = sum(x["tests"] for x in r["archivos"].values())
            ver(r["ok_corrio"], f"vitest: corre en {carpeta_vitest} ({n} pruebas, {r['seg']:.1f} s) {r['error']}")
            ver(nm.is_dir() and (nm / "vitest").is_dir(), "vitest: el node_modules del proyecto sigue intacto tras quitar la unión")
        else:
            print("ℹ vitest: sin carpeta (--probar --vitest <carpeta con node_modules>)")
    print("Revisores: todo bien" if not malos else f"Revisores: {malos} fallo(s)")
    return malos


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    if "--probar" in sys.argv:
        a = sys.argv
        sys.exit(probar(a[a.index("--vitest") + 1] if "--vitest" in a and len(a) > a.index("--vitest") + 1 else None))
    print(__doc__)
