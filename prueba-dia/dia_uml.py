"""Leer, escribir, revisar y dibujar diagramas de clase de Dia (.dia).
Dia 0.97 no se puede controlar en vivo (ni COM ni Python por dentro): se trabaja con sus archivos,
que son XML (a veces comprimido con gzip). De cada clase se saca nombre, atributos, métodos,
visibilidad y su caja exacta; con eso se revisa sin IA y se dibujan las marcas donde tocan."""
import gzip, html, re, unicodedata
import xml.etree.ElementTree as ET

NS = {"dia": "http://www.lysator.liu.se/~alla/dia/"}
VIS = {0: "+", 1: "-", 2: "#", 3: "~"}              # público, privado, protegido, implementación
VIS_NUM = {v: k for k, v in VIS.items()}
VIS_NOMBRE = {"+": "público (+)", "-": "privado (-)", "#": "protegido (#)", "~": "de paquete (~)"}


# ---------- Leer ----------
def _cadena(nodo, nombre):
    s = nodo.find(f"dia:attribute[@name='{nombre}']/dia:string", NS)
    t = (s.text or "") if s is not None else ""
    return t[1:-1] if t.startswith("#") and t.endswith("#") else t     # Dia guarda "#texto#"


def _num(nodo, nombre, etiqueta="enum", defecto=0):
    s = nodo.find(f"dia:attribute[@name='{nombre}']/dia:{etiqueta}", NS)
    return float(s.get("val")) if s is not None else defecto


# ---------- Rutas de paquetes: «java/util/function» (dos capas pueden llamarse igual si su padre es distinto) ----------
def partir_ruta(ref):
    """«java/util», «java › util» o «/util» → (["java", "util"], absoluta?). Una ruta que empieza por «/» es la completa desde la raíz."""
    ref = str(ref or "").strip()
    return [x.strip() for x in re.split(r"[/›>]", ref) if x.strip()], ref.startswith(("/", "›"))


def mostrar_ruta(ruta): return " › ".join(ruta)


def clave_ruta(ruta): return "/".join(_norm(x) for x in ruta)


def resolver_ruta(ref, rutas):
    """La ruta (tupla de nombres) del paquete que nombra `ref` entre `rutas` (tuplas de las capas que hay). `ref` es un nombre a secas
    («util»: vale solo si hay una capa con ese nombre) o el final de una ruta («java/util»; con «/» delante, la ruta completa).
    None si no hay ninguna. ValueError, pidiendo la ruta, si la referencia es ambigua."""
    partes, absoluta = partir_ruta(ref)
    if not partes: return None
    n = [_norm(x) for x in partes]
    cands = []
    for r in rutas:
        rn = [_norm(x) for x in r]
        if (len(rn) == len(n) if absoluta else len(rn) >= len(n)) and rn[len(rn) - len(n):] == n and tuple(r) not in cands: cands.append(tuple(r))
    if len(cands) > 1:
        ej = " o ".join("«" + ("/" + c[0] if len(c) == 1 else "/".join(c)) + "»" for c in cands[:4])
        raise ValueError(f"«{ref}» puede ser {' o '.join('«' + mostrar_ruta(c) + '»' for c in cands[:4])}: escribe la ruta ({ej}; con «/» delante es desde la raíz)")
    return cands[0] if cands else None


CAPA_TUTOR = "Tutor"          # la capa de las marcas del tutor (plugin-dia): no es parte del diagrama


def _objetos(raiz):
    """Todos los objetos del diagrama (también los de dentro de grupos), menos los de la capa «Tutor»."""
    for capa in raiz.findall("dia:layer", NS):
        if capa.get("name") == CAPA_TUTOR: continue
        yield from capa.iter(f"{{{NS['dia']}}}object")


def _meta(nodo, clave="tutor"):
    """Un valor de la meta del objeto (los objetos que crea el tutor llevan meta tutor = su etiqueta)."""
    s = nodo.find(f"dia:attribute[@name='meta']/dia:composite/dia:attribute[@name='{clave}']/dia:string", NS)
    t = (s.text or "") if s is not None else ""
    return t[1:-1] if t.startswith("#") and t.endswith("#") else t


def _estilo_fuente(nodo, nombre):
    """El estilo (número de Dia) de una fuente del objeto, p. ej. classname_font; 0 si no está."""
    f = nodo.find(f"dia:attribute[@name='{nombre}']/dia:font", NS)
    try: return int(f.get("style")) if f is not None else 0
    except (TypeError, ValueError): return 0


def en_negrita(estilo): return (estilo >> 4) & 7 >= 4          # peso de Dia: 4 = seminegrita, 5 = negrita...


def _padre_id(o):
    """El id del objeto padre en Dia (<dia:childnode parent="O6"/>: un paquete que contiene a este objeto), o None."""
    h = o.find("dia:childnode", NS)
    return h.get("parent") if h is not None else None


def _cajas_xml(o):
    p = o.find("dia:attribute[@name='elem_corner']/dia:point", NS)
    x0, y0 = map(float, p.get("val").split(",")) if p is not None else (0.0, 0.0)
    return (x0, y0, _num(o, "elem_width", "real", 4), _num(o, "elem_height", "real", 2))


# ---------- Tipos de objeto (registro): para añadir otro tipo de diagrama, se añade aquí ----------
# Relaciones de clase. «de» → «a»: el símbolo (triángulo, flecha o rombo) va siempre en «a».
#   herencia: de = hija, a = padre · realizacion: de = clase, a = interfaz · dependencia: de usa a a
#   asociacion: de — a (mult = [de, a]; "direccion": "a" = flecha en a) · agregacion / composicion: de = parte, a = todo (rombo)
# En Dia: "inicio" es el extremo 0 (handle 0) y "fin" el 1. `inicio_es_a` dice si el extremo 0 es «a».
TIPOS_REL = {
    "asociacion":  {"dia": "UML - Association", "inicio_es_a": False, "nombre": "asociación"},
    "agregacion":  {"dia": "UML - Association", "inicio_es_a": True, "assoc_type": 1, "nombre": "agregación"},
    "composicion": {"dia": "UML - Association", "inicio_es_a": True, "assoc_type": 2, "nombre": "composición"},
    "herencia":    {"dia": "UML - Generalization", "inicio_es_a": True, "nombre": "herencia"},
    "realizacion": {"dia": "UML - Realizes", "inicio_es_a": True, "nombre": "realización"},
    "dependencia": {"dia": "UML - Dependency", "inicio_es_a": False, "nombre": "dependencia"},
    # casos de uso: dependencias con estereotipo. include: de = caso base, a = el incluido · extend: de = el que extiende, a = el base
    "include":     {"dia": "UML - Dependency", "inicio_es_a": False, "nombre": "inclusión «include»", "estereotipo": "include"},
    "extend":      {"dia": "UML - Dependency", "inicio_es_a": False, "nombre": "extensión «extend»", "estereotipo": "extend"},
}
TIPOS_DIA_REL = {"UML - Association", "UML - Generalization", "UML - Realizes", "UML - Dependency"}


def _leer_relacion(o):
    """Una relación UML como dict, con sus extremos por id (de_id, a_id) y el resto de sus datos."""
    t = o.get("type")
    ext = {int(c.get("handle")): (c.get("to"), c.get("connection")) for c in o.findall("dia:connections/dia:connection", NS)}
    ini, fin = ext.get(0, (None, None)), ext.get(1, (None, None))
    r = {"id": o.get("id"), "tag": _meta(o), "nombre": _cadena(o, "name"), "mult": ["", ""], "roles": ["", ""], "direccion": "",
         "puntos": [tuple(map(float, p.get("val").split(","))) for p in o.findall("dia:attribute[@name='orth_points']/dia:point", NS)]}
    if t == "UML - Association":
        tipo_ag, sentido = int(_num(o, "assoc_type")), int(_num(o, "direction"))
        ma, mb = _cadena(o, "multipicity_a"), _cadena(o, "multipicity_b")
        ra, rb = _cadena(o, "role_a"), _cadena(o, "role_b")
        fa, fb = _bool(o, "show_arrow_a", False), _bool(o, "show_arrow_b", False)
        r["ver_lectura"] = _bool(o, "show_direction", False) and sentido in (1, 2)      # ¿se dibuja el triángulo ▶/◀ junto al nombre?
        r["glifo"] = sentido if r["ver_lectura"] else 0                                  # 1 = ▶ (apunta a la derecha), 2 = ◀
        if tipo_ag in (1, 2) and sentido in (1, 2):
            r["tipo"] = "agregacion" if tipo_ag == 1 else "composicion"
            if sentido == 1:   # rombo en el inicio (A): A es el todo
                r.update(a_id=ini[0], de_id=fin[0], mult=[mb, ma], roles=[rb, ra], punto_a=ini[1], punto_de=fin[1], flecha=(fb, fa))
            else:
                r.update(a_id=fin[0], de_id=ini[0], mult=[ma, mb], roles=[ra, rb], punto_a=fin[1], punto_de=ini[1], flecha=(fa, fb))
        else:
            r.update(tipo="asociacion", de_id=ini[0], a_id=fin[0], mult=[ma, mb], roles=[ra, rb], punto_de=ini[1], punto_a=fin[1], flecha=(fa, fb))
        fde, fa_ = r.pop("flecha")      # flecha de navegabilidad junto a «de» y junto a «a»
        r["direccion"] = "ambas" if fde and fa_ else "a" if fa_ else "de" if fde else ""
    else:
        r["tipo"] = {"UML - Generalization": "herencia", "UML - Realizes": "realizacion", "UML - Dependency": "dependencia"}[t]
        r["estereotipo"] = _cadena(o, "stereotype")
        if t == "UML - Dependency" and _norm(r["estereotipo"]).strip("«»<>") in ("include", "extend"):
            r["tipo"] = _norm(r["estereotipo"]).strip("«»<>")
        if TIPOS_REL[r["tipo"]]["inicio_es_a"]: r.update(a_id=ini[0], de_id=fin[0], punto_a=ini[1], punto_de=fin[1])
        else: r.update(de_id=ini[0], a_id=fin[0], punto_de=ini[1], punto_a=fin[1])
    return r


def leer(ruta):
    """{"clases": [...], "relaciones": [...], "notas": [...], "otros": [tipos que no se conocen]} de un .dia.
    Ignora la capa «Tutor»: si la persona guarda con marcas del tutor puestas, no cuentan.
    Cada relación dice entre qué clases va ("de", "a": nombres; None si el extremo está suelto)."""
    crudo = open(ruta, "rb").read()
    if crudo[:2] == b"\x1f\x8b": crudo = gzip.decompress(crudo)
    raiz = ET.fromstring(crudo)
    clases, relaciones, notas, otros, resto = [], [], [], [], []
    for o in _objetos(raiz):
        tipo = o.get("type")
        if tipo in TIPOS_DIA_REL:
            relaciones.append(_leer_relacion(o)); continue
        if tipo == "UML - Note":
            notas.append({"id": o.get("id"), "tag": _meta(o), "caja": _cajas_xml(o),
                          "texto": _cadena(o.find("dia:attribute[@name='text']/dia:composite", NS), "string")
                          if o.find("dia:attribute[@name='text']/dia:composite", NS) is not None else ""})
            continue
        if tipo != "UML - Class":
            resto.append(o); continue           # actores, casos, mensajes, estados, Flowchart, ER...: dia_objetos.completar
        atributos = [{"nombre": _cadena(a, "name"), "tipo": _cadena(a, "type"), "vis": VIS.get(int(_num(a, "visibility")), "+"),
                      "estatico": _bool(a, "class_scope", False)}
                     for a in o.findall("dia:attribute[@name='attributes']/dia:composite", NS)]
        metodos = []
        for m in o.findall("dia:attribute[@name='operations']/dia:composite", NS):
            params = [{"nombre": _cadena(p, "name"), "tipo": _cadena(p, "type")}
                      for p in m.findall("dia:attribute[@name='parameters']/dia:composite", NS)]
            metodos.append({"nombre": _cadena(m, "name"), "tipo": _cadena(m, "type"),
                            "vis": VIS.get(int(_num(m, "visibility")), "+"), "params": params,
                            "abstracto": _bool(m, "abstract", False), "estatico": _bool(m, "class_scope", False)})
        abstracta = _bool(o, "abstract", False)
        ver = tuple(_bool(o, n, d) for n, d in (("visible_attributes", True), ("visible_operations", True),
                                                ("suppress_attributes", False), ("suppress_operations", False)))
        estereo = _cadena(o, "stereotype")
        clases.append({"id": o.get("id"), "nombre": _cadena(o, "name"), "estereotipo": estereo, "tag": _meta(o),
                       "abstracta": abstracta,
                       "atributos": atributos, "metodos": metodos, "caja": _cajas_xml(o),
                       "fila_alto": _num(o, "normal_font_height", "real", 0.8),
                       # la negrita del nombre (la fuente que Dia usa: la de abstracta si lo es) y el padre (un paquete) en Dia
                       "negrita": en_negrita(_estilo_fuente(o, "abstract_classname_font" if abstracta else "classname_font")),
                       "enumerada": [a["nombre"] for a in atributos] if (not ver[1] and not estereo and atributos and not metodos
                                                                       and all(not a["tipo"] and a["vis"] == "~" for a in atributos)) else None,
                       "padre_id": _padre_id(o), "ver": ver})
    por_id = {c["id"]: c["nombre"] for c in clases}
    for r in relaciones: r["de"], r["a"] = por_id.get(r.get("de_id")), por_id.get(r.get("a_id"))
    d = {"clases": clases, "relaciones": relaciones, "notas": notas, "otros": otros}
    import dia_objetos
    d = dia_objetos.completar(d, resto)          # objetos y líneas de cualquier otro tipo (y nombres en las relaciones)
    # padres: el nombre del paquete (o de lo que contiene) de cada clase y de cada objeto, y a quién apunta el triángulo de lectura
    nombres = {c["id"]: c["nombre"] for c in clases}
    nombres.update({x["id"]: x.get("texto") or x.get("nombre") for x in d.get("objetos", [])})
    for o in resto:
        x = next((x for x in d.get("objetos", []) if x["id"] == o.get("id")), None)
        if x is not None: x["padre_id"] = _padre_id(o)
    for x in clases + d.get("objetos", []):
        x["padre"] = nombres.get(x.get("padre_id")) if x.get("padre_id") else None
    por_obj = {x["id"]: x for x in d.get("objetos", [])}
    def ruta_de(x, k=0):                            # nombres de sus paquetes, de fuera hacia dentro (con él, si es un paquete)
        padre = por_obj.get(x.get("padre_id")) if k < 20 else None
        return (ruta_de(padre, k + 1) if padre else ()) + ((x.get("texto") or x.get("nombre") or "",) if x.get("kind") == "paquete" else ())
    for x in d.get("objetos", []):
        if x.get("kind") == "paquete": x["ruta"] = ruta_de(x)
    for c in clases:
        pa = por_obj.get(c.get("padre_id"))
        c["ruta_padre"] = ruta_de(pa) if pa is not None and pa.get("kind") == "paquete" else None
    cajas = {c["id"]: c["caja"] for c in clases}
    cajas.update({x["id"]: x["caja"] for x in d.get("objetos", [])})
    for r in relaciones:                          # ▶ apunta al extremo que queda más a la derecha, ◀ al de más a la izquierda
        r["lectura_hacia"] = None
        if not r.get("glifo"): continue
        ca, cd_ = cajas.get(r.get("a_id")), cajas.get(r.get("de_id"))
        if not (ca and cd_): continue
        xa, xd = ca[0] + ca[2] / 2, cd_[0] + cd_[2] / 2
        if abs(xa - xd) < 0.05: continue
        derecha_es_a = xa > xd
        r["lectura_hacia"] = r.get("a") if (derecha_es_a == (r["glifo"] == 1)) else r.get("de")
    return d


def es_interfaz(c): return _norm(c.get("estereotipo", "")).strip("«»<>") in ("interface", "interfaz")


def _bool(nodo, nombre, defecto):
    s = nodo.find(f"dia:attribute[@name='{nombre}']/dia:boolean", NS)
    return defecto if s is None else s.get("val") == "true"


def _clave(clase, miembro=""):
    """Clave de una caja: "Clase" o "Clase.miembro" (sin el tipo ni los paréntesis, como las marcas del tutor)."""
    m = re.split(r"[:(]", miembro or "")[0].strip()
    return f"{clase}.{m}" if m else clase


def cajas_cm(d):
    """Cajas en cm del diagrama (las mismas cuentas que la orden «cajas» del plugin, pero sobre lo
    guardado): {"Clase": (x, y, w, h), "Clase.miembro": (x, y, w, h)}. Sirve de respaldo cuando el
    plugin no responde; con plugin, mejor sus cajas, que son las de la pantalla aunque no se haya guardado."""
    cajas = {}
    for c in d["clases"]:
        x, y, w, h = c["caja"]; fh = c.get("fila_alto", 0.8)
        ver_at, ver_op, sup_at, sup_op = c.get("ver", (True, True, False, False))
        caja_at = (0.4 if sup_at else max(0.4, 0.2 + fh * len(c["atributos"]))) if ver_at else 0
        caja_op = (0.4 if sup_op else max(0.4, 0.2 + fh * len(c["metodos"]))) if ver_op else 0
        alto_nombre = h - caja_at - caja_op
        cajas[c["nombre"]] = (x, y, w, h)
        if ver_at and not sup_at:
            for i, a in enumerate(c["atributos"]): cajas.setdefault(_clave(c["nombre"], a["nombre"]), (x, y + alto_nombre + 0.1 + i * fh, w, fh))
        if ver_op and not sup_op:
            for i, m in enumerate(c["metodos"]): cajas.setdefault(_clave(c["nombre"], m["nombre"]), (x, y + alto_nombre + caja_at + 0.1 + i * fh, w, fh))
    import dia_objetos
    for k, v in dia_objetos.cajas_otros(d).items(): cajas.setdefault(k, v)     # actores, casos, estados... y «#O7»
    return cajas


def cajas_de_plugin(respuesta):
    """Traduce la respuesta de la orden «cajas» del plugin al mismo formato que cajas_cm."""
    cajas = {}
    for linea in respuesta.splitlines():
        p = linea.split("\t")
        try:
            if p[0] == "caja" and len(p) >= 7: cajas[p[1]] = tuple(float(v) for v in p[3:7])
            elif p[0] == "fila" and len(p) >= 8 and p[3] in ("atributo", "metodo"):
                cajas.setdefault(_clave(p[1], p[2]), tuple(float(v) for v in p[4:8]))
        except ValueError: continue
    import dia_objetos
    for k, v in dia_objetos.cajas_de_plugin_objetos(respuesta).items(): cajas.setdefault(k, v)   # versión 4: todos los objetos
    return cajas


def frase_relacion(r):
    """Una relación en palabras, p. ej. «Perro hereda de Animal»."""
    de, a = r.get("de") or "(suelta)", r.get("a") or "(suelta)"
    m = r.get("mult") or ["", ""]
    mult = f" (multiplicidad {m[0] or '?'} en {de}, {m[1] or '?'} en {a})" if any(m) else ""
    nombre = f" «{r['nombre']}»" if r.get("nombre") else ""
    hacia = r.get("lectura_hacia") or ({"a": a, "de": de}.get(r.get("lectura")) if r.get("lectura") in ("a", "de") else None)
    nombre += f" (triángulo de lectura hacia {hacia})" if nombre and hacia else ""
    t = r["tipo"]
    if t == "herencia": return f"{de} hereda de {a}"
    if t == "realizacion": return f"{de} implementa la interfaz {a}"
    if t == "dependencia": return f"{de} depende de {a} (la usa)" + (f" «{r['estereotipo']}»" if r.get("estereotipo") else "") + (f", verbo «{r['nombre']}»" if r.get("nombre") else "")
    if t == "include": return f"«{de}» incluye a «{a}» («include»)"
    if t == "extend": return f"«{de}» extiende a «{a}» («extend»)"
    if t == "agregacion": return f"agregación{nombre}: {a} (todo, rombo vacío) tiene {de} (parte){mult}"
    if t == "composicion": return f"composición{nombre}: {a} (todo, rombo lleno) se compone de {de} (parte){mult}"
    flecha = {"a": f", navegable hacia {a}", "de": f", navegable hacia {de}", "ambas": ", navegable en los dos sentidos"}.get(r.get("direccion"), "")
    return f"asociación{nombre} entre {de} y {a}{mult}{flecha}"


def texto(d):
    """El diagrama como texto (para el tutor: barato, sin imágenes)."""
    rels, notas = d.get("relaciones", []), d.get("notas", [])
    if not d["clases"] and not rels and not notas and not d.get("objetos") and not d.get("lineas"): return "(el diagrama está vacío)"
    lineas = []
    for c in d["clases"]:
        extra = (" (abstracta)" if c["abstracta"] else "") + (f" «{c['estereotipo']}»" if c.get("estereotipo") else "") \
            + (" [la creaste tú, el tutor]" if c.get("tag") else "")
        extra += " (nombre en negrita)" if c.get("negrita") else " (nombre sin negrita)" if "negrita" in c else ""
        extra += f" (dentro de «{c['padre']}»)" if c.get("padre") else ""
        if c.get("enumerada"):
            lineas.append(f"Enumerada «{c['nombre']}»{extra}: " + ", ".join(c["enumerada"])); continue
        lineas.append(f"Clase «{c['nombre']}»{extra}")
        lineas += [f"  atributo: {linea_atributo(a)}" for a in c["atributos"]] or ["  (sin atributos)"]
        lineas += [f"  método: {linea_metodo(m)}" for m in c["metodos"]] or ["  (sin métodos)"]
    for r in rels: lineas.append("Relación: " + frase_relacion(r) + (" [la creaste tú, el tutor]" if r.get("tag") else ""))
    for n in notas: lineas.append(f"Nota: «{n['texto'][:120]}»" + (" [la creaste tú, el tutor]" if n.get("tag") else ""))
    if d["otros"]: lineas.append("Otros objetos: " + ", ".join(d["otros"]))
    import dia_objetos
    lineas += dia_objetos.texto_otros(d)
    return "\n".join(lineas)


def linea_atributo(a): return f"{a.get('vis', '+')}{a['nombre']}" + (f": {a['tipo']}" if a.get("tipo") else "")


def linea_param(p):
    """Un parámetro como se escribe: «sku: String», o solo «String» si no tiene nombre (parámetros solo con el tipo)."""
    if not p.get("nombre"): return p.get("tipo", "")
    return p["nombre"] + (f": {p['tipo']}" if p.get("tipo") else "")


def linea_metodo(m):
    ps = ", ".join(linea_param(p) for p in m.get("params", []))
    return f"{m.get('vis', '+')}{m['nombre']}({ps})" + (f": {m['tipo']}" if m.get("tipo") else "")


MIEMBRO = re.compile(r"^\s*([+\-#~])?\s*([A-Za-zÁÉÍÓÚÜÑáéíóúüñ_][\wÁÉÍÓÚÜÑáéíóúüñ]*)\s*(\(([^()]*)\))?\s*(?::\s*([^{}]+?))?\s*(\{\s*(abstract|abstracto|static|estatico|estático)\s*\})?\s*$")


def miembro(s):
    """Un atributo o método en notación UML («-nombre: String», «+inscribir(curso: String): void {abstract}»)
    → dict con "es" = "atributo" o "metodo". Lanza ValueError si no se entiende."""
    if isinstance(s, dict):
        m = dict(s); m.setdefault("vis", "+"); m.setdefault("tipo", "")
        if not isinstance(m.get("nombre"), str) or not re.match(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ_][\wÁÉÍÓÚÜÑáéíóúüñ]*$", m["nombre"]):
            raise ValueError(f"nombre de miembro no válido: {s!r}")
        if m["vis"] not in VIS_NUM: raise ValueError(f"visibilidad no válida en {s!r} (usa + - # ~)")
        m["es"] = "metodo" if "params" in m or m.get("es") == "metodo" else "atributo"
        if m["es"] == "metodo": m["params"] = [miembro_param(p) for p in m.get("params", [])]
        return m
    if not isinstance(s, str) or len(s) > 160: raise ValueError(f"miembro no válido: {s!r}")
    r = MIEMBRO.match(s)
    if not r: raise ValueError(f"no entiendo «{s}» (escribe p. ej. «-nombre: String» o «+metodo(x: int): void»)")
    vis, nombre, parentesis, params, tipo, _, marca = r.groups()
    d = {"nombre": nombre, "vis": vis or "+", "tipo": (tipo or "").strip()}
    marca = _norm(marca or "")
    if parentesis is not None:
        d.update(es="metodo", params=[miembro_param(p) for p in params.split(",") if p.strip()],
                 abstracto=marca.startswith("abstract"), estatico=marca.startswith(("static", "estatico")))
    else:
        d.update(es="atributo", estatico=marca.startswith(("static", "estatico")))
    return d


TIPO_PARAM = re.compile(r"^\s*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ_][\wÁÉÍÓÚÜÑáéíóúüñ.]*(\s*<[^<>]*>)?(\[[*\d.]*\])*\s*$")


def miembro_param(p):
    """Un parámetro: «nombre: Tipo» o, sin «:», solo el tipo («String»: parámetros solo con el tipo; Dia lo dibuja «(String)»)."""
    if isinstance(p, dict):
        if not isinstance(p.get("nombre"), str): raise ValueError(f"parámetro no válido: {p!r}")
        return {"nombre": p["nombre"].strip(), "tipo": str(p.get("tipo", "")).strip()}
    if ":" not in str(p):
        if not TIPO_PARAM.match(str(p)): raise ValueError(f"parámetro no válido: «{p}»")
        return {"nombre": "", "tipo": str(p).strip()}
    nombre, _, tipo = str(p).partition(":")
    if not re.match(r"^\s*[A-Za-zÁÉÍÓÚÜÑáéíóúüñ_][\wÁÉÍÓÚÜÑáéíóúüñ]*\s*$", nombre): raise ValueError(f"parámetro no válido: «{p}»")
    return {"nombre": nombre.strip(), "tipo": tipo.strip()}


def sin_nombres_de_parametros(m):
    """Un método (dict de miembro()) con los parámetros solo con el tipo (convención K1)."""
    if m.get("es") != "metodo" and "params" not in m: return m
    return dict(m, params=[{"nombre": "", "tipo": p.get("tipo") or p.get("nombre", "")} for p in m.get("params", [])])


# ---------- Escribir ----------
CABECERA = """<?xml version="1.0" encoding="UTF-8"?>
<dia:diagram xmlns:dia="http://www.lysator.liu.se/~alla/dia/">
  <dia:diagramdata>
    <dia:attribute name="background"><dia:color val="#ffffff"/></dia:attribute>
    <dia:attribute name="pagebreak"><dia:color val="#000099"/></dia:attribute>
    <dia:attribute name="paper"><dia:composite type="paper">
      <dia:attribute name="name"><dia:string>#A4#</dia:string></dia:attribute>
      <dia:attribute name="tmargin"><dia:real val="2.82"/></dia:attribute>
      <dia:attribute name="bmargin"><dia:real val="2.82"/></dia:attribute>
      <dia:attribute name="lmargin"><dia:real val="2.82"/></dia:attribute>
      <dia:attribute name="rmargin"><dia:real val="2.82"/></dia:attribute>
      <dia:attribute name="is_portrait"><dia:boolean val="true"/></dia:attribute>
      <dia:attribute name="scaling"><dia:real val="1"/></dia:attribute>
      <dia:attribute name="fitto"><dia:boolean val="false"/></dia:attribute>
    </dia:composite></dia:attribute>
    <dia:attribute name="grid"><dia:composite type="grid">
      <dia:attribute name="width_x"><dia:real val="1"/></dia:attribute>
      <dia:attribute name="width_y"><dia:real val="1"/></dia:attribute>
      <dia:attribute name="visible_x"><dia:int val="1"/></dia:attribute>
      <dia:attribute name="visible_y"><dia:int val="1"/></dia:attribute>
      <dia:composite type="color"/>
    </dia:composite></dia:attribute>
    <dia:attribute name="color"><dia:color val="#d8e5e5"/></dia:attribute>
    <dia:attribute name="guides"><dia:composite type="guides">
      <dia:attribute name="hguides"/><dia:attribute name="vguides"/>
    </dia:composite></dia:attribute>
  </dia:diagramdata>
  <dia:layer name="Fondo" visible="true" active="true">
"""
PIE = "  </dia:layer>\n</dia:diagram>\n"


def _s(nombre, valor): return f'<dia:attribute name="{nombre}"><dia:string>#{html.escape(valor, quote=False)}#</dia:string></dia:attribute>'
def _b(nombre, v): return f'<dia:attribute name="{nombre}"><dia:boolean val="{"true" if v else "false"}"/></dia:attribute>'
def _e(nombre, v): return f'<dia:attribute name="{nombre}"><dia:enum val="{v}"/></dia:attribute>'
def _r(nombre, v): return f'<dia:attribute name="{nombre}"><dia:real val="{v}"/></dia:attribute>'
def _f(nombre, fam, est, nom): return f'<dia:attribute name="{nombre}"><dia:font family="{fam}" style="{est}" name="{nom}"/></dia:attribute>'


def medidas(c):
    """Ancho y alto aproximados (Dia los recalcula al abrir el archivo)."""
    ats, mets = c.get("atributos", []), c.get("metodos", [])
    filas = [c["nombre"]] + [linea_atributo(a) for a in ats] + [linea_metodo(m) for m in mets]
    ancho = max(4.0, 0.55 * max(len(f) for f in filas) + 1.0)
    alto = 1.4 + 0.8 * max(1, len(ats)) + 0.8 * max(1, len(mets)) + 0.4
    return round(ancho, 2), round(alto, 2)


def _meta_xml(meta):
    """<meta> de Dia (diccionario de textos): la etiqueta del tutor y, para el plugin, a qué se conecta cada extremo."""
    meta = {k: v for k, v in (meta or {}).items() if v}
    if not meta: return ""
    return ('<dia:attribute name="meta"><dia:composite type="dict">'
            + "".join(f'<dia:attribute name="{k}"><dia:string>#{html.escape(str(v), quote=False)}#</dia:string></dia:attribute>' for k, v in meta.items())
            + '</dia:composite></dia:attribute>')


def valores_enumerada(c):
    """Los valores de una enumerada como atributos de Dia: sin tipo y con visibilidad «implementación» (Dia no dibuja ningún signo)."""
    return [{"nombre": v, "tipo": "", "vis": "~", "estatico": False} for v in c["enumerada"]]


def _hijo_xml(padre_id):
    """Parentesco de Dia: el objeto es hijo de otro (un paquete) y se mueve con él."""
    return f'<dia:childnode parent="{padre_id}"/>' if padre_id else ""


def _clase_xml(c, i, oid=None):
    """Una clase UML. c: {"nombre", "pos": (x, y), "atributos", "metodos", "abstracta", "estereotipo", "tag"}.
    Atributos {"nombre", "tipo", "vis", "estatico"}; métodos {"nombre", "tipo", "vis", "params", "abstracto", "estatico"}.
    Opcionales: "negrita" (False = nombre sin negrita, convención 18; por defecto True), "enumerada" (lista de valores:
    sin métodos visibles, convención 20), "ver" (visible_attributes, visible_operations, suppress_attributes, suppress_operations),
    "_padre_id" (id de su paquete en este mismo archivo: parentesco real) y "_hijo_de" (REF de un paquete que ya está en el
    diagrama: el plugin la hace hija suya al añadirla)."""
    if c.get("enumerada") is not None:
        c = dict(c, atributos=valores_enumerada(c), metodos=[], ver=(True, False, False, False), estereotipo="")
    ver = c.get("ver") or (True, True, False, False)
    negrita = c.get("negrita", True)
    fuente_nombre = _f("classname_font", "sans", 80, "Helvetica-Bold") if negrita else _f("classname_font", "sans", 0, "Helvetica")
    fuente_abstracta = (_f("abstract_classname_font", "sans", 88, "Helvetica-BoldOblique") if negrita
                        else _f("abstract_classname_font", "sans", 8, "Helvetica-Oblique"))
    fuente_miembro_abstracto = (_f("abstract_font", "monospace", 88, "Courier-BoldOblique") if negrita
                                else _f("abstract_font", "monospace", 8, "Courier-Oblique"))
    x, y = c.get("pos", (2 + 12 * i, 2))
    ancho, alto = medidas(c)
    ats = "".join(f'<dia:composite type="umlattribute">{_s("name", a["nombre"])}{_s("type", a.get("tipo", ""))}{_s("value", "")}'
                  f'{_s("comment", "")}{_e("visibility", VIS_NUM[a.get("vis", "+")])}{_b("abstract", False)}{_b("class_scope", a.get("estatico", False))}</dia:composite>'
                  for a in c.get("atributos", []))
    ops = ""
    for m in c.get("metodos", []):
        ps = "".join(f'<dia:composite type="umlparameter">{_s("name", p["nombre"])}{_s("type", p.get("tipo", ""))}{_s("value", "")}'
                     f'{_s("comment", "")}{_e("kind", 0)}</dia:composite>' for p in m.get("params", []))
        abstracto = bool(m.get("abstracto"))
        ops += (f'<dia:composite type="umloperation">{_s("name", m["nombre"])}{_s("stereotype", "")}{_s("type", m.get("tipo", ""))}'
                f'{_e("visibility", VIS_NUM[m.get("vis", "+")])}{_s("comment", "")}{_b("abstract", abstracto)}{_e("inheritance_type", 0 if abstracto else 2)}'
                f'{_b("query", False)}{_b("class_scope", m.get("estatico", False))}<dia:attribute name="parameters">{ps}</dia:attribute></dia:composite>')
    return (f'<dia:object type="UML - Class" version="0" id="{oid or f"O{i}"}">'
            f'<dia:attribute name="obj_pos"><dia:point val="{x},{y}"/></dia:attribute>'
            f'<dia:attribute name="obj_bb"><dia:rectangle val="{x - 0.05},{y - 0.05};{x + ancho + 0.05},{y + alto + 0.05}"/></dia:attribute>'
            f'{_meta_xml({"tutor": c.get("tag"), "hijo_de": c.get("_hijo_de")})}'
            f'<dia:attribute name="elem_corner"><dia:point val="{x},{y}"/></dia:attribute>'
            f'{_r("elem_width", ancho)}{_r("elem_height", alto)}'
            f'{_s("name", c["nombre"])}{_s("stereotype", c.get("estereotipo", ""))}{_s("comment", "")}{_b("abstract", c.get("abstracta", False))}'
            f'{_b("suppress_attributes", ver[2])}{_b("suppress_operations", ver[3])}{_b("visible_attributes", ver[0])}'
            f'{_b("visible_operations", ver[1])}{_b("visible_comments", False)}{_b("wrap_operations", False)}'
            f'<dia:attribute name="wrap_after_char"><dia:int val="40"/></dia:attribute>'
            f'<dia:attribute name="comment_line_length"><dia:int val="40"/></dia:attribute>{_b("comment_tagging", False)}'
            f'{_r("line_width", 0.1)}<dia:attribute name="line_color"><dia:color val="#000000"/></dia:attribute>'
            f'<dia:attribute name="fill_color"><dia:color val="#ffffff"/></dia:attribute>'
            f'<dia:attribute name="text_color"><dia:color val="#000000"/></dia:attribute>'
            f'{_f("normal_font", "monospace", 0, "Courier")}{fuente_miembro_abstracto}'
            f'{_f("polymorphic_font", "monospace", 8, "Courier-Oblique")}{fuente_nombre}'
            f'{fuente_abstracta}{_f("comment_font", "sans", 8, "Helvetica-Oblique")}'
            f'{_r("normal_font_height", 0.8)}{_r("polymorphic_font_height", 0.8)}{_r("abstract_font_height", 0.8)}'
            f'{_r("classname_font_height", 1)}{_r("abstract_classname_font_height", 1)}{_r("comment_font_height", 1)}'
            f'<dia:attribute name="attributes">{ats}</dia:attribute><dia:attribute name="operations">{ops}</dia:attribute>'
            f'{_b("template", False)}<dia:attribute name="templates"/>'
            f'<dia:connections/>{_hijo_xml(c.get("_padre_id"))}</dia:object>\n')


def punto_conexion(caja, otra):
    """(índice, (x, y)) del punto de conexión de una clase de caja `caja` que mira hacia `otra` (las mismas
    reglas que la conexión automática del plugin): centro de arriba o de abajo si están una sobre otra,
    si no el lado a la altura del nombre. Índices de Dia: 1 arriba, 6 abajo, 3 izquierda, 4 derecha."""
    x, y, w, h = caja; ox, oy, ow, oh = otra
    dx, dy = ox + ow / 2 - (x + w / 2), oy + oh / 2 - (y + h / 2)
    sep_v = oy >= y + h or oy + oh <= y
    sep_h = ox >= x + w or ox + ow <= x
    if sep_v and (not sep_h or abs(dy) * 1.3 >= abs(dx)):
        return (6, (x + w / 2, y + h)) if dy > 0 else (1, (x + w / 2, y))
    return (4, (x + w, y + 0.7)) if dx > 0 else (3, (x, y + 0.7))


def orientacion(r):
    """(inicio_es_a, sentido) de una asociación, agregación o composición. `sentido` es la propiedad «direction» de Dia:
    1 dibuja el triángulo de lectura ▶ y 2 lo dibuja ◀; en agregación y composición decide también dónde va el rombo
    (1 → en el extremo A, 2 → en el B). El triángulo es siempre horizontal: para que apunte de verdad hacia la clase de
    r["lectura"] ("a" o "de"), se mira dónde queda cada clase (r["_cx"] = (centro x de «de», centro x de «a»)) y, en la
    agregación y la composición, se elige qué extremo es A para que rombo y triángulo cuadren."""
    t = TIPOS_REL[r["tipo"]]
    inicio_es_a = t["inicio_es_a"]
    sentido = 1 if inicio_es_a else 0
    if t["dia"] == "UML - Association" and r.get("lectura") in ("a", "de"):
        cde, ca = r.get("_cx") or (0.0, 0.0)
        hacia, otro = (ca, cde) if r["lectura"] == "a" else (cde, ca)
        sentido = 1 if hacia >= otro else 2
        if t.get("assoc_type"): inicio_es_a = sentido == 1
    return inicio_es_a, sentido


def _relacion_xml(r, oid, p0, p1, meta=None, conexiones=""):
    """Una relación (tipo de TIPOS_REL) de p0 (extremo «inicio» de Dia) a p1 («fin»).
    r: {"tipo", "nombre", "mult": [de, a], "roles": [de, a], "direccion": "a"|"de"|"ambas"|"", "estereotipo", "tag"}."""
    t = TIPOS_REL[r["tipo"]]
    (x0, y0), (x1, y1) = p0, p1
    if r.get("_ruta") and len(r["_ruta"][0]) >= 3: pts, ori = r["_ruta"]   # trazo de dia_planes (con 2 puntos Dia se cierra)
    elif abs(y1 - y0) >= abs(x1 - x0):
        ym = (y0 + y1) / 2; pts, ori = [(x0, y0), (x0, ym), (x1, ym), (x1, y1)], (1, 0, 1)
    else:
        xm = (x0 + x1) / 2; pts, ori = [(x0, y0), (xm, y0), (xm, y1), (x1, y1)], (0, 1, 0)
    (x0, y0), (x1, y1) = pts[0], pts[-1]
    caja = f"{min(x0, x1) - 0.5},{min(y0, y1) - 0.5};{max(x0, x1) + 0.5},{max(y0, y1) + 0.5}"
    geo = (f'<dia:attribute name="obj_pos"><dia:point val="{x0},{y0}"/></dia:attribute>'
           f'<dia:attribute name="obj_bb"><dia:rectangle val="{caja}"/></dia:attribute>'
           + _meta_xml(dict(meta or {}, tutor=r.get("tag")))
           + '<dia:attribute name="orth_points">' + "".join(f'<dia:point val="{a},{b}"/>' for a, b in pts) + '</dia:attribute>'
           + '<dia:attribute name="orth_orient">' + "".join(f'<dia:enum val="{o}"/>' for o in ori) + '</dia:attribute>'
           + _b("orth_autoroute", r.get("_autoruta", True)) + _b("autorouting", r.get("_autoruta", True))
           + '<dia:attribute name="text_colour"><dia:color val="#000000"/></dia:attribute>'
           + '<dia:attribute name="line_colour"><dia:color val="#000000"/></dia:attribute>')
    nombre = r.get("nombre", "") or ""
    if t["dia"] == "UML - Association":
        mult, roles = list(r.get("mult") or ["", ""]), list(r.get("roles") or ["", ""])
        inicio_es_a, sentido = orientacion(r)
        if inicio_es_a:               # el extremo A (inicio) es «a» (el todo, en agregación y composición)
            ma, mb, ra, rb = mult[1], mult[0], roles[1], roles[0]
        else:
            ma, mb, ra, rb = mult[0], mult[1], roles[0], roles[1]
        d = r.get("direccion") or ""
        flecha_de, flecha_a = d in ("de", "ambas"), d in ("a", "ambas")
        fa, fb = (flecha_a, flecha_de) if inicio_es_a else (flecha_de, flecha_a)
        props = _e("direction", sentido) + _e("assoc_type", t.get("assoc_type", 0))
        ver_lectura = r.get("lectura") in ("a", "de") and bool(nombre)           # el triángulo ▶/◀ junto al verbo (convención 25)
        cuerpo = (_s("name", nombre) + props + _b("show_direction", ver_lectura)
                  + _s("role_a", ra) + _s("multipicity_a", ma) + _e("visibility_a", 3) + _b("show_arrow_a", fa)
                  + _s("role_b", rb) + _s("multipicity_b", mb) + _e("visibility_b", 3) + _b("show_arrow_b", fb) + geo)
        version = 2
    else:
        cuerpo = geo + _s("name", nombre) + _s("stereotype", r.get("estereotipo", "") or t.get("estereotipo", ""))
        if t["dia"] == "UML - Dependency": cuerpo += _b("draw_arrow", True)
        version = 1
    return (f'<dia:object type="{t["dia"]}" version="{version}" id="{oid}">{cuerpo}'
            f'<dia:connections>{conexiones}</dia:connections></dia:object>\n')


def medidas_nota(texto):
    lineas = (texto or " ").split("\n")
    return round(0.42 * max(len(l) for l in lineas) + 1.2, 2), round(0.8 * len(lineas) + 0.9, 2)


def _nota_xml(n, oid):
    """Una nota UML: {"texto", "pos": (x, y), "tag"}."""
    x, y = n.get("pos", (2, 2)); w, h = medidas_nota(n["texto"])
    return (f'<dia:object type="UML - Note" version="0" id="{oid}">'
            f'<dia:attribute name="obj_pos"><dia:point val="{x},{y}"/></dia:attribute>'
            f'<dia:attribute name="obj_bb"><dia:rectangle val="{x - 0.05},{y - 0.05};{x + w + 0.05},{y + h + 0.05}"/></dia:attribute>'
            f'{_meta_xml({"tutor": n.get("tag")})}'
            f'<dia:attribute name="elem_corner"><dia:point val="{x},{y}"/></dia:attribute>{_r("elem_width", w)}{_r("elem_height", h)}'
            f'{_r("line_width", 0.1)}<dia:attribute name="line_colour"><dia:color val="#000000"/></dia:attribute>'
            f'<dia:attribute name="fill_colour"><dia:color val="#ffffff"/></dia:attribute>'
            f'<dia:attribute name="text"><dia:composite type="text">{_s("string", n["texto"])}'
            f'{_f("font", "monospace", 0, "Courier")}{_r("height", 0.8)}'
            f'<dia:attribute name="pos"><dia:point val="{x + 0.35},{y + 1.185}"/></dia:attribute>'
            f'<dia:attribute name="color"><dia:color val="#000000"/></dia:attribute>{_e("alignment", 0)}'
            f'</dia:composite></dia:attribute></dia:object>\n')


def caja_estimada(c):
    x, y = c.get("pos", (2, 2)); w, h = medidas(c)
    return (x, y, w, h)


def escribir(ruta, clases, relaciones=(), notas=()):
    """Escribe un .dia (sin comprimir) con estas clases ([{"nombre", "pos": (x, y), "atributos": [...], "metodos": [...]}]),
    relaciones ([{"tipo", "de", "a", ...}] entre nombres de esas clases, pegadas de verdad con <dia:connections>)
    y notas ([{"texto", "pos"}]). Las líneas se dibujan con cajas estimadas: Dia las recoloca al mover una clase."""
    ids = {c["nombre"]: f"O{i}" for i, c in enumerate(clases)}
    cajas = {c["nombre"]: caja_estimada(dict(c, pos=c.get("pos", (2 + 12 * i, 2)))) for i, c in enumerate(clases)}
    partes = [_clase_xml(c, i) for i, c in enumerate(clases)]
    for k, r in enumerate(relaciones):
        r = dict(r, _cx=((cajas[r["de"]][0] + cajas[r["de"]][2] / 2), (cajas[r["a"]][0] + cajas[r["a"]][2] / 2)))
        ini, fin = (r["a"], r["de"]) if orientacion(r)[0] else (r["de"], r["a"])
        (ci, p0), (cf, p1) = punto_conexion(cajas[ini], cajas[fin]), punto_conexion(cajas[fin], cajas[ini])
        con = (f'<dia:connection handle="0" to="{ids[ini]}" connection="{ci}"/>'
               f'<dia:connection handle="1" to="{ids[fin]}" connection="{cf}"/>')
        partes.append(_relacion_xml(r, f"R{k}", p0, p1, conexiones=con))
    partes += [_nota_xml(n, f"N{k}") for k, n in enumerate(notas)]
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(CABECERA + "".join(partes) + PIE)


def escribir_para_anadir(ruta, clases=(), relaciones=(), notas=(), extra=(), fondo=()):
    """El archivo que el plugin AÑADE a un diagrama abierto (orden «anadir»). Cada relación trae
    "ref_de" y "ref_a" (p. ej. "tag:p1.2" para un objeto de este mismo archivo, "clase:Estudiante" para una
    clase que ya está; con "#N" se fija el punto de conexión, si no es automático) y el plugin las pega."""
    partes = list(fondo)                             # contenedores (límite del sistema, paquetes, nodos, calles): detrás de todo
    partes += [_clase_xml(c, i, f"C{i}") for i, c in enumerate(clases)]
    partes += list(extra)                            # objetos de cualquier otro tipo, ya en XML (dia_objetos / dia_planes)
    for k, r in enumerate(relaciones):               # las relaciones encima: sus rótulos («include», nombres) no quedan tapados
        t = TIPOS_REL[r["tipo"]]
        inicio_es_a, _ = orientacion(r)
        ini, fin = (r["ref_a"], r["ref_de"]) if inicio_es_a else (r["ref_de"], r["ref_a"])
        pts = r.get("puntos") or ((0, 0), (4, 4))          # del plan (inicio, fin) o de leer() (todos los puntos de la línea)
        p0, p1 = pts[0], pts[-1]
        if inicio_es_a != t["inicio_es_a"]:                # el triángulo de lectura dio la vuelta a la línea: sus puntos también
            p0, p1 = p1, p0
            if r.get("_ruta"): r = dict(r, _ruta=(list(reversed(r["_ruta"][0])), tuple(reversed(r["_ruta"][1]))))
        partes.append(_relacion_xml(r, f"R{k}", p0, p1, meta={"conecta_inicio": ini, "conecta_fin": fin}))
    partes += [_nota_xml(n, f"N{k}") for k, n in enumerate(notas)]
    texto = CABECERA + "".join(partes) + PIE
    for m in re.finditer(r'<dia:attribute name="orth_points">(.*?)</dia:attribute>', texto, re.S):
        if m.group(1).count("<dia:point") < 3:        # Dia 0.97 se cierra al leer una línea ortogonal de menos de 3 puntos
            raise ValueError("una línea ortogonal con menos de 3 puntos")
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        f.write(texto)


# ---------- Revisar el «Tu turno» (sin IA) ----------
def _norm(s):
    s = unicodedata.normalize("NFD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"\s+", "", s).lower()


def _tipo_ok(dado, esperado, sinonimos):
    d, e = _norm(dado), _norm(esperado)
    return d == e or d in {_norm(x) for x in sinonimos.get(esperado, [])}


def buscar_metodo(lista, m, esperados, sin, usados=None):
    """El método de `lista` que corresponde al esperado `m`: por nombre, y por FIRMA (nombre y tipos de los parámetros) cuando hay
    sobrecarga (varios con el mismo nombre, en lo esperado o en lo dibujado). Devuelve (método o None, ¿sobrecargado?)."""
    usados = usados if usados is not None else set()
    cands = [x for x in lista if _norm(x["nombre"]) == _norm(m["nombre"])]
    sobre = len(cands) > 1 or sum(1 for q in esperados if _norm(q["nombre"]) == _norm(m["nombre"])) > 1
    if not sobre: return (cands[0] if cands else None), False
    pe = m.get("params", [])
    for x in cands:
        if id(x) in usados or len(x.get("params", [])) != len(pe): continue
        if all(_tipo_ok(a.get("tipo", ""), b.get("tipo", ""), sin) for a, b in zip(x["params"], pe)): return x, True
    return None, True


def _revisar_miembros(c, esp, sin, conv=None):
    """Puntos de los atributos y métodos esperados (esp["atributos"], esp["metodos"]) en la clase c, y lo que sobra.
    Con esp["_varias"] (ejercicios de varias clases) los textos dicen también de qué clase es cada miembro."""
    puntos, nc = [], c["nombre"]
    en = f" en «{nc}»" if esp.get("_varias") else ""

    def buscar(lista, nombre):
        return next((x for x in lista if _norm(x["nombre"]) == _norm(nombre)), None)

    for a in esp.get("atributos") or []:
        dado = buscar(c["atributos"], a["nombre"])
        pegado = next((x for x in c["atributos"] if ":" in x["nombre"] and _norm(x["nombre"].split(":")[0]) == _norm(a["nombre"])), None)
        como_metodo = buscar(c["metodos"], a["nombre"])
        obj = f"{nc}.{a['nombre']}"
        if pegado:
            puntos.append({"ok": False, "objetivo": obj, "texto": f"Escribiste «{pegado['nombre']}» todo en Nombre: en Dia el tipo va en su propio campo, Tipo."})
        elif como_metodo and not dado:
            puntos.append({"ok": False, "objetivo": obj, "texto": f"«{a['nombre']}» quedó como método (pestaña Operaciones); es un atributo: va en la pestaña Atributos."})
        elif not dado:
            puntos.append({"ok": False, "objetivo": nc, "texto": f"Falta el atributo «{a['nombre']}»{en}."})
        elif not _tipo_ok(dado["tipo"], a["tipo"], sin):
            puntos.append({"ok": False, "objetivo": obj, "texto": f"«{a['nombre']}» debería ser de tipo {a['tipo']}" + (f", no {dado['tipo']}." if dado["tipo"] else "; el campo Tipo está vacío.")})
        elif dado["vis"] != a.get("vis", "+"):
            puntos.append({"ok": False, "objetivo": obj, "texto": f"«{a['nombre']}» debería ser {VIS_NOMBRE[a.get('vis', '+')]}, no {VIS_NOMBRE[dado['vis']]}."})
        else:
            puntos.append({"ok": True, "objetivo": obj, "texto": f"Atributo {linea_atributo(dado)}{en}."})

    usados = set()
    for m in esp.get("metodos") or []:
        dado, sobrecargado = buscar_metodo(c["metodos"], m, esp.get("metodos") or [], sin, usados)
        pegado = next((x for x in c["metodos"] if "(" in x["nombre"] and _norm(x["nombre"].split("(")[0]) == _norm(m["nombre"])), None)
        obj = f"{nc}.{m['nombre']}"
        if pegado:
            puntos.append({"ok": False, "objetivo": obj, "texto": f"Escribiste «{pegado['nombre']}» en Nombre: los paréntesis y los parámetros no van ahí, van en la lista de Parámetros, y el tipo de retorno en Tipo."})
            continue
        if not dado:
            firma = linea_metodo(dict(m, tipo="", vis=""))
            hay = [x for x in c["metodos"] if _norm(x["nombre"]) == _norm(m["nombre"]) and id(x) not in usados]
            if sobrecargado:        # varios métodos con el mismo nombre (sobrecarga): se distinguen por los tipos de sus parámetros
                puntos.append({"ok": False, "objetivo": nc, "texto": f"Falta la versión «{firma}» del método «{m['nombre']}»{en}"
                               + (f" (tienes {', '.join('«' + linea_metodo(dict(x, tipo='', vis='')) + '»' for x in hay)})." if hay else " (es una sobrecarga: mismo nombre, otros parámetros).")})
            else: puntos.append({"ok": False, "objetivo": nc, "texto": f"Falta el método «{m['nombre']}»{en}."})
            continue
        usados.add(id(dado))
        problema, params = None, m.get("params", [])
        if len(dado["params"]) != len(params):
            problema = f"«{m['nombre']}» debería tener {len(params)} parámetro(s) y tiene {len(dado['params'])}."
        else:
            for pe, pd in zip(params, dado["params"]):
                if not pe["nombre"] and pd["nombre"] and (conv or {}).get("parametros") == "solo_tipo":    # K1: los parámetros, solo con el tipo
                    cod = ((conv.get("codigos") or {}).get("parametros")) or "K1"
                    solo = f"{m['nombre']}(" + ", ".join(q["tipo"] for q in params) + ")"
                    problema = (f"Pusiste el parámetro con nombre ({linea_param(pd)}) en «{m['nombre']}»; este curso lo pide solo con el tipo: {solo} ({cod}). "
                                f"En Dia: doble clic en la clase → pestaña «Operaciones» → selecciona el método → en «Datos de parámetros» deja vacío el campo «Nombre» y escribe solo el «Tipo»."); break
                if (pe["nombre"] and _norm(pe["nombre"]) != _norm(pd["nombre"])) or not _tipo_ok(pd["tipo"], pe["tipo"], sin):
                    problema = f"En «{m['nombre']}» el parámetro debería ser {linea_param(pe)}" + (f", no {linea_param(pd) or '(vacío)'}." if pd else "."); break
        if not problema and not _tipo_ok(dado["tipo"], m.get("tipo", ""), sin):
            problema = f"«{m['nombre']}» debería devolver {m['tipo']}" + (f", no {dado['tipo']}." if dado["tipo"] else "; el campo Tipo está vacío.")
        if not problema and dado["vis"] != m.get("vis", "+"):
            problema = f"«{m['nombre']}» debería ser {VIS_NOMBRE[m.get('vis', '+')]}, no {VIS_NOMBRE[dado['vis']]}."
        puntos.append({"ok": not problema, "objetivo": obj, "texto": problema or f"Método {linea_metodo(dado)}{en}."})

    esperados = {_norm(x["nombre"]) for x in (esp.get("atributos") or []) + (esp.get("metodos") or [])}
    sobran = [x["nombre"] for x in c["atributos"] + c["metodos"] if _norm(re.split(r"[:(]", x["nombre"])[0]) not in esperados]
    return puntos, sobran


def _resultado(puntos, total, consejos, turno):
    ok = sum(p["ok"] for p in puntos)
    if ok == total:
        estado = "casi" if consejos else "bien"
        mensaje = (" ".join(consejos) if consejos else turno.get("al_terminar", "¡Todo bien!"))
    else:
        estado = "mal"
        primero = next(p for p in puntos if not p["ok"])
        mensaje = primero["texto"] + (" " + " ".join(consejos) if consejos else "")
    return {"estado": estado, "ok": ok, "total": total, "puntos": puntos, "mensaje": mensaje}


def revisar(d, turno):
    """Compara el diagrama con la clase esperada. Devuelve estado, conteo y una lista de puntos
    {ok, texto, objetivo}; el objetivo ("Clase" o "Clase.miembro") sirve para marcarlo en el dibujo."""
    esp, sin = turno["clase"], turno.get("sinonimos", {})
    total = 1 + len(esp["atributos"]) + len(esp["metodos"])
    if not d["clases"]:
        return {"estado": "vacio", "ok": 0, "total": total, "puntos": [],
                "mensaje": turno.get("al_empezar", "Pon una clase en el diagrama, guarda (Ctrl+S) y pulsa Comprobar.")}
    puntos = []
    c = next((c for c in d["clases"] if _norm(c["nombre"]) == _norm(esp["nombre"])), None)
    if c is None:
        c = d["clases"][0] if len(d["clases"]) == 1 else None
        if c is None:
            return {"estado": "mal", "ok": 0, "total": total, "puntos": [],
                    "mensaje": f"No encuentro la clase «{esp['nombre']}». Revisa cómo se llama."}
        puntos.append({"ok": False, "objetivo": c["nombre"],
                       "texto": f"La clase se llama «{c['nombre']}»; debería llamarse «{esp['nombre']}»."})
    else:
        puntos.append({"ok": True, "objetivo": c["nombre"], "texto": f"Clase «{c['nombre']}»."})
    miembros, sobran = _revisar_miembros(c, esp, sin)
    puntos += miembros
    consejos = []
    if sobran: consejos.append("Sobra: " + ", ".join(f"«{s}»" for s in sobran) + ".")
    if c["nombre"][:1].islower(): consejos.append("Por convención, el nombre de una clase empieza con mayúscula.")
    return _resultado(puntos, total, consejos, turno)


def _mult(s):
    s = re.sub(r"\s+", "", str(s or "")).lower()
    s = re.sub(r"(?<![a-z])[nm](?![a-z])", "*", s)
    return {"0..*": "*"}.get(s, s)


def revisar_varios(d, ej, conv=None):
    """Revisión sin IA de un ejercicio del tutor con varias clases y relaciones:
    ej = {"clases": [{"nombre", "atributos"?: [...], "metodos"?: [...], "abstracta"?: bool, "interfaz"?: bool}],
          "relaciones": [{"tipo", "de", "a", "mult"?: [de, a]}], "sinonimos"?, "al_empezar"?, "al_terminar"?}.
    Atributos y métodos como los del «Tu turno» (dicts de miembro()); si una clase no trae "atributos"
    ni "metodos", solo se mira que exista. Devuelve lo mismo que revisar().
    `conv` son las convenciones del curso (curso.json): si trae «nombre_negrita», «parametros» o «estricto», se suman las reglas de
    reglas_uml (cada una, un punto más con el número de la convención). Además, cada clase esperada puede traer "dentro_de",
    "biblioteca", "enumerada" y cada relación "nombre", "lectura" y "direccion" (se revisan siempre que estén)."""
    sin = ej.get("sinonimos", {})
    clases_esp, rels_esp = ej.get("clases", []), ej.get("relaciones", [])
    total = sum(1 + len(c.get("atributos") or []) + len(c.get("metodos") or []) + ("abstracta" in c) + bool(c.get("interfaz"))
                for c in clases_esp) + len(rels_esp)
    otros = []
    if ej.get("objetos") or ej.get("conexiones") or ej.get("mensajes"):     # casos de uso, secuencia, actividades, estados...
        import dia_planes
        otros, t2, consejos2 = dia_planes.revisar(d, ej)
        total += t2
    if not d["clases"] and not d.get("relaciones") and not d.get("objetos"):
        return {"estado": "vacio", "ok": 0, "total": total, "puntos": [],
                "mensaje": ej.get("al_empezar", "Dibuja el diagrama en Dia, guarda (Ctrl+S) y pulsa Comprobar.")}
    por_nombre = {_norm(c["nombre"]): c for c in d["clases"]}
    puntos, consejos, sobran = [], [], []
    for e in clases_esp:
        c = por_nombre.get(_norm(e["nombre"]))
        if not c:
            puntos.append({"ok": False, "objetivo": "", "texto": f"Falta la clase «{e['nombre']}»."}); continue
        puntos.append({"ok": True, "objetivo": c["nombre"], "texto": f"Clase «{c['nombre']}»."})
        if "abstracta" in e:
            bien = c["abstracta"] == bool(e["abstracta"])
            if bien: texto = f"«{c['nombre']}» es abstracta." if e["abstracta"] else f"«{c['nombre']}» no es abstracta."
            elif e["abstracta"]: texto = f"«{c['nombre']}» debería ser abstracta (en Propiedades, casilla Abstracta: el nombre sale en cursiva)."
            else: texto = f"«{c['nombre']}» no debería ser abstracta."
            puntos.append({"ok": bien, "objetivo": c["nombre"], "texto": texto})
        if e.get("interfaz"):
            bien = es_interfaz(c)
            puntos.append({"ok": bien, "objetivo": c["nombre"], "texto": f"«{c['nombre']}» es una interfaz." if bien else
                           f"«{c['nombre']}» debería ser una interfaz: en Propiedades, Estereotipo «interface»."})
        if e.get("enumerada") is not None or e.get("biblioteca"):       # sus miembros los revisa reglas_uml (valores; vacía)
            if e.get("biblioteca") and (c["atributos"] or c["metodos"]) and not (conv or {}).get("estricto"):
                sobran += [f"{c['nombre']}.{x['nombre']}" for x in c["atributos"] + c["metodos"]]
            continue
        m, s = _revisar_miembros(c, dict(e, _varias=True), sin, conv)
        puntos += m
        if (e.get("atributos") is not None or e.get("metodos") is not None) and s: sobran += [f"{c['nombre']}.{x}" for x in s]
    usadas = set()
    pares = []                                                       # (esperada, leída) ya emparejadas: para reglas_uml
    rels = d.get("relaciones", [])
    for e in rels_esp:
        nombre_t = TIPOS_REL[e["tipo"]]["nombre"]
        de, a = _norm(e["de"]), _norm(e["a"])
        entre = [r for r in rels if {_norm(r.get("de") or ""), _norm(r.get("a") or "")} == {de, a} and id(r) not in usadas]
        def orientada(r): return _norm(r.get("de") or "") == de and _norm(r.get("a") or "") == a
        igual = [r for r in entre if r["tipo"] == e["tipo"] and (orientada(r) or e["tipo"] == "asociacion")]
        frase = frase_relacion({"tipo": e["tipo"], "de": e["de"], "a": e["a"]})
        if igual:
            r = igual[0]; usadas.add(id(r)); pares.append((e, r))
            texto = None
            if e.get("mult"):
                dado = r["mult"] if orientada(r) else list(reversed(r["mult"]))
                for lado, quiere, hay in zip((e["de"], e["a"]), e["mult"], dado):
                    if quiere and _mult(quiere) != _mult(hay):
                        texto = (f"En la {nombre_t} entre «{e['de']}» y «{e['a']}», la multiplicidad junto a «{lado}» debería ser {quiere}"
                                 + (f", no {hay}." if hay else "; está vacía.")); break
            puntos.append({"ok": not texto, "objetivo": r.get("de") or e["de"], "texto": texto or (frase[:1].upper() + frase[1:] + ".")})
        elif any(r["tipo"] == e["tipo"] for r in entre):
            usadas.add(id(next(r for r in entre if r["tipo"] == e["tipo"])))
            puntos.append({"ok": False, "objetivo": e["de"], "texto": f"La {nombre_t} entre «{e['de']}» y «{e['a']}» está al revés: "
                                                                        f"el símbolo (triángulo, flecha o rombo) va junto a «{e['a']}»."})
        elif entre:
            r = entre[0]; usadas.add(id(r))
            extra = " (rombo vacío = agregación, lleno = composición)" if {r["tipo"], e["tipo"]} <= {"agregacion", "composicion"} else ""
            puntos.append({"ok": False, "objetivo": e["de"], "texto": f"Entre «{e['de']}» y «{e['a']}» pusiste una {TIPOS_REL[r['tipo']]['nombre']}; "
                                                                        f"debería ser una {nombre_t}{extra}."})
        else:
            corta = {"herencia": f"{e['de']} hereda de {e['a']}", "realizacion": f"{e['de']} implementa {e['a']}",
                     "dependencia": f"{e['de']} usa {e['a']}", "asociacion": f"entre {e['de']} y {e['a']}",
                     "agregacion": f"{e['a']} (todo, rombo vacío) con {e['de']} (parte)",
                     "composicion": f"{e['a']} (todo, rombo lleno) con {e['de']} (parte)"}[e["tipo"]]
            puntos.append({"ok": False, "objetivo": e["de"] if de in por_nombre else "", "texto": f"Falta la {nombre_t}: {corta}."})
    sueltas = [r for r in rels if not r.get("de") or not r.get("a")]
    if sueltas: consejos.append(f"Hay {len(sueltas)} relación(es) con un extremo suelto: arrastra cada punta hasta su clase hasta que se pegue.")
    esperadas = {_norm(c["nombre"]) for c in clases_esp}
    sobran = [c["nombre"] for c in d["clases"] if _norm(c["nombre"]) not in esperadas] + sobran
    otras = [r for r in rels if id(r) not in usadas and r.get("de") and r.get("a")]
    if otros:
        puntos += otros; consejos += consejos2
        sobran = sobran if clases_esp else []                      # en un diagrama sin clases esperadas no «sobran» clases
        otras = [r for r in otras if r["tipo"] in TIPOS_REL and not ej.get("conexiones")]
    if sobran: consejos.append("Sobra: " + ", ".join(f"«{s}»" for s in sobran) + ".")
    if otras: consejos.append("Sobra: " + "; ".join(frase_relacion(r) for r in otras) + ".")
    import reglas_uml                                                # convenciones del curso (negrita, estilo, parentesco...)
    reglas = reglas_uml.revisar(d, ej, conv) + reglas_uml.relaciones(pares, conv)
    if (conv or {}).get("estricto"):                                 # el toString que falta lo dice la convención 17, no el aviso genérico
        faltan = {x["objetivo"] for x in reglas if x["texto"].startswith("Falta +toString()")}
        antes = len(puntos)
        puntos = [p for p in puntos if not (p["texto"].startswith("Falta el método «toString»") and p["objetivo"] in faltan)]
        total -= antes - len(puntos)
    puntos += reglas; total += len(reglas)
    return _resultado(puntos, total, consejos, ej)


# ---------- Marcas del tutor dentro de Dia (órdenes del plugin, capa «Tutor») ----------
COLORES_MARCA = ("rojo", "verde", "amarillo", "azul")


def _txt(s):
    """Texto seguro para una orden del plugin (va entre comillas dobles)."""
    return '"' + re.sub(r"\s+", " ", str(s or "")[:80]).replace("\\", "/").replace('"', "'").strip() + '"'


def _borde(r, px, py, margen=0.15):
    """Punto del borde del rectángulo r (x, y, w, h), ampliado en `margen`, en la dirección de (px, py)."""
    x, y, w, h = r[0] - margen, r[1] - margen, r[2] + 2 * margen, r[3] + 2 * margen
    cx, cy = x + w / 2, y + h / 2; dx, dy = px - cx, py - cy
    if dx == 0 and dy == 0: return cx, cy
    t = min(w / 2 / abs(dx) if dx else 1e9, h / 2 / abs(dy) if dy else 1e9)
    return cx + dx * t, cy + dy * t


def _choca(a, b, holgura=0.3):
    return not (a[0] + a[2] + holgura <= b[0] or b[0] + b[2] + holgura <= a[0] or
                a[1] + a[3] + holgura <= b[1] or b[1] + b[3] + holgura <= a[1])


def ordenes_marcas(marcas, cajas, archivo=None):
    """Traduce las marcas del tutor (las mismas del SVG: marco, nota, flecha; objetivo "Clase" o
    "Clase.miembro") a órdenes del plugin, en cm. `cajas` viene de cajas_de_plugin (lo que hay en
    pantalla) o de cajas_cm (lo guardado). Devuelve (órdenes, cuántas marcas se pudieron colocar).
    Las notas y los rótulos de las flechas se ponen a la derecha de su clase (o de todas, si hay otra
    clase en medio) y buscan hueco hacia arriba y hacia abajo para no encimarse.
    Siguiente paso (pendiente): tipos que CREEN cosas (clase, atributo, relación) irían en otro
    diccionario como DIBUJAR, con órdenes sobre la capa activa (p. ej. la orden «clase» del plugin)."""
    pre = f"@{archivo} " if archivo else ""
    norm = {_norm(k): v for k, v in cajas.items()}
    clases = [v for k, v in cajas.items() if "." not in k]
    derecha = max((c[0] + c[2] for c in clases), default=0)
    ocupado = []                                  # notas y rótulos ya puestos
    f = lambda v: f"{v:.3f}"

    def es_fila(clave): return "." in (clave or "")
    def clase_de(clave): return norm.get(_norm((clave or "").split(".")[0]))

    def colocar(x, y, w, h, propia):
        """Primer hueco libre cerca de (x, y): ni encima de otra clase ni de otra nota."""
        if any(_choca((x, y, w, h), o) for o in clases if o is not propia): x = derecha + 1.4
        for k in range(0, 30):
            yy = y + (k + 1) // 2 * (h + 0.3) * (1 if k % 2 else -1) if k else y
            if not any(_choca((x, yy, w, h), n, 0.15) for n in ocupado) and \
               not any(_choca((x, yy, w, h), o, 0.15) for o in clases if o is not propia):
                y = yy; break
        ocupado.append((x, y, w, h))
        return x, y

    def rotulo(texto, x, y, propia):
        """Orden «nota» con la caja estimada del texto (negrita 0,7 cm ≈ 0,31 cm por letra)."""
        w, h = 0.55 + 0.31 * (len(texto) - 2), 0.95
        x, y = colocar(x, y - h / 2, w, h, propia)
        return x, y, w, h

    def marco(mk, col):
        r = norm.get(_norm(mk.get("objetivo", "")))
        if not r: return None
        mx, my = (0.06, 0.02) if es_fila(mk.get("objetivo")) else (0.15, 0.15)
        return [f"recuadro {f(r[0] - mx)} {f(r[1] - my)} {f(r[2] + 2 * mx)} {f(r[3] + 2 * my)} {col} {0.08 if es_fila(mk.get('objetivo')) else 0.1}"]

    def nota(mk, col):
        r = norm.get(_norm(mk.get("objetivo", "")))
        ordenes = marco(mk, col)
        if not ordenes: return None
        texto = _txt(mk.get("texto", ""))
        if len(texto) <= 2: return ordenes
        c = clase_de(mk.get("objetivo")) or r
        x, y, w, h = rotulo(texto, c[0] + c[2] + 1.4, r[1] + r[3] / 2, c)
        hx, hy = r[0] + r[2] + (0.06 if es_fila(mk.get("objetivo")) else 0.15), r[1] + r[3] / 2
        return ordenes + [f"nota {f(x + 0.2)} {f(y + 0.14)} {texto} {col} {f(hx)} {f(hy)}"]

    def flecha(mk, col):
        a, b = norm.get(_norm(mk.get("desde", ""))), norm.get(_norm(mk.get("hasta", "")))
        if not (a and b) or a == b: return None
        ca, cb = (a[0] + a[2] / 2, a[1] + a[3] / 2), (b[0] + b[2] / 2, b[1] + b[3] / 2)
        if a[0] == b[0] and a[2] == b[2]:        # dos filas de la misma clase: la flecha va por fuera, a la derecha
            x = a[0] + a[2] + 0.4
            x1, y1, x2, y2 = x + 0.9, ca[1], x, cb[1]
        else:
            x1, y1 = _borde(a, *cb); x2, y2 = _borde(b, *ca)
        ordenes = [f"flecha {f(x1)} {f(y1)} {f(x2)} {f(y2)} {col} 0.08"]
        texto = _txt(mk.get("texto", ""))
        if len(texto) > 2:                       # el rótulo, como una nota sin flecha junto al punto medio
            propia = clase_de(mk.get("desde")) if a[0] == b[0] else None
            x, y, w, h = rotulo(texto, max(x1, x2) + 0.5, (y1 + y2) / 2, propia)
            ordenes.append(f"nota {f(x + 0.2)} {f(y + 0.14)} {texto} {col}")
        return ordenes

    DIBUJAR = {"marco": marco, "nota": nota, "flecha": flecha}
    ordenes, n = [], 0
    for mk in marcas or []:
        hacer = DIBUJAR.get(mk.get("tipo"))
        col = mk.get("color") if mk.get("color") in COLORES_MARCA else "rojo"
        res = hacer(mk, col) if hacer else None
        if res: ordenes += [pre + o for o in res]; n += 1
    return ordenes, n


# ---------- Dibujar en SVG (para el panel), con marcas ----------
ESCALA = 34          # píxeles por centímetro de Dia
COLORES = {"rojo": "#c02828", "verde": "#1e8c46", "amarillo": "#d79100", "azul": "#1e5ac8"}


def _cajas(d):
    """Posición en pantalla de cada clase y de cada fila: {"Clase": (x, y, w, h), "Clase.miembro": (...)}.
    Las notas van en d["_notas_svg"] (x, y, w, h, texto)."""
    cajas, fila = {}, 0.8 * ESCALA
    todas = [c["caja"] for c in d["clases"]] + [n["caja"] for n in d.get("notas", [])]
    xs = [c[0] for c in todas] or [0]; ys = [c[1] for c in todas] or [0]
    ox, oy = min(xs) - 0.6, min(ys) - 0.6
    for c in d["clases"]:
        x, y = (c["caja"][0] - ox) * ESCALA, (c["caja"][1] - oy) * ESCALA
        filas = [linea_atributo(a) for a in c["atributos"]] + [linea_metodo(m) for m in c["metodos"]] + [c["nombre"]]
        w = max(150, max(len(f) for f in filas) * 8.4 + 42)     # por el texto (el ancho guardado depende de la fuente de Dia)
        h_nombre = (1.75 if c.get("estereotipo") else 1.3) * ESCALA
        h_at, h_me = max(1, len(c["atributos"])) * fila + 6, max(1, len(c["metodos"])) * fila + 6
        cajas[c["nombre"]] = (x, y, w, h_nombre + h_at + h_me)
        for i, a in enumerate(c["atributos"]): cajas[f"{c['nombre']}.{a['nombre'].split(':')[0].strip()}"] = (x, y + h_nombre + 3 + i * fila, w, fila)
        for i, m in enumerate(c["metodos"]): cajas[f"{c['nombre']}.{m['nombre'].split('(')[0].strip()}"] = (x, y + h_nombre + h_at + 3 + i * fila, w, fila)
        c["_svg"] = (x, y, w, h_nombre, h_at, h_me)
    d["_notas_svg"] = []
    for n in d.get("notas", []):
        lineas = (n.get("texto") or " ").split("\n")
        d["_notas_svg"].append(((n["caja"][0] - ox) * ESCALA, (n["caja"][1] - oy) * ESCALA,
                                max(len(l) for l in lineas) * 7.8 + 30, len(lineas) * 17 + 16, lineas))
    return cajas


def _punto_borde(r, px, py):
    """Dónde corta el borde de la caja r (x, y, w, h) la línea desde su centro hacia (px, py)."""
    cx, cy = r[0] + r[2] / 2, r[1] + r[3] / 2; dx, dy = px - cx, py - cy
    if dx == 0 and dy == 0: return cx, cy
    t = min(r[2] / 2 / abs(dx) if dx else 1e9, r[3] / 2 / abs(dy) if dy else 1e9)
    return cx + dx * t, cy + dy * t


def _svg_relacion(r, cajas):
    """Una relación UML entre dos cajas del SVG, con su punta: triángulo vacío (herencia, realización),
    flecha abierta (dependencia, asociación navegable), rombo vacío o lleno (agregación, composición)."""
    a, b = cajas.get(r.get("de") or ""), cajas.get(r.get("a") or "")
    if not (a and b) or a == b: return ""
    ca, cb = (a[0] + a[2] / 2, a[1] + a[3] / 2), (b[0] + b[2] / 2, b[1] + b[3] / 2)
    x1, y1 = _punto_borde(a, *cb); x2, y2 = _punto_borde(b, *ca)
    t = r["tipo"]
    discontinua = ' stroke-dasharray="7 5"' if t in ("realizacion", "dependencia") else ""
    fin = {"herencia": "tri", "realizacion": "tri", "dependencia": "flecha", "agregacion": "rombo-v", "composicion": "rombo-l"}.get(t)
    if t == "asociacion" and r.get("direccion") in ("a", "ambas"): fin = "flecha"
    ini = "flecha" if t == "asociacion" and r.get("direccion") in ("de", "ambas") else None
    partes = [f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#222" stroke-width="1.6"{discontinua}'
              + (f' marker-end="url(#uml-{fin})"' if fin else "") + (f' marker-start="url(#uml-{ini}-ini)"' if ini else "") + "/>"]
    largo = max(1.0, ((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5); ux, uy = (x2 - x1) / largo, (y2 - y1) / largo
    def rotulo(x, y, s, ancla="start"):
        return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="Consolas,Courier New,monospace" font-size="12" fill="#333" '
                f'text-anchor="{ancla}">{html.escape(s)}</text>')
    m = r.get("mult") or ["", ""]
    def ancla(vx): return "start" if vx > 0.3 else "end" if vx < -0.3 else "middle"
    if m[0]: partes.append(rotulo(x1 + ux * 8 - uy * 12, y1 + uy * 8 + ux * 12 + 4 + (8 if uy > 0.7 else 0), m[0], ancla(ux)))
    if m[1]: partes.append(rotulo(x2 - ux * 8 - uy * 12, y2 - uy * 8 + ux * 12 + 4 - (8 if uy > 0.7 else 0), m[1], ancla(-ux)))
    if r.get("nombre"): partes.append(rotulo((x1 + x2) / 2 - uy * 12, (y1 + y2) / 2 + ux * 12 - 4, r["nombre"], "middle"))
    return "".join(partes)


SUBRAYADO, CURSIVA = ' text-decoration="underline"', ' font-style="italic"'
DEFS_UML = ('<marker id="uml-tri" markerWidth="16" markerHeight="14" refX="15" refY="7" orient="auto" markerUnits="userSpaceOnUse">'
            '<path d="M1,1 L15,7 L1,13 z" fill="#fff" stroke="#222" stroke-width="1.4"/></marker>'
            '<marker id="uml-flecha" markerWidth="14" markerHeight="12" refX="13" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
            '<path d="M1,1 L13,6 L1,11" fill="none" stroke="#222" stroke-width="1.5"/></marker>'
            '<marker id="uml-flecha-ini" markerWidth="14" markerHeight="12" refX="13" refY="6" orient="auto-start-reverse" markerUnits="userSpaceOnUse">'
            '<path d="M1,1 L13,6 L1,11" fill="none" stroke="#222" stroke-width="1.5"/></marker>'
            '<marker id="uml-rombo-v" markerWidth="22" markerHeight="12" refX="21" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
            '<path d="M1,6 L11,1 L21,6 L11,11 z" fill="#fff" stroke="#222" stroke-width="1.4"/></marker>'
            '<marker id="uml-rombo-l" markerWidth="22" markerHeight="12" refX="21" refY="6" orient="auto" markerUnits="userSpaceOnUse">'
            '<path d="M1,6 L11,1 L21,6 L11,11 z" fill="#222" stroke="#222" stroke-width="1.4"/></marker>')


def svg(d, marcas=(), revision=None):
    """SVG del diagrama al estilo UML: clases, relaciones (con su punta UML) y notas. `revision` pinta ✔/✘ por fila;
    `marcas` son las del tutor: {"tipo": "marco"|"nota"|"flecha", "objetivo"/"desde"/"hasta": "Clase" o "Clase.miembro", "texto", "color"}."""
    if not d["clases"] and not d.get("notas"):
        return '<svg xmlns="http://www.w3.org/2000/svg" width="420" height="120"><text x="20" y="60" font-family="sans-serif" fill="#888">El diagrama está vacío.</text></svg>'
    cajas = _cajas(d); fila = 0.8 * ESCALA; partes = []
    norm = {_norm(k): v for k, v in cajas.items()}
    for x, y, w, h, lineas in d["_notas_svg"]:
        partes.append(f'<path d="M{x},{y} h{w - 12} l12,12 v{h - 12} h{-w} z" fill="#fff" stroke="#222" stroke-width="1.3"/>'
                      f'<path d="M{x + w - 12},{y} v12 h12" fill="none" stroke="#222" stroke-width="1.1"/>'
                      + "".join(f'<text x="{x + 9}" y="{y + 20 + i * 17}" font-family="Consolas,Courier New,monospace" font-size="13">{html.escape(l)}</text>'
                                for i, l in enumerate(lineas)))
    for c in d["clases"]:
        x, y, w, hn, ha, hm = c["_svg"]
        estereo = (f'<text x="{x + w / 2}" y="{y + 15}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" font-size="12">'
                   f'«{html.escape(c["estereotipo"])}»</text>') if c.get("estereotipo") else ""
        partes.append(f'<rect x="{x}" y="{y}" width="{w}" height="{hn + ha + hm}" fill="#fff" stroke="#222" stroke-width="1.5"/>'
                      f'<line x1="{x}" y1="{y + hn}" x2="{x + w}" y2="{y + hn}" stroke="#222"/>'
                      f'<line x1="{x}" y1="{y + hn + ha}" x2="{x + w}" y2="{y + hn + ha}" stroke="#222"/>' + estereo +
                      f'<text x="{x + w / 2}" y="{y + hn * (0.78 if estereo else 0.65)}" text-anchor="middle" font-family="Helvetica,Arial,sans-serif" '
                      f'font-weight="bold" font-style="{"italic" if c["abstracta"] else "normal"}" font-size="16">{html.escape(c["nombre"])}</text>')
        for i, a in enumerate(c["atributos"]):
            partes.append(f'<text x="{x + 8}" y="{y + hn + 3 + (i + 0.75) * fila}" font-family="Consolas,Courier New,monospace" font-size="14"'
                          f'{SUBRAYADO if a.get("estatico") else ""}>{html.escape(linea_atributo(a))}</text>')
        for i, m in enumerate(c["metodos"]):
            partes.append(f'<text x="{x + 8}" y="{y + hn + ha + 3 + (i + 0.75) * fila}" font-family="Consolas,Courier New,monospace" font-size="14"'
                          f'{CURSIVA if m.get("abstracto") else ""}>{html.escape(linea_metodo(m))}</text>')
    for r in d.get("relaciones", []): partes.append(_svg_relacion(r, cajas))   # después de las cajas: los rótulos no quedan tapados
    if revision:
        for p in revision.get("puntos", []):
            r = norm.get(_norm(p["objetivo"]))
            if r and "." in p["objetivo"] or (r and not p["ok"]):
                col = COLORES["verde" if p["ok"] else "rojo"]
                partes.append(f'<rect x="{r[0] + 1}" y="{r[1] + 1}" width="{r[2] - 2}" height="{r[3] - 2}" fill="none" stroke="{col}" stroke-width="2.5" rx="3"/>'
                              f'<text x="{r[0] + r[2] - 18}" y="{r[1] + r[3] * 0.72}" font-size="15" fill="{col}">{"✔" if p["ok"] else "✘"}</text>')
    ancho_total = max([v[0] + v[2] for v in cajas.values()] + [n[0] + n[2] for n in d["_notas_svg"]]) + 40
    x_notas, y_libre = ancho_total + 10, 10
    for mk in marcas:
        col = COLORES.get(mk.get("color"), COLORES["rojo"]); t = html.escape(str(mk.get("texto", ""))[:80])
        if mk.get("tipo") == "flecha":
            a, b = norm.get(_norm(mk.get("desde", ""))), norm.get(_norm(mk.get("hasta", "")))
            if not (a and b): continue
            x1, y1, x2, y2 = a[0] + a[2] / 2, a[1] + a[3] / 2, b[0] + b[2] / 2, b[1] + b[3] / 2
            partes.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="3" marker-end="url(#punta-{mk.get("color", "rojo")})"/>')
            if t: partes.append(f'<text x="{(x1 + x2) / 2 + 6}" y="{(y1 + y2) / 2 - 6}" font-family="sans-serif" font-size="13" font-weight="bold" fill="{col}">{t}</text>')
        else:
            r = norm.get(_norm(mk.get("objetivo", "")))
            if not r: continue
            partes.append(f'<rect x="{r[0] - 3}" y="{r[1] - 3}" width="{r[2] + 6}" height="{r[3] + 6}" fill="none" stroke="{col}" stroke-width="3" rx="5"/>')
            if mk.get("tipo") == "nota" and t:
                ancho_nota = 9 + 7.6 * len(t)
                partes.append(f'<rect x="{x_notas}" y="{y_libre}" width="{ancho_nota}" height="26" fill="#fff" stroke="{col}" stroke-width="2" rx="6"/>'
                              f'<text x="{x_notas + 8}" y="{y_libre + 17}" font-family="sans-serif" font-size="13" font-weight="bold" fill="{col}">{t}</text>'
                              f'<line x1="{x_notas}" y1="{y_libre + 13}" x2="{r[0] + r[2] + 3}" y2="{r[1] + r[3] / 2}" stroke="{col}" stroke-width="2" marker-end="url(#punta-{mk.get("color", "rojo")})"/>')
                ancho_total = max(ancho_total, x_notas + ancho_nota + 10); y_libre += 36
    alto_total = max([v[1] + v[3] for v in cajas.values()] + [n[1] + n[3] for n in d["_notas_svg"]] + [y_libre]) + 30
    defs = "".join(f'<marker id="punta-{n}" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="{c}"/></marker>'
                   for n, c in COLORES.items()) + DEFS_UML
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho_total} {alto_total}" width="{ancho_total}" height="{alto_total}">'
            f'<defs>{defs}</defs>{"".join(partes)}</svg>')
