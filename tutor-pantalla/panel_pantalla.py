"""Panel del asistente que mira UNA ventana (con permiso) y señala encima de ella.

  python panel_pantalla.py                          abre el panel (modo asistente)
  python panel_pantalla.py --puente                 abre el panel en modo puente: responde el chat de Claude Code
                                                   (ver puente.py)
  python panel_pantalla.py --probar "Word" [png]    prueba sin ventana: captura la primera ventana con ese texto en
                                                   el título o la app, pregunta dónde se guarda el archivo, dibuja las
                                                   flechas y guarda la captura con ellas (png) para revisarla

Permiso: nada sale de la PC sin pasar por la vista previa (ojos_panel y ojos_ui.js, los mismos de los tutores).
«Adjuntar» deja la captura en el mensaje y solo sale cuando la persona lo envía (preguntar() con su ojos_id).
Las flechas las dibuja ../prueba-dia/overlay_dia.py (el mismo de Dia, sin cambios): ventana transparente encima de
la app, que deja pasar los clics y solo se ve con la app o el panel al frente."""
import json, os, sys, time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ojos, asistente, ojos_panel, archivos                            # noqa: E402

PREFERENCIAS = AQUI.parent / "panel-excel" / "preferencias.json"         # el tema de los paneles del tutor
REGLAS = (asistente.REGLAS + ojos_panel.REGLAS_DIBUJOS.replace("(junto a tus otras marcas)", "(en la misma línea MARCAS: [...])")
          + ojos_panel.REGLAS_PREGUNTAS + "\nEl bloque <preguntas> va antes de la línea MARCAS.\n" + ojos_panel.REGLAS_VOLVER
          + archivos.REGLAS + "\n" + archivos.lista(()))


class Api(ojos_panel.OjosApi):
    """Lo que llama la página (window.pywebview.api.*). Los métodos con _ no se ven desde la página.
    La lista de ventanas, la vista previa y las flechas son de ojos_panel (los mismos de los tutores de Excel y Dia)."""

    def __init__(self, sesion, puente=None):
        self._sesion = sesion
        self._puente = puente           # modo puente: responde el chat de Claude Code (puente.LadoPanel), no la sesión
        self._esperando = {}            # id del mensaje → ya avisamos que lo está leyendo
        self._ventana = None            # la ventana de pywebview
        self._hwnd = None               # la ventana elegida
        self._mi_hwnd = None
        self._notas = []                # lo que se le cuenta al asistente en la próxima pregunta (dibujos que no salieron)
        self._ojos = ojos_panel.Ojos(panel_hwnd=self._panel_hwnd)

    def _panel_hwnd(self):
        """La ventana del panel (para poner las flechas justo debajo de ella y no taparlo)."""
        if not self._mi_hwnd and self._ventana:
            try: self._mi_hwnd = int(self._ventana.native.Handle.ToInt64())      # el Form de WinForms de pywebview
            except Exception: self._mi_hwnd = next(iter(ojos.ventanas_de(os.getpid())), None)
        return self._mi_hwnd

    def elegir(self, hwnd):
        hwnd = int(hwnd)
        if not ojos.u32.IsWindow(hwnd): return {"ok": False, "error": "Esa ventana ya no existe."}
        if hwnd != self._hwnd: self.borrar_flechas()
        self._hwnd = hwnd
        return {"ok": True, "titulo": ojos.titulo(hwnd), "app": ojos.app_de(ojos.pid_de(hwnd))}

    def _ventana_elegida(self):
        if self._hwnd and ojos.u32.IsWindow(self._hwnd):
            return {"titulo": ojos.titulo(self._hwnd), "app": ojos.app_de(ojos.pid_de(self._hwnd))}

    def preguntar(self, texto, adjuntos=None):
        """adjuntos: [{"ojos_id", "nombre"}] de las capturas que la persona adjuntó (pasaron por la vista previa) y
        archivos que adjuntó ella ({"nombre", "tipo": imagen | pdf | texto, "media_type", "datos"}: clip, pegar o
        arrastrar). Una captura solo sale así: en el mensaje que la persona envía con ella dentro."""
        texto = (texto or "").strip()
        caps = [self._ojos.capturas[a["ojos_id"]] for a in adjuntos or [] if a.get("ojos_id") in self._ojos.capturas]
        archivos = [a for a in adjuntos or [] if not a.get("ojos_id") and a.get("datos")]
        if not texto and not caps and not archivos: return {"ok": False, "error": "Escribe algo."}
        texto = texto or ("¿Qué ves? Ayúdame con esto." if caps else "Mira lo que te adjunto.")
        if self._notas and not self._puente: texto = "[Del panel] " + " ".join(self._notas) + "\n" + texto; self._notas = []
        if self._puente:
            if caps: self._ojos.ultima = caps[-1]
            return self._al_chat(texto, caps[-1] if caps else None, archivos)
        try: bloques, textos, nombres = ojos_panel.bloques_adjuntos(archivos)
        except ValueError as e: return {"ok": False, "error": str(e)}
        extra = (f"\n(Adjuntos: {', '.join(nombres)})" if nombres else "") + textos
        if not caps:
            v = self._ventana_elegida()
            t = f"(Ventana elegida: «{v['titulo']}»; sin captura nueva.)\nPersona: {texto}" if v else f"Persona: {texto}"
            return self._responder(bloques + [{"type": "text", "text": t + extra}] if bloques or extra else t)
        ctx = self._ojos.contexto(adjuntos)
        contenido = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                  "data": ojos.a_data_url(c.img).split(",", 1)[1]}} for c in caps]
        return self._responder(contenido + bloques + [{"type": "text", "text": f"{ctx}\n\nPersona: {texto}{extra}"}])

    # --- modo puente ---
    def _al_chat(self, texto, cap=None, archivos=()):
        """El mensaje va al chat de Claude Code; la respuesta llega luego por _vigilar_puente()."""
        mid = self._puente.mandar(texto, self._ventana_elegida(), cap, archivos)
        self._esperando[mid] = False
        return {"ok": True, "espera": True}

    def _js(self, funcion, dato):
        if self._ventana: self._ventana.evaluate_js(f"{funcion}({json.dumps(dato, ensure_ascii=False)})")

    def _vigilar_puente(self):
        """Hilo del modo puente: avisa cuando el chat leyó el mensaje y enseña lo que responde."""
        while self._ventana is not None:
            try:
                for mid, avisado in list(self._esperando.items()):
                    if not avisado and self._puente.leido(mid):
                        self._esperando[mid] = True; self._js("avisoTrabajo", "Claude Code lo está leyendo…")
                for d in self._puente.recibir():
                    if d.get("tipo") == "pedir_captura":
                        self._js("pedirCaptura", d.get("texto") or "¿Me dejas ver la ventana?")
                        continue
                    self._esperando.clear()
                    self._js("respuestaPuente", self._leer_respuesta(d.get("texto") or ""))
            except Exception:
                import traceback; traceback.print_exc()          # el vigía no se cae, pero el fallo queda a la vista
            time.sleep(0.4)

    def _responder(self, contenido):
        def trozo(t):
            if self._ventana: self._ventana.evaluate_js(f"trozo({json.dumps(t)})")
        def aviso(t):
            if self._ventana: self._ventana.evaluate_js(f"avisoTrabajo({json.dumps(t)})")
        try:
            r = self._sesion.preguntar(contenido, trozo, aviso)
        except Exception as e:
            return {"ok": False, "error": f"El asistente no respondió: {e}"}
        return self._leer_respuesta(r)

    def _leer_respuesta(self, r):
        """Texto para la página: sin la línea MARCAS (flechas y dibujos) ni <pedir_ventana/> (es un botón)."""
        limpio, pide = ojos_panel.separar_pedido(r)           # primero: puede venir antes o después de MARCAS
        limpio, preguntas = ojos_panel.separar_preguntas(limpio)            # <preguntas> → tarjeta con botones
        limpio, lista = asistente.separar(limpio)
        lista, lote, avisos = self._ojos.dibujos(lista, self._resolver, self._hwnd)
        if avisos: self._notas.append("Estos dibujos tuyos no se pudieron hacer: " + "; ".join(avisos) + ".")
        ms = asistente.marcas(lista, self._ojos.ultima) if self._ojos.ultima else []
        if ms: self._ojos.mostrar(ms)
        return {"ok": True, "texto": limpio, "marcas": len(ms), "pedir": pide, "dibujos": lote, "avisos": avisos, "preguntas": preguntas}

    def _resolver(self, m):
        """Las marcas con "celda": solo si la ventana es un Excel (se lee por COM, nunca se escribe)."""
        if not m.get("celda"): return None
        cap = self._ojos.ultima; h = cap.hwnd if cap else self._hwnd
        if not h or ojos.app_de(ojos.pid_de(h)).upper() != "EXCEL": raise ValueError("las celdas solo se ubican en una ventana de Excel")
        import pythoncom
        pythoncom.CoInitialize()                                # cada llamada de la página llega en su propio hilo
        xl = ojos_panel.rayos_x().excel_de_ventana(h)
        if xl is None: raise ValueError("no pude leer ese Excel")
        return ojos_panel.resolver_excel(xl, m)

    def borrar_flechas(self):
        self._ojos.borrar()
        return {"ok": True}

    def abrir_enlace(self, url):
        """Los enlaces de las respuestas se abren en el navegador de siempre (el panel no navega)."""
        if not str(url).startswith(("https://", "http://")): return {"ok": False}
        import webbrowser
        webbrowser.open(url)
        return {"ok": True}

    def nueva(self):
        self.borrar_flechas(); self._ojos.ultima = None
        if self._sesion: self._sesion.reiniciar(); self._sesion.calentar()
        return {"ok": True}


def area_visible():
    """Área de la pantalla sin la barra de tareas, en píxeles lógicos (los de pywebview); como en panel-excel."""
    import ctypes.wintypes
    r = ctypes.wintypes.RECT(); ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
    esc = ctypes.windll.user32.GetDpiForSystem() / 96
    return r.left / esc, r.top / esc, (r.right - r.left) / esc, (r.bottom - r.top) / esc


def tema():
    try: return json.loads(PREFERENCIAS.read_text(encoding="utf-8")).get("tema", "claro")
    except Exception: return "claro"


def abrir(api, al_abrir=None):
    """al_abrir: función que corre en otro hilo con la ventana ya creada (el vigía del puente, las pruebas)."""
    import webview
    x0, y0, ancho, alto = area_visible(); ancho_v = 460; t = tema()
    modo = "puente" if api._puente else "asistente"
    html = ojos_panel.inyectar_ui((AQUI / "panel.html").read_text(encoding="utf-8").replace(
        "<head>", f"<head><script>window.TEMA_PANEL = {json.dumps(t)}; window.MODO_PANEL = {json.dumps(modo)};</script>", 1))
    api._ventana = webview.create_window("Claude Code (puente)" if api._puente else "Asistente", html=html, js_api=api,
                                         width=ancho_v, height=int(alto), x=int(x0 + ancho - ancho_v), y=int(y0),
                                         on_top=True, text_select=True, min_size=(360, 300),
                                         background_color="#232631" if t == "oscuro" else "#F8F6F1")
    api._ventana.events.closed += lambda: setattr(api, "_ventana", None)
    ojos_panel.atajo(lambda: api._ventana, api._panel_hwnd)                # Ctrl+Alt+M: «Que mire» desde cualquier programa
    webview.start(al_abrir, gui="edgechromium")


def probar(texto, png=None):
    """Prueba de punta a punta sin el panel (no envía nada a la persona: es para quien desarrolla)."""
    v = next((v for v in ojos.listar_ventanas(excluir_pids=[os.getpid()])
              if texto.lower() in v["titulo"].lower() or texto.lower() in v["app"].lower()), None)
    if not v: sys.exit(f"No hay ninguna ventana con «{texto}».")
    ses = asistente.Sesion(REGLAS); api = Api(ses)
    try:
        t = time.time(); ses.calentar(); ses.preguntar("Responde solo: ok"); print(f"Arranque de la sesión: {time.time() - t:.1f}s")
        print(api.elegir(v["hwnd"]))
        t = time.time(); c = api.ojos_capturar(v["hwnd"])
        print(f"Captura: {c.get('w')}×{c.get('h')}, {c.get('controles')} controles, {c.get('como')} ({time.time() - t:.1f}s)" if c["ok"] else c)
        if not c["ok"]: return
        a = api.ojos_adjuntar()                    # lo que hace «Adjuntar» en la vista previa
        t = time.time(); r = api.preguntar("¿Dónde está la opción para guardar este archivo? Señálamela.", [{"ojos_id": a["ojos_id"], "nombre": a["nombre"]}])
        print(f"Respuesta ({time.time() - t:.1f}s): {r}")
        print("Marcas:", api._ojos.marcas)
        if png:
            img, origen, _ = ojos.imagen_de(v["hwnd"])
            d = api._ojos.ov.orden({"cmd": "volcar", "carpeta": str(Path(png).resolve().parent)})
            from PIL import Image
            for capa in d.get("capas", []):
                im = Image.open(capa["png"]); x, y = capa["en"]
                img.paste(im, (x - origen[0], y - origen[1]), im); os.remove(capa["png"])
            img.save(png); print("Guardada:", png)
    finally:
        api._ojos.cerrar(); ses.cerrar()


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    a = sys.argv[1:]
    if a[:1] == ["--probar"] and len(a) >= 2:
        probar(a[1], a[2] if len(a) > 2 else None)
    elif a == ["--puente"]:
        import puente
        try: lado = puente.LadoPanel()
        except RuntimeError as e: sys.exit(str(e))
        api = Api(None, lado)
        try: abrir(api, api._vigilar_puente)
        finally: api._ojos.cerrar(); lado.cerrar()
    elif not a:
        ses = asistente.Sesion(REGLAS); api = Api(ses)
        ses.calentar()                              # la sesión arranca mientras eliges la ventana
        try: abrir(api)
        finally: api._ojos.cerrar(); ses.cerrar()
    else:
        print(__doc__)
