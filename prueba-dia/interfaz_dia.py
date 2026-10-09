"""La interfaz real de Dia para la clase en vivo: dónde está cada cosa en pantalla («widgets» del plugin) y «hazlo por mí».

- `leer_widgets(texto)`: la respuesta de la orden «widgets» → ventanas (con su HWND y su rol) y sus widgets.
- `resolver(objetivos, widgets, pantalla)`: lo que un paso quiere señalar → marcas para overlay_dia.py
  (HWND de la ventana, su área de cliente y el rectángulo señalado, en coordenadas de GTK) y lo que no se ve ahora.
- `validar_interfaz` / `validar_hazlo`: revisan sin Dia lo que trae el JSON de la lección.
- `ordenes_hazlo(hacer, pestana)`: «Hazlo por mí» → órdenes del plugin (seleccionar, accion, pulsar, hoja).

Vocabulario de «interfaz» (una clave por objetivo, más "texto" y "color" opcionales):
  {"herramienta": "UML - Class"}  (el botón de la caja que crea ese tipo; "tip" lo distingue si hay dos, p. ej. "Clase")
  {"hoja": "UML"}  (el menú de hojas de la caja) · {"menu": "Objetos"} · {"pestana": "Atributos"} · {"boton": "Nuevo"}
  {"campo": "Nombre"} (la caja de texto junto a esa etiqueta) · {"objeto": "Libro"} (un objeto del diagrama de la lección)
Si la herramienta no está a la vista (otra hoja), se señala el menú de hojas con «Elige la hoja «UML»».

Vocabulario de «hazlo» (en orden; siempre sobre el diagrama de la lección, salvo en el «Tu turno», con permiso):
  {"hoja": "UML"} · {"herramienta": "UML - Class"} (la elige en la caja) · {"seleccionar": "Libro"} ·
  {"propiedades": "Libro"} (la selecciona y abre su diálogo Propiedades) · {"pulsar": "Atributos"} (pestaña o botón por su texto) ·
  {"accion": "ViewShowall"} (solo las de ACCIONES_OK) · {"esperar": 0.5}"""
import re

_LINEA = re.compile(r'^(widget|pestana|ventana) ?(\S*) x=(-?\d+) y=(-?\d+) w=(\d+) h=(\d+)(.*)$')
_CLAVE = re.compile(r'(\w+)="([^"]*)"')
CLAVES_INTERFAZ = ("herramienta", "hoja", "menu", "pestana", "boton", "campo", "objeto")
ACCIONES_OK = {"ObjectsProperties", "ViewShowall", "ViewZoomin", "ViewZoomout", "EditDeselect", "SelectAll", "SelectNone",
               "LayersAdd", "DiagramProperties"}        # «hazlo por mí» no guarda, no cierra ni borra nada
COLORES = ("rojo", "verde", "amarillo", "azul", "naranja")
ENTRADAS = ("GtkEntry", "GtkComboBoxEntry", "GtkComboBox", "GtkOptionMenu", "GtkTextView", "GtkSpinButton", "DiaFontSelector",
            "DiaColorSelector", "GtkCheckButton", "DiaSizeSelector", "DiaArrowSelector", "DiaLineStyleSelector")


def leer_widgets(texto):
    """[{"x", "y", "w", "h", "titulo", "hwnd", "rol", "widgets": [{"tipo": widget|pestana, "clase", "x", ... "texto", "tip"}]}]"""
    ventanas, actual = [], None
    for linea in (texto or "").splitlines():
        m = _LINEA.match(linea)
        if not m: continue
        d = {"x": int(m.group(3)), "y": int(m.group(4)), "w": int(m.group(5)), "h": int(m.group(6))}
        d.update(_CLAVE.findall(m.group(7)))
        if m.group(1) == "ventana":
            d["hwnd"] = int(d.get("hwnd") or 0); d["widgets"] = []; actual = d; ventanas.append(d)
        elif actual is not None:
            d.update(tipo_linea=m.group(1), clase=m.group(2), activa=" activa" in m.group(7), activo=m.group(7).endswith(" activo"))
            actual["widgets"].append(d)
    return ventanas


def principal(ventanas):
    return next((v for v in ventanas if v.get("rol") == "dia-main-window"), ventanas[0] if ventanas else None)


def _limpio(s): return re.sub(r"[\s_:]+$", "", (s or "").replace("_", "")).strip().lower()


def _buscar(ventanas, cond, preferir_dialogo=False):
    orden = sorted(ventanas, key=lambda v: (v.get("rol") == "dia-main-window") == (not preferir_dialogo))
    for v in orden:
        for w in v["widgets"]:
            if cond(w): return v, w
    return None, None


def resolver_uno(obj, ventanas, pantalla=None):
    """Un objetivo de «interfaz» → (marca o None, motivo si no se ve). `pantalla(nombre)` → rect del objeto del diagrama."""
    clave = next((k for k in CLAVES_INTERFAZ if k in obj), None)
    valor = str(obj.get(clave, ""))
    v = w = None
    texto = obj.get("texto")
    if clave == "herramienta":
        tip = obj.get("tip")
        v, w = _buscar(ventanas, lambda w: w.get("tipo") == valor and (not tip or w.get("tip") == tip))
        if not w:                                    # está en otra hoja: se señala el menú de hojas
            hoja = valor.split(" - ")[0]
            v, w = _buscar(ventanas, lambda w: w.get("clase") == "DiaDynamicMenu")
            if w: return _marca(v, w, f"Elige la hoja «{hoja}»", obj.get("color", "amarillo")), ""
            return None, f"no veo la herramienta {valor}"
        texto = texto or f"Herramienta «{w.get('tip') or valor}»"
    elif clave == "hoja":
        v, w = _buscar(ventanas, lambda w: w.get("clase") == "DiaDynamicMenu")
        texto = texto or (f"Hoja «{valor}»" if _limpio(w.get("texto") if w else "") == valor.lower() else f"Elige la hoja «{valor}»")
    elif clave == "menu":
        v, w = _buscar(ventanas, lambda w: w.get("clase") in ("GtkImageMenuItem", "GtkMenuItem") and _limpio(w.get("texto")) == _limpio(valor))
        texto = texto or f"Menú «{valor}»"
    elif clave == "pestana":
        v, w = _buscar(ventanas, lambda w: w["tipo_linea"] == "pestana" and _limpio(w.get("texto")) == _limpio(valor), True)
        texto = texto or f"Pestaña «{valor}»"
    elif clave == "boton":
        v, w = _buscar(ventanas, lambda w: w.get("clase") in ("GtkButton", "GtkToggleButton", "GtkCheckButton")
                       and (_limpio(w.get("texto")) == _limpio(valor) or _limpio(w.get("tip")) == _limpio(valor)), True)
        texto = texto or f"Botón «{valor}»"
    elif clave == "campo":
        v, etiqueta = _buscar(ventanas, lambda w: w.get("clase") == "GtkLabel" and _limpio(w.get("texto")) == _limpio(valor), True)
        if etiqueta:
            cy = etiqueta["y"] + etiqueta["h"] / 2
            cands = [x for x in v["widgets"] if x.get("clase") in ENTRADAS and x["x"] >= etiqueta["x"] + etiqueta["w"] - 4
                     and abs(x["y"] + x["h"] / 2 - cy) <= max(12, x["h"] / 2)]
            if not cands:                            # la caja debajo de la etiqueta
                cands = [x for x in v["widgets"] if x.get("clase") in ENTRADAS and 0 <= x["y"] - (etiqueta["y"] + etiqueta["h"]) <= 30
                         and abs(x["x"] - etiqueta["x"]) <= 40]
            w = min(cands, key=lambda x: abs(x["x"] - etiqueta["x"]) + abs(x["y"] - etiqueta["y"])) if cands else None
        texto = texto or f"Campo «{valor}»"
    elif clave == "objeto":
        r = pantalla(valor) if pantalla else None
        if not r: return None, f"«{valor}» no se ve ahora en Dia"
        v = principal(ventanas)
        if not v: return None, "no veo la ventana de Dia"
        return {"hwnd": v["hwnd"], "ventana": [v["x"], v["y"], v["w"], v["h"]], "rect": list(r), "texto": texto or f"«{valor}»",
                "color": obj.get("color", "azul")}, ""
    else:
        return None, "objetivo desconocido"
    if not w: return None, {"pestana": f"la pestaña «{valor}» no se ve (¿está abierto el diálogo Propiedades?)",
                            "boton": f"el botón «{valor}» no se ve ahora", "campo": f"el campo «{valor}» no se ve ahora",
                            "menu": f"el menú «{valor}» no se ve", "hoja": "no veo el menú de hojas"}.get(clave, f"no veo «{valor}»")
    return _marca(v, w, texto, obj.get("color", "azul")), ""


INTERACTIVOS = ("GtkButton", "GtkToggleButton", "GtkRadioButton", "GtkCheckButton", "GtkImageMenuItem", "GtkMenuItem", "DiaDynamicMenu",
                "GtkOptionMenu") + ENTRADAS


def _evitar(v, w):
    """Lo que la nota no debería tapar: los demás botones, herramientas, pestañas y campos de esa ventana."""
    return [[x["x"], x["y"], x["w"], x["h"]] for x in v["widgets"] if x is not w and (x["tipo_linea"] == "pestana" or x.get("clase") in INTERACTIVOS)]


def _marca(v, w, texto, color):
    return {"hwnd": v["hwnd"], "ventana": [v["x"], v["y"], v["w"], v["h"]], "rect": [w["x"], w["y"], w["w"], w["h"]],
            "texto": texto, "color": color if color in COLORES else "azul", "evitar": _evitar(v, w)}


def resolver(objetivos, ventanas, pantalla=None):
    """(marcas para el overlay, [motivos de lo que no se ve]). Con más de un objetivo, cada nota lleva su número."""
    marcas, faltan = [], []
    varios = len(objetivos or []) > 1
    for i, obj in enumerate(objetivos or [], 1):
        m, motivo = resolver_uno(obj, ventanas, pantalla)
        if m:
            if varios: m["n"] = i
            marcas.append(m)
        elif motivo: faltan.append(motivo)
    return marcas, faltan


# ---------- Validación del JSON de la lección (sin Dia) ----------
def validar_interfaz(lista, donde):
    if lista is None: return []
    if not isinstance(lista, list): raise ValueError(f"{donde}: «interfaz» es una lista [...]")
    out = []
    for k, o in enumerate(lista, 1):
        if not isinstance(o, dict): raise ValueError(f"{donde}, interfaz {k}: tiene que ser un objeto")
        claves = [c for c in CLAVES_INTERFAZ if c in o]
        if len(claves) != 1: raise ValueError(f"{donde}, interfaz {k}: lleva UNA de {', '.join(CLAVES_INTERFAZ)}")
        sobra = set(o) - set(claves) - {"texto", "color", "tip", "diagrama"}
        if sobra: raise ValueError(f"{donde}, interfaz {k}: campos que no conozco: {', '.join(sorted(sobra))}")
        if not isinstance(o[claves[0]], str) or not o[claves[0]].strip(): raise ValueError(f"{donde}, interfaz {k}: «{claves[0]}» es un texto")
        if o.get("color") and o["color"] not in COLORES: raise ValueError(f"{donde}, interfaz {k}: «color» es {', '.join(COLORES)}")
        out.append(dict(o))
    return out


PASOS_HAZLO = ("hoja", "herramienta", "seleccionar", "propiedades", "pulsar", "accion", "esperar")


def validar_hazlo(h, donde):
    if h is None: return None
    if not isinstance(h, dict): raise ValueError(f"{donde}: «hazlo» es {{\"etiqueta\": ..., \"hacer\": [...]}}")
    sobra = set(h) - {"etiqueta", "hacer", "senalar"}
    if sobra: raise ValueError(f"{donde}, hazlo: campos que no conozco: {', '.join(sorted(sobra))}")
    hacer = h.get("hacer")
    if not isinstance(hacer, list) or not hacer: raise ValueError(f"{donde}, hazlo: «hacer» es una lista de pasos")
    for k, p in enumerate(hacer, 1):
        if not isinstance(p, dict) or len(p) != 1 or next(iter(p)) not in PASOS_HAZLO:
            raise ValueError(f"{donde}, hazlo {k}: cada paso es UNO de {', '.join(PASOS_HAZLO)}")
        c, v = next(iter(p.items()))
        if c == "esperar":
            if not isinstance(v, (int, float)) or not 0 <= v <= 3: raise ValueError(f"{donde}, hazlo {k}: «esperar» son segundos (0 a 3)")
        elif not isinstance(v, str) or not v.strip(): raise ValueError(f"{donde}, hazlo {k}: «{c}» es un texto")
        if c == "accion" and v not in ACCIONES_OK: raise ValueError(f"{donde}, hazlo {k}: la acción «{v}» no está permitida (valen {', '.join(sorted(ACCIONES_OK))})")
    return {"etiqueta": str(h.get("etiqueta") or "Hazlo por mí")[:40], "hacer": hacer,
            "senalar": validar_interfaz(h.get("senalar"), f"{donde}, hazlo")}


def _q(s): return '"' + str(s).replace('"', "'") + '"'


def _ref(v):
    """Un objeto por su nombre o su texto (o una REF del plugin tal cual: tag:, id:, clase:, nombre:)."""
    return v if re.match(r"^(tag|id|clase|nombre):", v) else "nombre:" + v


def ordenes_hazlo(hacer, pestana, ventanas=None):
    """Los pasos de «hazlo» → [(orden del plugin, segundos que esperar después)]. `pestana`: el diagrama sobre el que se hace
    (se pone al frente antes, porque «accion» actúa sobre la pestaña activa)."""
    out = [(f"@{pestana} activar", 0.15)]
    for p in hacer:
        c, v = next(iter(p.items()))
        if c == "hoja": out.append((f"hoja {_q(v)}", 0.2))
        elif c == "herramienta":
            tip = None
            if ventanas:
                _, w = _buscar(ventanas, lambda w: w.get("tipo") == v)
                tip = w.get("tip") if w else None
            if not tip:                              # la caja muestra otra hoja: primero la hoja del tipo
                out.append((f"hoja {_q(v.split(' - ')[0])}", 0.3)); out.append(("__herramienta__ " + v, 0.1))
            else: out.append((f"pulsar {_q(tip)}", 0.1))
        elif c == "seleccionar": out.append((f"@{pestana} seleccionar {_q(_ref(v))}", 0.1))
        elif c == "propiedades":
            out.append((f"@{pestana} seleccionar {_q(_ref(v))}", 0.1)); out.append(("accion ObjectsProperties", 0.6))
        elif c == "pulsar": out.append((f"pulsar {_q(v)}", 0.3))
        elif c == "accion": out.append((f"accion {v}", 0.3))
        elif c == "esperar": out.append(("", float(v)))
    return out
