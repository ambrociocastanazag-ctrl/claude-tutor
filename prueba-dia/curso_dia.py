"""Cursos de Dia como los de Excel: un `curso.json` con varios módulos (una lección JSON cada uno).

    {"titulo": "UML en Dia", "modelo_tutor": "sonnet", "modulos": ["m1_clases.json", "m2_casos.json"]}

Dónde vive cada cosa (todo junto al `curso.json`; lo de la persona y lo generado no va al repositorio):
  pasos/clase_en_vivo.dia     la pestaña de la lección en Dia (el panel le carga cada paso)            (se genera)
  pasos/<módulo>/paso_N.dia   el diagrama de cada paso, armado con el plugin; indice.json = su huella   (se genera)
  mis_diagramas/mi_<módulo>.dia  el trabajo de la persona en ese módulo (uno por módulo; nunca se pisa)  (es suyo)
  tutor/                      los ejemplos y ejercicios que crea el tutor                                (se genera)
  progreso.json               módulo y paso donde se quedó                                                (es suyo)

Un módulo (formato completo en el README de prueba-dia):
  {"titulo", "titulo_codigo", "id", "tema_tutor", "notas_tutor", "pasos": [
     {"titulo", "texto", "en_dia", "cambios": [...vocabulario de cambios_dia, el mismo del tutor...],
      "senalar": ["Libro"], "interfaz": [{"herramienta": "UML - Class"}, ...], "hazlo": {"etiqueta", "hacer": [...]}},
     {"titulo": "Tu turno", "texto", "turno": {"titulo", "al_empezar", "al_terminar", "clases"/"relaciones"/"objetos"/
       "conexiones"/"mensajes" (la solución escondida, como los ejercicios del tutor), "sinonimos", "inicial": [cambios],
       "solucion": [cambios], "errores": [{"dice", "patron": {...}, "prueba": [cambios], "consejo": false}]}}]}
Los pasos SE SUMAN como en Excel: el paso 3 es el diagrama vacío más los cambios de los pasos 1, 2 y 3.
También vale el formato del prototipo («diagrama» con la lista de clases de ese paso, y «turno» con «clase»)."""
import hashlib, json, re, shlex, shutil, time
import xml.etree.ElementTree as ET
from pathlib import Path

import dia_uml as du
import dia_objetos as do
import cambios_dia as cd
import interfaz_dia as ui

VERSION_PASOS = "5.3"            # súbela si cambia cómo se arman los pasos: así se vuelven a armar
CAMPOS_PASO = {"titulo", "texto", "en_dia", "donde", "diagrama", "cambios", "senalar", "interfaz", "hazlo", "turno", "resumen"}
CAMPOS_TURNO = {"titulo", "al_empezar", "al_terminar", "clase", "clases", "relaciones", "objetos", "conexiones", "mensajes",
                "sinonimos", "inicial", "solucion", "errores", "archivo"}
NS = du.NS["dia"]


# ---------- Validación (sin Dia): errores claros para quien escribe el curso ----------
def _cambios(lista, donde):
    if lista is None: return None
    try: return cd.validar_propuesta({"diagrama": "leccion", "cambios": lista})
    except ValueError as e: raise ValueError(f"{donde}: {e}")


def validar_turno(t, donde):
    if not isinstance(t, dict): raise ValueError(f"{donde}: «turno» es un objeto")
    sobra = set(t) - CAMPOS_TURNO
    if sobra: raise ValueError(f"{donde}, turno: campos que no conozco: {', '.join(sorted(sobra))}")
    out = dict(t)
    if "clase" not in t:                              # formato de los ejercicios del tutor: cualquier tipo de diagrama
        spec = {k: t[k] for k in ("titulo", "clases", "relaciones", "objetos", "conexiones", "mensajes", "sinonimos", "al_empezar", "al_terminar") if k in t}
        try: out["_ej"] = cd._v_ejercicio(spec)
        except ValueError as e: raise ValueError(f"{donde}, turno: {e}")
    out["_inicial"] = _cambios(t.get("inicial"), f"{donde}, turno, inicial")
    out["_solucion"] = _cambios(t.get("solucion"), f"{donde}, turno, solucion")
    errores = []
    for i, e in enumerate(t.get("errores") or [], 1):
        if not isinstance(e, dict) or not isinstance(e.get("dice"), str) or not e["dice"].strip():
            raise ValueError(f"{donde}, error típico {i}: necesita «dice» (lo que se le explica)")
        s = set(e) - {"dice", "patron", "prueba", "consejo"}
        if s: raise ValueError(f"{donde}, error típico {i}: campos que no conozco: {', '.join(sorted(s))}")
        if not isinstance(e.get("patron"), dict): raise ValueError(f"{donde}, error típico {i}: «patron» dice qué tiene que haber en el diagrama para reconocerlo")
        try: patron = cd._v_ejercicio(dict(e["patron"], titulo="error"))
        except ValueError as x: raise ValueError(f"{donde}, error típico {i}, patron: {x}")
        errores.append({"dice": e["dice"].strip(), "_patron": patron, "consejo": bool(e.get("consejo")),
                        "_prueba": _cambios(e.get("prueba"), f"{donde}, error típico {i}, prueba")})
    out["_errores"] = errores
    return out


def validar_modulo(d, nombre="módulo"):
    """Revisa un módulo entero y devuelve sus pasos limpios (con _cambios, _interfaz, _hazlo, _turno). ValueError si algo falla."""
    if not isinstance(d, dict) or not isinstance(d.get("pasos"), list) or not d["pasos"]: raise ValueError(f"{nombre}: falta «pasos» (una lista)")
    if not d.get("titulo"): raise ValueError(f"{nombre}: falta «titulo»")
    pasos = []
    for k, p in enumerate(d["pasos"], 1):
        donde = f"{nombre}, paso {k}"
        if not isinstance(p, dict) or not isinstance(p.get("texto"), str): raise ValueError(f"{donde}: cada paso lleva «texto»")
        sobra = set(p) - CAMPOS_PASO
        if sobra: raise ValueError(f"{donde}: campos que no conozco: {', '.join(sorted(sobra))}")
        if p.get("cambios") and "diagrama" in p: raise ValueError(f"{donde}: usa «cambios» (se suman) o «diagrama» (el del prototipo), no los dos")
        q = dict(p)
        q["_cambios"] = _cambios(p.get("cambios"), donde) if p.get("cambios") else None
        q["_interfaz"] = ui.validar_interfaz(p.get("interfaz"), donde)
        q["_hazlo"] = ui.validar_hazlo(p.get("hazlo"), donde)
        if p.get("senalar") is not None and not isinstance(p["senalar"], (str, list)): raise ValueError(f"{donde}: «senalar» es un nombre o una lista")
        q["_turno"] = validar_turno(p["turno"], donde) if p.get("turno") else None
        pasos.append(q)
    return pasos


# ---------- Curso y módulos ----------
class Modulo:
    def __init__(self, ruta, carpeta, ejemplo=False):
        self.ruta = Path(ruta)
        self.d = json.loads(self.ruta.read_text(encoding="utf-8"))
        self.id = re.sub(r"[^\w]+", "_", str(self.d.get("id") or re.sub(r"^m\d+_", "", self.ruta.stem))).strip("_").lower() or "modulo"
        self.titulo, self.codigo = self.d["titulo"] if self.d.get("titulo") else self.ruta.stem, self.d.get("titulo_codigo", "")
        self.pasos = validar_modulo(self.d, self.ruta.name)
        if ejemplo:                                  # el prototipo de siempre: mi_diagrama.dia y pasos/ en prueba-dia
            self.mio, self.carpeta_pasos = carpeta / "mi_diagrama.dia", carpeta / "pasos"
        else:
            self.mio, self.carpeta_pasos = carpeta / "mis_diagramas" / f"mi_{self.id}.dia", carpeta / "pasos" / self.id
        self.huella = hashlib.sha1((json.dumps(self.d, sort_keys=True, ensure_ascii=False) + VERSION_PASOS).encode("utf-8")).hexdigest()[:16]

    def archivo_paso(self, n): return self.carpeta_pasos / f"paso_{n + 1}.dia"
    def indice(self): return leer_json(self.carpeta_pasos / "indice.json") or {}
    def turno(self, n): return self.pasos[n].get("_turno")


class Curso:
    """curso.json (varios módulos) o una lección suelta (el prototipo «La clase», un solo módulo)."""

    def __init__(self, ruta):
        ruta = Path(ruta).resolve()
        d = json.loads(ruta.read_text(encoding="utf-8"))
        self.carpeta, self.ruta = ruta.parent, ruta
        if "pasos" in d:                             # lección suelta
            self.d, self.titulo = {"modelo_tutor": d.get("modelo_tutor", "sonnet")}, d.get("curso", d.get("titulo", ""))
            self.modulos = [Modulo(ruta, self.carpeta, ejemplo=True)]
            self.pasos_dir = self.carpeta / "pasos"
        else:
            if not isinstance(d.get("modulos"), list) or not d["modulos"]: raise ValueError(f"{ruta.name}: falta «modulos» (la lista de lecciones)")
            self.d, self.titulo = d, d.get("titulo", "Curso de Dia")
            self.modulos = [Modulo(self.carpeta / m, self.carpeta) for m in d["modulos"]]
            ids = [m.id for m in self.modulos]
            if len(set(ids)) != len(ids): raise ValueError(f"{ruta.name}: dos módulos con el mismo «id» ({ids})")
            self.pasos_dir = self.carpeta / "pasos"
        self.en_vivo = self.pasos_dir / "clase_en_vivo.dia"
        self.tutor_dir = self.carpeta / "tutor"
        self.progreso_ruta = self.carpeta / "progreso.json"

    # ----- progreso: dónde se quedó (módulo y paso) -----
    def progreso(self):
        p = leer_json(self.progreso_ruta) or {}
        m = p.get("m", 0) if isinstance(p.get("m"), int) and 0 <= p.get("m", 0) < len(self.modulos) else 0
        n = p.get("n", 0) if isinstance(p.get("n"), int) and 0 <= p.get("n", 0) < len(self.modulos[m].pasos) else 0
        return m, n

    def guardar_progreso(self, m, n):
        try:
            tmp = self.progreso_ruta.with_suffix(".tmp")
            tmp.write_text(json.dumps({"m": m, "n": n, "modulo": self.modulos[m].id, "cuando": time.strftime("%Y-%m-%d %H:%M")}), encoding="utf-8")
            tmp.replace(self.progreso_ruta)
        except OSError: pass


def leer_json(ruta):
    try: return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError): return None


# ---------- Revisión del «Tu turno» (sin IA), con errores típicos ----------
def revisar_turno(d, turno):
    """La revisión de siempre (una clase con «clase»; si no, la de los ejercicios del tutor: objetos, conexiones, mensajes en
    orden, guardas...) y, encima, los errores típicos del JSON: si el diagrama cumple el «patron» de uno, su «dice» pasa a ser el
    mensaje (con "consejo": true, solo cuando lo demás ya está bien)."""
    res = du.revisar(d, turno) if "clase" in turno else du.revisar_varios(d, turno["_ej"])
    if res["estado"] == "vacio": return res
    todo_bien = res["ok"] == res["total"]
    for i, e in enumerate(turno.get("_errores") or []):
        if e["consejo"] != todo_bien: continue
        pr = du.revisar_varios(d, e["_patron"])
        if pr["total"] and pr["ok"] == pr["total"]:
            res = dict(res, mensaje=e["dice"], error_tipico=i + 1)
            if e["consejo"]: res["estado"] = "casi"
            break
    return res


# ---------- Armar los pasos ----------
def _info_paso(ruta, pid, plan, senalar):
    """Qué resaltar en un paso: los objetos que se crearon (o cambiaron) en él, o los de «senalar».
    -> {"objetivos": [nombres o #id para las marcas], "refs": [REF del plugin para seleccionar]}"""
    try: d = du.leer(ruta)
    except Exception: return {"objetivos": [], "refs": []}
    if senalar:
        nombres = [senalar] if isinstance(senalar, str) else list(senalar)
        return {"objetivos": nombres, "refs": ["nombre:" + n for n in nombres]}
    obj, refs = [], []
    pre = pid + "."
    for c in d["clases"]:
        if (c.get("tag") or "").startswith(pre) or (plan and c["nombre"] in plan["cuenta"].get("cambia", [])): obj.append(c["nombre"]); refs.append(f"clase:{c['nombre']}")
    for o in d.get("objetos", []):
        if (o.get("tag") or "").startswith(pre) and o["kind"] not in ("rotulo", "linea_vida"):
            obj.append(o.get("texto") or o.get("nombre") or f"#{o['id']}"); refs.append(f"tag:{o['tag']}")
    nuevas = [r for r in d.get("relaciones", []) + d.get("lineas", []) if (r.get("tag") or "").startswith(pre)]
    refs += [f"tag:{r['tag']}" for r in nuevas]
    if not obj:                                      # solo líneas nuevas: se resaltan los objetos que unen
        for r in nuevas:
            for x in (r.get("de"), r.get("a")):
                if x and x not in obj: obj.append(x)
    return {"objetivos": obj, "refs": refs}


def _plan(cam, prop, antes, pid, medir=True):
    """El plan de cambios_dia sobre `antes`; con el plugin, con el tamaño real que Dia da a lo nuevo (orden «medir»)."""
    plan = cd.planear(prop, antes, pid)
    if medir and plan.get("medir") and cam is not None:
        f = cam.tmp / f"{pid}_medir.dia"; du.escribir_para_anadir(f, extra=plan["medir"])
        medidas = {}
        for l in cam.orden(f'medir "{f}"').splitlines():
            q = l.split("\t")
            if q[0] == "medida" and len(q) >= 7 and q[1]:
                try: medidas[q[1]] = tuple(float(v) for v in q[3:7])
                except ValueError: pass
        if medidas: plan = cd.planear(prop, antes, pid, medidas)
    return plan


def construir(mod, cam=None, pestana=None, forzar=False, con_conexiones=True):
    """Arma pasos/<módulo>/paso_N.dia. Con el plugin (`cam` = cambios_dia.Cambios del panel y `pestana` = la de la lección):
    cada paso se hace EN la pestaña de la lección como lo haría el tutor (cargar el anterior + sus cambios) y se guarda con
    «copia»: así queda exacto (tamaños de Dia, líneas pegadas de verdad). Sin plugin, se escribe el XML aquí mismo (aproximado:
    tamaños estimados y sin los «props» de color; con `con_conexiones`, las líneas llevan sus extremos para poder leerlas).
    Vuelve a armar solo si cambió el módulo (huella) o si antes se armó sin plugin y ahora lo hay."""
    modo = "vivo" if cam is not None else "offline"
    ind = mod.indice()
    hechos = all(mod.archivo_paso(n).exists() for n in range(len(mod.pasos)))
    if not forzar and hechos and ind.get("huella") == mod.huella and (ind.get("modo") == "vivo" or modo == "offline"):
        return ind
    mod.carpeta_pasos.mkdir(parents=True, exist_ok=True)
    vacio = mod.carpeta_pasos / "_vacio.dia"; du.escribir(vacio, [])
    prev, info = vacio, []
    for n, p in enumerate(mod.pasos):
        destino, pid = mod.archivo_paso(n), f"s{n + 1}"
        plan = None
        if p.get("diagrama") is not None and not p.get("_cambios"):
            du.escribir(destino, p["diagrama"])       # formato del prototipo: el paso trae su diagrama entero
            senalar = p.get("senalar") or ([p["diagrama"][0]["nombre"]] if p["diagrama"] else [])
            info.append(_info_paso(destino, pid, None, senalar)); prev = destino; continue
        if p.get("_cambios"):
            antes = du.leer(prev)
            if cam is not None:
                r = cam.orden(f'@{pestana} cargar "{prev}"')
                if not r.startswith("ok"): raise RuntimeError(f"paso {n + 1}: no pude cargar el anterior en Dia ({r[:120]})")
                plan = _plan(cam, p["_cambios"], antes, pid)
                errores = cam._ordenes_plan(pestana, plan, pid)
                if errores: raise RuntimeError(f"{mod.ruta.name}, paso {n + 1}: Dia no pudo hacerlo ({errores[0].splitlines()[-1][:160]})")
                r = cam.orden(f'@{pestana} copia "{destino}"')
                if not r.startswith("ok"): raise RuntimeError(f"paso {n + 1}: no pude guardar el paso ({r[:120]})")
            else:
                plan = _plan(None, p["_cambios"], antes, pid, medir=False)
                aplicar_offline(prev, plan, destino, con_conexiones)
        else:
            shutil.copyfile(prev, destino)            # sin cambios (el «Tu turno», un paso solo de texto): el mismo diagrama
        info.append(_info_paso(destino, pid, plan, p.get("senalar")) if p.get("_cambios") or p.get("senalar") else {"objetivos": [], "refs": []})
        prev = destino
    try: vacio.unlink()
    except OSError: pass
    ind = {"huella": mod.huella, "modo": modo, "pasos": info, "cuando": time.strftime("%Y-%m-%d %H:%M")}
    (mod.carpeta_pasos / "indice.json").write_text(json.dumps(ind, ensure_ascii=False, indent=1), encoding="utf-8")
    return ind


def crear_inicial(mod, n, cam=None, pestana=None):
    """El diagrama de la persona en un módulo: vacío o, si el «Tu turno» trae «inicial», con eso ya dibujado (para ejercicios
    como «une estos casos de uso»). Solo si no existe: su trabajo nunca se pisa."""
    if mod.mio.exists(): return False
    mod.mio.parent.mkdir(parents=True, exist_ok=True)
    t = next((p.get("_turno") for p in mod.pasos if p.get("_turno")), None)
    ini = (t or {}).get("_inicial")
    if not ini:
        du.escribir(mod.mio, []); return True
    vacio = mod.carpeta_pasos / "_vacio_ini.dia"; mod.carpeta_pasos.mkdir(parents=True, exist_ok=True); du.escribir(vacio, [])
    if cam is not None:
        cam.orden(f'@{pestana} cargar "{vacio}"')
        plan = _plan(cam, ini, du.leer(vacio), "i0")
        if cam._ordenes_plan(pestana, plan, "i0"): du.escribir(mod.mio, [])
        else: cam.orden(f'@{pestana} copia "{mod.mio}"')
    else:
        aplicar_offline(vacio, _plan(None, ini, du.leer(vacio), "i0", medir=False), mod.mio, True)
    _quitar_etiquetas(mod.mio)                       # lo inicial es «suyo»: sin la etiqueta del tutor
    try: vacio.unlink()
    except OSError: pass
    return True


def _crudo(ruta):
    """El XML de un .dia (Dia los guarda a veces comprimidos con gzip)."""
    b = Path(ruta).read_bytes()
    if b[:2] == bytes((0x1f, 0x8b)):
        import gzip; b = gzip.decompress(b)
    return b


def _quitar_etiquetas(ruta):
    t = _crudo(ruta).decode("utf-8")
    t = re.sub(r'<dia:attribute name="tutor">\s*<dia:string>#[^#]*#</dia:string>\s*</dia:attribute>', "", t)
    Path(ruta).write_text(t, encoding="utf-8")


def diagrama_de(cambios, base=None):
    """Para las pruebas: el diagrama (leído con dia_uml.leer) que queda al aplicar estos cambios a uno vacío (o a `base`)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        a, b = Path(tmp) / "a.dia", Path(tmp) / "b.dia"
        if base: shutil.copyfile(base, a)
        else: du.escribir(a, [])
        aplicar_offline(a, _plan(None, cambios, du.leer(a), "t1", medir=False), b, True)
        return du.leer(b)


# ---------- Aplicar un plan sin Dia (XML) ----------
def _q(tag): return f"{{{NS}}}{tag}"


def _meta(o, clave):
    s = o.find(f"dia:attribute[@name='meta']/dia:composite/dia:attribute[@name='{clave}']/dia:string", du.NS)
    t = (s.text or "") if s is not None else ""
    return t[1:-1] if t.startswith("#") and t.endswith("#") else t


def _nombre_obj(o):
    for n in ("name", "text"):
        a = o.find(f"dia:attribute[@name='{n}']", du.NS)
        if a is None: continue
        s = a.find("dia:string", du.NS) if a.find("dia:string", du.NS) is not None else a.find("dia:composite/dia:attribute[@name='string']/dia:string", du.NS)
        if s is not None and (s.text or "").strip("#").strip(): return (s.text or "").strip("#").strip()
    return _meta(o, "nombre")


def aplicar_offline(origen, plan, destino, con_conexiones=True):
    """Lo mismo que harían las órdenes del plugin (reemplazar, poner, quitar, anadir) pero escribiendo el XML: para --probar y
    para el modo sin plugin. Con `con_conexiones`, cada línea queda pegada (por id) a lo que dice su meta conecta_inicio/fin."""
    raiz = ET.fromstring(_crudo(origen))
    capa = next(c for c in raiz.findall("dia:layer", du.NS) if c.get("name") != du.CAPA_TUTOR)
    objs = lambda: [o for o in capa if o.tag == _q("object")]
    # 1) reemplazar (modificar clases): la clase nueva con el mismo id y en el mismo sitio
    for oid, (vieja, nueva) in plan["modificar"].items():
        o = next((x for x in objs() if x.get("id") == oid), None)
        if o is None: continue
        x = ET.fromstring(f'<r xmlns:dia="http://www.lysator.liu.se/~alla/dia/">{du._clase_xml(dict(nueva, pos=vieja["caja"][:2], tag=vieja.get("tag")), 0, oid)}</r>')[0]
        i = list(capa).index(o); capa.remove(o); capa.insert(i, x)
    # 2) poner (cambios de propiedades de lo que ya estaba), por id
    for orden in plan.get("poner_antes", []): _poner_offline(capa, orden)
    # 3) quitar
    quitar = set(plan["quitar"])
    for o in [x for x in objs() if x.get("id") in quitar]: capa.remove(o)
    _renumerar(raiz)
    # 4) anadir lo nuevo (con ids propios) y pegar las líneas
    if plan["nuevas"] or plan["relaciones"] or plan["notas"] or plan.get("extra") or plan.get("fondo"):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "n.dia"
            du.escribir_para_anadir(f, plan["nuevas"], plan["relaciones"], plan["notas"], extra=plan.get("extra", []), fondo=plan.get("fondo", []))
            nuevos = [o for c in ET.fromstring(f.read_bytes()).findall("dia:layer", du.NS) for o in c if o.tag == _q("object")]
        n0 = len(objs())
        for k, o in enumerate(nuevos): o.set("id", f"N{k}"); capa.append(o)
        todos = objs()
        def destino_de(ref):
            ref = re.sub(r"@-?[\d.]+,-?[\d.]+$", "", ref or ""); punto = 0
            m = re.search(r"#(\d+)$", ref)
            if m: punto, ref = int(m.group(1)), ref[:m.start()]
            if ref.startswith("tag:"): o = next((x for x in todos if _meta(x, "tutor") == ref[4:]), None)
            elif ref.startswith("clase:"): o = next((x for x in todos if x.get("type") == "UML - Class" and _nombre_obj(x) == ref[6:]), None)
            elif ref.startswith("id:O"):
                i = int(ref[4:]); o = todos[i] if i < n0 else None
            elif ref.startswith("nombre:"): o = next((x for x in todos if _nombre_obj(x) == ref[7:]), None)
            else: o = None
            return (o.get("id"), punto) if o is not None else (None, 0)
        for o in nuevos:
            ini, fin = _meta(o, "conecta_inicio"), _meta(o, "conecta_fin")
            con = o.find("dia:connections", du.NS)
            if con is not None: o.remove(con)
            if not con_conexiones or not (ini or fin): continue
            con = ET.SubElement(o, _q("connections"))
            for h, ref in ((0, ini), (1, fin)):
                if not ref: continue
                oid, punto = destino_de(ref)
                if oid: ET.SubElement(con, _q("connection"), {"handle": str(h), "to": oid, "connection": str(punto)})
        # 5) poner (propiedades del modo libre en lo recién creado)
        for orden in plan.get("poner", []): _poner_offline(capa, orden)
    _renumerar(raiz)
    texto = ET.tostring(raiz, encoding="unicode").replace("ns0:", "dia:").replace(":ns0", ":dia")
    Path(destino).write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + texto, encoding="utf-8")


def _renumerar(raiz):
    """Ids O0, O1... en el orden en que Dia los guardaría (así valen las REF «id:On»), y las conexiones con ellos."""
    mapa, n = {}, 0
    for capa in raiz.findall("dia:layer", du.NS):
        for o in capa.iter(_q("object")):
            mapa[o.get("id")] = f"O{n}"; o.set("id", f"O{n}"); n += 1
    for c in raiz.iter(_q("connection")):
        if c.get("to") in mapa: c.set("to", mapa[c.get("to")])


_CLASES_XML = {"string": "string", "multistring": "string", "text": "text", "real": "real", "length": "real", "fontsize": "real",
               "int": "int", "enum": "enum", "arrow": "enum", "linestyle": "enum", "bool": "bool", "colour": "color"}


def _poner_offline(capa, orden):
    """Una orden «poner "REF" "prop=valor"...» aplicada al XML (solo los tipos sencillos; el resto lo pone el plugin)."""
    try: partes = shlex.split(orden)[1:]
    except ValueError: return
    if not partes: return
    ref, pares = partes[0], [p.split("=", 1) for p in partes[1:] if "=" in p]
    objs = [o for o in capa if o.tag == _q("object")]
    if ref.startswith("tag:"): o = next((x for x in objs if _meta(x, "tutor") == ref[4:]), None)
    elif ref.startswith("id:"): o = next((x for x in objs if x.get("id") == ref[3:]), None)
    else: o = next((x for x in objs if _nombre_obj(x) == ref.split(":", 1)[-1]), None)
    if o is None: return
    tipo = o.get("type")
    for n, v in pares:
        if n == "elem_corner":
            try: x, y = map(float, v.split(","))
            except ValueError: continue
            do.poner_xml(o, "elem_corner", "point", (x, y)); do.poner_xml(o, "obj_pos", "point", (x, y)); continue
        t = (do.props_tipo(tipo).get(n) or {}).get("t") if tipo in do.catalogo() else None
        clase = _CLASES_XML.get(t)
        if not clase: continue
        if clase == "bool": v = v == "true"
        elif clase in ("string", "text"): v = v.replace("\\n", "\n")
        do.poner_xml(o, n, clase, v)
        if n in ("elem_width", "elem_height"):         # la caja guardada también, como la dejaría Dia
            r = o.find("dia:attribute[@name='obj_bb']/dia:rectangle", du.NS); c = o.find("dia:attribute[@name='elem_corner']/dia:point", du.NS)
            if r is not None and c is not None:
                (x1, y1), (x2, y2) = [tuple(map(float, q.split(","))) for q in r.get("val").split(";")]
                cx, cy = map(float, c.get("val").split(","))
                if n == "elem_width": x2 = cx + float(v)
                else: y2 = cy + float(v)
                r.set("val", f"{x1:.4f},{y1:.4f};{x2:.4f},{y2:.4f}")
