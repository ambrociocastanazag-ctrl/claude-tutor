"""Las capacidades que TODOS los tutores (modo curso, Excel y Dia) comparten con el asistente. Un solo sitio:

  capacidades.reglas(app, codigo=False)       el bloque del prompt «lo que puedes hacer» (+ ojos, dibujos y preguntas)
  capacidades.ConWeb                          mezcla para la clase Tutor: WebSearch/WebFetch y el aviso «Buscando en la web…»
  capacidades.raices_curso(d)                 las carpetas del curso (proyecto, proyectos, lo que abre app.abrir)
  capacidades.contexto_editor(raices)         el archivo abierto en VS Code con números de línea, para el [Estado actual]
  capacidades.avisos_linea(ojos)              el texto «Sube/Baja hasta la línea N» que hay que añadir a la respuesta
  ojos_panel.Ojos(..., raices=[...])          con raices, los dibujos aceptan el objetivo {"linea": N, "archivo": "X.java"}
  capacidades.marcas_linea(marcas, ...)       para las flechas {"tipo": "app", "linea": N} del modo curso

Qué ya traía cada panel y qué falta está en tutor-pantalla/README.md («Capacidades de los tutores»)."""
import re, shutil, subprocess, tempfile, threading
from pathlib import Path

import archivos, asistente, editor_vscode, ojos, ojos_panel

HERRAMIENTAS_WEB = asistente.HERRAMIENTAS               # "WebSearch,WebFetch": solo leer la web


CAPACIDADES = """
TUS CAPACIDADES (las mismas del asistente del estudiante; úsalas cuando ayuden, sin presumir de ellas):
- VER OTRAS VENTANAS: si necesitas ver algo que no está en tu [Estado actual] (un diálogo, un error, otro programa, el
  navegador), pídeselo en una frase y termina con <pedir_ventana/>: le sale un botón con vista previa y él decide. También
  puede adjuntarte capturas con el botón de la cámara. Cuando tengas una captura, puedes señalar en ella con
  {{"tipo": "ventana", "id": N}} (o "caja") y dibujar sobre ella con los dibujos.
- DIBUJOS: foco, mano alzada, teclas, lupa, ratón fantasma, forma guía, secuencia, fórmula, SVG animado y más, encima de
  {app} o de cualquier ventana que él te haya enseñado. Úsalos cuando una demostración vea mejor que un párrafo.
- INVESTIGAR: WebSearch (buscar) y WebFetch (leer una página o un enlace que te pase). Úsalos si la respuesta depende de
  algo actual o de una página concreta, o si no estás seguro; no busques lo que ya sabes. Da siempre el enlace completo
  (https://...) y, si recomiendas descargar algo, la página oficial.
- ARCHIVOS: puede adjuntarte imágenes, PDF y texto (clip, Ctrl+V o arrastrar): léelos y úsalos. Y tú mismo lees los
  archivos de sus carpetas del curso (ver LEER ARCHIVOS).
- PREGUNTAS: puedes poner una tarjeta de preguntas con botones para comprobar que entendió (ver más abajo).
- VOZ: él puede activar la voz (botón del altavoz); lo que escribas en "decir" se lee en voz alta. Mantén las frases cortas.
En la pantalla solo miras, señalas y dibujas: nunca digas que hiciste clic, escribiste o cambiaste algo suyo. Si tu panel te deja cambiar su archivo (libro de Excel, diagrama de Dia), es solo con su permiso y como digan sus propias reglas."""

REGLAS_CODIGO = """
ARCHIVO ABIERTO Y LÍNEAS (cursos de código): cada vez que te escribe, el [Estado actual] trae «[Archivo abierto en el
editor]»: el archivo que tiene abierto ahora en {app}, con números de línea, el cursor y las líneas visibles. Si dice que
hay cambios SIN GUARDAR, el texto es el del disco y puede ir atrasado: pídele que guarde (Ctrl+S) si importa.
Para señalar UNA LÍNEA de ese archivo en el editor usa el objetivo "linea" (el número de la lista), con "archivo" si no es
el que tiene abierto; funciona en flechas y en dibujos:
  <marcas>[{{"tipo": "app", "linea": 21, "texto": "falta el punto y coma"}},
           {{"tipo": "dibujo", "forma": "foco", "linea": 14, "texto": "Aquí"}}]</marcas>
Si la línea no se ve en el editor, el panel le avisa «sube/baja hasta la línea N» y marca el borde: díselo tú también en
una frase. NUNCA digas que no ves la línea exacta: usa "linea". Si te piden señalar algo del código, ese es el camino
(no el nombre de un control de la ventana)."""


def reglas(app, codigo=False):
    """El bloque completo de capacidades para el prompt de cualquier tutor: capacidades + ojos + dibujos + preguntas
    (+ archivo abierto y líneas si es un curso de código)."""
    t = CAPACIDADES.format(app=app) + archivos.REGLAS + ojos_panel.REGLAS_OJOS + ojos_panel.REGLAS_DIBUJOS + ojos_panel.REGLAS_PREGUNTAS
    if codigo: t += REGLAS_CODIGO.format(app=app)
    return t


# ---------- investigar en la web: la mezcla para la clase Tutor de cada panel ----------
class ConWeb:
    """Mezcla para el Tutor (motor.Tutor de Excel o Dia): `class TutorX(capacidades.ConWeb, motor.Tutor)`. Arranca la
    sesión de Claude con WebSearch y WebFetch (nada más: ni archivos ni comandos) y manda «Buscando en la web…» a la
    página mientras investiga: pon `tutor.al_aviso = lambda t: api._empujar("window.avisoTrabajo(%s)" % json.dumps(t))`.
    Necesita en la clase: _intro() y self.curso (con .d["modelo_tutor"] o .modulos[0].d), como motor.Tutor."""
    herramientas = HERRAMIENTAS_WEB
    al_aviso = staticmethod(lambda t: None)
    carpetas = None                     # las de lectura libre; None = las del curso (archivos.carpetas_de)

    def _modelo(self):
        try: return self.curso.d.get("modelo_tutor") or self.curso.modulos[0].d.get("modelo_tutor") or "sonnet"
        except Exception: return "sonnet"

    def _arrancar(self):
        exe = shutil.which("claude")
        if not exe: raise RuntimeError("No encuentro Claude Code (el comando 'claude') en esta PC.")
        carpetas = self.carpetas if self.carpetas is not None else archivos.carpetas_de(getattr(self, "curso", None))
        archivos.activar(carpetas)                         # <pedir_archivo/> de este panel: dentro libre, fuera con tarjeta
        cwd, leer, extra = archivos.args_claude(carpetas)
        herr = self.herramientas + ("," + leer if leer else "")
        # --allowedTools solo la web: Read y Glob quedan con el permiso normal (libres en --add-dir, negados fuera)
        cmd = [exe, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--include-partial-messages", "--tools", herr, "--allowedTools", self.herramientas, *extra,
               "--model", self._modelo(), "--strict-mcp-config", "--no-session-persistence", "--setting-sources", ""]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, encoding="utf-8", bufsize=1, cwd=cwd,
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.turnos = 0
        self._turno(archivos.lista(carpetas) + "\n\n" + self._intro(), lambda t: None)

    def _turno(self, contenido, al_trozo):
        # el bucle de lectura es el del asistente (no se duplica): solo añade el aviso al usar una herramienta
        return asistente.Sesion._turno(self, contenido, al_trozo, self.al_aviso)


# ---------- archivo abierto y líneas ----------
def raices_curso(d):
    """Las carpetas donde puede estar el archivo abierto: «proyecto», las rutas de «proyectos» y la carpeta que abre
    app.abrir (p. ej. code "C:/…/Proyecto Programacion"). `d`: el curso.json ya leído."""
    r = []
    if d.get("proyecto"): r.append(str(d["proyecto"]))
    for info in (d.get("proyectos") or {}).values():
        if isinstance(info, dict) and info.get("ruta"): r.append(str(info["ruta"]))
    abrir = (d.get("app") or {}).get("abrir") or ""
    for c in re.findall(r'"([^"]+)"', abrir) or abrir.split()[1:]:
        if Path(c).is_dir(): r.append(c)
    vistos, out = set(), []
    for x in r:
        k = str(Path(x)).lower()
        if k not in vistos: vistos.add(k); out.append(x)
    # la carpeta más amplia primero no importa: se busca en todas y gana el archivo más reciente
    return out


def ventana_editor(hwnd=None, raices=()):
    """El hwnd del editor: el que se pasa (si es VS Code o de su familia); si no, el editor cuyo título nombra una
    carpeta del curso (con varios VS Code o forks abiertos, el del proyecto y no otro); si no, el más reciente."""
    if hwnd and editor_vscode.es_vscode(ojos.app_de(ojos.pid_de(hwnd))): return hwnd
    eds = [v for v in ojos.listar_ventanas() if editor_vscode.es_vscode(v["app"])]
    if not eds: return None
    nombres = set()
    for r in raices or ():
        p = Path(r)
        nombres |= {p.name.lower(), p.parent.name.lower()}
    nombres.discard("")
    for v in eds:                                   # en orden: el más reciente primero
        if any(f" - {n} - " in f" {v['titulo'].lower()} - " or v["titulo"].lower().endswith(f" - {n}") for n in nombres):
            return v["hwnd"]
    return eds[0]["hwnd"]


def contexto_editor(raices, hwnd=None):
    """Texto del archivo abierto para el [Estado actual] (vacío si no hay editor)."""
    h = ventana_editor(hwnd, raices)
    return editor_vscode.contexto_archivo(h, raices) if h else ""


def ubicar_linea(m, raices, hwnd=None):
    """Para Ojos._donde: la marca {"linea": N, "archivo": "X"} → (hwnd, caja [x, y, w, h] en pantalla, aviso o None).
    Lanza ValueError si no se puede ubicar."""
    h = ventana_editor(hwnd, raices)
    if not h: raise ValueError("no hay un editor de código abierto")
    try: n = int(m["linea"])
    except (TypeError, ValueError): raise ValueError(f"«linea» tiene que ser un número ({m.get('linea')!r})")
    v = editor_vscode.vista_editor(h, raices)
    if m.get("archivo") and v.get("archivo"):
        abierto = (v["archivo"]["nombre"] or "").lower()
        if Path(str(m["archivo"])).name.lower() != abierto:
            raise ValueError(f"ese archivo no es el que tiene abierto («{v['archivo']['nombre']}»): pídele que abra «{Path(str(m['archivo'])).name}»")
    r = editor_vscode.rect_linea(h, n, raices, v)
    if r["estado"] == "no_se": raise ValueError(f"línea {n}: {r['mensaje']}")
    return h, r["caja"], (r["mensaje"] if r["estado"] != "visible" else None)


def avisos_linea(o):
    """Los avisos «sube/baja hasta la línea N» que dejaron los objetivos «linea» (los vacía): se añaden a la respuesta."""
    a = list(dict.fromkeys(o.avisos_linea)); o.avisos_linea.clear()
    return a


def marcas_linea(marcas, raices, hwnd=None):
    """Las flechas con «linea» ({"tipo": "app", "linea": N, "texto": ...}) → ([{"c": {"caja": (l, t, r, b)}, "texto", "n",
    "color"}] para panel_curso._pintar, [avisos]). Las que no se pueden ubicar van a los avisos."""
    ms, av = [], []
    for m in marcas:
        if not (isinstance(m, dict) and m.get("linea") is not None and m.get("tipo") in ("app", "ventana", "linea", None)): continue
        try: h, c, aviso = ubicar_linea(m, raices, hwnd)
        except ValueError as e: av.append(str(e)); continue
        if aviso: av.append(aviso)
        ms.append({"c": {"caja": (c[0], c[1], c[0] + c[2], c[1] + c[3])}, "texto": str(m.get("texto") or "")[:40],
                   "n": m.get("n"), "color": m.get("color") or "azul"})
    return ms, av


def probar():
    """python capacidades.py: pruebas sin ventanas ni IA."""
    import sys
    malos = 0
    def ver(c, t):
        nonlocal malos
        print(("  ok " if c else "  ✘ MAL ") + t)
        if not c: malos += 1
    r = reglas("VS Code", True)
    ver("WebSearch" in r and "pedir_ventana" in r and "DIBUJOS" in r and "<preguntas>" in r and '"linea"' in r, "el prompt trae ojos, dibujos, web, preguntas y «linea»")
    ver("<volver_a_mirar/>" in reglas("Paint") and "Recortar" in reglas("Paint"), "el prompt trae la regla de volver a mirar la misma ventana")
    ver("linea" not in reglas("Paint").split("TUS CAPACIDADES")[1].split("DIBUJOS: además")[0], "sin código no hay bloque de archivo abierto")
    ver(editor_vscode.nombre_del_titulo("● Prueba.java - Proyecto Programacion - Visual Studio Code") == ("Prueba.java", True), "título con ● = sin guardar")
    ver(editor_vscode.nombre_del_titulo("Prueba.java - X - Visual Studio Code") == ("Prueba.java", False), "título sin ● = guardado")
    ver(editor_vscode.nombre_del_titulo("FALLOS.m… - Sistema - Visual Studio Code")[0] == "FALLOS.m…", "título cortado con «…»")
    with tempfile.TemporaryDirectory() as t:
        d = Path(t) / "a" / "src"; d.mkdir(parents=True); (d / "Foo.java").write_text("x\n", encoding="utf-8")
        ver(editor_vscode.buscar_archivo("Foo.java", [t]) == d / "Foo.java", "se encuentra el archivo dentro de la carpeta")
        ver(editor_vscode.buscar_archivo("Fo….", [t]) is None or True, "nombre cortado no rompe")
        ver(raices_curso({"proyecto": t, "proyectos": {"x": {"ruta": t}}, "app": {"abrir": f'code "{t}"'}}) == [t], "raices_curso sin repetidos")
    # numeración con una captura de mentira: 5 filas de «dígitos» a 24 px, cursor en la fila 3 = línea 40
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (400, 200), (30, 30, 30)); dr = ImageDraw.Draw(img)
    for k in range(6):
        y = 20 + 24 * k
        dr.rectangle((60, y, 78, y + 10), fill=(140, 140, 140))                  # «número»
        dr.rectangle((120, y, 120 + 30 + 20 * k, y + 10), fill=(200, 200, 200))   # «texto»
    num, como, xt, xf = editor_vscode.numerar(img, (10, 10, 390, 190), (118, 20 + 48 - 6, 380, 20 + 48 + 20), (40, 3), None)
    ver(como == "cursor" and [n for n, _, _ in num] == [38, 39, 40, 41, 42, 43], f"numera por el cursor ({[n for n, _, _ in num]})")
    # alineación con el archivo: largos crecientes en las filas ↔ líneas del archivo
    import random; random.seed(3); n_ = [random.randint(3, 60) for _ in range(60)]
    lineas = ["a" * k for k in n_]
    largos = [k * 9 for k in n_[20:30]]
    p, conf = editor_vscode.alinear_con_archivo(largos, lineas)
    ver(p == 21 and conf > 0.99, f"alinea las filas con el archivo (primera = {p})")
    print("Capacidades: todo bien" if not malos else f"Capacidades: {malos} fallo(s)")
    return malos


if __name__ == "__main__":
    import sys
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    sys.exit(probar())
