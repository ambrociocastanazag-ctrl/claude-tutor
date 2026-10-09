"""Reglas de estilo UML para «Comprobar», pensadas para cualquier curso de diagramas de clases con convenciones.

Las enciende el `curso.json` con `convenciones`:
    {"nombre_negrita": false,         # el nombre de toda clase va sin negrita (si está en negrita, error)
     "parametros": "solo_tipo",       # o "nombre_tipo": cómo se escriben los parámetros (K1)
     "estricto": true,                # compara EXACTO (mayúsculas) y revisa las reglas de estilo de abajo
     "numeros": {"atributo": 3},      # opcional: cambia el número de convención que sale en cada mensaje (NUMEROS)
     "codigos": {"parametros": "K1"}} # opcional: cambia las etiquetas de las reglas propias del curso (CODIGOS)
y lo que pida cada clase o relación del «Tu turno» (`dentro_de`, `biblioteca`, `enumerada`, `nombre`, `lectura`, `direccion`).

Cada mensaje lleva el número de la convención y dice DÓNDE se arregla en Dia 0.97.2 (nombres de pestañas y campos tal como salen
en el Dia en español). `revisar` (clases y paquetes) y `relaciones` (las ya emparejadas con la esperada) devuelven puntos
{"ok", "objetivo", "texto"}; dia_uml.revisar_varios los suma a los suyos. Los puntos de las reglas de estilo solo salen cuando
fallan (✘); los que pide el «Tu turno» salen también cuando están bien (✔)."""
import re

import dia_uml as du

NUMEROS = {            # numeración de las convenciones del curso (el PDF «Convenciones Java y UML»)
    "clase": 1, "metodo": 2, "atributo": 3, "paquete": 5, "coleccion": 14, "tostring": 17, "negrita": 18, "abstracto": 19,
    "enumerada": 20, "interfaz": 21, "multiplicidad": 23, "navegabilidad": 24, "lectura": 25, "linea": 26, "interfaz_pura": 29,
}
CODIGOS = {"parametros": "K1", "biblioteca": "K3"}      # reglas propias del curso (no del PDF)


class Reglas:
    def __init__(self, conv):
        self.conv = conv or {}
        self.estricto = bool(self.conv.get("estricto"))
        self.n = {**NUMEROS, **(self.conv.get("numeros") or {})}
        self.k = {**CODIGOS, **(self.conv.get("codigos") or {})}

    def num(self, clave): return f"convención {self.n[clave]}"

    def igual(self, dado, esperado):
        """Nombres iguales: sin distinguir mayúsculas ni espacios, y exactos con `estricto`."""
        if dado is None: return False
        return (dado.strip() == esperado.strip()) if self.estricto else du._norm(dado) == du._norm(esperado)


def _p(ok, objetivo, texto): return {"ok": ok, "objetivo": objetivo, "texto": texto}


def _juntos(c, e):
    """Para «Selecciona la clase y el paquete juntos»: el texto de cómo se hace en Dia."""
    return ("pon la clase sobre el paquete, selecciona los dos (clic en uno y Ctrl+clic en el otro) y elige Objetos → Padre (Ctrl+K); "
            "así, al mover el paquete, se mueve lo de dentro")


def _ruta_esperada(e, rutas_dado):
    """La ruta (tupla) de la capa que pide `e` (una clase o capa esperada): la que ya resolvió el ejercicio contra sus capas
    («dentro_ruta») o, si no, la que nombra su «dentro_de» entre las capas del diagrama. (ruta o None, texto del error o None)."""
    if e.get("dentro_ruta"): return tuple(e["dentro_ruta"]), None
    try: return du.resolver_ruta(e["dentro_de"], rutas_dado), None
    except ValueError as x: return None, str(x)


def _padre(r, x, ruta_esperada, nombre_x, tipo_x, error=None, ref=""):
    """Punto de «x está dentro de la capa esperada» (x: clase o capa leída con dia_uml.leer; sus rutas, con la ruta completa).
    ruta_esperada None = no hay esa capa en el diagrama."""
    actual = x.get("ruta_padre") if "ruta_padre" in x else (tuple(x["ruta"][:-1]) or None if x.get("ruta") else None)
    if error: return _p(False, nombre_x, f"{tipo_x} «{nombre_x}»: {error}")
    if ruta_esperada is None:
        return _p(False, nombre_x, f"No existe la capa «{ref}» para meter {tipo_x.lower()} «{nombre_x}» (Paquete grande, hoja UML).")
    esp = du.mostrar_ruta(ruta_esperada)
    if actual and du.clave_ruta(actual) == du.clave_ruta(ruta_esperada):
        return _p(True, nombre_x, f"{tipo_x} «{nombre_x}» está en {esp}.")
    if actual:
        return _p(False, nombre_x, f"{tipo_x} «{nombre_x}» debería estar en {esp}, y está en {du.mostrar_ruta(actual)}: "
                                   f"suéltala con Objetos → Orfandar (Ctrl+Mayús+K) y luego {_juntos(x, esp)}.")
    return _p(False, nombre_x, f"{tipo_x} «{nombre_x}» debería estar en {esp}, y no está dentro de ninguna capa: {_juntos(x, esp)}.")


def _tipo_exacto(r, dado, esperado, que, objetivo, puntos):
    """Los tipos van exactos en Java («string» ≠ «String»); las colecciones, entre corchetes (14)."""
    if not r.estricto or not esperado or not dado: return
    a, b = re.sub(r"\s+", "", dado), re.sub(r"\s+", "", esperado)
    if a != b and du._norm(a) == du._norm(b):
        puntos.append(_p(False, objetivo, f"El tipo «{dado}» ({que}) debería ser «{esperado}»: en Java los tipos van exactos"
                                          + (f"; la multiplicidad va entre corchetes ({r.num('coleccion')})" if "[" in esperado else "") + "."))


def revisar(d, ej, conv=None):
    """Puntos de las reglas sobre las CLASES y PAQUETES esperados por `ej` (con `conv` de curso.json)."""
    r = Reglas(conv)
    puntos = []
    por = {du._norm(c["nombre"]): c for c in d["clases"]}
    paquetes = [o for o in d.get("objetos", []) if o["kind"] == "paquete"]            # capas del diagrama (con su ruta completa)
    rutas_dado = [o["ruta"] for o in paquetes]
    # negrita del nombre (18): todas las clases del diagrama
    if r.conv.get("nombre_negrita") is False:
        for c in d["clases"]:
            if c.get("negrita"):
                fila = "Clase abstracta" if c.get("abstracta") else "Nombre de la clase"
                puntos.append(_p(False, c["nombre"], f"El nombre de «{c['nombre']}» está en negrita; va sin negrita ({r.num('negrita')}): doble clic en la clase → "
                                                     f"pestaña «Estilo» → fila «{fila}» → en su segundo desplegable cambia «Bold» por «Normal» → Aceptar."))
    for e in ej.get("clases", []):
        c = por.get(du._norm(e["nombre"]))
        if not c: continue
        nc = c["nombre"]
        if r.estricto and nc != e["nombre"]:
            puntos.append(_p(False, nc, f"El nombre de la clase «{nc}» debería ser «{e['nombre']}»: las clases van en UpperCamelCase ({r.num('clase')}) "
                                        f"(doble clic en la clase → campo «Nombre de la clase»)."))
        if e.get("dentro_de"):
            ruta, error = _ruta_esperada(e, rutas_dado)
            puntos.append(_padre(r, c, ruta, nc, "La clase", error, e["dentro_de"]))
        if e.get("biblioteca"):
            vacia = not c["atributos"] and not c["metodos"]
            puntos.append(_p(vacia, nc, f"«{nc}» es de la biblioteca de Java: va vacía, sin atributos ni métodos ({r.k['biblioteca']})."
                                        if not vacia else f"«{nc}» va vacía (biblioteca de Java)."))
        if e.get("enumerada") is not None: puntos += _enumerada(r, c, e)
        elif e.get("interfaz") or du.es_interfaz(c):
            if r.estricto and du.es_interfaz(c) and c["atributos"]:
                puntos.append(_p(False, nc, f"La interfaz «{nc}» tiene atributos; una interfaz es una clase abstracta pura y no los lleva ({r.num('interfaz_pura')}) "
                                            f"(doble clic → pestaña «Atributos» → Eliminar)."))
        if r.estricto: puntos += _miembros_exactos(r, c, e)
        # toString (17): toda clase del proyecto lo lleva (no las de la biblioteca, ni las enumeradas ni las interfaces)
        if r.estricto and not e.get("biblioteca") and e.get("enumerada") is None and not e.get("interfaz") and not du.es_interfaz(c):
            ts = next((m for m in c["metodos"] if du._norm(m["nombre"]) == "tostring"), None)
            if not ts:
                puntos.append(_p(False, nc, f"Falta +toString(): String en «{nc}» ({r.num('tostring')}): doble clic → pestaña «Operaciones» → Nuevo."))
    # capas esperadas (objetos de tipo paquete): por su ruta completa (dos capas pueden llamarse igual si su padre es distinto)
    for o in ej.get("objetos", []):
        if o.get("tipo") != "paquete": continue
        ruta = tuple(o.get("ruta") or (o["nombre"],))
        x = next((q for q in paquetes if du.clave_ruta(q["ruta"]) == du.clave_ruta(ruta)), None)
        if x is None:
            otras = [q for q in paquetes if du._norm(q["ruta"][-1]) == du._norm(ruta[-1])]
            puntos.append(_p(False, ruta[-1], f"Falta la capa «{du.mostrar_ruta(ruta)}»" + (f" (hay una «{ruta[-1]}» en {', '.join(du.mostrar_ruta(q['ruta']) for q in otras)}; "
                                                                                       f"la capa «{ruta[-1]}» debe estar en {du.mostrar_ruta(ruta[:-1]) or 'la raíz'})" if otras else "") + "."))
            continue
        puntos.append(_p(True, x["texto"], f"Capa «{du.mostrar_ruta(ruta)}»."))
        if r.estricto and any(a != b for a, b in zip(x["ruta"], ruta)):
            malo = next(a for a, b in zip(x["ruta"], ruta) if a != b)
            puntos.append(_p(False, x["texto"], f"El nombre de la capa «{malo}» debería ser «{next(b for a, b in zip(x['ruta'], ruta) if a != b)}»: las capas van en lowerCamelCase "
                                                f"({r.num('paquete')}) (doble clic en el paquete → campo «Nombre»)."))
    return puntos


def _miembros_exactos(r, c, e):
    """Con `estricto`: los miembros esperados que la persona escribió con otras mayúsculas, otro tipo exacto, static o abstract distinto."""
    puntos, nc = [], c["nombre"]
    busca = lambda lista, nombre: next((x for x in lista if du._norm(x["nombre"]) == du._norm(nombre)), None)
    for a in e.get("atributos") or []:
        x = busca(c["atributos"], a["nombre"])
        if not x: continue
        obj = f"{nc}.{x['nombre']}"
        if x["nombre"] != a["nombre"]:
            puntos.append(_p(False, obj, f"El atributo «{x['nombre']}» debería ser «{a['nombre']}»: los atributos van en lowerCamelCase ({r.num('atributo')}) "
                                         f"(doble clic en la clase → pestaña «Atributos» → campo «Nombre»)."))
        _tipo_exacto(r, x.get("tipo"), a.get("tipo"), f"atributo {a['nombre']}", obj, puntos)
        if bool(x.get("estatico")) != bool(a.get("estatico")):
            puntos.append(_p(False, obj, _estatico(x["nombre"], bool(a.get("estatico")), "Atributos")))
    usados = set()
    for m in e.get("metodos") or []:
        x, _ = du.buscar_metodo(c["metodos"], m, e.get("metodos") or [], {}, usados)
        if not x: continue
        usados.add(id(x))
        obj = f"{nc}.{x['nombre']}"
        if x["nombre"] != m["nombre"]:
            puntos.append(_p(False, obj, f"El método «{x['nombre']}» debería ser «{m['nombre']}»: los métodos van en lowerCamelCase ({r.num('metodo')}) "
                                         f"(doble clic en la clase → pestaña «Operaciones» → campo «Nombre»)."))
        _tipo_exacto(r, x.get("tipo"), m.get("tipo"), f"retorno de {m['nombre']}", obj, puntos)
        for pe, pd in zip(m.get("params", []), x.get("params", [])):
            _tipo_exacto(r, pd.get("tipo"), pe.get("tipo"), f"parámetro de {m['nombre']}", obj, puntos)
        if bool(x.get("estatico")) != bool(m.get("estatico")):
            puntos.append(_p(False, obj, _estatico(x["nombre"], bool(m.get("estatico")), "Operaciones")))
        if bool(x.get("abstracto")) != bool(m.get("abstracto")):
            puntos.append(_p(False, obj, f"«{x['nombre']}» " + ("debería ser abstracto (en cursiva)" if m.get("abstracto") else "no debería ser abstracto")
                             + f" ({r.num('abstracto')}): pestaña «Operaciones» → selecciónalo → «Tipo de herencia» → "
                             + ("«Abstracta»." if m.get("abstracto") else "otra opción que no sea «Abstracta».")))
    return puntos


def _estatico(nombre, debe, pestana):
    if debe: return f"«{nombre}» es static: va subrayado (doble clic en la clase → pestaña «{pestana}» → selecciónalo → casilla «Vista de clase»)."
    return f"«{nombre}» no es static: no va subrayado (pestaña «{pestana}» → selecciónalo → quita la casilla «Vista de clase»)."


def _enumerada(r, c, e):
    """Convención 20: sin estereotipo, sin compartimento de métodos y los valores como atributos sin visibilidad ni tipo."""
    puntos, nc, valores = [], c["nombre"], e["enumerada"]
    dados = {du._norm(a["nombre"]): a for a in c["atributos"]}
    for v in valores:
        a = dados.get(du._norm(v))
        if not a: puntos.append(_p(False, nc, f"Falta el valor «{v}» en la enumerada «{nc}» (pestaña «Atributos» → Nuevo; en «Nombre», solo el valor).")); continue
        puntos.append(_p(r.igual(a["nombre"], v), f"{nc}.{a['nombre']}", f"Valor «{a['nombre']}» de «{nc}»." if r.igual(a["nombre"], v)
                         else f"El valor «{a['nombre']}» debería ser «{v}» (como en el código)."))
        if r.estricto and a["vis"] != "~":
            puntos.append(_p(False, f"{nc}.{a['nombre']}", f"El valor «{a['nombre']}» lleva el signo «{a['vis']}»: en la enumerada los valores van sin visibilidad "
                                                           f"({r.num('enumerada')}) (pestaña «Atributos» → selecciónalo → «Visibilidad» → «Implementación»)."))
        if r.estricto and a.get("tipo"):
            puntos.append(_p(False, f"{nc}.{a['nombre']}", f"El valor «{a['nombre']}» tiene tipo «{a['tipo']}»: los valores no llevan tipo ({r.num('enumerada')}) "
                                                           f"(pestaña «Atributos» → campo «Tipo» vacío)."))
    if r.estricto:
        sobran = [a["nombre"] for a in c["atributos"] if du._norm(a["nombre"]) not in {du._norm(v) for v in valores}]
        if sobran: puntos.append(_p(False, nc, "Sobra en la enumerada: " + ", ".join(f"«{s}»" for s in sobran) + "."))
        if c.get("estereotipo"):
            puntos.append(_p(False, nc, f"«{nc}» tiene el estereotipo «{c['estereotipo']}»: la enumerada va sin estereotipo ({r.num('enumerada')}) "
                                        f"(doble clic en la clase → pestaña «Clase» → campo «Estereotipo» vacío)."))
        if c["metodos"] or c["ver"][1]:
            puntos.append(_p(False, nc, f"«{nc}» muestra el compartimento de métodos: la enumerada no lo lleva ({r.num('enumerada')}) "
                                        f"(doble clic en la clase → pestaña «Clase» → quita la casilla «Operaciones visibles»)."))
    return puntos


# ---------- Relaciones ----------
def _nombre_lado(rel, lado): return rel.get(lado) or "(suelta)"


def relaciones(pares, conv=None):
    """Puntos de las reglas sobre relaciones. `pares` = [(esperada, leida)] de las relaciones ya emparejadas (mismo tipo y sentido)
    por dia_uml.revisar_varios. La esperada puede traer nombre (el verbo), lectura ("a"/"de"), direccion y mult."""
    r = Reglas(conv)
    puntos = []
    for e, rel in pares:
        de, a = e["de"], e["a"]
        # la línea puede estar trazada desde la otra clase: lo que cuenta es EN QUÉ CLASE está la flecha, el rombo y el triángulo,
        # no por qué punta se empezó. `dir_rel` es la flecha de navegabilidad vista desde el sentido de lo esperado (de → a).
        invertida = du._norm(rel.get("de") or "") != du._norm(de) and du._norm(rel.get("de") or "") == du._norm(a)
        dir_rel = rel.get("direccion") or ""
        if invertida: dir_rel = {"a": "de", "de": "a"}.get(dir_rel, dir_rel)
        etiq = f"{du.TIPOS_REL[e['tipo']]['nombre']} entre «{de}» y «{a}»"
        asoc = e["tipo"] in ("asociacion", "agregacion", "composicion")
        if e.get("nombre"):                                                # el verbo que pide el «Tu turno»
            ok = r.igual(rel.get("nombre"), e["nombre"])
            if asoc: why = f"({r.num('lectura')}): doble clic en la línea → campo «Nombre»"
            else: why = f"({r.num('linea')}): doble clic en la línea → campo «Nombre»"
            puntos.append(_p(ok, de, f"La {etiq} lleva el verbo «{e['nombre']}»." if ok else
                             f"La {etiq} " + (f"lleva el verbo «{rel.get('nombre')}»; debería ser «{e['nombre']}» {why}." if rel.get("nombre")
                                                else f"no tiene verbo; debería llevar «{e['nombre']}» {why}.")))
        if asoc and e.get("lectura") in ("a", "de"):                       # el triángulo de lectura
            objetivo = a if e["lectura"] == "a" else de
            if rel.get("lectura_hacia") and du._norm(rel["lectura_hacia"]) == du._norm(objetivo):
                puntos.append(_p(True, de, f"El triángulo de lectura de la {etiq} apunta hacia «{objetivo}»."))
            elif not rel.get("ver_lectura"):
                puntos.append(_p(False, de, f"La {etiq} no tiene triángulo de lectura ({r.num('lectura')}): doble clic en la línea → casilla «Mostrar dirección» "
                                            f"(y el verbo en «Nombre»)."))
            else:
                puntos.append(_p(False, de, f"El triángulo de lectura de la {etiq} apunta hacia «{rel.get('lectura_hacia') or '(?)'}»; debería apuntar hacia «{objetivo}» "
                                            f"({r.num('lectura')}): doble clic en la línea → «Dirección» → cambia «De A a B» por «De B a A» (o al revés). "
                                            f"En la agregación y la composición eso mueve también el rombo: si pasa, da la vuelta a la línea."))
        if asoc and e.get("direccion") is not None and "direccion" in e:   # la flecha de navegabilidad que pide el «Tu turno»
            quiere = e["direccion"]
            ok = dir_rel == quiere
            texto = (f"La flecha de navegabilidad de la {etiq} está bien." if ok else
                     f"La {etiq} no tiene flecha de navegabilidad ({r.num('navegabilidad')}): doble clic en la línea → «Mostrar flecha» del lado de «{a if quiere == 'a' else de}»."
                     if not dir_rel else
                     f"La flecha de navegabilidad de la {etiq} apunta a «{ {'a': a, 'de': de, 'ambas': 'los dos'}.get(dir_rel) }»; "
                     f"debería {'apuntar a «' + (a if quiere == 'a' else de) + '»' if quiere in ('a', 'de') else 'estar en los dos lados' if quiere == 'ambas' else 'no estar'} "
                     f"({r.num('navegabilidad')}): doble clic en la línea → «Mostrar flecha» (Side A / Side B).")
            puntos.append(_p(ok, de, texto))
        if r.estricto and asoc:                                           # reglas de estilo de toda asociación, agregación y composición
            mult = list(rel.get("mult") or ["", ""])
            if not rel.get("de") or not rel.get("a"): continue
            for lado, m in ((rel["de"], mult[0]), (rel["a"], mult[1])):
                if not m.strip():
                    puntos.append(_p(False, de, f"La {etiq} no tiene multiplicidad junto a «{lado}» ({r.num('multiplicidad')}): doble clic en la línea → «Multiplicidad» "
                                                f"del lado de «{lado}» (Side A / Side B)."))
            if not dir_rel:
                if not (e.get("direccion") is not None and "direccion" in e):
                    puntos.append(_p(False, de, f"La {etiq} no tiene flecha de navegabilidad ({r.num('navegabilidad')}): doble clic en la línea → «Mostrar flecha» "
                                                f"del lado de la clase que guarda la otra."))
            if not (rel.get("nombre") and rel.get("ver_lectura")):
                puntos.append(_p(False, de, f"La {etiq} no tiene verbo o triángulo de lectura ({r.num('lectura')}): doble clic en la línea → «Nombre» (el verbo) "
                                            f"y casilla «Mostrar dirección»."))
    return puntos
