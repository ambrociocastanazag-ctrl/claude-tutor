"""Panel de curso en vivo para Excel (pywebview + panel.html).
Uso:  python panel_web.py <curso.json | leccion.json>            (abre el panel encima de Excel)
      python panel_web.py <curso.json | leccion.json> --probar   (prueba pasos y revisión sin ventana)
      python panel_web.py <curso.json> --probar-tutor            (además mide al tutor)
Excel por COM solo se puede usar desde el hilo que lo abrió: todo lo de Excel pasa por
HiloExcel, que además vigila la zona del "Tu turno" para saber si cambió después de comprobar.
La revisión del "Tu turno" solo se hace y se muestra cuando la persona pulsa «Comprobar».
El tutor es una sesión de Claude Code que se abre al arrancar (motor.Tutor). Si propone cambiar el libro
(bloque <acciones>), la página muestra una tarjeta de permiso: solo se aplica con «Aplicar» y se puede deshacer."""
import ctypes, json, os, queue, sys, threading, time
import pythoncom
from pathlib import Path
import motor

AQUI = os.path.dirname(os.path.abspath(__file__))
PISTA = "Pulsa Esc en Excel (puede que estés editando una celda o haya un aviso abierto) y vuelve a intentar."


class HiloExcel(threading.Thread):
    """Único hilo que toca Excel. hacer(f) ejecuta f(libro) ahí; entre trabajos llama a `vigia`."""
    def __init__(self, curso):
        super().__init__(daemon=True); self.curso = curso; self.vigia = None
        self.trabajos = queue.Queue(); self.listo = threading.Event(); self.error = None
    def run(self):
        pythoncom.CoInitialize()
        try: self.libro = motor.Libro(self.curso)
        except Exception as e: self.error = e
        self.listo.set()
        while True:
            try: f, caja, hecho = self.trabajos.get(timeout=0.7)
            except queue.Empty:
                if self.vigia:
                    try: self.vigia(self.libro)
                    except Exception: pass          # Excel ocupado (editando una celda): se intenta en la próxima vuelta
                continue
            try: caja["ok"] = f(self.libro)
            except Exception as e: caja["error"] = e
            hecho.set()
    def hacer(self, f):
        caja, hecho = {}, threading.Event(); self.trabajos.put((f, caja, hecho)); hecho.wait()
        if "error" in caja: raise caja["error"]
        return caja["ok"]


class Api:
    """Lo que la página llama con window.pywebview.api.<método>()."""
    def __init__(self, excel, tutor, curso):
        self._x, self._tutor, self._curso = excel, tutor, curso
        self._m, self._n, self._texto, self._ventana = 0, 0, "", None
        self._huella, self._revision = None, None
        self._huella_ej = None          # la zona del ejercicio del tutor, para saber si cambió después de comprobar
        self._notas = []                # lo que se le cuenta al tutor en la próxima pregunta (qué hizo la persona con su propuesta)
        self._requisito = ""            # lo que le falta a Excel para este módulo (acceso a VBA, Solver), para avisar en Lección
        self._m, self._n = self.progreso()      # vuelve al módulo y al paso donde se quedó (si es un curso)
        excel.vigia = self._vigilar_seguro

    # ----- dónde se quedó: progreso_panel.json junto a curso.json (no va al repositorio) -----
    def progreso(self):
        ruta = getattr(self._curso, "progreso", None)
        try:
            d = json.loads(Path(ruta).read_text(encoding="utf-8"))
            m = int(d.get("m", 0)); n = int(d.get("n", 0))
            if 0 <= m < len(self._curso.modulos) and 0 <= n < len(self._curso.modulos[m]): return m, n
        except Exception: pass
        return 0, 0

    def _guardar_progreso(self):
        ruta = getattr(self._curso, "progreso", None)
        if not ruta: return
        try: Path(ruta).write_text(json.dumps({"curso": self._curso.titulo, "m": self._m, "n": self._n, "modulo": self._lec().titulo,
                                               "cuando": time.strftime("%Y-%m-%d %H:%M")}, ensure_ascii=False), encoding="utf-8")
        except Exception: pass

    # ----- estado -----
    def _lec(self): return self._curso.modulos[self._m]
    def _turno(self): return self._lec().pasos[self._n].get("turno")

    def _estado(self, aviso=""):
        lec = self._lec()
        paso, t = lec.pasos[self._n], self._turno()
        return {"m": self._m, "n": self._n, "total": len(lec), "texto": self._texto, "aviso": aviso,
                "titulo": lec.titulo, "titulo_codigo": lec.d.get("titulo_codigo", ""), "curso": self._curso.titulo,
                "modulos": [{"titulo": l.titulo, "codigo": l.d.get("titulo_codigo", "")} for l in self._curso.modulos],
                "paso_titulo": paso.get("titulo", ""), "donde": paso.get("donde", ""), "app": "Excel",
                "hoja": lec.hoja + (f" · {t['rango']}" if t and t.get("rango") else ""),
                "ejercicio": (t.get("titulo") or t.get("rango") or (f"macro {t['macro']}" if t.get("macro") else "")) if t else "",
                "revision": (self._revision or self._pendiente(t)) if t else None, "requisito": self._requisito,
                "tutor_ej": self._libro().estado_ejercicio() if self._libro() else None}

    def _libro(self): return getattr(self._x, "libro", None)

    def _pendiente(self, t):
        """Lo que muestra el «Tu turno» antes de pulsar Comprobar: nada de errores mientras trabaja."""
        que = f"Escribe en {t['rango']}" if t.get("solucion") else f"Escribe la macro «{t['macro']}» (Alt+F11)" if t.get("macro") else "Hazlo en Excel"
        return {"estado": "pendiente", "ok": 0, "total": 0, "mensaje": t.get("al_empezar", f"{que} y, cuando termines, pulsa Comprobar.")}

    def _requisitos(self, libro):
        """Lo que le falta a este Excel para el módulo: acceso al código VBA o el complemento Solver (no se cambia solo)."""
        lec = self._lec(); acciones = [a for p in lec.pasos for a in p.get("acciones", [])]; turnos = [p.get("turno") or {} for p in lec.pasos]
        pide = set(lec.d.get("requiere", []))
        if any("vba" in a for a in acciones) or any(t.get("macro") for t in turnos): pide.add("vba")
        if any("solver" in a for a in acciones): pide.add("solver")
        out = []
        if "vba" in pide and not motor.vba.acceso(libro.wb): out.append(motor.vba.ACCESO)
        if "solver" in pide and not motor.avanzado.solver_disponible(libro.xl):
            out.append("Este módulo usa Solver: actívalo en Archivo → Opciones → Complementos → Administrar: Complementos de Excel → Ir… → ☑ Solver.")
        return " ".join(out)

    def _empujar(self, js):
        """Ejecuta JS en la ventana del panel, si está abierta."""
        if self._ventana:
            try: self._ventana.evaluate_js(js)
            except Exception: pass

    # ----- revisión del «Tu turno»: solo al pulsar Comprobar (corre en el hilo de Excel) -----
    def _huella_turno(self, libro):
        return libro.clase(self._m).huella(self._turno())

    def _vigilar(self, libro):
        """Si cambia la zona después de comprobar, el panel avisa que el resultado ya no está al día."""
        ej = libro.ejercicio
        if ej:                         # el ejercicio del tutor, igual que el «Tu turno»
            try: h = libro.huella_ejercicio()
            except Exception: h = None
            if h != self._huella_ej:
                self._huella_ej = h
                if ej.get("revision") and not ej["revision"].get("viejo"):
                    ej["revision"] = dict(ej["revision"], viejo=True); self._empujar("window.ejercicioCambio && window.ejercicioCambio()")
        if not self._turno(): return
        huella = self._huella_turno(libro)
        if huella == self._huella: return
        self._huella = huella
        if self._revision and not self._revision.get("viejo"):
            self._revision = dict(self._revision, viejo=True)
            self._empujar("window.turnoCambio()")

    def _vigilar_seguro(self, libro):
        """Mientras escribe en una celda (antes de Enter) Excel no deja leer nada: se espera a la próxima vuelta."""
        try: self._vigilar(libro)
        except Exception: pass

    def _revisar_ya(self, libro):
        """Al entrar en un paso: sin resultado ni marcos de la revisión anterior."""
        self._revision = None; self._huella = None
        if self._turno():
            try: libro.clase(self._m).borrar_comprobacion(); self._huella = self._huella_turno(libro)
            except Exception: pass

    def comprobar(self):
        """Botón «Comprobar» del «Tu turno»: revisa ahora, marca las celdas en verde o rojo y lo manda al panel."""
        t = self._turno()
        if not t: return {"revision": None}
        def hacer(libro):
            rev = libro.clase(self._m).revisar(t)
            self._huella = self._huella_turno(libro)
            return rev
        try: self._revision = self._x.hacer(hacer)
        except Exception:
            return {"aviso": "Excel está ocupado: termina de escribir en la celda (Enter o Esc) y vuelve a pulsar Comprobar."}
        return {"revision": self._revision}

    # ----- navegación -----
    def ir(self, n):
        n = max(0, min(len(self._lec()) - 1, int(n)))
        def hacer(libro):
            clase = libro.clase(self._m)
            self._texto = clase.ir(n); self._n = n
            libro.olvidar_marcas(clase.ws.Name)    # la hoja del módulo se rehízo: sus marcas se fueron (las de otras hojas siguen)
            ej = libro.ejercicio            # si el ejercicio del tutor está en esta hoja, sus marcos se fueron al rehacerla
            if ej and ej["hoja"].lower() == clase.ws.Name.lower(): ej["revision"] = None
            self._revisar_ya(libro); libro.guardar()
            try: self._requisito = self._requisitos(libro)
            except Exception: self._requisito = ""
        try: self._x.hacer(hacer); self._guardar_progreso(); return self._estado()
        except Exception as e: return self._estado(f"No pude hacer este paso en Excel. {PISTA} ({e})")

    def modulo(self, m):
        m = max(0, min(len(self._curso.modulos) - 1, int(m)))
        self._m, self._n, self._texto = m, 0, ""
        return self.ir(0)

    def estado(self):
        return self.ir(self._n) if not self._texto else self._estado()

    # ----- tutor -----
    def preguntar(self, pregunta, adjuntos=None):
        """adjuntos: capturas, PDF o textos que manda la página (formato en motor.mensaje)."""
        pregunta = (pregunta or "").strip()
        if not pregunta and not adjuntos: return {"texto": ""}
        pregunta = pregunta or "Mira lo que te adjunto."
        t = self._turno()
        def leer(libro):        # el tutor recibe la revisión de ahora mismo, sin dibujar nada en la hoja
            clase = libro.clase(self._m)
            return clase.contexto(self._n, self._texto, clase.revisar(t, dibujar=False) if t else None) + libro.contexto_extra(self._m)
        try: ctx = self._x.hacer(leer)
        except Exception: return {"texto": f"No pude leer la hoja. {PISTA}"}
        if self._notas: ctx = "[Del panel] " + " ".join(self._notas) + "\n" + ctx; self._notas = []
        def trozo(t): self._empujar(f"window.trozoTutor({json.dumps(t)})")   # el texto llega a pedazos
        try: resp = self._tutor.preguntar(ctx, pregunta, trozo, adjuntos)
        except ValueError as e: return {"texto": str(e)}             # un adjunto que no se admite
        except Exception as e: return {"texto": f"No pude hablar con el tutor ({e}). Intenta otra vez."}
        texto, marcas = motor.separar(resp)
        texto, prop, error = motor.separar_acciones(texto)     # varios bloques <acciones> → una sola propuesta
        hechas = 0
        if marcas:      # cada marca en su hoja (la que tiene al frente, o la que diga "hoja"); nada se pierde en silencio
            try: r = self._x.hacer(lambda libro: libro.dibujar_marcas(marcas, self._m))
            except Exception: texto += f"\n\n(No pude dibujar las marcas: {PISTA})"; r = None
            if r:
                hechas = r["hechas"]
                if r.get("vba"): texto += f"\n\n(Marqué {r['vba']} línea{'s' if r['vba'] > 1 else ''} de tu código con «' ← tutor:»: ábrelo con Alt+F11. Se quitan con «Borrar marcas».)"
                if r["fallos"]:
                    texto += f"\n\n(No pude poner {len(r['fallos'])} de las marcas: {'; '.join(r['fallos'])}.)"
                    self._notas.append(f"De tus últimas marcas, estas no se dibujaron: {'; '.join(r['fallos'])}.")
                try: frente = self._x.hacer(lambda libro: libro.frente().Name)
                except Exception: frente = None
                otras = [h for h in r["hojas"] if frente is None or h.lower() != frente.lower()]
                if otras: texto += "\n\n(Las marcas están en la hoja " + " y ".join(f"«{h}»" for h in otras) + ": ábrela para verlas.)"
        out = {"texto": texto, "marcas": hechas}
        if prop:
            try:
                out["propuesta"] = self._x.hacer(lambda libro: libro.preparar(prop, self._m))
                descartes = out["propuesta"].get("descartes") or []
                if descartes: error = "; ".join([error] * bool(error) + descartes)
            except ValueError as e: error = "; ".join([error] * bool(error) + [str(e)])
            except Exception: out["propuesta_error"] = f"No pude leer la hoja para preparar el cambio que propone. {PISTA}"
        if error:
            if "propuesta" in out:          # se usó una parte: la tarjeta trae solo lo que vale
                out["propuesta_error"] = f"Parte de lo que propuso el tutor no se puede usar ({error}). La tarjeta trae solo el resto."
                self._notas.append(f"De tus últimas <acciones>, esto no se pudo usar y NO está en la tarjeta: {error}. El resto sí.")
            else:
                out["propuesta_error"] = f"El tutor propuso un cambio que no se puede usar ({error}). Pídeselo otra vez."
                self._notas.append(f"Tus últimas <acciones> no se pudieron usar: {error}. Si hace falta, propón un bloque corregido.")
        return out

    # ----- cambios que propone el tutor: solo con permiso (Aplicar), y se pueden deshacer -----
    def _cambio(self, f, que):
        """Corre f(libro) en el hilo de Excel y devuelve la tarjeta actualizada y el ejercicio del tutor."""
        try: tarjeta = self._x.hacer(f)
        except KeyError: return {"aviso": "Esa propuesta ya no existe (¿reiniciaste el panel?)."}
        except Exception: return {"aviso": f"Excel está ocupado. {PISTA}"}
        if tarjeta["estado"] in ("aplicada", "rechazada", "deshecha"):
            self._notas.append(f"La persona {que} tu propuesta «{tarjeta['resumen']}».")
        elif tarjeta["estado"] == "error" and que == "APLICÓ":      # falló al aplicarla: todo volvió atrás y el tutor lo sabe
            self._notas.append(f"Tu propuesta «{tarjeta['resumen']}» falló al aplicarla y no cambió nada: {tarjeta['mensaje']}")
        if tarjeta["estado"] == "aplicada" and self._libro().ejercicio:
            try: self._huella_ej = self._x.hacer(lambda libro: libro.huella_ejercicio())
            except Exception: pass
        return {"propuesta": tarjeta, "tutor_ej": self._libro().estado_ejercicio()}

    def aplicar(self, pid):
        """Botón «Aplicar» de la tarjeta de permiso."""
        return self._cambio(lambda libro: libro.aplicar(pid), "APLICÓ")

    def rechazar(self, pid):
        """Botón «No»: no se toca nada."""
        return self._cambio(lambda libro: libro.rechazar(pid), "NO aplicó")

    def deshacer(self, pid, forzar=False):
        """Botón «Deshacer» (con forzar=True, «Borrar igual» cuando la persona escribió en la hoja creada)."""
        return self._cambio(lambda libro: libro.deshacer(pid, bool(forzar)), "DESHIZO")

    # ----- el ejercicio que armó el tutor: se revisa con su propio Comprobar, sin IA -----
    def comprobar_ejercicio(self):
        def hacer(libro):
            rev = libro.comprobar_ejercicio()
            self._huella_ej = libro.huella_ejercicio() if rev else None
            return libro.estado_ejercicio()
        try: return {"tutor_ej": self._x.hacer(hacer)}
        except ValueError as e:              # borró la hoja del ejercicio
            self._x.hacer(lambda libro: libro.quitar_ejercicio()); return {"tutor_ej": None, "aviso": str(e)}
        except Exception:
            return {"tutor_ej": self._libro().estado_ejercicio(), "aviso": "Excel está ocupado: termina de escribir en la celda (Enter o Esc) y vuelve a pulsar Comprobar."}

    def ir_ejercicio(self):
        try: self._x.hacer(lambda libro: libro.ir_ejercicio()); return {"ok": True}
        except Exception as e: return {"ok": False, "aviso": str(e) if isinstance(e, ValueError) else f"No pude ir a la hoja. {PISTA}"}

    def quitar_ejercicio(self):
        try: self._x.hacer(lambda libro: libro.quitar_ejercicio())
        except Exception: pass
        return {"tutor_ej": None}

    def listo(self):
        """La página avisa que cargó (queda en la salida, para comprobar que la ventana abre bien)."""
        print("ventana lista", flush=True); return True

    def borrar_marcas(self):
        """Botón «Borrar marcas»: las del tutor en todas las hojas del libro del curso."""
        try: self._x.hacer(lambda libro: libro.borrar_marcas(self._m)); return {"ok": True}
        except Exception: return {"ok": False, "texto": f"No pude borrar las marcas. {PISTA}"}

    def cerrar(self):
        """Al cerrar: se borran las copias ocultas del modo libre (Deshacer ya no existirá) y se guarda."""
        try: self._x.hacer(lambda libro: (libro.limpiar_copias(), libro.guardar()))
        except Exception: pass


def foto_hoja(libro, nombre, zona="A1:I9"):
    """Todo lo que se ve de una zona (fórmulas y formato celda por celda), los anchos, las tablas y las hojas del libro:
    sirve para comprobar que Deshacer deja todo exactamente como estaba."""
    ws = libro.buscar_hoja(nombre); celdas = []
    for c in ws.Range(zona):
        celdas.append((c.Address, c.Formula, c.NumberFormat, c.Interior.ColorIndex, c.Interior.Color, c.Font.Bold, c.Font.Italic,
                       c.Font.Color, c.Font.Size, c.HorizontalAlignment, tuple(c.Borders(e).LineStyle for e in (7, 8, 9, 10))))
    anchos = tuple(ws.Columns(i).ColumnWidth for i in range(1, 11))
    tablas = tuple(sorted((lo.Name, lo.Range.Address, bool(lo.ShowTotals)) for lo in ws.ListObjects))
    return celdas, anchos, tablas, tuple(s.Name for s in libro.wb.Worksheets)


def probar_propuestas(x, api):
    """Pruebas sin IA de los cambios que propone el tutor (bloque <acciones>): tarjeta de permiso, aplicar,
    deshacer (en la hoja del módulo, en una hoja nueva y después de cambiar de paso), avisos y su ejercicio con Comprobar.
    Devuelve cuántas fallaron. Deja el libro como estaba."""
    fallos = 0
    def ver(ok, texto):
        nonlocal fallos; fallos += not ok; print(f"      {'✔' if ok else '✘'} {texto}")
    def proponer(cuerpo):
        texto, prop, err = motor.separar_acciones("Te propongo esto. <acciones>" + json.dumps(cuerpo, ensure_ascii=False) + "</acciones>")
        if err: raise ValueError(err)
        return x.hacer(lambda l: l.preparar(prop, api._m))
    lec = api._curso.modulos[0]; ult = len(lec) - 1; hoja = lec.hoja
    api.modulo(0); api.ir(ult)
    ws = lambda l, n=hoja: l.buscar_hoja(n)
    print("== Cambios que propone el tutor (sin IA)")
    antes = x.hacer(lambda l: foto_hoja(l, hoja))

    # 1. En la hoja del módulo: datos, formato, una tabla con columna calculada; luego Deshacer
    t = proponer({"para": "prueba", "cambios": [
        {"poner": "G1:H3", "valores": [["Dato", "Valor"], ["uno", 1], ["dos", 2]]}, {"negrita": "G1:H1"}, {"alinear": "G1:H1", "es": "centro"},
        {"formato_numero": "E1", "es": "0.0%"}, {"color_letra": "E1", "es": "rojo"}, {"color": "G2", "es": "verde"}, {"bordes": "G1:H3"},
        {"ancho": "G:H", "valor": 18}, {"tabla": "G1:H3", "nombre": "PruebaTutor", "estilo": "TableStyleLight9"},
        {"columna_tabla": "PruebaTutor", "nombre": "Doble", "formula": "=[@Valor]*2"}]})
    ver(t["estado"] == "pendiente" and not t["avisos"], f"tarjeta de permiso: «{t['resumen']}», sin avisos")
    ver(x.hacer(lambda l: foto_hoja(l, hoja)) == antes, "antes de pulsar Aplicar no cambia nada")
    r = api.aplicar(t["id"])["propuesta"]
    hecho = x.hacer(lambda l: (ws(l).Range("I3").Value, ws(l).Range("G1").Font.Bold, ws(l).Range("E1").NumberFormatLocal == motor.formato_local(l.xl, "0.0%"), ws(l).ListObjects.Count))
    ver(r["estado"] == "aplicada" and hecho == (4.0, True, True, 1), f"aplicar en la hoja del módulo → {r['mensaje']} ({hecho})")
    r = api.deshacer(t["id"])["propuesta"]
    ver(r["estado"] == "deshecha" and x.hacer(lambda l: foto_hoja(l, hoja)) == antes, f"deshacer deja la hoja exactamente igual → {r['mensaje']}")

    # 2. En una hoja nueva, con un ejercicio que se revisa con Comprobar
    nueva = "Práctica tutor"
    turno = {"titulo": "Con IVA · C2:C5", "rango": "C2:C5", "solucion": "=B2*(1+$F$1)", "al_terminar": "¡Bien! El IVA quedó fijo.",
             "errores": [{"formula": "=B2*(1+F1)", "dice": "Al copiar se corre F1: fíjala con $."},
                         {"formula": "=B2*$F$1", "dice": "Eso es solo el IVA: falta sumarle el precio."}]}
    t = proponer({"para": "ejercicio parecido", "hoja": nueva, "cambios": [
        {"poner": "A1:C1", "valores": [["Producto", "Precio", "Con IVA"]]}, {"negrita": "A1:C1"},
        {"poner": "A2:B5", "valores": [["Libro", 20], ["Goma", 1], ["Tijeras", 8], ["Carpeta", 15]]},
        {"poner": "E1", "valor": "IVA"}, {"poner": "F1", "valor": 0.12, "formato": "porcentaje"}, {"color": "F1", "es": "amarillo"},
        {"ancho": "A:C", "valor": 14}], "turno": turno})
    ver(t["nueva"] and t["ejercicio"] == "C2:C5", f"tarjeta: «{t['resumen']}»")
    r = api.aplicar(t["id"])
    ej = r.get("tutor_ej") or {}
    ver(r["propuesta"]["estado"] == "aplicada" and x.hacer(lambda l: ws(l, nueva) is not None) and ej.get("rango") == "C2:C5"
        and ej["revision"]["estado"] == "pendiente", f"aplicar crea la hoja «{nueva}» y el ejercicio «{ej.get('titulo')}» (sin comprobar)")
    for nombre, ok, detalle in x.hacer(lambda l: l.probar_turno(None, turno, hoja=l.hoja_de(nueva))):
        ver(ok, f"revisión del ejercicio: {nombre} → {detalle}")
    def escribir(f):
        def hacer(l):
            r = ws(l, nueva).Range("C2:C5"); r.ClearContents(); r.Cells(1).Formula = f
            r.Cells(1).Copy(ws(l, nueva).Range("C3:C5")); l.xl.CutCopyMode = False
        x.hacer(hacer)
    escribir("=B2*(1+$F$1)"); e = api.comprobar_ejercicio()["tutor_ej"]["revision"]
    ver(e["estado"] == "bien" and e["ok"] == 4, f"Comprobar con la solución → {e['estado']} {e['ok']}/{e['total']}: {e['mensaje']}")
    escribir("=B2*(1+F1)"); e = api.comprobar_ejercicio()["tutor_ej"]["revision"]
    ver(e["estado"] == "mal" and e["mensaje"] == turno["errores"][0]["dice"], f"Comprobar con un error típico → {e['estado']}: {e['mensaje']}")
    formas = x.hacer(lambda l: sum(1 for i in range(1, ws(l, nueva).Shapes.Count + 1)))
    ver(formas == 0, f"las marcas de Comprobar no dejan formas encima de las celdas (formas: {formas})")
    r = api.deshacer(t["id"])["propuesta"]
    ver(r["estado"] == "confirmar", f"deshacer después de escribir en la hoja pide confirmación → {r['mensaje']}")
    r = api.deshacer(t["id"], True)
    ver(r["propuesta"]["estado"] == "deshecha" and r["tutor_ej"] is None and x.hacer(lambda l: foto_hoja(l, hoja)) == antes,
        f"«Borrar igual» borra la hoja y el ejercicio; el libro queda como antes → {r['propuesta']['mensaje']}")

    # 3. Avisos: celdas que escribió la persona y la zona del Tu turno
    def como_persona(l): ws(l).Range("G5").Value = "mío"; ws(l).Range("E4").Formula = "=1"
    x.hacer(como_persona)
    t = proponer({"cambios": [{"poner": "G5", "valor": "otra cosa"}, {"poner": "E4", "valor": "=2"}]})
    ver(len(t["avisos"]) == 2 and "escribiste tú" in t["avisos"][0] and "Tu turno" in t["avisos"][1], "avisos: " + " | ".join(t["avisos"]))
    r = api.rechazar(t["id"])["propuesta"]
    ver(r["estado"] == "rechazada" and x.hacer(lambda l: ws(l).Range("G5").Value) == "mío", "«No» no toca nada")
    def limpiar(l): ws(l).Range("G5").ClearContents(); ws(l).Range("E4").ClearContents()
    x.hacer(limpiar)

    # 4. Deshacer después de cambiar de paso (la hoja del módulo se rehízo: el formato del tutor ya se fue)
    t = proponer({"cambios": [{"poner": "G1", "valor": "del tutor"}, {"negrita": "G1"}, {"poner": "H2", "valor": "=B4*2"}]})
    api.aplicar(t["id"]); api.ir(ult - 1)
    sigue = x.hacer(lambda l: (ws(l).Range("G1").Value, "[la escribiste tú, el tutor]" in l.clase(0).lineas()))
    ver(sigue == ("del tutor", True), f"al cambiar de paso, lo que escribió el tutor se conserva y el tutor lo reconoce: {sigue}")
    r = api.deshacer(t["id"])["propuesta"]; api.ir(ult)
    ver(r["estado"] == "deshecha" and x.hacer(lambda l: foto_hoja(l, hoja)) == antes, f"deshacer después de cambiar de paso → {r['mensaje']}")

    # 5. Lo que no se acepta
    malos = [({"cambios": [{"poner": "A1", "valor": "=WEBSERVICE(\"http://x\")"}]}, None), ({"cambios": [{"pintar": "A1"}]}, None),
             ({"hoja": "a/b", "cambios": [{"negrita": "A1"}]}, None), ({"cambios": [{"poner": "A1:B2", "valores": [["a"]]}]}, None),
             ({"cambios": [{"borrar": "A1:Z20"}]}, "preparar"), ({"cambios": [{"columna_tabla": "NoExiste", "nombre": "X"}]}, "preparar"),
             ({"cambios": [{"poner": "G1", "valor": 1}], "turno": {"rango": "G1", "solucion": "=1"}}, "preparar")]
    rechazados = 0
    for cuerpo, _ in malos:
        try: proponer(cuerpo)
        except ValueError: rechazados += 1
    ver(rechazados == len(malos), f"rechaza {rechazados} de {len(malos)} propuestas inválidas (fórmulas con internet, acciones o hojas no válidas, tamaño, tablas que no existen, ejercicio ya escrito)")
    texto, marcas = motor.separar('Mira. <marcas>[{"tipo": "nota", "celda": "B1"}]</marcas>')
    ver(texto == "Mira." and len(marcas) == 1 and motor.separar_acciones(texto) == ("Mira.", None, None), "sin <acciones>, separar() y el resto quedan igual (como en Dia)")
    ver(x.hacer(lambda l: foto_hoja(l, hoja)) == antes, "al terminar, la hoja del módulo está como al empezar")
    print("Cambios del tutor:", "todo bien" if not fallos else f"{fallos} caso(s) no dieron lo esperado")
    return fallos


class TutorFalso:
    """Para probar Api.preguntar sin IA: responde lo que se le diga y guarda el contexto que recibió."""
    def __init__(self): self.resp, self.ctx = "", ""
    def preguntar(self, ctx, pregunta, al_trozo=lambda t: None, adjuntos=None): self.ctx = ctx; return self.resp


def probar_hojas_y_bloques(x, api):
    """Pruebas sin IA de las marcas en la hoja que toca («hoja», la que tiene al frente, Borrar marcas en todas,
    hojas que no valen, cambio de paso) y de varios bloques <acciones> en una respuesta (una sola tarjeta, nada
    se pierde en silencio, aplicar y deshacer enteros). Usa un tutor falso. Devuelve cuántas fallaron."""
    fallos = 0
    def ver(ok, texto):
        nonlocal fallos; fallos += not ok; print(f"      {'✔' if ok else '✘'} {texto}")
    lec = api._curso.modulos[0]; ult = len(lec) - 1; hoja = lec.hoja; prac = "Práctica tutor"
    api.modulo(0); api.ir(ult)
    tutor_real, falso = api._tutor, TutorFalso(); api._tutor = falso
    def responder(resp, pregunta="¿qué tal?"): falso.resp = resp; return api.preguntar(pregunta)
    def con_marcas(*marcas, texto="Mira."): return responder(texto + " <marcas>" + json.dumps(list(marcas), ensure_ascii=False) + "</marcas>")
    def marcas_en(l, nombre):
        ws = l.buscar_hoja(nombre); formas = otras = reglas = 0
        for i in range(1, ws.Shapes.Count + 1):
            n = ws.Shapes(i).Name
            if n.startswith("tutor_"): formas += 1
            elif not n.startswith("check_"): otras += 1          # las flechas de precedentes de Excel
        fcs = ws.Cells.FormatConditions
        for i in range(1, fcs.Count + 1):
            try: reglas += fcs(i).Formula1 == motor.FORMULA_MARCA["tutor_"]
            except Exception: pass
        return formas, reglas, otras
    def al_frente(nombre): x.hacer(lambda l: l.buscar_hoja(nombre).Activate())
    frente = lambda: x.hacer(lambda l: l.frente().Name)
    def nueva_hoja(nombre):
        def hacer(l): ws = l.wb.Worksheets.Add(After=l.wb.Worksheets(l.wb.Worksheets.Count)); ws.Name = nombre
        x.hacer(hacer)
    def quitar_hoja(nombre): x.hacer(lambda l: l._borrar_hoja(l.buscar_hoja(nombre)))
    print("== Marcas en la hoja que toca y varios bloques <acciones> (sin IA)")
    antes = x.hacer(lambda l: foto_hoja(l, hoja))
    try:
        # Una práctica del tutor, como la que armó en la prueba real
        r = responder('Te armo una práctica. <acciones>{"para": "practicar", "hoja": "' + prac + '", "cambios": ['
                      '{"poner": "A1:C1", "valores": [["Producto", "Precio", "Con IVA"]]}, {"poner": "A2:B3", "valores": [["Libro", 20], ["Goma", 1]]},'
                      '{"poner": "E1", "valor": 0.12}, {"poner": "E2", "valor": "=E1*100"}], '
                      '"turno": {"rango": "C2:C3", "solucion": "=B2*(1+$E$1)"}}</acciones>')
        t = r["propuesta"]; api.aplicar(t["id"])
        ver(x.hacer(lambda l: l.buscar_hoja(prac) is not None) and frente() == prac, f"preparación: la práctica «{prac}» creada y al frente")

        # 1. Con "hoja": caen en la práctica aunque la persona tenga al frente la del módulo, sin quitarle la hoja
        al_frente(hoja)
        r = con_marcas({"tipo": "nota", "hoja": prac, "celda": "C3", "texto": "aquí falta el IVA"}, {"tipo": "marco", "hoja": prac, "rango": "C2:C3"},
                       {"tipo": "precedentes", "hoja": prac, "celda": "E2"})
        p_, m_ = x.hacer(lambda l: (marcas_en(l, prac), marcas_en(l, hoja)))
        ver(r["marcas"] == 3 and p_[0] == 2 and p_[1] == 1 and p_[2] >= 1 and m_ == (0, 0, 0),
            f"con \"hoja\": las 3 marcas en «{prac}» (formas {p_[0]}, reglas {p_[1]}, flechas {p_[2]}) y ninguna en «{hoja}» {m_}")
        ver(frente() == hoja and f"«{prac}»: ábrela" in r["texto"], f"no le cambia la hoja de delante («{frente()}») y el chat dice dónde están")
        ver("La persona tiene al frente la hoja '" + hoja + "' (la del módulo)" in falso.ctx and f"irían a '{hoja}'" in falso.ctx,
            "el [Estado actual] dice qué hoja tiene al frente y adónde irían sus marcas")

        # 2. Sin "hoja" y con la práctica al frente: caen en la práctica; las anteriores se borran
        al_frente(prac)
        r = con_marcas({"tipo": "resaltar", "rango": "C2"}, {"tipo": "nota", "celda": "C2", "texto": "fíjate"})
        p_, m_ = x.hacer(lambda l: (marcas_en(l, prac), marcas_en(l, hoja)))
        ver(r["marcas"] == 2 and p_ == (2, 1, 0) and m_ == (0, 0, 0), f"sin \"hoja\", con la práctica al frente: caen en ella y las de antes se fueron {p_} / módulo {m_}")
        ver(f"tiene al frente la hoja '{prac}' (una que creaste tú)" in falso.ctx and f"Tus marcas de ahora: 3 en '{prac}'" in falso.ctx
            and f"Hoja '{prac}'" in falso.ctx and "B2: 20" in falso.ctx,
            "el [Estado actual] trae la práctica al frente, sus marcas de ese momento y el contenido de la práctica")

        # 3. Sin "hoja" con una hoja de la persona al frente: van a la del módulo
        nueva_hoja("Mía"); al_frente("Mía")
        r = con_marcas({"tipo": "resaltar", "rango": "B4"})
        p_, m_, mia = x.hacer(lambda l: (marcas_en(l, prac), marcas_en(l, hoja), marcas_en(l, "Mía")))
        ver(r["marcas"] == 1 and m_[1] == 1 and p_ == (0, 0, 0) and mia == (0, 0, 0), f"sin \"hoja\", con una hoja suya al frente: van a «{hoja}» {m_}, nada en «Mía» ni en la práctica")
        quitar_hoja("Mía")

        # 4. Varias hojas en una respuesta, y «Borrar marcas» limpia todas
        al_frente(hoja)
        r = con_marcas({"tipo": "marco", "rango": "E4:E7"}, {"tipo": "nota", "hoja": prac, "celda": "C2", "texto": "tu ejercicio"},
                       {"tipo": "precedentes", "celda": "C7"})
        p_, m_ = x.hacer(lambda l: (marcas_en(l, prac), marcas_en(l, hoja)))
        ver(r["marcas"] == 3 and p_[0] == 2 and m_[1] == 1 and m_[2] >= 1, f"marcas en dos hojas a la vez: práctica {p_}, módulo {m_}")
        api.borrar_marcas()
        p_, m_, quedan = x.hacer(lambda l: (marcas_en(l, prac), marcas_en(l, hoja), dict(l.marcas)))
        ver(p_ == (0, 0, 0) and m_ == (0, 0, 0) and not quedan, f"«Borrar marcas» las quita en todas las hojas: práctica {p_}, módulo {m_}")

        # 5. Al cambiar de paso: se van las de la hoja del módulo; las de la práctica se quedan
        con_marcas({"tipo": "resaltar", "rango": "B4"}, {"tipo": "resaltar", "hoja": prac, "rango": "B2"})
        api.ir(ult - 1); api.ir(ult)
        p_, m_, quedan = x.hacer(lambda l: (marcas_en(l, prac), marcas_en(l, hoja), [n for n, _ in l.marcas.values()]))
        ver(m_[:2] == (0, 0) and p_[1] == 1 and quedan == [prac], f"al cambiar de paso: módulo {m_[:2]}, práctica {p_}; el tutor sabe que quedan en {quedan}")
        api.borrar_marcas()

        # 6. Hojas que no valen: la de otro módulo, otro libro, una que no existe (y se le cuenta al tutor)
        class Falso: hoja = "Otro módulo"; titulo = "Otro"; d = {}; pasos = []
        nueva_hoja("Otro módulo"); api._curso.modulos.append(Falso())
        try:
            r = con_marcas({"tipo": "resaltar", "hoja": "Otro módulo", "rango": "A1"}, {"tipo": "resaltar", "hoja": "[Libro1]Hoja1", "rango": "A1"},
                           {"tipo": "resaltar", "hoja": "No existe", "rango": "A1"}, {"tipo": "resaltar", "hoja": prac, "rango": "B2"})
            otro = x.hacer(lambda l: marcas_en(l, "Otro módulo"))
            ver(r["marcas"] == 1 and otro == (0, 0, 0) and "No pude poner 3 de las marcas" in r["texto"] and "otro módulo" in r["texto"],
                f"rechaza la hoja de otro módulo, de otro libro y una que no existe; dibuja la buena → {r['texto'].splitlines()[-1][:150]}")
            responder("Vale.")
            ver(falso.ctx.startswith("[Del panel]") and "no se dibujaron" in falso.ctx, "el tutor se entera en la próxima pregunta ([Del panel])")
            api.borrar_marcas()

            # 7. Un bloque bueno, uno con JSON malo y uno para la hoja de otro módulo: la tarjeta trae el bueno y el chat dice el resto
            r = responder('Te propongo. <acciones>{"cambios": [{"poner": "G1", "valor": "del tutor"}]}</acciones>'
                          '<acciones>{"cambios": [{"pintar": "A1"}]}</acciones><acciones>{"hoja": "Otro módulo", "cambios": [{"negrita": "A1"}]}</acciones>')
            e = r.get("propuesta_error", "")
            ver(r.get("propuesta") and r["propuesta"]["hoja"] == hoja and "bloque 2" in e and "Otro módulo" in e and "solo el resto" in e,
                f"bloques que no valen: no se pierden en silencio → {e[:170]}")
            responder("Vale.")
            ver("NO está en la tarjeta" in falso.ctx and "bloque 2" in falso.ctx, "y el tutor se entera de qué parte no se usó")
            api.rechazar(r["propuesta"]["id"])
        finally:
            api._curso.modulos.pop(); quitar_hoja("Otro módulo")

        # 8. Dos bloques (módulo + hoja nueva con ejercicio): UNA tarjeta, se aplica y se deshace entera
        al_frente(hoja); antes2 = x.hacer(lambda l: foto_hoja(l, hoja))
        r = responder('Te dejo otro ejercicio y una nota en el ejemplo. <acciones>{"para": "repasar", "cambios": [{"poner": "G1", "valor": "mira la Práctica 2"}, {"negrita": "G1"}]}</acciones> '
                      '<acciones>{"hoja": "Práctica 2", "cambios": [{"poner": "A1:B1", "valores": [["Precio", "Doble"]]}, {"poner": "A2", "valor": 4}], '
                      '"turno": {"rango": "B2", "solucion": "=A2*2"}}</acciones>')
        t = r.get("propuesta") or {}
        ver(t.get("hoja") == f"{hoja} + Práctica 2 (nueva)" and "propuesta_error" not in r and t.get("ejercicio") == "B2" and len(t.get("detalle", [])) == 5,
            f"una sola tarjeta: [{t.get('hoja')}] «{t.get('resumen')}»")
        ver(r["texto"] == "Te dejo otro ejercicio y una nota en el ejemplo.", "el texto del chat queda sin los bloques")
        a = api.aplicar(t["id"])
        hecho = x.hacer(lambda l: (l.buscar_hoja(hoja).Range("G1").Value, l.buscar_hoja("Práctica 2") is not None, l.frente().Name))
        ver(a["propuesta"]["estado"] == "aplicada" and hecho == ("mira la Práctica 2", True, "Práctica 2") and (a["tutor_ej"] or {}).get("hoja") == "Práctica 2",
            f"aplicar hace las dos hojas y deja al frente la del ejercicio → {a['propuesta']['mensaje']}")
        d = api.deshacer(t["id"])
        ver(d["propuesta"]["estado"] == "deshecha" and d["tutor_ej"] is None and x.hacer(lambda l: foto_hoja(l, hoja)) == antes2,
            f"deshacer deshace las dos (módulo igual que antes, «Práctica 2» borrada) → {d['propuesta']['mensaje']}")

        # 9. Dos bloques para la misma hoja se juntan; un segundo «turno» no se usa (y se dice)
        _, prop, err = motor.separar_acciones('<acciones>{"cambios": [{"poner": "G1", "valor": 1}]}</acciones><acciones>{"cambios": [{"poner": "G2", "valor": 2}]}</acciones>')
        t = x.hacer(lambda l: l.preparar(prop, 0))
        ver(err is None and t["hoja"] == hoja and len(t["detalle"]) == 2, f"dos bloques de la misma hoja → una parte: «{t['resumen']}»")
        api.rechazar(t["id"])
        _, prop, err = motor.separar_acciones('<acciones>{"hoja": "P3", "turno": {"rango": "A1", "solucion": "=1"}}</acciones><acciones>{"hoja": "P4", "turno": {"rango": "A1", "solucion": "=2"}}</acciones>')
        ver(len(prop["partes"]) == 1 and err and "un ejercicio" in err, f"dos «turno»: se usa el primero y se avisa → {err}")

        # 10. Si una hoja falla al aplicar, la otra también vuelve atrás
        r = responder('<acciones>{"cambios": [{"poner": "G1", "valor": "x"}]}</acciones><acciones>{"hoja": "Práctica 3", "cambios": ['
                      '{"poner": "A1:B2", "valores": [["a", "b"], [1, 2]]}, {"tabla": "A1:B2", "nombre": "TablaQueFalla"}, {"filtrar": "TablaQueFalla", "columna": "NoHay", "igual_a": "x"}]}</acciones>')
        a = api.aplicar(r["propuesta"]["id"])["propuesta"]
        ver(a["estado"] == "error" and x.hacer(lambda l: (foto_hoja(l, hoja) == antes2, l.buscar_hoja("Práctica 3") is None)) == (True, True),
            f"una acción falla en la 2.ª hoja: todo vuelve atrás → {a['mensaje'][:120]}")
    finally:
        api._tutor = tutor_real
        for pid, p in list(x.hacer(lambda l: l.propuestas).items()):       # quita lo que quede de estas pruebas
            if p["estado"] in ("aplicada", "confirmar"): api.deshacer(pid, True)
        api.borrar_marcas(); api.ir(ult)
    ver(x.hacer(lambda l: foto_hoja(l, hoja)) == antes, "al terminar, el libro está como al empezar (hojas, celdas y tablas)")
    print("Marcas y bloques:", "todo bien" if not fallos else f"{fallos} caso(s) no dieron lo esperado")
    return fallos


def foto_libro(libro):
    """Todo lo que se ve del libro, hoja por hoja (menos las internas del panel): celdas con formato, formato condicional,
    validación, tablas, gráficos, tablas dinámicas, formas, anchos, inmovilizar, y los nombres definidos.
    Sirve para comprobar que Deshacer del modo libre deja el libro EXACTAMENTE como estaba."""
    wb = libro.wb
    def t(f, d=None):
        try: return f()
        except Exception: return d
    activa = wb.ActiveSheet.Name; out = {"hojas": [], "nombres": sorted((n, v) for n, v in libro._estado_libro()["nombres"].items())}
    for ws in wb.Worksheets:
        if ws.Name.lower().startswith(motor.COPIA): continue
        out["hojas"].append((ws.Name, ws.Visible))
        ur = ws.UsedRange
        zona = ws.Range(ws.Cells(1, 1), ws.Cells(max(ur.Row + ur.Rows.Count, 12), max(ur.Column + ur.Columns.Count, 10)))
        celdas = [(c.Address, c.Formula, c.NumberFormat, c.Interior.Color, c.Font.Bold, c.Font.Color, c.MergeCells, c.HorizontalAlignment,
                   t(lambda: (c.Validation.Type, c.Validation.Formula1))) for c in zona]
        F = ws.Cells.FormatConditions
        fcs = sorted(str((F(i).Type, t(lambda: F(i).AppliesTo.Address), t(lambda: F(i).Formula1), t(lambda: F(i).Interior.Color))) for i in range(1, F.Count + 1))
        tablas = [(lo.Name, lo.Range.Address, bool(lo.ShowTotals), t(lambda: lo.TableStyle.Name)) for lo in ws.ListObjects]
        graf = sorted(str((co.Name, round(co.Left), round(co.Top), co.Chart.ChartType, co.Chart.HasTitle, t(lambda: co.Chart.ChartTitle.Text),
                           tuple(co.Chart.SeriesCollection(i).Formula for i in range(1, co.Chart.SeriesCollection().Count + 1)))) for co in ws.ChartObjects())
        din = sorted(str((pt.Name, pt.TableRange2.Address, str(pt.SourceData), tuple(f.Name for f in pt.RowFields), tuple(f.Name for f in pt.DataFields),
                          tuple(str(c.Value) for c in pt.TableRange2))) for pt in ws.PivotTables())
        formas = sorted((s.Name, s.Type) for s in ws.Shapes if not s.Name.startswith(("tutor_", "check_")))
        anchos = tuple(ws.Columns(i).ColumnWidth for i in range(1, 12))
        vent = t(lambda: motor.ventana(ws)) if ws.Visible == -1 else None
        out[ws.Name] = (celdas, fcs, tablas, graf, din, formas, anchos, vent)
    try: wb.Worksheets(activa).Activate()
    except Exception: pass
    return out


def diferencias(a, b):
    """Qué cambió entre dos foto_libro (para el mensaje de la prueba)."""
    out = []
    for k in sorted(set(a) | set(b), key=str):
        if a.get(k) != b.get(k):
            if isinstance(a.get(k), tuple) and isinstance(b.get(k), tuple):
                partes = ("celdas", "formato condicional", "tablas", "gráficos", "dinámicas", "formas", "anchos", "inmovilizar")
                out += [f"{k}: {n}" for n, x, y in zip(partes, a[k], b[k]) if x != y]
            elif k == "nombres":
                x, y = set(a[k]), set(b[k]); out.append(f"nombres: sobran {sorted(y - x)}, faltan {sorted(x - y)}")
            else: out.append(str(k))
    return out


def probar_modo_libre(x, api):
    """Pruebas sin IA del modo libre (cambios {"com": [...]}): gráfico, tabla dinámica, formato condicional, validación y nombres
    creados por el tutor; aplicar y deshacer EXACTO (comparando todo el libro); en la hoja del módulo (que siga funcionando
    con Clase); intentos peligrosos rechazados; y un fallo a mitad que vuelve atrás. Devuelve cuántas fallaron."""
    fallos = 0
    def ver(ok, texto):
        nonlocal fallos; fallos += not ok; print(f"      {'✔' if ok else '✘'} {texto}")
    lec = api._curso.modulos[0]; ult = len(lec) - 1; hoja = lec.hoja; prac = "Práctica libre"
    api.modulo(0); api.ir(ult)
    def proponer(cambios, en=prac, **extra):
        cuerpo = dict({"para": "prueba", "hoja": en, "cambios": cambios}, **extra)
        texto, prop, err = motor.separar_acciones("Te propongo. <acciones>" + json.dumps(cuerpo, ensure_ascii=False) + "</acciones>")
        if err: raise ValueError(err)
        return x.hacer(lambda l: l.preparar(prop, api._m))
    foto = lambda: x.hacer(foto_libro)
    print("== Modo libre: el modelo de objetos de Excel, con permiso y Deshacer exacto (sin IA)")
    inicio = foto()
    # Una práctica con datos, otra hoja que la usa (fórmula, gráfico y dinámica) y un nombre: lo que Deshacer no debe romper
    datos = [["Categoría", "Mes", "Ventas"], ["Útiles", "Ene", 10], ["Libros", "Ene", 25], ["Útiles", "Feb", 14], ["Arte", "Feb", 8],
             ["Libros", "Mar", 30], ["Arte", "Mar", 12], ["Útiles", "Mar", 9], ["Libros", "Abr", 18]]
    t = proponer([{"poner": "A1:C9", "valores": datos}, {"negrita": "A1:C1"}])
    api.aplicar(t["id"]); base = t["id"]
    def otra_hoja(l):
        ws = l.wb.Worksheets.Add(None, l.wb.Worksheets(l.wb.Worksheets.Count)); ws.Name = "Resumen"
        ws.Range("A1").Formula = f"=SUM('{prac}'!C2:C9)"; ws.Range("A3").Select()
        co = ws.ChartObjects().Add(150, 40, 220, 140); co.Chart.ChartType = 4
        se = co.Chart.SeriesCollection().NewSeries(); se.Values = l.buscar_hoja(prac).Range("C2:C9")
        pc = l.wb.PivotCaches().Create(1, l.buscar_hoja(prac).Range("A1:C9")); pt = pc.CreatePivotTable(ws.Range("H3"), "DinResumen")
        pt.PivotFields("Mes").Orientation = 1; pt.AddDataField(pt.PivotFields("Ventas"), "Suma", -4157)
        l.wb.Names.Add("IVA", "=0,12"); l.wb.Names.Add("Datos", f"='{prac}'!$A$1:$C$9"); l.buscar_hoja(prac).Activate()
    x.hacer(otra_hoja)
    antes = foto()

    # 1. Gráfico de columnas con título y ejes
    graf = [{"ruta": "ChartObjects.Add", "args": [260, 10, 360, 220], "guardar": "g"}, {"en": "$g", "ruta": "Chart.SetSourceData", "args": [{"rango": "B1:C9"}]},
            {"en": "$g", "ruta": "Chart.ChartType", "valor": "xlColumnClustered"}, {"en": "$g", "ruta": "Chart.HasTitle", "valor": True},
            {"en": "$g", "ruta": "Chart.ChartTitle.Text", "valor": "Ventas por mes"}, {"en": "$g", "ruta": "Chart.Axes(1).HasTitle", "valor": True},
            {"en": "$g", "ruta": "Chart.Axes(1).AxisTitle.Text", "valor": "Mes"}, {"en": "$g", "ruta": "Chart.Axes(2).HasTitle", "valor": True},
            {"en": "$g", "ruta": "Chart.Axes(2).AxisTitle.Text", "valor": "Ventas"}, {"en": "$g", "ruta": "Chart.HasLegend", "valor": False}]
    # 2. Tabla dinámica de ventas por categoría
    din = [{"en": "libro", "ruta": "PivotCaches.Create", "args": ["xlDatabase", {"rango": "A1:C9"}], "guardar": "c"},
           {"en": "$c", "ruta": "CreatePivotTable", "args": [{"rango": "F12"}, "VentasPorCategoria"], "guardar": "td"},
           {"en": "$td", "ruta": "PivotFields('Categoría').Orientation", "valor": "xlRowField"},
           {"en": "$td", "ruta": "PivotFields('Ventas')", "guardar": "v"}, {"en": "$td", "ruta": "AddDataField", "args": ["$v", "Total de ventas", "xlSum"]}]
    # 3. Formato condicional (escala de colores y una fórmula en inglés), 4. validación, 5. nombres
    fc = [{"ruta": "Range('C2:C9').FormatConditions.AddColorScale", "args": [3]},
          {"ruta": "Range('A2:B9').FormatConditions.Add", "args": ["xlExpression", None, "=AND($C2>10,$C2<20)"], "guardar": "f"},
          {"en": "$f", "ruta": "Interior.Color", "valor": 13434828}]
    val = [{"ruta": "Range('D2:D9').Validation.Add", "args": ["xlValidateList", "xlValidAlertStop", "xlBetween", "Sí,No"]},
           {"ruta": "Range('E2').Validation.Add", "args": ["xlValidateDecimal", "xlValidAlertStop", "xlBetween", "0.5", "10"]}]
    nom = [{"en": "libro", "ruta": "Names.Add", "args": ["TotalVentas", f"=SUM('{prac}'!$C$2:$C$9)"]}, {"en": "libro", "ruta": "Names('IVA').RefersTo", "valor": "=0.15"}]
    t = proponer([{"com": graf}, {"com": din}, {"com": fc}, {"com": val}, {"com": nom}, {"ordenar": "A1:C9", "por": "C", "orden": "desc"}, {"inmovilizar": "A2"}])
    ver(t["estado"] == "pendiente" and len(t["detalle"]) == 24 and any("copia" in n for n in t["notas"]),
        f"tarjeta: «{t['resumen']}» ({len(t['detalle'])} pasos en «Ver los cambios»)")
    print("        detalle, p. ej.:", " | ".join(t["detalle"][:3]))
    ver(foto() == antes, "antes de pulsar Aplicar no cambia nada")
    r = api.aplicar(t["id"])["propuesta"]
    if r["estado"] != "aplicada":
        ver(False, f"aplicar el gráfico, la dinámica, el formato, la validación y los nombres → {r['mensaje']}")
        x.hacer(lambda l: l._borrar_hoja(l.buscar_hoja("Resumen"))); api.deshacer(base, True); return fallos
    def revisar(l):
        ws = l.buscar_hoja(prac); co = ws.ChartObjects(1); ch = co.Chart; pt = ws.PivotTables("VentasPorCategoria")
        filas = {str(ws.Cells(pt.TableRange1.Row + i, pt.TableRange1.Column).Value): ws.Cells(pt.TableRange1.Row + i, pt.TableRange1.Column + 1).Value for i in range(1, 4)}
        fc2 = next(ws.Cells.FormatConditions(i) for i in range(1, ws.Cells.FormatConditions.Count + 1) if ws.Cells.FormatConditions(i).Type == 2)
        return {"grafico": (ch.ChartType, ch.ChartTitle.Text, ch.Axes(1).AxisTitle.Text, ch.Axes(2).AxisTitle.Text, ch.HasLegend),
                "dinamica": filas, "fc": (ws.Range("C2").FormatConditions.Count, fc2.Formula1), "val": (ws.Range("D5").Validation.Formula1, ws.Range("E2").Validation.Formula1),
                "nombres": (l.wb.Names("TotalVentas").RefersTo, l.wb.Names("IVA").RefersTo), "orden": ws.Range("C2").Value, "inm": motor.ventana(ws)[:3],
                "otra": l.buscar_hoja("Resumen").Range("A1").Value}
    v = x.hacer(revisar)
    ver(r["estado"] == "aplicada" and v["grafico"] == (51, "Ventas por mes", "Mes", "Ventas", False), f"aplicar → {r['mensaje'][:110]}… gráfico {v['grafico']}")
    ver(v["dinamica"] == {"Arte": 20.0, "Libros": 73.0, "Útiles": 33.0}, f"tabla dinámica por categoría: {v['dinamica']}")
    ver(v["fc"][0] >= 1 and v["fc"][1] == "=Y($C2>10;$C2<20)", f"formato condicional (la fórmula en inglés quedó en español): {v['fc']}")
    ver(v["val"] == ("Sí;No", "0,5"), f"validación (lista y decimal traducidos): {v['val']}")
    ver(v["nombres"] == (f"=SUM('{prac}'!$C$2:$C$9)", "=0.15") and v["orden"] == 30 and v["inm"] == (True, 1, 0) and v["otra"] == 126,
        f"nombres {v['nombres']}, ordenado (C2={v['orden']}), inmovilizado {v['inm']}, «Resumen» sigue sumando {v['otra']}")
    ctx = x.hacer(lambda l: (l.buscar_hoja(prac).Activate(), l.contexto_extra(0))[1])
    ver("Gráfico '" in ctx and "Tabla dinámica 'VentasPorCategoria'" in ctx and "Validación de datos en" in ctx and "TotalVentas" in ctx,
        "el [Estado actual] del tutor cuenta el gráfico, la dinámica, la validación y los nombres")
    d = api.deshacer(t["id"])["propuesta"]
    dif = diferencias(antes, foto())
    ver(d["estado"] == "deshecha" and not dif, f"deshacer deja el libro EXACTAMENTE como estaba (todas las hojas y nombres) → {d['mensaje']} {dif}")
    dep = x.hacer(lambda l: (l.buscar_hoja("Resumen").Range("A1").Formula, l.buscar_hoja("Resumen").PivotTables("DinResumen").PivotCache().Refresh() or "ok"))
    dep += (x.hacer(lambda l: l.wb.Names("Datos").RefersTo),)
    ver(dep == (f"=SUM('{prac}'!C2:C9)", "ok", f"='{prac}'!$A$1:$C$9"), f"lo que usaba la hoja sigue apuntando a ella (fórmula y dinámica de «Resumen», nombre «Datos»): {dep}")
    copias = x.hacer(lambda l: [s.Name for s in l.wb.Worksheets if s.Name.lower().startswith(motor.COPIA)])
    ver(copias == [], f"no quedan hojas internas del panel: {copias}")

    # 6. Si la persona cambió la hoja después, deshacer pregunta antes
    t = proponer([{"com": fc}]); api.aplicar(t["id"])
    x.hacer(lambda l: setattr(l.buscar_hoja(prac).Range("H1"), "Value", "mío"))
    r = api.deshacer(t["id"])["propuesta"]
    ver(r["estado"] == "confirmar" and r["confirmar_boton"] == "Deshacer igual", f"después de escribir en la hoja, deshacer pregunta → {r['mensaje'][:90]}…")
    r = api.deshacer(t["id"], True)["propuesta"]
    ver(r["estado"] == "deshecha" and not diferencias(antes, foto()), "«Deshacer igual» la deja como antes")

    # 7. Un paso que falla a mitad: todo vuelve atrás y el tutor lo sabe
    malo = graf[:4] + [{"en": "$g", "ruta": "Chart.Axes(9).HasTitle", "valor": True}]
    t = proponer([{"poner": "H1", "valor": "x"}, {"com": din}, {"com": malo}]); api._notas = []
    r = api.aplicar(t["id"])["propuesta"]
    ver(r["estado"] == "error" and "paso 5" in r["mensaje"] and not diferencias(antes, foto()), f"falla el paso 5: todo vuelve atrás → {r['mensaje'][:150]}")
    ver(any("falló al aplicarla" in n for n in api._notas), "y el tutor lo recibe en «[Del panel]»")

    # 8. Lo peligroso no se acepta (revisión sin Excel o al ejecutar, sin cambiar nada)
    peligrosos = [
        ("abrir otro libro", [{"en": "libro", "ruta": "Workbooks.Open", "args": ["C:\\\\datos.xlsx"]}]),
        ("guardar como", [{"ruta": "Parent.SaveAs", "args": ["C:\\\\copia.xlsx"]}]),
        ("ejecutar una macro", [{"en": "libro", "ruta": "Run", "args": ["Macro1"]}]),
        ("VBProject", [{"en": "libro", "ruta": "VBProject.VBComponents.Add", "args": [1]}]),
        ("cerrar Excel", [{"ruta": "Application.Quit"}]),
        ("hipervínculo", [{"ruta": "Hyperlinks.Add", "args": [{"rango": "A1"}, "http://ejemplo.com"]}]),
        ("fórmula con internet", [{"ruta": "Range('H2').Formula", "valor": "=WEBSERVICE(\"http://x\")"}]),
        ("consulta externa", [{"ruta": "QueryTables.Add", "args": ["URL;http://x", {"rango": "H1"}]}]),
        ("dinámica de una conexión externa", [{"en": "libro", "ruta": "PivotCaches.Create", "args": [2, "Conexión1"], "guardar": "c"}]),
        ("hoja de otro libro", [{"ruta": "Range(\"'[Libro1]Hoja1'!A1\").Value", "valor": 1}]),
        ("exportar el gráfico a un archivo", [{"ruta": "ChartObjects(1).Chart.Export", "args": ["C:\\\\g.png"]}]),
        ("una imagen de un archivo", [{"ruta": "Shapes.AddPicture", "args": ["C:\\\\a.png", 0, 1, 0, 0, 10, 10]}]),
        ("escribir en la hoja de otro módulo", [{"ruta": f"Range('{hoja}!A1').Value", "valor": 1}]),
        ("renombrar la hoja", [{"ruta": "Name", "valor": "Otra cosa"}]),
        ("borrar la hoja", [{"ruta": "Delete"}]),
        ("copiar la hoja (crea un libro)", [{"ruta": "Range('A1').Copy"}]),
        ("llegar al libro por Worksheet", [{"ruta": "Range('A1').Worksheet.Parent.Close"}]),
        ("una ruta como texto", [{"ruta": "Range('H3').Value", "valor": "C:\\\\Windows\\\\system32"}]),
    ]
    rechazos = []
    for nombre, pasos in peligrosos:
        try: t = proponer([{"com": pasos}])
        except ValueError as e: rechazos.append((nombre, "al revisar", str(e)[:70])); continue
        r = api.aplicar(t["id"])["propuesta"]
        if r["estado"] == "error": rechazos.append((nombre, "al ejecutar", r["mensaje"][:70]))
        else: api.deshacer(t["id"], True)
    ver(len(rechazos) == len(peligrosos) and not diferencias(antes, foto()), f"rechaza {len(rechazos)} de {len(peligrosos)} intentos peligrosos y el libro no cambia")
    for nombre, cuando, msg in rechazos[:len(peligrosos)]: print(f"        · {nombre}: {cuando} — {msg}")
    for nombre, _ in peligrosos:
        if nombre not in {n for n, _, _ in rechazos}: print(f"        ✘ NO se rechazó: {nombre}")

    # 9. En la hoja del módulo: formato condicional y gráfico; deshacer y la lección sigue funcionando (también tras cambiar de paso)
    mod_antes = x.hacer(lambda l: foto_hoja(l, hoja))
    try: proponer([{"com": din}], en=None); ver(False, "una tabla dinámica en la hoja del módulo debía rechazarse")
    except ValueError as e: ver("hoja aparte" in str(e), f"tabla dinámica en la hoja del módulo: no ({str(e)[:70]})")
    enmod = [{"ruta": "Range('C4:C7').FormatConditions.AddDatabar"}, {"ruta": "ChartObjects.Add", "args": [400, 10, 200, 120], "guardar": "g"},
             {"en": "$g", "ruta": "Chart.SetSourceData", "args": [{"rango": "B4:B7"}]}]
    t = proponer([{"com": enmod}], en=None); api.aplicar(t["id"])
    d = api.deshacer(t["id"])["propuesta"]
    ver(d["estado"] == "deshecha" and x.hacer(lambda l: foto_hoja(l, hoja)) == mod_antes, f"en la hoja del módulo: aplicar y deshacer la deja igual → {d['mensaje']}")
    api.ir(ult - 1); api.ir(ult)
    ver(x.hacer(lambda l: foto_hoja(l, hoja)) == mod_antes, "y la lección sigue funcionando (cambiar de paso y volver)")
    t = proponer([{"com": enmod}], en=None); api.aplicar(t["id"]); api.ir(ult - 1)
    r = api.deshacer(t["id"])["propuesta"]
    if r["estado"] == "confirmar": r = api.deshacer(t["id"], True)["propuesta"]
    api.ir(ult)
    ver(r["estado"] == "deshecha" and x.hacer(lambda l: foto_hoja(l, hoja)) == mod_antes and x.hacer(lambda l: l.clase(0).ws.ChartObjects().Count) == 0,
        f"deshacer después de cambiar de paso: sin gráfico y la hoja como antes → {r['mensaje']}")

    # al terminar: se quita la práctica y lo demás
    def limpiar(l):
        l._borrar_hoja(l.buscar_hoja("Resumen"))
        for n in ("IVA", "Datos"):
            try: l.wb.Names(n).Delete()
            except Exception: pass
    x.hacer(limpiar); api.deshacer(base, True)
    dif = diferencias(inicio, foto())
    ver(not dif, f"al terminar, el libro está como al empezar {dif}")
    print("Modo libre:", "todo bien" if not fallos else f"{fallos} caso(s) no dieron lo esperado")
    return fallos


class _Pruebas:
    """Lo común de las pruebas nuevas: contar fallos, proponer como el tutor y fotos del libro."""
    def __init__(self, x, api, titulo):
        self.x, self.api, self.fallos = x, api, 0
        print(f"== {titulo}")
    def ver(self, ok, texto):
        self.fallos += not ok; print(f"      {'✔' if ok else '✘'} {texto}")
        return ok
    def proponer(self, cuerpo, texto="Te propongo esto."):
        _, prop, err = motor.separar_acciones(texto + " <acciones>" + json.dumps(cuerpo, ensure_ascii=False) + "</acciones>")
        if err: raise ValueError(err)
        return self.x.hacer(lambda l: l.preparar(prop, self.api._m))
    def rechaza(self, cuerpo):
        """¿Se rechaza la propuesta (al revisarla o al aplicarla, sin cambiar nada)? Devuelve el motivo o None."""
        try: t = self.proponer(cuerpo)
        except ValueError as e: return str(e)
        r = self.api.aplicar(t["id"])["propuesta"]
        if r["estado"] == "error": return r["mensaje"]
        self.api.deshacer(t["id"], True); return None
    def foto(self): return self.x.hacer(foto_libro)
    def hoja(self, l, nombre): return l.buscar_hoja(nombre)


def foto_pq(libro):
    """Las consultas y conexiones del libro (para comprobar que Deshacer de Power Query las deja igual)."""
    return sorted(motor.avanzado.consultas(libro.wb).items()), sorted(motor.avanzado.conexiones(libro.wb))


def probar_matrices(x, api):
    """Matrices dinámicas (sin IA): el motor escribe con Formula2 (se desbordan, sin @), Evaluate en inglés, el Comprobar
    de una fórmula que se desborda (bien, error típico, #¡DESBORDAMIENTO!, a mano, con @), el [Estado actual] y que una
    fórmula de la persona que se desborda sobreviva al cambio de paso."""
    P = _Pruebas(x, api, "Matrices dinámicas (sin IA)")
    lec = api._curso.modulos[0]; ult = len(lec) - 1; prac = "Práctica matrices"
    api.modulo(0); api.ir(ult); inicio = P.foto()
    datos = [["Producto", "Categoría", "Ventas"], ["Cuaderno", "Útiles", 30], ["Lápiz", "Útiles", 12], ["Mochila", "Bolsos", 45],
             ["Regla", "Útiles", 20], ["Libro", "Lectura", 25]]
    turno = {"titulo": "FILTRAR · E2", "rango": "E2", "solucion": "=FILTER(A2:C6,C2:C6>20)",
             "errores": [{"formula": "=FILTER(A2:C6,C2:C6>=20)", "dice": "Con >= entra también la Regla."}]}
    t = P.proponer({"para": "matrices", "hoja": prac, "cambios": [{"poner": "A1:C6", "valores": datos}, {"poner": "I1", "valor": "=SORT(UNIQUE(B2:B6))"}], "turno": turno})
    a = api.aplicar(t["id"])
    hoja = lambda l: l.buscar_hoja(prac)
    sp = x.hacer(lambda l: (hoja(l).Range("I1").Formula2, motor.desborde(hoja(l).Range("I1"))))
    P.ver(a["propuesta"]["estado"] == "aplicada" and sp == ("=SORT(UNIQUE(B2:B6))", "I1:I3"), f"lo que escribe el tutor se desborda, sin @ (Formula2): {sp}")
    def escribir(*celdas):
        def hacer(l):
            ws = hoja(l); ws.Range("E2:G12").ClearContents()
            for ref, f in celdas: motor.poner_formula(ws.Range(ref), f)
        x.hacer(hacer)
    def comprobar(): return api.comprobar_ejercicio()["tutor_ej"]["revision"]
    e = comprobar(); P.ver(e["estado"] == "vacio", f"Comprobar sin escribir nada → {e['estado']}: {e['mensaje']}")
    escribir(("E2", "=FILTER(A2:C6,C2:C6>20)")); e = comprobar()
    P.ver(e["estado"] == "bien" and (e["ok"], e["total"]) == (9, 9), f"la solución (se desborda en E2:G4) → {e['estado']} {e['ok']}/{e['total']}")
    escribir(("E2", "=FILTER(A2:C6,C2:C6>=20)")); e = comprobar()
    P.ver(e["estado"] == "mal" and e["mensaje"] == turno["errores"][0]["dice"], f"error típico → {e['mensaje']}")
    escribir(("E2", "=FILTER(A2:C6,C2:C6>20)"), ("F3", "estorbo")); e = comprobar()
    P.ver(e["estado"] == "mal" and "DESBORDAMIENTO" in e["mensaje"], f"algo estorba (#¡DESBORDAMIENTO!) → {e['mensaje'][:90]}")
    escribir(("E2", "=FILTER(A2:C6,C2:C6>20)"), ("E3", "=FILTER(A2:C6,C2:C6>20)")); e = comprobar()
    P.ver(e["estado"] == "mal" and "DESBORDAMIENTO" in e["mensaje"], "la copió hacia abajo → también #¡DESBORDAMIENTO!")
    escribir(("E2", "Cuaderno"), ("F2", "Útiles"), ("G2", 30)); e = comprobar()
    P.ver(e["estado"] == "mal" and "a mano" in e["mensaje"], f"lo escribió a mano → {e['mensaje']}")
    escribir(("E2", "=@FILTER(A2:C6,C2:C6>20)")); e = comprobar()
    P.ver(e["estado"] == "mal" and "@" in e["mensaje"], f"con @ (no se desborda) → {e['mensaje'][:80]}")
    formas = x.hacer(lambda l: hoja(l).Shapes.Count)
    P.ver(formas == 0, f"las marcas de Comprobar son formato condicional, sin formas (formas: {formas})")
    lineas = x.hacer(lambda l: l.hoja_de(prac).lineas())
    P.ver("[se desborda en I1:I3: Bolsos, Lectura, Útiles]" in lineas, "el [Estado actual] muestra la fórmula desbordada y su rango")
    res = x.hacer(lambda l: l.probar_turno(None, turno, hoja=l.hoja_de(prac)))
    P.ver(all(ok for _, ok, _ in res), "probar_turno (lo que usa --probar en las lecciones) con una solución que se desborda: " + "; ".join(f"{n[:25]} → {d[:30]}" for n, _, d in res))
    t2 = {"rango": "K2", "solucion": "=SUM(C2:C6)", "errores": [{"formula": "=SUM(C2:C5)", "dice": "Te falta la última fila."}]}
    res = x.hacer(lambda l: l.probar_turno(None, t2, hoja=l.hoja_de(prac)))
    P.ver(all(ok for _, ok, _ in res), "una solución con funciones (SUM) se revisa bien: Evaluate va en inglés (antes daba #¿NOMBRE? en este Excel)")
    t3 = P.proponer({"hoja": prac, "cambios": [{"com": [{"ruta": "Range('M1').Formula", "valor": "=SEQUENCE(4)"}]}]}); api.aplicar(t3["id"])
    z = x.hacer(lambda l: motor.desborde(hoja(l).Range("M1")))
    P.ver(z == "M1:M4", f"el modo libre (Range.Formula) también escribe con Formula2: se desborda en {z}")
    api.deshacer(t3["id"], True)
    # una fórmula de la persona que se desborda, en la hoja del módulo, sigue igual al cambiar de paso
    x.hacer(lambda l: motor.poner_formula(l.clase(0).ws.Range("K1"), "=SEQUENCE(3)"))
    api.ir(ult - 1); api.ir(ult)
    k = x.hacer(lambda l: (l.clase(0).ws.Range("K1").Formula2, motor.desborde(l.clase(0).ws.Range("K1"))))
    P.ver(k == ("=SEQUENCE(3)", "K1:K3"), f"su fórmula que se desborda sigue igual al cambiar de paso (sin @): {k}")
    x.hacer(lambda l: l.clase(0).ws.Range("K1").ClearContents()); api.ir(ult - 1); api.ir(ult)
    api.deshacer(t["id"], True)
    dif = diferencias(inicio, P.foto())
    P.ver(not dif, f"al terminar, el libro está como al empezar {dif}")
    print("Matrices dinámicas:", "todo bien" if not P.fallos else f"{P.fallos} caso(s) no dieron lo esperado")
    return P.fallos


def _leccion_temporal(d):
    """Una lección escrita en un archivo temporal (para probar los pasos sin tocar las del curso)."""
    import tempfile
    ruta = os.path.join(tempfile.gettempdir(), f"leccion_prueba_{os.getpid()}.json")
    Path(ruta).write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    try: return motor.Leccion(ruta)
    finally: os.remove(ruta)


def probar_pasos(x, api):
    """Pasos de lección con modo libre y limpieza (sin IA): al cambiar de paso se quita lo que no es del paso (gráficos,
    dinámicas, formato condicional, nombres), no se duplica nada, y lo que hizo la persona (gráfico, tabla, formato
    condicional, validación) se conserva; el Comprobar de objetos no cuenta el gráfico del ejemplo."""
    P = _Pruebas(x, api, "Pasos con modo libre y limpieza (sin IA)")
    m0, n0 = api._m, api._n; inicio = P.foto()
    datos = [["Categoría", "Mes", "Ventas"], ["Útiles", "Ene", 10], ["Libros", "Ene", 25], ["Útiles", "Feb", 14], ["Arte", "Feb", 8],
             ["Libros", "Mar", 30], ["Arte", "Mar", 12], ["Útiles", "Mar", 9], ["Libros", "Abr", 18]]
    graf = [{"ruta": "ChartObjects.Add", "args": [420, 5, 260, 160], "guardar": "g"}, {"en": "$g", "ruta": "Chart.SetSourceData", "args": [{"rango": "B1:C9"}]},
            {"en": "$g", "ruta": "Chart.ChartType", "valor": "xlColumnClustered"}]
    din = [{"en": "libro", "ruta": "PivotCaches.Create", "args": ["xlDatabase", {"rango": "A1:C9"}], "guardar": "c"},
           {"en": "$c", "ruta": "CreatePivotTable", "args": [{"rango": "E12"}, "DinPasos"], "guardar": "td"},
           {"en": "$td", "ruta": "PivotFields('Categoría').Orientation", "valor": "xlRowField"},
           {"en": "$td", "ruta": "PivotFields('Ventas')", "guardar": "v"}, {"en": "$td", "ruta": "AddDataField", "args": ["$v", "Suma", "xlSum"]}]
    d = {"titulo": "Pasos libres", "hoja": "Pasos libres", "pasos": [
        {"texto": "Datos", "acciones": [{"poner": "A1:C9", "valores": datos}]},
        {"texto": "Gráfico, colores y un nombre", "acciones": [{"com": graf}, {"com": [{"ruta": "Range('C2:C9').FormatConditions.AddColorScale", "args": [3]}]},
                                                               {"com": [{"en": "libro", "ruta": "Names.Add", "args": ["TotalPasos", "=SUM('Pasos libres'!$C$2:$C$9)"]}]}]},
        {"texto": "Una dinámica", "acciones": [{"com": din}]},
        {"texto": "Tu turno", "acciones": [], "turno": {"pide": [{"grafico": {"tipo": "columnas", "datos": "B1:C9"}}]}}]}
    try: _leccion_temporal(dict(d, pasos=[{"texto": "x", "acciones": [{"com": [{"en": "libro", "ruta": "Workbooks.Open", "args": ["C:\\\\a.xlsx"]}]}]}])); malo = None
    except ValueError as e: malo = str(e)
    P.ver(bool(malo), f"una lección con modo libre peligroso no se abre: {(malo or '')[:90]}")
    lec = _leccion_temporal(d); api._curso.modulos.append(lec); m = len(api._curso.modulos) - 1
    cuenta = lambda l: (l.buscar_hoja("Pasos libres").ChartObjects().Count, l.buscar_hoja("Pasos libres").PivotTables().Count,
                        any(n.Name == "TotalPasos" for n in l.wb.Names), sum(1 for _, dd in motor.avanzado.reglas_fc(l.buscar_hoja("Pasos libres")) if dd["tipo"] == 3))
    try:
        api.modulo(m); api.ir(3)
        c = x.hacer(cuenta); P.ver(c == (1, 1, True, 1), f"paso 4: gráfico, dinámica, nombre y escala de colores del paso: {c}")
        api.ir(0); c = x.hacer(cuenta)
        P.ver(c == (0, 0, False, 0), f"al volver al paso 1 se quita lo que no es de ese paso (gráfico, dinámica, nombre, colores): {c}")
        api.ir(3); api.ir(3); c = x.hacer(cuenta)
        P.ver(c == (1, 1, True, 1), f"al volver al paso 4, una sola vez cada cosa (nada amontonado): {c}")
        e = api.comprobar()["revision"]
        P.ver(e["estado"] == "vacio", f"Comprobar de objetos: el gráfico del ejemplo no cuenta como suyo → {e['estado']}")
        def persona(l):
            ws = l.buscar_hoja("Pasos libres")
            co = ws.ChartObjects().Add(700, 5, 220, 150); co.Chart.SetSourceData(ws.Range("B1:C9")); co.Chart.ChartType = 5       # circular
            ws.Range("H1:I3").Value = [["Nota", "Valor"], ["a", 1], ["b", 2]]; lo = ws.ListObjects.Add(1, ws.Range("H1:I3"), pythoncom.Empty, 1); lo.Name = "MiTabla"
            ws.Range("A2:A9").FormatConditions.Add(2, pythoncom.Empty, "=$C2>20")
            ws.Range("J2:J4").Validation.Add(3, 1, 1, "Sí;No")
            return co.Name
        suyo = x.hacer(persona)
        e = api.comprobar()["revision"]
        P.ver(e["estado"] == "mal" and any(not p["ok"] and "circular" in p["texto"] for p in e.get("puntos", [])), f"su gráfico circular se revisa (✘ {next((p['texto'] for p in e.get('puntos', []) if not p['ok']), '')})")
        ctx = x.hacer(lambda l: l.clase(m).contexto(3, "x", l.clase(m).revisar(lec.pasos[3]["turno"], dibujar=False)))
        P.ver("✘ El gráfico es circular" in ctx, "el [Estado actual] trae los puntos de la revisión de objetos")
        api.ir(2); api.ir(3)
        def mirar(l):
            ws = l.buscar_hoja("Pasos libres")
            return (sorted(co.Chart.ChartType for co in ws.ChartObjects()), [lo.Name for lo in ws.ListObjects], ws.Range("I3").Value,
                    sum(1 for _, dd in motor.avanzado.reglas_fc(ws) if dd["tipo"] == 2), _t(lambda: ws.Range("J3").Validation.Formula1), ws.PivotTables().Count)
        v = x.hacer(mirar)
        P.ver(v == ([5, 51], ["MiTabla"], 2.0, 1, "Sí;No", 1),
              f"al cambiar de paso y volver se conserva lo suyo: su gráfico (sin tocar), su tabla, su formato condicional y su validación (se rehacen): {v}")
        x.hacer(lambda l: setattr(l.buscar_hoja("Pasos libres").ChartObjects(suyo).Chart, "ChartType", 51))
        e = api.comprobar()["revision"]
        P.ver(e["estado"] == "bien", f"cambia su gráfico a columnas → {e['estado']}: {e['mensaje']}")
        x.hacer(lambda l: l.buscar_hoja("Pasos libres").ChartObjects(suyo).Delete())
        api.ir(2); api.ir(3); c = x.hacer(cuenta)
        P.ver(c[0] == 1, f"si borra su gráfico, no vuelve a aparecer (gráficos: {c[0]})")
    finally:
        def limpiar(l):
            l._borrar_hoja(l.buscar_hoja("Pasos libres"))
            for n in list(l.wb.Names):
                if n.Name in ("TotalPasos",): n.Delete()
            l.clases.pop(m, None)
        x.hacer(limpiar); api._curso.modulos.pop(); api.modulo(m0); api.ir(n0)
    dif = diferencias(inicio, P.foto())
    P.ver(not dif, f"al terminar, el libro está como al empezar {dif}")
    print("Pasos con modo libre:", "todo bien" if not P.fallos else f"{P.fallos} caso(s) no dieron lo esperado")
    return P.fallos


def _t(f, d=None):
    try: return f()
    except Exception: return d


def probar_objetos(x, api):
    """Comprobar de ejercicios de objetos (sin IA): gráfico, tabla, dinámica, formato condicional, validación, nombre,
    orden, filtro, inmovilizar y formato de número; vacío, todo bien y tres errores (uno típico, con su mensaje)."""
    P = _Pruebas(x, api, "Comprobar de objetos (sin IA)")
    api.modulo(0); inicio = P.foto(); prac = "Práctica objetos"
    datos = [["Categoría", "Mes", "Ventas"], ["Útiles", "Ene", 10], ["Libros", "Ene", 25], ["Útiles", "Feb", 14], ["Arte", "Feb", 8],
             ["Libros", "Mar", 30], ["Arte", "Mar", 12], ["Útiles", "Mar", 9], ["Libros", "Abr", 18]]
    pide = [{"grafico": {"tipo": "columnas", "datos": "B1:C9", "titulo": "Ventas", "leyenda": False}},
            {"tabla": {"rango": "H1:I5", "nombre": "Notas", "totales": True}},
            {"dinamica": {"origen": "A1:C9", "filas": ["Categoría"], "valores": [{"campo": "Ventas", "funcion": "suma"}]}},
            {"formato_condicional": {"rango": "C2:C9", "tipo": "valor", "operador": "mayor", "valor": 20}},
            {"validacion": {"rango": "K2:K5", "tipo": "lista", "lista": ["Sí", "No"]}},
            {"nombre": {"nombre": "IVAobj", "valor": 0.12}},
            {"orden": {"rango": "M1:N6", "por": "N", "orden": "desc"}},
            {"filtro": {"rango": "A1:C9", "columna": "Categoría", "igual_a": "Útiles"}},
            {"inmovilizar": {"celda": "A2"}},
            {"formato_numero": {"rango": "C2:C9", "es": "moneda"}}]
    turno = {"titulo": "Todo junto", "pide": pide, "errores": [{"si": {"grafico": {"tipo": "circular"}}, "dice": "Un circular no compara meses: usa columnas."}]}
    malos = [{"pide": [{"pastel": {}}]}, {"pide": [{"grafico": {"color": "rojo"}}]}, {"pide": []}, {"pide": [{"tabla": {"rango": "ZZZ9999"}}]}]
    rech = sum(1 for tt in malos if P.rechaza({"hoja": prac, "cambios": [{"poner": "A1", "valor": 1}], "turno": tt}))
    P.ver(rech == len(malos), f"rechaza {rech} de {len(malos)} ejercicios de objetos mal escritos")
    t = P.proponer({"hoja": prac, "cambios": [{"poner": "A1:C9", "valores": datos}, {"poner": "H1:I5", "valores": [["Alumno", "Nota"], ["Ana", 15], ["Luis", 12], ["Eva", 18], ["Rosa", 14]]},
                                               {"poner": "M1:N6", "valores": [["Prod", "Monto"], ["a", 5], ["b", 40], ["c", 12], ["d", 33], ["e", 1]]}, {"poner": "P1", "valor": 0.12}],
                    "turno": turno})
    r = api.aplicar(t["id"]); ej = r.get("tutor_ej") or {}
    P.ver(r["propuesta"]["estado"] == "aplicada" and ej.get("titulo") == "Todo junto", f"el ejercicio de objetos se crea: «{ej.get('titulo')}» en «{ej.get('hoja')}» → {r['propuesta']['mensaje'][:70]}")
    comprobar = lambda: api.comprobar_ejercicio()["tutor_ej"]["revision"]
    e = comprobar(); P.ver(e["estado"] == "vacio", f"sin hacer nada → {e['estado']}: {e['mensaje']}")
    def todo_bien(l):
        ws = l.buscar_hoja(prac); E = pythoncom.Empty
        ws.Range("M1:N6").Sort(ws.Range("N1"), 2, E, E, E, E, E, 1)
        co = ws.ChartObjects().Add(420, 5, 300, 180); ch = co.Chart; ch.SetSourceData(ws.Range("B1:C9")); ch.ChartType = 51
        ch.HasTitle = True; ch.ChartTitle.Text = "Ventas"; ch.HasLegend = False
        lo = ws.ListObjects.Add(1, ws.Range("H1:I5"), E, 1); lo.Name = "Notas"; lo.ShowTotals = True
        pt = l.wb.PivotCaches().Create(1, ws.Range("A1:C9")).CreatePivotTable(ws.Range("S3"), "DinObj")
        pt.PivotFields("Categoría").Orientation = 1; pt.AddDataField(pt.PivotFields("Ventas"), "Suma de Ventas", -4157)
        ws.Range("C2:C9").FormatConditions.Add(1, 5, "=20")
        ws.Range("K2:K5").Validation.Add(3, 1, 1, "Sí;No")
        l.wb.Names.Add("IVAobj", f"='{prac}'!$P$1")
        ws.Range("C2:C9").NumberFormatLocal = motor.formato_local(l.xl, "$#,##0.00")
        ws.Range("A1:C9").AutoFilter(1, "Útiles")
        ws.Activate(); motor.inmovilizar(ws, "A2")
    x.hacer(todo_bien)
    e = comprobar()
    P.ver(e["estado"] == "bien" and e["ok"] == e["total"], f"todo bien → {e['estado']} {e['ok']}/{e['total']}: {e['mensaje']}")
    for p in e.get("puntos", [])[:30]: print(f"        {'✔' if p['ok'] else '✘'} {p['texto']}")
    def tres_errores(l):
        ws = l.buscar_hoja(prac); ws.ChartObjects(1).Chart.ChartType = 5                 # circular (error típico)
        for i in range(ws.Cells.FormatConditions.Count, 0, -1):
            fc = ws.Cells.FormatConditions(i)
            if fc.Type == 1: fc.Delete()
        ws.Range("C2:C9").FormatConditions.Add(1, 6, "=20")                                   # menor que, no mayor
        ws.Range("K2:K5").Validation.Delete(); ws.Range("K2:K5").Validation.Add(3, 1, 1, "Sí;Tal vez")
    x.hacer(tres_errores)
    e = comprobar(); malas = [p["texto"] for p in e.get("puntos", []) if not p["ok"]]
    P.ver(e["estado"] == "mal" and e["mensaje"] == turno["errores"][0]["dice"] and len(malas) == 3,
          f"tres errores → {e['estado']} {e['ok']}/{e['total']}; mensaje del error típico: «{e['mensaje']}»")
    for m_ in malas: print(f"        ✘ {m_}")
    formas = x.hacer(lambda l: [s.Name for s in l.buscar_hoja(prac).Shapes if s.Type != 3])
    reglas = x.hacer(lambda l: sum(1 for i in range(1, l.buscar_hoja(prac).Cells.FormatConditions.Count + 1)
                                   if _t(lambda: l.buscar_hoja(prac).Cells.FormatConditions(i).Formula1) == "=1=1"))
    P.ver(not formas and reglas >= 3, f"las marcas son formato condicional (reglas de Comprobar: {reglas}), ninguna forma encima de las celdas ({formas})")
    api._vigilar(x.hacer(lambda l: l)); x.hacer(lambda l: setattr(l.buscar_hoja(prac).ChartObjects(1).Chart, "ChartType", 51))
    api._vigilar(x.hacer(lambda l: l))
    P.ver(x.hacer(lambda l: (l.ejercicio.get("revision") or {}).get("viejo")) is True, "el vigía avisa «Cambiaste algo desde que comprobaste» al cambiar el gráfico")
    ctx = x.hacer(lambda l: l.contexto_extra(0))
    if not P.ver("pide: grafico, tabla" in ctx and "✘" in ctx, "el [Estado actual] cuenta el ejercicio de objetos con sus puntos"): print(ctx[:1500])
    def limpiar(l):
        for n in list(l.wb.Names):
            if n.Name == "IVAobj": n.Delete()
    x.hacer(limpiar); api.deshacer(t["id"], True)
    dif = diferencias(inicio, P.foto())
    P.ver(not dif, f"al terminar, el libro está como al empezar {dif}")
    print("Comprobar de objetos:", "todo bien" if not P.fallos else f"{P.fallos} caso(s) no dieron lo esperado")
    return P.fallos


def probar_power_query(x, api):
    """Power Query con límite (sin IA): crear y cargar consultas de una tabla del libro y de un archivo de la carpeta
    de datos, Deshacer exacto (hoja nueva y hoja que ya existía), cambiar una consulta (aviso de que no queda exacto)
    y 10 consultas o propuestas peligrosas rechazadas."""
    import tempfile
    P = _Pruebas(x, api, "Power Query (sin IA)")
    api.modulo(0); inicio = P.foto(); pq0 = x.hacer(foto_pq)
    carpeta = os.path.join(tempfile.gettempdir(), f"datos_prueba_{os.getpid()}"); os.makedirs(carpeta, exist_ok=True)
    Path(carpeta, "ventas.csv").write_text("Producto,Unidades\nCuaderno,4\nLápiz,10\nMochila,1\n", encoding="utf-8")
    datos_antes = api._curso.datos; api._curso.datos = carpeta
    try:
        m_limpia = ('let\n    Origen = Excel.CurrentWorkbook(){[Name="GenteP"]}[Content],\n'
                    '    Limpio = Table.TransformColumns(Origen, {{"Nombre", each Text.Proper(Text.Trim(_)), type text}}),\n'
                    '    ConEdad = Table.SelectRows(Limpio, each [Edad] <> null)\nin\n    ConEdad')
        gente = [["Nombre", "Edad"], ["  ana pérez", 20], ["LUIS GÓMEZ ", None], ["eva soto", 30]]
        t = P.proponer({"para": "limpiar", "hoja": "PQ prueba", "cambios": [{"poner": "A1:B4", "valores": gente}, {"tabla": "A1:B4", "nombre": "GenteP"},
                                                                            {"consulta": "GentePLimpia", "m": m_limpia, "cargar_en": "D1"}]})
        P.ver("consulta «GentePLimpia»" in t["resumen"] and any("Power Query" in d for d in t["detalle"]), f"tarjeta: «{t['resumen']}»")
        r = api.aplicar(t["id"])["propuesta"]
        v = x.hacer(lambda l: l.buscar_hoja("PQ prueba").Range("D1:E3").Value if l.buscar_hoja("PQ prueba") else None)
        P.ver(r["estado"] == "aplicada" and v == (("Nombre", "Edad"), ("Ana Pérez", 20.0), ("Eva Soto", 30.0)), f"crea la consulta y la carga en D1 (limpia): {v} → {r['mensaje'][:60]}")
        ctx = x.hacer(lambda l: l.contexto_extra(0))
        P.ver("Consultas de Power Query" in ctx and "«GentePLimpia» (cargada en 'PQ prueba'!D1" in ctx and "Text.Proper" in ctx, "el [Estado actual] cuenta la consulta, dónde está cargada y su M")
        d = api.deshacer(t["id"])["propuesta"]
        P.ver(d["estado"] == "deshecha" and x.hacer(foto_pq) == pq0 and not diferencias(inicio, P.foto()), f"deshacer (hoja nueva): sin hoja, sin consulta y sin conexión → {d['mensaje']}")
        # En una hoja que ya existía (sin datos de Power Query): copia para deshacer, exacto
        base = P.proponer({"hoja": "PQ base", "cambios": [{"poner": "A1:B2", "valores": [["Hola", 1], ["Chau", 2]]}, {"negrita": "A1:B1"}]})
        api.aplicar(base["id"]); antes = P.foto(); pq1 = x.hacer(foto_pq)
        t = P.proponer({"hoja": "PQ base", "cambios": [{"consulta": "VentasArchivo", "cargar_en": "D1",
                        "m": 'let\n    Origen = Csv.Document(File.Contents("{datos}/ventas.csv"), [Delimiter=",", Encoding=65001]),\n    Enc = Table.PromoteHeaders(Origen)\nin\n    Enc'}]})
        r = api.aplicar(t["id"])["propuesta"]
        v = x.hacer(lambda l: l.buscar_hoja("PQ base").Range("D1:E4").Value)
        P.ver(r["estado"] == "aplicada" and v[1][0] == "Cuaderno" and len(v) == 4, f"un archivo de la carpeta de datos ({{datos}}/ventas.csv) se carga en una hoja que ya existía: {v[1]}")
        d = api.deshacer(t["id"])["propuesta"]
        P.ver(d["estado"] == "deshecha" and not diferencias(antes, P.foto()) and x.hacer(foto_pq) == pq1, f"deshacer (hoja que ya existía) la deja exacta y sin la consulta → {d['mensaje']}")
        # Cambiar una consulta que ya existe: la tarjeta avisa que Deshacer no queda exacto; deshacer le devuelve su M
        c = P.proponer({"hoja": "PQ base", "cambios": [{"consulta": "SoloConexion", "m": 'let x = Excel.CurrentWorkbook() in x'}]}); api.aplicar(c["id"])
        t = P.proponer({"hoja": "PQ base", "cambios": [{"consulta": "SoloConexion", "m": 'let x = Excel.CurrentWorkbook(), y = Table.RowCount(x) in y'}]})
        P.ver(any("no queda exacto" in a for a in t["avisos"]), f"cambiar una consulta avisa antes: «{next((a for a in t['avisos'] if 'exacto' in a), '')[:80]}…»")
        api.aplicar(t["id"]); api.deshacer(t["id"])
        P.ver(x.hacer(lambda l: motor.avanzado.consultas(l.wb).get("SoloConexion")) == 'let x = Excel.CurrentWorkbook() in x', "deshacer le devuelve su M de antes")
        api.deshacer(c["id"], True)
        t = P.proponer({"hoja": "PQ base", "cambios": [{"actualizar": "todo"}]}) if False else None
        # Lo peligroso no se acepta
        peligrosos = [("web", 'let x = Web.Contents("http://example.com") in x'), ("ODBC", 'let x = Odbc.DataSource("dsn=x") in x'),
                      ("SQL", 'let x = Sql.Database("srv", "db") in x'), ("carpeta", 'let x = Folder.Files("C:\\\\") in x'),
                      ("archivo fuera de la carpeta", 'let x = File.Contents("C:\\\\Windows\\\\win.ini") in x'),
                      ("#shared", 'let f = Record.Field(#shared, "Web.Contents") in f("http://x")'),
                      ("Expression.Evaluate", 'let x = Expression.Evaluate("1+1") in x'), ("nombre entre comillas", 'let x = #"Web.Contents"("http://x") in x'),
                      ("ruta juntando textos", 'let x = File.Contents("{datos}" & "/ventas.csv") in x'), ("Value.NativeQuery", 'let x = Value.NativeQuery(a, "select 1") in x')]
        rech = []
        for nombre, m in peligrosos:
            mot = P.rechaza({"hoja": "PQ base", "cambios": [{"consulta": "Mala", "m": m, "cargar_en": "H1"}]})
            if mot: rech.append((nombre, mot))
            else: print(f"        ✘ NO se rechazó: {nombre}")
        P.ver(len(rech) == len(peligrosos) and not diferencias(antes, P.foto()), f"rechaza {len(rech)} de {len(peligrosos)} consultas peligrosas y el libro no cambia")
        for nombre, mot in rech: print(f"        · {nombre}: {mot[:80]}")
        mot = P.rechaza({"cambios": [{"consulta": "EnModulo", "m": 'let x = Excel.CurrentWorkbook() in x', "cargar_en": "H1"}]})
        P.ver(bool(mot) and "hoja aparte" in mot, f"no se carga en la hoja del módulo: {(mot or '')[:70]}")
        con_pq = P.proponer({"hoja": "PQ base", "cambios": [{"consulta": "EnBase", "m": 'let x = Excel.CurrentWorkbook() in x', "cargar_en": "D1"}]}); api.aplicar(con_pq["id"])
        mot = P.rechaza({"hoja": "PQ base", "cambios": [{"com": [{"ruta": "Range('K1').Value", "valor": 1}]}]})
        P.ver(bool(mot) and "Power Query" in mot, f"en una hoja con datos de Power Query, el modo libre (que copia la hoja) se rechaza: {(mot or '')[:70]}")
        t = P.proponer({"hoja": "PQ base", "cambios": [{"actualizar": "EnBase"}]})
        P.ver(any("no se deshace" in n for n in t["notas"]), "actualizar avisa que no se deshace")
        api.rechazar(t["id"]); api.deshacer(con_pq["id"], True); api.deshacer(base["id"], True)
    finally:
        api._curso.datos = datos_antes
        try: os.remove(os.path.join(carpeta, "ventas.csv")); os.rmdir(carpeta)
        except Exception: pass
    dif = diferencias(inicio, P.foto())
    P.ver(not dif and x.hacer(foto_pq) == pq0, f"al terminar, el libro está como al empezar (también consultas y conexiones) {dif}")
    print("Power Query:", "todo bien" if not P.fallos else f"{P.fallos} caso(s) no dieron lo esperado")
    return P.fallos


def probar_analisis(x, api):
    """Herramientas de análisis (sin IA): Buscar objetivo, tabla de datos y escenarios, con Deshacer exacto; Solver
    solo si está activado."""
    P = _Pruebas(x, api, "Herramientas de análisis (sin IA)")
    api.modulo(0); inicio = P.foto(); h = "Análisis"
    base = P.proponer({"hoja": h, "cambios": [{"poner": "A1:B3", "valores": [["Precio", 10], ["Unidades", 5], ["Total", "=B1*B2"]]},
                                             {"poner": "D1", "valor": "=B3"}, {"poner": "C2:C4", "valores": [[4], [5], [6]]}]})
    api.aplicar(base["id"]); antes = P.foto()
    def caso(cambios, leer, esperado, que):
        t = P.proponer({"hoja": h, "cambios": cambios})
        r = api.aplicar(t["id"])["propuesta"]; v = x.hacer(lambda l: leer(l.buscar_hoja(h)))
        P.ver(r["estado"] == "aplicada" and v == esperado, f"{que}: {v} → {r['mensaje'][:70]}")
        d = api.deshacer(t["id"])["propuesta"]
        P.ver(d["estado"] == "deshecha" and not diferencias(antes, P.foto()), f"  y deshacer lo deja exacto → {d['mensaje']}")
        return t
    caso([{"buscar_objetivo": "B3", "valor": 100, "cambiando": "B2"}], lambda ws: round(ws.Range("B2").Value, 6), 10.0, "Buscar objetivo (B3 = 100 cambiando B2)")
    caso([{"tabla_datos": "C1:D4", "columna": "B2"}], lambda ws: ws.Range("D2:D4").Value, ((40.0,), (50.0,), (60.0,)), "Tabla de datos (C1:D4, entrada B2)")
    caso([{"escenario": "Optimista", "celdas": "B1:B2", "valores": [12, 8]}, {"mostrar_escenario": "Optimista"}],
         lambda ws: (ws.Range("B3").Value, ws.Scenarios().Count), (96.0, 1), "Escenario «Optimista» creado y mostrado")
    t = P.proponer({"hoja": h, "cambios": [{"buscar_objetivo": "B3", "valor": 100, "cambiando": "B2"}]})
    P.ver(any("copia" in n for n in t["notas"]), "la tarjeta avisa que guarda una copia para deshacer"); api.rechazar(t["id"])
    solver = x.hacer(lambda l: motor.avanzado.solver_disponible(l.xl))
    mot = P.rechaza({"hoja": h, "cambios": [{"solver": "B3", "tipo": "max", "cambiando": "B2", "restricciones": [{"celda": "B2", "es": "<=", "valor": 10}]}]})
    if solver: P.ver(mot is None, "Solver está activado: maximiza B3 con B2 ≤ 10 (aplicar y deshacer)")
    else: P.ver(bool(mot) and "Solver no está activado" in mot, f"Solver no está activado en este Excel: se rechaza con un mensaje claro ({(mot or '')[:60]})")
    malos = [{"buscar_objetivo": "B3:B4", "valor": 1, "cambiando": "B2"}, {"tabla_datos": "C1:D4"}, {"escenario": "X", "celdas": "B1:B2", "valores": [1]},
             {"solver": "B3", "cambiando": "B2", "restricciones": [{"celda": "B2", "es": "~", "valor": 1}]}]
    rech = sum(1 for c in malos if P.rechaza({"hoja": h, "cambios": [c]}))
    P.ver(rech == len(malos), f"rechaza {rech} de {len(malos)} acciones de análisis mal escritas")
    api.deshacer(base["id"], True)
    dif = diferencias(inicio, P.foto())
    P.ver(not dif, f"al terminar, el libro está como al empezar {dif}")
    print("Herramientas de análisis:", "todo bien" if not P.fallos else f"{P.fallos} caso(s) no dieron lo esperado")
    return P.fallos


def probar_vba(x, api):
    """VBA (sin IA): análisis estático (lo peligroso se rechaza, lo normal pasa), el vigía de bucles, el acceso al
    proyecto y, si está activado, insertar y deshacer código, marcar líneas y el Comprobar de una macro."""
    P = _Pruebas(x, api, "VBA (sin IA)")
    api.modulo(0); inicio = P.foto()
    peligrosos = [
        ("Shell", 'Sub A()\n    Shell "cmd /c del x"\nEnd Sub'), ("Kill", 'Sub A()\n    Kill "C:\\x.txt"\nEnd Sub'),
        ("Open For Output", 'Sub A()\n    Open "C:\\x.txt" For Output As #1\n    Print #1, "hola"\n    Close #1\nEnd Sub'),
        ("CreateObject WScript.Shell", 'Sub A()\n    Dim o As Object\n    Set o = CreateObject("WScript.Shell")\nEnd Sub'),
        ("CreateObject MSXML", 'Sub A()\n    Set o = CreateObject("MSXML2.XMLHTTP")\nEnd Sub'),
        ("Declare PtrSafe / URLDownloadToFile", 'Private Declare PtrSafe Function URLDownloadToFile Lib "urlmon" (ByVal a As LongPtr) As Long\nSub A()\nEnd Sub'),
        ("SendKeys", 'Sub A()\n    SendKeys "%{F4}"\nEnd Sub'), ("Application.Run", 'Sub A()\n    Application.Run "Otra"\nEnd Sub'),
        ("Workbooks.Open", 'Sub A()\n    Workbooks.Open "C:\\a.xlsx"\nEnd Sub'), ("SaveAs", 'Sub A()\n    ThisWorkbook.SaveAs "C:\\b.xlsm"\nEnd Sub'),
        ("VBProject", 'Sub A()\n    ThisWorkbook.VBProject.VBComponents.Add 1\nEnd Sub'), ("Environ", 'Sub A()\n    Range("A1").Value = Environ("USERNAME")\nEnd Sub'),
        ("CallByName", 'Sub A()\n    CallByName Application, "Quit", VbMethod\nEnd Sub'), ("ExecuteExcel4Macro", 'Sub A()\n    ExecuteExcel4Macro "CALL(""x"")"\nEnd Sub'),
        ("SaveSetting (registro)", 'Sub A()\n    SaveSetting "a", "b", "c", "d"\nEnd Sub'), ("Evaluate con [ ]", 'Sub A()\n    x = [CALL("kernel32","x")]\nEnd Sub'),
        ("GetObject", 'Sub A()\n    Set o = GetObject("winmgmts:")\nEnd Sub'), ("Auto_Open (se ejecuta sola)", 'Sub Auto_Open()\n    Range("A1").Value = 1\nEnd Sub'),
        ("Worksheet_Change (evento)", 'Private Sub Worksheet_Change(ByVal Target As Range)\nEnd Sub'), ("AddIns", 'Sub A()\n    AddIns("x").Installed = True\nEnd Sub'),
        ("Application.OnTime", 'Sub A()\n    Application.OnTime Now, "A"\nEnd Sub'), ("Name … As (renombrar archivos)", 'Sub A()\n    Name "C:\\a.txt" As "C:\\b.txt"\nEnd Sub'),
        ("partido con « _»", 'Sub A()\n    Application. _\n        Run "Otra"\nEnd Sub'), ("Dir (leer carpetas)", 'Sub A()\n    x = Dir("C:\\*.*")\nEnd Sub'),
    ]
    rech = []
    for nombre, cod in peligrosos:
        try: motor.vba.analizar(cod, "tutor"); print(f"        ✘ NO se rechazó: {nombre}")
        except ValueError as e: rech.append((nombre, str(e)))
    P.ver(len(rech) == len(peligrosos), f"análisis estático: rechaza {len(rech)} de {len(peligrosos)} macros peligrosas")
    for nombre, mot in rech[:6]: print(f"        · {nombre}: {mot[:90]}")
    buenos = ['Sub Negrita()\n    Dim c As Range\n    For Each c In Range("A2:A9")\n        If c.Value = "Total" Then c.Font.Bold = True \' total\n    Next c\n    MsgBox "Listo"\nEnd Sub',
              'Function Doble(x As Double) As Double\n    Dim d As Object: Set d = CreateObject("Scripting.Dictionary")\n    Doble = x * 2\nEnd Function',
              'Sub Comentarios()\n    \' Shell, Kill y Workbooks en un comentario no cuentan\n    Range("A1").Value = "Shell y Kill en un texto tampoco"\nEnd Sub']
    ok = [b for b in buenos if not motor.vba.problemas(b, "tutor")]
    P.ver(len(ok) == len(buenos), f"lo normal pasa ({len(ok)} de {len(buenos)}: bucles, MsgBox, Scripting.Dictionary, palabras en comentarios y textos)")
    ins = motor.vba.instrumentar(buenos[0])
    P.ver("tutorVigia: Next c" in ins and "Private Function MsgBox" in ins and "Private Function InputBox" in ins,
          "el vigía va antes de cada Next/Loop/GoTo y MsgBox/InputBox no se quedan esperando")
    acceso = x.hacer(lambda l: motor.vba.acceso(l.wb))
    print(f"        acceso al proyecto de VBA: {'activado' if acceso else 'NO activado'}")
    turno = {"macro": "NegritaTotales", "rango": "A1:B4",
             "solucion_vba": 'Sub NegritaTotales()\n    Dim c As Range\n    For Each c In Range("A2:A4")\n        If c.Value = "Total" Then c.Resize(1, 2).Font.Bold = True\n    Next c\nEnd Sub',
             "errores": [{"vba": 'Sub NegritaTotales()\n    Range("A2:B4").Font.Bold = True\nEnd Sub', "dice": "Pusiste en negrita toda la tabla."}]}
    t = P.proponer({"hoja": "VBA prueba", "cambios": [{"poner": "A1:B4", "valores": [["Concepto", "Monto"], ["Uno", 1], ["Total", 1], ["Dos", 2]]}], "turno": turno})
    api.aplicar(t["id"])
    comprobar = lambda: api.comprobar_ejercicio()["tutor_ej"]["revision"]
    if not acceso:
        mot = P.rechaza({"cambios": [{"vba": "Macros", "codigo": buenos[0]}]})
        P.ver(bool(mot) and "Confiar en el acceso" in mot, f"sin acceso, proponer código se rechaza y explica cómo activarlo: {(mot or '')[:80]}…")
        e = comprobar()
        P.ver(e["estado"] == "vacio" and "Confiar en el acceso" in e["mensaje"], "sin acceso, Comprobar de un ejercicio de VBA explica cómo activarlo (y no ejecuta nada)")
        r = x.hacer(lambda l: l.dibujar_marcas([{"tipo": "linea", "modulo": "Module1", "linea": 2, "texto": "x"}], 0))
        P.ver(r["fallos"] and "sin acceso" in r["fallos"][0], f"sin acceso, marcar líneas no se puede y se dice: {r['fallos'][0][:60]}")
        print("        (sin probar por falta de acceso: insertar y deshacer código, marcar líneas en el editor y ejecutar el Comprobar de una macro)")
    else:
        t2 = P.proponer({"cambios": [{"vba": "MacrosTutor", "codigo": buenos[0]}]})
        P.ver(t2["codigos"] and "Sub Negrita()" in t2["codigos"][0]["texto"], "la tarjeta muestra el código entero")
        r = api.aplicar(t2["id"])["propuesta"]
        hay = x.hacer(lambda l: any(n == "MacrosTutor" for n, _, _ in motor.vba.modulos(l.wb)))
        P.ver(r["estado"] == "aplicada" and hay, f"aplicar crea el módulo MacrosTutor → {r['mensaje']}")
        r = x.hacer(lambda l: l.dibujar_marcas([{"tipo": "linea", "modulo": "MacrosTutor", "linea": 4, "texto": "mira esta condición"}], 0))
        txt = x.hacer(lambda l: motor.vba._texto(next(c for c in l.wb.VBProject.VBComponents if c.Name == "MacrosTutor")))
        P.ver(r["vba"] == 1 and "' ← tutor: mira esta condición" in txt, "marca una línea con un comentario temporal encima")
        x.hacer(lambda l: l.borrar_marcas(0))
        txt = x.hacer(lambda l: motor.vba._texto(next(c for c in l.wb.VBProject.VBComponents if c.Name == "MacrosTutor")))
        P.ver("← tutor" not in txt, "«Borrar marcas» quita el comentario")
        d = api.deshacer(t2["id"])["propuesta"]
        hay = x.hacer(lambda l: any(n == "MacrosTutor" for n, _, _ in motor.vba.modulos(l.wb)))
        P.ver(d["estado"] == "deshecha" and not hay, f"deshacer quita el módulo → {d['mensaje']}")
        def escribir(cod):
            def hacer(l):
                vbp = l.wb.VBProject; comp = next((c for c in vbp.VBComponents if c.Name == "MiModulo"), None) or vbp.VBComponents.Add(1)
                comp.Name = "MiModulo"; cm = comp.CodeModule
                if cm.CountOfLines: cm.DeleteLines(1, cm.CountOfLines)
                cm.AddFromString(cod.replace("\n", "\r\n"))
            x.hacer(hacer)
        escribir(turno["solucion_vba"]); e = comprobar()
        P.ver(e["estado"] == "bien", f"Comprobar con la macro bien hecha → {e['estado']}: {e['mensaje']}")
        escribir(turno["errores"][0]["vba"]); e = comprobar()
        P.ver(e["estado"] == "mal" and e["mensaje"] == turno["errores"][0]["dice"], f"con el error típico → {e['mensaje']}")
        escribir('Sub NegritaTotales()\n    Dim i As Long\n    Do While True\n        i = i + 1\n    Loop\nEnd Sub'); e = comprobar()
        P.ver(e["estado"] == "mal" and "corté" in e["mensaje"], f"un bucle que no termina se corta → {e['mensaje']}")
        escribir('Sub NegritaTotales()\n    Dim x As Long\n    x = 1 / 0\nEnd Sub'); e = comprobar()
        P.ver(e["estado"] == "mal" and "error" in e["mensaje"].lower(), f"un error al ejecutar se dice → {e['mensaje'][:80]}")
        escribir('Sub NegritaTotales()\n    Kill "C:\\x.txt"\nEnd Sub'); e = comprobar()
        P.ver(e["estado"] == "mal" and "seguridad" in e["mensaje"], f"lo peligroso no se ejecuta → {e['mensaje'][:80]}")
        abiertos = x.hacer(lambda l: [w.Name for w in l.xl.Workbooks])
        P.ver(len(abiertos) == len(set(abiertos)) and x.hacer(lambda l: l.buscar_hoja("VBA prueba").Range("B3").Font.Bold) is False,
              f"los libros temporales se cerraron y su hoja no se tocó (libros abiertos: {abiertos})")
        x.hacer(lambda l: l.wb.VBProject.VBComponents.Remove(l.wb.VBProject.VBComponents("MiModulo")))
    api.deshacer(t["id"], True)
    perm = x.hacer(lambda l: l.macros_permitidas())
    P.ver(perm, "un libro nuevo sin guardar (lección suelta) puede tener macros; un curso con «macros»: true usa .xlsm (lo prueba --probar del curso de ejemplo)")
    dif = diferencias(inicio, P.foto())
    P.ver(not dif, f"al terminar, el libro está como al empezar {dif}")
    print("VBA:", "todo bien" if not P.fallos else f"{P.fallos} caso(s) no dieron lo esperado")
    return P.fallos


def probar_progreso(x, api):
    """Que el panel recuerde dónde se quedó (módulo y paso) en progreso_panel.json, junto a curso.json."""
    import tempfile
    P = _Pruebas(x, api, "Progreso recordado (sin IA)")
    ruta = os.path.join(tempfile.gettempdir(), f"progreso_prueba_{os.getpid()}.json"); antes = getattr(api._curso, "progreso", None)
    api._curso.progreso = ruta
    try:
        api.modulo(0); api.ir(2)
        d = json.loads(Path(ruta).read_text(encoding="utf-8"))
        P.ver((d["m"], d["n"]) == (0, 2), f"al cambiar de paso se guarda: {d}")
        otra = Api(x, api._tutor, api._curso)
        P.ver((otra._m, otra._n) == (0, 2), f"al volver a abrir el panel, empieza en el módulo {otra._m + 1}, paso {otra._n + 1}")
        x.vigia = None
        Path(ruta).write_text('{"m": 9, "n": 99}', encoding="utf-8")
        P.ver(Api(x, api._tutor, api._curso).progreso() == (0, 0), "si el archivo no cuadra con el curso (otro curso, módulos quitados), empieza desde el principio")
        x.vigia = None
    finally:
        api._curso.progreso = antes
        try: os.remove(ruta)
        except Exception: pass
    print("Progreso:", "todo bien" if not P.fallos else f"{P.fallos} caso(s) no dieron lo esperado")
    return P.fallos


def area_visible():
    """Área de la pantalla sin la barra de tareas, en píxeles lógicos (los que usa pywebview).
    Con la escala de Windows al 125 % o 150 %, un alto fijo se salía de la pantalla."""
    import ctypes.wintypes
    try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception: pass
    r = ctypes.wintypes.RECT(); ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(r), 0)
    esc = ctypes.windll.user32.GetDpiForSystem() / 96
    return r.left / esc, r.top / esc, (r.right - r.left) / esc, (r.bottom - r.top) / esc, esc


def preferencias():
    """preferencias.json junto al panel: {"tema": "claro" | "oscuro" | "auto"} (auto = el de Windows). Sin archivo: claro."""
    try: return json.loads(Path(AQUI, "preferencias.json").read_text(encoding="utf-8"))
    except Exception: return {}


def abrir_ventana(api):
    """Una sola ventana, pegada a la derecha y a todo el alto del área visible, con las pestañas Lección y Tutor."""
    import webview
    from pathlib import Path
    x0, y0, ancho, alto, _ = area_visible(); ancho_v = 460
    tema = preferencias().get("tema", "claro")
    html = Path(AQUI, "panel.html").read_text(encoding="utf-8").replace(
        "<head>", f"<head><script>window.TEMA_PANEL = {json.dumps(tema)};</script>", 1)
    api._ventana = webview.create_window(api._curso.titulo or "Clase en vivo", html=html, js_api=api,
                                         width=ancho_v, height=int(alto), x=int(x0 + ancho - ancho_v), y=int(y0),
                                         on_top=True, min_size=(360, 300), background_color="#232631" if tema == "oscuro" else "#F8F6F1")
    return api._ventana


def arrancar(ruta):
    curso = motor.Curso(ruta)
    x = HiloExcel(curso); x.start(); x.listo.wait()
    if x.error: raise x.error
    tutor = motor.Tutor(curso)
    return x, tutor, Api(x, tutor, curso)


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")     # acentos bien en cualquier consola
    except Exception: pass
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args: sys.exit("Uso: python panel_web.py <curso.json | leccion.json> [--probar | --probar-tutor] [--completo]")
    x, tutor, api = arrancar(args[0])
    if "--probar" in sys.argv or "--probar-tutor" in sys.argv:
        x.vigia = None; fallos = 0
        api._curso.progreso = None          # las pruebas no cambian dónde se quedó la persona
        if api._curso.macros:
            fmt = x.hacer(lambda l: l.wb.FileFormat); ok = fmt == 52; fallos += not ok
            print(f"Libro con macros {'✔' if ok else '✘'} {x.hacer(lambda l: l.wb.Name)} (formato {fmt}; 52 = .xlsm)")
        for m, lec in enumerate(api._curso.modulos):
            api.modulo(m); print(f"== Módulo {m + 1}: {lec.titulo} (hoja {lec.hoja})")
            if api._estado().get("requisito"): print(f"      aviso del módulo en el panel: {api._estado()['requisito'][:110]}…")
            for k in range(len(lec)):
                print(f"  [{k + 1}]", api.ir(k)["texto"])
                t = lec.pasos[k].get("turno")
                if t and not t.get("solucion"):     # ejercicio de objetos o de VBA: sin hacer nada, Comprobar no ve nada (lo del ejemplo no cuenta)
                    e = api._estado()["revision"]; c = api.comprobar()["revision"]
                    ok = e["estado"] == "pendiente" and c["estado"] == "vacio"; fallos += not ok
                    print(f"      Comprobar de {'una macro' if t.get('macro') else 'objetos'} {'✔' if ok else '✘'} antes: {e['estado']} → al pulsar sin hacer nada: {c['estado']} ({c['mensaje'][:80]})")
                elif t:       # la revisión automática: la solución debe salir bien y cada error con su mensaje
                    for nombre, ok, detalle in x.hacer(lambda l: l.probar_turno(m, t)):
                        fallos += not ok
                        print(f"      revisión {'✔' if ok else '✘'} {nombre} → {detalle}")
                    e = api._estado()["revision"]; c = api.comprobar()["revision"]   # sin pulsar nada no se ve ningún error
                    ok = e["estado"] == "pendiente" and c["estado"] == "vacio"; fallos += not ok
                    print(f"      botón Comprobar {'✔' if ok else '✘'} antes: {e['estado']} → al pulsar con la zona vacía: {c['estado']}")
                    def marcas_seleccionables(libro):    # las marcas no pueden tapar la celda: si no, el clic va a la forma
                        clase = libro.clase(m); ws = clase.ws; rng = ws.Range(t["rango"]); antes = rng.Formula
                        try:
                            rng.Cells(1).Formula = "=1"; clase.revisar(t)
                            clase.dibujar([{"tipo": "marco", "rango": t["rango"]}, {"tipo": "resaltar", "celda": rng.Cells(1).Address}])
                            formas = sum(1 for i in range(1, ws.Shapes.Count + 1) if ws.Shapes(i).Name.startswith(("check_", "tutor_")))
                            reglas = rng.Cells(1).FormatConditions.Count
                            clase.borrar_marcas(); clase.borrar_comprobacion()
                            return formas, reglas, rng.Cells(1).FormatConditions.Count
                        finally: rng.Formula = antes
                    formas, reglas, quedan = x.hacer(marcas_seleccionables)
                    ok = formas == 0 and reglas == 3 and quedan == 0; fallos += not ok
                    print(f"      marcas sin formas sobre las celdas {'✔' if ok else '✘'} formas: {formas}, reglas en la celda: {reglas}, tras borrar: {quedan}")
        # Las pruebas del motor (propuestas, marcas, modo libre y todo lo avanzado) usan el primer módulo tal como es en
        # ejemplo_leccion.json: van con la lección suelta (libro sin guardar) o con --completo. En un curso, solo sus módulos.
        if api._curso.libro is None or "--completo" in sys.argv:
            for prueba in (probar_propuestas, probar_hojas_y_bloques, probar_modo_libre, probar_matrices, probar_pasos, probar_objetos,
                           probar_power_query, probar_analisis, probar_vba, probar_progreso):
                try: fallos += prueba(x, api)
                except Exception as e:
                    import traceback; traceback.print_exc(); fallos += 1; print(f"      ✘ {prueba.__name__} se cortó: {e}")
        print("Revisión automática:", "todo bien" if not fallos else f"{fallos} caso(s) no dieron lo esperado")
        if "--probar-tutor" in sys.argv:
            t = time.time(); tutor.calentar(); tutor.preguntar("", "Responde solo: ok"); print(f"Arranque del tutor: {time.time() - t:.1f}s")
            t = time.time(); r = api.preguntar("¿De qué trata este módulo y qué tengo que hacer en el Tu turno?")
            print(f"[pregunta al tutor] {time.time() - t:.1f}s\n  {r['texto'][:300]!r}")
            tutor.cerrar()
        api.cerrar()
        if x.hacer(lambda l: l.cerrar_si_temporal()): print("Libro de prueba cerrado sin guardar.")
    else:
        import webview
        tutor.calentar()                 # la sesión del tutor arranca mientras miras el panel
        abrir_ventana(api)
        webview.start(gui="edgechromium")
        x.vigia = None; api.cerrar(); tutor.cerrar()
