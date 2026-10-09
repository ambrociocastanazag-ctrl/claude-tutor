"""Lo que el tutor puede crear en Dia además de clases: el resto de diagramas UML y el «modo libre».

Vocabulario del bloque <acciones> (cada cambio lleva UNA de estas claves; el texto del objeto es su nombre):
  casos de uso   {"actor": "Cliente", "lado": "izquierda"|"derecha"} · {"caso": "Sacar dinero", "dentro_de": "Cajero"} ·
                 {"sistema": "Cajero"} (límite) · relaciones con "relacion": asociacion, include, extend, herencia
  secuencia      {"participante": ":Cajero", "como_actor": false} ·
                 {"mensaje": "validar(pin)", "de": ":Cajero", "a": ":Banco", "tipo": "sincrono"|"asincrono"|"retorno"|"crear"|"destruir"}
  actividades    {"inicial": "inicio"} · {"final": "fin"} · {"accion": "Leer PIN", "en_calle": "Cliente"} ·
                 {"decision": "d1", "pregunta": "¿PIN correcto?"} · {"fusion": "m1"} · {"bifurcacion": "b1"} · {"union": "u1"} ·
                 {"calle": "Cliente"} · {"flujo": "", "de": "Leer PIN", "a": "d1", "guarda": "sí"}
  estados        {"estado": "Esperando", "entrada": "", "hacer": "", "salida": "", "dentro_de": "Activo"} · {"compuesto": "Activo"} ·
                 {"transicion": "evento", "de": "A", "a": "B", "guarda": "x > 0", "efecto": "avisar()"}
  componentes, despliegue, paquetes y objetos
                 {"componente": "Pagos", "dentro_de": "Servidor"} · {"interfaz_ofrecida": "IPago", "de": "Pagos"} ·
                 {"interfaz_requerida": "IBanco", "de": "Pagos"} · {"nodo": "Servidor", "estereotipo": "device"} ·
                 {"artefacto": "app.war", "dentro_de": "Servidor"} · {"paquete": "Modelo"} · {"objeto": "ana: Alumno", "valores": ["edad = 20"]}
  modo libre     {"crear": "Flowchart - Box", "texto": "Inicio", "nombre": "i1", "props": {"fill_colour": "#ffeecc"}} ·
                 {"conectar": "Standard - Line", "de": "i1", "a": "x", "props": {"end_arrow": "triangulo"}, "texto": "sí"} ·
                 {"cambiar": "Inicio", "texto": "Empezar", "props": {...}, "pos": [x, y], "ancho": 4, "alto": 2} · {"eliminar": "Inicio"}
Los objetos ya existentes se nombran por su texto o por «#O7» (el id que sale en el [Estado actual]).

`Contexto` lleva el plan de estos cambios junto al de las clases (cambios_dia.planear): registra los nombres, coloca todo
de forma legible según el tipo de diagrama (secuencia: participantes en fila y mensajes hacia abajo; actividades, estados
y modo libre: de arriba abajo por capas; casos de uso: actores a los lados y casos dentro del límite; contenedores con lo
de dentro) y escribe el XML desde las plantillas de Dia. `revisar(d, ej)` revisa los ejercicios sin IA."""
import itertools, re

import dia_uml as du
import dia_objetos as do

# ---------- Vocabulario ----------
ELEMENTOS = {   # clave del bloque → (tipo de Dia, familia, campos permitidos además de la clave y "pos")
    "actor": ("UML - Actor", "casos", {"lado"}),
    "caso": ("UML - Usecase", "casos", {"dentro_de"}),
    "sistema": ("Standard - Box", "casos", set()),
    "participante": ("UML - Object", "secuencia", {"como_actor"}),
    "inicial": ("UML - State Term", "flujo", {"en_calle", "dentro_de"}),
    "final": ("UML - State Term", "flujo", {"en_calle", "dentro_de"}),
    "accion": ("UML - Activity", "flujo", {"en_calle", "dentro_de"}),
    "decision": ("UML - Branch", "flujo", {"en_calle", "pregunta", "dentro_de"}),
    "fusion": ("UML - Branch", "flujo", {"en_calle", "dentro_de"}),
    "bifurcacion": ("UML - Fork", "flujo", {"en_calle", "dentro_de"}),
    "union": ("UML - Fork", "flujo", {"en_calle", "dentro_de"}),
    "calle": ("Standard - Box", "flujo", set()),
    "estado": ("UML - State", "flujo", {"entrada", "hacer", "salida", "dentro_de"}),
    "compuesto": ("Standard - Box", "flujo", {"dentro_de"}),
    "componente": ("UML - Component", "bloques", {"estereotipo", "dentro_de"}),
    "nodo": ("UML - Node", "bloques", {"estereotipo", "dentro_de"}),
    "artefacto": ("UML - Class", "bloques", {"dentro_de"}),
    "paquete": ("UML - LargePackage", "bloques", {"estereotipo", "dentro_de"}),
    "objeto": ("UML - Object", "bloques", {"valores", "dentro_de"}),
    "crear": (None, "libre", {"nombre", "texto", "props", "ancho", "alto", "dentro_de"}),
}
LINEAS = {      # clave → (tipo de Dia, campos)
    "mensaje": ("UML - Message", {"de", "a", "tipo", "despues_de", "antes_de"}),
    "flujo": ("UML - Transition", {"de", "a", "guarda"}),
    "transicion": ("UML - Transition", {"de", "a", "guarda", "efecto"}),
    "interfaz_ofrecida": ("UML - Component Feature", {"de"}),
    "interfaz_requerida": ("UML - Component Feature", {"de"}),
    "conectar": (None, {"de", "a", "props", "texto", "nombre"}),
}
OTRAS = {"cambiar": {"texto", "props", "pos", "ancho", "alto"}, "eliminar": set()}
CONTENEDORES = {"sistema", "compuesto", "paquete", "nodo", "calle"}
SIN_TEXTO = {"inicial", "final", "decision", "fusion", "bifurcacion", "union"}
MENSAJE_TIPO = {"sincrono": 0, "síncrono": 0, "llamada": 0, "asincrono": 3, "asíncrono": 3, "retorno": 4, "respuesta": 4,
                "crear": 1, "create": 1, "destruir": 2, "destroy": 2}
NOMBRE_TIPO_MSG = {0: "síncrono", 3: "asíncrono", 4: "de retorno", 1: "de creación «create»", 2: "de destrucción «destroy»", 6: "a sí mismo"}
S_FILA = 1.4          # separación entre mensajes (cm): también es la distancia entre los puntos de conexión de las líneas de vida


def claves(): return set(ELEMENTOS) | set(LINEAS) | set(OTRAS)


def _campos(a, permitidos, k):
    sobra = set(a) - permitidos
    if sobra: raise ValueError(f"cambio {k}: campos que no conozco: {', '.join(sorted(sobra))}")


def _txt(v, donde, largo=80, vacio=False):
    if v is None or isinstance(v, bool): v = ""
    if not isinstance(v, (str, int, float)): raise ValueError(f"{donde}: tiene que ser texto")
    v = str(v).replace("\\n", "\n").replace("\\", "/").strip()
    if not v and not vacio: raise ValueError(f"{donde}: está vacío")
    if len(v) > largo: raise ValueError(f"{donde}: demasiado largo (máximo {largo} caracteres)")
    return v


def _pos(v, k):
    if v is None: return None
    if not (isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, (int, float)) for x in v)) or not all(-50 <= x <= 300 for x in v):
        raise ValueError(f"cambio {k}: «pos» tiene que ser [x, y] en cm (entre -50 y 300)")
    return (float(v[0]), float(v[1]))


def _medida(v, k, nombre):
    if v is None: return None
    if not isinstance(v, (int, float)) or not 0.5 <= v <= 100: raise ValueError(f"cambio {k}: «{nombre}» es un número de cm (0,5 a 100)")
    return float(v)


def _props(tipo, v, k):
    if v is None: return []
    if not isinstance(v, dict): raise ValueError(f"cambio {k}: «props» es un objeto {{\"propiedad\": valor}}")
    if len(v) > 15: raise ValueError(f"cambio {k}: demasiadas propiedades")
    return [do.valor_prop(tipo, n, x, f"cambio {k}") for n, x in v.items()]


def validar(clave, a, k):
    """Valida un cambio de este vocabulario. Devuelve el cambio limpio (con "accion" = la clave)."""
    if clave in ELEMENTOS:
        tipo, fam, extra = ELEMENTOS[clave]
        _campos(a, {clave, "pos"} | extra, k)
        c = {"accion": clave, "familia": fam, "pos": _pos(a.get("pos"), k)}
        if clave == "crear":
            c["tipo"] = do.tipo_dia(a[clave], f"cambio {k}")
            if do.es_conector(c["tipo"]): raise ValueError(f"cambio {k}: «{c['tipo']}» es una línea: usa «conectar» con «de» y «a»")
            if any(p["t"] == "file" for p in do.catalogo()[c["tipo"]]["props"]): raise ValueError(f"cambio {k}: «{c['tipo']}» usa un archivo: no se puede crear desde aquí")
            c["texto"] = _txt(a.get("texto"), f"cambio {k}, texto", 300, True)
            c["nombre"] = _txt(a.get("nombre"), f"cambio {k}, nombre", 60, True) or c["texto"]
            if not c["nombre"]: raise ValueError(f"cambio {k}: un objeto sin texto necesita «nombre» para poder unirlo")
            if c["texto"] and not do.texto_principal(c["tipo"]): raise ValueError(f"cambio {k}: «{c['tipo']}» no lleva texto")
            c["props"] = _props(c["tipo"], a.get("props"), k)
            c["ancho"], c["alto"] = _medida(a.get("ancho"), k, "ancho"), _medida(a.get("alto"), k, "alto")
        else:
            c["tipo"] = tipo
            vacio = clave in SIN_TEXTO
            nombre = _txt(a[clave] if not isinstance(a[clave], bool) else "", f"cambio {k}, {clave}", 80, vacio)
            if clave == "inicial" and not nombre: nombre = "inicio"
            if clave == "final" and not nombre: nombre = "fin"
            if vacio and not nombre: raise ValueError(f"cambio {k}: ponle un nombre corto a la {clave} (p. ej. \"d1\") para poder unirla con flujos")
            c["nombre"] = nombre; c["texto"] = "" if vacio else nombre
            if "lado" in a:
                lado = _txt(a["lado"], f"cambio {k}, lado", 10).lower()
                if lado not in ("izquierda", "derecha"): raise ValueError(f"cambio {k}: «lado» es \"izquierda\" o \"derecha\"")
                c["lado"] = lado
            for f in ("entrada", "hacer", "salida", "pregunta", "estereotipo"):
                if f in a: c[f] = _txt(a[f], f"cambio {k}, {f}", 80, True)
            if "valores" in a:
                if not isinstance(a["valores"], list) or len(a["valores"]) > 12: raise ValueError(f"cambio {k}: «valores» es una lista de textos")
                c["valores"] = [_txt(x, f"cambio {k}, valores", 60) for x in a["valores"]]
            c["como_actor"] = bool(a.get("como_actor"))
        for f in ("dentro_de", "en_calle"):
            if a.get(f): c[f] = _txt(a[f], f"cambio {k}, {f}", 80)
        return c
    if clave in LINEAS:
        tipo, extra = LINEAS[clave]
        _campos(a, {clave} | extra, k)
        c = {"accion": clave, "tipo": tipo}
        if clave == "conectar":
            c["tipo"] = do.tipo_dia(a[clave] or "Standard - Line", f"cambio {k}")
            if not do.es_conector(c["tipo"]): raise ValueError(f"cambio {k}: «{c['tipo']}» no es una línea (prueba «Standard - Line» o «Standard - ZigZagLine»)")
            c["props"] = _props(c["tipo"], a.get("props"), k)
            c["texto"] = _txt(a.get("texto"), f"cambio {k}, texto", 60, True)
            c["nombre"] = _txt(a.get("nombre"), f"cambio {k}, nombre", 60, True)
        elif clave == "mensaje":
            c["texto"] = _txt(a[clave], f"cambio {k}, mensaje", 80, True)
            t = _txt(a.get("tipo") or "sincrono", f"cambio {k}, tipo", 20).lower()
            if t not in MENSAJE_TIPO: raise ValueError(f"cambio {k}: «tipo» del mensaje es sincrono, asincrono, retorno, crear o destruir")
            c["mtipo"] = MENSAJE_TIPO[t]
            for f in ("despues_de", "antes_de"):          # meterlo entre dos que ya están (si no, va al final)
                if a.get(f): c[f] = _txt(a[f], f"cambio {k}, {f}", 80)
            if c.get("despues_de") and c.get("antes_de"): raise ValueError(f"cambio {k}: usa «despues_de» o «antes_de», no los dos")
        elif clave in ("flujo", "transicion"):
            c["evento"] = _txt(a[clave] if isinstance(a[clave], str) and clave == "transicion" else "", f"cambio {k}", 80, True)
            c["guarda"] = _txt(a.get("guarda"), f"cambio {k}, guarda", 80, True).strip("[] ")
            c["efecto"] = _txt(a.get("efecto"), f"cambio {k}, efecto", 80, True).lstrip("/ ")
        else:
            c["texto"] = _txt(a[clave], f"cambio {k}, {clave}", 60)
        c["de"] = _txt(a.get("de"), f"cambio {k}, de", 80)
        if clave in ("interfaz_ofrecida", "interfaz_requerida"): c["a"] = None
        else:
            c["a"] = _txt(a.get("a"), f"cambio {k}, a", 80)
            if c["a"].lower() == c["de"].lower() and clave != "mensaje": raise ValueError(f"cambio {k}: una línea de un objeto a sí mismo no se puede dibujar aquí")
            if clave == "mensaje" and c["a"].lower() == c["de"].lower():
                if c["mtipo"] not in (0, 3): raise ValueError(f"cambio {k}: un mensaje a sí mismo es síncrono o asíncrono")
                c["mtipo"] = 6
        return c
    if clave == "cambiar":
        _campos(a, {"cambiar"} | OTRAS["cambiar"], k)
        c = {"accion": "cambiar", "ref": _txt(a["cambiar"], f"cambio {k}", 80), "texto": None if "texto" not in a else _txt(a["texto"], f"cambio {k}, texto", 300, True),
             "props_crudas": a.get("props") or {}, "pos": _pos(a.get("pos"), k), "ancho": _medida(a.get("ancho"), k, "ancho"), "alto": _medida(a.get("alto"), k, "alto")}
        if not isinstance(c["props_crudas"], dict): raise ValueError(f"cambio {k}: «props» es un objeto")
        if c["texto"] is None and not c["props_crudas"] and not c["pos"] and not c["ancho"] and not c["alto"]: raise ValueError(f"cambio {k}: «cambiar» no dice qué cambiar")
        return c
    if clave == "eliminar":
        _campos(a, {"eliminar"}, k)
        return {"accion": "eliminar", "ref": _txt(a["eliminar"], f"cambio {k}", 80)}
    raise ValueError(f"cambio {k}: no conozco «{clave}»")


def describir(c):
    """Una línea de «Ver los cambios» de la tarjeta."""
    acc = c["accion"]
    if acc == "crear": return f"Crear un «{c['tipo']}»" + (f" con el texto «{c['texto']}»" if c["texto"] else f" («{c['nombre']}»)")
    if acc == "conectar": return f"Unir «{c['de']}» con «{c['a']}» con una «{c['tipo']}»" + (f" («{c['texto']}»)" if c["texto"] else "")
    if acc == "cambiar":
        partes = ([f"texto «{c['texto']}»"] if c["texto"] is not None else []) + [f"{n} = {v}" for n, v in c["props_crudas"].items()] \
            + (["moverlo"] if c["pos"] else []) + (["cambiar su tamaño"] if c["ancho"] or c["alto"] else [])
        return f"Cambiar «{c['ref']}»: " + ", ".join(partes)
    if acc == "eliminar": return f"Quitar «{c['ref']}» (y las líneas pegadas a él)"
    if acc == "mensaje":
        donde = f" (después de «{c['despues_de']}»)" if c.get("despues_de") else f" (antes de «{c['antes_de']}»)" if c.get("antes_de") else ""
        return f"Mensaje {NOMBRE_TIPO_MSG[c['mtipo']]} de «{c['de']}» a «{c['a']}»" + (f": `{c['texto']}`" if c["texto"] and c["mtipo"] not in (1, 2) else "") + donde
    if acc in ("flujo", "transicion"):
        et = (c["evento"] + (f" [{c['guarda']}]" if c["guarda"] else "") + (f" / {c['efecto']}" if c["efecto"] else "")).strip()
        return f"{'Flujo' if acc == 'flujo' else 'Transición'} de «{c['de']}» a «{c['a']}»" + (f": `{et}`" if et else "")
    if acc in ("interfaz_ofrecida", "interfaz_requerida"): return f"Interfaz {'ofrecida' if acc.endswith('ofrecida') else 'requerida'} «{c['texto']}» en «{c['de']}»"
    nombre = do.NOMBRES.get(acc, (acc,))[0]
    extra = "".join([f" dentro de «{c['dentro_de']}»" if c.get("dentro_de") else "", f" (calle «{c['en_calle']}»)" if c.get("en_calle") else "",
                     f": «{c['pregunta']}»" if c.get("pregunta") else "", f" «{c['estereotipo']}»" if c.get("estereotipo") else ""])
    if acc in SIN_TEXTO: return f"Crear {nombre} «{c['nombre']}»{extra}"
    return f"Crear {nombre} «{c['texto']}»{extra}"


# ---------- Plan: nombres, colocación y XML ----------
def _n(s): return du._norm(s or "")


class Contexto:
    """Los cambios de este vocabulario dentro de un plan de cambios_dia.planear (que hace las clases)."""

    def __init__(self, d, plan, etiqueta, clases):
        self.d, self.plan, self.etiqueta, self.clases = d, plan, etiqueta, clases   # clases: el registro de cambios_dia
        self.reg, self.repetidos = {}, set()
        self.elems, self.lineas, self.cambiar, self.eliminar = [], [], [], []
        plan.setdefault("extra_tags", [])
        for o in d.get("objetos", []):
            if o["kind"] in ("rotulo", "linea_vida"): continue
            self._registrar(o, o.get("texto")); self._registrar(o, o.get("nombre")); self._registrar(o, "#" + o["id"], unico=True)
        for l in d.get("lineas", []) + d.get("relaciones", []): self._registrar(l, "#" + l["id"], unico=True)
        for c in d["clases"]: self._registrar(c, "#" + c["id"], unico=True)
        for nt in d.get("notas", []): self._registrar(nt, "#" + nt["id"], unico=True)

    def _registrar(self, o, nombre, unico=False, nueva=False):
        if not nombre: return
        k = _n(nombre)
        if k in self.reg and self.reg[k]["o"] is not o and not unico: self.repetidos.add(k)
        self.reg[k] = {"o": o, "nueva": nueva}

    def buscar(self, nombre, k, quien="objeto"):
        """El objeto (nuevo o que ya estaba) con ese texto o «#id». Las clases también valen."""
        kn = _n(nombre)
        if kn in self.repetidos: raise ValueError(f"cambio {k}: hay dos objetos «{nombre}»: usa su «#id» del [Estado actual]")
        x = self.reg.get(kn)
        if x: return x
        c = self.clases.get(kn)
        if c: return {"o": c["c"], "nueva": c["nueva"], "clase": True, "reg_clase": c}
        raise ValueError(f"cambio {k}: no hay ningún «{nombre}» en el diagrama")

    # ----- cada cambio -----
    def cambio(self, a, k):
        acc = a["accion"]
        if acc in ELEMENTOS:
            if _n(a["nombre"]) in self.reg or _n(a["nombre"]) in self.clases:
                raise ValueError(f"cambio {k}: ya hay algo llamado «{a['nombre']}» (usa otro nombre, o «cambiar»)")
            e = dict(a, tag=self.etiqueta(), k=k)
            self.elems.append(e); self._registrar(e, e["nombre"], nueva=True)
            if e.get("texto") and _n(e["texto"]) != _n(e["nombre"]): self._registrar(e, e["texto"], nueva=True)
            self.plan["cuenta"].setdefault("nuevos", {}).setdefault(acc, 0); self.plan["cuenta"]["nuevos"][acc] += 1
        elif acc in LINEAS:
            l = dict(a, tag=self.etiqueta(), k=k)
            l["_de"] = self.buscar(a["de"], k)
            l["_a"] = self.buscar(a["a"], k) if a.get("a") else None
            if acc == "mensaje":
                for lado in ("_de", "_a"):
                    o = l[lado]["o"]
                    if l[lado]["nueva"] and o.get("accion") != "participante" or not l[lado]["nueva"] and not (o.get("kind") == "participante" or o.get("vidas")):
                        raise ValueError(f"cambio {k}: «{a['de'] if lado == '_de' else a['a']}» no es un participante (crea antes {{\"participante\": ...}})")
            self.lineas.append(l)
            self.plan["cuenta"].setdefault("nuevas_lineas", {}).setdefault(acc, 0); self.plan["cuenta"]["nuevas_lineas"][acc] += 1
        elif acc == "cambiar":
            x = self.buscar(a["ref"], k)
            if x["nueva"]: raise ValueError(f"cambio {k}: «{a['ref']}» lo creas en esta misma propuesta: ponlo todo al crearlo")
            o = x["o"]; tipo = o.get("tipo") or "UML - Class"
            pares = []
            if a["texto"] is not None:
                tp = do.texto_principal(tipo) if tipo in do.catalogo() else None
                if not tp: raise ValueError(f"cambio {k}: «{a['ref']}» no tiene texto que cambiar")
                pares.append(do.valor_prop(tipo, tp, a["texto"], f"cambio {k}"))
            pares += [do.valor_prop(tipo, n, v, f"cambio {k}") for n, v in a["props_crudas"].items()]
            if a["pos"] or a["ancho"] or a["alto"]:
                ps = do.props_tipo(tipo) if tipo in do.catalogo() else {}
                if "elem_corner" not in ps: raise ValueError(f"cambio {k}: «{a['ref']}» no se puede mover ni cambiar de tamaño así")
                if a["pos"]:
                    x0, y0 = o["caja"][:2]
                    pares.append(("elem_corner", f"{a['pos'][0]!r},{a['pos'][1]!r}"))
                if a["ancho"]: pares.append(("elem_width", repr(a["ancho"])))
                if a["alto"]: pares.append(("elem_height", repr(a["alto"])))
            if o.get("tag"): pass
            self.cambiar.append({"id": o["id"], "pares": pares, "nombre": a["ref"], "tag": o.get("tag")})
            self.plan["cuenta"]["cambia"].append(a["ref"])
        elif acc == "eliminar":
            x = self.buscar(a["ref"], k)
            if x["nueva"]: raise ValueError(f"cambio {k}: «{a['ref']}» lo creas en esta misma propuesta")
            if x.get("clase"): raise ValueError(f"cambio {k}: para quitar una clase usa «quitar_clase»")
            o = x["o"]; ids = [o["id"]]
            if o.get("titulo_id"): ids.append(o["titulo_id"])
            for v in o.get("vidas", []): ids.append(v)
            for l in self.d.get("lineas", []) + self.d.get("relaciones", []):
                if l["id"] != o["id"] and ({l.get("de_id"), l.get("a_id")} & set(ids)): ids.append(l["id"])
            for i in ids:
                if i not in self.plan["quitar"]: self.plan["quitar"].append(i)
            self.plan["quitadas"].setdefault("objetos", []).append(o)
            self.plan["cuenta"]["quita"].append(nombre_de(o))
            for kk in [kk for kk, v in self.reg.items() if v["o"] is o]: del self.reg[kk]
        else: raise ValueError(f"cambio {k}: no sé hacer «{acc}»")

    # ----- referencias para el plugin (después de saber qué se quita) -----
    def ref(self, x, punto=None):
        if x["nueva"]: r = f"tag:{x['o']['tag']}"
        elif x.get("clase"):
            rc = x["reg_clase"]; mod = self.plan["modificar"].get(rc["id"])
            r = f"clase:{(mod or (None, rc['c']))[1]['nombre']}"
        else: r = f"id:{self.id_tras_quitar(x['o']['id'])}"
        return r + (punto or "")

    def id_tras_quitar(self, oid):
        m = re.match(r"O(\d+)$", oid or "")
        if not m: return oid
        n = int(m.group(1))
        quit = [int(q[1:]) for q in self.plan["quitar"] if re.match(r"O\d+$", str(q))]
        return f"O{n - sum(1 for q in quit if q < n)}"

    # ----- tamaños -----
    def tam(self, e, medidas):
        """(w, h) de la caja exterior de un elemento nuevo: medida por Dia si se pudo; si no, estimada."""
        if e.get("_tam"): return e["_tam"]
        if e["accion"] in ("bifurcacion", "union"): return (e.get("_ancho_barra", 4.0), 0.4)
        m = (medidas or {}).get(e["tag"])
        if m: return (m[2], m[3])
        t, n = e.get("texto") or "", len((e.get("texto") or "").split("\n")[0])
        acc = e["accion"]
        if acc == "actor": return (max(2.6, 0.48 * n + 0.4), 5.5)
        if acc == "caso": return (max(3.3, 0.5 * n + 1.6), 2.1 if n < 14 else 2.6)
        if acc in ("accion", "estado"):
            h = 1.9 + 0.8 * sum(1 for f in ("entrada", "hacer", "salida") if e.get(f))
            return (max(4.1, 0.5 * max([n] + [len(e.get(f) or "") + 7 for f in ("entrada", "hacer", "salida")]) + 1.0), h)
        if acc in ("inicial", "final"): return (1.1, 1.1)
        if acc in ("decision", "fusion"): return (2.15, 2.15)
        if acc in ("bifurcacion", "union"): return (e.get("_ancho_barra", 4.0), 0.4)
        if acc == "participante": return (max(2.6, 0.48 * n + 0.4), 5.5) if e.get("como_actor") else (max(2.0, 0.5 * n + 1.0), 1.9)
        if acc == "componente": return (max(4.1, 0.5 * n + 2.0), 3.6)
        if acc == "objeto": return (max(3.0, 0.5 * max([n] + [len(v) for v in e.get("valores", [])]) + 1.0), 1.9 + 0.8 * len(e.get("valores", [])))
        if acc == "artefacto": return (max(4.0, 0.62 * n + 1.4), 2.4)
        if acc == "crear":
            bb = do.caja_xml(do.nuevo(e["tipo"]))
            return (e.get("ancho") or max(bb[2], 0.45 * n + 1.2 if n else 0), e.get("alto") or bb[3])
        return (4.0, 2.0)

    # ----- cerrar: colocar y escribir -----
    def cerrar(self, medidas=None, pistas=()):
        """Coloca lo nuevo (sin encimar lo que hay) y deja en el plan: extra (XML de objetos y líneas), fondo (contenedores,
        que van detrás), poner (propiedades del modo libre y cambios con la orden «poner»), y los puntos de las relaciones."""
        if not (self.elems or self.lineas or self.cambiar): return
        self._insertar_mensajes()
        Colocador(self, medidas, pistas).colocar()
        fondo, extra, poner = [], [], []
        for e in self.elems:
            xs = xml_elemento(e)
            (fondo if e["accion"] in CONTENEDORES else extra).extend(xs)
            for n, v in e.get("props") or []: poner.append(do.comando_poner(f"tag:{e['tag']}", [(n, v)]))
        extra.extend(xml_vidas(self))                   # líneas de vida de la secuencia (antes que los mensajes)
        for l in self.lineas:
            extra.extend(xml_linea(self, l))
            for n, v in l.get("props") or []: poner.append(do.comando_poner(f"tag:{l['tag']}", [(n, v)]))
        self.plan["fondo"], self.plan["extra"], self.plan["poner"] = fondo, extra, poner
        self.plan["poner_antes"] = [do.comando_poner(f"id:{c['id']}", c["pares"]) for c in self.cambiar]
        self.plan["cambiar_gen"] = self.cambiar
        self.plan["extra_tags"] = [e["tag"] for e in self.elems] + [l["tag"] for l in self.lineas if l.get("tag")] + \
            [t for e in self.elems + self.lineas for t in (e.get("_tags_extra") or [])] + [v["tag"] for v in self.plan.get("vidas", [])]

    def _insertar_mensajes(self):
        """Mensajes con «despues_de» / «antes_de» que caen ENTRE dos que ya estaban: la secuencia se vuelve a trazar entera
        (se quitan los mensajes y las líneas de vida de antes y se dibujan otra vez, en el orden nuevo, con los participantes
        donde estaban). Si caen al final, se añaden como siempre."""
        nuevos = [l for l in self.lineas if l["accion"] == "mensaje"]
        if not any(l.get("despues_de") or l.get("antes_de") for l in nuevos): return
        d = self.d; por_id = d.get("_por_id", {})
        viejos = [m for m in do.mensajes_en_orden(d) if m["id"] not in self.plan["quitar"]]
        orden = [("viejo", m) for m in viejos]
        for l in nuevos:
            ancla = l.get("despues_de") or l.get("antes_de")
            if not ancla: orden.append(("nuevo", l)); continue
            i = next((k for k, x in enumerate(orden) if _igual_texto(x[1].get("texto") or "", ancla)), None)
            if i is None:
                raise ValueError(f"cambio {l['k']}: no hay un mensaje «{ancla}» para poner «{l.get('texto')}» {'después' if l.get('despues_de') else 'antes'}")
            orden.insert(i + 1 if l.get("despues_de") else i, ("nuevo", l))
        tipos = [t for t, _ in orden]
        if "viejo" not in tipos[tipos.index("nuevo"):]:
            return                                     # todo lo nuevo queda al final: se añade como siempre
        if any(m["extra"].get("mtipo") == 1 for m in viejos):
            raise ValueError("con mensajes «crear» en el diagrama, los mensajes nuevos solo pueden ir al final")

        def cabeza(lid):
            """El participante (su cabeza) de una línea de vida, subiendo por los tramos encadenados."""
            v = por_id.get(lid)
            for _ in range(20):
                if v is None or v.get("tipo") != "UML - Lifeline": break
                v = por_id.get(v.get("de")) if v.get("de") else None
            return v if v is not None and v.get("tipo") != "UML - Lifeline" else None

        lineas_msg = []
        for t, x in orden:
            if t == "nuevo": lineas_msg.append(x); continue
            a = cabeza(x.get("de_id")); b = a if x["extra"].get("mtipo") == 6 else cabeza(x.get("a_id"))
            if a is None or b is None:
                raise ValueError(f"no puedo meter un mensaje en medio: «{x.get('texto') or x['id']}» tiene un extremo suelto")
            lineas_msg.append({"accion": "mensaje", "tipo": "UML - Message", "texto": x.get("texto") or "", "mtipo": x["extra"].get("mtipo", 0),
                               "tag": x.get("tag") or "", "k": 0, "_de": {"o": a, "nueva": False}, "_a": {"o": b, "nueva": False}, "_copia": True})
        vidas = [o for o in d.get("objetos", []) if o.get("tipo") == "UML - Lifeline" and o["id"] not in self.plan["quitar"]]
        for o in viejos + vidas:
            self.plan["quitar"].append(o["id"])
        self.plan["quitadas"].setdefault("objetos", []).extend(viejos + vidas)
        self.lineas = lineas_msg + [l for l in self.lineas if l["accion"] != "mensaje"]
        self.retrazar = True

    def xml_medir(self):
        """Los elementos nuevos, sin colocar, para que Dia diga su tamaño real (orden «medir»)."""
        out = []
        for e in self.elems:
            if e["accion"] in CONTENEDORES: continue
            o = _objeto_base(e)
            out.append(do.a_texto(o, f"M{len(out)}"))
        return out


def nombre_de(o): return o.get("nombre") if "accion" in o else do.nombre_de_objeto(o) if "kind" in o else o.get("nombre", "")


# ---------- Colocar ----------
def _union(cajas):
    cajas = [c for c in cajas if c]
    if not cajas: return None
    x0 = min(c[0] for c in cajas); y0 = min(c[1] for c in cajas)
    return (x0, y0, max(c[0] + c[2] for c in cajas) - x0, max(c[1] + c[3] for c in cajas) - y0)


def capas(nodos, aristas):
    """Capa de cada nodo (de arriba abajo) por el camino más largo, sin contar las aristas que vuelven atrás (bucles)."""
    suc = {n: [] for n in nodos}
    for u, v in aristas:
        if u in suc and v in suc and u != v: suc[u].append(v)
    entra = {n: 0 for n in nodos}
    for u in nodos:
        for v in suc[u]: entra[v] += 1
    estado, atras = {}, set()
    def dfs(n):
        estado[n] = 1
        for v in suc[n]:
            if estado.get(v) == 1: atras.add((n, v))
            elif v not in estado: dfs(v)
        estado[n] = 2
    for n in [n for n in nodos if entra[n] == 0] + nodos:
        if n not in estado: dfs(n)
    capa = {n: 0 for n in nodos}
    for _ in range(len(nodos)):
        cambio = False
        for u in nodos:
            for v in suc[u]:
                if (u, v) not in atras and capa[v] < capa[u] + 1: capa[v] = capa[u] + 1; cambio = True
        if not cambio: break
    return capa, atras


def disponer(nodos, aristas, tam, gap_x=2.4, gap_y=2.0, columna=None):
    """Posición (x, y) de la esquina de cada nodo, por capas de arriba abajo, centrando cada nodo bajo sus padres.
    `columna`: {nodo: (x0, ancho)} si los nodos van en calles (columnas fijas)."""
    capa, atras = capas(nodos, aristas)
    padres = {n: [u for u, v in aristas if v == n and (u, v) not in atras and u in capa] for n in nodos}
    filas = {}
    for n in nodos: filas.setdefault(capa[n], []).append(n)
    pos, y = {}, 0.0
    for c in sorted(filas):
        fila = filas[c]
        alto = max(tam(n)[1] for n in fila)
        deseo = {}
        for n in fila:
            ps = [pos[p][0] + tam(p)[0] / 2 for p in padres[n] if p in pos]
            deseo[n] = sum(ps) / len(ps) if ps else None
        xs = {}
        if columna:                                    # calles: los de cada calle, centrados en su calle
            grupos = {}
            for n in fila: grupos.setdefault(columna.get(n, (0, 6))[0:2], []).append(n)
            for (x0, ancho), ns in grupos.items():
                ns.sort(key=lambda n: (deseo[n] is None, deseo[n] or 0, nodos.index(n)))
                total = sum(tam(n)[0] for n in ns) + gap_x * (len(ns) - 1)
                x = x0 + (ancho - total) / 2
                for n in ns: xs[n] = x; x += tam(n)[0] + gap_x
        else:
            orden = sorted(fila, key=lambda n: (deseo[n] is None, deseo[n] if deseo[n] is not None else 0, nodos.index(n)))
            x = None
            for n in orden:
                w = tam(n)[0]
                quiere = (deseo[n] - w / 2) if deseo[n] is not None else (x + gap_x if x is not None else 0)
                xs[n] = quiere if x is None else max(quiere, x + gap_x); x = xs[n] + w
            con_deseo = [n for n in fila if deseo[n] is not None]
            if con_deseo:                              # que la fila quede, en promedio, bajo sus padres
                corr = sum(deseo[n] - (xs[n] + tam(n)[0] / 2) for n in con_deseo) / len(con_deseo)
                xs = {n: v + corr for n, v in xs.items()}
        for n in fila: pos[n] = (xs[n], y + (alto - tam(n)[1]) / 2)
        y += alto + gap_y
    if pos:
        mx = min(p[0] for p in pos.values())
        if not columna: pos = {n: (p[0] - mx, p[1]) for n, p in pos.items()}
    return pos


class Colocador:
    def __init__(self, ctx, medidas, pistas):
        self.ctx, self.medidas, self.pistas = ctx, medidas or {}, pistas
        self.elems = ctx.elems
        self.por_nombre = {_n(e["nombre"]): e for e in self.elems}
        for e in self.elems:
            if e.get("texto"): self.por_nombre.setdefault(_n(e["texto"]), e)
        d = ctx.d
        quit = set(ctx.plan["quitar"])
        cajas = [c["caja"] for c in d["clases"] if c["id"] not in quit] + [n["caja"] for n in d.get("notas", []) if n["id"] not in quit] \
            + [o["caja"] for o in d.get("objetos", []) if o["id"] not in quit] + [l["caja"] for l in d.get("lineas", []) if l["id"] not in quit]
        cajas += [(*c["pos"], *_caja_clase(c)) for c in ctx.plan["nuevas"] if c.get("pos") and not c.get("dentro_de")]
        cajas += [(*n["pos"], *du.medidas_nota(n["texto"])) for n in ctx.plan["notas"] if n.get("pos")]
        self.ocupado = _union(cajas)

    def tam(self, e): return self.ctx.tam(e, self.medidas)

    def aristas(self):
        """(de, a) entre elementos nuevos (por su nombre normalizado), de las líneas, las relaciones y las pistas del ejercicio."""
        out = []
        for l in self.ctx.lineas:
            if l["_de"]["nueva"] and l.get("_a") and l["_a"]["nueva"]: out.append((_n(l["_de"]["o"]["nombre"]), _n(l["_a"]["o"]["nombre"])))
        for r in self.ctx.plan["relaciones"]:            # el padre (o el base de un extend) arriba
            out.append((_n(r["a"]), _n(r["de"])) if r["tipo"] in ("herencia", "realizacion", "extend") else (_n(r["de"]), _n(r["a"])))
        for p in self.pistas: out.append((_n(p.get("de")), _n(p.get("a"))))
        return [(u, v) for u, v in out if u in self.por_nombre and v in self.por_nombre]

    def colocar(self):
        for e in self.elems:                           # una barra de bifurcación/unión tan ancha como sus ramas
            if e["accion"] in ("bifurcacion", "union"):
                sal = sum(1 for l in self.ctx.lineas if l["_de"]["o"] is e); ent = sum(1 for l in self.ctx.lineas if l.get("_a") and l["_a"]["o"] is e)
                e["_ancho_barra"] = max(4.0, 4.2 * max(sal, ent) - 1.0)
        fams = {}
        for e in self.elems: fams.setdefault(e["familia"], []).append(e)
        bloques = []
        if fams.get("casos"): bloques.append(self.casos(fams["casos"]))
        if fams.get("secuencia") or any(l["accion"] == "mensaje" for l in self.ctx.lineas): bloques.append(self.secuencia(fams.get("secuencia", [])))
        for f in ("flujo", "bloques", "libre"):
            if fams.get(f): bloques.append(self.capas_con_contenedores(fams[f], f))
        # cada bloque (posiciones relativas) va debajo de lo que ya hay, sin encimar
        y = (self.ocupado[1] + self.ocupado[3] + 3) if self.ocupado else 2.0
        x = self.ocupado[0] if self.ocupado else 2.0
        for b in bloques:
            if not b or not b.get("rel"): continue
            caja = _union([(p[0], p[1], *self.tam_o(e)) for e, p in b["rel"]])
            dx, dy = x - caja[0], y - caja[1]
            for e, p in b["rel"]: e["xy"] = (p[0] + dx, p[1] + dy)
            for f in b.get("despues", []): f(dx, dy)
            y += caja[3] + 3
        for e in self.elems:
            if e.get("pos"): e["xy"] = e["pos"]
            e.setdefault("xy", (2.0, 2.0))
            if e["accion"] == "artefacto" or e.get("es_clase"): pass
        self.barras()
        self.flujos_puntos()

    def barras(self):
        """Cada barra de bifurcación (o unión) tan ancha como sus ramas, para que las flechas bajen rectas a sus puntos."""
        for e in self.elems:
            if e["accion"] not in ("bifurcacion", "union") or not e.get("xy"): continue
            ramas = [l["_a"] for l in self.ctx.lineas if l["_de"]["o"] is e and l.get("_a")] if e["accion"] == "bifurcacion" \
                else [l["_de"] for l in self.ctx.lineas if l.get("_a") and l["_a"]["o"] is e]
            cs = [c[0] + c[2] / 2 for c in (self.caja_de(r)[0] for r in ramas)]
            if len(cs) < 2: continue
            lo, hi = min(cs), max(cs); w = max(4.0, (hi - lo) / 0.75)
            e["_ancho_barra"] = w; e["xy"] = ((lo + hi) / 2 - w / 2, e["xy"][1])

    def tam_o(self, e): return e["_tam"] if e.get("_tam") else self.tam(e)

    # ----- casos de uso -----
    def casos(self, es):
        actores = [e for e in es if e["accion"] == "actor"]
        casos = [e for e in es if e["accion"] == "caso"]
        sistemas = [e for e in es if e["accion"] == "sistema"]
        existentes = [o for o in self.ctx.d.get("objetos", []) if o["kind"] == "sistema" and o["id"] not in self.ctx.plan["quitar"]]
        for c in casos:                               # el sistema de cada caso: el que dice, o el único que hay
            if not c.get("dentro_de"):
                if len(sistemas) == 1: c["dentro_de"] = sistemas[0]["nombre"]
                elif not sistemas and len(existentes) == 1: c["dentro_de"] = nombre_de(existentes[0])
        rels = [(l["_de"], l["_a"], "x") for l in self.ctx.lineas if l.get("_a")]
        rels += [(self._x(r["de"]), self._x(r["a"]), r["tipo"]) for r in self.ctx.plan["relaciones"]]
        def nuevo(x): return x and x.get("nueva") and x["o"] in es
        asociados = {id(a): [] for a in actores}
        secundarios = set()
        for u, v, t in rels:
            # el incluido y el que extiende van a la segunda columna (aunque el caso base ya estuviera en el diagrama)
            if t == "include" and nuevo(v) and v["o"] in casos: secundarios.add(id(v["o"]))
            if t == "extend" and nuevo(u) and u["o"] in casos: secundarios.add(id(u["o"]))
            if not (u and v): continue
            for p, q in ((u, v), (v, u)):
                if nuevo(p) and p["o"]["accion"] == "actor" and q.get("o") and q["o"] in casos: asociados[id(p["o"])].append(q["o"])
        orden = []
        for a in actores:
            for c in asociados[id(a)]:
                if c not in orden and id(c) not in secundarios: orden.append(c)
        orden += [c for c in casos if c not in orden and id(c) not in secundarios]
        segunda = [c for c in casos if id(c) in secundarios]
        rel, despues = [], []
        # ¿van dentro de un límite que ya está? se ponen debajo de lo que tiene dentro y se agranda
        for s in existentes:
            dentro = [c for c in orden + segunda if _n(c.get("dentro_de")) in (_n(s.get("texto")), _n(s.get("nombre")))]
            if not dentro: continue
            sx, sy, sw, sh = s["caja"]
            hijos = [o for o in self.ctx.d.get("objetos", []) if o["kind"] == "caso" and sx <= o["caja"][0] + o["caja"][2] / 2 <= sx + sw
                     and sy <= o["caja"][1] + o["caja"][3] / 2 <= sy + sh]
            y = max([o["caja"][1] + o["caja"][3] for o in hijos] + [sy + 1.6]) + 1.0
            # los incluidos y los que extienden, en una segunda columna a la derecha (con sitio para el rótulo «include»/«extend»
            # entre las dos); los demás, debajo de los que ya hay
            dentro_1 = [c for c in dentro if id(c) not in secundarios]
            dentro_2 = [c for c in dentro if id(c) in secundarios]
            izq = min([o["caja"][0] for o in hijos] or [sx])
            col1 = [o for o in hijos if o["caja"][0] < izq + 2.0]; col2 = [o for o in hijos if o not in col1]
            if col2: y = max([o["caja"][1] + o["caja"][3] for o in col1] + [sy + 1.6]) + 1.0
            for c in dentro_1:
                w, h = self.tam(c); c["pos"] = ((min(o["caja"][0] for o in col1) if col1 else sx + max(1.0, (sw - w) / 2)), y); y += h + 0.9
            derecha_1 = max([o["caja"][0] + o["caja"][2] for o in col1] + [c["pos"][0] + self.tam(c)[0] for c in dentro_1] + [sx + 1.0])
            x2 = min(o["caja"][0] for o in col2) if col2 else derecha_1 + 8.0
            y2 = max([o["caja"][1] + o["caja"][3] + 0.9 for o in col2] + [sy + 2.6])
            fondo = max([y] + [o["caja"][1] + o["caja"][3] for o in hijos])
            for c in dentro_2:
                w, h = self.tam(c)
                base = None                                            # el caso con el que va (para ponerlo a su altura)
                for r in self.ctx.plan["relaciones"]:
                    if r["tipo"] not in ("include", "extend"): continue
                    otro = r.get("_de") if r["tipo"] == "include" else r.get("_a")
                    yo = r.get("_a") if r["tipo"] == "include" else r.get("_de")
                    if yo and yo.get("o") is c and otro and otro.get("o") is not None:
                        o = otro["o"]; base = (o.get("caja") or (*o.get("pos", (0, 0)), 0, 0))[1] if (o.get("caja") or o.get("pos")) else None
                c["pos"] = (x2, max(y2, base if base is not None else y2)); y2 = c["pos"][1] + h + 0.9; fondo = max(fondo, y2)
            pares = []
            if fondo + 0.6 > sy + sh: pares.append(("elem_height", repr(round(fondo + 0.6 - sy, 2))))
            if dentro_2:
                ancho = max(x2 + self.tam(c)[0] for c in dentro_2) + 1.2 - sx
                if ancho > sw: pares.append(("elem_width", repr(round(ancho, 2))))
            for c in dentro:
                if c in orden: orden.remove(c)
                if c in segunda: segunda.remove(c)
            if pares: self.ctx.cambiar.append({"id": s["id"], "pares": pares, "nombre": nombre_de(s), "tag": s.get("tag"), "auto": True})
            for a in actores:                                          # sus actores, a la izquierda del límite
                if a.get("pos"): continue
                cs = [c for c in asociados[id(a)] if c.get("pos")]
                if cs:
                    w, h = self.tam(a); cy = sum(c["pos"][1] + self.tam(c)[1] / 2 for c in cs) / len(cs)
                    a["pos"] = ((sx + sw + 3.0) if a.get("lado") == "derecha" else (sx - 3.0 - w), cy - h / 2)
        # lo demás, como bloque: actores | límite con casos | actores de la derecha
        for a in actores:                              # un actor de la derecha con casos de la 1.ª columna cruzaría la 2.ª: va a la izquierda
            if a.get("lado") == "derecha" and segunda and any(c in orden for c in asociados[id(a)]): a["lado"] = "izquierda"
        izq = [a for a in actores if a.get("lado") != "derecha" and not a.get("pos")]
        der = [a for a in actores if a.get("lado") == "derecha" and not a.get("pos")]
        if not (orden or segunda or izq or der or sistemas): return {"rel": rel}
        ancho_izq = max([self.tam(a)[0] for a in izq] or [0])
        x_sis = ancho_izq + 3.5 if izq else 0
        tit = 2.0 if sistemas else 0
        w1 = max([self.tam(c)[0] for c in orden] or [0]); w2 = max([self.tam(c)[0] for c in segunda] or [0])
        y = tit + 0.8; ys = {}
        for c in orden:
            w, h = self.tam(c); rel.append((c, (x_sis + 1.2 + (w1 - w) / 2, y))); ys[id(c)] = (y, h); y += h + 0.9
        x2 = x_sis + 1.2 + w1 + 8.0                    # sitio para «include» / «extend» entre las dos columnas
        y2 = tit + 0.8
        for c in segunda:
            w, h = self.tam(c)
            base = [ys[id(q["o"])][0] for u, v, t in rels for p, q in ((u, v), (v, u)) if p and q and p.get("o") is c and q.get("o") is not None and id(q["o"]) in ys]
            yy = max(base[0] if base else y2, y2)
            rel.append((c, (x2 + (w2 - w) / 2, yy))); ys[id(c)] = (yy, h); y2 = yy + h + 0.9
        alto_sis = max(y, y2) + 0.2
        ancho_sis = 1.2 + w1 + (8.0 + w2 if segunda else 0) + 1.2
        for s in sistemas:
            s["_tam"] = (max(ancho_sis, 0.6 * len(s["texto"]) + 2), max(alto_sis, 4))
            rel.append((s, (x_sis, 0)))
        def colocar_actores(lista, x_fn):
            yy = 0.0
            for a in lista:
                w, h = self.tam(a)
                cs = [ys[id(c)] for c in asociados[id(a)] if id(c) in ys]
                cy = sum(p + q / 2 for p, q in cs) / len(cs) if cs else yy + h / 2
                top = max(cy - h / 2, yy); rel.append((a, (x_fn(w), top))); yy = top + h + 1.0
        colocar_actores(izq, lambda w: ancho_izq - w)
        x_der = x_sis + (ancho_sis if (orden or segunda or sistemas) else 0) + 3.5
        colocar_actores(der, lambda w: x_der)
        return {"rel": rel}

    def _x(self, nombre):
        e = self.por_nombre.get(_n(nombre))
        return {"o": e, "nueva": True} if e else None

    # ----- secuencia -----
    def secuencia(self, es):
        ctx, d = self.ctx, self.ctx.d
        msgs = [l for l in ctx.lineas if l["accion"] == "mensaje"]
        viejos = [o for o in d.get("objetos", []) if (o["kind"] == "participante" or o.get("vidas")) and o["id"] not in ctx.plan["quitar"]]
        por_id = d.get("_por_id", {})
        retrazar = getattr(ctx, "retrazar", False)       # la secuencia se traza otra vez entera (un mensaje entre dos)
        # participantes: los que ya están (con su cabeza y su última línea de vida) y los nuevos, en fila
        cab_top = min([o["caja"][1] for o in viejos] or [0.0])
        x_sig = max([o["caja"][0] + o["caja"][2] for o in viejos] or [-3.0]) + 3.0
        info = {}
        for o in viejos:
            vidas = [por_id[v] for v in o.get("vidas", []) if v in por_id]
            ult = max(vidas, key=lambda v: max(p[1] for p in v.get("puntos") or [(0, 0)]), default=None)
            cx = o["caja"][0] + o["caja"][2] / 2
            if retrazar: ult = None
            info[id(o)] = {"cx": cx, "nuevo": False, "o": o, "ult": ult, "fresco": retrazar,
                           "bajo": o["caja"][1] + o["caja"][3] if retrazar else max([p[1] for v in vidas for p in v.get("puntos") or []] + [o["caja"][1] + o["caja"][3]])}
        creados = {id(l["_a"]["o"]): l for l in msgs if l["mtipo"] == 1 and l["_a"]["nueva"]}
        rel = []
        x = x_sig if viejos else 0.0
        for e in es:
            w, h = self.tam(e)
            info[id(e)] = {"cx": x + w / 2, "nuevo": True, "o": e, "w": w, "h": h}
            x += w + 3.0
        # separación suficiente para el texto de los mensajes entre participantes vecinos
        orden = sorted(info.values(), key=lambda i: i["cx"])
        for l in msgs:
            a, b = info.get(id(l["_de"]["o"])), info.get(id(l["_a"]["o"]))
            if not a or not b or a is b: continue
            necesita = 0.45 * len(l.get("texto") or "") + 1.6
            i, j = sorted((orden.index(a), orden.index(b)))
            falta = necesita - (orden[j]["cx"] - orden[i]["cx"])
            if falta > 0:
                for q in orden[j:]:
                    if q["nuevo"]: q["cx"] += falta
        # filas de los mensajes nuevos (debajo de todo lo de antes)
        alto_cab = max([i["h"] for i in info.values() if i["nuevo"]] + [o["caja"][3] for o in viejos] + [1.9])
        y = max([cab_top + alto_cab] + [i["bajo"] for i in info.values() if not i["nuevo"]] +
                [l.get("y", 0) for l in d.get("lineas", []) if l["tipo"] == "UML - Message" and l["id"] not in ctx.plan["quitar"]]) + S_FILA
        filas = []
        for l in msgs:
            l["_y"] = y; filas.append(y)
            if l["mtipo"] == 1:                        # el creado aparece a la altura del mensaje
                i = info[id(l["_a"]["o"])]; i["y_cab"] = y - i["h"] / 2
            y += S_FILA * (2 if l["mtipo"] == 6 else 1)
        fin_comun = y + 0.6
        # cabezas de los nuevos
        for i in info.values():
            if i["nuevo"]:
                top = i.get("y_cab", cab_top)
                rel.append((i["o"], (i["cx"] - i["w"] / 2, top)))
        # actividad de cada participante en estos mensajes
        uso = {}
        for l in msgs:
            for lado in ("_de", "_a"):
                uso.setdefault(id(l[lado]["o"]), []).append(l["_y"] + (S_FILA if l["mtipo"] == 6 and lado == "_a" else 0))
        vidas = []
        for k, i in info.items():
            ys = sorted(uso.get(k, []))
            if not ys and not i["nuevo"] and not i.get("fresco"): continue
            destruido = next((l for l in msgs if l["mtipo"] == 2 and id(l["_a"]["o"]) == k), None)
            if i["nuevo"]:
                top = i.get("y_cab", cab_top) + i["h"]; arriba = {"x": i}
            elif i.get("fresco"):                       # otra línea de vida, colgada de su cabeza de siempre
                top = i["o"]["caja"][1] + i["o"]["caja"][3]; arriba = {"x": i}
            else:
                ult = i["ult"]
                if ult is None: continue
                top = max(p[1] for p in ult["puntos"]) if not ys else None
                arriba = {"seg": ult}
                top = _fondo_actividad(ult)
            primero = ys[0] if ys else top + S_FILA
            if i["nuevo"] and id(i["o"]) in creados: primero = creados[id(i["o"])]["_y"] + S_FILA
            ultimo = ys[-1] if ys else primero
            if destruido: ultimo = destruido["_y"]
            span = max(0.0, round((ultimo - primero) / S_FILA))
            span2 = max(2, int(span + span % 2))
            fin = (primero + span2 * S_FILA + 0.5) if destruido else max(fin_comun, primero + span2 * S_FILA + 0.6)
            v = {"accion": "_vida", "tag": ctx.etiqueta(), "x": i["cx"], "top": top, "rtop": primero - top, "rbot": primero - top + span2 * S_FILA,
                 "n": span2 // 2 - 1, "fin": fin, "cruz": bool(destruido), "arriba": arriba, "info": i, "familia": "secuencia"}
            if v["rtop"] < 0.3: v["rtop"] = 0.3; v["rbot"] = 0.3 + span2 * S_FILA
            i["vida"] = v; vidas.append(v)
        ctx.plan["vidas"] = vidas
        for l in msgs:
            a, b = info[id(l["_de"]["o"])], info[id(l["_a"]["o"])]
            l["_info"] = (a, b)
        def despues(dx, dy):
            for i in info.values():
                if i["nuevo"]: i["cx"] += dx
            for v in vidas:
                if v["info"]["nuevo"]: v["x"] += dx; v["top"] += dy; v["fin"] += dy
            for l in msgs: l["_y"] += dy
        # si ya había participantes, el bloque no se mueve (va alineado con ellos)
        if viejos:
            for e, p in rel: e["xy"] = p
            return {"rel": []}
        return {"rel": rel, "despues": [despues]}

    # ----- capas con contenedores (actividades, estados, componentes, despliegue, paquetes, modo libre) -----
    def capas_con_contenedores(self, es, familia):
        hijos, raiz = {}, []
        nombres = {_n(e["nombre"]): e for e in es}
        clases_dentro = [c for c in self.ctx.plan["nuevas"] if c.get("dentro_de") and _n(c["dentro_de"]) in nombres]
        for c in clases_dentro:
            c["accion"], c["familia"], c["es_clase"] = "_clase", familia, True
            c["_tam"] = _caja_clase(c); nombres.setdefault(_n(c["nombre"]), c)
        todos = es + clases_dentro
        existentes = {_n(o.get("texto") or o.get("nombre")): o for o in self.ctx.d.get("objetos", []) if o["kind"] in ("paquete", "nodo", "compuesto", "sistema")}
        for e in todos:
            p = _n(e.get("dentro_de"))
            if p and p in nombres and nombres[p] is not e: hijos.setdefault(id(nombres[p]), []).append(e)
            elif p and p in existentes: e["_en_existente"] = existentes[p]
            else: raiz.append(e)
        aristas = self.aristas()
        for c in clases_dentro:
            for r in self.ctx.plan["relaciones"]: pass
        def antepasado(e, nivel):
            while e is not None and e not in nivel:
                p = _n(e.get("dentro_de")); e = nombres.get(p) if p else None
            return e
        def resolver(nivel):
            """Posiciones relativas de los elementos de `nivel` (y de lo que tienen dentro)."""
            for e in nivel:
                if id(e) in hijos:
                    sub = hijos[id(e)]
                    rel = resolver(sub)
                    caja = _union([(p[0], p[1], *self.tam_o(h)) for h, p in rel]) or (0, 0, 3, 2)
                    tit = 2.2 if e["accion"] in ("paquete", "compuesto") else 2.6 if e["accion"] == "nodo" else 1.8
                    e["_tam"] = (max(caja[2] + 2.4, 0.6 * len(e.get("texto") or "") + 3), caja[3] + tit + 1.2)
                    e["_hijos_rel"] = {id(h): (p[0] - caja[0] + 1.2, p[1] - caja[1] + tit) for h, p in rel}
                    e["_hijos"] = sub
            locales = [e for e in nivel]
            ar = []
            for u, v in aristas:
                a, b = antepasado(nombres.get(u), locales), antepasado(nombres.get(v), locales)
                if a is not None and b is not None and a is not b: ar.append((id(a), id(b)))
            ids = [id(e) for e in locales]
            calles = None
            if familia == "flujo" and nivel is raiz:
                calles = [e for e in locales if e["accion"] == "calle"]
                if calles: return self._con_calles(locales, calles, ar)
            pos = disponer(ids, ar, lambda i: self.tam_o(next(e for e in locales if id(e) == i)))
            return [(e, pos[id(e)]) for e in locales]
        rel_raiz = resolver(raiz)
        def bajar(e, xy):
            e["xy"] = xy
            for h in e.get("_hijos", []):
                dx, dy = e["_hijos_rel"][id(h)]; bajar(h, (xy[0] + dx, xy[1] + dy))
        rel = list(rel_raiz)
        def despues(dx, dy):
            for e, p in rel_raiz: bajar(e, (p[0] + dx, p[1] + dy))
            for c in clases_dentro: c["pos"] = c["xy"]
            for e in es:
                if e.get("_calle_caja"): pass
        # lo que va dentro de un contenedor que ya existía: debajo de lo que tiene, y se agranda
        for o in {id(e["_en_existente"]): e["_en_existente"] for e in todos if e.get("_en_existente")}.values():
            dentro = [e for e in todos if e.get("_en_existente") is o]
            sx, sy, sw, sh = o["caja"]
            y = sy + sh - 0.6
            hijos_viejos = [q for q in self.ctx.d.get("objetos", []) + [{"caja": c["caja"]} for c in self.ctx.d["clases"]] if q is not o and
                            sx <= q["caja"][0] + q["caja"][2] / 2 <= sx + sw and sy <= q["caja"][1] + q["caja"][3] / 2 <= sy + sh]
            y = max([q["caja"][1] + q["caja"][3] for q in hijos_viejos] + [sy + 2.0]) + 1.0
            x = sx + 1.2
            for e in dentro:
                w, h = self.tam_o(e); e["pos"] = (x, y)
                if e.get("es_clase"): e["pos"] = (x, y)
                y += h + 1.0
            nuevo_alto = y + 0.4 - sy; nuevo_ancho = max([sw] + [self.tam_o(e)[0] + 2.4 for e in dentro])
            pares = []
            if nuevo_alto > sh: pares.append(("elem_height", repr(round(nuevo_alto, 2))))
            if nuevo_ancho > sw: pares.append(("elem_width", repr(round(nuevo_ancho, 2))))
            if pares: self.ctx.cambiar.append({"id": o["id"], "pares": pares, "nombre": nombre_de(o), "tag": o.get("tag"), "auto": True})
        return {"rel": rel, "despues": [despues]}

    def _con_calles(self, locales, calles, ar):
        """Actividades con calles: cada calle es una columna; los nodos van en la suya, por capas de arriba abajo."""
        nombre_calle = {_n(c["nombre"]): c for c in calles}
        resto = [e for e in locales if e["accion"] != "calle"]
        def calle_de(e): return nombre_calle.get(_n(e.get("en_calle"))) or calles[0]
        # ancho de cada calle: lo más ancho que tenga en una misma capa
        ids = [id(e) for e in resto]
        capa, _ = capas(ids, ar)
        anchos = {id(c): max(5.5, 0.6 * len(c["texto"]) + 2) for c in calles}
        for c in calles:
            por_capa = {}
            for e in resto:
                if calle_de(e) is c: por_capa.setdefault(capa[id(e)], []).append(self.tam_o(e)[0] + (0.46 * len(e["pregunta"]) + 0.8 if e.get("pregunta") else 0))
            for ws in por_capa.values(): anchos[id(c)] = max(anchos[id(c)], sum(ws) + 2.4 * (len(ws) - 1) + 2.4)
        x, columna = 0.0, {}
        for c in calles:
            for e in resto:
                if calle_de(e) is c: columna[id(e)] = (x, anchos[id(c)])
            c["_x"] = x; x += anchos[id(c)]
        pos = disponer(ids, ar, lambda i: self.tam_o(next(e for e in resto if id(e) == i)), columna=columna)
        out = [(e, (pos[id(e)][0], pos[id(e)][1] + 2.6)) for e in resto]
        alto = max([p[1] + self.tam_o(e)[1] for e, p in out] + [6]) + 1.2
        for c in calles:
            c["_tam"] = (anchos[id(c)], alto); out.append((c, (c["_x"], 0.0)))
        return out

    # ----- puntos de las líneas (el plugin las pega a sus objetos; esto es solo el trazo inicial) -----
    def caja_de(self, x):
        """Caja (x, y, w, h) de un extremo (nuevo o que ya estaba) y su clase de objeto."""
        o = x["o"]
        if x["nueva"]:
            if o.get("accion") == "_clase" or o.get("es_clase") or "atributos" in o:
                w, h = _caja_clase(o); p = o.get("pos") or o.get("xy") or (0, 0); return (p[0], p[1], w, h), "clase"
            w, h = self.tam_o(o); k = o.get("accion", "")
            if k == "crear" and "Diamond" in o.get("tipo", ""): k = "decision"     # el rombo de un diagrama de flujo
            return (o["xy"][0], o["xy"][1], w, h), k
        return tuple(o.get("caja") or (0, 0, 1, 1)), o.get("kind", "clase" if "atributos" in o else "")

    def flujos_puntos(self):
        """Trazo de cada línea nueva que no es mensaje: de qué lado sale y a qué lado llega (el plugin la pega al punto de
        conexión más cercano a esos lados) y, si es ortogonal, sus tramos (sin autorruta: así quedan limpias), sin pasar
        por encima de otros objetos ni de otras líneas."""
        cajas = [self.caja_de({"o": e, "nueva": True})[0] for e in self.elems if e.get("xy") and e["accion"] not in CONTENEDORES]
        cajas += [tuple(o["caja"]) for o in self.ctx.d.get("objetos", []) if o["kind"] not in CONTENEDORES | {"rotulo", "linea_vida"}]
        cajas += [tuple(c["caja"]) for c in self.ctx.d["clases"]]
        derecha = max([c[0] + c[2] for c in cajas] or [0])
        conts = [self.caja_de({"o": e, "nueva": True})[0] for e in self.elems if e.get("xy") and e["accion"] in ("compuesto", "paquete", "nodo")]
        conts += [tuple(o["caja"]) for o in self.ctx.d.get("objetos", []) if o["kind"] in ("compuesto", "paquete", "nodo")]
        trazos = Trazos(cajas, derecha + 1.5, conts)
        salidas = {}
        for l in self.ctx.lineas:
            if l["accion"] == "mensaje" or not l.get("_a"): continue
            salidas.setdefault(id(l["_de"]["o"]), []).append(l)
        for l in self.ctx.lineas:
            if l["accion"] == "mensaje": continue
            A, ka = self.caja_de(l["_de"])
            if not l.get("_a"):                        # interfaz de un componente: ofrecidas a la derecha, requeridas a la izquierda
                lado = 1 if l["accion"] == "interfaz_ofrecida" else -1
                mismas = [m for m in self.ctx.lineas if not m.get("_a") and m["_de"]["o"] is l["_de"]["o"] and m["accion"] == l["accion"]]
                k = mismas.index(l); dy = (k - (len(mismas) - 1) / 2) * 1.4
                p0 = (A[0] + A[2] if lado > 0 else A[0], A[1] + A[3] / 2 + dy)
                l["_p"] = (p0, (p0[0] + 3.0 * lado, p0[1])); l["_hint"] = (p0, None); continue
            B, kb = self.caja_de(l["_a"])
            l["_ruta"], l["_hint"] = trazos.trazar(A, ka, B, kb, len(salidas.get(id(l["_de"]["o"]), [])) > 1)
            l["_p"] = (l["_ruta"][0][0], l["_ruta"][0][-1])
            o = l["_de"]["o"]
            if l["_de"]["nueva"] and o.get("accion") == "decision":       # por qué lados sale (para poner la pregunta en otro)
                p0, p1 = l["_ruta"][0][0], l["_ruta"][0][1]
                o.setdefault("_lados", set()).add("derecha" if p1[0] > p0[0] + 0.01 else "izquierda" if p1[0] < p0[0] - 0.01 else "abajo")
        tronco = {}
        for r in self.ctx.plan["relaciones"]:          # relaciones con actores, casos, nodos, paquetes...: lado a lado
            dx, ax = r.get("_de"), r.get("_a")
            if not dx or not ax or ("c" in dx and "c" in ax): continue
            ex = [self._extremo_rel(dx), self._extremo_rel(ax)]
            ini, fin = (1, 0) if du.TIPOS_REL[r["tipo"]]["inicio_es_a"] else (0, 1)
            (A, ka), (B, kb) = ex[ini], ex[fin]
            ruta, hint = trazos.trazar(A, ka, B, kb, False, preferir_lados=True,
                                       rotulo=r["tipo"] in ("include", "extend") or bool(r.get("estereotipo")))
            r["_ruta"], r["_autoruta"] = ruta, False
            r["puntos"] = (ruta[0][0], ruta[0][-1])
            r["_hint_ini"], r["_hint_fin"] = hint

    def _extremo_rel(self, x):
        if "c" in x:                                   # una clase (registro de cambios_dia)
            c = x["c"]
            if x["nueva"]:
                w, h = _caja_clase(c); p = c.get("pos") or (0, 0); return (p[0], p[1], w, h), "clase"
            return tuple(c["caja"]), "clase"
        return self.caja_de(x)


H, V = 0, 1          # orientación de cada tramo de una línea ortogonal de Dia


class Trazos:
    """Trazos ortogonales limpios: hacia abajo, del centro de abajo al centro de arriba (de una decisión con varias salidas,
    por sus puntas); hacia arriba (un bucle), por fuera a la derecha; al lado, de lado a lado. Cada trazo prueba varias
    alturas (o columnas) para su tramo del medio y se queda con la primera que no pisa otro objeto ni otra línea."""

    def __init__(self, cajas, derecha, contenedores=()):
        self.cajas, self.usados, self.x_vuelta, self.contenedores = cajas, [], derecha, list(contenedores)

    def _choca(self, pts, A, B):
        n = len(pts) - 1
        for i, ((x0, y0), (x1, y1)) in enumerate(zip(pts, pts[1:])):
            if abs(x0 - x1) < 1e-6 and abs(y0 - y1) < 1e-6: continue
            extremo = i == 0 or i == n - 1             # salir de un mismo sitio o llegar al mismo punto no es pisarse
            lx, hx, ly, hy = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
            for c in self.cajas:
                if c == A or c == B: continue
                if lx < c[0] + c[2] - 0.05 and hx > c[0] + 0.05 and ly < c[1] + c[3] - 0.05 and hy > c[1] + 0.05: return True
            dentro = lambda r, c: c[0] <= r[0] + r[2] / 2 <= c[0] + c[2] and c[1] <= r[1] + r[3] / 2 <= c[1] + c[3]
            for c in self.contenedores:                # un estado compuesto, paquete o nodo: solo lo cruzan las líneas de lo de dentro
                if c == A or c == B or dentro(A, c) or dentro(B, c): continue
                if lx < c[0] + c[2] and hx > c[0] and ly < c[1] + c[3] and hy > c[1]: return True
            for (u0, v0), (u1, v1) in ([] if extremo else self.usados):
                if abs(y0 - y1) < 1e-6 and abs(v0 - v1) < 1e-6 and abs(y0 - v0) < 0.3 and min(hx, max(u0, u1)) - max(lx, min(u0, u1)) > 0.1: return True
                if abs(x0 - x1) < 1e-6 and abs(u0 - u1) < 1e-6 and abs(x0 - u0) < 0.3 and min(hy, max(v0, v1)) - max(ly, min(v0, v1)) > 0.1: return True
        return False

    def _guardar(self, ruta):
        pts = ruta[0][0]
        self.usados += [(a, b) for a, b in zip(pts, pts[1:]) if a != b]
        return ruta

    def trazar(self, A, ka, B, kb, varias=False, preferir_lados=False, rotulo=False):
        """`rotulo`: la línea lleva un rótulo que Dia pone junto a su tramo del medio («include», «extend»): ese tramo va cerca
        de la caja de la izquierda para que el rótulo quede en el hueco y no roce la caja de la derecha."""
        ax, ay, aw, ah = A; bx, by, bw, bh = B
        acx, bcx = ax + aw / 2, bx + bw / 2
        acy = ay + ah * (0.36 if ka == "actor" else 0.5); bcy = by + bh * (0.36 if kb == "actor" else 0.5)
        debajo, encima = by >= ay + ah - 0.05, by + bh <= ay + 0.05
        separados_x = bx >= ax + aw - 0.05 or bx + bw <= ax + 0.05
        clamp = lambda v, a, b: max(a, min(b, v))
        def mejor(opciones):
            for o in opciones:
                if not self._choca(o[0][0], A, B): return self._guardar(o)
            return self._guardar(opciones[0])
        def con_rodeo(opciones, rodeos):
            """La primera opción limpia; si todas pisan algo (una línea que salta varias capas), un rodeo por un pasillo libre."""
            for o in opciones:
                if not self._choca(o[0][0], A, B): return self._guardar(o)
            for o in rodeos:
                if not self._choca(o[0][0], A, B): return self._guardar(o)
            return self._guardar(opciones[0])
        def estorban(lo, hi, eje):
            return [c for c in self.cajas if c != A and c != B and (c[1] < hi and c[1] + c[3] > lo if eje == "y" else c[0] < hi and c[0] + c[2] > lo)]
        def lado_a_lado():
            p0, p1 = ((ax + aw, acy), (bx, bcy)) if bx >= acx else ((ax, acy), (bx + bw, bcy))
            if abs(p0[1] - p1[1]) < 0.05: p1 = (p1[0], p0[1])     # en línea: el tramo del medio mide 0 (Dia necesita 3 puntos o más)
            xm = (p0[0] + p1[0]) / 2; s = 1 if p1[0] >= p0[0] else -1
            xs = [xm] + [v for k in range(1, 12) for v in (p0[0] + s * 0.4 * k, p1[0] - s * 0.4 * k) if min(p0[0], p1[0]) < v < max(p0[0], p1[0])]
            if rotulo and abs(p1[0] - p0[0]) > 2: xs = [min(p0[0], p1[0]) + 0.6] + xs
            opciones = [(([p0, (x, p0[1]), (x, p1[1]), p1], [H, V, H]), (p0, p1)) for x in xs]
            # rodeo: sale un poco, sube o baja a un pasillo libre por encima o por debajo de lo que estorba, cruza y vuelve
            xa, xb = p0[0] + s * 0.7, p1[0] - s * 0.7
            malas = estorban(min(p0[0], p1[0]), max(p0[0], p1[0]), "x")
            yc = [y for c in malas for y in (c[1] - 0.8, c[1] + c[3] + 0.8)]
            yc += [min([c[1] for c in malas] + [p0[1], p1[1]]) - 0.8 - 0.6 * k for k in range(3)]
            yc += [max([c[1] + c[3] for c in malas] + [p0[1], p1[1]]) + 0.8 + 0.6 * k for k in range(3)]
            yc.sort(key=lambda y: abs(y - (p0[1] + p1[1]) / 2))
            rodeos = [(([p0, (xa, p0[1]), (xa, y), (xb, y), (xb, p1[1]), p1], [H, V, H, V, H]), (p0, p1)) for y in yc]
            return con_rodeo(opciones, rodeos)
        def vertical(p0, p1):
            if abs(p0[0] - p1[0]) < 0.05: p1 = (p0[0], p1[1])
            ym = (p0[1] + p1[1]) / 2; s = 1 if p1[1] >= p0[1] else -1
            ys = [ym] + [v for k in range(1, 14) for v in (p0[1] + s * 0.35 * k, p1[1] - s * 0.35 * k) if min(p0[1], p1[1]) < v < max(p0[1], p1[1])]
            opciones = [(([p0, (p0[0], y), (p1[0], y), p1], [V, H, V]), (p0, p1)) for y in ys]
            # rodeo: baja un poco, se va a un lado de lo que estorba, baja por ese pasillo y vuelve encima de su destino
            ya, yb = p0[1] + s * 0.7, p1[1] - s * 0.7
            malas = estorban(min(p0[1], p1[1]), max(p0[1], p1[1]), "y")
            centro = (p0[0] + p1[0]) / 2
            xc = [x for c in sorted(malas, key=lambda c: abs(c[0] + c[2] / 2 - centro)) for x in (c[0] + c[2] + 0.8, c[0] - 0.8)]
            xc += [max([c[0] + c[2] for c in malas] + [p0[0], p1[0]]) + 0.8 + 0.6 * k for k in range(3)]
            xc += [min([c[0] for c in malas] + [p0[0], p1[0]]) - 0.8 - 0.6 * k for k in range(3)]
            rodeos = [(([p0, (p0[0], ya), (x, ya), (x, yb), (p1[0], yb), p1], [V, H, V, H, V]), (p0, p1)) for x in xc]
            return con_rodeo(opciones, rodeos)
        if preferir_lados:
            if separados_x and not (debajo and abs(acx - bcx) < 2) and not (encima and abs(acx - bcx) < 2): return lado_a_lado()
            if debajo: return vertical((acx, ay + ah), (bcx, by))
            if encima: return vertical((acx, ay), (bcx, by + bh))
            return lado_a_lado()
        barra = ("bifurcacion", "union")
        if debajo:
            if ka in ("decision", "fusion") and varias and abs(bcx - acx) > aw / 2:
                p0 = (ax + aw, acy) if bcx > acx else (ax, acy); p1 = (bcx, by)
                op = (([p0, (bcx, acy), p1], [H, V]), (p0, p1))
                if not self._choca(op[0][0], A, B): return self._guardar(op)
            x0 = clamp(bcx, ax + 0.3, ax + aw - 0.3) if ka in barra else acx
            x1 = clamp(x0, bx + 0.3, bx + bw - 0.3) if kb in barra else bcx
            return vertical((x0, ay + ah), (x1, by))
        if encima:                                     # vuelve atrás: por fuera, por el lado que esté libre
            op = []
            for k in range(4):
                Xd = max(ax + aw, bx + bw) + 1.0 + 0.8 * k; Xi = min(ax, bx) - 1.0 - 0.8 * k
                op.append((([(ax + aw, acy), (Xd, acy), (Xd, bcy), (bx + bw, bcy)], [H, V, H]), ((ax + aw, acy), (bx + bw, bcy))))
                op.append((([(ax, acy), (Xi, acy), (Xi, bcy), (bx, bcy)], [H, V, H]), ((ax, acy), (bx, bcy))))
            X = max(self.x_vuelta, ax + aw + 1.0, bx + bw + 1.0); self.x_vuelta = X + 0.9
            op.append((([(ax + aw, acy), (X, acy), (X, bcy), (bx + bw, bcy)], [H, V, H]), ((ax + aw, acy), (bx + bw, bcy))))
            for o in op:
                if not self._choca(o[0][0], A, B): return self._guardar(o)
            return self._guardar(op[-1])
        return lado_a_lado()


def _textos_de_trazo(ruta, guarda="", evento=""):
    """Dónde poner la guarda (junto a la salida) y el evento (en el tramo más largo) de un flujo o una transición.
    Dia los dibuja centrados en ese punto: se apartan de la línea la mitad de su ancho."""
    pts, ori = ruta
    mg, me = 0.23 * (len(guarda) + 2) + 0.3, 0.23 * len(evento) + 0.4
    (x0, y0), (x1, y1) = pts[0], pts[1]
    g = ((x0 + (mg if x1 >= x0 else -mg), y0 - 0.3) if ori[0] == H else (x0 + mg, y0 + 0.75))
    k = max(range(len(ori)), key=lambda i: abs(pts[i + 1][0] - pts[i][0]) + abs(pts[i + 1][1] - pts[i][1]))
    (a, b), (c, d) = pts[k], pts[k + 1]
    ev = ((a + c) / 2, b - 0.3) if ori[k] == H else (a + me, (b + d) / 2 + 0.25)
    return g, ev


def _caja_clase(c):
    import cambios_dia
    return cambios_dia.caja_estimada(c)


def _fondo_actividad(v):
    """Dónde termina la caja de actividad de una línea de vida que ya estaba (para colgar otra debajo): su punto 6."""
    pts = v.get("puntos") or [(0, 0), (0, 3)]
    return pts[0][1] + (v.get("rbot") or 0) if v.get("rbot") else min(pts[-1][1], pts[0][1] + 3)


# ---------- XML de lo nuevo ----------
def _objeto_base(e):
    """El objeto de Dia de un elemento nuevo (en su sitio de la plantilla), con su texto y sus valores."""
    acc = e["accion"]; tipo = e["tipo"] if acc != "participante" or not e.get("como_actor") else "UML - Actor"
    o = do.nuevo(tipo)
    meta = {"tutor": e["tag"]}
    if acc in SIN_TEXTO or acc in ("crear",) and not e.get("texto"): meta["nombre"] = e["nombre"]
    if acc in ("sistema", "calle", "compuesto"): meta.update(rol=acc, nombre=e["nombre"])
    if acc == "crear" and e.get("texto") and _n(e["nombre"]) != _n(e["texto"]): meta["nombre"] = e["nombre"]
    do.poner_meta(o, meta)
    texto = e.get("texto") or ""
    if acc == "nodo" and e.get("estereotipo"): texto = f"«{e['estereotipo']}»\n{texto}"
    if acc == "artefacto":
        do.poner_xml(o, "name", "string", texto); do.poner_xml(o, "stereotype", "string", "artifact")
        for b in ("visible_attributes", "visible_operations"): do.poner_xml(o, b, "bool", False)
    elif acc in ("paquete",):
        do.poner_xml(o, "name", "string", texto)
    elif acc == "nodo":
        do.poner_xml(o, "name", "text", texto)
    elif texto and acc not in ("sistema", "calle", "compuesto"):
        tp = do.texto_principal(tipo)
        if tp: do.poner_xml(o, tp, "text" if do.props_tipo(tipo)[tp]["t"] == "text" else "string", texto)
    if acc in ("inicial", "final"): do.poner_xml(o, "is_final", "bool", acc == "final")
    if acc == "estado":
        for f, a in (("entrada", "entry_action"), ("hacer", "do_action"), ("salida", "exit_action")):
            if e.get(f): do.poner_xml(o, a, "string", e[f])
    if acc in ("componente", "paquete") and e.get("estereotipo"): do.poner_xml(o, "stereotype", "string", e["estereotipo"])
    if acc == "objeto" and e.get("valores"):
        do.poner_xml(o, "attrib", "text", "\n".join(e["valores"])); do.poner_xml(o, "show_attribs", "bool", True)
    if acc in ("sistema", "calle", "compuesto"):
        do.poner_xml(o, "show_background", "bool", False)
        if acc == "compuesto": do.poner_xml(o, "corner_radius", "real", 0.8)
        if acc == "calle": do.poner_xml(o, "line_width", "real", 0.06)
    if acc == "crear":
        if e.get("ancho"): do.poner_xml(o, "elem_width", "real", e["ancho"])
        if e.get("alto"): do.poner_xml(o, "elem_height", "real", e["alto"])
    return o


def _texto_suelto(texto, x, y, meta, centrado=True, alto=0.8, negrita=False, alineacion=None):
    o = do.nuevo("Standard - Text")
    do.poner_meta(o, meta)
    do.poner_xml(o, "text", "text", texto)
    comp = o.find("dia:attribute[@name='text']/dia:composite", du.NS)
    do.poner_xml(comp, "alignment", "enum", alineacion if alineacion is not None else 1 if centrado else 0)
    do.poner_xml(comp, "height", "real", alto)
    if negrita:
        f = comp.find("dia:attribute[@name='font']/dia:font", du.NS)
        if f is not None: f.set("style", "80"); f.set("name", "Helvetica-Bold")
    do.poner_xml(comp, "pos", "point", (x, y))
    do.poner_xml(o, "obj_pos", "point", (x, y))
    return o


def xml_elemento(e):
    """XML de un elemento nuevo ya colocado (e["xy"] = esquina de su caja exterior), y sus rótulos."""
    acc = e["accion"]
    if acc == "_clase": return []
    o = _objeto_base(e)
    bb = do.caja_xml(o)
    if e.get("_tam") and acc in CONTENEDORES | {"crear"} and acc != "crear" or acc in CONTENEDORES:
        w, h = e.get("_tam") or (bb[2], bb[3])
        do.poner_xml(o, "elem_width", "real", round(w, 3)); do.poner_xml(o, "elem_height", "real", round(h, 3))
        bb = (bb[0], bb[1], w, h)
        r = o.find("dia:attribute[@name='obj_bb']/dia:rectangle", du.NS)     # la caja guardada también (la lee quien no es Dia)
        if r is not None: r.set("val", f"{bb[0]:.4f},{bb[1]:.4f};{bb[0] + w:.4f},{bb[1] + h:.4f}")
    if acc in ("bifurcacion", "union") and e.get("_ancho_barra"): do.poner_xml(o, "elem_width", "real", e["_ancho_barra"])
    x, y = e["xy"]
    m = e.get("_medida")
    do.trasladar(o, x - (m[0] if m else bb[0]), y - (m[1] if m else bb[1]))
    out = [do.a_texto(o, f"E{e['tag'].replace('.', '_')}")]
    e["_tags_extra"] = []
    w, h = e.get("_tam") or (bb[2], bb[3])
    if acc in ("sistema", "calle", "compuesto"):
        t = e["tag"] + "t"; e["_tags_extra"].append(t)
        tx = x + w / 2 if acc != "compuesto" else x + 0.8
        out.append(do.a_texto(_texto_suelto(e["texto"], tx, y + 1.25, {"tutor": t, "rol": "titulo"}, centrado=acc != "compuesto", negrita=True),
                              f"E{t.replace('.', '_')}"))
    if acc == "decision" and e.get("pregunta"):          # la pregunta, en el lado por el que no sale ninguna flecha
        t = e["tag"] + "p"; e["_tags_extra"].append(t); lados = e.get("_lados") or set()
        if "derecha" not in lados: px, py, al = x + w + 0.3, y + h / 2 + 0.25, 0
        elif "izquierda" not in lados: px, py, al = x - 0.3, y + h / 2 + 0.25, 2
        else: px, py, al = x - 0.2, y - 0.25, 2
        out.append(do.a_texto(_texto_suelto(e["pregunta"], px, py, {"tutor": t, "rol": "pregunta"}, alineacion=al), f"E{t.replace('.', '_')}"))
    return out


def xml_linea(ctx, l):
    """XML de una línea nueva (mensaje, flujo/transición, interfaz o la del modo libre) con a qué se pega cada extremo."""
    acc = l["accion"]; o = do.nuevo(l["tipo"])
    meta = {"tutor": l["tag"]}
    if l.get("nombre"): meta["nombre"] = l["nombre"]
    out = []
    if acc == "mensaje":
        a, b = l["_info"]; y = l["_y"]
        va, vb = a.get("vida"), b.get("vida")
        lado = 0.35 if b["cx"] >= a["cx"] else -0.35
        p0 = (a["cx"] + (0.35 if l["mtipo"] == 6 else lado), y)
        if l["mtipo"] == 1:
            p1 = (b["cx"] - (b.get("w", 2) / 2) * (1 if b["cx"] >= a["cx"] else -1), y)
            ref_b = ctx.ref({"o": b["o"], "nueva": b["nuevo"]}, f"@{p1[0]:.3f},{p1[1]:.3f}")
        elif l["mtipo"] == 6:
            p1 = (a["cx"] + 1.8, y + S_FILA); ref_b = None
        else:
            p1 = (b["cx"] - lado, y)
            ref_b = f"tag:{vb['tag']}@{p1[0]:.3f},{p1[1]:.3f}" if vb else None
        ref_a = f"tag:{va['tag']}@{p0[0]:.3f},{p0[1]:.3f}" if va else None
        if l["mtipo"] == 4: p0, p1, ref_a, ref_b = p1, p0, ref_b, ref_a        # el retorno se dibuja con la punta en el extremo 0
        do.poner_extremos(o, p0, p1)
        do.poner_xml(o, "text", "string", l.get("texto") or "")
        do.poner_xml(o, "type", "enum", l["mtipo"])
        if l["mtipo"] == 6: tpos = (a["cx"] + 2.4 + 0.22 * len(l.get("texto") or ""), y + S_FILA / 2 + 0.25)   # a la derecha del bucle
        else: tpos = ((p0[0] + p1[0]) / 2, y - 0.35)
        do.poner_xml(o, "text_pos", "point", tpos)
        if ref_a: meta["conecta_inicio"] = ref_a
        if ref_b: meta["conecta_fin"] = ref_b
    else:
        p0, p1 = l["_p"]
        do.poner_extremos(o, p0, p1, l.get("_ruta"))
        if acc in ("flujo", "transicion"):
            do.poner_xml(o, "trigger", "string", l.get("evento") or ""); do.poner_xml(o, "guard", "string", l.get("guarda") or "")
            do.poner_xml(o, "action", "string", l.get("efecto") or "")
            g, ev = _textos_de_trazo(l["_ruta"], l.get("guarda") or "", (l.get("evento") or "") + (" / " + l["efecto"] if l.get("efecto") else "")) if l.get("_ruta") else ((p0[0] + 0.4, p0[1] + 0.6), ((p0[0] + p1[0]) / 2 + 0.4, (p0[1] + p1[1]) / 2))
            if not (l.get("evento") or l.get("efecto")): ev = (ev[0], ev[1] - 5)       # sin evento: que el texto vacío no estorbe
            elif l.get("guarda"): g = (ev[0], ev[1] + 0.8)                             # evento [guarda] / efecto juntos
            do.poner_xml(o, "trigger_text_pos", "point", ev); do.poner_xml(o, "guard_text_pos", "point", g)
        elif acc in ("interfaz_ofrecida", "interfaz_requerida"):
            do.poner_xml(o, "role", "enum", 0 if acc.endswith("ofrecida") else 1)
            do.poner_xml(o, "text", "text", l["texto"])
            do.poner_xml(o, "text_pos", "point", (p1[0] + 0.3, p1[1] - 0.6))
        elif acc == "conectar" and l.get("texto"):
            tp = do.texto_principal(l["tipo"])
            if tp: do.poner_xml(o, tp, "text" if do.props_tipo(l["tipo"])[tp]["t"] == "text" else "string", l["texto"])
            else:
                t = l["tag"] + "t"; mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
                l.setdefault("_tags_extra", []).append(t)
                out.append(do.a_texto(_texto_suelto(l["texto"], mx + 0.3, my - 0.2, {"tutor": t, "rol": "rotulo"}, centrado=False), f"L{t.replace('.', '_')}"))
        h0, h1 = l.get("_hint") or (None, None)
        punto = lambda h: f"@{h[0]:.3f},{h[1]:.3f}" if h else None
        meta["conecta_inicio"] = ctx.ref(l["_de"], punto(h0))
        if l.get("_a"): meta["conecta_fin"] = ctx.ref(l["_a"], punto(h1))
    do.poner_meta(o, meta)
    return [do.a_texto(o, f"L{l['tag'].replace('.', '_')}")] + out


def xml_vidas(ctx):
    """Las líneas de vida de la secuencia (una por participante con mensajes nuevos), con su caja de actividad."""
    out = []
    for v in ctx.plan.get("vidas", []):
        o = do.nuevo("UML - Lifeline")
        do.poner_xml(o, "conn_endpoints", "points", [(v["x"], v["top"]), (v["x"], v["fin"])])
        do.poner_xml(o, "obj_pos", "point", (v["x"], v["top"]))
        do.poner_xml(o, "rtop", "real", round(v["rtop"], 4)); do.poner_xml(o, "rbot", "real", round(v["rbot"], 4))
        for c in ("cpl_northwest", "cpl_southwest", "cpl_northeast", "cpl_southeast"): do.poner_xml(o, c, "int", v["n"])
        do.poner_xml(o, "draw_focus", "bool", True); do.poner_xml(o, "draw_cross", "bool", v["cruz"])
        i = v["info"]
        if "seg" in v["arriba"]: conecta = f"id:{ctx.id_tras_quitar(v['arriba']['seg']['id'])}#6"
        else: conecta = ctx.ref({"o": i["o"], "nueva": i["nuevo"]}, f"@{v['x']:.3f},{v['top']:.3f}")
        do.poner_meta(o, {"tutor": v["tag"], "conecta_inicio": conecta})
        out.append(do.a_texto(o, f"V{v['tag'].replace('.', '_')}"))
    return out


# ---------- Revisar ejercicios de estos diagramas (sin IA) ----------
REL_TIPOS = set(du.TIPOS_REL) | {"generalizacion"}
LINEA_TIPOS = {"flujo", "transicion", "mensaje"}
FAMILIA_SIN_NOMBRE = {"inicial": "inicial", "final": "final", "decision": "rombo", "fusion": "rombo", "bifurcacion": "barra", "union": "barra"}


def validar_ejercicio(e, ej):
    """Valida "objetos", "conexiones" y "mensajes" del ejercicio (además de clases y relaciones)."""
    objs = []
    for i, o in enumerate(e.get("objetos") or [], 1):
        if not isinstance(o, dict) or set(o) - {"tipo", "nombre"}: raise ValueError(f"ejercicio, objeto {i}: es {{\"tipo\": ..., \"nombre\": ...}}")
        t = _txt(o.get("tipo"), f"ejercicio, objeto {i}, tipo", 60)
        if t not in ELEMENTOS or t == "crear": t = do.tipo_dia(t, f"ejercicio, objeto {i}")
        n = _txt(o.get("nombre"), f"ejercicio, objeto {i}, nombre", 80, t in SIN_TEXTO)
        if not n and t not in SIN_TEXTO: raise ValueError(f"ejercicio, objeto {i}: falta «nombre»")
        objs.append({"tipo": t, "nombre": n})
    cons = []
    for i, c in enumerate(e.get("conexiones") or [], 1):
        if not isinstance(c, dict) or set(c) - {"tipo", "de", "a", "guarda", "evento", "efecto", "texto", "mult"}: raise ValueError(f"ejercicio, conexión {i}: campos que no conozco")
        t = _txt(c.get("tipo") or "flujo", f"ejercicio, conexión {i}, tipo", 60).lower()
        t = {"generalizacion": "herencia", "asociación": "asociacion", "transición": "transicion"}.get(t, t)
        if t not in REL_TIPOS | LINEA_TIPOS: t = do.tipo_dia(c.get("tipo"), f"ejercicio, conexión {i}")
        cons.append({"tipo": t, "de": _txt(c.get("de"), f"ejercicio, conexión {i}, de"), "a": _txt(c.get("a"), f"ejercicio, conexión {i}, a"),
                     **{f: _txt(c.get(f), f"ejercicio, conexión {i}, {f}", 80, True).strip("[]/ ") for f in ("guarda", "evento", "efecto", "texto") if c.get(f)}})
    msgs = []
    for i, m in enumerate(e.get("mensajes") or [], 1):
        if not isinstance(m, dict) or set(m) - {"de", "a", "texto", "tipo"}: raise ValueError(f"ejercicio, mensaje {i}: es {{\"de\", \"a\", \"texto\", \"tipo\"}}")
        t = _txt(m.get("tipo") or "", f"ejercicio, mensaje {i}, tipo", 20, True).lower()
        if t and t not in MENSAJE_TIPO: raise ValueError(f"ejercicio, mensaje {i}: «tipo» es sincrono, asincrono, retorno, crear o destruir")
        msgs.append({"de": _txt(m.get("de"), f"ejercicio, mensaje {i}, de"), "a": _txt(m.get("a"), f"ejercicio, mensaje {i}, a"),
                     "texto": _txt(m.get("texto"), f"ejercicio, mensaje {i}, texto", 80, True), "mtipo": MENSAJE_TIPO.get(t) if t else None})
    ej.update(objetos=objs, conexiones=cons, mensajes=msgs)
    return ej


def frase_esperada(ej):
    """La solución del ejercicio en una línea (para el tutor; no la revela entera)."""
    p = [f"{do.NOMBRES.get(o['tipo'], (o['tipo'],))[0]} «{o['nombre']}»" if o["nombre"] else do.NOMBRES.get(o["tipo"], (o["tipo"],))[0] for o in ej.get("objetos", [])]
    p += [f"{c['tipo']} {c['de']} → {c['a']}" + (f" [{c['guarda']}]" if c.get("guarda") else "") + (f" {c['evento']}" if c.get("evento") else "") for c in ej.get("conexiones", [])]
    p += [f"mensaje {m['de']} → {m['a']}: {m['texto']}" for m in ej.get("mensajes", [])]
    return "; ".join(p)


def _igual_nombre(dado, esperado):
    a, b = _n(dado), _n(esperado)
    if a == b or a.strip(":") == b.strip(":"): return True
    if ":" in esperado and esperado.strip().startswith(":"):      # «:Cajero» vale para «c: Cajero»
        return a.split(":")[-1] == b.split(":")[-1]
    return False


def _igual_texto(dado, esperado):
    a, b = _n(dado), _n(esperado)
    return a == b or a.split("(")[0] == b.split("(")[0] or a.strip("[]/") == b.strip("[]/")


def revisar(d, ej):
    """Puntos de los objetos, conexiones y mensajes esperados (mismo formato que dia_uml.revisar_varios).
    Devuelve (puntos, total, consejos)."""
    objs = [o for o in d.get("objetos", []) if o["kind"] not in ("rotulo", "linea_vida")]
    puntos, consejos, total = [], [], 0
    usados = set()
    # nombres → id del objeto del diagrama
    def buscar(nombre, kinds=None):
        cands = [o for o in objs if (_igual_nombre(o.get("texto") or "", nombre) or _igual_nombre(o.get("nombre") or "", nombre))]
        cands += [{"id": c["id"], "texto": c["nombre"], "kind": "clase", "caja": c["caja"]} for c in d["clases"] if _igual_nombre(c["nombre"], nombre)]
        if kinds: cands = sorted(cands, key=lambda o: o["kind"] not in kinds)
        return cands[0] if cands else None
    # 1) objetos con nombre
    sin_nombre_esp = {}
    for e in ej.get("objetos", []):
        t = e["tipo"]
        if t in FAMILIA_SIN_NOMBRE and not e["nombre"]:
            sin_nombre_esp.setdefault(t, []).append(e); continue
        total += 1
        kinds = {t} | ({"participante", "objeto"} if t in ("participante", "objeto") else set()) | ({"decision", "fusion"} if t in ("decision", "fusion") else set())
        o = buscar(e["nombre"], kinds)
        nombre_t = do.NOMBRES.get(t, (t,))[0]
        if not o:
            puntos.append({"ok": False, "objetivo": "", "texto": f"Falta {'el' if not nombre_t.endswith(('ón', 'a')) else 'la'} {nombre_t} «{e['nombre']}»."}); continue
        usados.add(o["id"])
        tipo_ok = o["kind"] in kinds or (t not in ELEMENTOS and o.get("tipo") == t)
        if tipo_ok: puntos.append({"ok": True, "objetivo": o.get("texto") or "", "texto": f"{nombre_t.capitalize()} «{e['nombre']}»."})
        else:
            dado = do.NOMBRES.get(o["kind"], (o.get("tipo") or o["kind"],))[0]
            puntos.append({"ok": False, "objetivo": o.get("texto") or "", "texto": f"«{e['nombre']}» debería ser {nombre_t}, no {dado}."})
    for t, lista in sin_nombre_esp.items():
        hay = [o for o in objs if o["kind"] == t or (FAMILIA_SIN_NOMBRE.get(o["kind"]) == FAMILIA_SIN_NOMBRE[t] and t in ("decision", "fusion", "bifurcacion", "union"))]
        total += 1
        nombre_t = do.NOMBRES[t]
        if len(hay) >= len(lista): puntos.append({"ok": True, "objetivo": "", "texto": f"{(nombre_t[0] if len(lista) == 1 else str(len(lista)) + ' ' + nombre_t[1]).capitalize()}."})
        else: puntos.append({"ok": False, "objetivo": "", "texto": f"Falta{'n' if len(lista) - len(hay) > 1 else ''} {len(lista) - len(hay)} {nombre_t[0] if len(lista) - len(hay) == 1 else nombre_t[1]}."})
    # 2) conexiones: los nodos sin nombre (inicio, fin, decisión...) se asignan como mejor encajen
    cons = ej.get("conexiones", [])
    especiales = sorted({x for c in cons for x in (c["de"], c["a"]) if _clave_especial(x)})
    asignacion = _asignar(especiales, cons, d, objs, buscar)
    def resolver(nombre):
        if _clave_especial(nombre): return asignacion.get(nombre)
        o = buscar(nombre); return o["id"] if o else None
    lineas = d.get("lineas", []); rels = d.get("relaciones", [])
    usadas = set()
    for c in cons:
        total += 1
        a, b = resolver(c["de"]), resolver(c["a"])
        t = c["tipo"]
        que = _nombre_con(t)
        if not a or not b:
            falta = c["de"] if not a else c["a"]
            puntos.append({"ok": False, "objetivo": "", "texto": f"Falta {que} de «{c['de']}» a «{c['a']}» (no encuentro «{falta}»)."}); continue
        if t in REL_TIPOS:
            todas = [(r, r["tipo"], r.get("de_id"), r.get("a_id")) for r in rels]
        elif t in ("flujo", "transicion"):
            todas = [(l, "flujo", l.get("de_id"), l.get("a_id")) for l in lineas if l["tipo"] == "UML - Transition"]
        else:
            todas = [(l, l["tipo"], l.get("de_id"), l.get("a_id")) for l in lineas if l["tipo"] == t]
        tt = "flujo" if t in ("flujo", "transicion") else t
        igual = [x for x in todas if x[1] == tt and x[2] == a and x[3] == b and id(x[0]) not in usadas]
        if tt == "asociacion": igual += [x for x in todas if x[1] == tt and x[2] == b and x[3] == a and id(x[0]) not in usadas]
        reves = [x for x in todas if x[1] == tt and x[2] == b and x[3] == a and id(x[0]) not in usadas]
        otro = [x for x in (todas if t in REL_TIPOS else [(r, r["tipo"], r.get("de_id"), r.get("a_id")) for r in rels] + todas)
                if {x[2], x[3]} == {a, b} and x[1] != tt and id(x[0]) not in usadas]
        objetivo = next((o.get("texto") or "" for o in objs if o["id"] == a), c["de"])
        if igual:
            x = igual[0]; usadas.add(id(x[0])); texto = None
            if tt == "flujo":
                ex = x[0]["extra"]
                for campo, nombre in (("guarda", "la guarda"), ("evento", "el evento"), ("efecto", "el efecto")):
                    quiere = c.get(campo)
                    if quiere and not _igual_texto(ex.get(campo) or "", quiere):
                        texto = (f"{que.capitalize()} de «{c['de']}» a «{c['a']}»: {nombre} debería ser «{quiere}»"
                                 + (f", no «{ex.get(campo)}»." if ex.get(campo) else "; está vacía." if campo == "guarda" else "; está vacío."))
                        break
            elif c.get("texto") and not _igual_texto(x[0].get("texto") or x[0].get("nombre") or "", c["texto"]):
                texto = f"{que.capitalize()} de «{c['de']}» a «{c['a']}» debería decir «{c['texto']}»."
            puntos.append({"ok": not texto, "objetivo": objetivo, "texto": texto or f"{que.capitalize()}: {c['de']} → {c['a']}" + (f" [{c['guarda']}]" if c.get("guarda") else "") + "."})
        elif reves:
            usadas.add(id(reves[0][0]))
            puntos.append({"ok": False, "objetivo": objetivo, "texto": f"{que.capitalize()} entre «{c['de']}» y «{c['a']}» está al revés: la flecha va hacia «{c['a']}»."})
        elif otro:
            usadas.add(id(otro[0][0]))
            puntos.append({"ok": False, "objetivo": objetivo, "texto": f"Entre «{c['de']}» y «{c['a']}» pusiste {_nombre_con(otro[0][1])}; debería ser {que}."
                                                                    + (" («include»: el caso base siempre usa al otro; «extend»: el otro amplía al base a veces)" if {otro[0][1], tt} == {"include", "extend"} else "")})
        else:
            puntos.append({"ok": False, "objetivo": objetivo, "texto": f"Falta {que} de «{c['de']}» a «{c['a']}»" + (f" con la guarda [{c['guarda']}]" if c.get("guarda") else "") + "."})
    # 3) mensajes, en orden de arriba abajo
    msgs = ej.get("mensajes", [])
    if msgs:
        dados = do.mensajes_en_orden(d); j = 0
        for m in msgs:
            total += 1
            def coincide(x, de, a): return _igual_nombre(x.get("de") or "", de) and _igual_nombre(x.get("a") or "", a)
            def mismo_texto(x): return not m["texto"] or m["mtipo"] in (1, 2) or _igual_texto(x.get("texto") or "", m["texto"])
            idx = next((i for i in range(j, len(dados)) if coincide(dados[i], m["de"], m["a"]) and mismo_texto(dados[i])), None)
            antes = next((i for i in range(0, j) if coincide(dados[i], m["de"], m["a"]) and mismo_texto(dados[i])), None)
            nombre = f"«{m['texto']}»" if m["texto"] else f"de «{m['de']}» a «{m['a']}»"
            if idx is not None:
                x = dados[idx]; j = idx + 1
                mt = x["extra"].get("mtipo")
                if m["mtipo"] is not None and mt != m["mtipo"] and not (m["mtipo"] in (0, 3) and mt == 6):
                    puntos.append({"ok": False, "objetivo": x.get("texto") or "", "texto": f"El mensaje {nombre} debería ser {NOMBRE_TIPO_MSG[m['mtipo']]}, no {NOMBRE_TIPO_MSG.get(mt, '?')}"
                                                                               + (" (línea discontinua)." if m["mtipo"] == 4 else ".")})
                else: puntos.append({"ok": True, "objetivo": x.get("texto") or "", "texto": f"Mensaje {nombre}: {m['de']} → {m['a']}."})
            elif antes is not None:
                puntos.append({"ok": False, "objetivo": dados[antes].get("texto") or "", "texto": f"El mensaje {nombre} está fuera de orden: va después de los anteriores (más abajo)."})
            elif any(coincide(x, m["a"], m["de"]) and mismo_texto(x) for x in dados):
                x = next(x for x in dados if coincide(x, m["a"], m["de"]) and mismo_texto(x))
                puntos.append({"ok": False, "objetivo": x.get("texto") or "", "texto": f"El mensaje {nombre} va al revés: sale de «{m['de']}» y llega a «{m['a']}»."})
            elif m["texto"] and any(_igual_texto(x.get("texto") or "", m["texto"]) for x in dados):
                x = next(x for x in dados if _igual_texto(x.get("texto") or "", m["texto"]))
                puntos.append({"ok": False, "objetivo": x.get("texto") or "", "texto": f"El mensaje {nombre} debería ir de «{m['de']}» a «{m['a']}», no de «{x.get('de')}» a «{x.get('a')}»."})
            elif any(coincide(x, m["de"], m["a"]) for x in dados[j:]):
                x = next(x for x in dados[j:] if coincide(x, m["de"], m["a"]))
                puntos.append({"ok": False, "objetivo": x.get("texto") or "", "texto": f"El mensaje de «{m['de']}» a «{m['a']}» debería decir «{m['texto']}», no «{x.get('texto')}»."})
            else:
                puntos.append({"ok": False, "objetivo": "", "texto": f"Falta el mensaje {nombre} de «{m['de']}» a «{m['a']}»."})
    sueltas = [l for l in d.get("lineas", []) if l["tipo"] in ("UML - Transition", "UML - Message") and (not l.get("de_id") or not l.get("a_id")) and l["extra"].get("mtipo") != 6]
    if sueltas and (cons or msgs): consejos.append(f"Hay {len(sueltas)} flecha(s) con un extremo suelto: arrastra la punta hasta su objeto hasta que se pegue.")
    if ej.get("objetos"):
        esperados = {_n(e["nombre"]) for e in ej["objetos"] if e["nombre"]}
        sobran = [o["texto"] for o in objs if o.get("texto") and o["kind"] in ELEMENTOS and o["kind"] not in CONTENEDORES
                  and o["id"] not in usados and _n(o["texto"]) not in esperados and o["kind"] != "objeto"]
        if sobran: consejos.append("Sobra: " + ", ".join(f"«{s}»" for s in sobran[:6]) + ".")
    return puntos, total, consejos


def _clave_especial(nombre):
    n = _n(nombre)
    return re.match(r"^(inicio|inicial|fin|final|decision|fusion|bifurcacion|union)\d*$", n) is not None


def _kind_especial(nombre):
    n = re.sub(r"\d+$", "", _n(nombre))
    return {"inicio": "inicial", "inicial": "inicial", "fin": "final", "final": "final"}.get(n, n)


def _asignar(especiales, cons, d, objs, buscar):
    """Qué nodo sin nombre del diagrama es cada «inicio», «fin», «decision», «decision2»... (el reparto que más conexiones cumple)."""
    if not especiales: return {}
    # los que el tutor creó con ese nombre (meta nombre) se respetan
    fijo = {}
    for e in especiales:
        o = next((o for o in objs if _n(o.get("nombre")) == _n(e)), None)
        if o: fijo[e] = o["id"]
    libres = [e for e in especiales if e not in fijo]
    pares = {(l.get("de_id"), l.get("a_id")) for l in d.get("lineas", [])} | {(r.get("de_id"), r.get("a_id")) for r in d.get("relaciones", [])}
    def puntua(asig):
        m = dict(fijo, **asig)
        def res(n): return m.get(n) if _clave_especial(n) else (buscar(n) or {}).get("id")
        return sum(1 for c in cons if (res(c["de"]), res(c["a"])) in pares)
    mejor, mejor_p = {}, -1
    grupos = {}
    for e in libres: grupos.setdefault(FAMILIA_SIN_NOMBRE.get(_kind_especial(e), _kind_especial(e)), []).append(e)
    opciones = []
    for fam, es in grupos.items():
        cands = [o["id"] for o in objs if FAMILIA_SIN_NOMBRE.get(o["kind"]) == fam and o["id"] not in fijo.values()]
        perms = list(itertools.islice(itertools.permutations(cands + [None] * len(es), len(es)), 2000))
        opciones.append([dict(zip(es, p)) for p in perms] or [{}])
    for combo in itertools.islice(itertools.product(*opciones), 5000):
        asig = {}
        for c in combo: asig.update({k: v for k, v in c.items() if v})
        p = puntua(asig)
        if p > mejor_p: mejor, mejor_p = asig, p
    return dict(fijo, **mejor)


def _nombre_con(t):
    return {"flujo": "el flujo", "transicion": "la transición", "asociacion": "una asociación", "herencia": "una generalización (herencia)",
            "include": "un «include»", "extend": "un «extend»", "dependencia": "una dependencia", "realizacion": "una realización",
            "agregacion": "una agregación", "composicion": "una composición"}.get(t, f"una «{t}»")
