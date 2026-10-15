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
import json, os, re, sys, threading, time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
EXCEL = AQUI.parent / "panel-excel"
sys.path.insert(0, str(AQUI)); sys.path.insert(0, str(EXCEL))
import ojos, ojos_panel, capacidades, curso_pantalla as cp   # noqa: E402
import motor                                             # noqa: E402  (motor.Tutor: la sesión de Claude Code; motor.separar)

REGLAS_CURSO = """Eres el tutor de un curso de {app} de un estudiante, dentro de un panel junto a la ventana de {app}. Español, tono cercano,
MUY breve (máximo 6 líneas). Primero la idea y luego los clics. Si se equivoca, señala el paso exacto que falla, sin rehacer todo.
En los «Tu turno» NO hagas el ejercicio por él: da pistas, salvo que pida la solución. Solo miras y señalas: nunca digas que hiciste clic.
Tus únicas herramientas son WebSearch y WebFetch (ver TUS CAPACIDADES). No menciones archivos de este panel y no afirmes cómo funciona {app} si no estás seguro: dilo (o búscalo).
Cada pregunta llega con el [Estado actual]: el módulo y el paso, la revisión automática y el estado de {app} EN TEXTO (qué está activo o
elegido, valores, textos y los nombres de los controles que se pueden señalar). Úsalo siempre: es lo único actualizado.

Para SEÑALAR en {app} (de 1 a 4 marcas, solo si ayudan), al FINAL añade un bloque en una línea:
<marcas>[{{"tipo": "app", "nombre": "Pencil", "texto": "el lápiz"}}]</marcas>
con "nombre" EXACTO de la lista de controles del [Estado actual]; "texto" de 1 a 4 palabras, "n" si hay orden, "color" opcional
(azul, verde, rojo, naranja). Se dibujan como flechas encima de la ventana de {app}."""


class TutorCurso(capacidades.ConWeb, motor.Tutor):
    """motor.Tutor con las reglas y el temario de este curso, y con WebSearch/WebFetch (capacidades.ConWeb)."""

    def _intro(self):
        c = self.curso
        partes = [REGLAS_CURSO.format(app=c.app_nombre) + capacidades.reglas(c.app_nombre, bool(c.d.get("proyecto") or c.d.get("proyectos"))), f"\nCurso: {c.titulo}. Módulos:"]
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
        self._raices = capacidades.raices_curso(curso.d)          # dónde buscar el archivo abierto en VS Code
        self._codigo = bool(curso.d.get("proyecto") or curso.d.get("proyectos"))
        self._ojos = ojos_panel.Ojos(apps=[curso.app["exe"]], panel_hwnd=self._hwnd_panel, raices=self._raices)
        tutor.al_aviso = lambda t: self._empujar(f"window.avisoTrabajo && window.avisoTrabajo({json.dumps(t)})")
        self._senalando = []                    # lo que señala ahora el paso (para seguirlo si se mueve)
        self._notas = []
        self._rev_lock = threading.Lock()       # una revisión de código a la vez (Maven tarda)
        self._seg_estimados = 20

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
        if self._paso().get("dibujos"): bs.insert(0, {"id": "dibujos", "etiqueta": f"Muéstramelo en {nombre}", "icono": "spark"})
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
        if cual == "dibujos": return self._dibujos_paso(v)
        return {"ok": True}

    def _dibujos_paso(self, v):
        """«Muéstramelo»: los dibujos que trae el paso (por nombre de control), sin IA."""
        try: marcas = ojos_panel.validar_dibujos(self._paso().get("dibujos"), f"paso {self._n + 1}")
        except ValueError as e: return {"ok": False, "aviso": str(e)}
        _, lote, avisos = self._ojos.dibujos(marcas, self._resolver_nombre(), v["hwnd"])
        if not lote:
            antes = self._paso().get("antes")
            return {"ok": False, "aviso": f"{antes} y vuelve a pulsar «Muéstramelo»." if antes else "Ahora no lo veo: " + ("; ".join(avisos) or "nada que mostrar") + "."}
        return {"ok": True, "dibujos": lote, "aviso": f"Mira {self._curso.app_nombre}." + (f" (No salió: {avisos[0]})" if avisos else "")}

    # ----- señalar por nombre -----
    def _senalar(self, objetivos, color="azul"):
        """Flechas encima de la app en los controles con esos nombres. Devuelve el aviso para la persona."""
        est = cp.estado(self._curso.app["exe"])
        marcas, faltan = [], []
        for k, o in enumerate(objetivos):
            if o.get("linea") is not None:                # una línea del editor
                ms, av = capacidades.marcas_linea([dict(o, tipo="app")], self._raices, (self._app() or {}).get("hwnd"))
                for m in ms: m["n"] = o.get("n") or (k + 1 if len(objetivos) > 1 else None); m["color"] = o.get("color", color)
                marcas += ms; faltan += [] if ms else [f"la línea {o['linea']}"]
                self._lin_avisos = av
                continue
            c = cp.buscar(est, o) if est else None
            if not c: faltan.append(o.get("texto") or cp.lista(o.get("nombre") or o.get("empieza"))[0]); continue
            marcas.append({"c": c, "texto": o.get("texto", ""), "n": o.get("n") or (k + 1 if len(objetivos) > 1 else None),
                           "color": o.get("color", color)})
        self._pintar(marcas)
        extra = " " + " ".join(getattr(self, "_lin_avisos", []) or []) if getattr(self, "_lin_avisos", None) else ""
        self._lin_avisos = []
        if not marcas:
            antes = self._paso().get("antes")
            if antes: return {"ok": False, "aviso": f"{antes} y vuelve a pulsar «Señálamelo»."}
            return {"ok": False, "aviso": f"Ahora no veo eso en {self._curso.app_nombre}" + (f": {', '.join(faltan[:2])}." if faltan else ".")}
        falta = f" (no veo: {faltan[0]})" if faltan else ""
        return {"ok": True, "aviso": f"Mira {self._curso.app_nombre}: te señalé {len(marcas)} cosa{'s' if len(marcas) != 1 else ''}{falta}.{extra}"}

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
    def _aviso_pagina(self, boton, aviso):
        """Pone el texto del botón Comprobar y el aviso del turno desde Python (mientras la revisión corre en segundo plano)."""
        self._empujar("(function(){var b=document.getElementById('comprobarTxt'),a=document.getElementById('turnoAviso');"
                      f"if(b)b.textContent={json.dumps(boton)};if(a){{a.hidden=false;a.textContent={json.dumps(aviso)};}}}})()")

    def comprobar(self):
        t = self._turno()
        if not t: return {"revision": None}
        codigo = cp.ContextoCodigo.usa_codigo(t)
        if codigo and not self._rev_lock.acquire(blocking=False):
            return {"revision": None, "aviso": "Todavía estoy revisando lo anterior; espera un momento."}
        try:
            ctx = None
            if codigo:                  # Maven corre en este hilo (no en el de la página): el panel y el tutor siguen vivos
                ctx = cp.ContextoCodigo(self._curso, self._mod, t)
                self._aviso_pagina("Revisando…", f"Revisando… (corriendo tus pruebas, ~{self._seg_estimados} s)" if cp.ContextoCodigo.usa_maven(t) else "Revisando…")
            ui = any(q["tipo"] not in cp.TIPOS_CODIGO for q in t.get("pide") or []) or bool(t.get("tutor"))
            est = cp.estado(self._curso.app["exe"]) if (ui or not codigo) else None
            t0 = time.time()
            rev = cp.revisar_turno(est, t, ctx) if t.get("pide") else {"estado": "bien", "ok": 0, "total": 0, "puntos": [], "mensaje": ""}
            if ctx is not None and ctx._mvn: self._seg_estimados = max(5, int(round(time.time() - t0)))
        finally:
            if codigo: self._rev_lock.release()
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
            if cp.ContextoCodigo.usa_codigo(t):          # Maven no se corre por cada pregunta: lo último que vio Comprobar
                partes.append("Este Tu turno revisa " + cp.ContextoCodigo(self._curso, self._mod, t).descripcion()
                              + ". Los archivos que pida son relativos a esa carpeta; no es el proyecto de otros pasos.")
                if self._vista: partes.append(f"Última revisión automática: {self._vista['mensaje']} ({self._vista['ok']} de {self._vista['total']} bien)")
                rev = None
            else: rev = cp.revisar_turno(est, t) if t.get("pide") else None
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
        resp, preguntas = ojos_panel.separar_preguntas(resp)          # <preguntas> → tarjeta con botones
        texto, marcas = motor.separar(resp)
        lote = avisos = None
        if any(isinstance(m, dict) and m.get("tipo") == "dibujo" for m in marcas):    # encima de la app (dibujante.js + capa.py)
            marcas, lote, avisos = self._ojos.dibujos(marcas, self._resolver_nombre(), (self._app() or {}).get("hwnd"))
        if avisos: self._notas.append("Estos dibujos tuyos no se pudieron hacer: " + "; ".join(avisos) + ".")
        marcas, en_ventana = self._ojos.marcar(marcas)            # las "ventana" (sobre una captura)
        hechas = 0
        ms = []
        por_linea = [m for m in marcas if isinstance(m, dict) and m.get("tipo") in ("app", "linea") and m.get("linea") is not None]
        if por_linea and not en_ventana:                           # flechas sobre una línea del editor
            ms, av = capacidades.marcas_linea(por_linea[:4], self._raices, (self._app() or {}).get("hwnd"))
            for a in av:
                self._notas.append(f"Tu marca de línea: {a}.")
                if a.startswith(("Sube", "Baja")): self._ojos.avisos_linea.append(a)
        por_nombre = [m for m in marcas if isinstance(m, dict) and m.get("tipo") == "app" and m.get("nombre")]
        if por_nombre:
            est = cp.estado(self._curso.app["exe"])
            for k, m in enumerate(por_nombre[:4]):
                c = cp.buscar(est, {"nombre": m["nombre"]}) if est else None
                if c: ms.append({"c": c, "texto": str(m.get("texto") or "")[:40], "n": m.get("n"), "color": m.get("color") or "azul"})
                else: self._notas.append(f"Tu marca en «{m['nombre']}» no se dibujó: ese control no está a la vista.")
        if ms and not en_ventana: hechas = self._pintar(ms) and len(ms)
        for a in capacidades.avisos_linea(self._ojos):             # «Sube/Baja hasta la línea N»: se lo dice el panel
            texto = (texto + "\n\n" if texto else "") + "↕ " + a + "."
        return {"texto": texto, "marcas": 0, "marcas_ventana": en_ventana + hechas, "pedir": pide, "dibujos": lote, "preguntas": preguntas}

    def _resolver_nombre(self):
        """Para Ojos.dibujos: los "dibujo" con "nombre" se ubican por UI Automation en la ventana de la app (el estado
        se lee una sola vez por respuesta, aunque haya varios pasos)."""
        est = {}
        def resolver(m):
            if not m.get("nombre"): return None
            if "e" not in est: est["e"] = cp.estado(self._curso.app["exe"])
            c = cp.buscar(est["e"], {"nombre": m["nombre"]}) if est["e"] else None
            v = self._app()
            if not c or not v: raise ValueError(f"«{m['nombre']}» no está a la vista")
            a, b, x1, y1 = c["caja"]
            return {"hwnd": v["hwnd"], "r": [a, b, x1 - a, y1 - b]}
        return resolver

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
                                         on_top=True, text_select=True, min_size=(360, 300), background_color="#232631" if tema == "oscuro" else "#F8F6F1")


def probar_codigo(curso, mod, kmod, i, t, pide_ui, ver):
    """--probar de un «Tu turno» de código: contra solucion/<stem>/ debe salir bien y contra la del módulo anterior (o
    solucion/plantilla/) no. Los http no se prueban aquí. Devuelve 0 (los fallos los cuenta `ver`)."""
    sol = curso.carpeta / "solucion"
    mia = sol / mod.ruta.stem
    ant = next((sol / curso.modulos[j].ruta.stem for j in range(kmod - 1, -1, -1) if (sol / curso.modulos[j].ruta.stem).is_dir()), sol / "plantilla")
    if not mia.is_dir():
        print(f"ℹ   paso {i + 1}: no hay solucion/{mod.ruta.stem}/: el Tu turno de código no se prueba contra una solución"); return 0
    est = cp.simular(pide_ui)
    ctx = cp.ContextoCodigo(curso, mod, t, raiz=mia, sin_http=True)
    r = cp.revisar_turno(est, t, ctx)
    ver(r["estado"] == "bien", f"  paso {i + 1} (código): con solucion/{mia.name}/ → {r['estado']} ({r['mensaje'][:90]})")
    if not ant.is_dir():
        print(f"ℹ   paso {i + 1}: no hay {ant.name}/ para comprobar que sin hacerlo no sale bien"); return 0
    ctx = cp.ContextoCodigo(curso, mod, t, raiz=ant, sin_http=True)
    r = cp.revisar_turno(est, t, ctx)
    ver(r["estado"] != "bien", f"  paso {i + 1} (código): con solucion/{ant.name}/ (sin hacerlo) → {r['estado']} ({r['mensaje'][:90]})")
    return 0


def probar_otro_proyecto(curso, mod, i, t, pide_ui, ver):
    """--probar de un «Tu turno» con "proyecto": un proyecto del estudiante, sin solucion/. Solo se informa (ℹ, nunca ✘)
    cómo saldría hoy contra el proyecto real (Maven en una copia temporal; los http no se corren)."""
    ctx = cp.ContextoCodigo(curso, mod, t, sin_http=True)
    if not ctx.raiz.is_dir():
        print(f"ℹ   paso {i + 1}: el proyecto {ctx.descripcion()} no existe en este PC: no se puede probar contra él"); return
    sub = ctx.raiz / ctx.maven_sub
    if cp.ContextoCodigo.usa_maven(t) and not (sub / "mvnw.cmd").exists() and not (sub / "mvnw").exists():
        print(f"ℹ   paso {i + 1}: {ctx.descripcion()} aún no tiene Maven Wrapper (mvnw): los turnos de Maven saldrán con ese aviso")
    r = cp.revisar_turno(cp.simular(pide_ui), t, ctx)
    print(f"ℹ   paso {i + 1} (proyecto «{ctx.nombre}», solo informa; no es un fallo): hoy saldría «{r['estado']}» ({r['ok']} de {r['total']}): {r['mensaje'][:140]}")
    for p in r["puntos"]:
        print(f"      {'✓' if p['ok'] else '·'} {p['texto']}" + (f" → {p['detalle'][:120]}" if p.get("detalle") else ""))


def probar(curso):
    """--probar: sin ventanas ni IA. Devuelve los fallos."""
    malos = 0

    def ver(c, txt):
        nonlocal malos
        malos += not c; print("✔" if c else "✘", txt)

    print(f"Curso «{curso.titulo}» ({curso.app_nombre}): {len(curso.modulos)} módulo(s)")
    est = cp.estado(curso.app["exe"])
    print(f"  {curso.app_nombre} {'abierto: se buscan los «senalar»' if est else 'cerrado: no se buscan los «senalar» (ábrelo para probarlos)'}")
    for kmod, mod in enumerate(curso.modulos):
        print(f"Módulo {mod.codigo} «{mod.titulo}»: {len(mod.pasos)} pasos")
        for i, p in enumerate(mod.pasos):
            if est:
                for o in p.get("senalar") or []:
                    if o.get("linea") is not None: continue         # una línea del editor: depende del archivo abierto
                    nombre = cp.lista(o.get("nombre") or o.get("empieza"))[0]
                    if cp.buscar(est, o) is None and p.get("antes"):     # solo se ve después de abrir algo (un diálogo)
                        print(f"ℹ   paso {i + 1}: «{nombre}» no está a la vista ahora ({p['antes']})"); continue
                    ver(cp.buscar(est, o) is not None, f"  paso {i + 1}: «{nombre}» se encuentra en {curso.app_nombre}")
            if p.get("dibujos"):                                         # «Muéstramelo»: bien escritos y, con la app abierta, se encuentran
                try: dibs = ojos_panel.validar_dibujos(p["dibujos"], f"paso {i + 1}"); ver(True, f"  paso {i + 1}: {len(dibs)} dibujo(s) bien escritos")
                except ValueError as e: dibs = []; ver(False, f"  {e}")
                if est:
                    for d in dibs:
                        for o in [d] + [q for q in d.get("pasos") or [] if isinstance(q, dict)] + ([d["hasta"]] if isinstance(d.get("hasta"), dict) else []):
                            if not o.get("nombre"): continue
                            nombre = cp.lista(o["nombre"])[0]
                            if cp.buscar(est, {"nombre": o["nombre"]}) is None and p.get("antes"):
                                print(f"ℹ   paso {i + 1}: «{nombre}» (dibujo) no está a la vista ahora ({p['antes']})"); continue
                            ver(cp.buscar(est, {"nombre": o["nombre"]}) is not None, f"  paso {i + 1}: «{nombre}» (dibujo «{d['forma']}») se encuentra en {curso.app_nombre}")
            t = p.get("turno")
            if not t: continue
            pide_all = t.get("pide") or []
            codigo = cp.ContextoCodigo.usa_codigo(t)
            pide = [q for q in pide_all if q["tipo"] not in cp.TIPOS_CODIGO]
            t_ui = dict(t, pide=pide, errores=[e for e in t.get("errores") or [] if e["si"]["tipo"] not in cp.TIPOS_CODIGO])
            for q in pide_all:
                if q["tipo"] in cp.TIPOS_CODIGO: ver(True, f"  paso {i + 1}: «{q['tipo']}» bien escrito ({q.get('texto') or q.get('ruta') or q.get('url') or q.get('clases')})")
                if q["tipo"] == "pruebas" and q.get("ocultas"):
                    d = curso.carpeta / "pruebas" / mod.ruta.stem
                    ver(d.is_dir() and any(d.rglob("*.java")), f"  paso {i + 1}: hay pruebas ocultas en pruebas/{mod.ruta.stem}/")
            if pide:
                r = cp.revisar_turno(cp.simular(pide), t_ui)
                ver(r["estado"] == "bien", f"  paso {i + 1} (Tu turno): con la solución → {r['estado']}")
                r = cp.revisar_turno(cp.simular(), t_ui)
                ver(r["estado"] in ("mal", "parcial") and r["ok"] == 0, f"  paso {i + 1}: sin hacer nada → {r['estado']} («{r['mensaje'][:60]}»)")
                for k, e in enumerate(t_ui.get("errores") or []):
                    otros = [q for q in pide if q["tipo"] != e["si"]["tipo"]]   # el error reemplaza lo de su tipo; lo demás, bien hecho
                    r = cp.revisar_turno(cp.simular(otros, [e["si"]]), t_ui)
                    ver(r["estado"] == "mal" and r["mensaje"] == e["mensaje"], f"  paso {i + 1}: error típico {k + 1} se reconoce («{e['mensaje'][:50]}…»)")
            if codigo and t.get("proyecto"):
                probar_otro_proyecto(curso, mod, i, t, pide, ver)
            elif codigo and curso.proyecto:
                n = probar_codigo(curso, mod, kmod, i, t, pide, ver)   # primero la llamada: `ver` suma a malos dentro
                malos += n
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
    ojos_panel.atajo(lambda: api._ventana, api._hwnd_panel)                # Ctrl+Alt+M: «Mirar ventana»
    webview.start(gui="edgechromium")
    api.cerrar(); tutor.cerrar()
