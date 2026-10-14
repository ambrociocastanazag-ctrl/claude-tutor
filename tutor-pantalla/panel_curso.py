"""Panel de un curso de una app sin API (modo curso de tutor-pantalla): Lección | Tutor, como los de Excel y Dia.

  python tutor-pantalla/panel_curso.py <curso.json>             abre el panel (y la app, si se pulsa «Abrir»)
  python tutor-pantalla/panel_curso.py <curso.json> --probar    sin ventanas ni IA: el curso, cada «Tu turno» con su
                                                                solución y sus errores típicos; con la app abierta,
                                                                además, que cada «senalar» se encuentre en ella

La página es la de los tutores (../panel-excel/panel.html) con los ojos (ojos_ui.js).
- «Señálamelo en <app>»: busca por nombre (UI Automation) cada control del paso y pone flechas encima de la app.
  Leer los nombres no manda nada a nadie: no hace falta la vista previa.
- «Comprobar»: revisa sin IA lo que el turno pide ("pide"); si además lleva "tutor", abre la vista previa de la app
  y el tutor mira la captura que la persona adjunta (bien / casi / revisa).
- Tutor: conoce el curso, recibe el estado de la app EN TEXTO (lo activo, valores; nunca el botón de la cuenta) y marca
  encima de la app por nombre o, con una captura adjunta, por caja."""
import json, os, re, sys, time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EXCEL = AQUI.parent / "panel-excel"
sys.path.insert(0, str(AQUI)); sys.path.insert(0, str(EXCEL))
import ojos, ojos_panel, curso_pantalla as cp            # noqa: E402
import motor                                             # noqa: E402  (motor.Tutor: la sesión de Claude Code; motor.separar)

REGLAS_CURSO = """Eres el tutor de un curso de {app} de un estudiante, dentro de un panel junto a la ventana de {app}. Español, tono cercano,
MUY breve (máximo 6 líneas). Primero la idea y luego los clics. Si se equivoca, señala el paso exacto que falla, sin rehacer todo.
En los «Tu turno» NO hagas el ejercicio por él: da pistas, salvo que pida la solución. Solo miras y señalas: nunca digas que hiciste clic.
No uses herramientas, no menciones archivos y no afirmes cómo funciona {app} si no estás seguro: dilo.
Cada pregunta llega con el [Estado actual]: el módulo y el paso, la revisión automática y el estado de {app} EN TEXTO (qué está activo o
elegido, valores, textos y los nombres de los controles que se pueden señalar). Úsalo siempre: es lo único actualizado.

Para SEÑALAR en {app} (de 1 a 4 marcas, solo si ayudan), al FINAL añade un bloque en una línea:
<marcas>[{{"tipo": "app", "nombre": "Pencil", "texto": "el lápiz"}}]</marcas>
con "nombre" EXACTO de la lista de controles del [Estado actual]; "texto" de 1 a 4 palabras, "n" si hay orden, "color" opcional
(azul, verde, rojo, naranja). Se dibujan como flechas encima de la ventana de {app}."""


class TutorCurso(motor.Tutor):
    """motor.Tutor con las reglas y el temario de este curso."""

    def _intro(self):
        c = self.curso
        partes = [REGLAS_CURSO.format(app=c.app_nombre) + ojos_panel.REGLAS_OJOS, f"\nCurso: {c.titulo}. Módulos:"]
        for k, mod in enumerate(c.modulos):
            pasos = "; ".join(f"{p.get('titulo', '')}: {re.sub(r'[*]', '', p['texto'])[:140]}" for p in mod.pasos)
            partes.append(f"\nMódulo {k + 1}: {mod.titulo}. Tema: {mod.d.get('tema_tutor', '')}\n  Pasos: {pasos}\n"
                          f"  Lo que solo sabes tú (no lo reveles entero): {mod.d.get('notas_tutor', '')}")
        partes.append("\nResponde solo: Listo")
        return "\n".join(partes)


class Api(ojos_panel.OjosApi):
    def __init__(self, curso, tutor):
        self._curso, self._tutor = curso, tutor
        self._m, self._n = curso.progreso()
        self._ventana, self._vista, self.recordar = None, None, False
        self._marcas = []                       # las del tutor «por nombre» (se rehacen si la ventana cambia)
        self._ojos = ojos_panel.Ojos(apps=[curso.app["exe"]], panel_hwnd=self._hwnd_panel)
        self._senalando = []                    # lo que señala ahora el paso (para seguirlo si se mueve)
        self._notas = []

    # ----- utilidades -----
    @property
    def _mod(self): return self._curso.modulos[self._m]

    def _paso(self): return self._mod.pasos[self._n]

    def _turno(self): return self._paso().get("turno")

    def _hwnd_panel(self):
        try: return int(self._ventana.native.Handle.ToInt64())
        except Exception: return None

    def _empujar(self, js):
        if self._ventana:
            try: self._ventana.evaluate_js(js)
            except Exception: pass

    def _app(self): return cp.ventana_app(self._curso.app["exe"])

    # ----- lo que pide la página -----
    def listo(self): print("ventana lista", flush=True); return True

    def _botones(self):
        nombre = self._curso.app_nombre
        if not self._app(): return [{"id": "abrir", "etiqueta": f"Abrir {nombre}", "icono": "open"}]
        bs = [{"id": "app", "etiqueta": f"Ir a {nombre}", "icono": "open"}]
        if self._paso().get("senalar"): bs.insert(0, {"id": "senalar", "etiqueta": f"Señálamelo en {nombre}", "icono": "cursor"})
        return bs

    def _estado(self, aviso=""):
        p, t = self._paso(), self._turno()
        c = self._curso
        return {"n": self._n, "total": len(self._mod.pasos), "texto": p["texto"], "aviso": aviso,
                "m": self._m, "modulos": [{"titulo": m.titulo, "codigo": m.codigo} for m in c.modulos] if len(c.modulos) > 1 else [],
                "titulo": self._mod.titulo, "titulo_codigo": self._mod.codigo, "curso": c.titulo,
                "paso_titulo": p.get("titulo", ""), "donde": p.get("donde", ""), "app": c.app_nombre, "objeto": "ventana",
                "hoja": c.app_nombre, "ejercicio": t.get("titulo", "") if t else "", "svg": "", "botones": self._botones(),
                "revision": (self._vista or {"estado": "pendiente", "ok": 0, "total": 0,
                                             "mensaje": t.get("al_empezar", "Hazlo en la app y pulsa Comprobar.")}) if t else None,
                "tutor_ej": None}

    def estado(self): return self._estado()

    def _salir_del_paso(self):
        self._vista = None; self._senalando = []; self._marcas = []
        self._ojos.borrar()

    def ir(self, n):
        self._salir_del_paso()
        self._n = max(0, min(len(self._mod.pasos) - 1, int(n)))
        if self.recordar: self._curso.guardar_progreso(self._m, self._n)
        return self._estado()

    def modulo(self, m):
        self._salir_del_paso()
        self._m, self._n = max(0, min(len(self._curso.modulos) - 1, int(m))), 0
        if self.recordar: self._curso.guardar_progreso(self._m, self._n)
        return self._estado()

    def boton(self, cual):
        app = self._curso.app
        if cual == "abrir":
            cp.abrir_app(app)
            for _ in range(40):
                if self._app(): break
                time.sleep(0.25)
            return {"ok": bool(self._app()), "aviso": f"Abrí {self._curso.app_nombre}." if self._app() else f"No pude abrir {self._curso.app_nombre}."}
        v = self._app()
        if not v: return {"ok": False, "aviso": f"No encuentro {self._curso.app_nombre} abierto."}
        _al_frente(v["hwnd"])
        if cual == "senalar": return self._senalar(self._paso().get("senalar") or [])
        return {"ok": True}

    # ----- señalar por nombre -----
    def _senalar(self, objetivos, color="azul"):
        """Flechas encima de la app en los controles con esos nombres. Devuelve el aviso para la persona."""
        est = cp.estado(self._curso.app["exe"])
        marcas, faltan = [], []
        for k, o in enumerate(objetivos):
            c = cp.buscar(est, o) if est else None
            if not c: faltan.append(o.get("texto") or cp.lista(o.get("nombre") or o.get("empieza"))[0]); continue
            marcas.append({"c": c, "texto": o.get("texto", ""), "n": o.get("n") or (k + 1 if len(objetivos) > 1 else None),
                           "color": o.get("color", color)})
        self._pintar(marcas)
        if not marcas:
            antes = self._paso().get("antes")
            if antes: return {"ok": False, "aviso": f"{antes} y vuelve a pulsar «Señálamelo»."}
            return {"ok": False, "aviso": f"Ahora no veo eso en {self._curso.app_nombre}" + (f": {', '.join(faltan[:2])}." if faltan else ".")}
        falta = f" (no veo: {faltan[0]})" if faltan else ""
        return {"ok": True, "aviso": f"Mira {self._curso.app_nombre}: te señalé {len(marcas)} cosa{'s' if len(marcas) != 1 else ''}{falta}."}

    def _pintar(self, marcas):
        """marcas: [{"c": control de cp.estado (caja en pantalla), "texto", "n", "color"}] → overlay encima de su ventana."""
        if not marcas: self._ojos.borrar(); return 0
        v = self._app()
        if not v: return 0
        hwnd = v["hwnd"]; cli = ojos.cliente(hwnd)
        evitar = []
        try:
            est = cp.estado(self._curso.app["exe"]) or {"controles": []}
            evitar = [[a, b, c - a, d - b] for (a, b, c, d) in (x["caja"] for x in est["controles"] if x.get("caja") and x["tipo"] != "texto")]
        except Exception: pass
        r = self._ojos.ov.orden({"cmd": "mostrar", "pids": [v["pid"], os.getpid()], "panel": self._hwnd_panel(), "marcas": [
            {"hwnd": hwnd, "ventana": list(cli), "rect": [m["c"]["caja"][0], m["c"]["caja"][1], m["c"]["caja"][2] - m["c"]["caja"][0],
                                                          m["c"]["caja"][3] - m["c"]["caja"][1]],
             "texto": m["texto"], "color": m["color"], "n": m.get("n"), "evitar": evitar} for m in marcas]})
        return r.get("dibujadas", 0)

    # ----- Comprobar -----
    def comprobar(self):
        t = self._turno()
        if not t: return {"revision": None}
        est = cp.estado(self._curso.app["exe"])
        rev = cp.revisar_turno(est, t) if t.get("pide") else {"estado": "bien", "ok": 0, "total": 0, "puntos": [], "mensaje": ""}
        if rev["estado"] == "bien" and t.get("tutor") and est is not None:
            v = self._app()
            self._sin_ia = rev
            return {"revision": None, "necesita_captura": True, "hwnd": v["hwnd"] if v else None,
                    "aviso": "Para revisar el dibujo, el tutor necesita verlo: adjunta la captura de la ventana (o cancela)."}
        self._vista = rev
        return {"revision": rev}

    def comprobar_tutor(self, ojos_id):
        """La parte del «Tu turno» que solo se ve en la imagen: el tutor mira la captura que la persona adjuntó."""
        t = self._turno(); cap = self._ojos.capturas.get(ojos_id or "")
        if not t or not cap: return {"revision": None, "aviso": "No hay captura: vuelve a pulsar Comprobar."}
        base = getattr(self, "_sin_ia", None) or {"ok": 0, "total": 0, "puntos": []}
        b64 = ojos.a_data_url(cap.img).split(",", 1)[1]
        pregunta = (f"Revisa el «Tu turno» «{t.get('titulo', '')}» en la captura adjunta. Tiene que verse: {t['tutor']['revisar']}. "
                    "Responde SOLO con una línea así, sin nada más: "
                    '<revision>{"estado": "bien" | "casi" | "mal", "mensaje": "una frase para el estudiante (si falla, qué cambiar, sin hacerlo por él)"}</revision>')
        try:
            r = self._tutor.preguntar(self._contexto(), pregunta, lambda x: None,
                                      [{"nombre": "captura.png", "tipo": "imagen", "media_type": "image/png", "datos": b64}])
        except Exception as e:
            return {"revision": None, "aviso": f"No pude hablar con el tutor ({e}). Vuelve a pulsar Comprobar."}
        m = re.search(r"<revision>\s*(\{.*?\})\s*</revision>", r or "", re.S)
        try: d = json.loads(m.group(1)) if m else {}
        except ValueError: d = {}
        estado = d.get("estado") if d.get("estado") in ("bien", "casi", "mal") else "casi"
        puntos = base["puntos"] + [{"ok": estado == "bien", "texto": t["tutor"]["revisar"][:1].upper() + t["tutor"]["revisar"][1:] + " (lo revisó el tutor)"}]
        rev = {"estado": estado, "ok": base["ok"] + (estado == "bien"), "total": base["total"] + 1, "puntos": puntos,
               "mensaje": d.get("mensaje") or ("¡Bien hecho!" if estado == "bien" else "Revisa tu dibujo y vuelve a comprobar.")}
        self._vista = rev
        return {"revision": rev}

    # ----- tutor -----
    def _contexto(self):
        p, t = self._paso(), self._turno()
        mods = f"Módulo {self._m + 1} de {len(self._curso.modulos)} («{self._mod.titulo}»). " if len(self._curso.modulos) > 1 else ""
        partes = [f"[Estado actual] {mods}Paso {self._n + 1} de {len(self._mod.pasos)}: {p.get('titulo', '')}. El panel dice: {p['texto']}"]
        est = cp.estado(self._curso.app["exe"])
        if t:
            rev = cp.revisar_turno(est, t) if t.get("pide") else None
            if rev: partes.append(f"Revisión automática ahora: {rev['mensaje']} ({rev['ok']} de {rev['total']} bien)")
            if t.get("tutor"): partes.append(f"Este turno además pide (se ve en la imagen): {t['tutor']['revisar']}")
        partes.append(cp.contexto_tutor(est, self._curso.app_nombre))
        return "\n".join(partes)

    def preguntar(self, pregunta, adjuntos=None):
        pregunta = (pregunta or "").strip()
        if not pregunta and not adjuntos: return {"texto": ""}
        pregunta = pregunta or "Mira lo que te adjunto."
        ctx = self._contexto()
        if self._notas: ctx = "[Del panel] " + " ".join(self._notas) + "\n" + ctx; self._notas = []
        ctx += ("\n" + self._ojos.contexto(adjuntos)).rstrip()
        def trozo(t): self._empujar(f"window.trozoTutor({json.dumps(t)})")
        try: resp = self._tutor.preguntar(ctx, pregunta, trozo, adjuntos)
        except ValueError as e: return {"texto": str(e)}
        except Exception as e: return {"texto": f"No pude hablar con el tutor ({e}). Intenta otra vez."}
        resp, pide = ojos_panel.separar_pedido(resp)
        texto, marcas = motor.separar(resp)
        marcas, en_ventana = self._ojos.marcar(marcas)            # las "ventana" (sobre una captura)
        hechas = 0
        por_nombre = [m for m in marcas if isinstance(m, dict) and m.get("tipo") == "app" and m.get("nombre")]
        if por_nombre:
            est = cp.estado(self._curso.app["exe"])
            ms = []
            for k, m in enumerate(por_nombre[:4]):
                c = cp.buscar(est, {"nombre": m["nombre"]}) if est else None
                if c: ms.append({"c": c, "texto": str(m.get("texto") or "")[:40], "n": m.get("n"), "color": m.get("color") or "azul"})
                else: self._notas.append(f"Tu marca en «{m['nombre']}» no se dibujó: ese control no está a la vista.")
            if ms and not en_ventana: hechas = self._pintar(ms) and len(ms)
        return {"texto": texto, "marcas": 0, "marcas_ventana": en_ventana + hechas, "pedir": pide}

    def borrar_marcas(self):
        self._ojos.borrar(); self._senalando = []
        return {"ok": True}

    def restaurar(self, m, n):
        self._m = max(0, min(len(self._curso.modulos) - 1, int(m)))
        self._n = max(0, min(len(self._mod.pasos) - 1, int(n)))

    def cerrar(self):
        self._ojos.cerrar()


def _al_frente(h):
    try:
        if ojos.u32.IsIconic(h): ojos.u32.ShowWindow(h, 9)
        ojos.u32.SetForegroundWindow(h)
    except Exception: pass


def abrir_ventana(api):
    import webview, panel_web
    x0, y0, ancho, alto, _ = panel_web.area_visible(); ancho_v = 480
    tema = panel_web.preferencias().get("tema", "claro")
    app = json.dumps(api._curso.app_nombre)
    pagina = (EXCEL / "panel.html").read_text(encoding="utf-8").replace(
        "<head>", f"<head><script>window.TEMA_PANEL = {json.dumps(tema)}; window.OBJETO_PANEL = 'ventana'; window.APP_PANEL = {app};</script>", 1)
    pagina = ojos_panel.inyectar_ui(pagina)
    api._ventana = webview.create_window(api._curso.titulo or "Curso", html=pagina, js_api=api,
                                         width=ancho_v, height=int(alto), x=int(x0 + ancho - ancho_v), y=int(y0),
                                         on_top=True, min_size=(360, 300), background_color="#232631" if tema == "oscuro" else "#F8F6F1")


def probar(curso):
    """--probar: sin ventanas ni IA. Devuelve los fallos."""
    malos = 0

    def ver(c, txt):
        nonlocal malos
        malos += not c; print("✔" if c else "✘", txt)

    print(f"Curso «{curso.titulo}» ({curso.app_nombre}): {len(curso.modulos)} módulo(s)")
    est = cp.estado(curso.app["exe"])
    print(f"  {curso.app_nombre} {'abierto: se buscan los «senalar»' if est else 'cerrado: no se buscan los «senalar» (ábrelo para probarlos)'}")
    for mod in curso.modulos:
        print(f"Módulo {mod.codigo} «{mod.titulo}»: {len(mod.pasos)} pasos")
        for i, p in enumerate(mod.pasos):
            if est:
                for o in p.get("senalar") or []:
                    nombre = cp.lista(o.get("nombre") or o.get("empieza"))[0]
                    if cp.buscar(est, o) is None and p.get("antes"):     # solo se ve después de abrir algo (un diálogo)
                        print(f"ℹ   paso {i + 1}: «{nombre}» no está a la vista ahora ({p['antes']})"); continue
                    ver(cp.buscar(est, o) is not None, f"  paso {i + 1}: «{nombre}» se encuentra en {curso.app_nombre}")
            t = p.get("turno")
            if not t: continue
            pide = t.get("pide") or []
            if pide:
                r = cp.revisar_turno(cp.simular(pide), t)
                ver(r["estado"] == "bien", f"  paso {i + 1} (Tu turno): con la solución → {r['estado']}")
                r = cp.revisar_turno(cp.simular(), t)
                ver(r["estado"] in ("mal", "parcial") and r["ok"] == 0, f"  paso {i + 1}: sin hacer nada → {r['estado']} («{r['mensaje'][:60]}»)")
                for k, e in enumerate(t.get("errores") or []):
                    otros = [q for q in pide if q["tipo"] != e["si"]["tipo"]]   # el error reemplaza lo de su tipo; lo demás, bien hecho
                    r = cp.revisar_turno(cp.simular(otros, [e["si"]]), t)
                    ver(r["estado"] == "mal" and r["mensaje"] == e["mensaje"], f"  paso {i + 1}: error típico {k + 1} se reconoce («{e['mensaje'][:50]}…»)")
            if t.get("tutor"): print(f"  paso {i + 1}: además lo revisa el tutor con la captura: «{t['tutor']['revisar']}»")
    ver(cp.revisar_turno(None, {"pide": [{"tipo": "activo", "nombre": "x"}]})["estado"] == "vacio", "sin la app abierta, Comprobar lo dice")
    ctx = cp.contexto_tutor({"titulo": "a", "titulos": ["a"], "controles": [{"tipo": "botón", "nombre": "Signed in as Fulano", "caja": (0, 0, 1, 1), "activo": False, "valor": ""}]}, "app")
    ver("Fulano" not in ctx, "el botón de la cuenta (con su nombre) no llega al tutor")
    print("Curso: todo bien" if not malos else f"Curso: {malos} fallo(s)")
    return malos


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args: sys.exit(__doc__)
    try: curso = cp.Curso(args[0])
    except (OSError, ValueError, KeyError) as e: sys.exit(f"No puedo abrir el curso {args[0]}: {e}")
    if "--probar" in sys.argv: sys.exit(probar(curso))
    import webview
    tutor = TutorCurso(curso); tutor.calentar()
    api = Api(curso, tutor); api.recordar = True
    abrir_ventana(api)
    webview.start(gui="edgechromium")
    api.cerrar(); tutor.cerrar()
