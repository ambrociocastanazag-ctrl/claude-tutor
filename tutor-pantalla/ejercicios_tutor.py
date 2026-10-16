"""Los ejercicios que arma el tutor del modo curso (panel_curso.py), sobre todo en el modo práctica (practica.py).

Como el «Ejercicio del tutor» de Excel y Dia: el tutor propone con un bloque <ejercicio>{...}</ejercicio>, la persona
lo acepta con la tarjeta de permiso (Aplicar / No / Deshacer) y se revisa con su propio Comprobar, sin IA.

  Curso de código: el tutor crea un ARCHIVO NUEVO en el proyecto (esqueleto que compila, con el enunciado y los TODO)
  y escribe pruebas JUnit para él, que quedan ocultas en <curso>/practica/<id>/ (nunca en el proyecto). Comprobar
  compila y corre esas pruebas en una COPIA temporal del proyecto (curso_pantalla.correr_maven), nunca en su carpeta.
  Si el ejercicio es justo crear el archivo, "lo_crea": "estudiante": no se escribe nada y Comprobar mira que exista.
  Curso de una app: el ejercicio trae "pide" (las mismas comprobaciones sin IA del curso) y Comprobar las revisa.

  Ejercicios(curso, practica, codigo)       uno por panel
  .separar(texto) -> (texto, tarjeta, error)  el bloque → la tarjeta de permiso (o el error para el tutor)
  .aplicar / rechazar / deshacer(pid, forzar) -> tarjeta;  .comprobar() / .estado() -> tutor_ej para la página
  reglas(curso, codigo)                      lo que va en el prompt del tutor"""
import json, re, shutil, subprocess, time
from pathlib import Path

import curso_pantalla as cp

BLOQUE_RE = re.compile(r"\s*<ejercicio>\s*(\{.*?\})\s*</ejercicio>\s*", re.S | re.I)

REGLAS_CODIGO = """
CREAR UN EJERCICIO (curso de código): para darle un ejercicio de verdad, al final de tu respuesta pon UN bloque así
(JSON válido en una línea o varias; los saltos de línea del código, como \\n dentro de las cadenas):
<ejercicio>{{"titulo": "Contar préstamos", "archivo": "src/main/java/gt/biblioteca/practica/Ejercicio1.java",
 "contenido": "package gt.biblioteca.practica;\\n\\n/** Enunciado: ... */\\npublic class Ejercicio1 {{\\n    // TODO: ...\\n    public static int contar(...) {{ throw new UnsupportedOperationException(\\"TODO\\"); }}\\n}}\\n",
 "pruebas": "package gt.biblioteca.practica;\\n\\nimport org.junit.Test;\\nimport static org.junit.Assert.*;\\n\\npublic class Ejercicio1Test {{ @Test public void cuentaBien() {{ ... }} }}\\n",
 "enunciado": "Completa contar(...) para que ...", "proyecto": ""}}</ejercicio>
- "archivo": ruta NUEVA, relativa al proyecto ({proyectos}); que no exista ya (Ejercicio2, Ejercicio3…). Van en un paquete
  «practica» para no mezclarse con lo suyo. "proyecto": "" = el principal; o el nombre de otro proyecto del curso.
- "contenido": el esqueleto. TIENE QUE COMPILAR desde el principio: firmas declaradas y cuerpos con // TODO y
  throw new UnsupportedOperationException("TODO") (o un return por defecto). Arriba, el enunciado en un comentario.
- "pruebas": una clase de pruebas en el MISMO paquete, con {junit}. Se quedan ocultas (él no las ve) y
  Comprobar las corre: escribe 2 a 5 pruebas claras, con mensajes en español en los assert.
- "lo_crea": "estudiante" solo si el ejercicio es justo crear el archivo o el paquete: entonces no mandes "contenido"
  (dile en el enunciado qué crear) y Comprobar mira que exista, compile y pase tus pruebas.
Le sale una tarjeta Aplicar / No; si aplica, el archivo se crea y se abre en el editor. NO pegues el esqueleto en el chat."""

REGLAS_APP = """
CREAR UN EJERCICIO (curso de {app}): para darle un ejercicio de verdad, al final de tu respuesta pon UN bloque así:
<ejercicio>{{"titulo": "Círculo rojo", "enunciado": "Dibuja un círculo con el color rojo", "pide": [{{"tipo": "activo", "nombre": "Rojo", "texto": "El color rojo está elegido"}}]}}</ejercicio>
"pide" usa las mismas comprobaciones sin IA de las lecciones (activo, nombre, texto, valor, titulo, existe) con los
nombres EXACTOS de los controles del [Estado actual]; "texto" es lo que leerá él. Le sale una tarjeta Aplicar / No; luego
lo hace en {app} y pulsa Comprobar. Lo que no se puede comprobar así, revísalo tú cuando te pida «Revisar»."""


def junit_de(raiz):
    """«JUnit 4 (org.junit.Test, org.junit.Assert)» o «JUnit 5 (org.junit.jupiter.api…)», según el pom del proyecto."""
    try: pom = (Path(raiz) / "pom.xml").read_text(encoding="utf-8", errors="replace")
    except OSError: pom = ""
    if re.search(r"<artifactId>\s*junit\s*</artifactId>", pom):
        return "JUnit 4, como las pruebas del curso (import org.junit.Test; import static org.junit.Assert.*;)"
    return "JUnit 5 (import org.junit.jupiter.api.Test; import static org.junit.jupiter.api.Assertions.*;)"


def reglas(curso, codigo):
    if not codigo: return REGLAS_APP.format(app=curso.app_nombre)
    ps = [f"principal: {curso.proyecto}"] if curso.proyecto else []
    ps += [f"«{k}»: {v['ruta']}" for k, v in curso.proyectos.items()]
    raiz = curso.proyecto or next((v["ruta"] for v in curso.proyectos.values()), "")
    return REGLAS_CODIGO.format(proyectos="; ".join(ps) or "el del curso", junit=junit_de(raiz))


class _Ctx(cp.ContextoCodigo):
    """El Comprobar de código de siempre, pero con las pruebas ocultas del ejercicio (no las del módulo)."""
    def __init__(self, curso, turno, ocultas):
        super().__init__(curso, None, turno); self._ocultas_ej = ocultas

    def maven(self):
        if self._mvn is None:
            self._mvn = cp.correr_maven(self.raiz, self.curso.java_home, self.clases, self._ocultas_ej, maven=self.maven_sub)
        return self._mvn


class Ejercicios:
    def __init__(self, curso, practica=None, codigo=False):
        self.curso, self.practica, self.codigo = curso, practica, codigo
        self.props, self.n, self.ej, self.rev = {}, 0, None, None
        self.abrir_editor = True                  # en las pruebas, False: no abrir nada en el VS Code de la persona

    # ---------- la propuesta ----------
    def separar(self, texto):
        """(texto sin el bloque, tarjeta de permiso o None, error para el tutor o None)."""
        m = BLOQUE_RE.search(texto or "")
        if not m: return texto or "", None, None
        limpio = (texto[:m.start()] + "\n" + texto[m.end():]).strip()
        try: d = json.loads(m.group(1))
        except ValueError as e: return limpio, None, f"tu <ejercicio> no es JSON válido ({e}); vuelve a mandarlo"
        try: p = self._validar(d if isinstance(d, dict) else {})
        except ValueError as e: return limpio, None, f"tu <ejercicio> no se pudo usar: {e}"
        self.n += 1; p["id"] = f"e{self.n}"; self.props[p["id"]] = p
        return limpio, self._tarjeta(p, "pendiente"), None

    def _raiz(self, nombre):
        if nombre:
            if nombre not in self.curso.proyectos: raise ValueError(f"no hay un proyecto «{nombre}» en este curso ({', '.join(self.curso.proyectos) or 'solo el principal'})")
            return Path(self.curso.proyectos[nombre]["ruta"]), self.curso.proyectos[nombre].get("maven", "")
        if not self.curso.proyecto: raise ValueError("este curso no tiene «proyecto»: di \"proyecto\" con el nombre de uno")
        return Path(self.curso.proyecto), ""

    def _validar(self, d):
        titulo = str(d.get("titulo") or "").strip()[:80]
        if not titulo: raise ValueError("falta «titulo»")
        p = {"titulo": titulo, "enunciado": str(d.get("enunciado") or "").strip()[:600]}
        if not self.codigo:
            pide = d.get("pide")
            if not isinstance(pide, list) or not pide: raise ValueError("falta «pide» (una lista de comprobaciones)")
            for k, q in enumerate(pide):
                if not isinstance(q, dict): raise ValueError(f"pide[{k}] no es un objeto")
                cp.valida_q(q, f"pide[{k}]", False)
            p["pide"] = pide; return p
        raiz, sub = self._raiz(str(d.get("proyecto") or ""))
        rel = str(d.get("archivo") or "").replace("\\", "/").strip().lstrip("/")
        if not rel: raise ValueError("falta «archivo» (ruta relativa al proyecto)")
        if Path(rel).is_absolute() or ".." in Path(rel).parts or ":" in rel: raise ValueError("«archivo» tiene que ser relativo al proyecto, sin «..»")
        ruta = (raiz / rel).resolve()
        try: ruta.relative_to(raiz.resolve())
        except ValueError: raise ValueError("«archivo» queda fuera del proyecto")
        lo_crea = "estudiante" if d.get("lo_crea") == "estudiante" else "tutor"
        if lo_crea == "tutor":
            if ruta.exists(): raise ValueError(f"«{rel}» ya existe: usa otro nombre (Ejercicio2…)")
            if not str(d.get("contenido") or "").strip(): raise ValueError("falta «contenido» (el esqueleto)")
        pr = str(d.get("pruebas") or "")
        clase = re.search(r"\bclass\s+(\w+)", pr)
        if not clase or "@Test" not in pr: raise ValueError("«pruebas» tiene que ser una clase JUnit con al menos un @Test")
        paquete = re.search(r"^\s*package\s+([\w.]+)\s*;", pr, re.M)
        p.update(proyecto=str(d.get("proyecto") or ""), raiz=str(raiz), maven=sub, archivo=rel, ruta=str(ruta), lo_crea=lo_crea,
                 contenido=str(d.get("contenido") or ""), pruebas=pr, clase=clase.group(1), paquete=paquete.group(1) if paquete else "")
        return p

    def _tarjeta(self, p, estado, mensaje=""):
        """La tarjeta de permiso con el formato de la página (panel-excel/panel.html, tarjetaPermiso)."""
        if self.codigo:
            nombre = Path(p["archivo"]).name
            det = ([f"Crear `{p['archivo']}` (esqueleto con el enunciado y los TODO)"] if p["lo_crea"] == "tutor"
                   else [f"Tú creas `{p['archivo']}`"]) + [f"Pruebas del tutor `{p['clase']}` (ocultas; las corre Comprobar)"]
            hoja, nueva, resumen = nombre, p["lo_crea"] == "tutor", f"ejercicio «{p['titulo']}» en {nombre}"
        else:
            det = [q.get("texto") or q["tipo"] for q in p["pide"]]
            hoja, nueva, resumen = self.curso.app_nombre, False, f"ejercicio «{p['titulo']}»"
        return {"id": p["id"], "estado": estado, "resumen": resumen, "para": p["enunciado"][:160], "hoja": hoja, "nueva": nueva,
                "avisos": [], "notas": [], "detalle": det, "ejercicio": p["titulo"], "mensaje": mensaje}

    # ---------- los botones de la tarjeta ----------
    def aplicar(self, pid):
        p = self.props[pid]
        if self.codigo:
            ruta = Path(p["ruta"])
            if p["lo_crea"] == "tutor":
                if ruta.exists(): return self._tarjeta(p, "error", f"«{p['archivo']}» ya existe: no lo toqué. Pídele otro.")
                ruta.parent.mkdir(parents=True, exist_ok=True)
                ruta.write_text(p["contenido"], encoding="utf-8")
                p["huella"] = p["contenido"]
            ocultas = Path(self.curso.carpeta) / "practica" / f"{time.strftime('%Y%m%d-%H%M%S')}-{pid}"
            destino = ocultas.joinpath(*p["paquete"].split(".")) if p["paquete"] else ocultas
            destino.mkdir(parents=True, exist_ok=True)
            (destino / f"{p['clase']}.java").write_text(p["pruebas"], encoding="utf-8")
            p["ocultas"] = str(ocultas)
        if self.ej and self.ej is not p: self._limpiar(self.ej)
        self.ej, self.rev = p, None
        if self.practica and self.practica.activa: self.practica.ejercicio_hecho()
        p["estado"] = "aplicada"
        if self.codigo:
            if p["lo_crea"] == "tutor":
                self.abrir()
                return self._tarjeta(p, "aplicada", f"Creé `{p['archivo']}` y lo abrí en el editor. Completa los TODO y pulsa Comprobar.")
            return self._tarjeta(p, "aplicada", f"Listo: crea `{p['archivo']}` como dice el enunciado y pulsa Comprobar.")
        return self._tarjeta(p, "aplicada", f"Listo: hazlo en {self.curso.app_nombre} y pulsa Comprobar.")

    def rechazar(self, pid):
        p = self.props[pid]; p["estado"] = "rechazada"
        return self._tarjeta(p, "rechazada", "No se creó nada.")

    def deshacer(self, pid, forzar=False):
        p = self.props[pid]
        if self.codigo and p.get("lo_crea") == "tutor":
            ruta = Path(p["ruta"])
            cambiado = ruta.exists() and ruta.read_text(encoding="utf-8", errors="replace") != p.get("huella")
            if cambiado and not forzar:
                t = self._tarjeta(p, "confirmar", f"Ya escribiste en `{p['archivo']}`. Si deshaces, se borra el archivo con lo tuyo.")
                t.update(confirmar_titulo="¿Borrar el archivo?", confirmar_boton="Borrar igual"); return t
            try: ruta.unlink()
            except FileNotFoundError: pass
        self._limpiar(p)
        if self.ej is p: self.ej, self.rev = None, None
        p["estado"] = "deshecha"
        return self._tarjeta(p, "deshecha", f"Deshecho: borré `{p['archivo']}`." if self.codigo and p.get("lo_crea") == "tutor" else "Deshecho: quité el ejercicio.")

    def _limpiar(self, p):
        if p.get("ocultas"): shutil.rmtree(p["ocultas"], ignore_errors=True)

    # ---------- revisar ----------
    def turno(self, p=None):
        """El «Tu turno» equivalente al ejercicio (para revisar_turno)."""
        p = p or self.ej
        if not self.codigo: return {"pide": p["pide"], "bien": f"¡Bien! «{p['titulo']}» está hecho."}
        nombre = Path(p["archivo"]).name
        pide = [{"tipo": "archivo", "ruta": p["archivo"], "texto": f"Existe {nombre}"},
                {"tipo": "compila", "texto": "El proyecto compila"},
                {"tipo": "pruebas", "clases": [p["clase"]], "ocultas": True, "texto": "Pasa las pruebas del tutor"}]
        t = {"pide": pide, "bien": f"¡Bien! {nombre} pasa todas las pruebas del tutor."}
        if p["proyecto"]: t["proyecto"] = p["proyecto"]
        return t

    def comprobar(self, est=None):
        if not self.ej: return None
        t = self.turno()
        if self.codigo:
            ctx = _Ctx(self.curso, t, self.ej["ocultas"])
            self.rev = cp.revisar_turno(None, t, ctx)
        else:
            self.rev = cp.revisar_turno(est, t)
        return self.estado()

    def estado(self):
        """El tutor_ej de la página ({id, hoja, titulo, rango, revision}) o None."""
        if not self.ej: return None
        p = self.ej
        rev = self.rev or {"estado": "pendiente", "ok": 0, "total": 0,
                           "mensaje": (p["enunciado"] or p["titulo"]) + " Cuando termines, pulsa Comprobar."}
        hoja = Path(p["archivo"]).name if self.codigo else self.curso.app_nombre
        return {"id": p["id"], "hoja": hoja, "titulo": p["titulo"], "rango": p["titulo"], "revision": rev}

    def contexto(self):
        """Para el [Estado actual]: el ejercicio en curso y su última revisión."""
        if not self.ej: return ""
        p = self.ej
        t = f"[Ejercicio tuyo en curso] «{p['titulo']}»" + (f" en {p['archivo']} (pruebas ocultas: {p['clase']})" if self.codigo else "")
        if self.rev: t += f". Último Comprobar: {self.rev['mensaje']} ({self.rev['ok']} de {self.rev['total']} bien)"
        return t + "."

    def abrir(self):
        """Abre el archivo del ejercicio en VS Code (code -g). Solo abre: no escribe nada."""
        if not (self.codigo and self.ej and self.abrir_editor): return False
        exe = shutil.which("code") or shutil.which("code.cmd")
        if not exe: return False
        try:
            subprocess.Popen([exe, "-r", "-g", self.ej["ruta"]], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)); return True
        except OSError: return False

    def quitar(self):
        """Quita la tarjeta del ejercicio (el archivo se queda; las pruebas ocultas, también hasta que se deshaga)."""
        self.ej, self.rev = None, None


def probar():
    """python ejercicios_tutor.py: pruebas sin ventanas ni IA (Maven solo con --maven)."""
    import sys, tempfile
    malos = 0
    def ver(c, t):
        nonlocal malos
        print(("  ok " if c else "  ✘ MAL ") + t)
        if not c: malos += 1
    with tempfile.TemporaryDirectory() as t:
        t = Path(t); proy = t / "proy"; (proy / "src" / "main" / "java").mkdir(parents=True)
        (proy / "pom.xml").write_text("<artifactId>junit</artifactId>", encoding="utf-8")
        class C: pass
        curso = C(); curso.carpeta = t / "curso"; curso.carpeta.mkdir(); curso.proyecto = proy; curso.proyectos = {}
        curso.app_nombre = "VS Code"; curso.java_home = ""
        import practica as pr
        prac = pr.Practica(curso.carpeta); prac.entrar(0, 3)
        E = Ejercicios(curso, prac, codigo=True); E.abrir_editor = False
        ej = {"titulo": "Sumar", "archivo": "src/main/java/gt/practica/Ejercicio1.java", "enunciado": "Completa sumar.",
              "contenido": "package gt.practica;\npublic class Ejercicio1 { public static int sumar(int a, int b) { throw new UnsupportedOperationException(\"TODO\"); } }\n",
              "pruebas": "package gt.practica;\nimport org.junit.Test;\nimport static org.junit.Assert.*;\npublic class Ejercicio1Test { @Test public void suma() { assertEquals(\"2+3\", 5, Ejercicio1.sumar(2, 3)); } }\n"}
        txt, tj, err = E.separar("Va uno.\n<ejercicio>" + json.dumps(ej) + "</ejercicio>")
        ver(txt == "Va uno." and tj and tj["estado"] == "pendiente" and tj["nueva"] and err is None, "el bloque → tarjeta de permiso")
        ver("JUnit 4" in reglas(curso, True) and "{" not in reglas(curso, True).split("<ejercicio>")[0][-5:], "las reglas dicen el JUnit del proyecto")
        ruta = proy / ej["archivo"]
        ver(not ruta.exists(), "antes de Aplicar no se crea nada")
        a = E.aplicar(tj["id"])
        oc = Path(E.ej["ocultas"])
        ver(a["estado"] == "aplicada" and ruta.read_text(encoding="utf-8") == ej["contenido"], "Aplicar crea el esqueleto en el proyecto")
        ver((oc / "gt" / "practica" / "Ejercicio1Test.java").is_file() and not (proy / "src" / "test").exists(), "las pruebas quedan ocultas en el curso, no en el proyecto")
        ver(prac.hechos == 1 and E.estado()["hoja"] == "Ejercicio1.java", "cuenta el ejercicio de la práctica y la página lo ve")
        _, _, err = E.separar("<ejercicio>" + json.dumps(ej) + "</ejercicio>")
        ver(err and "ya existe" in err, "no pisa un archivo que ya existe")
        _, _, err = E.separar('<ejercicio>{"titulo": "x", "archivo": "../fuera.java", "contenido": "a", "pruebas": "class T { @Test }"}</ejercicio>')
        ver(err and "relativo" in err, "no escribe fuera del proyecto")
        ruta.write_text(ej["contenido"] + "// mío\n", encoding="utf-8")
        d = E.deshacer(tj["id"])
        ver(d["estado"] == "confirmar" and ruta.exists(), "Deshacer pide confirmar si ya escribió en el archivo")
        d = E.deshacer(tj["id"], True)
        ver(d["estado"] == "deshecha" and not ruta.exists() and not oc.exists() and E.estado() is None, "Borrar igual quita archivo, pruebas y tarjeta")
        if "--maven" in sys.argv:          # con un proyecto Maven de verdad (lento: ~20 s por corrida)
            real = Path(sys.argv[sys.argv.index("--maven") + 1]); curso.proyecto = real; curso.carpeta = t / "curso"
            E = Ejercicios(curso, prac, codigo=True); E.abrir_editor = False
            ej["archivo"] = "src/main/java/gt/practica/EjercicioPruebaTutor.java"
            ej["contenido"] = ej["contenido"].replace("Ejercicio1", "EjercicioPruebaTutor")
            ej["pruebas"] = ej["pruebas"].replace("Ejercicio1Test", "EjercicioPruebaTutorTest").replace("Ejercicio1.", "EjercicioPruebaTutor.")
            ruta = real / ej["archivo"]
            _, tj, err = E.separar("<ejercicio>" + json.dumps(ej) + "</ejercicio>")
            try:
                E.aplicar(tj["id"]); r = E.comprobar()["revision"]
                ver(r["estado"] != "bien" and "pruebas del tutor" in r["mensaje"], f"esqueleto sin hacer: no pasa ({r['mensaje']})")
                ruta.write_text(ej["contenido"].replace('throw new UnsupportedOperationException("TODO");', "return a + b;"), encoding="utf-8")
                r = E.comprobar()["revision"]
                ver(r["estado"] == "bien", f"resuelto: pasa las pruebas ocultas ({r['mensaje']})")
                ver(not (real / "src" / "test" / "java" / "gt" / "practica").exists(), "Maven corrió en una copia: el proyecto no tiene las pruebas")
            finally:
                E.deshacer(tj["id"], True)
                for c in (ruta.parent, ruta.parent.parent):
                    try: c.rmdir()
                    except OSError: pass
        # curso de una app
        A = Ejercicios(curso, None, codigo=False)
        _, tj, err = A.separar('<ejercicio>{"titulo": "Rojo", "pide": [{"tipo": "activo", "nombre": "Rojo", "texto": "Rojo elegido"}]}</ejercicio>')
        ver(tj and not err and A.aplicar(tj["id"])["estado"] == "aplicada", "app: el ejercicio con «pide» se aplica")
        est = {"controles": [{"nombre": "Rojo", "activo": True, "tipo": "boton", "valor": ""}], "titulos": []}
        ver(A.comprobar(est)["revision"]["estado"] == "bien", "app: Comprobar revisa sin IA")
        _, tj, err = A.separar('<ejercicio>{"titulo": "x", "pide": [{"tipo": "raro"}]}</ejercicio>')
        ver(err and "raro" in err, "app: una comprobación inventada se rechaza")
    print("Ejercicios: todo bien" if not malos else f"Ejercicios: {malos} MAL")
    return not malos


if __name__ == "__main__":
    import sys
    sys.exit(0 if probar() else 1)
