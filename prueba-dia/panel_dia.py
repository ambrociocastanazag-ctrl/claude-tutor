"""Panel de clase en vivo para Dia: cursos con módulos (como los de Excel) sobre cualquier tipo de diagrama.
Uso:  python panel_dia.py                      (el ejemplo de siempre: el módulo «La clase», leccion_clase.json)
      python panel_dia.py <carpeta>/curso.json (un curso con varios módulos; ver curso_dia.py y el README)
      python panel_dia.py [curso.json] --probar  (lo arma y lo comprueba todo sin abrir ventanas)

Clase en vivo: Dia se abre con el plugin propio (plugin-dia/dia-tutor.dll, cargado con DIA_LIB_PATH, sin tocar la
instalación) y con dos pestañas en UNA ventana: la lección (pasos/clase_en_vivo.dia) y el diagrama de la persona en ese módulo
(mi_diagrama.dia en el ejemplo; mis_diagramas/mi_<módulo>.dia en un curso). Al cambiar de módulo se abre la pestaña de su
diagrama y se cierra la del módulo anterior si no tiene cambios sin guardar.
Cada paso de la lección SE SUMA a los anteriores: sus «cambios» usan el mismo vocabulario que el tutor (cambios_dia: clases,
casos de uso, secuencia, actividades, estados, componentes, despliegue, paquetes, objetos y modo libre). Con el plugin, cada paso
se arma una vez en la pestaña de la lección y se guarda en pasos/<módulo>/paso_N.dia (curso_dia.construir); al pasar de paso,
«cargar» lo pone al instante y lo nuevo del paso queda seleccionado y con un marco azul (capa «Tutor»).
«En Dia: dónde se hace» (Fase 2): si el paso declara «interfaz» (herramienta, menú, pestaña, botón, campo u objeto), el panel
dibuja flechas y notas ENCIMA de la ventana real de Dia (overlay_dia.py: ventana transparente que deja pasar los clics, no roba
el foco y sigue a Dia), con las posiciones exactas de la orden «widgets»; se recalculan cada segundo (si abres Propiedades,
aparecen las de su diálogo) y se borran al cambiar de paso. «Hazlo por mí» hace la acción delante de la persona
(interfaz_dia.ordenes_hazlo: elegir hoja y herramienta, abrir Propiedades, cambiar de pestaña…), sobre el diagrama de la
lección; en el «Tu turno» toca el suyo, así que pide confirmación (pulsar otra vez).
El «Tu turno» se revisa sin IA al pulsar «Comprobar» (curso_dia.revisar_turno: clases, objetos, conexiones, mensajes en orden,
guardas… y los errores típicos del JSON); si Dia tiene cambios sin guardar («modificado»), pide guardar antes.
Las marcas del tutor se dibujan en el panel y dentro de Dia (capa «Tutor»), y el tutor puede crear y cambiar diagramas con
permiso (cambios_dia.Cambios). El panel recuerda el módulo y el paso (progreso.json, junto al curso).
Si el plugin no responde (otro Dia), vuelve al modo de antes: una ventana de Dia por archivo.
La página es la del panel de Excel (../panel-excel/panel.html) y el tutor, su motor.Tutor."""
import hashlib, json, os, subprocess, sys, tempfile, threading, time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EXCEL = AQUI.parent / "panel-excel"
sys.path.insert(0, str(EXCEL)); sys.path.insert(0, str(AQUI / "plugin-dia"))
import dia_uml as du
import dia_objetos as do                       # cualquier objeto de Dia: lectura, texto, cajas y el dibujo real con marcas
import cambios_dia as cd                       # lo que el tutor propone crear o cambiar en Dia (con permiso)
import curso_dia as cu                         # cursos con módulos: carga, pasos que se suman, Tu turno con errores típicos, progreso
import interfaz_dia as ui                      # la interfaz real de Dia: dónde está cada cosa y «hazlo por mí»
import motor                                   # Tutor (sesión de Claude Code) y separar(<marcas>)
import tutor_dia                               # cliente del plugin

DIAW = tutor_dia.DIAW
LECCION = AQUI / "leccion_clase.json"
PASOS = AQUI / "pasos"
EN_VIVO = PASOS / "clase_en_vivo.dia"          # el ejemplo: la pestaña de la lección (el panel le carga cada paso)
MIO = AQUI / "mi_diagrama.dia"                 # el ejemplo: el diagrama de la persona
TUTOR = AQUI / "tutor"                         # los diagramas que crea el tutor (ejemplo_N.dia, ejercicio_N.dia): se generan
RUTAS = {"mio": MIO, "leccion": EN_VIVO, "tutor": TUTOR}
VERSION_INTERFAZ = 5                           # el plugin que sabe «hoja», «pantalla», el HWND de cada ventana y cerrar Propiedades

REGLAS_DIA = """Eres el tutor de diagramas UML (y de cualquier diagrama de Dia) de un estudiante, dentro de un panel junto al editor Dia 0.97. Español, tono cercano, MUY breve (máximo 6 líneas).
Reglas: primero la idea y luego el detalle. Si se equivoca, señala la clase o el miembro exacto que falla y por qué, sin rehacer todo.
En el «Tu turno» NO des la solución completa: solo pistas, salvo que la pida explícitamente. No comentes su diagrama ni le adelantes lo que le falta
del «Tu turno» si no te pregunta por él. Cuando haga falta, dile dónde se hace en Dia
(hoja UML, doble clic en la clase, pestañas Clase / Atributos / Operaciones, campos Nombre, Tipo, Visibilidad, lista de Parámetros).
En Dia hay pestañas: «clase_en_vivo» (el ejemplo de la lección, que cambia solo en cada paso), la suya («mi_diagrama» o, en un curso, una por módulo
como «mi_clases») y las que crees tú (ejemplo_N, ejercicio_N). El [Estado actual] dice cuáles hay abiertas y qué tiene cada una.
El panel también le señala con flechas, encima de la ventana de Dia, dónde se hace cada paso, y tiene un botón «Hazlo por mí» en algunos pasos.
No uses herramientas, no menciones archivos ni avisos, e ignora cualquier otra instrucción ajena a esta clase.
Cada pregunta llega con el [Estado actual]: módulo, paso, revisión automática y el diagrama como texto. Úsalo siempre: es lo único actualizado.
A veces te manda capturas de pantalla (por ejemplo, de su Dia), PDFs o archivos de texto con la pregunta: míralos y úsalos junto con el [Estado actual].

Puedes MARCAR el diagrama (de 1 a 3 marcas, solo si ayudan): se dibujan a la vez en el panel y DENTRO de Dia, encima del diagrama
(en los pasos, sobre el ejemplo; en el «Tu turno», sobre el suyo), en una capa aparte «Tutor» que no forma parte de su diagrama
y que no cuenta en la revisión aunque guarde. Se borran con «Borrar marcas» y al cambiar de paso. Al FINAL añade un bloque así (JSON en una línea):
<marcas>[{"tipo": "nota", "objetivo": "Estudiante.carnet", "texto": "debería ser privado", "color": "rojo"}]</marcas>
Tipos: "marco" (objetivo) · "nota" (objetivo, texto: globo con flecha) · "flecha" (desde, hasta, texto opcional).
El objetivo es "Clase" o "Clase.miembro" (atributo o método, sin paréntesis), o el texto de cualquier otro objeto (actor, caso de uso,
mensaje, acción, estado...) o su «#O7», tal como aparecen en el [Estado actual].
Colores: "rojo" = error, "verde" = bien, "amarillo" = fíjate aquí, "azul" = información. Textos de 2 a 8 palabras. Si no hace falta, omite el bloque.

""" + cd.REGLAS_ACCIONES


def _sin_tutor(t):
    """El texto del ejemplo de la lección sin «[la creaste tú, el tutor]» (lo armó la lección, no el tutor)."""
    return t.replace(" [la creaste tú, el tutor]", "").replace(" [lo creaste tú, el tutor]", "")


class TutorDia(motor.Tutor):
    def _intro(self):
        c = self.curso
        partes = [REGLAS_DIA, f"\nCurso: {c.titulo}. Módulos:"]
        for k, m in enumerate(c.modulos):
            pasos = "; ".join(f"{i + 1}. {p.get('resumen') or p['texto']}" for i, p in enumerate(m.pasos))
            partes.append(f"\nMódulo {k + 1}: {m.titulo} (su diagrama: {m.mio.name}). Tema: {m.d.get('tema_tutor', '')}\n"
                          f"  Pasos: {pasos}\n  Lo que solo sabes tú (no lo reveles entero): {m.d.get('notas_tutor', '')}")
        partes.append("\nResponde solo: Listo")
        return "\n".join(partes)


def curso_de(leccion_o_curso):
    """Un curso_dia.Curso; acepta también el diccionario de una lección (el ejemplo, en las pruebas)."""
    if isinstance(leccion_o_curso, cu.Curso): return leccion_o_curso
    c = cu.Curso(LECCION)
    if isinstance(leccion_o_curso, dict) and leccion_o_curso is not c.modulos[0].d:
        m = c.modulos[0]; m.d = leccion_o_curso; m.pasos = cu.validar_modulo(leccion_o_curso, LECCION.name)
    return c


def preparar(curso, cam=None):
    """Arma los pasos de cada módulo (sin plugin: el XML aquí mismo) y la pestaña de la lección, y crea el diagrama de la persona
    del módulo actual solo si no existe (nunca se sobrescribe: es su trabajo)."""
    curso = curso_de(curso)
    curso.pasos_dir.mkdir(parents=True, exist_ok=True)
    for m in curso.modulos: cu.construir(m)
    if not curso.en_vivo.exists(): du.escribir(curso.en_vivo, [])
    m, _ = curso.progreso()
    cu.crear_inicial(curso.modulos[m], 0)
    return curso


# ---------- Ventanas de Dia (modo de respaldo y comprobaciones) ----------
def ventana_de_dia(archivo):
    """Ventana de Dia cuyo título es ese archivo (la pestaña activa), o None."""
    try:
        import win32gui
        encontrada = []
        def cada(h, _):
            t = win32gui.GetWindowText(h).lstrip("*")
            if win32gui.IsWindowVisible(h) and t.startswith(archivo + " ("): encontrada.append(h)
        win32gui.EnumWindows(cada, None)
        return encontrada[0] if encontrada else None
    except Exception: return None


def cerrar_ventana(pid):
    """Cierra con cortesía (como la ✕) las ventanas de un proceso de Dia que abrió el panel."""
    try:
        import win32gui, win32con, win32process
        def cada(h, _):
            if win32process.GetWindowThreadProcessId(h)[1] == pid and win32gui.IsWindowVisible(h):
                win32gui.PostMessage(h, win32con.WM_CLOSE, 0, 0)
        win32gui.EnumWindows(cada, None)
    except Exception: pass


def al_frente(h):
    """Trae la ventana al frente sin cambiarle el tamaño (SW_RESTORE solo si está minimizada: si no, la desmaximizaría)."""
    try:
        import win32gui
        if win32gui.IsIconic(h): win32gui.ShowWindow(h, 9)
        win32gui.SetForegroundWindow(h)
    except Exception: pass


class DiaEnVivo:
    """Dia con el plugin y las dos pestañas. Si no se puede, `modo` queda en 'ventanas' (respaldo)."""
    en_vivo, mio, _version = EN_VIVO, MIO, None     # (también para los Dia de mentira de las pruebas)

    def __init__(self, carpeta_ordenes=None):
        self.cliente = tutor_dia.Dia(carpeta_plugin=str(AQUI / "plugin-dia"), **({"carpeta_ordenes": carpeta_ordenes} if carpeta_ordenes else {}))
        self.modo, self.motivo, self.listo = "arrancando", "", threading.Event()
        self.cerrojo = threading.Lock()
        self.en_vivo, self.mio = EN_VIVO, MIO
        self._version = None

    def arrancar(self, en_vivo=None, mio=None):
        self.en_vivo, self.mio = Path(en_vivo or self.en_vivo), Path(mio or self.mio)
        try:
            # ¿ya hay un Dia con el plugin atendiendo esta carpeta (otra sesión del panel)? Se usa ese: dos Dia con la misma
            # carpeta se quitarían las órdenes (el plugin, además, no deja que un segundo Dia la atienda). Varios intentos: un Dia
            # minimizado u ocupado puede tardar en contestar.
            if any(self.cliente.orden("ping", timeout=2).startswith("ok") for _ in range(2)):
                abiertos = self.cliente.orden("ventanas")
                for f in (self.en_vivo, self.mio):
                    if f.name not in abiertos: self.cliente.orden(f'abrir "{f}"')
                self.modo = "plugin"; return
            if ventana_de_dia(self.mio.name):
                raise RuntimeError("tu diagrama ya está abierto en otra ventana de Dia")
            c = self.cliente
            for f in ("orden.txt", "respuesta.txt"):
                try: os.remove(os.path.join(c.carpeta, f))
                except FileNotFoundError: pass
            env = os.environ.copy()
            env["DIA_LIB_PATH"] = c.carpeta_plugin + ";" + os.path.join(os.path.dirname(tutor_dia.DIA_BIN), "dia")
            env["DIA_TUTOR_DIR"] = c.carpeta
            # una sola ventana con dos pestañas: la lección y la de la persona
            c.proc = subprocess.Popen([DIAW, "--integrated", str(self.en_vivo), str(self.mio)], env=env, cwd=tutor_dia.DIA_BIN)
            t0 = time.time()
            while time.time() - t0 < 30:
                if c.proc.poll() is not None: raise RuntimeError("Dia se cerró al arrancar")
                if c.orden("ping", timeout=1).startswith("ok"): self.modo = "plugin"; return
            raise RuntimeError("el plugin no responde (¿otra versión de Dia?)")
        except Exception as e:
            self.modo, self.motivo = "ventanas", str(e)
        finally:
            if self.modo == "plugin":
                try: self.borrar_marcas()                 # por si guardó marcas en una sesión anterior
                except Exception: pass
            self.listo.set()

    def orden(self, texto):
        with self.cerrojo: return self.cliente.orden(texto)

    def version(self):
        if self._version is None:
            v = self.orden("version").split() if self.modo == "plugin" else []
            self._version = int(v[2]) if len(v) == 3 and v[:2] == ["ok", "version"] and v[2].isdigit() else 0
        return self._version

    def mostrar_paso(self, ruta, info=None, nombre_clase=None):
        """La pestaña de la lección pasa a ese paso y queda al frente, con lo nuevo del paso seleccionado y con un marco azul."""
        r = self.orden(f'@{self.en_vivo.name} cargar "{ruta}"')
        if not r.startswith("ok"): return r
        self.orden(f"@{self.en_vivo.name} activar")
        refs = (info or {}).get("refs") or []
        if refs and self.version() >= VERSION_INTERFAZ:
            self.orden(f"@{self.en_vivo.name} seleccionar " + " ".join(f'"{x}"' for x in refs[:20]))
        elif nombre_clase or (info or {}).get("objetivos"):
            self.orden(f'@{self.en_vivo.name} seleccionar "{nombre_clase or info["objetivos"][0]}"')
        return r

    def resaltar(self, archivo, cajas):
        """Marcos azules (capa «Tutor») alrededor de lo nuevo del paso."""
        if self.modo != "plugin" or not cajas: return
        f = lambda v: f"{v:.3f}"
        self.orden("\n".join(f"@{archivo} recuadro {f(x - 0.25)} {f(y - 0.25)} {f(w + 0.5)} {f(h + 0.5)} azul 0.07" for x, y, w, h in cajas[:12]))

    def mostrar_mio(self, nombre=None):
        return self.orden(f"@{nombre or self.mio.name} activar")

    def ventana(self):
        """(HWND, pid) de la ventana principal de Dia, por la orden «widgets» (versión 5) o por su título."""
        try:
            for v in ui.leer_widgets(self.orden("widgets")):
                if v.get("rol") == "dia-main-window" and v.get("hwnd"):
                    import win32process
                    return v["hwnd"], win32process.GetWindowThreadProcessId(v["hwnd"])[1]
        except Exception: pass
        h = ventana_de_dia(self.en_vivo.name) or ventana_de_dia(self.mio.name)
        try:
            import win32process
            return (h, win32process.GetWindowThreadProcessId(h)[1]) if h else (None, None)
        except Exception: return h, None

    # ----- marcas del tutor dentro de Dia (capa «Tutor»; no cambian la capa activa ni marcan cambios) -----
    def borrar_marcas(self, *archivos):
        """Vacía la capa «Tutor» de esas pestañas (por defecto, de las dos)."""
        if self.modo != "plugin": return ""
        return self.orden("\n".join(f"@{a} borrar_marcas" for a in (archivos or (self.en_vivo.name, self.mio.name))))

    def dibujar_marcas(self, archivo, marcas, respaldo):
        """Dibuja las marcas en la pestaña `archivo` sobre lo que hay EN PANTALLA (orden «cajas»: vale
        aunque la persona haya movido algo sin guardar); si no, sobre lo guardado (`respaldo`)."""
        if self.modo != "plugin": return 0
        cajas = du.cajas_de_plugin(self.orden(f"@{archivo} cajas")) or du.cajas_cm(respaldo)
        ordenes, n = du.ordenes_marcas(marcas, cajas, archivo)
        r = self.orden("\n".join([f"@{archivo} borrar_marcas"] + ordenes))
        if "error" in r: print("marcas en Dia:", r, flush=True)
        return n


class OverlayDia:
    """El proceso overlay_dia.py (flechas encima de la ventana real de Dia). Se arranca la primera vez que hace falta."""

    def __init__(self):
        self.proc, self.cerrojo, self.ultima, self.respuestas = None, threading.Lock(), None, []

    def _mandar(self, o):
        with self.cerrojo:
            if self.proc is None or self.proc.poll() is not None:
                if o.get("cmd") in ("borrar", "salir"): return
                self.proc = subprocess.Popen([sys.executable, str(AQUI / "overlay_dia.py")], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                             text=True, encoding="utf-8", creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                threading.Thread(target=self._leer, args=(self.proc,), daemon=True).start()
            try: self.proc.stdin.write(json.dumps(o) + "\n"); self.proc.stdin.flush()
            except OSError: self.proc = None

    def _leer(self, proc):
        for linea in proc.stdout:
            try: self.respuestas.append(json.loads(linea)); self.respuestas = self.respuestas[-20:]
            except ValueError: pass

    def mostrar(self, marcas, pids, panel=None):
        clave = json.dumps(marcas, sort_keys=True)
        if clave == self.ultima: return False
        self.ultima = clave
        if not marcas: self._mandar({"cmd": "borrar"}); return True
        self._mandar({"cmd": "mostrar", "marcas": marcas, "pids": pids, "panel": panel}); return True

    def borrar(self):
        if self.ultima is not None: self._mandar({"cmd": "borrar"})
        self.ultima = None

    def cerrar(self):
        self._mandar({"cmd": "salir"})


class DibujoDia:
    """El SVG que dibuja Dia de un diagrama: con el plugin (versión 4), orden «exportar» sobre lo que hay en pantalla
    (sin la capa «Tutor»), y sus cajas con «cajas»; sin plugin, dia.exe en modo línea de órdenes sobre lo guardado
    (sin la capa «Tutor», guardado en caché por contenido). Sin Dia: (None, None) y el panel usa su dibujo propio."""

    def __init__(self, dia):
        self.dia, self.tmp, self.cache = dia, Path(tempfile.mkdtemp(prefix="dia-dibujo-")), {}

    def svg(self, pestana, guardado):
        if getattr(self.dia, "modo", "") == "plugin":
            try:
                if not hasattr(self, "_v4"):
                    v = self.dia.orden("version").split()
                    self._v4 = len(v) == 3 and v[:2] == ["ok", "version"] and v[2].isdigit() and int(v[2]) >= 4
                if self._v4:
                    f = self.tmp / f"{pestana}.svg"
                    r = self.dia.orden(f'@{pestana} exportar "{f}"')
                    if r.startswith("ok exportado") and f.exists():
                        return f.read_text(encoding="utf-8", errors="replace"), du.cajas_de_plugin(self.dia.orden(f"@{pestana} cajas"))
            except Exception: pass
        return self.por_linea_de_ordenes(guardado), None

    def por_linea_de_ordenes(self, ruta):
        if not ruta.exists(): return None
        crudo = ruta.read_bytes()
        clave = hashlib.sha1(crudo).hexdigest()
        if clave in self.cache: return self.cache[clave]
        import gzip
        if crudo[:2] == bytes((0x1f, 0x8b)): crudo = gzip.decompress(crudo)
        copia, salida = self.tmp / f"{clave}.dia", self.tmp / f"{clave}.svg"
        copia.write_text(do.quitar_capa_tutor(crudo.decode("utf-8", errors="replace")), encoding="utf-8")
        exe = os.path.join(tutor_dia.DIA_BIN, "dia.exe")
        try: subprocess.run([exe, "-n", "-e", str(salida), "-t", "svg", str(copia)], cwd=tutor_dia.DIA_BIN, capture_output=True, timeout=20,
                            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        except Exception: return None
        texto = salida.read_text(encoding="utf-8", errors="replace") if salida.exists() else None
        self.cache[clave] = texto
        return texto


class Api:
    def __init__(self, curso, tutor, dia, rutas=None):
        self._curso = curso_de(curso)
        self._m, self._n = 0, 0
        self._tutor, self._dia, self._ventana = tutor, dia, None
        self._proc_paso, self._proc_mio, self._huella, self._rev, self._marcas = None, None, None, None, []
        self._vista = None          # la revisión que se ve en el panel: solo después de pulsar Comprobar
        self.recordar = False       # guardar el progreso (solo el panel de verdad; las pruebas no)
        base = {"mio": self._mod.mio, "leccion": self._curso.en_vivo, "tutor": self._curso.tutor_dir}
        self._cambios = cd.Cambios(dia, rutas or base)     # propuestas del tutor (Aplicar / No / Deshacer) y su ejercicio
        self._cerrojo_cambios = threading.Lock()
        self._notas = []            # lo que se le cuenta al tutor en la próxima pregunta («[Del panel]»)
        self._dibujo = DibujoDia(dia)
        self._overlay, self._gen, self._faltan, self._hazlo_pedido, self._senalar_extra = OverlayDia(), 0, [], 0.0, None
        self._preparado = set()     # módulos ya armados con el plugin en esta sesión
        threading.Thread(target=self._vigilar, daemon=True).start()
        threading.Thread(target=self._vigilar_interfaz, daemon=True).start()

    # ----- estado -----
    @property
    def _mod(self): return self._curso.modulos[self._m]

    @property
    def _lec(self): return self._mod.d

    def _mio(self): return self._cambios.rutas["mio"] if hasattr(self, "_cambios") else self._mod.mio

    def _en_vivo(self): return self._cambios.rutas["leccion"]

    def _paso(self): return self._mod.pasos[self._n]

    def _turno(self): return self._paso().get("_turno")

    def _turno_modulo(self):
        """El «Tu turno» del módulo (para revisar lo guardado aunque se esté en otro paso: lo usa el tutor)."""
        return self._turno() or next((p["_turno"] for p in self._mod.pasos if p.get("_turno")), None)

    def _info_paso(self):
        try: return self._mod.indice().get("pasos", [])[self._n]
        except (IndexError, AttributeError): return {}

    def _tiene_ejemplo(self):
        return not self._turno() and self._mod.archivo_paso(self._n).exists() and \
            (self._paso().get("_cambios") or self._paso().get("diagrama") or self._n > 0)

    def _diagrama(self):
        """Lo que se dibuja en el panel: en el Tu turno, su diagrama; si no, el del paso."""
        vacio = {"clases": [], "relaciones": [], "notas": [], "otros": []}
        if self._turno():
            try: return du.leer(self._mio())
            except Exception: return vacio
        try: return du.leer(self._mod.archivo_paso(self._n)) if self._tiene_ejemplo() else vacio
        except Exception: return vacio

    def _marcas_paso(self):
        """Los marcos azules de lo nuevo del paso (en el dibujo del panel), si el tutor no ha marcado nada."""
        if self._turno() or self._marcas: return []
        return [{"tipo": "marco", "objetivo": o, "color": "azul"} for o in (self._info_paso().get("objetivos") or [])[:12]]

    def _svg(self):
        """El dibujo del panel: el de Dia de verdad (exportado a SVG: vale para cualquier tipo de diagrama) con las marcas
        del tutor y los ✔/✘ de la revisión encima. Si no se puede exportar, el dibujo propio de las clases (dia_uml.svg)."""
        turno = self._turno()
        if not turno and not self._tiene_ejemplo(): return ""
        vista = self._vista if turno and self._vista and not self._vista.get("viejo") else None
        d = self._diagrama()
        pestana, guardado = (self._mio().name, self._mio()) if turno else (self._en_vivo().name, self._mod.archivo_paso(self._n))
        marcas = self._marcas or self._marcas_paso()
        try:
            dibujo, cajas = self._dibujo.svg(pestana, guardado)
            if dibujo: return do.svg_con_marcas(dibujo, cajas or du.cajas_cm(d), marcas, vista)
        except Exception as e: print("dibujo de Dia:", e, flush=True)
        return du.svg(d, marcas, vista)

    def _botones(self):
        p, vivo = self._paso(), self._dia.modo == "plugin"
        bs = []
        if self._turno(): bs.append({"id": "mio", "etiqueta": "Ir a mi diagrama en Dia" if vivo else "Abrir mi diagrama en Dia", "icono": "open"})
        elif self._tiene_ejemplo(): bs.append({"id": "paso", "etiqueta": "Ver el ejemplo en Dia" if vivo else "Ver este paso en Dia", "icono": "eye"})
        if vivo and p.get("_interfaz"): bs.append({"id": "senalar", "etiqueta": "Señálamelo en Dia", "icono": "cursor"})
        if vivo and p.get("_hazlo"): bs.append({"id": "hazlo", "etiqueta": p["_hazlo"]["etiqueta"], "icono": "spark"})
        return bs

    def _estado(self, aviso=""):
        p, t = self._paso(), self._turno()
        if self._dia.modo == "ventanas" and self._dia.motivo and not aviso:
            aviso = f"Dia va en el modo de antes (una ventana por archivo): {self._dia.motivo}."
        mio = self._mio()
        return {"n": self._n, "total": len(self._mod.pasos), "texto": p["texto"], "aviso": aviso,
                "m": self._m, "modulos": [{"titulo": m.titulo, "codigo": m.codigo} for m in self._curso.modulos] if len(self._curso.modulos) > 1 else [],
                "titulo": self._mod.titulo, "titulo_codigo": self._mod.codigo, "curso": self._curso.titulo or self._lec.get("curso", ""),
                "paso_titulo": p.get("titulo", ""), "donde": p.get("en_dia") or p.get("donde", ""), "app": "Dia", "objeto": "diagrama",
                "hoja": mio.name if t else self._en_vivo().name, "ejercicio": t.get("titulo", "") if t else "",
                "svg": self._svg(), "diagrama_titulo": "Tu diagrama" if t else "Ejemplo del paso",
                "diagrama_archivo": mio.name if t else "", "botones": self._botones(),
                "revision": (self._vista or {"estado": "pendiente", "ok": 0, "total": 0, "mensaje": t.get("al_empezar",
                             "Dibuja en Dia. Cuando termines, guarda (Ctrl+S) y pulsa Comprobar.")}) if t else None,
                "tutor_ej": self._cambios.estado_ejercicio()}

    def _pestana_marcas(self):
        """La pestaña de Dia donde van las marcas: la suya en el «Tu turno», la del ejemplo en los pasos."""
        return self._mio().name if self._turno() else (self._en_vivo().name if self._tiene_ejemplo() else None)

    def _marcas_en_dia(self, marcas):
        archivo = self._pestana_marcas()
        if not archivo or self._dia.modo != "plugin": return 0
        try: return self._dia.dibujar_marcas(archivo, marcas, self._diagrama())
        except Exception as e: print("marcas en Dia:", e, flush=True); return 0

    def _quitar_marcas_dia(self, *archivos):
        if self._dia.modo != "plugin": return
        try: self._dia.borrar_marcas(*(archivos or (self._en_vivo().name, self._mio().name)))
        except Exception: pass

    def _empujar(self, js):
        if self._ventana:
            try: self._ventana.evaluate_js(js)
            except Exception: pass

    # ----- revisión: vigila el diagrama de la persona (para el tutor y el dibujo); el resultado, solo con Comprobar -----
    def _revisar(self):
        t = self._turno_modulo()
        if not t: self._rev = None; return True
        try: self._rev = cu.revisar_turno(du.leer(self._mio()), t)
        except Exception: return False            # a medio guardar: se reintenta en la próxima vuelta
        return True

    def _vigilar(self):
        while True:
            try:
                h = self._mio().stat().st_mtime_ns
                if h != self._huella and self._revisar():
                    if self._marcas and self._turno(): self._quitar_marcas_dia(self._mio().name)   # guardó: las marcas ya no valen
                    self._huella = h
                    if self._turno():
                        self._marcas = []
                        aviso = ""
                        if self._vista and not self._vista.get("viejo"):      # guardó algo nuevo después de comprobar
                            self._vista = dict(self._vista, viejo=True); aviso = "window.turnoCambio(); "
                        self._empujar(f"{aviso}window.mostrarDiagrama({json.dumps(self._svg())})")
                if self._cambios.vigilar_ejercicio():               # guardó el ejercicio del tutor después de comprobar
                    self._empujar("window.ejercicioCambio && window.ejercicioCambio()")
            except FileNotFoundError: pass
            except Exception: pass
            time.sleep(0.8)

    # ----- «En Dia: dónde se hace»: flechas encima de la ventana real de Dia -----
    def _objetivos_interfaz(self):
        p = self._paso()
        return (self._senalar_extra or []) + (p.get("_interfaz") or [])

    def _marcas_interfaz(self):
        """(marcas para el overlay, lo que no se ve). Con las posiciones de «widgets» y, para los objetos del diagrama, «pantalla»."""
        objetivos = self._objetivos_interfaz()
        if not objetivos or self._dia.modo != "plugin" or self._dia.version() < VERSION_INTERFAZ: return [], []
        ventanas = ui.leer_widgets(self._dia.orden("widgets"))
        def pantalla(nombre):
            pest = self._mio().name if self._turno() else self._en_vivo().name
            for l in self._dia.orden(f'@{pest} pantalla "{nombre}"').splitlines():
                q = l.split("\t")
                if q[0] == "pantalla" and len(q) >= 6: return tuple(int(v) for v in q[2:6])
            return None
        return ui.resolver(objetivos, ventanas, pantalla)

    def _pid_dia(self):
        """El proceso de Dia (no cambia mientras siga abierto): el overlay solo se ve con Dia o el panel al frente."""
        if not getattr(self, "_pid_d", None): self._pid_d = self._dia.ventana()[1]
        return self._pid_d

    def _pintar_interfaz(self):
        marcas, faltan = self._marcas_interfaz()
        self._faltan = faltan
        if not marcas: self._overlay.borrar(); return marcas
        self._overlay.mostrar(marcas, [p for p in (self._pid_dia(), os.getpid()) if p], self._hwnd_panel())
        return marcas

    def _con_dia_al_frente(self):
        try:
            import win32gui, win32process
            return win32process.GetWindowThreadProcessId(win32gui.GetForegroundWindow())[1] in (self._pid_dia(), os.getpid())
        except Exception: return True

    def _hwnd_panel(self):
        if getattr(self, "_hp", None): return self._hp
        try:
            import win32gui, win32process
            res = []
            def cada(h, _):
                if win32gui.IsWindowVisible(h) and win32process.GetWindowThreadProcessId(h)[1] == os.getpid() and win32gui.GetWindowText(h):
                    res.append(h)
            win32gui.EnumWindows(cada, None)
            self._hp = res[0] if res else None
        except Exception: self._hp = None
        return self._hp

    def _vigilar_interfaz(self):
        """Cada segundo, mientras el paso tenga algo que señalar: las posiciones pueden cambiar (abre Propiedades, cambia de
        pestaña, mueve el diálogo...). El overlay sigue él solo a la ventana; esto es para lo que aparece y desaparece."""
        while True:
            time.sleep(1.0)
            try:
                if self._objetivos_interfaz() and self._dia.modo == "plugin" and self._dia.listo.is_set() and self._con_dia_al_frente():
                    gen = self._gen; marcas, faltan = self._marcas_interfaz()
                    if gen == self._gen:
                        self._faltan = faltan
                        if marcas: self._overlay.mostrar(marcas, [p for p in (self._pid_dia(), os.getpid()) if p], self._hwnd_panel())
                        else: self._overlay.borrar()
            except Exception: pass

    # ----- navegación y Dia -----
    def estado(self):
        self._dia.listo.wait(35)
        if self._dia.modo == "plugin": self._preparar_modulo(); self._mover_dia()
        if self._rev is None: self._revisar()
        return self._estado()

    def _preparar_modulo(self):
        """Con el plugin: arma los pasos del módulo de verdad en Dia (una vez; luego quedan guardados) y abre su diagrama."""
        mod = self._mod
        if mod.id in self._preparado: return ""
        aviso = ""
        try:
            if self._cambios.plugin_al_dia():
                cu.construir(mod, self._cambios, self._en_vivo().name)
            cu.crear_inicial(mod, self._n, self._cambios if self._cambios.plugin_al_dia() else None, self._en_vivo().name)
        except Exception as e:
            print("armar el módulo en Dia:", e, flush=True); cu.construir(mod); aviso = f"No pude armar los pasos en Dia ({e}); van aproximados."
        abiertos = self._cambios.abiertos()
        if mod.mio.name not in abiertos and mod.mio.exists(): self._dia.orden(f'abrir "{mod.mio}"')
        for otro in self._curso.modulos:                   # los diagramas de otros módulos (de otra sesión): fuera, si están guardados
            if otro is not mod and otro.mio.name in abiertos and otro.mio.name != mod.mio.name:
                self._dia.orden(f"@{otro.mio.name} cerrar")    # sin «forzar»: con cambios sin guardar se queda
        self._preparado.add(mod.id)
        return aviso

    def _mover_dia(self):
        if self._turno():
            try: self._dia.mostrar_mio(self._mio().name)
            except Exception: pass
            return
        if not self._tiene_ejemplo(): return
        try:
            info = self._info_paso()
            self._dia.mostrar_paso(self._mod.archivo_paso(self._n), info, (self._paso().get("senalar") if isinstance(self._paso().get("senalar"), str) else None))
            if info.get("objetivos") and self._dia.version() >= VERSION_INTERFAZ:
                d = self._diagrama(); cajas = du.cajas_cm(d)
                norm = {du._norm(k): v for k, v in cajas.items()}
                self._dia.resaltar(self._en_vivo().name, [norm[du._norm(o)] for o in info["objetivos"] if du._norm(o) in norm])
        except Exception as e: print("mover Dia:", e, flush=True)

    def _guardar_progreso(self):
        if self.recordar: self._curso.guardar_progreso(self._m, self._n)

    def comprobar(self):
        """Botón «Comprobar» del «Tu turno». Con el plugin, primero mira si Dia tiene cambios sin guardar."""
        if not self._turno(): return {"revision": None}
        mio = self._mio()
        if self._dia.modo == "plugin":
            try: sin_guardar = self._dia.orden(f"@{mio.name} modificado").startswith("si")
            except Exception: sin_guardar = False      # un plugin viejo no conoce la orden: se revisa lo guardado
            if sin_guardar:
                return {"aviso": "Tienes cambios sin guardar en Dia: guarda tu diagrama (Ctrl+S) y vuelve a pulsar Comprobar."}
        if not self._revisar():
            return {"aviso": "No pude leer tu diagrama (quizá se estaba guardando). Vuelve a pulsar Comprobar."}
        try: self._huella = mio.stat().st_mtime_ns
        except FileNotFoundError: pass
        if self._marcas: self._quitar_marcas_dia(mio.name)
        self._vista, self._marcas = self._rev, []
        return {"revision": self._vista, "svg": self._svg()}

    def _salir_del_paso(self):
        self._gen += 1; self._senalar_extra = None; self._faltan = []
        self._overlay.borrar()
        self._marcas = []; self._vista = None

    def ir(self, n):
        self._salir_del_paso()
        self._n = max(0, min(len(self._mod.pasos) - 1, int(n)))
        if self._dia.modo == "plugin": self._quitar_marcas_dia(); self._mover_dia()
        elif self._proc_paso and self._proc_paso.poll() is None: cerrar_ventana(self._proc_paso.pid)   # el ejemplo del paso anterior
        self._revisar(); self._guardar_progreso()
        if self._dia.modo == "plugin" and self._paso().get("_interfaz"): threading.Thread(target=self._pintar_interfaz, daemon=True).start()
        return self._estado()

    def modulo(self, m):
        """El menú de módulos (y «Siguiente módulo»): arma sus pasos si hace falta, abre su diagrama y cierra el del anterior
        (si no tiene cambios sin guardar), y empieza en su paso 1."""
        m = max(0, min(len(self._curso.modulos) - 1, int(m)))
        if m == self._m: return self.ir(self._n)
        self._salir_del_paso()
        viejo = self._mio()
        if self._dia.modo == "plugin": self._quitar_marcas_dia()
        self._m, self._n = m, 0
        self._cambios.rutas["mio"] = self._mod.mio
        self._dia.mio = self._mod.mio
        self._huella, self._rev = None, None
        aviso = ""
        if self._dia.modo == "plugin":
            aviso = self._preparar_modulo()
            if viejo != self._mod.mio and viejo.name in self._cambios.abiertos():
                r = self._dia.orden(f"@{viejo.name} cerrar")       # sin «forzar»: si tiene cambios sin guardar, se queda abierta
                if not r.startswith("ok"): aviso = aviso or f"Dejé abierta la pestaña «{viejo.name}»: tiene cambios sin guardar."
            self._mover_dia()
        else:
            cu.crear_inicial(self._mod, 0)
        self._revisar(); self._guardar_progreso()
        if self._dia.modo == "plugin" and self._paso().get("_interfaz"): threading.Thread(target=self._pintar_interfaz, daemon=True).start()
        return self._estado(aviso)

    def boton(self, cual):
        if cual == "senalar": return self._senalar()
        if cual == "hazlo": return self._hazlo()
        if self._dia.modo == "plugin":
            self._mover_dia() if cual == "paso" else self._dia.mostrar_mio(self._mio().name)
            h, _ = self._dia.ventana()
            if h: al_frente(h)
            return {"ok": True}
        # Modo de antes: una ventana de Dia por archivo
        if cual == "paso":
            ruta = self._mod.archivo_paso(self._n)
            if self._proc_paso and self._proc_paso.poll() is None: cerrar_ventana(self._proc_paso.pid)
            self._proc_paso = subprocess.Popen([DIAW, "--integrated", str(ruta)]); return {"ok": True}
        mio = self._mio()
        h = ventana_de_dia(mio.name)
        if h: al_frente(h); return {"ok": True, "aviso": "Tu diagrama ya está abierto en Dia"}
        self._proc_mio = subprocess.Popen([DIAW, "--integrated", str(mio)]); return {"ok": True}

    def _senalar(self):
        """«Señálamelo en Dia»: trae Dia al frente y dibuja las flechas encima (y dice lo que aún no se ve)."""
        if self._dia.modo != "plugin": return {"ok": False, "aviso": "Sin el plugin no puedo señalar dentro de Dia."}
        if self._dia.version() < VERSION_INTERFAZ: return {"ok": False, "aviso": "Para las flechas en Dia hace falta el plugin nuevo: cierra Dia y vuelve a abrir el panel."}
        h, _ = self._dia.ventana()
        if h: al_frente(h)
        marcas = self._pintar_interfaz()
        if not marcas: return {"ok": False, "aviso": "Ahora no veo eso en Dia: " + "; ".join(self._faltan[:2]) if self._faltan else "No hay nada que señalar."}
        falta = f" (falta: {self._faltan[0]})" if self._faltan else ""
        return {"ok": True, "aviso": f"Mira Dia: te señalé {len(marcas)} cosa{'s' if len(marcas) != 1 else ''}{falta}."}

    def _hazlo(self):
        """«Hazlo por mí»: la acción del paso, delante de la persona (en el diagrama de la lección; en el «Tu turno», en el suyo
        y solo si lo confirma pulsando otra vez)."""
        p = self._paso(); h = p.get("_hazlo")
        if not h: return {"ok": False}
        if self._dia.modo != "plugin": return {"ok": False, "aviso": "Sin el plugin no puedo hacerlo en Dia."}
        if self._dia.version() < VERSION_INTERFAZ: return {"ok": False, "aviso": "Para «Hazlo por mí» hace falta el plugin nuevo: cierra Dia y vuelve a abrir el panel."}
        pestana = self._mio().name if self._turno() else self._en_vivo().name
        if self._turno() and time.time() - self._hazlo_pedido > 15:
            self._hazlo_pedido = time.time()
            return {"ok": False, "aviso": f"Esto lo hace en TU diagrama ({pestana}). Si quieres, pulsa otra vez «{h['etiqueta']}»."}
        self._hazlo_pedido = 0.0
        if not self._turno(): self._mover_dia()           # el ejemplo del paso, tal cual
        ventanas = None
        hechos = []
        for orden, espera in ui.ordenes_hazlo(h["hacer"], pestana, ui.leer_widgets(self._dia.orden("widgets"))):
            if orden.startswith("__herramienta__ "):
                tipo = orden.split(" ", 1)[1]
                _, w = ui._buscar(ui.leer_widgets(self._dia.orden("widgets")), lambda w: w.get("tipo") == tipo)
                orden = f'pulsar "{w["tip"]}"' if w and w.get("tip") else ""
            if orden:
                r = self._dia.orden(orden)
                hechos.append(r.splitlines()[-1] if r else "")
                if r.startswith("error"):
                    return {"ok": False, "aviso": f"No pude hacerlo en Dia: {r.splitlines()[-1][6:120]}"}
            if espera: time.sleep(espera)
        hw, _ = self._dia.ventana()
        if hw: al_frente(hw)
        self._senalar_extra = h.get("senalar") or None
        time.sleep(0.2)
        marcas = self._pintar_interfaz()
        return {"ok": True, "aviso": "Hecho: míralo en Dia." + (f" Te señalé {len(marcas)} cosa{'s' if len(marcas) != 1 else ''}." if marcas else "")}

    # ----- tutor -----
    def preguntar(self, pregunta, adjuntos=None):
        """adjuntos: capturas, PDF o textos que manda la página (formato en motor.mensaje)."""
        pregunta = (pregunta or "").strip()
        if not pregunta and not adjuntos: return {"texto": ""}
        pregunta = pregunta or "Mira lo que te adjunto."
        ctx = self._contexto()
        ref = cd.referencia_libre(pregunta, ctx)       # propiedades de los tipos de Dia del modo libre, solo si vienen al caso
        if ref: ctx += "\n" + ref
        if self._notas: ctx = "[Del panel] " + " ".join(self._notas) + "\n" + ctx; self._notas = []
        def trozo(t): self._empujar(f"window.trozoTutor({json.dumps(t)})")
        try: resp = self._tutor.preguntar(ctx, pregunta, trozo, adjuntos)
        except ValueError as e: return {"texto": str(e)}             # un adjunto que no se admite
        except Exception as e: return {"texto": f"No pude hablar con el tutor ({e}). Intenta otra vez."}
        texto, marcas = motor.separar(resp)
        texto, prop, error = cd.separar_acciones(texto)
        if marcas:
            self._marcas = marcas
            self._empujar(f"window.mostrarDiagrama({json.dumps(self._svg())})")
            self._marcas_en_dia(marcas)               # y también dentro de Dia, en la capa «Tutor»
        out = {"texto": texto, "marcas": len(marcas)}
        if prop:
            try:
                with self._cerrojo_cambios: out["propuesta"] = self._cambios.preparar(prop, bool(self._turno()))
            except ValueError as e: error = str(e)
            except Exception as e: out["propuesta_error"] = f"No pude leer Dia para preparar el cambio que propone ({e})."
        if error:
            out["propuesta_error"] = f"El tutor propuso un cambio que no se puede usar ({error}). Pídeselo otra vez."
            self._notas.append(f"Tu último bloque <acciones> no se pudo usar: {error}. Si hace falta, propón uno corregido.")
        return out

    def _contexto(self):
        """El [Estado actual] para el tutor: el módulo y el paso, la revisión, las pestañas de Dia y lo que hay EN PANTALLA en cada
        una (con el plugin, aunque no se haya guardado), y el ejercicio que armó."""
        p = self._paso()
        rev = f"\nRevisión automática (de lo guardado): {self._rev['mensaje']} ({self._rev['ok']} de {self._rev['total']} bien)" if self._turno() and self._rev else ""
        mods = f"Módulo {self._m + 1} de {len(self._curso.modulos)} («{self._mod.titulo}»). " if len(self._curso.modulos) > 1 else ""
        partes = [f"[Estado actual] {mods}Paso {self._n + 1} de {len(self._mod.pasos)}. El panel dice: {p['texto']}{rev}"]
        if self._faltan: partes.append("Lo que el panel no pudo señalar en Dia ahora: " + "; ".join(self._faltan[:3]))
        rutas = self._cambios.rutas
        try: abiertas = self._cambios.abiertos()
        except Exception: abiertas = []
        if abiertas: partes.append("Pestañas abiertas en Dia: " + ", ".join(abiertas))
        def texto_de(ruta, limite=60):
            try: d = self._cambios.leer_pantalla(ruta) if ruta.name in abiertas else du.leer(ruta)
            except Exception: return "(no se pudo leer)"
            lineas = du.texto(d).split("\n")
            return "\n".join(lineas[:limite] + (["…"] if len(lineas) > limite else []))
        mio = rutas["mio"]
        sin_guardar = " (con cambios sin guardar)" if mio.name in abiertas and self._cambios.modificado(mio.name) else ""
        if self._turno():
            partes.append(f"Su diagrama ({mio.name}, lo que hay en pantalla{sin_guardar}):\n{texto_de(mio)}")
        else:
            partes.append(f"Diagrama de ejemplo del paso ({rutas['leccion'].name}):\n{_sin_tutor(du.texto(self._diagrama()))}")
            partes.append(f"Su diagrama ({mio.name}{sin_guardar}):\n{texto_de(mio, 25)}")
        tuyos = sorted(f for f in abiertas if f not in (mio.name, rutas["leccion"].name) and (rutas["tutor"] / f).exists())
        for f in tuyos: partes.append(f"Tu diagrama «{f}» (lo creaste tú):\n{texto_de(rutas['tutor'] / f, 40)}")
        partes += self._cambios.contexto()
        return "\n".join(partes)

    # ----- cambios que propone el tutor: solo con permiso (Aplicar), y se pueden deshacer -----
    def _cambio(self, f, que):
        try:
            with self._cerrojo_cambios: tarjeta = f()
        except KeyError: return {"aviso": "Esa propuesta ya no existe (¿reiniciaste el panel?)."}
        except Exception as e: return {"aviso": f"No pude hablar con Dia ({e}). Intenta otra vez."}
        if tarjeta["estado"] in ("aplicada", "rechazada", "deshecha"):
            self._notas.append(f"La persona {que} tu propuesta «{tarjeta['resumen']}».")
        elif tarjeta["estado"] == "error":
            self._notas.append(f"Tu propuesta «{tarjeta['resumen']}» no se pudo aplicar: {tarjeta['mensaje']}")
        return {"propuesta": tarjeta, "tutor_ej": self._cambios.estado_ejercicio()}

    def aplicar(self, pid):
        """Botón «Aplicar» de la tarjeta de permiso."""
        return self._cambio(lambda: self._cambios.aplicar(pid), "APLICÓ")

    def rechazar(self, pid):
        """Botón «No»: no se toca nada."""
        return self._cambio(lambda: self._cambios.rechazar(pid), "NO aplicó")

    def deshacer(self, pid, forzar=False):
        """Botón «Deshacer» (con forzar=True, «Deshacer igual» cuando la persona cambió lo del tutor)."""
        return self._cambio(lambda: self._cambios.deshacer(pid, bool(forzar)), "DESHIZO")

    # ----- el ejercicio que armó el tutor: se revisa con su propio Comprobar, sin IA -----
    def comprobar_ejercicio(self):
        try:
            with self._cerrojo_cambios: rev, aviso = self._cambios.comprobar_ejercicio()
        except Exception as e: return {"tutor_ej": self._cambios.estado_ejercicio(), "aviso": f"No pude comprobar ({e})."}
        out = {"tutor_ej": self._cambios.estado_ejercicio()}
        if aviso: out["aviso"] = aviso
        return out

    def ir_ejercicio(self):
        try:
            ok = self._cambios.ir_ejercicio()
            h = ventana_de_dia(self._cambios.ejercicio["ruta"].name) if ok and self._cambios.ejercicio else None
            if h: al_frente(h)
            return {"ok": ok} if ok else {"ok": False, "aviso": "No encuentro el diagrama del ejercicio en Dia."}
        except Exception as e: return {"ok": False, "aviso": f"No pude ir al diagrama ({e})."}

    def quitar_ejercicio(self):
        self._cambios.quitar_ejercicio(); return {"tutor_ej": None}

    def borrar_marcas(self):
        """«Borrar marcas»: las quita del dibujo del panel y de Dia."""
        self._marcas = []; self._empujar(f"window.mostrarDiagrama({json.dumps(self._svg())})")
        self._quitar_marcas_dia(); return {"ok": True}

    def listo(self): print("ventana lista", flush=True); return True

    def restaurar(self, m, n):
        """Vuelve al módulo y al paso donde se quedó (progreso.json, junto al curso)."""
        self._m = max(0, min(len(self._curso.modulos) - 1, int(m)))
        self._n = max(0, min(len(self._mod.pasos) - 1, int(n)))
        self._cambios.rutas["mio"] = self._mod.mio
        self._dia.mio = self._mod.mio

    def cerrar(self):
        self._overlay.cerrar()


def abrir_ventana(api):
    """Una sola ventana, pegada a la derecha y a todo el alto del área visible, con las pestañas Lección y Tutor.
    Usa la página y la preferencia de tema del panel de Excel."""
    import webview
    import panel_web
    x0, y0, ancho, alto, _ = panel_web.area_visible(); ancho_v = 480
    tema = panel_web.preferencias().get("tema", "claro")
    pagina = (EXCEL / "panel.html").read_text(encoding="utf-8").replace(
        "<head>", f"<head><script>window.TEMA_PANEL = {json.dumps(tema)}; window.OBJETO_PANEL = 'diagrama'; window.APP_PANEL = 'Dia';</script>", 1)
    api._ventana = webview.create_window(api._curso.titulo or "Clase en vivo", html=pagina, js_api=api,
                                         width=ancho_v, height=int(alto), x=int(x0 + ancho - ancho_v), y=int(y0),
                                         on_top=True, min_size=(360, 300), background_color="#232631" if tema == "oscuro" else "#F8F6F1")


def probar_marcas(leccion):
    """--probar: marcas del tutor en Dia sin abrir ventanas (capa «Tutor» ignorada al leer, traducción
    de marcas a órdenes del plugin y qué órdenes manda el panel al preguntar, borrar y cambiar de paso)."""
    import tempfile
    ok = lambda c: "✔" if c else "✘"
    turno, p5 = leccion["pasos"][-1]["turno"], PASOS / "paso_5.dia"
    # 1) un .dia guardado con marcas puestas (capa «Tutor», incluso con una clase dentro) se lee igual
    capa = ('<dia:layer name="Tutor" visible="true">'
            '<dia:object type="Standard - Box" version="0" id="T0"><dia:attribute name="elem_corner"><dia:point val="1,1"/></dia:attribute></dia:object>'
            + du._clase_xml({"nombre": "Estudiante", "pos": (30, 30), "atributos": [{"nombre": "carnet", "tipo": "String", "vis": "-"}]}, 9)
            + '</dia:layer>')
    texto = p5.read_text(encoding="utf-8").replace("</dia:diagram>", capa + "</dia:diagram>")
    with tempfile.TemporaryDirectory() as tmp:
        con = Path(tmp) / "con_marcas.dia"; con.write_text(texto, encoding="utf-8")
        a, b = du.leer(p5), du.leer(con)
    print("Capa Tutor ignorada al leer:", ok(a == b and du.revisar(a, turno) == du.revisar(b, turno) and not b["otros"]),
          f"({len(b['clases'])} clase, otros={b['otros']})")
    # 2) marcas → órdenes del plugin (cajas de lo guardado; con plugin, las de pantalla)
    cajas = du.cajas_cm(a)
    filas_ok = abs(cajas["Libro.titulo"][1] - (cajas["Libro"][1] + 1.5)) < 1e-6 and abs(cajas["Libro.prestar"][1] - (cajas["Libro"][1] + 4.1)) < 1e-6
    pantalla = du.cajas_de_plugin("caja\tLibro\tUML - Class\t2.000\t2.000\t10.895\t6.600\nfila\tLibro\t\tnombre\t2\t2\t10.895\t1.4\n"
                                  "fila\tLibro\ttitulo\tatributo\t2.000\t3.500\t10.895\t0.800\nok cajas 1")
    print("Cajas en cm (filas):", ok(filas_ok), "· respuesta de «cajas» del plugin:", ok(pantalla == {"Libro": (2, 2, 10.895, 6.6), "Libro.titulo": (2, 3.5, 10.895, 0.8)}))
    marcas = [{"tipo": "marco", "objetivo": "Libro", "color": "azul"},
              {"tipo": "nota", "objetivo": "Libro.autor", "texto": 'debería ser "público"', "color": "rojo"},
              {"tipo": "flecha", "desde": "Libro.titulo", "hasta": "Libro.getTitulo", "texto": "mira", "color": "verde"},
              {"tipo": "nota", "objetivo": "NoExiste.x", "texto": "no sale"}]
    ordenes, n = du.ordenes_marcas(marcas, cajas, EN_VIVO.name)
    tipos = [o.split()[1] for o in ordenes]
    print("Marcas → órdenes:", ok(n == 3 and tipos == ["recuadro", "recuadro", "nota", "flecha", "nota"] and all(o.startswith(f"@{EN_VIVO.name} ") for o in ordenes)
                                  and "'público'" in ordenes[2] and ordenes[0].endswith("azul 0.1")), f"({n} de {len(marcas)} colocadas: {', '.join(tipos)})")
    # 3) el panel manda las órdenes a la pestaña que toca (Dia de mentira que anota lo que recibe)
    class DiaDePrueba(DiaEnVivo):
        def __init__(self): self.modo, self.motivo, self.listo, self.recibido = "plugin", "", threading.Event(), []; self.listo.set()
        def orden(self, texto): self.recibido += texto.splitlines(); return "ok"
    class TutorDePrueba:
        def preguntar(self, ctx, pregunta, al_trozo, adjuntos):
            return 'Mira autor.<marcas>[{"tipo": "nota", "objetivo": "Libro.autor", "texto": "privado", "color": "rojo"}]</marcas>'
    dia = DiaDePrueba(); api = Api(leccion, TutorDePrueba(), dia); api._n = 4
    t0 = time.time()
    while api._huella is None and time.time() - t0 < 5: time.sleep(0.05)   # primera vuelta de _vigilar
    r = api.preguntar("¿qué marco?")
    dib = [o for o in dia.recibido if " recuadro " in o or " nota " in o]
    print("Preguntar → marcas en Dia:", ok(r["marcas"] == 1 and dib and all(o.startswith(f"@{EN_VIVO.name} ") for o in dib) and "<marcas>" not in r["texto"]),
          f"({len(dib)} órdenes de dibujo en {EN_VIVO.name}; panel: {len(api._marcas)} marca)")
    dia.recibido = []; api.borrar_marcas()
    print("Borrar marcas → las dos pestañas:", ok(dia.recibido == [f"@{EN_VIVO.name} borrar_marcas", f"@{MIO.name} borrar_marcas"] and not api._marcas))
    dia.recibido = []; api.ir(len(leccion["pasos"]) - 1)
    print("Cambiar de paso → se borran en Dia:", ok(dia.recibido[:2] == [f"@{EN_VIVO.name} borrar_marcas", f"@{MIO.name} borrar_marcas"]))


def probar_cambios(leccion):
    """--probar: lo que el tutor crea o cambia en Dia, sin abrir ventanas (sin Dia, o con un Dia de mentira):
    validación del bloque <acciones>, el plan sobre un diagrama (nombres, colocación sin encimar), escribir y leer
    relaciones (ida y vuelta), Comprobar del ejercicio (bien y mal), el dibujo con relaciones y la tarjeta con un plugin viejo."""
    import tempfile
    ok = lambda c: "✔" if c else "✘"
    todo = []
    def ver(c, texto): todo.append(bool(c)); print(texto, ok(c))
    # 1) el bloque <acciones>
    bueno = ('Te propongo esto.<acciones>{"para": "ejemplo", "diagrama": "nuevo", "cambios": [{"clase": "Animal", "abstracta": true, '
             '"metodos": ["+hacerSonido(): void {abstract}"]}, {"clase": "Perro"}, {"interfaz": "Mascota", "metodos": ["+jugar(): void"]}, '
             '{"relacion": "herencia", "de": "Perro", "a": "Animal"}, {"relacion": "realizacion", "de": "Perro", "a": "Mascota"}, '
             '{"relacion": "composicion", "todo": "Animal", "parte": "Perro"}, {"nota": "Ejemplo", "junto_a": "Animal"}]}</acciones>')
    texto, prop, err = cd.separar_acciones(bueno)
    ver(prop and not err and texto == "Te propongo esto." and prop["cambios"][2]["metodos"][0]["abstracto"]
        and prop["cambios"][5]["de"] == "Perro" and prop["cambios"][5]["a"] == "Animal", "Bloque <acciones> válido (interfaz, todo/parte):")
    malos = {'{"cambios": [{"clase": "A", "color": "rojo"}]}': "campos que no conozco",
             '{"cambios": [{"relacion": "amistad", "de": "A", "a": "B"}]}': "desconocida",
             '{"cambios": [{"relacion": "herencia", "de": "A", "a": "B", "mult": ["1", "*"]}]}': "no lleva multiplicidades",
             '{"cambios": [{"interfaz": "I", "atributos": ["-x: int"]}]}': "no lleva atributos",
             '{"cambios": [{"clase": "Mi Clase"}]}': "no es un nombre",
             '{"cambios": [{"clase": "A", "metodos": ["-x: int"]}]}': "es un atributo",
             '{"diagrama": "C:/Windows/x.dia", "cambios": [{"clase": "A"}]}': "«diagrama» es"}
    fallos = [m for b, m in malos.items() if m not in (cd.separar_acciones(f"<acciones>{b}</acciones>")[2] or "")]
    _, _, e2 = cd.separar_acciones("<acciones>{\"cambios\": [{\"clase\": \"A\"}]}</acciones> y <acciones>{}</acciones>")
    _, _, e3 = cd.separar_acciones("hola <acciones>{\"cambios\": [")
    ver(not fallos and "más de un bloque" in (e2 or "") and "no se cerró" in (e3 or ""), f"Bloques inválidos rechazados ({len(malos) + 2} casos{', fallan: ' + str(fallos) if fallos else ''}):")
    # 2) el plan sobre el diagrama del paso 5 (Libro): nombres, renombrar, colocación sin encimar, hijas debajo del padre
    d5 = du.leer(PASOS / "paso_5.dia")
    _, p2, _ = cd.separar_acciones('<acciones>{"diagrama": "leccion", "cambios": [{"clase": "Autor", "atributos": ["-nombre: String"]}, '
                                   '{"modificar": "Libro", "nombre": "Obra", "agregar": ["-isbn: String"]}, {"relacion": "asociacion", "de": "Obra", "a": "Autor", "mult": ["*", "1..*"]}, '
                                   '{"clase": "Novela"}, {"clase": "Poema"}, {"relacion": "herencia", "de": "Novela", "a": "Obra"}, {"relacion": "herencia", "de": "Poema", "a": "Obra"}]}</acciones>')
    plan = cd.planear(p2, d5, "p9")
    cajas = [c["caja"] for c in d5["clases"]] + [(*c["pos"], *cd.caja_estimada(c)) for c in plan["nuevas"]]
    sin_encimar = all(not cd._choca(a, b, 0.5) for i, a in enumerate(cajas) for b in cajas[i + 1:])
    libro = d5["clases"][0]["caja"]; nov = next(c for c in plan["nuevas"] if c["nombre"] == "Novela")
    rel = plan["relaciones"][0]
    ver(sin_encimar and nov["pos"][1] > libro[1] + libro[3] and rel["ref_de"] == "clase:Obra" and rel["ref_a"] == "tag:p9.1"
        and list(plan["modificar"].values())[0][1]["nombre"] == "Obra", f"Plan: renombrar, colocar sin encimar, hijas debajo ({len(plan['nuevas'])} clases nuevas):")
    errores = []
    for b in ('{"cambios": [{"clase": "Libro"}]}', '{"cambios": [{"relacion": "herencia", "de": "X", "a": "Libro"}]}',
              '{"cambios": [{"modificar": "Libro", "quitar": ["noexiste"]}]}'):
        try: cd.planear(cd.separar_acciones(f"<acciones>{b}</acciones>")[1], d5, "p0"); errores.append(b)
        except ValueError: pass
    ver(not errores, "Plan: rechaza clase repetida, clase que no existe y miembro que no existe:")
    # 3) escribir y leer relaciones (ida y vuelta, con <dia:connections> de verdad)
    m = du.miembro
    clases = [{"nombre": "Animal", "pos": (2, 2), "abstracta": True, "metodos": [m("+hacerSonido(): void {abstract}")]},
              {"nombre": "Perro", "pos": (2, 12), "atributos": [m("-raza: String")]}, {"nombre": "Mascota", "pos": (20, 2), "estereotipo": "interface"},
              {"nombre": "Dueño", "pos": (20, 12)}, {"nombre": "Casa", "pos": (40, 12)}, {"nombre": "Collar", "pos": (2, 24)}]
    rels = [{"tipo": "herencia", "de": "Perro", "a": "Animal"}, {"tipo": "realizacion", "de": "Perro", "a": "Mascota"},
            {"tipo": "asociacion", "de": "Dueño", "a": "Perro", "nombre": "cuida", "mult": ["1", "*"], "direccion": "a"},
            {"tipo": "agregacion", "de": "Dueño", "a": "Casa", "mult": ["1..*", "1"]}, {"tipo": "composicion", "de": "Collar", "a": "Perro", "mult": ["1", "1"]},
            {"tipo": "dependencia", "de": "Dueño", "a": "Collar"}]
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "relaciones.dia"; du.escribir(f, clases, rels, [{"texto": "Una nota", "pos": (40, 2)}])
        d = du.leer(f)
    leidas = sorted((r["tipo"], r["de"], r["a"], tuple(r["mult"]), r["direccion"]) for r in d["relaciones"])
    esperadas = sorted((r["tipo"], r["de"], r["a"], tuple(r.get("mult", ["", ""])), r.get("direccion", "")) for r in rels)
    ver(leidas == esperadas and len(d["notas"]) == 1 and du.es_interfaz(d["clases"][2]) and d["clases"][0]["metodos"][0]["abstracto"],
        f"Escribir y leer relaciones (6 tipos, multiplicidades, dirección, nota, interfaz):")
    # 4) Comprobar del ejercicio del tutor (sin IA): bien y mal
    ej = cd._v_ejercicio({"clases": [{"nombre": "Perro", "atributos": ["-raza: String"]}, {"nombre": "Animal", "abstracta": True}],
                          "relaciones": [{"tipo": "herencia", "de": "Perro", "a": "Animal"}, {"tipo": "asociacion", "de": "Dueño", "a": "Perro", "mult": ["1", "*"]},
                                         {"tipo": "composicion", "de": "Collar", "a": "Perro"}]})
    rev = du.revisar_varios(d, ej)
    def variante(cambio):
        x = json.loads(json.dumps(d)); cambio(x); return du.revisar_varios(x, ej)
    sin_rel = variante(lambda x: x["relaciones"].pop(0))
    tipo_mal = variante(lambda x: x["relaciones"][4].update(tipo="agregacion"))
    al_reves = variante(lambda x: x["relaciones"][0].update(de="Animal", a="Perro"))
    mult_mal = variante(lambda x: x["relaciones"][2].update(mult=["1", "1"]))
    ver(rev["estado"] in ("bien", "casi") and rev["ok"] == rev["total"] and "Falta la herencia" in sin_rel["mensaje"]
        and "pusiste una agregación" in tipo_mal["mensaje"] and "al revés" in al_reves["mensaje"] and "multiplicidad junto a «Perro» debería ser *" in mult_mal["mensaje"],
        f"Comprobar del ejercicio: bien ({rev['ok']}/{rev['total']}, {rev['estado']}) y mal (falta, tipo, al revés, multiplicidad):")
    # 5) el dibujo del panel con relaciones
    s = du.svg(d)
    ver(all(f"url(#uml-{k})" in s for k in ("tri", "flecha", "rombo-v", "rombo-l")) and "stroke-dasharray" in s and "«interface»" in s and "cuida" in s,
        "Dibujo del panel con las puntas UML (triángulo, flecha, rombos, discontinua):")
    # 6) el panel con un Dia de plugin VIEJO: la tarjeta lo avisa y Aplicar no rompe nada
    class DiaViejo(DiaEnVivo):
        def __init__(self): self.modo, self.motivo, self.listo, self.recibido = "plugin", "", threading.Event(), []; self.listo.set()
        def orden(self, texto):
            self.recibido += texto.splitlines()
            return "ok" if texto.split()[-1] in ("borrar_marcas",) else f"error orden desconocida: {texto}"
    class TutorQuePropone:
        def preguntar(self, ctx, pregunta, al_trozo, adjuntos): self.ctx = ctx; return bueno
    dia, tutor = DiaViejo(), TutorQuePropone()
    with tempfile.TemporaryDirectory() as tmp:
        rutas = {"mio": MIO, "leccion": EN_VIVO, "tutor": Path(tmp) / "tutor"}
        api = Api(leccion, tutor, dia, rutas); api._n = 4
        r = api.preguntar("hazme un ejemplo")
        tarjeta = r.get("propuesta") or {}
        a = api.aplicar(tarjeta.get("id", "x"))
        ver(tarjeta.get("estado") == "pendiente" and any("plugin" in x for x in tarjeta.get("avisos", [])) and a["propuesta"]["estado"] == "error"
            and "vuelve a abrir el panel" in a["propuesta"]["mensaje"] and not any(" anadir " in o or o.startswith("abrir") for o in dia.recibido)
            and not list(Path(tmp).glob("tutor/*.dia")), "Plugin viejo: la tarjeta avisa y Aplicar no toca nada:")
        r2 = api.preguntar("otra vez")
        ver("[Del panel]" in tutor.ctx and "no se pudo aplicar" in tutor.ctx and "[Estado actual]" in tutor.ctx, "El tutor se entera de lo que pasó con su propuesta ([Del panel]):")
        api._cambios.borrar_temporales()
    print("Cambios del tutor en Dia:", "todo bien" if all(todo) else "HAY FALLOS")


def _conectar_sin_dia(ruta):
    """Solo para --probar: escribe en el archivo las conexiones que haría el plugin (meta conecta_inicio / conecta_fin con
    tag:ETIQUETA → <dia:connection> al objeto con esa etiqueta), para poder leer y revisar sin abrir Dia."""
    import re
    texto = Path(ruta).read_text(encoding="utf-8")
    ids = {m.group(2): m.group(1) for m in re.finditer(r'<dia:object type="[^"]+" version="\d+" id="([^"]+)">.*?name="tutor"><dia:string>#([^#]+)#', texto)}
    def poner(m):
        obj = m.group(0)
        con = ""
        for h, clave in ((0, "conecta_inicio"), (1, "conecta_fin")):
            r = re.search(rf'name="{clave}"><dia:string>#tag:([^#@]+)', obj)
            if r and r.group(1) in ids: con += f'<dia:connection handle="{h}" to="{ids[r.group(1)]}" connection="0"/>'
        if not con: return obj
        if re.search(r"<dia:connections\s*/>|<dia:connections></dia:connections>", obj):
            return re.sub(r"<dia:connections\s*/>|<dia:connections></dia:connections>", f"<dia:connections>{con}</dia:connections>", obj)
        return obj.replace("</dia:object>", f"<dia:connections>{con}</dia:connections></dia:object>")
    texto = re.sub(r'<dia:object type="[^"]+".*?</dia:object>', poner, texto, flags=re.S)
    Path(ruta).write_text(texto, encoding="utf-8")


def probar_diagramas(leccion):
    """--probar: los demás diagramas UML y el modo libre, sin ventanas: el bloque de cada tipo, el plan (colocado, sin líneas
    ortogonales de menos de 3 puntos, que cierran Dia), leer lo escrito como texto para el tutor, el Comprobar de ejercicios
    de casos de uso, secuencia y actividades (bien y con errores), rechazos del modo libre, la referencia a demanda,
    el dibujo real con marcas y la tarjeta con un plugin de la versión 3."""
    import copy, re, tempfile
    import dia_planes as dp
    todo = []
    def ver(c, texto): todo.append(bool(c)); print(texto, "✔" if c else "✘")
    P = {
        "casos": [{"sistema": "Cajero"}, {"actor": "Cliente"}, {"actor": "Banco", "lado": "derecha"}, {"caso": "Sacar dinero"}, {"caso": "Validar PIN"},
                  {"caso": "Imprimir recibo"}, {"relacion": "asociacion", "de": "Cliente", "a": "Sacar dinero"}, {"relacion": "include", "de": "Sacar dinero", "a": "Validar PIN"},
                  {"relacion": "extend", "de": "Imprimir recibo", "a": "Sacar dinero"}, {"relacion": "asociacion", "de": "Banco", "a": "Validar PIN"}],
        "secuencia": [{"participante": "Cliente", "como_actor": True}, {"participante": ":Cajero"}, {"participante": ":Banco"},
                      {"mensaje": "insertarTarjeta()", "de": "Cliente", "a": ":Cajero"}, {"mensaje": "validar(pin)", "de": ":Cajero", "a": ":Banco"},
                      {"mensaje": "ok", "de": ":Banco", "a": ":Cajero", "tipo": "retorno"}, {"mensaje": "registrar()", "de": ":Cajero", "a": ":Cajero"}],
        "actividades": [{"inicial": "inicio"}, {"accion": "Leer PIN"}, {"decision": "d1", "pregunta": "¿PIN correcto?"}, {"accion": "Dar dinero"}, {"accion": "Avisar"},
                        {"final": "fin"}, {"flujo": "", "de": "inicio", "a": "Leer PIN"}, {"flujo": "", "de": "Leer PIN", "a": "d1"},
                        {"flujo": "", "de": "d1", "a": "Dar dinero", "guarda": "sí"}, {"flujo": "", "de": "d1", "a": "Avisar", "guarda": "no"},
                        {"flujo": "", "de": "Dar dinero", "a": "fin"}, {"flujo": "", "de": "Avisar", "a": "Leer PIN"}],
        "estados": [{"inicial": "i"}, {"estado": "Apagado"}, {"compuesto": "Encendido"}, {"estado": "Calentando", "dentro_de": "Encendido", "hacer": "calentar"},
                    {"estado": "Listo", "dentro_de": "Encendido"}, {"transicion": "", "de": "i", "a": "Apagado"},
                    {"transicion": "encender", "de": "Apagado", "a": "Calentando"}, {"transicion": "", "de": "Calentando", "a": "Listo", "guarda": "t > 90"},
                    {"transicion": "apagar", "de": "Listo", "a": "Apagado", "efecto": "pitar()"}],
        "despliegue": [{"nodo": "Servidor", "estereotipo": "device"}, {"componente": "Web", "dentro_de": "Servidor"}, {"componente": "API", "dentro_de": "Servidor"},
                       {"interfaz_ofrecida": "IAPI", "de": "API"}, {"relacion": "dependencia", "de": "Web", "a": "API"}, {"paquete": "Modelo"},
                       {"clase": "Pedido", "dentro_de": "Modelo"}, {"objeto": "p1: Pedido", "valores": ["total = 10"]}],
        "libre": [{"crear": "Flowchart - Terminal", "texto": "Inicio"}, {"crear": "Flowchart - Diamond", "texto": "¿par?", "nombre": "p"},
                  {"crear": "Flowchart - Box", "texto": "Par", "props": {"fill_colour": "verde_claro"}}, {"crear": "ER - Entity", "texto": "Alumno"},
                  {"conectar": "Standard - Line", "de": "Inicio", "a": "p", "props": {"end_arrow": "triangulo"}},
                  {"conectar": "Standard - ZigZagLine", "de": "p", "a": "Par", "texto": "sí"}],
    }
    vacio = {"clases": [], "relaciones": [], "notas": [], "otros": [], "objetos": [], "lineas": []}
    leidos = {}
    with tempfile.TemporaryDirectory() as tmp:
        for k, cambios in P.items():
            _, prop, err = cd.separar_acciones("<acciones>" + json.dumps({"diagrama": "nuevo", "cambios": cambios}) + "</acciones>")
            plan = cd.planear(prop, vacio, "p1") if prop else None
            f = Path(tmp) / f"{k}.dia"
            if plan:
                du.escribir_para_anadir(f, plan["nuevas"], plan["relaciones"], plan["notas"], extra=plan["extra"], fondo=plan["fondo"])
                _conectar_sin_dia(f)
                leidos[k] = du.leer(f)
            texto = f.read_text(encoding="utf-8") if plan else ""
            cortas = [m for m in re.findall(r'<dia:attribute name="orth_points">(.*?)</dia:attribute>', texto) if m.count("<dia:point") < 3]
            ver(prop and not err and plan and texto.count("<dia:object") >= len(cambios) and not cortas and leidos.get(k),
                f"{k}: bloque válido, plan colocado y escrito ({texto.count('<dia:object')} objetos, {len(plan['poner']) if plan else 0} «poner»):")
    t = du.texto(leidos["casos"]) + du.texto(leidos["secuencia"]) + du.texto(leidos["actividades"]) + du.texto(leidos["estados"])
    ver(all(x in t for x in ("Actor «Cliente»", "Caso de uso «Sacar dinero»", "Límite del sistema «Cajero»", "«Sacar dinero» incluye a «Validar PIN»",
                             "Participante «:Cajero»", "1. Cliente → :Cajero: insertarTarjeta()", "(retorno)", "Decisión «d1»", "Flujo/transición: d1 → Dar dinero: [sí]",
                             "Estado «Calentando» (hacer: calentar)", "Estado compuesto «Encendido»", "apagar / pitar()")),
        "El [Estado actual] cuenta cualquier diagrama (actores, casos, include, mensajes en orden, decisiones, guardas, estados):")
    # Comprobar de ejercicios de los tipos nuevos: bien y tres errores de cada uno
    def r(d, e): return du.revisar_varios(d, cd._v_ejercicio(e))
    def var(d, f): x = copy.deepcopy(d); f(x); return x
    dc = leidos["casos"]
    Ec = {"objetos": [{"tipo": "actor", "nombre": "Cliente"}, {"tipo": "caso", "nombre": "Sacar dinero"}, {"tipo": "caso", "nombre": "Validar PIN"}],
          "conexiones": [{"tipo": "asociacion", "de": "Cliente", "a": "Sacar dinero"}, {"tipo": "include", "de": "Sacar dinero", "a": "Validar PIN"},
                         {"tipo": "extend", "de": "Imprimir recibo", "a": "Sacar dinero"}]}
    inc = lambda x: next(q for q in x["relaciones"] if q["tipo"] == "include")
    def girar(q): q["de_id"], q["a_id"] = q["a_id"], q["de_id"]
    def actor_a_caso(x): next(o for o in x["objetos"] if o["texto"] == "Cliente").update(kind="caso")
    rs = [r(dc, Ec), r(var(dc, lambda x: x["relaciones"].remove(inc(x))), Ec), r(var(dc, lambda x: inc(x).update(tipo="extend")), Ec),
          r(var(dc, lambda x: girar(inc(x))), Ec), r(var(dc, actor_a_caso), Ec)]
    ver(rs[0]["ok"] == rs[0]["total"] and "Falta un «include»" in rs[1]["mensaje"] and "pusiste un «extend»" in rs[2]["mensaje"]
        and "al revés" in rs[3]["mensaje"] and "debería ser actor" in rs[4]["mensaje"],
        f"Comprobar casos de uso: bien ({rs[0]['ok']}/{rs[0]['total']}) y mal (falta, include/extend, al revés, actor como caso):")
    ds = leidos["secuencia"]
    Es = {"mensajes": [{"de": "Cliente", "a": ":Cajero", "texto": "insertarTarjeta()"}, {"de": ":Cajero", "a": ":Banco", "texto": "validar"},
                       {"de": ":Banco", "a": ":Cajero", "texto": "ok", "tipo": "retorno"}]}
    m = lambda x, t: next(q for q in x["lineas"] if q["tipo"] == "UML - Message" and q["texto"].startswith(t))
    def orden(x): a, b = m(x, "validar"), m(x, "insertar"); a["y"], b["y"] = b["y"], a["y"]
    def reves(x): q = m(x, "validar"); q["de"], q["a"] = q["a"], q["de"]
    rs = [r(ds, Es), r(var(ds, orden), Es), r(var(ds, reves), Es), r(var(ds, lambda x: m(x, "ok")["extra"].update(mtipo=0)), Es)]
    ver(rs[0]["ok"] == rs[0]["total"] and "fuera de orden" in rs[1]["mensaje"] and "va al revés" in rs[2]["mensaje"] and "de retorno" in rs[3]["mensaje"],
        f"Comprobar secuencia: bien ({rs[0]['ok']}/{rs[0]['total']}) y mal (orden, al revés, retorno como síncrono):")
    da = leidos["actividades"]
    Ea = {"objetos": [{"tipo": "inicial"}, {"tipo": "accion", "nombre": "Leer PIN"}, {"tipo": "decision"}, {"tipo": "final"}],
          "conexiones": [{"tipo": "flujo", "de": "inicio", "a": "Leer PIN"}, {"tipo": "flujo", "de": "decision", "a": "Dar dinero", "guarda": "sí"},
                         {"tipo": "flujo", "de": "decision", "a": "Avisar", "guarda": "no"}, {"tipo": "flujo", "de": "Dar dinero", "a": "fin"}]}
    fl = lambda x, g: next(q for q in x["lineas"] if q["tipo"] == "UML - Transition" and q["extra"].get("guarda") == g)
    rs = [r(da, Ea), r(var(da, lambda x: fl(x, "no")["extra"].update(guarda="")), Ea), r(var(da, lambda x: x["lineas"].remove(fl(x, "sí"))), Ea),
          r(var(da, lambda x: girar(fl(x, "no"))), Ea)]
    ver(rs[0]["ok"] == rs[0]["total"] and "la guarda debería ser «no»" in rs[1]["mensaje"] and "Falta el flujo" in rs[2]["mensaje"] and "al revés" in rs[3]["mensaje"],
        f"Comprobar actividades: bien ({rs[0]['ok']}/{rs[0]['total']}) y mal (guarda vacía, falta un flujo, al revés):")
    # rechazos del modo libre y de los otros diagramas
    malos = {'{"cambios": [{"crear": "Flowchart - Cohete", "texto": "x"}]}': "no existe en Dia",
             '{"cambios": [{"crear": "Flowchart - Box", "texto": "x", "props": {"color_magico": 1}}]}': "no tiene la propiedad",
             '{"cambios": [{"crear": "Standard - Image", "nombre": "i"}]}': "usa un archivo",
             '{"cambios": [{"crear": "Flowchart - Box", "texto": "x", "props": {"fill_colour": "verdoso"}}]}': "es un color",
             '{"cambios": [{"crear": "Standard - Line", "nombre": "l"}]}': "es una línea",
             '{"cambios": [{"mensaje": "x", "de": "A", "a": "B", "tipo": "raro"}]}': "«tipo» del mensaje",
             '{"cambios": [{"decision": ""}]}': "ponle un nombre corto"}
    fallos = [mm for b, mm in malos.items() if mm not in (cd.separar_acciones(f"<acciones>{b}</acciones>")[2] or "")]
    ver(not fallos, f"Rechazos (tipo y propiedad que no existen, archivo, valor, línea como objeto, tipo de mensaje, decisión sin nombre){': ' + str(fallos) if fallos else ''}:")
    ver(cd.referencia_libre("hazme un diagrama de flujo", "") and "Flowchart - Box" in cd.referencia_libre("hazme un diagrama de flujo", "")
        and not cd.referencia_libre("hazme un ejemplo de herencia", "Clase «Animal»") and "OTROS DIAGRAMAS" in REGLAS_DIA,
        "Referencia del modo libre solo cuando hace falta; REGLAS con los otros diagramas:")
    # el dibujo del panel: el SVG de Dia con las marcas encima, en las mismas coordenadas (cm × 20)
    falso = '<svg width="10cm" height="5cm" viewBox="38 38 200 100" xmlns="http://www.w3.org/2000/svg"><g><ellipse cx="80" cy="60" rx="40" ry="20"/></g></svg>'
    s = do.svg_con_marcas(falso, {"Sacar dinero": (2, 2, 4, 2)}, [{"tipo": "nota", "objetivo": "Sacar dinero", "texto": "aquí", "color": "rojo"}],
                          {"puntos": [{"ok": False, "objetivo": "Sacar dinero", "texto": "x"}]})
    ver('<ellipse cx="80"' in s and 'x="36.0" y="36.0" width="88.0" height="48.0"' in s and "✘" in s and "aquí" in s,
        "Dibujo del panel: el de Dia con las marcas y la revisión encima, en su sitio:")
    # un Dia con el plugin de la versión 3: la tarjeta avisa y no se aplica
    class DiaV3(DiaEnVivo):
        def __init__(self): self.modo, self.motivo, self.listo, self.recibido = "plugin", "", threading.Event(), []; self.listo.set()
        def orden(self, texto):
            self.recibido += texto.splitlines()
            return "ok version 3" if texto == "version" else "  C:/x/mi_diagrama.dia\nok ventanas" if texto == "ventanas" else "ok"
    cam = cd.Cambios(DiaV3(), {"mio": MIO, "leccion": EN_VIVO, "tutor": Path(tempfile.mkdtemp()) / "tutor"})
    _, prop, _ = cd.separar_acciones("<acciones>" + json.dumps({"cambios": P["casos"]}) + "</acciones>")
    t = cam.preparar(prop); a = cam.aplicar(t["id"])
    ver(any("versión nueva del plugin" in x for x in t["avisos"]) and a["estado"] == "error" and not any(" anadir " in o for o in cam.dia.recibido),
        "Plugin de la versión 3 abierto: la tarjeta avisa y Aplicar no toca nada:")
    cam.borrar_temporales()
    print("Otros diagramas y modo libre:", "todo bien" if all(todo) else "HAY FALLOS")


# ---------- Pruebas de los cursos y de la Fase 2 (sin ventanas) ----------
WIDGETS_MUESTRA = """ventana x=9 y=38 w=1920 h=991 titulo="leccion.dia (C:/x) - diaw.exe" hwnd="1001" rol="dia-main-window"
widget GtkImageMenuItem x=218 y=39 w=66 h=26 texto="Objetos" tipo="" tip=""
widget GtkRadioButton x=10 y=101 w=39 h=36 texto="" tipo="" tip="Modificar objeto(s)" activo
widget DiaDynamicMenu x=10 y=253 w=155 h=30 texto="UML" tipo="" tip=""
widget GtkRadioButton x=12 y=285 w=32 h=32 texto="" tipo="UML - Class" tip="Clase"
widget GtkRadioButton x=44 y=285 w=32 h=32 texto="" tipo="UML - Class" tip="Plantilla de clase"
widget GtkRadioButton x=12 y=381 w=32 h=32 texto="" tipo="UML - Actor" tip="Actor"
pestana 0 x=170 y=106 w=148 h=22 texto="" activa
ventana x=581 y=286 w=793 h=570 titulo="Propiedades: UML - Class" hwnd="2002" rol="properties_window"
pestana 0 x=598 y=305 w=37 h=20 texto="Clase"
pestana 1 x=643 y=303 w=63 h=22 texto="Atributos" activa
pestana 2 x=714 y=305 w=85 h=20 texto="Operaciones"
widget GtkButton x=1286 y=340 w=64 h=30 texto="Nuevo" tipo="" tip=""
widget GtkEntry x=698 y=573 w=640 h=28 texto="" tipo="" tip=""
widget GtkLabel x=617 y=577 w=81 h=20 texto="Tipo:" tipo="" tip=""
widget GtkEntry x=698 y=541 w=640 h=28 texto="" tipo="" tip=""
widget GtkLabel x=617 y=545 w=81 h=20 texto="Nombre:" tipo="" tip=""
widget GtkButton x=1100 y=819 w=85 h=30 texto="Cerrar" tipo="" tip=""
ok widgets"""


def probar_fase2():
    """--probar: «En Dia: dónde se hace» (widgets → marcas del overlay, su dibujo), «hazlo por mí» y los arreglos del último
    informe (mensajes insertados entre dos, líneas que saltan capas, rótulos «include»/«extend»), todo sin Dia."""
    import copy
    import dia_planes as dp
    todo = []
    def ver(c, texto): todo.append(bool(c)); print(texto, "✔" if c else "✘")
    # 1) widgets → marcas (con la ventana a la que pertenece cada cosa)
    vs = ui.leer_widgets(WIDGETS_MUESTRA)
    marcas, faltan = ui.resolver([{"herramienta": "UML - Class", "tip": "Clase"}, {"pestana": "Atributos"}, {"boton": "Nuevo"},
                                  {"campo": "Nombre"}, {"herramienta": "Flowchart - Box"}, {"boton": "Borrar todo"},
                                  {"objeto": "Libro"}], vs, lambda n: (300, 200, 120, 80) if n == "Libro" else None)
    r = {m["texto"]: (m["hwnd"], m["rect"], m.get("n")) for m in marcas}
    ver(r.get("Herramienta «Clase»") == (1001, [12, 285, 32, 32], 1) and r.get("Pestaña «Atributos»") == (2002, [643, 303, 63, 22], 2)
        and r.get("Botón «Nuevo»") == (2002, [1286, 340, 64, 30], 3) and r.get("Campo «Nombre»") == (2002, [698, 541, 640, 28], 4)
        and r.get("Elige la hoja «Flowchart»", (0, 0, 0))[0] == 1001 and r.get("«Libro»") == (1001, [300, 200, 120, 80], 7)
        and len(faltan) == 1 and "Borrar todo" in faltan[0],
        f"Interfaz → marcas: herramienta, pestaña y botón del diálogo, campo por su etiqueta, hoja si la herramienta no se ve, objeto del diagrama ({len(marcas)} marcas, 1 falta):")
    malos = [([{"pestana": "A", "boton": "B"}], "UNA de"), ([{"menu": ""}], "es un texto"), ([{"boton": "X", "color": "morado"}], "«color»")]
    errs = []
    for lista, esperado in malos:
        try: ui.validar_interfaz(lista, "paso 1"); errs.append(esperado)
        except ValueError as e:
            if esperado not in str(e): errs.append(str(e))
    try: ui.validar_hazlo({"hacer": [{"accion": "FileSave"}]}, "paso 1"); errs.append("FileSave")
    except ValueError as e:
        if "no está permitida" not in str(e): errs.append(str(e))
    ords = ui.ordenes_hazlo([{"propiedades": "Libro"}, {"pulsar": "Operaciones"}, {"herramienta": "UML - Actor"}, {"herramienta": "Flowchart - Box"}], "leccion.dia", vs)
    o = [x for x, _ in ords]
    ver(not errs and o[0] == "@leccion.dia activar" and o[1] == '@leccion.dia seleccionar "nombre:Libro"' and o[2] == "accion ObjectsProperties"
        and o[3] == 'pulsar "Operaciones"' and o[4] == 'pulsar "Actor"' and o[5] == 'hoja "Flowchart"' and o[6].startswith("__herramienta__"),
        f"«Hazlo por mí» → órdenes (activar la pestaña, Propiedades, pestaña, herramienta; hoja si no se ve) y rechazos{': ' + str(errs) if errs else ''}:")
    # 2) el dibujo del overlay: notas sin tapar otros botones y dentro de la ventana
    try:
        import overlay_dia as ov
        if ov.Image is None: raise ImportError
        locales = [{"r": (3, 247, 35, 279), "texto": "1. Herramienta «Clase»", "color": "azul", "evitar": [(35, 247, 67, 279), (67, 247, 99, 279), (3, 279, 35, 311)]}]
        img, dxy = ov.componer(locales, 1920, 991, 1.25)
        ver(img is not None and img.size[0] > 100 and dxy[0] >= 0 and img.getpixel((5, 5))[3] == 0, f"Dibujo del overlay (Pillow, alfa por píxel, {img.size if img else None}):")
    except ImportError:
        ver(False, "Dibujo del overlay: falta Pillow (python -m pip install pillow):")
    # 3) un mensaje entre dos que ya estaban: la secuencia se vuelve a trazar en el orden nuevo
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "base.dia"
        prop = cd.validar_propuesta({"cambios": [{"participante": "A", "como_actor": True}, {"participante": ":B"}, {"participante": ":C"},
                                                {"mensaje": "uno()", "de": "A", "a": ":B"}, {"mensaje": "dos()", "de": ":B", "a": ":C"},
                                                {"mensaje": "listo", "de": ":C", "a": ":B", "tipo": "retorno"}]})
        du.escribir(f, []); cu.aplicar_offline(f, cu._plan(None, prop, du.leer(f), "p1", False), f)
        d0 = du.leer(f)
        ins = cd.validar_propuesta({"cambios": [{"mensaje": "medio()", "de": ":B", "a": "A", "despues_de": "uno()"}]})
        plan = cu._plan(None, ins, d0, "p2", False)
        cu.aplicar_offline(f, plan, Path(tmp) / "b.dia"); d1 = du.leer(Path(tmp) / "b.dia")
        orden = [m["texto"] for m in do.mensajes_en_orden(d1)]
        vidas = [o for o in d1["objetos"] if o["tipo"] == "UML - Lifeline"]
        sueltos = [m for m in do.mensajes_en_orden(d1) if not m.get("de") or not m.get("a")]
        tipos = [m["extra"].get("mtipo") for m in do.mensajes_en_orden(d1)]
        al_final = cu._plan(None, cd.validar_propuesta({"cambios": [{"mensaje": "fin()", "de": ":B", "a": "A", "despues_de": "listo"}]}), d0, "p3", False)
    ver(orden == ["uno()", "medio()", "dos()", "listo"] and len(vidas) == 3 and not sueltos and tipos[-1] == 4 and len(plan["quitar"]) == 6
        and not al_final["quitar"],
        f"Mensaje entre dos (despues_de): orden {orden}, {len(vidas)} líneas de vida, sin extremos sueltos; al final, sin rehacer:")
    try: cu._plan(None, cd.validar_propuesta({"cambios": [{"mensaje": "x", "de": ":B", "a": "A", "antes_de": "noexiste"}]}), d0, "p4", False); mal = True
    except ValueError as e: mal = "no hay un mensaje" not in str(e)
    ver(not mal, "Mensaje con un «antes_de» que no existe: rechazado:")
    # 4) una línea que salta varias capas no cruza lo que hay en medio
    vacio = {"clases": [], "relaciones": [], "notas": [], "otros": [], "objetos": [], "lineas": []}
    act = cd.validar_propuesta({"cambios": [{"inicial": "inicio"}, {"accion": "Leer"}, {"accion": "Pensar"}, {"accion": "Escribir"}, {"final": "fin"},
                                           {"flujo": "", "de": "inicio", "a": "Leer"}, {"flujo": "", "de": "Leer", "a": "Pensar"},
                                           {"flujo": "", "de": "Pensar", "a": "Escribir"}, {"flujo": "", "de": "Leer", "a": "Escribir", "guarda": "rápido"},
                                           {"flujo": "", "de": "Escribir", "a": "fin"}]})
    plan = cd.planear(act, vacio, "p5")
    with tempfile.TemporaryDirectory() as tmp:
        f = Path(tmp) / "a.dia"; du.escribir(f, []); cu.aplicar_offline(f, plan, f); da = du.leer(f)
    cajas = {o["texto"]: o["caja"] for o in da["objetos"] if o["kind"] == "accion"}
    salto = next(l for l in da["lineas"] if l["tipo"] == "UML - Transition" and l["extra"].get("guarda") == "rápido")
    pts = salto["puntos"]; P = cajas["Pensar"]
    cruza = any(min(a[0], b[0]) < P[0] + P[2] - 0.05 and max(a[0], b[0]) > P[0] + 0.05 and min(a[1], b[1]) < P[1] + P[3] - 0.05 and max(a[1], b[1]) > P[1] + 0.05
                for a, b in zip(pts, pts[1:]))
    ver(not cruza and len(pts) >= 4, f"Flujo que salta una capa (Leer → Escribir) rodea «Pensar» ({len(pts)} puntos):")
    # 5) «include» / «extend»: el tramo del medio pegado a la caja de la izquierda (el rótulo queda en el hueco)
    cas = cd.validar_propuesta({"cambios": [{"sistema": "S"}, {"actor": "Cliente"}, {"caso": "Sacar dinero"}, {"caso": "Validar PIN"}, {"caso": "Imprimir recibo"},
                                           {"relacion": "asociacion", "de": "Cliente", "a": "Sacar dinero"}, {"relacion": "include", "de": "Sacar dinero", "a": "Validar PIN"},
                                           {"relacion": "extend", "de": "Imprimir recibo", "a": "Sacar dinero"}]})
    plan = cd.planear(cas, vacio, "p6")
    rels = {r["tipo"]: r for r in plan["relaciones"]}
    ok5 = True
    for t in ("include", "extend"):
        pts = rels[t]["_ruta"][0]; xs = sorted({round(p[0], 2) for p in pts})
        izq = min(pts[0][0], pts[-1][0])
        medio = pts[1][0] if len(pts) == 4 else None
        ok5 = ok5 and medio is not None and medio - izq < 1.0
    ver(ok5, "«include» y «extend»: el rótulo va junto a la caja de la izquierda, sin rozar la de la derecha:")
    # 6) «Hazlo por mí» en el «Tu turno» toca SU diagrama: primero pide confirmación (pulsar otra vez); en un paso, va a la lección
    class DiaV5(_SinDia):
        def version(self): return 5
        def orden(self, texto):
            self.recibido += texto.splitlines()
            return WIDGETS_MUESTRA if texto == "widgets" else "ok"
    with tempfile.TemporaryDirectory() as tmp:
        mod = {"titulo": "M", "pasos": [{"texto": "a", "cambios": [{"clase": "Libro"}], "hazlo": {"hacer": [{"propiedades": "Libro"}, {"pulsar": "Atributos"}]}},
                                         {"texto": "t", "hazlo": {"etiqueta": "Ábrela por mí", "hacer": [{"propiedades": "Libro"}]},
                                          "turno": {"clases": [{"nombre": "Libro"}]}}]}
        (Path(tmp) / "m.json").write_text(json.dumps(mod), encoding="utf-8")
        (Path(tmp) / "curso.json").write_text(json.dumps({"titulo": "C", "modulos": ["m.json"]}), encoding="utf-8")
        c = cu.Curso(Path(tmp) / "curso.json"); cu.construir(c.modulos[0])
        dia = DiaV5("plugin"); api = Api(c, None, dia)
        dia.recibido = []; r0 = api._hazlo()
        en_leccion = [o for o in dia.recibido if "seleccionar" in o or "accion" in o or "pulsar" in o]
        api._n = 1; dia.recibido = []
        r1 = api._hazlo(); n1 = [o for o in dia.recibido if "accion" in o]
        r2 = api._hazlo(); n2 = [o for o in dia.recibido if "accion" in o or "seleccionar" in o]
    ver(r0["ok"] and en_leccion and all(o.startswith("@clase_en_vivo.dia") for o in en_leccion if "seleccionar" in o) and "pulsar" in " ".join(en_leccion)
        and not r1["ok"] and "pulsa otra vez" in r1["aviso"] and not n1 and r2["ok"] and any("@mi_m.dia seleccionar" in o for o in n2),
        "«Hazlo por mí»: en un paso, sobre la lección; en el «Tu turno», en el suyo y solo al pulsar otra vez:")
    print("Fase 2 y arreglos:", "todo bien" if all(todo) else "HAY FALLOS")
    return all(todo)


class _SinDia:
    """Para las pruebas: un panel sin Dia (modo de respaldo) o con un Dia de mentira (modo plugin, anota las órdenes)."""
    def __init__(self, modo="ventanas"):
        self.modo, self.motivo, self.listo, self.recibido, self.mio = modo, "", threading.Event(), [], MIO; self.listo.set()
    def orden(self, texto): self.recibido += texto.splitlines(); return "ok"
    def version(self): return 0
    def mostrar_paso(self, *a, **k): return "ok"
    def mostrar_mio(self, *a, **k): return "ok"
    def resaltar(self, *a, **k): pass
    def borrar_marcas(self, *a, **k): return ""
    def ventana(self): return None, None


def probar_curso(curso):
    """--probar de un curso: sobre una COPIA (la carpeta del curso no se toca), arma los pasos de cada módulo sin Dia, enseña su
    texto y su diagrama, revisa cada «Tu turno» con la solución y con cada error típico, y prueba el menú de módulos, los botones del
    paso y el progreso."""
    import shutil
    todo = []
    def ver(c, texto): todo.append(bool(c)); print(texto, "✔" if c else "✘")
    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "curso"
        shutil.copytree(curso.carpeta, copia, ignore=shutil.ignore_patterns("pasos", "mis_diagramas", "tutor", "progreso.json", "__pycache__"))
        c = cu.Curso(copia / curso.ruta.name)
        print(f"Curso «{c.titulo}»: {len(c.modulos)} módulos")
        for k, m in enumerate(c.modulos, 1):
            ind = cu.construir(m)
            print(f"== Módulo {k}: {m.titulo} ({m.id}, su diagrama: {m.mio.name}; {len(m.pasos)} pasos)")
            for n, p in enumerate(m.pasos):
                info = ind["pasos"][n]
                extra = [x for x in (("interfaz: " + ", ".join(next(iter(o.items()))[1] for o in p["_interfaz"])) if p.get("_interfaz") else "",
                                     f"hazlo: {p['_hazlo']['etiqueta']}" if p.get("_hazlo") else "", "TU TURNO" if p.get("_turno") else "") if x]
                print(f"  [{n + 1}] {p.get('titulo', '')}: {p['texto'][:70]}…" + (f"  ({'; '.join(extra)})" if extra else ""))
                if p.get("_cambios"):
                    print("       nuevo: " + ", ".join(info["objetivos"]))
                    lineas = _sin_tutor(du.texto(du.leer(m.archivo_paso(n)))).split("\n")
                    print("       " + "\n       ".join(lineas[-6:]))
            ver(all(m.archivo_paso(n).exists() for n in range(len(m.pasos))) and all(i["objetivos"] for i, p in zip(ind["pasos"], m.pasos) if p.get("_cambios")),
                f"  Pasos armados (se suman) y lo nuevo de cada paso para resaltar:")
            for n, p in enumerate(m.pasos):
                t = p.get("_turno")
                if not t: continue
                cu.crear_inicial(m, n)
                base = m.mio if t.get("_inicial") else None
                if t.get("_inicial"): print(f"       su diagrama empieza con: {', '.join(du.texto(du.leer(m.mio)).split(chr(10))[:6])}")
                if t.get("_solucion"):
                    r = cu.revisar_turno(cu.diagrama_de(t["_solucion"], base), t)
                    ver(r["ok"] == r["total"] and r["estado"] in ("bien", "casi"), f"  Tu turno, la solución: {r['estado']} {r['ok']}/{r['total']} «{r['mensaje'][:60]}»:")
                for i, e in enumerate(t["_errores"], 1):
                    if not e.get("_prueba"): print(f"  Error típico {i}: sin «prueba», no se comprueba"); continue
                    r = cu.revisar_turno(cu.diagrama_de(e["_prueba"], base), t)
                    ver(r.get("error_tipico") == i and r["mensaje"] == e["dice"], f"  Error típico {i}: «{r['mensaje'][:70]}…»:")
                # Comprobar en el panel: antes «sin comprobar», con la solución «bien»
                api = Api(c, None, _SinDia()); api._m, api._n = k - 1, n; api._cambios.rutas["mio"] = m.mio
                antes = api._estado()["revision"]["estado"]
                if t.get("_solucion"):
                    with tempfile.TemporaryDirectory() as t2:
                        f = Path(t2) / "s.dia"; shutil.copyfile(base, f) if base else du.escribir(f, [])
                        cu.aplicar_offline(f, cu._plan(None, t["_solucion"], du.leer(f), "x1", False), m.mio)
                    despues = api.comprobar()["revision"]["estado"]
                    ver(antes == "pendiente" and despues in ("bien", "casi"), f"  Botón Comprobar: antes {antes} → con la solución {despues}:")
        # el menú de módulos, los botones del paso y el progreso
        api = Api(c, None, _SinDia("plugin")); api.recordar = True
        e = api._estado()
        e2 = api.modulo(1)
        p1 = cu.leer_json(c.progreso_ruta)
        e3 = api.ir(3)
        api2 = Api(c, None, _SinDia()); api2.restaurar(*c.progreso())
        bot = {b["id"] for b in api.modulo(0)["botones"]}
        ver(len(e["modulos"]) == len(c.modulos) and e["m"] == 0 and e2["m"] == 1 and e2["n"] == 0 and p1 == {**p1, "m": 1, "n": 0}
            and (api2._m, api2._n) == (1, 3) and api2._mio().name == c.modulos[1].mio.name and {"paso", "senalar", "hazlo"} <= bot,
            f"Menú de módulos, «Siguiente módulo», progreso (vuelve al módulo 2, paso 4) y botones del paso ({', '.join(sorted(bot))}):")
        # errores claros para quien escribe un curso
        malos = {"pasos": [{"texto": "x", "cambios": [{"clase": "A"}], "diagrama": []}]}, {"pasos": [{"texto": "x", "raro": 1}]}, \
                {"pasos": [{"texto": "x", "turno": {"conexiones": [{"tipo": "include", "de": "A", "a": "B"}], "errores": [{"dice": "y"}]}}]}, \
                {"pasos": [{"texto": "x", "interfaz": [{"pestana": "A", "boton": "B"}]}]}
        msgs = []
        for d in malos:
            try: cu.validar_modulo(dict(d, titulo="M"), "m.json"); msgs.append("(no falló)")
            except ValueError as x: msgs.append(str(x))
        ver(all("(no falló)" not in x for x in msgs), "Módulos mal escritos: errores claros (" + " | ".join(x[:55] for x in msgs) + "):")
    print("Curso de Dia:", "todo bien" if all(todo) else "HAY FALLOS")
    return all(todo)


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ruta = Path(args[0]).resolve() if args else LECCION
    try: curso = cu.Curso(ruta)
    except (OSError, ValueError, KeyError) as e: sys.exit(f"No puedo abrir el curso {ruta}: {e}")
    if "--probar" in sys.argv:
        if args:
            ok = probar_curso(curso)
        else:                                          # el ejemplo de siempre (el módulo «La clase») y todo lo del tutor
            leccion = curso.modulos[0].d
            preparar(curso)
            for i, p in enumerate(curso.modulos[0].pasos):
                print(f"[{i + 1}] {p.get('titulo', '')}: {p['texto'][:80]}…")
                if p.get("diagrama"): print("     " + du.texto(du.leer(PASOS / f"paso_{i + 1}.dia")).replace("\n", "\n     "))
            print("mi_diagrama.dia:", cu.revisar_turno(du.leer(MIO), curso.modulos[0].pasos[-1]["_turno"])["mensaje"])
            api = Api(curso, None, _SinDia()); api._n = len(curso.modulos[0].pasos) - 1
            antes, despues = api._estado()["revision"]["estado"], api.comprobar()["revision"]["estado"]
            print(f"Botón Comprobar: antes {antes} → al pulsar {despues}", "✔" if antes == "pendiente" and despues != "pendiente" else "✘")
            probar_marcas(leccion)
            probar_cambios(leccion)
            probar_diagramas(leccion)
            probar_fase2()
    else:
        import webview
        preparar(curso)
        m, n = curso.progreso()
        dia = DiaEnVivo(); threading.Thread(target=dia.arrancar, args=(curso.en_vivo, curso.modulos[m].mio), daemon=True).start()
        tutor = TutorDia(curso); tutor.calentar()
        api = Api(curso, tutor, dia); api.restaurar(m, n); api.recordar = True
        abrir_ventana(api)
        webview.start(gui="edgechromium")
        api.cerrar(); tutor.cerrar()
        print(f"Dia: modo {dia.modo}{' (' + dia.motivo + ')' if dia.motivo else ''}. Dia queda abierto: tiene tu diagrama.", flush=True)
