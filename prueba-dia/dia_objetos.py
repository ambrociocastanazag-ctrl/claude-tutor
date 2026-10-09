"""Cualquier objeto de Dia (no solo clases): catálogo de tipos, XML desde plantillas, lectura, texto y dibujo.

- catalogo_dia.json (lo genera plugin-dia/catalogo.py con un Dia aparte) trae los 868 tipos que tiene este
  Dia 0.97.2 con sus propiedades y el XML exacto de un objeto por defecto («plantilla»). Con eso se crean objetos
  de cualquier tipo sin tocar Dia: se toma la plantilla, se le ponen los textos y se traslada a su sitio.
- `completar(d, nodos)` lee lo que dia_uml.leer no entiende como clase: actores, casos de uso, líneas de vida,
  mensajes, acciones, decisiones, estados, transiciones, componentes, nodos, paquetes, objetos y cualquier otro
  objeto (Flowchart, ER, Network...) con sus conexiones.
- `texto_otros(d)` lo cuenta en palabras para el tutor; `cajas_otros(d)` da las cajas para las marcas;
  `svg_con_marcas` pone las marcas del tutor y la revisión encima del dibujo REAL de Dia (SVG exportado)."""
import copy, difflib, html, json, re
import xml.etree.ElementTree as ET
from pathlib import Path

import dia_uml as du

NSU = du.NS["dia"]
Q = "{" + NSU + "}"
ET.register_namespace("dia", NSU)
CATALOGO = Path(__file__).with_name("catalogo_dia.json")
_CAT = None


# ---------- Catálogo ----------
def catalogo():
    global _CAT
    if _CAT is None:
        try: _CAT = json.loads(CATALOGO.read_text(encoding="utf-8"))["tipos"]
        except (OSError, ValueError, KeyError): _CAT = {}
    return _CAT


def tipo_dia(nombre, donde="tipo"):
    """El nombre exacto de un tipo de Dia (acepta otra combinación de mayúsculas). ValueError con sugerencias."""
    cat = catalogo()
    if not cat: raise ValueError("no encuentro el catálogo de tipos de Dia (catalogo_dia.json)")
    n = re.sub(r"\s+", " ", str(nombre or "")).strip()
    if n in cat: return n
    bajo = {k.lower(): k for k in cat}
    if n.lower() in bajo: return bajo[n.lower()]
    cerca = difflib.get_close_matches(n, list(cat), 4, 0.55)
    raise ValueError(f"{donde}: el tipo «{n}» no existe en Dia" + (f" (¿quisiste decir {', '.join(f'«{c}»' for c in cerca)}?)" if cerca
                                                                 else " (usa el nombre exacto, como «Flowchart - Box» o «ER - Entity»)"))


def props_tipo(tipo): return {p["n"]: p for p in catalogo()[tipo]["props"]}


def es_conector(tipo):
    """¿El tipo es una línea que une dos objetos (tiene extremos)?"""
    x = catalogo().get(tipo, {}).get("xml", "")
    return tipo != "UML - Lifeline" and any(f'name="{a}"' in x for a in ("conn_endpoints", "orth_points", "poly_points"))


# ---------- Propiedades: alias en español y conversión de valores (para la orden «poner» del plugin) ----------
ALIAS = {"texto": "text", "relleno": "fill_colour", "fondo": "fill_colour", "color": "line_colour", "color_linea": "line_colour",
         "borde": "line_colour", "color_texto": "text_colour", "grosor": "line_width", "estilo": "line_style",
         "flecha_inicio": "start_arrow", "flecha_fin": "end_arrow", "flecha": "end_arrow", "radio": "corner_radius",
         "ver_fondo": "show_background", "estereotipo": "stereotype", "tamano_texto": "text_height", "tamaño_texto": "text_height",
         "fuente": "text_font", "alineacion": "text_alignment", "alineación": "text_alignment"}
COLORES = {"rojo": "#c02828", "verde": "#1e8c46", "amarillo": "#f2c500", "azul": "#1e5ac8", "negro": "#000000", "blanco": "#ffffff",
           "gris": "#888888", "gris_claro": "#e6e6e6", "naranja": "#f08c00", "morado": "#7d3cb4", "rosa": "#e678aa",
           "celeste": "#a0d2ff", "verde_claro": "#c8f0c8", "amarillo_claro": "#fff5b4", "rojo_claro": "#ffd2d2", "azul_claro": "#d2e1ff"}
FLECHAS = {"ninguna": 0, "no": 0, "abierta": 1, "flecha": 1, "lineas": 1, "triangulo_vacio": 2, "triangulo": 3, "llena": 3,
           "rombo_vacio": 4, "rombo": 5, "rombo_lleno": 5, "media": 6, "circulo": 8, "circulo_vacio": 9,
           "pata_de_gallo": 20, "uno_o_muchos": 28, "cero_o_muchos": 29, "cero_o_uno": 30, "uno": 31}
ESTILOS = {"continua": 0, "solida": 0, "sólida": 0, "discontinua": 1, "guiones": 1, "raya_punto": 2, "raya_punto_punto": 3,
           "punteada": 4, "puntos": 4}
FUERA = {"obj_pos", "obj_bb", "meta", "conn_endpoints", "orth_points", "orth_orient", "orth_autoroute", "poly_points",
         "bez_points", "corner_types", "elem_corner", "numcp", "attributes", "operations", "templates"}
PROP_TIPOS_OK = {"string", "multistring", "text", "real", "length", "fontsize", "int", "enum", "bool", "colour", "arrow", "linestyle", "font"}


def texto_principal(tipo):
    """El nombre de la propiedad que es «el texto» del objeto (text, name...), o None."""
    ps = props_tipo(tipo)
    for n in ("text", "name"):
        if n in ps and ps[n]["t"] in ("text", "string"): return n
    return None


def valor_prop(tipo, nombre, valor, donde):
    """(nombre real, valor como texto para «poner») o ValueError claro. Nada de rutas ni archivos."""
    ps = props_tipo(tipo)
    real = ALIAS.get(str(nombre).lower(), nombre)
    if real == "text" and "text" not in ps: real = texto_principal(tipo) or real
    if real in ("ancho", "width"): real = "elem_width"
    if real in ("alto", "height"): real = "elem_height"
    p = ps.get(real)
    visibles = sorted(n for n, q in ps.items() if q["t"] in PROP_TIPOS_OK and n not in FUERA and q["f"] & 1)
    if not p or real in FUERA:
        raise ValueError(f"{donde}: «{tipo}» no tiene la propiedad «{nombre}» (tiene: {', '.join(visibles[:18])})")
    t = p["t"]
    if t == "file" or "file" in real or "image" in real: raise ValueError(f"{donde}: no se pueden usar archivos ni rutas («{nombre}»)")
    if t not in PROP_TIPOS_OK: raise ValueError(f"{donde}: la propiedad «{nombre}» ({t}) no se puede cambiar desde aquí")
    v = valor
    if t in ("string", "multistring", "text"):
        if not isinstance(v, (str, int, float)): raise ValueError(f"{donde}: «{nombre}» es un texto")
        v = str(v).replace("\\", "/")
        if len(v) > 300: raise ValueError(f"{donde}: «{nombre}» es demasiado largo")
        return real, v.replace("\n", "\\n")
    if t in ("real", "length", "fontsize"):
        try: f = float(v)
        except (TypeError, ValueError): raise ValueError(f"{donde}: «{nombre}» es un número (en cm)")
        if not -500 <= f <= 500: raise ValueError(f"{donde}: «{nombre}» fuera de rango")
        if t in ("length", "fontsize") and f < 0: raise ValueError(f"{donde}: «{nombre}» no puede ser negativo")
        return real, repr(round(f, 4))
    if t == "int":
        try: return real, str(int(v))
        except (TypeError, ValueError): raise ValueError(f"{donde}: «{nombre}» es un número entero")
    if t == "bool":
        if isinstance(v, str): v = {"si": True, "sí": True, "true": True, "no": False, "false": False}.get(v.lower(), v)
        if not isinstance(v, bool): raise ValueError(f"{donde}: «{nombre}» es true o false")
        return real, "true" if v else "false"
    if t == "colour":
        nombre = str(v).lower().strip().replace(" ", "_").replace("-", "_")
        s = COLORES.get(nombre, str(v))
        if nombre not in COLORES and nombre.endswith(("_claro", "_clara")) and nombre[:-6] in COLORES:     # cualquier color «claro»: el mismo, aclarado
            base = COLORES[nombre[:-6]]
            s = "#" + "".join(f"{int(int(base[i:i + 2], 16) * 0.25 + 255 * 0.75):02x}" for i in (1, 3, 5))
        if not re.match(r"^#[0-9a-fA-F]{6}$", s): raise ValueError(f"{donde}: «{nombre}» es un color #rrggbb o {', '.join(list(COLORES)[:9])}…")
        return real, s.lower()
    if t == "enum":
        ops = p.get("e") or {}
        if isinstance(v, (int, float)) and not isinstance(v, bool) and (int(v) in ops.values() or not ops): return real, str(int(v))
        for k, n in ops.items():
            if str(v).lower() == k.lower(): return real, str(n)
        raise ValueError(f"{donde}: «{nombre}» es una de: {', '.join(ops) or 'un número'}")
    if t == "arrow":
        n = FLECHAS.get(str(v).lower().replace(" ", "_"), v)
        if not (isinstance(n, int) and 0 <= n <= 33): raise ValueError(f"{donde}: «{nombre}» es una flecha: {', '.join(FLECHAS)} (o un número 0–33)")
        return real, str(n)
    if t == "linestyle":
        n = ESTILOS.get(str(v).lower().replace(" ", "_"), v)
        if not (isinstance(n, int) and 0 <= n <= 4): raise ValueError(f"{donde}: «{nombre}» es: continua, discontinua, raya_punto o punteada")
        return real, str(n)
    if t == "font":
        s = str(v).lower().strip()
        if not re.match(r"^(sans|serif|monospace)(,(negrita|cursiva))*$", s): raise ValueError(f"{donde}: «{nombre}» es sans, serif o monospace (con «,negrita» o «,cursiva»)")
        return real, s
    raise ValueError(f"{donde}: «{nombre}» no se puede cambiar")


def comando_poner(ref, pares):
    """Orden «poner» del plugin: `poner "REF" "prop=valor" ...` (los valores ya vienen de valor_prop)."""
    q = lambda s: '"' + str(s).replace('"', "'") + '"'
    return "poner " + q(ref) + " " + " ".join(q(f"{n}={v}") for n, v in pares)


# ---------- XML desde la plantilla de Dia ----------
def _parse(xml):
    return ET.fromstring(f'<dia:r xmlns:dia="{NSU}">{xml}</dia:r>')[0]


def _attr(o, nombre, crear=True):
    a = o.find(f"dia:attribute[@name='{nombre}']", du.NS)
    if a is None and crear:
        a = ET.SubElement(o, Q + "attribute", {"name": nombre})
        con = o.find("dia:connections", du.NS)            # que <connections> quede al final
        if con is not None: o.remove(con); o.append(con)
    return a


def poner_xml(o, nombre, clase, valor):
    """Escribe una propiedad en el XML del objeto. clase: string, text, bool, real, int, enum, color, point."""
    a = _attr(o, nombre)
    if clase == "text":
        comp = a.find("dia:composite", du.NS)
        if comp is None:
            for h in list(a): a.remove(h)
            comp = ET.SubElement(a, Q + "composite", {"type": "text"})
        s = _attr(comp, "string")
        for h in list(s): s.remove(h)
        ET.SubElement(s, Q + "string").text = "#" + str(valor) + "#"
        return
    for h in list(a): a.remove(h)
    if clase == "string": ET.SubElement(a, Q + "string").text = "#" + str(valor) + "#"
    elif clase == "bool": ET.SubElement(a, Q + "boolean", {"val": "true" if valor else "false"})
    elif clase == "point": ET.SubElement(a, Q + "point", {"val": f"{valor[0]:.4f},{valor[1]:.4f}"})
    elif clase == "points":
        for x, y in valor: ET.SubElement(a, Q + "point", {"val": f"{x:.4f},{y:.4f}"})
    elif clase == "enums":
        for v in valor: ET.SubElement(a, Q + "enum", {"val": str(v)})
    elif clase == "color": ET.SubElement(a, Q + "color", {"val": valor})
    else: ET.SubElement(a, Q + {"real": "real", "int": "int", "enum": "enum"}[clase], {"val": str(valor)})


def leer_xml(o, nombre):
    """Valor sencillo de un atributo del XML (texto, número, booleano o punto)."""
    a = o.find(f"dia:attribute[@name='{nombre}']", du.NS)
    if a is None or not len(a): return None
    h = a[0]; t = h.tag[len(Q):]
    if t == "string": return du._cadena(o, nombre)
    if t == "composite":
        s = h.find("dia:attribute[@name='string']/dia:string", du.NS)
        x = (s.text or "") if s is not None else ""
        return x[1:-1] if x.startswith("#") and x.endswith("#") else x
    if t == "boolean": return h.get("val") == "true"
    if t in ("real", "int", "enum"): return float(h.get("val"))
    if t == "point": return tuple(map(float, h.get("val").split(",")))
    return None


def caja_xml(o):
    """Caja exterior (bounding box) guardada: (x, y, w, h)."""
    r = o.find("dia:attribute[@name='obj_bb']/dia:rectangle", du.NS)
    if r is None: return (0.0, 0.0, 1.0, 1.0)
    (x1, y1), (x2, y2) = [tuple(map(float, p.split(","))) for p in r.get("val").split(";")]
    return (x1, y1, x2 - x1, y2 - y1)


def trasladar(o, dx, dy):
    """Mueve todos los puntos y rectángulos del objeto (posición, esquina, textos...)."""
    for p in o.iter(Q + "point"):
        x, y = map(float, p.get("val").split(",")); p.set("val", f"{x + dx:.4f},{y + dy:.4f}")
    for r in o.iter(Q + "rectangle"):
        (x1, y1), (x2, y2) = [tuple(map(float, q.split(","))) for q in r.get("val").split(";")]
        r.set("val", f"{x1 + dx:.4f},{y1 + dy:.4f};{x2 + dx:.4f},{y2 + dy:.4f}")


def poner_meta(o, meta):
    meta = {k: v for k, v in (meta or {}).items() if v not in (None, "")}
    a = _attr(o, "meta")
    for h in list(a): a.remove(h)
    comp = ET.SubElement(a, Q + "composite", {"type": "dict"})
    for k, v in meta.items():
        ET.SubElement(ET.SubElement(comp, Q + "attribute", {"name": k}), Q + "string").text = "#" + str(v) + "#"


def nuevo(tipo):
    """Un objeto nuevo (Element de ElementTree) desde la plantilla del tipo."""
    return _parse(catalogo()[tipo]["xml"])


def a_texto(o, oid):
    o.set("id", oid)
    if o.find("dia:connections", du.NS) is None and es_conector(o.get("type")): ET.SubElement(o, Q + "connections")
    s = ET.tostring(o, encoding="unicode").replace(f' xmlns:dia="{NSU}"', "")
    return s + "\n"


def ruta_ortogonal(p0, p1):
    """Cuatro puntos de una línea en ángulo recto de p0 a p1 y sus orientaciones (como _relacion_xml)."""
    (x0, y0), (x1, y1) = p0, p1
    if abs(y1 - y0) >= abs(x1 - x0):
        ym = (y0 + y1) / 2; return [(x0, y0), (x0, ym), (x1, ym), (x1, y1)], (1, 0, 1)
    xm = (x0 + x1) / 2; return [(x0, y0), (xm, y0), (xm, y1), (x1, y1)], (0, 1, 0)


def poner_extremos(o, p0, p1, ruta=None):
    """Coloca una línea (conn_endpoints, orth_points o poly_points) de p0 a p1 y mueve sus textos al medio.
    Con `ruta` = (puntos, orientaciones), una línea ortogonal lleva esos tramos y sin autorruta."""
    bb = caja_xml(o)
    cx, cy = bb[0] + bb[2] / 2, bb[1] + bb[3] / 2
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    trasladar(o, mx - cx, my - cy)                         # los textos de la plantilla quedan cerca del medio
    if o.find("dia:attribute[@name='orth_points']", du.NS) is not None:
        pts, ori = ruta if ruta and len(ruta[0]) >= 3 else ruta_ortogonal(p0, p1)   # una línea ortogonal de 2 puntos cierra Dia
        poner_xml(o, "orth_points", "points", pts); poner_xml(o, "orth_orient", "enums", ori)
        auto = ruta is None
        if o.find("dia:attribute[@name='orth_autoroute']", du.NS) is not None or "orth_autoroute" in props_tipo(o.get("type")):
            poner_xml(o, "orth_autoroute", "bool", auto)
        if o.find("dia:attribute[@name='autorouting']", du.NS) is not None: poner_xml(o, "autorouting", "bool", auto)
    elif o.find("dia:attribute[@name='poly_points']", du.NS) is not None:
        poner_xml(o, "poly_points", "points", [p0, p1])
    else:
        poner_xml(o, "conn_endpoints", "points", [p0, p1])
    poner_xml(o, "obj_pos", "point", p0)


# ---------- Leer lo que no son clases ----------
KIND_DE_TIPO = {"UML - Actor": "actor", "UML - Usecase": "caso", "UML - Activity": "accion", "UML - Branch": "decision",
                "UML - Fork": "bifurcacion", "UML - State": "estado", "UML - Component": "componente", "UML - Node": "nodo",
                "UML - LargePackage": "paquete", "UML - SmallPackage": "paquete", "UML - Object": "objeto",
                "UML - Lifeline": "linea_vida", "UML - Message": "mensaje", "UML - Transition": "flujo",
                "UML - Component Feature": "interfaz", "UML - Constraint": "restriccion", "UML - Classicon": "clase_icono",
                "UML - Implements": "implementa"}
NOMBRES = {  # kind → (singular, plural) para textos y resúmenes
    "actor": ("actor", "actores"), "caso": ("caso de uso", "casos de uso"), "sistema": ("límite del sistema", "límites del sistema"),
    "participante": ("participante", "participantes"), "linea_vida": ("línea de vida", "líneas de vida"),
    "mensaje": ("mensaje", "mensajes"), "inicial": ("nodo inicial", "nodos iniciales"), "final": ("nodo final", "nodos finales"),
    "accion": ("acción", "acciones"), "decision": ("decisión", "decisiones"), "fusion": ("fusión", "fusiones"),
    "bifurcacion": ("bifurcación", "bifurcaciones"), "union": ("unión", "uniones"), "estado": ("estado", "estados"),
    "compuesto": ("estado compuesto", "estados compuestos"), "calle": ("calle", "calles"),
    "flujo": ("flujo", "flujos"), "transicion": ("transición", "transiciones"), "componente": ("componente", "componentes"),
    "interfaz": ("interfaz", "interfaces"), "nodo": ("nodo", "nodos"), "paquete": ("paquete", "paquetes"),
    "objeto": ("objeto", "objetos"), "artefacto": ("artefacto", "artefactos"), "texto": ("texto", "textos"),
    "libre": ("objeto", "objetos"), "linea": ("línea", "líneas"), "rotulo": ("rótulo", "rótulos")}


def _texto_de(o):
    for n in ("name", "text"):
        v = leer_xml(o, n)
        if isinstance(v, str) and v.strip(): return v.strip()
    return ""


def completar(d, nodos):
    """Añade a d (de dia_uml.leer) los objetos que no son clases ni notas: d["objetos"] (cajas) y d["lineas"]
    (conectores que no son relaciones de clase), y pone nombre a los extremos de las relaciones UML."""
    objetos, lineas, por_id = [], [], {}
    for o in nodos:
        t = o.get("type")
        con = {int(c.get("handle")): (c.get("to"), c.get("connection")) for c in o.findall("dia:connections/dia:connection", du.NS)}
        x = {"id": o.get("id"), "tipo": t, "kind": KIND_DE_TIPO.get(t, ""), "texto": _texto_de(o), "nombre": du._meta(o, "nombre"),
             "tag": du._meta(o, "tutor"), "rol": du._meta(o, "rol"), "caja": caja_xml(o), "con": con, "extra": {},
             "xml": re.sub(r"<dia:connections>.*?</dia:connections>", "", ET.tostring(o, encoding="unicode"), flags=re.S).replace(f' xmlns:dia="{NSU}"', "")}
        if t == "UML - State Term":
            x["kind"] = "final" if leer_xml(o, "is_final") else "inicial"
        elif t == "UML - State":
            x["extra"] = {k: leer_xml(o, a) or "" for k, a in (("entrada", "entry_action"), ("hacer", "do_action"), ("salida", "exit_action"))}
        elif t == "UML - Object":
            x["extra"] = {"valores": [l for l in (leer_xml(o, "attrib") or "").split("\n") if l.strip()], "estereotipo": leer_xml(o, "stereotype") or ""}
        elif t in ("UML - Component", "UML - LargePackage", "UML - SmallPackage", "UML - Node"):
            x["extra"] = {"estereotipo": leer_xml(o, "stereotype") or ""}
        elif t == "UML - Message":
            x["extra"] = {"mtipo": int(leer_xml(o, "type") or 0)}
        elif t == "UML - Transition":
            x["extra"] = {k: (leer_xml(o, a) or "").strip() for k, a in (("evento", "trigger"), ("guarda", "guard"), ("efecto", "action"))}
            x["texto"] = ""
        elif t == "UML - Component Feature":
            x["extra"] = {"rol": int(leer_xml(o, "role") or 0)}
        elif t == "UML - Lifeline":
            x["extra"] = {"cruz": bool(leer_xml(o, "draw_cross"))}
            x["rtop"], x["rbot"] = leer_xml(o, "rtop") or 0.5, leer_xml(o, "rbot") or 2.5
        if t in ("Standard - Box",) and x["rol"] in ("sistema", "calle", "compuesto"): x["kind"] = x["rol"]
        if t == "Standard - Text" and x["rol"]: x["kind"] = "rotulo"
        es_linea = t != "UML - Lifeline" and (es_conector(t) or any(o.find(f"dia:attribute[@name='{n}']", du.NS) is not None
                                                                   for n in ("conn_endpoints", "orth_points", "poly_points", "bez_points")))
        if es_linea:
            pts = [tuple(map(float, p.get("val").split(","))) for nombre in ("conn_endpoints", "orth_points", "poly_points")
                   for p in o.findall(f"dia:attribute[@name='{nombre}']/dia:point", du.NS)]
            x["puntos"] = pts
            if not x["kind"]: x["kind"] = "linea"
            lineas.append(x)
        else:
            if t == "UML - Lifeline":
                pts = [tuple(map(float, p.get("val").split(","))) for p in o.findall("dia:attribute[@name='conn_endpoints']/dia:point", du.NS)]
                x["puntos"] = pts
            objetos.append(x)
        por_id[x["id"]] = x
    # Límites del sistema dibujados a mano: una caja que contiene casos de uso; su título es el texto de arriba
    def dentro(c, caja):
        cx, cy = c[0] + c[2] / 2, c[1] + c[3] / 2
        return caja[0] <= cx <= caja[0] + caja[2] and caja[1] <= cy <= caja[1] + caja[3]
    textos = [o for o in objetos if o["tipo"] == "Standard - Text"]
    for b in objetos:
        if b["tipo"] != "Standard - Box": continue
        if b["kind"] == "" and any(o["kind"] == "caso" and dentro(o["caja"], b["caja"]) for o in objetos): b["kind"] = "sistema"
        if b["kind"] in ("sistema", "calle", "compuesto"):
            arriba = [t for t in textos if dentro(t["caja"], b["caja"]) and t["caja"][1] - b["caja"][1] < 2.2]
            if arriba:
                tit = min(arriba, key=lambda t: t["caja"][1])
                tit["kind"] = "rotulo"; tit["de"] = b["id"]; b["titulo_id"] = tit["id"]
                if not b["nombre"]: b["nombre"] = tit["texto"]
            b["texto"] = b["texto"] or b["nombre"]
    # Participantes de secuencia: un objeto (o actor) con una línea de vida debajo; segmentos encadenados
    vida_de = {}
    for v in [o for o in objetos if o["tipo"] == "UML - Lifeline"]:
        arriba = v["con"].get(0, (None, None))[0]
        cadena, k = v, 0
        while arriba in por_id and por_id[arriba]["tipo"] == "UML - Lifeline" and k < 20:
            cadena = por_id[arriba]; arriba = cadena["con"].get(0, (None, None))[0]; k += 1
        if arriba in por_id:
            cabeza = por_id[arriba]
            if cabeza["tipo"] == "UML - Object": cabeza["kind"] = "participante"
            cabeza.setdefault("vidas", []).append(v["id"])
            v["de"] = cabeza["id"]; vida_de[v["id"]] = cabeza
    # Decisión o fusión, bifurcación o unión (por cuántas líneas entran y salen)
    entra, sale = {}, {}
    for l in lineas:
        a, b = l["con"].get(0, (None,))[0], l["con"].get(1, (None,))[0]
        if a: sale[a] = sale.get(a, 0) + 1
        if b: entra[b] = entra.get(b, 0) + 1
    for o in objetos:
        if o["kind"] == "decision" and entra.get(o["id"], 0) >= 2 and sale.get(o["id"], 0) <= 1: o["kind"] = "fusion"
        if o["kind"] == "bifurcacion" and entra.get(o["id"], 0) >= 2 and sale.get(o["id"], 0) <= 1: o["kind"] = "union"
    # Nombres de los extremos
    def nombre_obj(oid):
        x = por_id.get(oid)
        if x is None: return None
        if x["tipo"] == "UML - Lifeline": return nombre_obj(x.get("de")) if x.get("de") else None
        return x["texto"] or x["nombre"] or f"#{x['id']}"
    for l in lineas:
        a, b = l["con"].get(0, (None,))[0], l["con"].get(1, (None,))[0]
        if l["tipo"] == "UML - Message" and l["extra"].get("mtipo") == 4: a, b = b, a     # el retorno tiene la punta en el extremo 0
        if l["tipo"] == "UML - Message" and l["extra"].get("mtipo") == 6: b = a             # a sí mismo: el otro extremo queda libre
        l["de_id"], l["a_id"] = a, b
        l["de"], l["a"] = nombre_obj(a), nombre_obj(b)
        if l["tipo"] == "UML - Message": l["y"] = sum(p[1] for p in l.get("puntos") or [(0, 0)]) / max(1, len(l.get("puntos") or [1]))
    d["objetos"], d["lineas"] = objetos, lineas
    d["_por_id"] = por_id
    nombres = {c["id"]: c["nombre"] for c in d["clases"]}
    for r in d.get("relaciones", []):
        if r.get("de") is None: r["de"] = nombres.get(r.get("de_id")) or nombre_obj(r.get("de_id"))
        if r.get("a") is None: r["a"] = nombres.get(r.get("a_id")) or nombre_obj(r.get("a_id"))
    return d


def nombre_de_objeto(o):
    return o.get("texto") or o.get("nombre") or f"#{o['id']}"


def mensajes_en_orden(d):
    return sorted([l for l in d.get("lineas", []) if l["tipo"] == "UML - Message"], key=lambda l: l.get("y", 0))


TIPO_MENSAJE = {0: "síncrono", 1: "crear «create»", 2: "destruir «destroy»", 3: "asíncrono", 4: "retorno", 5: "asíncrono (media flecha)", 6: "a sí mismo"}


def texto_otros(d):
    """Las líneas del [Estado actual] para lo que no son clases (todo tipo de diagrama)."""
    L, objs, lineas = [], d.get("objetos", []), d.get("lineas", [])
    tutor = lambda o: " [lo creaste tú, el tutor]" if o.get("tag") else ""
    ref = lambda o: f" (#{o['id']})" if not o.get("texto") else ""
    por_id = d.get("_por_id", {})
    def contiene(c):
        return [nombre_de_objeto(o) for o in objs if o is not c and o["kind"] not in ("rotulo", "linea_vida")
                and c["caja"][0] <= o["caja"][0] + o["caja"][2] / 2 <= c["caja"][0] + c["caja"][2]
                and c["caja"][1] <= o["caja"][1] + o["caja"][3] / 2 <= c["caja"][1] + c["caja"][3]]
    for o in objs:
        k = o["kind"]
        if k in ("rotulo", "linea_vida"): continue
        n = nombre_de_objeto(o)
        if k == "actor": L.append(f"Actor «{n}»" + (" (participante, con línea de vida)" if o.get("vidas") else "") + tutor(o))
        elif k == "caso": L.append(f"Caso de uso «{n}»{tutor(o)}")
        elif k == "sistema": L.append(f"Límite del sistema «{n}» (dentro: {', '.join(f'«{x}»' for x in contiene(o)) or 'nada'}){tutor(o)}")
        elif k == "participante": L.append(f"Participante «{n}» (con línea de vida){tutor(o)}")
        elif k in ("inicial", "final"): L.append(f"{NOMBRES[k][0].capitalize()}{' «' + o['nombre'] + '»' if o['nombre'] else ''} (#{o['id']}){tutor(o)}")
        elif k == "accion": L.append(f"Acción «{n}»{tutor(o)}")
        elif k in ("decision", "fusion", "bifurcacion", "union"):
            L.append(f"{NOMBRES[k][0].capitalize()}{' «' + o['nombre'] + '»' if o['nombre'] else ''} (#{o['id']}){tutor(o)}")
        elif k == "estado":
            acc = ", ".join(f"{a}: {v}" for a, v in o["extra"].items() if v)
            L.append(f"Estado «{n}»" + (f" ({acc})" if acc else "") + tutor(o))
        elif k == "compuesto": L.append(f"Estado compuesto «{n}» (dentro: {', '.join(f'«{x}»' for x in contiene(o)) or 'nada'}){tutor(o)}")
        elif k == "calle": L.append(f"Calle «{n}»{tutor(o)}")
        elif k == "componente": L.append(f"Componente «{n}»" + (f" «{o['extra']['estereotipo']}»" if o["extra"].get("estereotipo") else "") + tutor(o))
        elif k in ("nodo", "paquete"):
            dentro = contiene(o)
            L.append(f"{NOMBRES[k][0].capitalize()} «{n}»" + (f" «{o['extra']['estereotipo']}»" if o["extra"].get("estereotipo") else "")
                     + (f" (dentro: {', '.join(f'«{x}»' for x in dentro)})" if dentro else "") + tutor(o))
        elif k == "objeto":
            v = o["extra"].get("valores") or []
            L.append(f"Objeto «{n}»" + (f" ({'; '.join(v)})" if v else "") + tutor(o))
        elif o["tipo"] == "Standard - Text": L.append(f"Texto «{n}»{tutor(o)}")
        else: L.append(f"{o['tipo']} «{n}»{ref(o)}{tutor(o)}" if o.get("texto") else f"{o['tipo']} (#{o['id']}){tutor(o)}")
    msgs = mensajes_en_orden(d)
    if msgs:
        L.append("Mensajes (de arriba abajo):")
        for i, m in enumerate(msgs, 1):
            L.append(f"  {i}. {m['de'] or '(suelto)'} → {m['a'] or '(suelto)'}: {m['texto'] or ''} ({TIPO_MENSAJE.get(m['extra'].get('mtipo'), '?')}){tutor(m)}")
    for l in lineas:
        if l["tipo"] == "UML - Message": continue
        de, a = l["de"] or "(suelto)", l["a"] or "(suelto)"
        if l["tipo"] == "UML - Transition":
            e = l["extra"]; et = (e.get("evento") or "") + (f" [{e['guarda']}]" if e.get("guarda") else "") + (f" / {e['efecto']}" if e.get("efecto") else "")
            L.append(f"Flujo/transición: {de} → {a}" + (f": {et.strip()}" if et.strip() else "") + tutor(l))
        elif l["tipo"] == "UML - Component Feature":
            L.append(f"Interfaz {'ofrecida' if l['extra'].get('rol') == 0 else 'requerida'} «{l['texto']}» de «{de}»{tutor(l)}")
        else:
            L.append(f"{l['tipo']}{' «' + l['texto'] + '»' if l['texto'] else ''}: {de} → {a} (#{l['id']}){tutor(l)}")
    return L


def cajas_otros(d):
    """Cajas en cm de los objetos que no son clases, por su texto y por «#id» (para las marcas)."""
    cajas = {}
    for o in d.get("objetos", []) + d.get("lineas", []):
        if o.get("kind") == "linea_vida": continue
        c = tuple(o["caja"])
        cajas.setdefault(f"#{o['id']}", c)
        for n in (o.get("texto"), o.get("nombre")):
            if n: cajas.setdefault(n.replace("\n", " "), c)
    return cajas


def cajas_de_plugin_objetos(respuesta):
    """Las líneas «objeto» de la orden «cajas» (versión 4): {"#O7": caja, "texto": caja}."""
    cajas = {}
    for linea in respuesta.splitlines():
        p = linea.split("\t")
        if p[0] == "objeto" and len(p) >= 7:
            try: c = tuple(float(v) for v in p[3:7])
            except ValueError: continue
            cajas.setdefault("#" + p[1], c)
            if len(p) > 7 and p[7].strip(): cajas.setdefault(p[7].strip(), c)
    return cajas


# ---------- Dibujo del panel: el SVG REAL de Dia con las marcas encima ----------
ESCALA_SVG = 20.0          # el exportador SVG de Dia usa 20 unidades por cm


def svg_con_marcas(svg_dia, cajas, marcas=(), revision=None):
    """Junta el SVG que exporta Dia (filtro SVG: lo que se ve en Dia, cualquier tipo de diagrama) con las marcas del
    tutor (marco, nota, flecha) y los ✔/✘ de la revisión, en las mismas coordenadas (cm × 20). `cajas` son las de
    las marcas (dia_uml.cajas_cm / cajas_de_plugin: "Clase", "Clase.miembro", "texto de un objeto", "#O7")."""
    m = re.search(r"<svg\b[^>]*>", svg_dia)
    if not m: return ""
    cab = m.group(0)
    vb = re.search(r'viewBox="([^"]+)"', cab)
    x0, y0, w0, h0 = map(float, vb.group(1).split()) if vb else (0, 0, 800, 600)
    cuerpo = svg_dia[m.end():svg_dia.rfind("</svg>")]
    cuerpo = re.sub(r"<!DOCTYPE[^>]*>|<\?xml[^>]*\?>", "", cuerpo)
    S = ESCALA_SVG
    norm = {du._norm(k): v for k, v in cajas.items()}
    fs = max(13.0, w0 / 34)                     # rótulos legibles aunque el panel encoja el dibujo
    partes, x1, y1 = [], x0 + w0, y0 + h0
    color = lambda n: du.COLORES.get(n, du.COLORES["rojo"])
    if revision:
        for p in revision.get("puntos", []):
            r = norm.get(du._norm(p.get("objetivo", "")))
            if not r or (p["ok"] and "." not in p.get("objetivo", "")): continue
            c = color("verde" if p["ok"] else "rojo")
            X, Y, W, H = r[0] * S, r[1] * S, r[2] * S, r[3] * S
            partes.append(f'<rect x="{X:.1f}" y="{Y:.1f}" width="{W:.1f}" height="{H:.1f}" fill="none" stroke="{c}" stroke-width="3" rx="3"/>'
                          f'<text x="{X + W - fs:.1f}" y="{Y + H * 0.75:.1f}" font-size="{fs:.0f}" fill="{c}">{"✔" if p["ok"] else "✘"}</text>')
    yl = y0 + 6
    for mk in marcas or []:
        c = color(mk.get("color")); t = html.escape(str(mk.get("texto", ""))[:80])
        if mk.get("tipo") == "flecha":
            a, b = norm.get(du._norm(mk.get("desde", ""))), norm.get(du._norm(mk.get("hasta", "")))
            if not (a and b): continue
            ax, ay, bx, by = (a[0] + a[2] / 2) * S, (a[1] + a[3] / 2) * S, (b[0] + b[2] / 2) * S, (b[1] + b[3] / 2) * S
            partes.append(f'<line x1="{ax:.1f}" y1="{ay:.1f}" x2="{bx:.1f}" y2="{by:.1f}" stroke="{c}" stroke-width="4" marker-end="url(#mk-{mk.get("color", "rojo")})"/>')
            if t: partes.append(f'<text x="{(ax + bx) / 2 + 8:.1f}" y="{(ay + by) / 2 - 8:.1f}" font-family="sans-serif" font-size="{fs:.0f}" font-weight="bold" fill="{c}">{t}</text>')
            continue
        r = norm.get(du._norm(mk.get("objetivo", "")))
        if not r: continue
        X, Y, W, H = r[0] * S, r[1] * S, r[2] * S, r[3] * S
        partes.append(f'<rect x="{X - 4:.1f}" y="{Y - 4:.1f}" width="{W + 8:.1f}" height="{H + 8:.1f}" fill="none" stroke="{c}" stroke-width="4" rx="6"/>')
        if mk.get("tipo") == "nota" and t:
            ancho = fs * 0.62 * len(t) + 16
            nx = x0 + w0 + 30
            partes.append(f'<rect x="{nx:.1f}" y="{yl:.1f}" width="{ancho:.1f}" height="{fs * 1.9:.1f}" fill="#fff" stroke="{c}" stroke-width="2.5" rx="7"/>'
                          f'<text x="{nx + 8:.1f}" y="{yl + fs * 1.3:.1f}" font-family="sans-serif" font-size="{fs:.0f}" font-weight="bold" fill="{c}">{t}</text>'
                          f'<line x1="{nx:.1f}" y1="{yl + fs:.1f}" x2="{X + W + 4:.1f}" y2="{Y + H / 2:.1f}" stroke="{c}" stroke-width="2.5" marker-end="url(#mk-{mk.get("color", "rojo")})"/>')
            x1 = max(x1, nx + ancho + 10); yl += fs * 2.4
    y1 = max(y1, yl)
    defs = "".join(f'<marker id="mk-{n}" markerWidth="10" markerHeight="8" refX="9" refY="4" orient="auto"><path d="M0,0 L10,4 L0,8 z" fill="{c}"/></marker>'
                   for n, c in du.COLORES.items())
    W, H = x1 - x0 + 4, y1 - y0 + 4
    return (f'<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" viewBox="{x0 - 2:.1f} {y0 - 2:.1f} {W:.1f} {H:.1f}" '
            f'width="{W:.0f}" height="{H:.0f}"><defs>{defs}</defs><rect x="{x0 - 2:.1f}" y="{y0 - 2:.1f}" width="{W:.1f}" height="{H:.1f}" fill="#fff"/>'
            f'{cuerpo}{"".join(partes)}</svg>')


def quitar_capa_tutor(texto_dia):
    """El XML de un .dia sin la capa «Tutor» (para exportarlo con dia.exe sin las marcas)."""
    return re.sub(r'<dia:layer name="Tutor"[^>]*>.*?</dia:layer>|<dia:layer name="Tutor"[^>]*/>', "", texto_dia, flags=re.S)
