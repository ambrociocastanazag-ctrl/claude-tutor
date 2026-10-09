"""Cambios que el tutor propone en Dia (siempre con permiso), como en el panel de Excel.

El tutor termina su respuesta con UN bloque <acciones>{...}</acciones> (formato en REGLAS_ACCIONES).
El panel lo valida sin tocar Dia (separar_acciones), arma la tarjeta «El tutor quiere…» con lo que hay
en pantalla (Cambios.preparar) y, solo si la persona pulsa Aplicar, lo hace en vivo con el plugin
(órdenes reemplazar / quitar / anadir / transaccion): lo creado SÍ cuenta como cambio del diagrama
(queda modificado y Ctrl+Z de Dia lo deshace). «Deshacer» de la tarjeta quita lo creado y devuelve lo
modificado. Si la propuesta trae un ejercicio, se revisa con «Comprobar» sin IA (dia_uml.revisar_varios).

Los demás diagramas UML (casos de uso, secuencia, actividades, estados, componentes, despliegue, paquetes,
objetos) y el «modo libre» (cualquier objeto de Dia por su tipo) están en dia_planes: sus acciones entran en el
registro ACCIONES y su plan lo lleva dia_planes.Contexto junto al de las clases. Cada relación de clase vive en
dia_uml.TIPOS_REL."""
import hashlib, json, os, re, tempfile, time
from pathlib import Path

import dia_uml as du
import dia_objetos as do
import dia_planes as dp

MAX_CAMBIOS, MAX_CLASES, MAX_MIEMBROS = 60, 12, 20          # propuestas del tutor
MAX_CAMBIOS_CURSO, MAX_CLASES_CURSO, MAX_OBJETOS_CURSO = 300, 40, 100   # lo que viene de un curso (pasos, inicial, solucion, prueba)
NOMBRE = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ_][\wÁÉÍÓÚÜÑáéíóúüñ]{0,40}$")
VERSION_PLUGIN = 6                                   # la orden «version» del plugin que sabe aplicar todos estos cambios


# ---------- Validación del bloque (sin tocar Dia) ----------
def _texto(v, donde, largo=300, vacio=True):
    if v is None: v = ""
    if not isinstance(v, (str, int, float)): raise ValueError(f"{donde}: tiene que ser texto")
    v = str(v).strip()
    if not v and not vacio: raise ValueError(f"{donde}: está vacío")
    if len(v) > largo: raise ValueError(f"{donde}: demasiado largo (máximo {largo} caracteres)")
    return v


def _nombre_clase(v, donde):
    v = _texto(v, donde, 40, vacio=False)
    if not NOMBRE.match(v): raise ValueError(f"{donde}: «{v}» no es un nombre de clase válido (una palabra, sin espacios)")
    return v


def _solo_tipo(conv, parametros=None):
    """¿Los parámetros se dibujan solo con el tipo (K1)? `parametros` es el de este cambio (si lo trae) o el del curso."""
    return (parametros or (conv or {}).get("parametros")) == "solo_tipo"


def _miembros(lista, donde, es=None, conv=None, parametros=None):
    if lista is None: return None
    if not isinstance(lista, list): raise ValueError(f"{donde}: tiene que ser una lista [...]")
    if len(lista) > MAX_MIEMBROS: raise ValueError(f"{donde}: demasiados (máximo {MAX_MIEMBROS})")
    out = []
    for s in lista:
        m = du.miembro(s)
        if m["es"] == "metodo" and _solo_tipo(conv, parametros): m = du.sin_nombres_de_parametros(m)    # convención K1
        if es and m["es"] != es:
            raise ValueError(f"{donde}: «{du.linea_metodo(m) if m['es'] == 'metodo' else du.linea_atributo(m)}» es un "
                             f"{'método' if m['es'] == 'metodo' else 'atributo'}" + (" (lleva paréntesis)" if m["es"] == "metodo" else " (sin paréntesis)"))
        out.append(m)
    return out


def _campos(a, permitidos, k):
    sobra = set(a) - permitidos
    if sobra: raise ValueError(f"cambio {k}: campos que no conozco: {', '.join(sorted(sobra))}")


def _pos(v, k):
    if v is None: return None
    if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)) or not all(-50 <= x <= 300 for x in v):
        raise ValueError(f"cambio {k}: «pos» tiene que ser [x, y] en cm (entre -50 y 300)")
    return (float(v[0]), float(v[1]))


def _v_clase(a, k, interfaz=False, conv=None):
    clave = "interfaz" if interfaz else "clase"
    _campos(a, {clave, "atributos", "metodos", "abstracta", "estereotipo", "pos", "dentro_de", "biblioteca", "enumerada", "parametros", "negrita"}, k)
    if a.get("parametros") not in (None, "solo_tipo", "nombre_tipo"): raise ValueError(f"cambio {k}: «parametros» es \"solo_tipo\" o \"nombre_tipo\"")
    par = a.get("parametros")
    c = {"accion": "clase", "nombre": _nombre_clase(a[clave], f"cambio {k}"),
         "atributos": _miembros(a.get("atributos"), f"cambio {k}, atributos", "atributo", conv, par) or [],
         "metodos": _miembros(a.get("metodos"), f"cambio {k}, métodos", "metodo", conv, par) or [],
         "abstracta": bool(a.get("abstracta", False)), "estereotipo": _texto(a.get("estereotipo"), f"cambio {k}, estereotipo", 30),
         "pos": _pos(a.get("pos"), k), "dentro_de": _texto(a.get("dentro_de"), f"cambio {k}, dentro_de", 80),
         "biblioteca": bool(a.get("biblioteca", False)), "enumerada": None}
    if (conv or {}).get("nombre_negrita") is False: c["negrita"] = False        # convención 18
    if "negrita" in a:                                                           # «negrita»: true la planta a propósito (ejercicios «corrige el diagrama»)
        if not isinstance(a["negrita"], bool): raise ValueError(f"cambio {k}: «negrita» es true o false")
        c["negrita"] = a["negrita"]
    if c["biblioteca"] and (c["atributos"] or c["metodos"]): raise ValueError(f"cambio {k}: una clase «biblioteca» va vacía (sin atributos ni métodos)")
    if a.get("enumerada") is not None:
        vals = a["enumerada"]
        if not isinstance(vals, list) or not vals or len(vals) > MAX_MIEMBROS or not all(isinstance(v, str) and NOMBRE.match(v.strip()) for v in vals):
            raise ValueError(f"cambio {k}: «enumerada» es la lista de sus valores, como [\"ALWAYS\", \"NEVER\"]")
        if c["atributos"] or c["metodos"] or c["estereotipo"] or c["abstracta"] or interfaz:
            raise ValueError(f"cambio {k}: una enumerada solo lleva sus valores (sin atributos, métodos ni estereotipo)")
        c["enumerada"] = [v.strip() for v in vals]
    if interfaz:
        c["estereotipo"] = "interface"
        for m in c["metodos"]: m["abstracto"] = True
        if c["atributos"]: raise ValueError(f"cambio {k}: una interfaz no lleva atributos")
    return c


def _v_modificar(a, k, conv=None):
    _campos(a, {"modificar", "nombre", "abstracta", "estereotipo", "atributos", "metodos", "agregar", "quitar", "negrita"}, k)
    if "negrita" in a and not isinstance(a["negrita"], bool): raise ValueError(f"cambio {k}: «negrita» es true o false")
    c = {"accion": "modificar", "clase": _nombre_clase(a["modificar"], f"cambio {k}")}
    if "nombre" in a: c["nombre"] = _nombre_clase(a["nombre"], f"cambio {k}, nombre")
    if "abstracta" in a: c["abstracta"] = bool(a["abstracta"])
    if "negrita" in a: c["negrita"] = a["negrita"]
    if "estereotipo" in a: c["estereotipo"] = _texto(a["estereotipo"], f"cambio {k}, estereotipo", 30)
    if "atributos" in a: c["atributos"] = _miembros(a["atributos"], f"cambio {k}, atributos", "atributo", conv)
    if "metodos" in a: c["metodos"] = _miembros(a["metodos"], f"cambio {k}, métodos", "metodo", conv)
    if "agregar" in a: c["agregar"] = _miembros(a["agregar"], f"cambio {k}, agregar", None, conv)
    if "quitar" in a:
        if not isinstance(a["quitar"], list): raise ValueError(f"cambio {k}: «quitar» es una lista de nombres de atributos o métodos")
        c["quitar"] = [re.split(r"[:(]", _texto(x, f"cambio {k}, quitar", 60, False))[0].strip().lstrip("+-#~") for x in a["quitar"]]
    if len(c) == 2: raise ValueError(f"cambio {k}: «modificar» no dice qué cambiar")
    return c


def _v_quitar(a, k):
    _campos(a, {"quitar_clase"}, k)
    return {"accion": "quitar_clase", "clase": _nombre_clase(a["quitar_clase"], f"cambio {k}")}


def _ref_objeto(v, donde):
    """Nombre de una clase o de cualquier otro objeto (actor, caso de uso, nodo...: su texto, o «#O7»)."""
    v = _texto(v, donde, 80, vacio=False)
    return v


def _v_relacion(a, k):
    _campos(a, {"relacion", "de", "a", "todo", "parte", "nombre", "mult", "roles", "direccion", "estereotipo", "lectura"}, k)
    tipo = _texto(a["relacion"], f"cambio {k}, relacion", 20).lower()
    tipo = {"generalizacion": "herencia", "generalización": "herencia", "realización": "realizacion", "implementacion": "realizacion",
            "asociación": "asociacion", "agregación": "agregacion", "composición": "composicion", "inclusion": "include",
            "inclusión": "include", "extension": "extend", "extensión": "extend"}.get(tipo, tipo)
    if tipo not in du.TIPOS_REL: raise ValueError(f"cambio {k}: relación «{tipo}» desconocida (usa {', '.join(du.TIPOS_REL)})")
    if "todo" in a or "parte" in a:          # agregación / composición: también con todo y parte
        if tipo not in ("agregacion", "composicion"): raise ValueError(f"cambio {k}: «todo» y «parte» son para agregación y composición")
        de, al = a.get("parte"), a.get("todo")
    else: de, al = a.get("de"), a.get("a")
    r = {"accion": "relacion", "tipo": tipo, "de": _ref_objeto(de, f"cambio {k}, de"), "a": _ref_objeto(al, f"cambio {k}, a"),
         "nombre": _texto(a.get("nombre"), f"cambio {k}, nombre", 40), "mult": ["", ""], "roles": ["", ""], "direccion": "",
         "estereotipo": _texto(a.get("estereotipo"), f"cambio {k}, estereotipo", 30)}
    if r["estereotipo"] and tipo != "dependencia": raise ValueError(f"cambio {k}: «estereotipo» es solo para dependencias (p. ej. \"import\", \"deploy\")")
    if r["de"].lower() == r["a"].lower(): raise ValueError(f"cambio {k}: una relación de una clase consigo misma no se puede dibujar aquí")
    for campo in ("mult", "roles"):
        if campo in a:
            v = a[campo]
            if not (isinstance(v, list) and len(v) == 2): raise ValueError(f"cambio {k}: «{campo}» es [junto a de, junto a a]")
            r[campo] = [_texto(x, f"cambio {k}, {campo}", 20) for x in v]
    if tipo not in ("asociacion", "agregacion", "composicion") and (any(r["mult"]) or any(r["roles"])):
        raise ValueError(f"cambio {k}: la {du.TIPOS_REL[tipo]['nombre']} no lleva multiplicidades")
    if "direccion" in a:
        d = _texto(a["direccion"], f"cambio {k}, direccion", 10).lower()
        if d not in ("", "a", "de", "ambas", "ninguna"): raise ValueError(f"cambio {k}: «direccion» es \"a\", \"de\", \"ambas\" o \"ninguna\"")
        if d and d != "ninguna" and tipo not in ("asociacion", "agregacion", "composicion"):
            raise ValueError(f"cambio {k}: «direccion» es solo para asociaciones, agregaciones y composiciones")
        r["direccion"] = "" if d == "ninguna" else d
    if "lectura" in a:      # el triángulo de lectura (convención 25) hacia «a» o hacia «de»; hace falta el verbo en «nombre»
        lec = _texto(a["lectura"], f"cambio {k}, lectura", 10).lower()
        if lec not in ("", "a", "de"): raise ValueError(f"cambio {k}: «lectura» es \"a\" o \"de\" (hacia qué clase apunta el triángulo)")
        if lec and tipo not in ("asociacion", "agregacion", "composicion"): raise ValueError(f"cambio {k}: «lectura» es solo para asociaciones, agregaciones y composiciones")
        if lec and not r["nombre"]: raise ValueError(f"cambio {k}: «lectura» necesita el verbo en «nombre» (p. ej. \"tiene\")")
        r["lectura"] = lec
    return r


def _v_quitar_relacion(a, k):
    _campos(a, {"quitar_relacion", "de", "a"}, k)
    tipo = _texto(a["quitar_relacion"], f"cambio {k}", 20).lower()
    if tipo not in du.TIPOS_REL and tipo != "cualquiera": raise ValueError(f"cambio {k}: relación «{tipo}» desconocida")
    return {"accion": "quitar_relacion", "tipo": tipo, "de": _nombre_clase(a.get("de"), f"cambio {k}, de"),
            "a": _nombre_clase(a.get("a"), f"cambio {k}, a")}


def _v_nota(a, k):
    _campos(a, {"nota", "junto_a", "pos"}, k)
    return {"accion": "nota", "texto": _texto(a["nota"], f"cambio {k}, nota", 300, False).replace("\\n", "\n"),
            "junto_a": _nombre_clase(a["junto_a"], f"cambio {k}, junto_a") if a.get("junto_a") else "", "pos": _pos(a.get("pos"), k)}


def _d_clase(c):
    tipo = "la interfaz" if c.get("estereotipo") == "interface" else "la clase abstracta" if c.get("abstracta") else "la clase"
    ms = [du.linea_atributo(x) for x in c["atributos"]] + [du.linea_metodo(x) for x in c["metodos"]]
    return f"Crear {tipo} «{c['nombre']}»" + (": " + ", ".join(f"`{m}`" for m in ms[:6]) + ("…" if len(ms) > 6 else "") if ms else "")


def _d_modificar(c):
    partes = []
    if "nombre" in c: partes.append(f"llamarla «{c['nombre']}»")
    if "abstracta" in c: partes.append("hacerla abstracta" if c["abstracta"] else "que no sea abstracta")
    if "estereotipo" in c: partes.append(f"estereotipo «{c['estereotipo']}»" if c["estereotipo"] else "quitarle el estereotipo")
    if c.get("agregar"): partes.append("añadir " + ", ".join(f"`{du.linea_metodo(m) if m['es'] == 'metodo' else du.linea_atributo(m)}`" for m in c["agregar"]))
    if c.get("quitar"): partes.append("quitar " + ", ".join(f"«{q}»" for q in c["quitar"]))
    if "atributos" in c: partes.append("atributos: " + (", ".join(f"`{du.linea_atributo(m)}`" for m in c["atributos"]) or "ninguno"))
    if "metodos" in c: partes.append("métodos: " + (", ".join(f"`{du.linea_metodo(m)}`" for m in c["metodos"]) or "ninguno"))
    return f"Cambiar la clase «{c['clase']}»: " + "; ".join(partes)


def _d_relacion(r):
    f = du.frase_relacion({**r, "de": r["de"], "a": r["a"]})
    return f"Relación: {f}"


ACCIONES = {          # clave del JSON → (validar, describir); las de los otros diagramas, al final (dia_planes)
    "clase": (lambda a, k, conv=None: _v_clase(a, k, conv=conv), _d_clase),
    "interfaz": (lambda a, k, conv=None: _v_clase(a, k, interfaz=True, conv=conv), _d_clase),
    "modificar": (_v_modificar, _d_modificar),
    "quitar_clase": (lambda a, k, conv=None: _v_quitar(a, k), lambda c: f"Quitar la clase «{c['clase']}» (y las relaciones que tiene)"),
    "relacion": (lambda a, k, conv=None: _v_relacion(a, k), _d_relacion),
    "quitar_relacion": (lambda a, k, conv=None: _v_quitar_relacion(a, k), lambda c: f"Quitar la relación {c['tipo'] if c['tipo'] != 'cualquiera' else ''} entre «{c['de']}» y «{c['a']}»".replace("  ", " ")),
    "nota": (lambda a, k, conv=None: _v_nota(a, k), lambda c: f"Nota: «{c['texto'][:60]}»" + (f" junto a «{c['junto_a']}»" if c["junto_a"] else "")),
}
for _clave in sorted(dp.claves()):           # casos de uso, secuencia, actividades, estados, componentes... y modo libre
    ACCIONES[_clave] = ((lambda c: lambda a, k, conv=None: dp.validar(c, a, k))(_clave), dp.describir)


def _v_ejercicio(e, conv=None):
    if not isinstance(e, dict): raise ValueError("«ejercicio» tiene que ser un objeto {...}")
    sobra = set(e) - {"titulo", "clases", "relaciones", "al_empezar", "al_terminar", "sinonimos", "objetos", "conexiones", "mensajes"}
    if sobra: raise ValueError(f"ejercicio: campos que no conozco: {', '.join(sorted(sobra))}")
    clases = []
    for i, c in enumerate(e.get("clases") or [], 1):
        if not isinstance(c, dict): raise ValueError(f"ejercicio, clase {i}: tiene que ser un objeto")
        s = set(c) - {"nombre", "atributos", "metodos", "abstracta", "interfaz", "dentro_de", "biblioteca", "enumerada"}
        if s: raise ValueError(f"ejercicio, clase {i}: campos que no conozco: {', '.join(sorted(s))}")
        x = {"nombre": _nombre_clase(c.get("nombre"), f"ejercicio, clase {i}")}
        if c.get("atributos") is not None: x["atributos"] = _miembros(c["atributos"], f"ejercicio, {x['nombre']}, atributos", "atributo", conv)
        if c.get("metodos") is not None: x["metodos"] = _miembros(c["metodos"], f"ejercicio, {x['nombre']}, métodos", "metodo", conv)
        if "abstracta" in c: x["abstracta"] = bool(c["abstracta"])
        if c.get("interfaz"): x["interfaz"] = True
        if c.get("dentro_de"): x["dentro_de"] = _texto(c["dentro_de"], f"ejercicio, {x['nombre']}, dentro_de", 80)     # su paquete (parentesco real)
        if c.get("biblioteca"):                                       # clase de la biblioteca de Java: va vacía (K3)
            if c.get("atributos") or c.get("metodos") or c.get("enumerada"): raise ValueError(f"ejercicio, {x['nombre']}: una clase «biblioteca» va vacía")
            x["biblioteca"] = True
        if c.get("enumerada") is not None:
            if not isinstance(c["enumerada"], list) or not c["enumerada"] or not all(isinstance(v, str) and NOMBRE.match(v.strip()) for v in c["enumerada"]):
                raise ValueError(f"ejercicio, {x['nombre']}: «enumerada» es la lista de sus valores")
            x["enumerada"] = [v.strip() for v in c["enumerada"]]
        clases.append(x)
    rels = []
    for i, r in enumerate(e.get("relaciones") or [], 1):
        if not isinstance(r, dict): raise ValueError(f"ejercicio, relación {i}: tiene que ser un objeto")
        r = dict(r)
        if "tipo" in r and "relacion" not in r: r["relacion"] = r.pop("tipo")
        v = _v_relacion(r, f"del ejercicio {i}")
        rels.append({"tipo": v["tipo"], "de": v["de"], "a": v["a"], "mult": v["mult"] if any(v["mult"]) else None,
                     **{k2: v[k2] for k2 in ("nombre", "lectura", "direccion") if v.get(k2)}})
    sin = e.get("sinonimos") or {}
    if not isinstance(sin, dict): raise ValueError("ejercicio: «sinonimos» es {\"String\": [\"string\", \"texto\"]}")
    ej = {"titulo": _texto(e.get("titulo"), "ejercicio, titulo", 60) or "Ejercicio", "clases": clases, "relaciones": rels,
          "al_empezar": _texto(e.get("al_empezar"), "ejercicio, al_empezar", 300) or "Hazlo en Dia, guarda (Ctrl+S) y pulsa Comprobar.",
          "al_terminar": _texto(e.get("al_terminar"), "ejercicio, al_terminar", 300) or "¡Todo bien!", "sinonimos": sin}
    dp.validar_ejercicio(e, ej)                  # objetos, conexiones y mensajes (casos de uso, secuencia, actividades, estados...)
    rutas = [o["ruta"] for o in ej["objetos"] if o.get("ruta")]
    for x in clases:                             # «dentro_de» de cada clase: nombre o ruta de su capa (ambiguo = error que pide la ruta)
        if x.get("dentro_de") and rutas:
            try: r = du.resolver_ruta(x["dentro_de"], rutas)
            except ValueError as err: raise ValueError(f"ejercicio, {x['nombre']}, dentro_de: {err}")
            if r is not None: x["dentro_ruta"] = r
    if not clases and not rels and not ej["objetos"] and not ej["conexiones"] and not ej["mensajes"]:
        raise ValueError("el ejercicio no dice qué se espera (clases, relaciones, objetos, conexiones o mensajes)")
    return ej


def validar_propuesta(d, conv=None, curso=False):
    """Revisa el bloque <acciones> sin tocar Dia. Devuelve la propuesta limpia o lanza ValueError con el motivo.
    `conv` son las convenciones del curso (nombre_negrita, parametros): lo que se crea las lleva (sin negrita, parámetros solo con el tipo...)."""
    if not isinstance(d, dict): raise ValueError("el bloque tiene que ser un objeto JSON {...}")
    sobra = set(d) - {"para", "resumen", "diagrama", "titulo", "cambios", "ejercicio"}
    if sobra: raise ValueError(f"campos que no conozco: {', '.join(sorted(sobra))}")
    diag = _texto(d.get("diagrama") or "nuevo", "diagrama", 60).lower()
    if diag in ("mi_diagrama", "mi_diagrama.dia", "mio", "mío", "suyo"): diag = "mio"
    elif diag in ("leccion", "lección", "clase_en_vivo", "clase_en_vivo.dia", "ejemplo"): diag = "leccion"
    elif diag != "nuevo" and not re.match(r"^(ejemplo|ejercicio)_\d{1,3}(\.dia)?$", diag):
        raise ValueError(f"«diagrama» es \"nuevo\", \"mio\", \"leccion\" o uno tuyo como \"ejemplo_1.dia\" (no «{diag}»)")
    elif diag != "nuevo" and not diag.endswith(".dia"): diag += ".dia"
    cambios = d.get("cambios", [])
    if not isinstance(cambios, list): raise ValueError("«cambios» tiene que ser una lista [...]")
    max_c, max_cl, max_o = (MAX_CAMBIOS_CURSO, MAX_CLASES_CURSO, MAX_OBJETOS_CURSO) if curso else (MAX_CAMBIOS, MAX_CLASES, 40)
    if len(cambios) > max_c: raise ValueError(f"demasiados cambios (máximo {max_c})")
    limpios = []
    for k, a in enumerate(cambios, 1):
        if not isinstance(a, dict): raise ValueError(f"cambio {k}: tiene que ser un objeto {{...}}")
        claves = [c for c in a if c in ACCIONES]
        if len(claves) != 1: raise ValueError(f"cambio {k}: tiene que tener UNA de estas claves: {', '.join(ACCIONES)}")
        limpios.append(ACCIONES[claves[0]][0](a, k, conv))
    if sum(c["accion"] == "clase" for c in limpios) > max_cl: raise ValueError(f"demasiadas clases (máximo {max_cl})")
    if sum(c["accion"] in dp.ELEMENTOS for c in limpios) > max_o: raise ValueError(f"demasiados objetos (máximo {max_o})")
    ej = _v_ejercicio(d["ejercicio"], conv) if d.get("ejercicio") else None
    if not limpios and not ej: raise ValueError("no trae ningún cambio")
    if not limpios and diag != "nuevo": raise ValueError("un ejercicio sin cambios va en un diagrama nuevo")
    return {"para": _texto(d.get("para") or d.get("resumen"), "para", 200), "diagrama": diag,
            "titulo": _texto(d.get("titulo"), "titulo", 60), "cambios": limpios, "ejercicio": ej, "conv": dict(conv or {})}


def separar_acciones(resp, conv=None):
    """Saca de la respuesta el bloque <acciones>{...}</acciones>: (texto, propuesta o None, error o None)."""
    m = re.search(r"<acciones>(.*?)</acciones>", resp, re.S)
    if not m:
        m2 = re.search(r"<acciones>.*\Z", resp, re.S)
        if not m2: return resp, None, None
        return resp[:m2.start()].strip(), None, "el bloque <acciones> no se cerró"
    texto = (resp[:m.start()] + resp[m.end():]).strip()
    if re.search(r"<acciones>", texto): return texto, None, "trae más de un bloque <acciones>: junta todo en uno"
    try: d = json.loads(m.group(1))
    except Exception as e: return texto, None, f"el JSON no es válido ({e})"
    try: return texto, validar_propuesta(d, conv), None
    except ValueError as e: return texto, None, str(e)


# ---------- Planear: qué hay que hacer en el diagrama de ahora (sin tocarlo) ----------
def firma(c):
    """Lo que importa de una clase para saber si alguien la cambió."""
    return (c["nombre"], bool(c.get("abstracta")), c.get("estereotipo", "") or "",
            tuple((a["nombre"], a.get("tipo", ""), a.get("vis", "+"), bool(a.get("estatico"))) for a in c["atributos"]),
            tuple((m["nombre"], m.get("tipo", ""), m.get("vis", "+"), bool(m.get("abstracto")), bool(m.get("estatico")),
                   tuple((p["nombre"], p.get("tipo", "")) for p in m.get("params", []))) for m in c["metodos"]))


def _choca(a, b, margen=1.5):
    return not (a[0] + a[2] + margen <= b[0] or b[0] + b[2] + margen <= a[0] or a[1] + a[3] + margen <= b[1] or b[1] + b[3] + margen <= a[1])


def caja_estimada(c):
    """Ancho y alto aproximados de una clase en Dia (fuente Courier 0,8: unos 0,42 cm por letra)."""
    filas = [du.linea_atributo(a) for a in c.get("atributos", [])] + [du.linea_metodo(m) for m in c.get("metodos", [])]
    w = max(4.0, 0.42 * max([len(f) for f in filas] or [0]) + 0.8, 0.62 * len(c["nombre"]) + 1.4)
    h = (1.9 if c.get("estereotipo") else 1.4) + 0.8 * max(1, len(c.get("atributos", []))) + 0.8 * max(1, len(c.get("metodos", []))) + 0.4
    return w, h


def planear(prop, d, pid, medidas=None):
    """Traduce la propuesta a órdenes sobre el diagrama `d` (dia_uml.leer de lo que hay ahora en pantalla).
    Lanza ValueError si no encaja (una clase que no existe, un nombre repetido…). Devuelve el plan:
    nuevas (clases con su etiqueta y su sitio), relaciones, notas, modificar [(id, vieja, nueva)],
    quitar [id], quitadas (lo que se quita, para poder devolverlo) y el detalle para la tarjeta."""
    clases = {}                                        # nombre normalizado → {"c": dict, "nueva": bool, "id": id de Dia}
    repetidos = set()
    for c in d["clases"]:
        k = du._norm(c["nombre"])
        if k in clases: repetidos.add(k)
        clases[k] = {"c": c, "nueva": False, "id": c["id"]}
    nombre_de_id = {c["id"]: c["nombre"] for c in d["clases"]}
    plan = {"nuevas": [], "relaciones": [], "notas": [], "modificar": {}, "quitar": [], "quitadas": {"clases": [], "relaciones": [], "notas": []},
            "detalle": [], "tags": [], "cuenta": {"clases": 0, "relaciones": 0, "notas": 0, "cambia": [], "quita": [], "quita_rel": 0}}
    rels_vivas = [r for r in d.get("relaciones", [])]
    n = 0

    def etiqueta():
        nonlocal n
        n += 1; t = f"{pid}.{n}"; plan["tags"].append(t); return t

    def buscar(nombre, k, quien):
        x = clases.get(du._norm(nombre))
        if not x: raise ValueError(f"cambio {k}: no hay una clase «{nombre}» en el diagrama")
        if du._norm(nombre) in repetidos: raise ValueError(f"cambio {k}: hay dos clases «{nombre}»; cambia el nombre de una")
        return x

    ctx = dp.Contexto(d, plan, etiqueta, clases)       # actores, casos, mensajes, estados, nodos... y el modo libre
    plan["conv"] = dict(prop.get("conv") or {})

    def extremo(nombre, k):
        """Un extremo de relación: una clase (como antes) o cualquier otro objeto (dia_planes)."""
        if du._norm(nombre) in clases: return buscar(nombre, k, "")
        x = ctx.buscar(nombre, k)
        return x if not x.get("clase") else x["reg_clase"]

    def id_de(x): return x["id"] if "c" in x else x["o"].get("id")

    for k, a in enumerate(prop["cambios"], 1):
        acc = a["accion"]
        if acc == "clase":
            if du._norm(a["nombre"]) in clases: raise ValueError(f"cambio {k}: ya hay una clase «{a['nombre']}» (para cambiarla, usa «modificar»)")
            c = {"nombre": a["nombre"], "atributos": a["atributos"], "metodos": a["metodos"], "abstracta": a["abstracta"],
                 "estereotipo": a["estereotipo"], "tag": etiqueta(), "pos": a.get("pos"), "dentro_de": a.get("dentro_de", "")}
            if "negrita" in a: c["negrita"] = a["negrita"]
            if a.get("enumerada") is not None: c["enumerada"] = a["enumerada"]
            clases[du._norm(c["nombre"])] = {"c": c, "nueva": True, "id": None}
            plan["nuevas"].append(c); plan["cuenta"]["clases"] += 1
        elif acc == "modificar":
            x = buscar(a["clase"], k, "modificar")
            if x["nueva"]: raise ValueError(f"cambio {k}: «{a['clase']}» la creas en esta misma propuesta: ponlo todo al crearla")
            m = plan["modificar"].get(x["id"])
            vieja = x["c"]; nueva = dict(m[1] if m else vieja)
            nueva["atributos"], nueva["metodos"] = list(nueva["atributos"]), list(nueva["metodos"])
            for campo in ("abstracta", "negrita", "estereotipo", "atributos", "metodos"):
                if campo in a: nueva[campo] = a[campo]
            if a.get("quitar"):
                faltan = [q for q in a["quitar"] if not any(du._norm(x2["nombre"]) == du._norm(q) for x2 in nueva["atributos"] + nueva["metodos"])]
                if faltan: raise ValueError(f"cambio {k}: «{a['clase']}» no tiene {', '.join(f'«{q}»' for q in faltan)}")
                nueva["atributos"] = [x2 for x2 in nueva["atributos"] if du._norm(x2["nombre"]) not in {du._norm(q) for q in a["quitar"]}]
                nueva["metodos"] = [x2 for x2 in nueva["metodos"] if du._norm(x2["nombre"]) not in {du._norm(q) for q in a["quitar"]}]
            for mb in a.get("agregar") or []:
                lista = nueva["metodos"] if mb["es"] == "metodo" else nueva["atributos"]
                if any(du._norm(x2["nombre"]) == du._norm(mb["nombre"]) for x2 in lista):
                    raise ValueError(f"cambio {k}: «{a['clase']}» ya tiene «{mb['nombre']}»")
                lista.append(mb)
            if "nombre" in a and du._norm(a["nombre"]) != du._norm(nueva["nombre"]):
                if du._norm(a["nombre"]) in clases: raise ValueError(f"cambio {k}: ya hay una clase «{a['nombre']}»")
                del clases[du._norm(nueva["nombre"])]; nueva["nombre"] = a["nombre"]
                clases[du._norm(a["nombre"])] = dict(x, c=vieja)
            plan["modificar"][x["id"]] = (vieja, nueva)
            if vieja["nombre"] not in plan["cuenta"]["cambia"]: plan["cuenta"]["cambia"].append(vieja["nombre"])
        elif acc == "quitar_clase":
            x = buscar(a["clase"], k, "quitar")
            if x["nueva"]: raise ValueError(f"cambio {k}: «{a['clase']}» la creas en esta misma propuesta")
            if x["id"] in plan["modificar"]: raise ValueError(f"cambio {k}: «{a['clase']}» se cambia y se quita a la vez")
            del clases[du._norm(a["clase"])]
            plan["quitar"].append(x["id"]); plan["quitadas"]["clases"].append(x["c"]); plan["cuenta"]["quita"].append(x["c"]["nombre"])
            for r in [r for r in rels_vivas if x["id"] in (r.get("de_id"), r.get("a_id"))]:
                rels_vivas.remove(r); plan["quitar"].append(r["id"]); plan["quitadas"]["relaciones"].append(r)
        elif acc == "relacion":
            de, al = extremo(a["de"], k), extremo(a["a"], k)
            if not de["nueva"] and not al["nueva"] and any(r["tipo"] == a["tipo"] and {r.get("de_id"), r.get("a_id")} == {id_de(de), id_de(al)} for r in rels_vivas):
                raise ValueError(f"cambio {k}: esa {du.TIPOS_REL[a['tipo']]['nombre']} ya está en el diagrama")
            nombre_x = lambda x: x["c"]["nombre"] if "c" in x else dp.nombre_de(x["o"])
            r = dict(a, tag=etiqueta(), de=nombre_x(de), a=nombre_x(al), _de=de, _a=al)
            plan["relaciones"].append(r); plan["cuenta"]["relaciones"] += 1
        elif acc == "quitar_relacion":
            de, al = buscar(a["de"], k, "de"), buscar(a["a"], k, "a")
            cand = [r for r in rels_vivas if {r.get("de_id"), r.get("a_id")} == {de["id"], al["id"]} and (a["tipo"] == "cualquiera" or r["tipo"] == a["tipo"])]
            if not cand: raise ValueError(f"cambio {k}: no hay esa relación entre «{a['de']}» y «{a['a']}»")
            rels_vivas.remove(cand[0]); plan["quitar"].append(cand[0]["id"]); plan["quitadas"]["relaciones"].append(cand[0])
            plan["cuenta"]["quita_rel"] += 1
        elif acc == "nota":
            junto = buscar(a["junto_a"], k, "junto_a") if a["junto_a"] else None
            plan["notas"].append({"texto": a["texto"], "pos": a.get("pos"), "tag": etiqueta(), "_junto": junto})
            plan["cuenta"]["notas"] += 1
        else:
            ctx.cambio(a, k)                           # los demás diagramas y el modo libre
        plan["detalle"].append(ACCIONES["interfaz" if acc == "clase" and a.get("estereotipo") == "interface" else acc][1](a))
    ctx.resolver_clases(plan["nuevas"])                # «dentro_de» de las clases: nombre o ruta de su capa (error claro si es ambiguo)
    ej = prop.get("ejercicio") or {}
    ctx.dentro_de_existentes()                         # clases que van dentro de un paquete que ya estaba: su sitio dentro de él
    _colocar(plan, d, ej.get("relaciones") or [])
    ctx.cerrar(medidas, list(ej.get("conexiones") or []) + list(ej.get("relaciones") or []))
    plan["medir"] = ctx.xml_medir()
    # las relaciones a clases que ya estaban se pegan por su nombre DESPUÉS de los cambios (reemplazar va antes que anadir);
    # las de otros objetos que ya estaban, por su id (descontando lo que se quita antes)
    for r in plan["relaciones"]:
        inicio_es_a = du.TIPOS_REL[r["tipo"]]["inicio_es_a"]
        r["_cx"] = tuple(_centro_x(r["_" + lado]) for lado in ("de", "a"))     # dónde queda cada extremo: para el triángulo de lectura
        if r.get("lectura") in ("a", "de"): inicio_es_a = du.orientacion(r)[0]   # y qué extremo es el inicio (A) de la línea
        for lado in ("de", "a"):
            x = r.pop("_" + lado)
            h = r.get("_hint_ini" if (lado == "a") == inicio_es_a else "_hint_fin")
            punto = f"@{h[0]:.3f},{h[1]:.3f}" if h else ""      # el lado por el que entra (trazo de dia_planes)
            if "c" in x:
                r["ref_" + lado] = (f"tag:{x['c']['tag']}" if x["nueva"] else f"clase:{(plan['modificar'].get(x['id']) or (None, x['c']))[1]['nombre']}") + punto
            else:
                r["ref_" + lado] = ctx.ref(x, punto or None)
    return plan


def _centro_x(x):
    """Centro horizontal (cm) de un extremo de relación: una clase nueva (por su sitio), una que ya estaba o cualquier otro objeto."""
    if "c" in x:
        c = x["c"]
        if x["nueva"] or not c.get("caja"):
            w, _ = caja_estimada(c); p = c.get("pos") or (0, 0)
            return p[0] + w / 2
        return c["caja"][0] + c["caja"][2] / 2
    o = x["o"]
    return o["caja"][0] + o["caja"][2] / 2 if o.get("caja") else 0.0


def _colocar(plan, d, pistas=()):
    """Sitio para las clases y notas nuevas sin encimar lo que hay (las cajas reales salen de lo que hay en pantalla).
    Las hijas (herencia, realización) van debajo de su padre, una al lado de otra; lo demás, a la derecha de la clase
    con la que se relaciona o, si no, debajo de todo lo que hay. `pistas`: las relaciones de la solución de un ejercicio
    (no se dibujan, pero las clases se colocan como quedarán cuando la persona las dibuje)."""
    quitados = {c["id"] for c in plan["quitadas"]["clases"]}
    ocupado = [c["caja"] for c in d["clases"] if c["id"] not in quitados] + [n["caja"] for n in d.get("notas", [])]
    sitio = {}                                         # nombre normalizado → caja (x, y, w, h)
    for c in d["clases"]:
        if c["id"] not in quitados: sitio[du._norm((plan["modificar"].get(c["id"]) or (None, c))[1]["nombre"])] = c["caja"]
    fondo = max([o[1] + o[3] for o in ocupado], default=-1) + 3 if ocupado else 2
    izquierda = min([o[0] for o in ocupado], default=2) if ocupado else 2

    def libre(x, y, w, h): return not any(_choca((x, y, w, h), o) for o in ocupado)

    def buscar_hueco(cands, w, h, paso_x):
        for x, y in cands:
            for i in range(25):
                xx = x + i * paso_x
                if xx >= -2 and libre(xx, y, w, h): return xx, y
        y = fondo
        while True:
            for i in range(12):
                xx = izquierda + i * 6
                if libre(xx, y, w, h): return xx, y
            y += 6

    padres = {}                                        # hija → padre (herencia o realización)
    otras = {}
    for r in list(plan["relaciones"]) + list(pistas):
        if r["tipo"] in ("herencia", "realizacion"): padres.setdefault(du._norm(r["de"]), du._norm(r["a"]))
        otras.setdefault(du._norm(r["de"]), []).append(du._norm(r["a"])); otras.setdefault(du._norm(r["a"]), []).append(du._norm(r["de"]))
    pendientes = list(plan["nuevas"])
    for vuelta in range(len(pendientes) + 1):           # primero las que tienen a su padre (o a alguien) ya colocado
        quedan = []
        for c in pendientes:
            k = du._norm(c["nombre"]); w, h = caja_estimada(c)
            if c.get("pos"): x, y = c["pos"]
            else:
                p = padres.get(k)
                hijas = [h2 for h2, p2 in padres.items() if p2 == k and h2 in sitio]
                vecinos = [v for v in otras.get(k, []) if v in sitio]
                if p in sitio:
                    P = sitio[p]; x, y = buscar_hueco([(P[0], P[1] + P[3] + 3)], w, h, w + 2)
                elif hijas:
                    H = sitio[hijas[0]]; x, y = buscar_hueco([(H[0], H[1] - h - 3)], w, h, w + 2)
                elif vecinos:
                    V = sitio[vecinos[0]]
                    x, y = buscar_hueco([(V[0] + V[2] + 5, V[1]), (V[0], V[1] + V[3] + 3), (V[0] - w - 5, V[1])], w, h, 2)
                elif vuelta < len(pendientes) and (p or otras.get(k)):
                    quedan.append(c); continue                # esperar a que se coloque su pariente
                else:
                    x, y = buscar_hueco([], w, h, 0)
            c["pos"] = (round(x, 2), round(y, 2)); sitio[k] = (x, y, w, h); ocupado.append((x, y, w, h))
        pendientes = quedan
        if not pendientes: break
    for nt in plan["notas"]:
        w, h = du.medidas_nota(nt["texto"])
        if not nt.get("pos"):
            j = nt.pop("_junto", None)
            J = sitio.get(du._norm(j["c"]["nombre"])) if j else None
            nt["pos"] = buscar_hueco([(J[0] + J[2] + 3, J[1])] if J else [], w, h, 2)
        nt.pop("_junto", None)
        ocupado.append((*nt["pos"], w, h))
    plan["_sitio"] = sitio
    for r in plan["relaciones"]:                       # puntos aproximados (el plugin los pega a las cajas reales)
        A, B = sitio.get(du._norm(r["de"]), (0, 0, 4, 4)), sitio.get(du._norm(r["a"]), (0, 0, 4, 4))
        ini, fin = (B, A) if du.TIPOS_REL[r["tipo"]]["inicio_es_a"] else (A, B)
        r["puntos"] = (du.punto_conexion(ini, fin)[1], du.punto_conexion(fin, ini)[1])


def _cuantas(n, uno, varios): return f"{n} {uno if n == 1 else varios}"


def _y(partes): return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def resumen(plan, donde, ejercicio):
    """(lo que quiere hacer, lo que hizo) para la tarjeta."""
    c = plan["cuenta"]; quiere, hizo = [], []
    def parte(presente, pasado, resto): quiere.append(presente + resto); hizo.append(pasado + resto)
    def contar(d, alias):
        cuenta = {}
        for kk, v in d.items(): cuenta[alias.get(kk, kk)] = cuenta.get(alias.get(kk, kk), 0) + v
        return [_cuantas(v, *do.NOMBRES.get(kk, (kk, kk + "s"))) for kk, v in cuenta.items()]
    nuevos = contar(c.get("nuevos", {}), {"crear": "libre"})
    if c["clases"]: nuevos.insert(0, _cuantas(c["clases"], "clase", "clases"))
    if nuevos: parte("crear", "creé", " " + _y(nuevos))
    if c["relaciones"]: parte("dibujar" if not nuevos else "unir con", "dibujé" if not nuevos else "uní con", " " + _cuantas(c["relaciones"], "relación", "relaciones"))
    if c["notas"]: parte("poner", "puse", " " + _cuantas(c["notas"], "nota", "notas"))
    if c["cambia"]: parte("cambiar", "cambié", " " + _y([f"«{x}»" for x in c["cambia"]]))
    if c["quita"]: parte("quitar", "quité", " " + _y([f"«{x}»" for x in c["quita"]]))
    if c["quita_rel"]: parte("quitar", "quité", " " + _cuantas(c["quita_rel"], "relación", "relaciones"))
    lineas = contar(c.get("nuevas_lineas", {}), {"conectar": "linea", "interfaz_ofrecida": "interfaz", "interfaz_requerida": "interfaz"})
    if lineas: parte("dibujar", "dibujé", " " + _y(lineas))
    if ejercicio: parte("dejarte", "te dejé", " un ejercicio")
    if not quiere: quiere, hizo = ["hacer los cambios"], ["hice los cambios"]
    return _y(quiere) + donde[0], _y(hizo) + donde[1]


# ---------- Las propuestas y el ejercicio del tutor, con un Dia en vivo ----------
class Cambios:
    """Propuestas del tutor sobre Dia. `dia` es el DiaEnVivo del panel (orden(texto), modo); `rutas` dice
    dónde están los diagramas: {"mio": Path, "leccion": Path, "tutor": carpeta de los diagramas del tutor}."""

    def __init__(self, dia, rutas):
        self.dia, self.rutas = dia, rutas
        self.propuestas, self.ejercicio, self.num = {}, None, 0
        self.tmp = Path(tempfile.mkdtemp(prefix="dia-tutor-"))
        self._version = None

    # ----- utilidades -----
    def orden(self, texto): return self.dia.orden(texto)

    def plugin_al_dia(self):
        """¿El Dia abierto tiene el plugin que sabe aplicar cambios? (uno viejo responde «orden desconocida»)."""
        if self.dia.modo != "plugin": return False
        if self._version is None:
            r = self.orden("version")
            m = re.match(r"ok version (\d+)", r)
            self._version = int(m.group(1)) if m else 0
        return self._version >= VERSION_PLUGIN

    def _ruta_de(self, diag, reservar=None):
        if diag == "mio": return self.rutas["mio"]
        if diag == "leccion": return self.rutas["leccion"]
        if diag == "nuevo": return reservar
        return self.rutas["tutor"] / diag

    def _nombre_nuevo(self, ejercicio):
        base = "ejercicio" if ejercicio else "ejemplo"
        usados = {p["ruta"].name for p in self.propuestas.values() if p.get("ruta")}
        self.rutas["tutor"].mkdir(parents=True, exist_ok=True)
        for i in range(1, 1000):
            r = self.rutas["tutor"] / f"{base}_{i}.dia"
            if not r.exists() and r.name not in usados: return r
        raise ValueError("hay demasiados diagramas del tutor en la carpeta tutor/")

    def abiertos(self):
        """Nombres de archivo de las pestañas abiertas en Dia (con el plugin)."""
        if self.dia.modo != "plugin": return []
        r = self.orden("ventanas")
        if not r.rstrip().endswith("ok ventanas"): return []
        return [Path(l[2:].strip()).name for l in r.splitlines() if not l.startswith("ok")]

    def leer_pantalla(self, ruta):
        """Lo que hay EN PANTALLA en esa pestaña (aunque no se haya guardado): orden «copia» del plugin.
        Si no se puede, lo guardado."""
        if self.plugin_al_dia() and ruta.name in self.abiertos():
            copia = self.tmp / f"copia_{time.time_ns()}.dia"
            r = self.orden(f'@{ruta.name} copia "{copia}"')
            if r.startswith("ok"):
                try: return du.leer(copia)
                finally:
                    for f in (copia, Path(str(copia) + "~")):
                        try: f.unlink()
                        except OSError: pass
        return du.leer(ruta) if ruta.exists() else {"clases": [], "relaciones": [], "notas": [], "otros": []}

    def modificado(self, nombre):
        if self.dia.modo != "plugin": return False
        try: return self.orden(f"@{nombre} modificado").startswith("si")
        except Exception: return False

    def _tarjeta(self, pid):
        p = self.propuestas[pid]
        return {k: p[k] for k in ("id", "estado", "resumen", "para", "hoja", "nueva", "avisos", "notas", "detalle", "ejercicio", "mensaje")}

    # ----- preparar: la tarjeta de permiso (no cambia nada) -----
    def preparar(self, prop, paso_turno=False):
        """Revisa la propuesta contra lo que hay en Dia y arma su tarjeta. Lanza ValueError si no se puede usar."""
        self.num += 1; pid = f"p{self.num}"
        diag = prop["diagrama"]
        ruta = self._nombre_nuevo(bool(prop.get("ejercicio"))) if diag == "nuevo" else self._ruta_de(diag)
        if diag not in ("nuevo", "mio", "leccion") and not ruta.exists():
            raise ValueError(f"no hay un diagrama tuyo «{diag}» (los que creaste están en la carpeta tutor/)")
        d = {"clases": [], "relaciones": [], "notas": [], "otros": []} if diag == "nuevo" else self.leer_pantalla(ruta)
        plan = planear(prop, d, pid)
        avisos, notas = [], []
        if diag == "mio":
            avisos.append("Cambia tu diagrama (mi_diagrama.dia): quedará con cambios sin guardar; guárdalo (Ctrl+S) si te sirve.")
            if paso_turno: avisos.append("Es el diagrama de tu «Tu turno»: Comprobar revisará también lo que añada el tutor.")
        suyas = [c["nombre"] for c in plan["quitadas"]["clases"] if not c.get("tag")] + \
                [v["nombre"] for v, _ in plan["modificar"].values() if not v.get("tag")]
        if suyas and diag != "leccion": avisos.append("Toca clases que hiciste tú: " + ", ".join(f"«{s}»" for s in suyas))
        if diag != "nuevo" and self.modificado(ruta.name):
            avisos.append("Tienes cambios sin guardar en Dia en ese diagrama: lo del tutor se suma a ellos (Deshacer quita solo lo del tutor).")
        if diag == "leccion": notas.append("Es el ejemplo de la lección: al cambiar de paso se rehace y lo añadido se pierde.")
        if diag == "nuevo": notas.append("Se abre como pestaña nueva en tu Dia (se guarda en la carpeta tutor/ del curso).")
        if not self.plugin_al_dia():
            avisos.append("Tu Dia no tiene la versión nueva del plugin: para aplicarlo, cierra Dia y vuelve a abrir el panel."
                          if self.dia.modo == "plugin" else "Dia va sin el plugin (modo de respaldo): así no puedo cambiarlo en vivo.")
        donde = {"nuevo": (f" en un diagrama nuevo («{ruta.name}»)", f" en un diagrama nuevo («{ruta.name}»)"),
                 "mio": (" en tu diagrama", " en tu diagrama"), "leccion": (" en el ejemplo de la lección", " en el ejemplo de la lección")
                 }.get(diag, (f" en «{ruta.name}»", f" en «{ruta.name}»"))
        quiere, hizo = resumen(plan, donde, prop.get("ejercicio"))
        detalle = plan["detalle"][:40]
        if prop.get("ejercicio"): detalle.append(f"Ejercicio «{prop['ejercicio']['titulo']}»: lo revisas con Comprobar en la pestaña Lección")
        self.propuestas[pid] = {"id": pid, "estado": "pendiente", "resumen": quiere, "hecho": hizo, "para": prop.get("para", ""),
                                "hoja": ruta.name, "nueva": diag == "nuevo", "avisos": avisos, "notas": notas, "detalle": detalle,
                                "ejercicio": prop["ejercicio"]["titulo"] if prop.get("ejercicio") else "", "mensaje": "",
                                "prop": prop, "ruta": ruta, "diag": diag}
        return self._tarjeta(pid)

    # ----- aplicar -----
    def _ordenes_plan(self, nombre, plan, pid):
        """Manda el plan al plugin (reemplazar, quitar, anadir) y cierra la transacción. Devuelve los errores."""
        errores = []
        for k, (oid, (vieja, nueva)) in enumerate(plan["modificar"].items()):
            f = self.tmp / f"{pid}_mod{k}.dia"; du.escribir_para_anadir(f, [dict(nueva, tag=vieja.get("tag"))])
            r = self.orden(f'@{nombre} reemplazar id:{oid} "{f}"')
            if not r.startswith("ok"): errores.append(r)
        plan["antes_poner"] = []
        for o in plan.get("poner_antes", []):          # cambios de propiedades de lo que ya estaba (por id, antes de quitar nada)
            if errores: break
            r = self.orden(f"@{nombre} {o}")
            if not r.startswith("antes") and not r.startswith("ok"): errores.append(r)
            else: plan["antes_poner"].append((o.split('"')[1], [tuple(l.split("\t")[1:3]) for l in r.splitlines() if l.startswith("antes\t")]))
        if plan["quitar"] and not errores:
            r = self.orden(f"@{nombre} quitar " + " ".join(f"id:{i}" for i in plan["quitar"]))
            if not r.startswith("ok") or "falta" in r: errores.append(r)
        if (plan["nuevas"] or plan["relaciones"] or plan["notas"] or plan.get("extra") or plan.get("fondo")) and not errores:
            f = self.tmp / f"{pid}_nuevo.dia"
            du.escribir_para_anadir(f, plan["nuevas"], plan["relaciones"], plan["notas"], extra=plan.get("extra", []), fondo=plan.get("fondo", []))
            r = self.orden(f'@{nombre} anadir "{f}"')
            if "ok anadidos" not in r: errores.append(r)
        for o in plan.get("poner", []):                # propiedades del modo libre en lo recién creado
            if errores: break
            r = self.orden(f"@{nombre} {o}")
            if "ok puesto" not in r: errores.append(r)
        r = self.orden(f"@{nombre} transaccion")
        self._ultima_tp = r.split()[-1] if r.startswith("ok transaccion") else ""
        return errores

    def aplicar(self, pid):
        """Aplica la propuesta (la persona pulsó Aplicar). Si algo falla, deja todo como estaba."""
        p = self.propuestas[pid]
        if p["estado"] != "pendiente": return self._tarjeta(pid)
        if not self.plugin_al_dia():
            p.update(estado="error", mensaje="No puedo cambiar Dia en vivo: " + ("cierra Dia y vuelve a abrir el panel (hace falta el plugin nuevo)."
                                                                             if self.dia.modo == "plugin" else "Dia va sin el plugin."))
            return self._tarjeta(pid)
        ruta, prop, nombre = p["ruta"], p["prop"], p["ruta"].name
        creada = p["diag"] == "nuevo"
        if creada:
            if ruta.exists(): ruta = p["ruta"] = self._nombre_nuevo(bool(prop.get("ejercicio"))); nombre = ruta.name
            du.escribir(ruta, [])
            r = self.orden(f'abrir "{ruta}"')
            if not r.startswith("ok"):
                try: ruta.unlink()
                except OSError: pass
                p.update(estado="error", mensaje=f"No pude abrir el diagrama nuevo en Dia ({r[:120]})."); return self._tarjeta(pid)
        elif nombre not in self.abiertos():
            p.update(estado="error", mensaje=f"«{nombre}» no está abierto en Dia."); return self._tarjeta(pid)
        antes = self.leer_pantalla(ruta)
        try:
            plan = planear(prop, antes, pid)
            if plan.get("medir"):                          # tamaño real de lo nuevo (Dia lo calcula al leerlo) para colocarlo bien
                f = self.tmp / f"{pid}_medir.dia"; du.escribir_para_anadir(f, extra=plan["medir"])
                r = self.orden(f'medir "{f}"')
                medidas = {}
                for l in r.splitlines():
                    q = l.split("\t")
                    if q[0] == "medida" and len(q) >= 7 and q[1]:
                        try: medidas[q[1]] = tuple(float(v) for v in q[3:7])
                        except ValueError: pass
                if medidas: plan = planear(prop, antes, pid, medidas)
        except ValueError as e:
            if creada: self._cerrar_y_borrar(ruta)
            p.update(estado="error", mensaje=f"Ya no se puede aplicar: {e}"); return self._tarjeta(pid)
        errores = self._ordenes_plan(nombre, plan, pid)
        if errores:
            self.orden(f"@{nombre} deshacer_ultimo {self._ultima_tp}")
            if creada: self._cerrar_y_borrar(ruta)
            p.update(estado="error", mensaje=f"No pude hacerlo en Dia ({errores[0].splitlines()[-1][:140]}). Dejé todo como estaba.")
            return self._tarjeta(pid)
        if creada: self.orden(f"@{nombre} guardar")
        self.orden(f"@{nombre} activar")
        if creada: self.orden("accion ViewShowall")        # «accion» va a la pestaña activa: la que se acaba de poner al frente
        despues = self.leer_pantalla(ruta)
        mensaje = f"Hecho: {p['hecho']}."
        if not creada: mensaje += " Lo puedes deshacer aquí o con Ctrl+Z en Dia."
        if p["diag"] == "mio": mensaje += " Tu diagrama tiene cambios sin guardar: guárdalo (Ctrl+S) si te sirve."
        if prop.get("ejercicio"):
            self.ejercicio = {"id": pid, "ruta": ruta, "ej": prop["ejercicio"], "revision": None, "huella": None}
        p.update(estado="aplicada", mensaje=mensaje, plan=plan, antes=antes, despues=despues, creada=creada, tp=self._ultima_tp,
                 hash=hashlib.sha256(ruta.read_bytes()).hexdigest() if creada else None)
        return self._tarjeta(pid)

    def rechazar(self, pid):
        p = self.propuestas[pid]
        if p["estado"] == "pendiente": p.update(estado="rechazada", mensaje="No se aplicó.")
        return self._tarjeta(pid)

    # ----- deshacer -----
    def _cerrar_y_borrar(self, ruta):
        if ruta.name in self.abiertos(): self.orden(f"@{ruta.name} cerrar forzar")
        for f in (ruta, Path(str(ruta) + "~")):
            try: f.unlink()
            except OSError: pass

    def deshacer(self, pid, forzar=False):
        """Quita lo que puso el tutor y devuelve lo que cambió (Ctrl+Z de Dia también sirve).
        - Diagrama nuevo: se cierra su pestaña y se borra. Si la persona lo cambió, primero pregunta (estado «confirmar»).
        - Diagrama que ya estaba: si lo del tutor es lo último que se hizo en Dia, se deshace igual que con Ctrl+Z
          (y si no se hizo nada más, vuelve a quedar como guardado). Si no, se quita solo lo del tutor que siga
          como lo dejó: lo que la persona cambió después no se toca y la tarjeta lo dice."""
        p = self.propuestas[pid]
        if p["estado"] not in ("aplicada", "confirmar"): return self._tarjeta(pid)
        ruta, nombre = p["ruta"], p["ruta"].name
        quita_ej = self.ejercicio and self.ejercicio["id"] == pid
        if p["creada"]:
            abierto = nombre in self.abiertos()
            cambiado = (abierto and self.modificado(nombre)) or (ruta.exists() and hashlib.sha256(ruta.read_bytes()).hexdigest() != p["hash"])
            if cambiado and not forzar:
                p.update(estado="confirmar", mensaje=f"Cambiaste «{nombre}» después de aplicar. Si deshaces, se cierra y se borra, con lo tuyo.")
                return self._tarjeta(pid)
            self._cerrar_y_borrar(ruta)
            if quita_ej: self.ejercicio = None
            p.update(estado="deshecha", mensaje=f"Deshecho: cerré y borré «{nombre}»."); return self._tarjeta(pid)
        if nombre not in self.abiertos():
            p.update(estado="deshecha", mensaje=f"«{nombre}» ya no está abierto en Dia: no había nada que deshacer."); return self._tarjeta(pid)
        r = self.orden(f"@{nombre} deshacer_ultimo {p['tp']}") if p.get("tp") else ""
        if r.startswith("ok deshecho"):
            if quita_ej: self.ejercicio = None
            p.update(estado="deshecha", mensaje="Deshecho: todo quedó como estaba" + (" (como lo guardaste)." if r.endswith("guardado") else "."))
            return self._tarjeta(pid)
        plan, despues = p["plan"], p["despues"]
        ahora = self.leer_pantalla(ruta)
        todos = lambda x: x["clases"] + x["relaciones"] + x["notas"] + x.get("objetos", []) + x.get("lineas", [])
        tags_ahora = {o.get("tag"): o for o in todos(ahora) if o.get("tag")}
        tags_despues = {o.get("tag"): o for o in todos(despues) if o.get("tag")}
        nuevas = [t for t in plan["tags"] + plan.get("extra_tags", []) if t in tags_ahora]
        nuevas = list(dict.fromkeys(nuevas))
        cambiadas = [tags_ahora[t]["nombre"] for t in nuevas if t in tags_despues and "atributos" in tags_ahora[t]
                     and firma(tags_ahora[t]) != firma(tags_despues[t])]
        pegadas = [r2 for r2 in ahora["relaciones"] if not r2.get("tag") and any(
            tags_ahora.get(t, {}).get("id") in (r2.get("de_id"), r2.get("a_id")) for t in nuevas if "atributos" in tags_ahora.get(t, {}))]
        if (cambiadas or pegadas) and not forzar:
            que = ([f"cambiaste {_y([f'«{c}»' for c in cambiadas])}"] if cambiadas else []) + \
                  ([f"pegaste {_cuantas(len(pegadas), 'relación tuya', 'relaciones tuyas')} a lo del tutor"] if pegadas else [])
            p.update(estado="confirmar", mensaje=f"Después de aplicar {_y(que)}. Si deshaces, se quita igual lo que creó el tutor"
                                                 + (" y tus relaciones quedan sueltas." if pegadas else "."))
            return self._tarjeta(pid)
        errores, sin_tocar = [], []
        por_nombre = {du._norm(c["nombre"]): c for c in ahora["clases"]}
        for k, (oid, (vieja, nueva)) in enumerate(plan["modificar"].items()):
            actual = por_nombre.get(du._norm(nueva["nombre"]))
            despues_c = next((c for c in despues["clases"] if du._norm(c["nombre"]) == du._norm(nueva["nombre"])), None)
            if actual and firma(actual) == firma(vieja): continue           # ya estaba como antes (¿Ctrl+Z?)
            if not actual or not despues_c or firma(actual) != firma(despues_c): sin_tocar.append(nueva["nombre"]); continue
            f = self.tmp / f"{pid}_volver{k}.dia"; du.escribir_para_anadir(f, [dict(vieja, tag=vieja.get("tag"))])
            r = self.orden(f'@{nombre} reemplazar id:{actual["id"]} "{f}"')
            if not r.startswith("ok"): errores.append(r)
        if nuevas:
            r = self.orden(f"@{nombre} quitar " + " ".join(f'"tag:{t}"' for t in nuevas))
            if not r.startswith("ok"): errores.append(r)
        for ref, previos in reversed(plan.get("antes_poner", [])):     # lo que se cambió con «poner» vuelve a como estaba
            if previos:
                r = self.orden(f"@{nombre} " + do.comando_poner(ref if not ref.startswith("id:") else ref, previos))
                if "ok puesto" not in r: sin_tocar.append(ref)
        q = plan["quitadas"]
        if q.get("objetos"):
            xs = [x["xml"] for x in q["objetos"] if x.get("xml")]
            if xs:
                f = self.tmp / f"{pid}_devolver_obj.dia"; du.escribir_para_anadir(f, extra=xs)
                r = self.orden(f'@{nombre} anadir "{f}"')
                if "ok anadidos" not in r: errores.append(r)
        if q["clases"] or q["relaciones"]:
            vivas = {du._norm(c["nombre"]) for c in self.leer_pantalla(ruta)["clases"]}
            clases = [dict(c, pos=c["caja"][:2]) for c in q["clases"] if du._norm(c["nombre"]) not in vivas]
            nombres_ids = {c["id"]: c["nombre"] for c in p["antes"]["clases"]}
            rels = []
            for r2 in q["relaciones"]:
                de, a = nombres_ids.get(r2.get("de_id")), nombres_ids.get(r2.get("a_id"))
                if not de or not a: continue
                todas = vivas | {du._norm(c["nombre"]) for c in clases}
                if du._norm(de) not in todas or du._norm(a) not in todas: continue
                rels.append(dict(r2, ref_de=f"clase:{de}#{r2.get('punto_de')}" if r2.get("punto_de") else f"clase:{de}",
                                 ref_a=f"clase:{a}#{r2.get('punto_a')}" if r2.get("punto_a") else f"clase:{a}"))
            if clases or rels:
                f = self.tmp / f"{pid}_devolver.dia"; du.escribir_para_anadir(f, clases, rels)
                r = self.orden(f'@{nombre} anadir "{f}"')
                if "ok anadidos" not in r: errores.append(r)
        self.orden(f"@{nombre} transaccion")
        if quita_ej: self.ejercicio = None
        if errores: msg = f"Deshice lo que pude; algo falló en Dia ({errores[0].splitlines()[-1][:120]})."
        elif sin_tocar: msg = f"Deshecho, menos {_y([f'«{s}»' for s in sin_tocar])}, que cambiaste después: lo dejé como está."
        elif not nuevas and not plan["modificar"] and not q["clases"] and not q["relaciones"] and not q.get("objetos") \
                and not any(v for _, v in plan.get("antes_poner", [])): msg = "Ya estaba deshecho (¿Ctrl+Z en Dia?)."
        else: msg = "Deshecho: quité lo del tutor y devolví lo que había cambiado."
        p.update(estado="deshecha", mensaje=msg)
        return self._tarjeta(pid)

    # ----- el ejercicio del tutor: Comprobar sin IA, sobre lo GUARDADO -----
    def estado_ejercicio(self):
        ej = self.ejercicio
        if not ej: return None
        rev = ej.get("revision") or {"estado": "pendiente", "ok": 0, "total": 0, "mensaje": ej["ej"]["al_empezar"]}
        return {"id": ej["id"], "hoja": ej["ruta"].name, "rango": ej["ej"]["titulo"], "titulo": ej["ej"]["titulo"], "revision": rev}

    def comprobar_ejercicio(self):
        """(revisión o None, aviso). Si el diagrama tiene cambios sin guardar, pide guardar antes."""
        ej = self.ejercicio
        if not ej: return None, ""
        if not ej["ruta"].exists():
            self.ejercicio = None; return None, f"El diagrama «{ej['ruta'].name}» ya no está: quité el ejercicio."
        if self.modificado(ej["ruta"].name):
            return None, f"Tienes cambios sin guardar en «{ej['ruta'].name}»: guarda (Ctrl+S) y vuelve a pulsar Comprobar."
        try: d = du.leer(ej["ruta"])
        except Exception: return None, "No pude leer el diagrama (quizá se estaba guardando). Vuelve a pulsar Comprobar."
        ej["revision"] = du.revisar_varios(d, ej["ej"]); ej["huella"] = ej["ruta"].stat().st_mtime_ns
        return ej["revision"], ""

    def ir_ejercicio(self):
        ej = self.ejercicio
        if not ej: return False
        if ej["ruta"].name not in self.abiertos():
            if not ej["ruta"].exists(): return False
            self.orden(f'abrir "{ej["ruta"]}"')
        return self.orden(f"@{ej['ruta'].name} activar").startswith("ok")

    def quitar_ejercicio(self): self.ejercicio = None

    def vigilar_ejercicio(self):
        """True si se guardó algo en el diagrama del ejercicio después de comprobar (el resultado ya no está al día)."""
        ej = self.ejercicio
        if not ej or not ej.get("revision") or ej["revision"].get("viejo"): return False
        try: h = ej["ruta"].stat().st_mtime_ns
        except FileNotFoundError: return False
        if h != ej["huella"]:
            ej["revision"] = dict(ej["revision"], viejo=True); return True
        return False

    def contexto(self):
        """Para el tutor: los diagramas que creó y su ejercicio (con la revisión de lo guardado ahora)."""
        partes = []
        if self.ejercicio:
            ej = self.ejercicio
            try: rev = du.revisar_varios(du.leer(ej["ruta"]), ej["ej"])
            except Exception: rev = None
            esp = "; ".join([f"clase {c['nombre']}" + (f" ({', '.join(du.linea_atributo(a) for a in c.get('atributos') or [])}"
                                                        f"{'; ' if c.get('atributos') and c.get('metodos') else ''}"
                                                        f"{', '.join(du.linea_metodo(m) for m in c.get('metodos') or [])})"
                                                        if c.get("atributos") or c.get("metodos") else "") for c in ej["ej"]["clases"]]
                            + [du.frase_relacion(r) for r in ej["ej"]["relaciones"]] + ([dp.frase_esperada(ej["ej"])] if dp.frase_esperada(ej["ej"]) else []))
            partes.append(f"Ejercicio que armaste en «{ej['ruta'].name}» (se revisa con Comprobar en la pestaña Lección): «{ej['ej']['titulo']}». "
                          f"Solución esperada (no la reveles entera): {esp}." + (f" Revisión de lo guardado ahora: {rev['mensaje']} ({rev['ok']} de {rev['total']} bien)" if rev else ""))
        return partes

    def borrar_temporales(self):
        try:
            for f in self.tmp.iterdir(): f.unlink()
            self.tmp.rmdir()
        except OSError: pass


REGLAS_ACCIONES = """También puedes CREAR y CAMBIAR diagramas en Dia cuando te lo pida («hazme un ejemplo», «créalo en mi diagrama», «ponme un ejercicio»)
o cuando de verdad le ayude. El panel le muestra un resumen y SOLO se aplica si pulsa «Aplicar» (luego puede deshacerlo):
no digas que ya lo hiciste; di «te propongo…» o «pulsa Aplicar». En el «Tu turno» NO le hagas su clase salvo que lo pida explícitamente.
Al final (después de <marcas> si lo hay), UN solo bloque en una línea:
<acciones>{"para": "un ejemplo de herencia", "diagrama": "nuevo", "cambios": [{"clase": "Animal", "abstracta": true, "atributos": ["-nombre: String"], "metodos": ["+hacerSonido(): void {abstract}"]}, {"clase": "Perro", "metodos": ["+hacerSonido(): void"]}, {"relacion": "herencia", "de": "Perro", "a": "Animal"}]}</acciones>
- "diagrama": "nuevo" (por defecto: pestaña nueva en su Dia; para ejemplos y ejercicios tuyos) · "mio" (mi_diagrama.dia, SOLO si te lo pide) ·
  "leccion" (el ejemplo del paso; se pierde al cambiar de paso) · o uno tuyo de antes, como "ejemplo_1.dia" (los ves en [Estado actual]).
- "cambios" (en orden; nombres de clase de una palabra, como en el diagrama):
  {"clase": "Curso", "atributos": ["-codigo: String"], "metodos": ["+getNota(): float", "+inscribir(e: Estudiante): void"], "abstracta": false, "estereotipo": ""} ·
  {"interfaz": "Volador", "metodos": ["+volar(): void"]} · {"modificar": "Estudiante", "agregar": ["-edad: int"], "quitar": ["promedio"], "nombre": "Alumno", "abstracta": true}
  (o "atributos"/"metodos" para dar la lista entera) · {"quitar_clase": "X"} (quita también sus relaciones) ·
  {"relacion": TIPO, "de": "A", "a": "B", "nombre": "inscribe", "mult": ["*", "1..*"], "direccion": "a"} · {"quitar_relacion": TIPO, "de": "A", "a": "B"} ·
  {"nota": "texto corto", "junto_a": "Clase"}. Opcional "pos": [x, y] en cm; si no, se colocan solas sin encimar nada.
  TIPO: "asociacion", "herencia", "realizacion", "dependencia", "agregacion", "composicion". El símbolo va SIEMPRE junto a «a»:
  herencia de hija a padre · realizacion de la clase a la interfaz · dependencia de la que usa a la usada · asociacion de A a B
  ("direccion": "a" pone la flecha en B; "mult" = [junto a de, junto a a]) · agregacion y composicion de la PARTE al TODO
  (el rombo va en el todo; también vale {"relacion": "composicion", "todo": "Casa", "parte": "Habitacion"}). Solo asociación,
  agregación y composición llevan "mult". Miembros en notación UML: "-nombre: String", "+metodo(x: int): void", con " {abstract}" o " {static}".
  Máximo 30 cambios y 12 clases. Si la clase ya existe, usa "modificar".
  Para cursos con convenciones: "dentro_de": "capa" (con {"paquete": "capa"} antes; {"paquete": "awt", "dentro_de": "java"} los anida) deja la clase hija de
  verdad de su paquete · {"clase": "JFrame", "biblioteca": true} (vacía) · {"clase": "Show", "enumerada": ["A", "B"]} · en asociacion, agregacion y composicion,
  "nombre": "tiene" es el verbo y "lectura": "a"|"de" el triángulo de lectura hacia esa clase ("direccion" = flecha de navegabilidad). Si el curso lo pide,
  los parámetros van solo con el tipo ("+f(String, int): void") y los nombres de clase sin negrita: el panel lo aplica solo.
- "ejercicio" (opcional, con su solución ESCONDIDA para que lo revise Comprobar sin IA; normalmente en "diagrama": "nuevo", donde
  "cambios" pone lo que le das hecho): {"titulo": "Herencia de animales", "clases": [{"nombre": "Perro", "atributos": ["-raza: String"],
  "metodos": ["+ladrar(): void"]}, {"nombre": "Animal", "abstracta": true}], "relaciones": [{"tipo": "herencia", "de": "Perro", "a": "Animal"},
  {"tipo": "asociacion", "de": "Dueño", "a": "Perro", "mult": ["1", "*"]}], "al_empezar": "qué tiene que hacer", "al_terminar": "…"}.
  Si una clase no trae "atributos" ni "metodos", solo se mira que exista. No le des la solución: explícale en el texto qué tiene que hacer
  (y que guarde con Ctrl+S y pulse Comprobar en la pestaña Lección).
- Lo que creas lleva «[la creaste tú, el tutor]» en el [Estado actual]. A veces llega [Del panel] con lo que hizo con tu propuesta.
- Si no hace falta crear ni cambiar nada, omite el bloque.
OTROS DIAGRAMAS, en el mismo bloque (los objetos se nombran por su texto, o por su «#O7» del [Estado actual]; se colocan solos y las líneas quedan pegadas):
- Casos de uso: {"sistema": "Cajero"} · {"actor": "Cliente"} ("lado": "derecha" para los secundarios) · {"caso": "Sacar dinero"} (va en el único sistema;
  si hay varios, "dentro_de") · {"relacion": "asociacion"|"include"|"extend"|"herencia", "de", "a"} (include: del base al incluido; extend: del que extiende al base).
- Secuencia: {"participante": ":Cajero"} (de izquierda a derecha; "como_actor": true) y los mensajes EN ORDEN:
  {"mensaje": "validar(pin)", "de": ":Cajero", "a": ":Banco", "tipo": "sincrono"|"asincrono"|"retorno"|"crear"|"destruir"} (de = a: a sí mismo).
- Actividades: {"inicial": "inicio"} {"accion": "Leer PIN"} {"decision": "d1", "pregunta": "¿PIN correcto?"} {"fusion": "f1"} {"bifurcacion": "b1"}
  {"union": "u1"} {"final": "fin"} · {"flujo": "", "de": "Leer PIN", "a": "d1", "guarda": "sí"} · calles: {"calle": "Cliente"} y "en_calle" en cada nodo.
- Estados: {"estado": "Esperando", "entrada": "", "hacer": "", "salida": ""} · {"compuesto": "Activo"} y "dentro_de": "Activo" en los suyos ·
  {"transicion": "evento", "de": "A", "a": "B", "guarda": "x > 0", "efecto": "avisar()"} (inicial y final como en actividades).
- Componentes y despliegue: {"componente": "Pagos", "dentro_de": "Servidor"} {"interfaz_ofrecida": "IPago", "de": "Pagos"} {"interfaz_requerida": "IBanco", "de": "Pagos"}
  {"nodo": "Servidor", "estereotipo": "device"} {"artefacto": "app.war", "dentro_de": "Servidor"}; entre ellos, relaciones dependencia o asociacion.
- Paquetes y objetos: {"paquete": "Modelo"} (clases dentro con "dentro_de"), {"relacion": "dependencia", "de": "Vista", "a": "Modelo", "estereotipo": "import"},
  {"objeto": "ana: Alumno", "valores": ["edad = 20"]} y sus enlaces con "relacion": "asociacion".
- MODO LIBRE (flujo, entidad-relación, redes o cualquier otro objeto de Dia, por su nombre exacto de tipo):
  {"crear": "Flowchart - Box", "texto": "Inicio", "nombre": "i1", "props": {"fill_colour": "verde_claro"}} · {"conectar": "Standard - Line", "de": "i1", "a": "x",
  "texto": "sí", "props": {"end_arrow": "triangulo"}} (Standard - ZigZagLine: en ángulo recto; ER: "ER - Participation") · {"cambiar": "Inicio", "texto": "Empezar",
  "props": {...}, "pos": [x, y], "ancho": 5, "alto": 2} · {"eliminar": "Inicio"} (cambiar y eliminar valen para cualquier objeto que no sea clase).
  Tipos: Flowchart - Terminal/Box/Diamond/Parallelogram/Document/Ellipse, ER - Entity/Relationship/Attribute, Network - ..., Standard - Box/Ellipse/Text.
  Props: text, fill_colour, line_colour, line_width, line_style (continua, discontinua, punteada), start_arrow/end_arrow (ninguna, flecha, triangulo, rombo),
  corner_radius, text_colour, text_height. Colores: #rrggbb o rojo, verde, azul, amarillo, gris, naranja (y _claro). Si una no existe, el panel te dice cuáles hay.
- Ejercicio de estos diagramas (además de "clases"/"relaciones"): "objetos": [{"tipo": "actor", "nombre": "Cliente"}, {"tipo": "decision"}],
  "conexiones": [{"tipo": "include"|"asociacion"|"flujo"|"transicion"|…, "de": "A", "a": "B", "guarda": "sí", "evento": "abrir"}]
  (los nodos sin nombre son inicio, fin, decision, decision2...), "mensajes": [{"de": ":A", "a": ":B", "texto": "pedir()", "tipo": "retorno"}] en orden."""


def referencia_libre(pregunta, contexto):
    """[Referencia de Dia] para el tutor, solo si viene al caso: las propiedades de los tipos de Dia del modo libre que
    salen en el diagrama o en la pregunta (diagrama de flujo, entidad-relación, red...). Así REGLAS no crece."""
    texto = f"{pregunta}\n{contexto}".lower()
    cat = do.catalogo()
    tipos = [t for t in cat if t.lower() in texto and not t.startswith("UML - ")]
    temas = {"flujo": "Flowchart - ", "flowchart": "Flowchart - ", "entidad": "ER - ", "e-r": "ER - ", "red ": "Network - ", "redes": "Network - ",
             "network": "Network - ", "cisco": "Cisco - ", "bpmn": "BPMN - ", "circuito": "Circuit - ", "base de datos": "Database - "}
    for clave, pre in temas.items():
        if clave in texto and not any(t.startswith(pre) for t in tipos):
            tipos += [t for t in cat if t.startswith(pre)][:12]
    if not tipos: return ""
    lineas = ["[Referencia de Dia, modo libre] Tipos y sus propiedades (las que se pueden poner en \"props\"):"]
    for t in tipos[:14]:
        ps = [p["n"] for p in cat[t]["props"] if p["f"] & 1 and p["t"] in do.PROP_TIPOS_OK and p["n"] not in do.FUERA]
        lineas.append(f"- {t}: " + ", ".join(ps[:14]) + ("" if do.texto_principal(t) else " (sin texto)"))
    return "\n".join(lineas)
