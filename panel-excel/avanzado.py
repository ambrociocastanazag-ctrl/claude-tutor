"""Lo avanzado del panel de Excel (lo usa motor.py; el formato está en README.md):
- Comprobar de objetos («pide» en un turno): gráfico, tabla, tabla dinámica, formato condicional, validación, nombres,
  orden, filtros, inmovilizar y formato de número, sin IA, con puntos ✔/✘ y errores típicos («si»).
- Inventario de la hoja: lo que hay además de celdas, para que al cambiar de paso se quite lo que no es del paso y se
  conserve (o se rehaga) lo que hizo la persona.
- Power Query con límite: consultas M con orígenes seguros (tablas del libro y archivos de la carpeta de datos del curso).
- Herramientas de análisis: Buscar objetivo, tablas de datos, escenarios y Solver (solo si el complemento está activado).
Todo se usa desde el hilo de Excel (COM)."""
import os, re
import pythoncom
import motor as M

E = pythoncom.Empty


def _t(f, d=None):
    try: return f()
    except Exception: return d


def _norm(s):
    return " ".join(str(s if s is not None else "").split()).casefold()


def _dir(a):
    return str(a).replace("$", "")


# ---------- Inventario: lo que hay en la hoja además de celdas ----------
TIPO_COMENTARIO = 4


def _es_marca(nombre):
    return nombre.startswith(("tutor_", "check_"))


def _rango_tabla(lo):
    """El rango de una tabla sin la fila de totales (encabezados y datos), como 'H1:I5'."""
    r = lo.Range; f = r.Rows.Count - (1 if lo.ShowTotals else 0)
    return M.dir_((r.Row, r.Column, r.Row + f - 1, r.Column + r.Columns.Count - 1))


def describir_dinamica(pt):
    filtro = lambda c: [f.SourceName if _t(lambda: f.SourceName) else f.Name for f in c if f.Name not in ("Valores", "Values", "Σ Valores")]
    return {"nombre": pt.Name, "origen": str(_t(lambda: pt.SourceData, "")), "destino": _dir(pt.TableRange1.Cells(1).Address),
            "filas": filtro(pt.RowFields), "columnas": filtro(pt.ColumnFields), "filtros": filtro(pt.PageFields),
            "valores": [(f.SourceName, f.Name, f.Function) for f in pt.DataFields]}


def describir_fc(r):
    d = {"tipo": r.Type, "rango": _dir(r.AppliesTo.Address)}
    for k, p in (("operador", "Operator"), ("f1", "Formula1"), ("f2", "Formula2"), ("texto", "Text"), ("texto_op", "TextOperator"),
                 ("rank", "Rank"), ("top", "TopBottom"), ("percent", "Percent"), ("dupe", "DupeUnique"), ("encima", "AboveBelow")):
        v = _t(lambda: getattr(r, p))
        if v is not None: d[k] = v
    if d["tipo"] in (1, 2, 5, 8, 9, 12):
        d["relleno"] = _t(lambda: r.Interior.Color); d["letra"] = _t(lambda: r.Font.Color); d["negrita"] = _t(lambda: r.Font.Bold)
    if d["tipo"] == 3: d["colores"] = _t(lambda: r.ColorScaleCriteria.Count, 3)
    return d


def reglas_fc(ws):
    """Las reglas de formato condicional de la hoja (sin las marcas del panel), como (regla COM, descripción)."""
    out, fcs = [], ws.Cells.FormatConditions
    for i in range(1, fcs.Count + 1):
        r = fcs(i)
        if _t(lambda: r.Formula1) in M.FORMULA_MARCA.values(): continue
        d = _t(lambda: describir_fc(r))
        if d: out.append((r, d))
    return out


def validaciones(ws, limite=400):
    """{(tipo, operador, f1, f2, alerta): [celdas]} de la validación de datos de la hoja."""
    grupos = {}
    try: areas = ws.Cells.SpecialCells(-4174).Areas            # xlCellTypeAllValidation (falla si no hay)
    except Exception: return grupos
    n = 0
    for a in areas:
        for c in a.Cells:
            n += 1
            if n > limite: return grupos
            v = c.Validation
            k = (_t(lambda: v.Type), _t(lambda: v.Operator), _t(lambda: v.Formula1, ""), _t(lambda: v.Formula2, ""), _t(lambda: v.AlertStyle),
                 _t(lambda: v.IgnoreBlank), _t(lambda: v.InCellDropdown))
            grupos.setdefault(k, []).append((c.Row, c.Column))
    return grupos


def inventario(ws):
    """{clave: descripción} de lo que hay en la hoja además de celdas, sin las marcas del panel ni lo que puso la
    lección (formas «lec_»). Las claves no dependen de nombres que Excel cambia al rehacer (tablas y dinámicas por su
    sitio, formato condicional y validación por su regla)."""
    out = {}
    for s in ws.Shapes:
        n = s.Name
        if _es_marca(n) or n.startswith("lec_") or _t(lambda: s.Type) == TIPO_COMENTARIO: continue
        out[("forma", n)] = None
    for lo in ws.ListObjects:
        if _t(lambda: lo.SourceType) == 3: continue          # las de Power Query las rehace su consulta
        out[("tabla", _dir(lo.Range.Address))] = {"nombre": lo.Name, "rango": _rango_tabla(lo), "estilo": _t(lambda: lo.TableStyle.Name),
                                                 "totales": bool(lo.ShowTotals)}
    for pt in ws.PivotTables():
        d = _t(lambda: describir_dinamica(pt))
        if d: out[("dinamica", d["destino"])] = d
    vistos = {}
    for _, d in reglas_fc(ws):
        k = ("fc", d["tipo"], d["rango"], str(d.get("f1", "")))
        vistos[k] = vistos.get(k, 0) + 1
        out[k + (vistos[k],)] = d
    for regla, celdas in validaciones(ws).items():
        out[("validacion",) + tuple(str(x) for x in regla)] = {"regla": regla, "celdas": celdas}
    return out


def recrear(libro, ws, clave, d):
    """Vuelve a poner en la hoja (rehecha) algo que hizo la persona: tabla, dinámica, formato condicional o validación.
    Las formas y gráficos no hace falta: no se borran al rehacer. Devuelve el motivo si no se pudo (o None)."""
    tipo = clave[0]
    try:
        if tipo == "tabla":
            r = M.rect(d["rango"])
            for lo in ws.ListObjects:
                q = lo.Range
                if not (r[2] < q.Row or q.Row + q.Rows.Count - 1 < r[0] or r[3] < q.Column or q.Column + q.Columns.Count - 1 < r[1]): return "se monta sobre otra tabla"
            lo = ws.ListObjects.Add(1, ws.Range(d["rango"]), E, 1)
            if not any(x.Name.lower() == d["nombre"].lower() for s in libro.wb.Worksheets for x in s.ListObjects): lo.Name = d["nombre"]
            if d.get("estilo"): lo.TableStyle = d["estilo"]
            if d.get("totales"): lo.ShowTotals = True
        elif tipo == "dinamica":
            src = d["origen"]
            fuente = libro.wb.Worksheets(src.split("!")[0].strip("'")).Range(M._a1(src)) if "!" in src else src
            pt = libro.wb.PivotCaches().Create(1, fuente).CreatePivotTable(ws.Range(d["destino"]), d["nombre"])
            for campo in d["filas"]: pt.PivotFields(campo).Orientation = 1
            for campo in d["columnas"]: pt.PivotFields(campo).Orientation = 2
            for campo in d["filtros"]: pt.PivotFields(campo).Orientation = 3
            for fuente_c, titulo, fn in d["valores"]: pt.AddDataField(pt.PivotFields(fuente_c), titulo, fn)
        elif tipo == "fc":
            rg = ws.Range(d["rango"].replace(",", libro.xl.International[4])); t = d["tipo"]
            if t in (1, 2): fc = rg.FormatConditions.Add(t, d.get("operador", E) if t == 1 else E, d.get("f1", E), d.get("f2", E) if t == 1 and d.get("f2") else E)
            elif t == 9: fc = rg.FormatConditions.Add(9, E, E, E, d.get("texto", ""), d.get("texto_op", 0))
            elif t == 3: fc = rg.FormatConditions.AddColorScale(d.get("colores", 3))
            elif t == 4: fc = rg.FormatConditions.AddDatabar()
            elif t == 6: fc = rg.FormatConditions.AddIconSetCondition()
            elif t == 5:
                fc = rg.FormatConditions.AddTop10(); fc.TopBottom = d.get("top", 1); fc.Rank = d.get("rank", 10); fc.Percent = bool(d.get("percent"))
            elif t == 8: fc = rg.FormatConditions.AddUniqueValues(); fc.DupeUnique = d.get("dupe", 1)
            elif t == 12: fc = rg.FormatConditions.AddAboveAverage(); fc.AboveBelow = d.get("encima", 0)
            else: return "ese tipo de formato condicional no se puede rehacer"
            if t in (1, 2, 5, 8, 9, 12):
                if d.get("relleno") not in (None, 0) or t == 1: _t(lambda: setattr(fc.Interior, "Color", d["relleno"]) if d.get("relleno") is not None else None)
                if d.get("letra") is not None: _t(lambda: setattr(fc.Font, "Color", d["letra"]))
                if d.get("negrita"): _t(lambda: setattr(fc.Font, "Bold", True))
        elif tipo == "validacion":
            tv, op, f1, f2, alerta, blancos, lista = d["regla"]
            for (f, c) in d["celdas"]:
                v = ws.Cells(f, c).Validation; v.Delete()
                v.Add(tv, alerta if alerta is not None else 1, op if op is not None else 1, f1 or E, f2 or E)
                if blancos is not None: v.IgnoreBlank = blancos
                if lista is not None and tv == 3: v.InCellDropdown = lista
    except Exception as e: return M.motivo(e, 120)
    return None


# ---------- Comprobar de objetos («pide») ----------
TIPOS_GRAFICO = {"columnas": {51, 52, 53, 54, 55, 56, -4100}, "barras": {57, 58, 59, 60, 61, 62}, "lineas": {4, 65, 63, 64, 66, 67, -4101},
                 "circular": {5, 69, 68, 70, 71, -4102}, "anillo": {-4120, 80}, "dispersion": {-4169, 74, 72, 73, 75},
                 "area": {1, 76, 77, 78, 79, -4098}, "radial": {-4151, 81, 82}, "burbujas": {15, 87}}
NOMBRE_TIPO = {"columnas": "de columnas", "barras": "de barras", "lineas": "de líneas", "circular": "circular", "anillo": "de anillo",
               "dispersion": "de dispersión", "area": "de áreas", "radial": "radial", "burbujas": "de burbujas"}
FUNCION = {"suma": -4157, "cuenta": -4112, "contar": -4112, "promedio": -4106, "maximo": -4136, "max": -4136, "minimo": -4139, "min": -4139,
           "producto": -4149, "contar_numeros": -4113}
NOMBRE_FUNCION = {-4157: "suma", -4112: "cuenta", -4106: "promedio", -4136: "máximo", -4139: "mínimo", -4149: "producto", -4113: "cuenta de números"}
TIPOS_FC = {"valor": 1, "formula": 2, "escala": 3, "barras": 4, "superiores": 5, "iconos": 6, "duplicados": 8, "unicos": 8, "texto": 9, "promedio": 12}
NOMBRE_FC = {1: "valor de celda", 2: "fórmula", 3: "escala de colores", 4: "barras de datos", 5: "superiores/inferiores", 6: "iconos",
             8: "duplicados o únicos", 9: "texto que contiene", 12: "sobre/bajo el promedio"}
OPERADORES = {"entre": 1, "fuera": 2, "igual": 3, "distinto": 4, "mayor": 5, "menor": 6, "mayor_igual": 7, "menor_igual": 8,
              ">": 5, "<": 6, "=": 3, "<>": 4, ">=": 7, "<=": 8}
TIPOS_VAL = {"cualquiera": 0, "entero": 1, "decimal": 2, "lista": 3, "fecha": 4, "hora": 5, "longitud": 6, "personalizada": 7}
NOMBRE_VAL = {v: k for k, v in TIPOS_VAL.items()}
PIDE = ("grafico", "tabla", "dinamica", "formato_condicional", "validacion", "nombre", "orden", "filtro", "inmovilizar", "formato_numero")
CAMPOS_PIDE = {
    "grafico": {"tipo", "datos", "series", "titulo", "eje_x", "eje_y", "leyenda", "existente"},
    "tabla": {"rango", "nombre", "columnas", "totales", "estilo", "existente"},
    "dinamica": {"origen", "filas", "columnas", "valores", "filtros", "en", "nombre", "existente"},
    "formato_condicional": {"rango", "tipo", "operador", "valor", "valor2", "formula", "texto"},
    "validacion": {"rango", "tipo", "lista", "operador", "min", "max", "formula"},
    "nombre": {"nombre", "refiere", "valor"},
    "orden": {"rango", "por", "orden", "encabezado"},
    "filtro": {"tabla", "rango", "columna", "igual_a", "mayor_que", "menor_que"},
    "inmovilizar": {"celda"},
    "formato_numero": {"rango", "es", "codigo", "decimales"},
}


def validar_pide(pide, donde="turno"):
    """Revisa «pide» (y los «si» de los errores típicos) sin Excel. Lanza ValueError con el motivo."""
    if not isinstance(pide, list) or not pide or len(pide) > 12: raise ValueError(f"{donde}: «pide» es una lista de 1 a 12 cosas [{{\"grafico\": {{...}}}}, ...]")
    for k, item in enumerate(pide, 1):
        if not isinstance(item, dict) or len(item) != 1 or next(iter(item)) not in PIDE:
            raise ValueError(f"{donde}, pide {k}: cada cosa es {{\"<tipo>\": {{...}}}} con un tipo de: {', '.join(PIDE)}")
        tipo, spec = next(iter(item.items()))
        if not isinstance(spec, dict): raise ValueError(f"{donde}, pide {k} ({tipo}): tiene que ser un objeto {{...}}")
        sobra = set(spec) - CAMPOS_PIDE[tipo]
        if sobra: raise ValueError(f"{donde}, pide {k} ({tipo}): campos que no conozco: {', '.join(sorted(sobra))}")
        for c in ("rango", "datos", "en", "celda"):
            if c in spec and not (tipo == "dinamica" and c == "origen"): M.rect(spec[c])
        if tipo == "grafico" and "tipo" in spec:
            tipos = spec["tipo"] if isinstance(spec["tipo"], list) else [spec["tipo"]]
            if any(t not in TIPOS_GRAFICO and not isinstance(t, int) for t in tipos): raise ValueError(f"{donde}, pide {k}: tipos de gráfico: {', '.join(TIPOS_GRAFICO)}")
        if tipo == "formato_condicional" and spec.get("tipo") not in (None, *TIPOS_FC): raise ValueError(f"{donde}, pide {k}: tipos: {', '.join(TIPOS_FC)}")
        if tipo == "validacion" and spec.get("tipo") not in (None, *TIPOS_VAL): raise ValueError(f"{donde}, pide {k}: tipos: {', '.join(TIPOS_VAL)}")
        if tipo in ("formato_condicional", "validacion") and spec.get("operador") not in (None, *OPERADORES): raise ValueError(f"{donde}, pide {k}: operadores: {', '.join(OPERADORES)}")
        if tipo == "orden" and ("rango" not in spec or "por" not in spec): raise ValueError(f"{donde}, pide {k} (orden): faltan «rango» y «por»")
        if tipo == "filtro" and "columna" not in spec: raise ValueError(f"{donde}, pide {k} (filtro): falta «columna»")
        if tipo == "nombre" and not isinstance(spec.get("nombre"), str): raise ValueError(f"{donde}, pide {k} (nombre): falta «nombre»")
        if tipo == "formato_numero" and "rango" not in spec: raise ValueError(f"{donde}, pide {k} (formato_numero): falta «rango»")
        for v in spec.values():
            if isinstance(v, str): M._texto_seguro(v, f"{donde}, pide {k}", 500)


def _local(hoja, formula):
    """Una fórmula en inglés como la escribe este Excel (para comparar con lo que leen FormatConditions y Validation)."""
    libro = getattr(hoja, "libro", None)
    if libro is None or not isinstance(formula, str) or not formula.startswith("="): return formula
    c = libro._celda_aux(); c.Formula = formula
    try: return c.FormulaLocal
    finally: c.ClearContents()


def _numero(s):
    try: return float(str(s).lstrip("=").replace(",", "."))
    except (TypeError, ValueError): return None


def _celdas_serie(formula, hoja_nombre):
    """Las celdas (de esta hoja) que usa una serie: =SERIES(nombre, categorías, valores, orden)."""
    out = set()
    for m in re.finditer(r"(?:'((?:[^']|'')+)'|([^'!,()=]+))!(\$?[A-Z]{1,3}\$?\d+(?::\$?[A-Z]{1,3}\$?\d+)?)", formula):
        h = (m.group(1) or m.group(2) or "").replace("''", "'").strip()
        if h.lower() == hoja_nombre.lower(): out |= M.celdas_de(M.rect(m.group(3)))
    return out


def _punto(ok, texto): return {"ok": bool(ok), "texto": texto}


def _base(hoja, clave):
    return getattr(hoja, "base", {}).get(clave, set())


def chk_grafico(hoja, s):
    ws = hoja.ws
    cands = [co for co in ws.ChartObjects() if s.get("existente") or co.Name not in _base(hoja, "graficos")]
    if not cands: return {"hallado": False, "puntos": [_punto(False, "Falta el gráfico" + (f" con los datos de {s['datos']}" if s.get("datos") else "") + ".")]}
    mejor = None
    for co in cands:
        ch = co.Chart; pts = [_punto(True, "Hay un gráfico.")]
        if "tipo" in s:
            tipos = s["tipo"] if isinstance(s["tipo"], list) else [s["tipo"]]
            codigos = set().union(*[TIPOS_GRAFICO.get(t, {t}) for t in tipos])
            actual = M.TIPOS_GRAFICO.get(ch.ChartType, f"de tipo {ch.ChartType}")
            quiere = " o ".join(NOMBRE_TIPO.get(t, str(t)) for t in tipos)
            pts.append(_punto(ch.ChartType in codigos, f"Gráfico {quiere}." if ch.ChartType in codigos else f"El gráfico es {actual}: aquí va uno {quiere}."))
        series = [_t(lambda i=i: ch.SeriesCollection(i).Formula, "") for i in range(1, ch.SeriesCollection().Count + 1)]
        if "datos" in s:
            f1, c1, f2, c2 = M.rect(s["datos"]); esp = M.celdas_de((f1, c1, f2, c2))
            usa = set().union(*[_celdas_serie(f, ws.Name) for f in series]) if series else set()
            nucleo = M.celdas_de((f1 + 1, c1 + 1, f2, c2)) if f2 > f1 and c2 > c1 else esp
            cats = (f2 > f1 and c2 > c1) and not (M.celdas_de((f1 + 1, c1, f2, c1)) <= usa or M.celdas_de((f1, c1 + 1, f1, c2)) <= usa)
            ok = bool(usa) and usa <= esp and nucleo <= usa and not cats
            if ok: txt = f"Usa los datos de {s['datos']}."
            elif not usa: txt = f"El gráfico no tiene datos de esta hoja: selecciona {s['datos']} y vuelve a crearlo."
            elif not usa <= esp: txt = f"El gráfico usa celdas fuera de {s['datos']}: selecciona solo {s['datos']}."
            elif cats: txt = f"Faltan las categorías (la primera columna de {s['datos']}): selecciona todo {s['datos']}, con los encabezados."
            else: txt = f"Al gráfico le faltan datos de {s['datos']}: selecciona el rango entero."
            pts.append(_punto(ok, txt))
        if "series" in s:
            pts.append(_punto(len(series) == s["series"], f"Tiene {M._cuantas(len(series), 'serie')}" + ("." if len(series) == s["series"] else f": deberían ser {s['series']}.")))
        if "titulo" in s:
            tiene = bool(ch.HasTitle); txt = _t(lambda: ch.ChartTitle.Text, "") if tiene else ""
            if s["titulo"] is True: pts.append(_punto(tiene, "Tiene título." if tiene else "Falta el título del gráfico."))
            elif s["titulo"] is False: pts.append(_punto(not tiene, "Sin título." if not tiene else "Este gráfico va sin título."))
            else: pts.append(_punto(tiene and _norm(txt) == _norm(s["titulo"]), f"Título «{s['titulo']}»." if tiene and _norm(txt) == _norm(s["titulo"])
                                    else (f"El título dice «{txt}»: debería decir «{s['titulo']}»." if tiene else f"Falta el título «{s['titulo']}».")))
        for clave, eje, nombre in (("eje_x", 1, "horizontal"), ("eje_y", 2, "vertical")):
            if clave not in s: continue
            tiene = bool(_t(lambda: ch.Axes(eje).HasTitle, False)); txt = _t(lambda: ch.Axes(eje).AxisTitle.Text, "") if tiene else ""
            if s[clave] is True: pts.append(_punto(tiene, f"El eje {nombre} tiene título." if tiene else f"Falta el título del eje {nombre}."))
            else: pts.append(_punto(tiene and _norm(txt) == _norm(s[clave]), f"Eje {nombre}: «{s[clave]}»." if tiene and _norm(txt) == _norm(s[clave])
                                    else (f"El eje {nombre} dice «{txt}»: debería decir «{s[clave]}»." if tiene else f"Falta el título del eje {nombre}: «{s[clave]}».")))
        if "leyenda" in s:
            tiene = bool(ch.HasLegend)
            pts.append(_punto(tiene == bool(s["leyenda"]), ("Con leyenda." if tiene else "Sin leyenda.") if tiene == bool(s["leyenda"])
                              else ("Quítale la leyenda: con una sola serie no hace falta." if tiene else "Falta la leyenda.")))
        if mejor is None or sum(p["ok"] for p in pts) > sum(p["ok"] for p in mejor): mejor = pts
    return {"hallado": True, "puntos": mejor, "marcar": s.get("datos")}


def chk_tabla(hoja, s):
    ws = hoja.ws
    los = [lo for lo in ws.ListObjects if s.get("existente") or lo.Name not in _base(hoja, "tablas")]
    if "nombre" in s and any(lo.Name.lower() == s["nombre"].lower() for lo in los): los = [lo for lo in los if lo.Name.lower() == s["nombre"].lower()]
    elif "rango" in s:
        r = M.rect(s["rango"])
        cerca = [lo for lo in los if not (r[2] < lo.Range.Row or lo.Range.Row + lo.Range.Rows.Count - 1 < r[0]
                                          or r[3] < lo.Range.Column or lo.Range.Column + lo.Range.Columns.Count - 1 < r[1])]
        los = cerca or los
    if not los: return {"hallado": False, "puntos": [_punto(False, "Falta la tabla" + (f" en {s['rango']}" if s.get("rango") else "") + " (Ctrl+T).")], "marcar": s.get("rango")}
    lo = los[0]; pts = [_punto(True, f"Hay una tabla ({lo.Name}).")]
    if "rango" in s:
        actual = _rango_tabla(lo); ok = M.rect(actual) == M.rect(s["rango"])
        pts.append(_punto(ok, f"La tabla ocupa {s['rango']}." if ok else f"La tabla ocupa {actual}: debería ocupar {s['rango']} (con los encabezados)."))
    if "nombre" in s:
        ok = lo.Name.lower() == s["nombre"].lower()
        pts.append(_punto(ok, f"Se llama «{s['nombre']}»." if ok else f"La tabla se llama «{lo.Name}»: ponle «{s['nombre']}» (Diseño de tabla → Nombre)."))
    if "columnas" in s:
        cab = [str(v) for v in M._como_matriz(lo.HeaderRowRange.Value)[0]]
        faltan = [c for c in s["columnas"] if _norm(c) not in {_norm(x) for x in cab}]
        pts.append(_punto(not faltan, "Tiene las columnas que hacen falta." if not faltan else f"Faltan las columnas: {', '.join(faltan)}."))
    if "totales" in s:
        if isinstance(s["totales"], dict):
            for colname, fn in s["totales"].items():
                try: calc = lo.ListColumns(colname).TotalsCalculation
                except Exception: pts.append(_punto(False, f"No hay una columna «{colname}» en la tabla.")); continue
                ok = bool(lo.ShowTotals) and calc == M.TOTALES.get(fn, -1)
                pts.append(_punto(ok, f"Total de «{colname}»: {fn}." if ok else (f"En la fila de totales, «{colname}» debería ser {fn}." if lo.ShowTotals else "Falta la fila de totales.")))
        else:
            ok = bool(lo.ShowTotals) == bool(s["totales"])
            pts.append(_punto(ok, ("Con fila de totales." if lo.ShowTotals else "Sin fila de totales.") if ok else ("Falta la fila de totales." if s["totales"] else "Esta tabla va sin fila de totales.")))
    if "estilo" in s:
        actual = _t(lambda: lo.TableStyle.Name, ""); ok = _norm(actual) == _norm(s["estilo"])
        pts.append(_punto(ok, f"Estilo {s['estilo']}." if ok else f"El estilo es {actual}: debería ser {s['estilo']}."))
    return {"hallado": True, "puntos": pts, "marcar": _dir(lo.Range.Address)}


def _origen(src, ws_nombre):
    """('hoja', 'A1:C9') o ('', 'NombreTabla') para comparar el origen de una dinámica."""
    src = str(src)
    if "!" in src: return src.split("!")[0].strip("'").lower(), M.dir_(M.rect(M._a1(src)))
    if M.REF.match(src.replace("$", "").upper()): return ws_nombre.lower(), M.dir_(M.rect(src))
    return "", src.lower()


def chk_dinamica(hoja, s):
    ws = hoja.ws
    pts_ = [pt for pt in ws.PivotTables() if s.get("existente") or pt.Name not in _base(hoja, "dinamicas")]
    if "nombre" in s: pts_ = [pt for pt in pts_ if pt.Name.lower() == s["nombre"].lower()] or pts_
    if not pts_: return {"hallado": False, "puntos": [_punto(False, "Falta la tabla dinámica (Insertar → Tabla dinámica).")]}
    pt = pts_[0]; d = describir_dinamica(pt); pts = [_punto(True, f"Hay una tabla dinámica ({pt.Name}).")]
    if "origen" in s:
        ok = _origen(d["origen"], ws.Name) == _origen(s["origen"], ws.Name)
        pts.append(_punto(ok, f"Sus datos son {s['origen']}." if ok else f"Los datos de la dinámica son {_origen(d['origen'], ws.Name)[1]}: deberían ser {s['origen']}."))
    for clave, nombre in (("filas", "Filas"), ("columnas", "Columnas"), ("filtros", "Filtros")):
        if clave not in s: continue
        quiere, hay = [_norm(x) for x in s[clave]], [_norm(x) for x in d[clave]]
        ok = quiere == hay
        if ok: txt = f"En {nombre}: {', '.join(s[clave]) or 'nada'}."
        else:
            faltan = [x for x in s[clave] if _norm(x) not in hay]; sobran = [x for x in d[clave] if _norm(x) not in quiere]
            txt = f"En {nombre} " + ("; ".join(([f"falta {', '.join(faltan)}"] if faltan else []) + ([f"sobra {', '.join(sobran)}"] if sobran else [])) or f"el orden debería ser {', '.join(s[clave])}") + "."
        pts.append(_punto(ok, txt))
    if "valores" in s:
        for v in s["valores"]:
            campo, fn = (v, None) if isinstance(v, str) else (v.get("campo"), v.get("funcion"))
            hay = [(src, f) for src, _, f in d["valores"] if _norm(src) == _norm(campo)]
            if not hay: pts.append(_punto(False, f"En Valores falta «{campo}».")); continue
            ok = fn is None or any(f == FUNCION.get(fn) for _, f in hay)
            pts.append(_punto(ok, f"En Valores: {fn or 'resumen'} de «{campo}»." if ok else f"«{campo}» se resume con {NOMBRE_FUNCION.get(hay[0][1], hay[0][1])}: debería ser {fn} (Configuración de campo de valor)."))
    if "en" in s:
        ok = M.rect(d["destino"])[:2] == M.rect(s["en"])[:2] or M.rect(_dir(pt.TableRange2.Cells(1).Address))[:2] == M.rect(s["en"])[:2]
        pts.append(_punto(ok, f"Empieza en {s['en']}." if ok else f"La dinámica empieza en {d['destino']}: debería empezar en {s['en']}."))
    return {"hallado": True, "puntos": pts, "marcar": _dir(pt.TableRange1.Address)}


def chk_formato_condicional(hoja, s):
    ws = hoja.ws; base = _base(hoja, "fc")
    reglas = [(r, d) for r, d in reglas_fc(ws) if (d["tipo"], d["rango"], str(d.get("f1", ""))) not in base]
    if "rango" in s:
        r0 = M.rect(s["rango"])
        exactas = [(r, d) for r, d in reglas if "," not in d["rango"] and M.rect(d["rango"]) == r0]
        cerca = [(r, d) for r, d in reglas if any(not (r0[2] < q[0] or q[2] < r0[0] or r0[3] < q[1] or q[3] < r0[1])
                                                  for q in [M.rect(x) for x in d["rango"].split(",")])]
        reglas = exactas or cerca
    if "tipo" in s:
        del_tipo = [x for x in reglas if x[1]["tipo"] == TIPOS_FC[s["tipo"]]]
        reglas = del_tipo or reglas
    if not reglas: return {"hallado": False, "puntos": [_punto(False, "Falta el formato condicional" + (f" en {s['rango']}" if s.get("rango") else "") + " (Inicio → Formato condicional).")], "marcar": s.get("rango")}
    _, d = reglas[0]; pts = [_punto(True, f"Hay formato condicional ({NOMBRE_FC.get(d['tipo'], d['tipo'])}).")]
    if "rango" in s:
        ok = "," not in d["rango"] and M.rect(d["rango"]) == M.rect(s["rango"])
        pts.append(_punto(ok, f"Se aplica a {s['rango']}." if ok else f"Se aplica a {d['rango']}: debería ser {s['rango']}."))
    if "tipo" in s:
        ok = d["tipo"] == TIPOS_FC[s["tipo"]]
        pts.append(_punto(ok, f"Regla de {NOMBRE_FC[TIPOS_FC[s['tipo']]]}." if ok else f"La regla es de {NOMBRE_FC.get(d['tipo'], d['tipo'])}: aquí va una de {NOMBRE_FC[TIPOS_FC[s['tipo']]]}."))
    if "operador" in s:
        ok = d.get("operador") == OPERADORES[s["operador"]]
        pts.append(_punto(ok, f"Operador «{s['operador']}»." if ok else f"El operador de la regla no es «{s['operador']}»."))
    for clave, k in (("valor", "f1"), ("valor2", "f2")):
        if clave not in s: continue
        ok = _numero(d.get(k)) is not None and abs(_numero(d.get(k)) - float(s[clave])) < 1e-9
        pts.append(_punto(ok, f"Con el valor {s[clave]}." if ok else f"La regla usa {str(d.get(k, '')).lstrip('=') or 'otro valor'}: debería ser {s[clave]}."))
    if "formula" in s:
        quiere = _local(hoja, s["formula"]); ok = _norm(d.get("f1", "")).replace(" ", "") == _norm(quiere).replace(" ", "")
        pts.append(_punto(ok, f"Con la fórmula {quiere}." if ok else f"La fórmula de la regla es {d.get('f1', '')}: debería ser {quiere}."))
    if "texto" in s:
        ok = _norm(d.get("texto", "")) == _norm(s["texto"])
        pts.append(_punto(ok, f"Con el texto «{s['texto']}»." if ok else f"La regla busca «{d.get('texto', '')}»: debería buscar «{s['texto']}»."))
    return {"hallado": True, "puntos": pts, "marcar": s.get("rango") or d["rango"].split(",")[0]}


def chk_validacion(hoja, s):
    ws = hoja.ws; r = M.rect(s["rango"]); celdas = sorted(M.celdas_de(r))[:300]
    reglas = {}
    for (f, c) in celdas:
        v = ws.Cells(f, c).Validation; tv = _t(lambda: v.Type)
        reglas[(f, c)] = None if tv is None else (tv, _t(lambda: v.Operator), _t(lambda: v.Formula1, ""), _t(lambda: v.Formula2, ""))
    sin = [k for k, v in reglas.items() if v is None]
    if len(sin) == len(celdas): return {"hallado": False, "puntos": [_punto(False, f"Falta la validación de datos en {s['rango']} (Datos → Validación de datos).")], "marcar": s["rango"]}
    pts = [_punto(not sin, f"Hay validación en {s['rango']}." if not sin else f"Faltan celdas con validación: {M._lista_celdas(sin)}.")]
    tv, op, f1, f2 = next(v for v in reglas.values() if v is not None)
    if "tipo" in s:
        ok = tv == TIPOS_VAL[s["tipo"]]
        pts.append(_punto(ok, f"Permite: {s['tipo']}." if ok else f"La validación es de tipo {NOMBRE_VAL.get(tv, tv)}: debería ser {s['tipo']}."))
    if "lista" in s:
        if isinstance(s["lista"], list):
            sep = hoja.xl.International[4]
            hay = [x.strip() for x in str(f1).split(sep)] if not str(f1).startswith("=") else []
            ok = {_norm(x) for x in hay} == {_norm(x) for x in s["lista"]}
            pts.append(_punto(ok, f"Lista: {', '.join(s['lista'])}." if ok else f"La lista tiene {', '.join(hay) or str(f1)}: debería tener {', '.join(s['lista'])}."))
        else:
            ok = _norm(str(f1).replace("'", "")) == _norm(str(s["lista"]).replace("'", ""))
            pts.append(_punto(ok, f"La lista sale de {s['lista']}." if ok else f"La lista sale de {f1}: debería salir de {s['lista']}."))
    if "operador" in s:
        ok = op == OPERADORES[s["operador"]]; pts.append(_punto(ok, f"Operador «{s['operador']}»." if ok else f"El operador de la validación no es «{s['operador']}»."))
    for clave, v in (("min", f1), ("max", f2 if op in (1, 2) else f1)):
        if clave in s:
            ok = _numero(v) is not None and abs(_numero(v) - float(s[clave])) < 1e-9
            pts.append(_punto(ok, f"{'Mínimo' if clave == 'min' else 'Máximo'} {s[clave]}." if ok else f"El {'mínimo' if clave == 'min' else 'máximo'} es {str(v).lstrip('=') or 'otro'}: debería ser {s[clave]}."))
    if "formula" in s:
        quiere = _local(hoja, s["formula"]); ok = _norm(f1).replace(" ", "") == _norm(quiere).replace(" ", "")
        pts.append(_punto(ok, f"Con la fórmula {quiere}." if ok else f"La fórmula es {f1}: debería ser {quiere}."))
    return {"hallado": True, "puntos": pts, "marcar": s["rango"]}


def chk_nombre(hoja, s):
    wb = hoja.ws.Parent; n = None
    for x in wb.Names:
        if x.Name.split("!")[-1].lower() == s["nombre"].lower(): n = x; break
    if n is None: return {"hallado": False, "puntos": [_punto(False, f"Falta el nombre «{s['nombre']}» (Fórmulas → Definir nombre).")]}
    pts = [_punto(True, f"Existe el nombre «{s['nombre']}».")]
    if "refiere" in s:
        limpia = lambda x: str(x).replace("'", "").replace(" ", "").casefold()
        ok = limpia(n.RefersTo) == limpia(s["refiere"]) or limpia(n.RefersTo).split("!")[-1] == limpia(s["refiere"]).lstrip("=")
        pts.append(_punto(ok, f"«{s['nombre']}» se refiere a {s['refiere']}." if ok else f"«{s['nombre']}» se refiere a {n.RefersTo}: debería ser {s['refiere']}."))
    if "valor" in s:
        v = _t(lambda: M.evaluar_en(hoja.ws, "=" + n.Name.split("!")[-1]))
        ok = M.igual(v, s["valor"])
        pts.append(_punto(ok, f"«{s['nombre']}» vale {s['valor']}." if ok else f"«{s['nombre']}» vale {v}: debería valer {s['valor']}."))
    return {"hallado": True, "puntos": pts}


def _filas(ws, r):
    return [tuple(fila) for fila in M._como_matriz(ws.Range(M.dir_(r)).Value)]


def _clave_orden(v):
    if v is None: return (2, "")
    if isinstance(v, (int, float)): return (0, v)
    return (1, str(v).casefold())


def chk_orden(hoja, s):
    ws = hoja.ws; f1, c1, f2, c2 = M.rect(s["rango"]); cab = s.get("encabezado", True)
    datos = (f1 + 1 if cab else f1, c1, f2, c2); col_ = M.num_col(s["por"]) - c1
    filas = _filas(ws, datos); vals = [_clave_orden(f[col_]) for f in filas]
    desc = s.get("orden") == "desc"
    ok = all((a >= b) if desc else (a <= b) for a, b in zip(vals, vals[1:]))
    pts = [_punto(ok, f"Ordenado por la columna {s['por'].upper()} {'de mayor a menor' if desc else 'de menor a mayor'}." if ok
                  else f"La columna {s['por'].upper()} no está ordenada {'de mayor a menor' if desc else 'de menor a mayor'} (Datos → Ordenar).")]
    base = getattr(hoja, "base", {}).get("datos", {}).get(M.dir_(datos))
    if base is not None:
        entera = sorted(map(str, base)) == sorted(map(str, filas))
        pts.append(_punto(entera, "Las filas siguen completas." if entera else "Al ordenar se mezclaron las filas: ordena el rango entero, no solo una columna."))
    return {"hallado": True, "puntos": pts, "marcar": s["rango"], "sin_hacer": not ok and base is not None and filas == list(base)}


def chk_filtro(hoja, s):
    ws = hoja.ws
    if s.get("tabla"):
        try: lo = next(lo for lo in ws.ListObjects if lo.Name.lower() == s["tabla"].lower())
        except StopIteration: return {"hallado": False, "puntos": [_punto(False, f"No hay una tabla «{s['tabla']}» en la hoja.")]}
        r = M.rect(_dir(lo.Range.Address))
    else: r = M.rect(s["rango"])
    cab = [str(v) for v in _filas(ws, (r[0], r[1], r[0], r[3]))[0]]
    col_s = str(s["columna"])
    if any(_norm(x) == _norm(col_s) for x in cab): j = next(i for i, x in enumerate(cab) if _norm(x) == _norm(col_s))
    elif re.fullmatch(r"[A-Za-z]{1,3}", col_s): j = M.num_col(col_s) - r[1]
    else: return {"hallado": False, "puntos": [_punto(False, f"No hay una columna «{col_s}».")]}
    def pasa(v):
        if "igual_a" in s:
            quiere = s["igual_a"] if isinstance(s["igual_a"], list) else [s["igual_a"]]
            return any(M.igual(v, q) or _norm(v) == _norm(q) for q in quiere)
        n = v if isinstance(v, (int, float)) else None
        if n is None: return False
        return ("mayor_que" not in s or n > s["mayor_que"]) and ("menor_que" not in s or n < s["menor_que"])
    filas = range(r[0] + 1, r[2] + 1); vals = _filas(ws, (r[0] + 1, r[1] + j, r[2], r[1] + j))
    ocultas = {f for f in filas if ws.Rows(f).Hidden}
    if not ocultas: return {"hallado": False, "puntos": [_punto(False, f"No hay ningún filtro aplicado en «{cab[j]}» (Datos → Filtro).")], "marcar": M.dir_(r)}
    malas = [f for f, v in zip(filas, vals) if (f in ocultas) == pasa(v[0])]
    sobran = [f for f in malas if f not in ocultas]; faltan = [f for f in malas if f in ocultas]
    crit = f"= {', '.join(map(str, s['igual_a'])) if isinstance(s.get('igual_a'), list) else s['igual_a']}" if "igual_a" in s else \
        " ".join(x for x in ((f"> {s['mayor_que']}" if "mayor_que" in s else ""), (f"< {s['menor_que']}" if "menor_que" in s else "")) if x)
    txt = f"Filtrado: {cab[j]} {crit}." if not malas else ("Se ven filas que no cumplen el filtro (" + ", ".join(map(str, sobran[:4])) + ")." if sobran
                                                             else "El filtro oculta filas que sí cumplen (" + ", ".join(map(str, faltan[:4])) + ").")
    return {"hallado": True, "puntos": [_punto(not malas, txt)], "marcar": M.dir_(r)}


def chk_inmovilizar(hoja, s):
    ws = hoja.ws; f1, c1, _, _ = M.rect(s["celda"])
    try:
        if ws.Parent.ActiveSheet.Name != ws.Name: return {"hallado": True, "puntos": [_punto(True, "Inmovilizar: se mira al pulsar Comprobar.")], "sin_mirar": True}
        win = ws.Parent.Windows(1); fp, sr, sc = bool(win.FreezePanes), win.SplitRow, win.SplitColumn
    except Exception: return {"hallado": True, "puntos": [_punto(True, "Inmovilizar: no pude mirarlo ahora.")], "sin_mirar": True}
    if not fp: return {"hallado": False, "puntos": [_punto(False, f"No hay paneles inmovilizados: selecciona {s['celda']} y Vista → Inmovilizar paneles.")]}
    ok = (sr, sc) == (f1 - 1, c1 - 1)
    return {"hallado": True, "puntos": [_punto(ok, f"Inmovilizado en {s['celda']}." if ok else
                                               f"Inmovilizaste en {M.col(sc + 1)}{sr + 1}: selecciona {s['celda']} antes de inmovilizar.")]}


def _categoria_formato(xl, nf, es):
    I = xl.International; dec, anio, mes, dia, hora, general = I[2], I[18], I[19], I[20], I[21], I[25]
    limpio = re.sub(r'"[^"]*"|\[[^\]]*\]|\\.', "", nf)
    if es == "porcentaje": return "%" in limpio
    if es == "moneda": return any(x in nf for x in ("$", "€", "£", "¥", "[$", str(I[24]) if len(I) > 24 else "$"))
    if es == "fecha": return any(ch in limpio.lower() for ch in (dia.lower(), anio.lower())) and "0" not in limpio
    if es == "hora": return hora.lower() in limpio.lower() and "0" not in limpio
    if es == "texto": return nf == "@"
    if es == "general": return nf.lower() == general.lower()
    if es in M.FORMATOS: return nf == M.formato_local(xl, M.FORMATOS[es])
    return nf == M.formato_local(xl, es)


def chk_formato_numero(hoja, s):
    ws, xl = hoja.ws, hoja.xl; r = M.rect(s["rango"]); celdas = sorted(M.celdas_de(r))[:300]
    rg = ws.Range(s["rango"]); comun = rg.NumberFormatLocal
    formatos = {k: comun for k in celdas} if comun is not None else {k: ws.Cells(*k).NumberFormatLocal for k in celdas}
    malas = []
    for k, nf in formatos.items():
        ok = True
        if "es" in s: ok = ok and _categoria_formato(xl, nf, s["es"])
        if "codigo" in s: ok = ok and nf == M.formato_local(xl, s["codigo"])
        if "decimales" in s:
            parte = re.sub(r'"[^"]*"|\[[^\]]*\]', "", nf.split(";")[0]); dec = xl.International[2]
            n = len(re.match(r"0*", parte.split(dec, 1)[1]).group(0)) if dec in parte else 0
            ok = ok and n == s["decimales"]
        if not ok: malas.append(k)
    que = " ".join(x for x in (s.get("es", ""), s.get("codigo", ""), f"con {s['decimales']} decimales" if "decimales" in s else "") if x)
    ok = not malas
    return {"hallado": True, "puntos": [_punto(ok, f"Formato {que} en {s['rango']}." if ok else
                                               f"Falta el formato {que} en {M._lista_celdas(malas)} (Inicio → Número).")], "marcar": s["rango"],
            "sin_hacer": len(malas) == len(celdas)}


COMPROBAR = {"grafico": chk_grafico, "tabla": chk_tabla, "dinamica": chk_dinamica, "formato_condicional": chk_formato_condicional,
             "validacion": chk_validacion, "nombre": chk_nombre, "orden": chk_orden, "filtro": chk_filtro,
             "inmovilizar": chk_inmovilizar, "formato_numero": chk_formato_numero}


def comprobar_item(hoja, item):
    tipo, spec = next(iter(item.items()))
    try: return COMPROBAR[tipo](hoja, spec)
    except Exception as e: return {"hallado": False, "puntos": [_punto(False, f"No pude revisar {tipo.replace('_', ' ')}: {M.motivo(e, 90)}")]}


def revisar_objetos(hoja, turno, dibujar=True, previo=None):
    """Comprobar de un turno con «pide»: cada cosa da sus puntos ✔/✘; los errores típicos («si») ponen su mensaje.
    Las marcas son formato condicional sobre el rango de cada cosa (nunca formas encima de las celdas)."""
    if dibujar and previo is None: hoja._borrar("check_")
    puntos, hallados, marcas, sin_hacer = [], 0, [], 0
    if previo is not None:
        puntos.append(_punto(previo["estado"] == "bien", f"Fórmulas de {previo.get('rango', '')}: {previo['mensaje']}"))
        hallados += previo["estado"] != "vacio"
    for item in turno["pide"]:
        r = comprobar_item(hoja, item)
        puntos += r["puntos"]; hallados += bool(r.get("hallado")) and not r.get("sin_hacer"); sin_hacer += bool(r.get("sin_hacer"))
        if r.get("marcar") and r.get("hallado"): marcas.append((r["marcar"], all(p["ok"] for p in r["puntos"])))
    ok = sum(p["ok"] for p in puntos); total = len(puntos)
    res = {"ok": ok, "total": total, "rango": turno.get("rango") or (marcas[0][0] if marcas else ""), "puntos": puntos}
    if dibujar:
        for rango, bien in marcas:
            try: hoja._marcar_celdas(hoja.ws.Range(rango), "check_", M.COLORES["verde" if bien else "rojo"], M.FONDOS["verde" if bien else "rojo"])
            except Exception: pass
    if not hallados:
        return dict(res, estado="vacio", puntos=[], mensaje=turno.get("al_empezar", "Haz lo que pide el ejercicio y pulsa Comprobar."))
    if ok == total: return dict(res, estado="bien", mensaje=turno.get("al_terminar", "¡Todo bien! Puedes seguir."))
    for e in turno.get("errores", []):
        if "si" not in e: continue
        r = comprobar_item(hoja, e["si"])
        if r.get("hallado") and all(p["ok"] for p in r["puntos"]): return dict(res, estado="mal", mensaje=e["dice"])
    primero = next(p["texto"] for p in puntos if not p["ok"])
    return dict(res, estado="mal", mensaje=primero if total - ok == 1 else f"Vas {ok} de {total}. {primero}")


def base_objetos(hoja, turno, excluir=None):
    """Lo que ya hay en la hoja al empezar el ejercicio (para no contar como suyo el gráfico del ejemplo) y los datos
    de los rangos que hay que ordenar (para ver que las filas siguen enteras). excluir: claves de inventario de la persona."""
    ws = hoja.ws; excluir = excluir or set()
    b = {"graficos": {co.Name for co in ws.ChartObjects() if ("forma", co.Name) not in excluir},
         "tablas": {lo.Name for lo in ws.ListObjects if ("tabla", _dir(lo.Range.Address)) not in excluir},
         "dinamicas": {pt.Name for pt in ws.PivotTables() if ("dinamica", _dir(pt.TableRange1.Cells(1).Address)) not in excluir},
         "fc": {(d["tipo"], d["rango"], str(d.get("f1", ""))) for _, d in reglas_fc(ws)
                if not any(k[0] == "fc" and k[1:4] == (d["tipo"], d["rango"], str(d.get("f1", ""))) for k in excluir)},
         "datos": {}}
    for item in turno.get("pide", []):
        tipo, s = next(iter(item.items()))
        if tipo == "orden":
            f1, c1, f2, c2 = M.rect(s["rango"]); d = (f1 + 1 if s.get("encabezado", True) else f1, c1, f2, c2)
            b["datos"][M.dir_(d)] = _filas(ws, d)
    return b


def huella_objetos(hoja, turno):
    """Firma barata de lo que mira «pide» (el vigía la compara cada 0,7 s)."""
    ws, out = hoja.ws, []
    tipos = {next(iter(i)) for i in turno.get("pide", [])}
    if "grafico" in tipos:
        for co in ws.ChartObjects():
            ch = co.Chart
            out.append((co.Name, ch.ChartType, bool(ch.HasTitle), _t(lambda: ch.ChartTitle.Text) if ch.HasTitle else "", bool(ch.HasLegend),
                        tuple(_t(lambda i=i: ch.SeriesCollection(i).Formula) for i in range(1, ch.SeriesCollection().Count + 1)),
                        tuple(_t(lambda e=e: ch.Axes(e).AxisTitle.Text) if _t(lambda e=e: ch.Axes(e).HasTitle) else "" for e in (1, 2))))
    if "tabla" in tipos or "filtro" in tipos: out.append(tuple((lo.Name, lo.Range.Address, bool(lo.ShowTotals)) for lo in ws.ListObjects))
    if "dinamica" in tipos: out.append(tuple(str(describir_dinamica(pt)) for pt in ws.PivotTables()))
    if "formato_condicional" in tipos: out.append(tuple(str(d) for _, d in reglas_fc(ws)))
    if "validacion" in tipos: out.append(str(validaciones(ws, 200)))
    if "nombre" in tipos: out.append(tuple((n.Name, _t(lambda: n.RefersTo)) for n in ws.Parent.Names))
    for item in turno.get("pide", []):
        tipo, s = next(iter(item.items()))
        if tipo in ("orden", "formato_numero") and s.get("rango"): out.append((ws.Range(s["rango"]).Value, ws.Range(s["rango"]).NumberFormatLocal))
        if tipo == "filtro":
            r = ws.UsedRange; out.append(tuple(ws.Rows(f).Hidden for f in range(r.Row, min(r.Row + r.Rows.Count, r.Row + 400))))
    return tuple(out)


# ---------- Power Query (con límite) ----------
NS_M = {"Table", "List", "Record", "Text", "Number", "Date", "DateTime", "DateTimeZone", "Duration", "Time", "Logical", "Splitter",
        "Combiner", "Comparer", "Replacer", "Order", "JoinKind", "JoinAlgorithm", "JoinSide", "MissingField", "Occurrence", "RoundingMode",
        "QuoteStyle", "ExtraValues", "Character", "Byte", "Int8", "Int16", "Int32", "Int64", "Single", "Double", "Decimal", "Currency",
        "Percentage", "Type", "Function", "Binary", "Lines", "Culture", "Precision", "GroupKind", "TextEncoding", "Compression", "Guid",
        "BinaryEncoding", "BinaryOccurrence", "RelativePosition", "Day", "Csv", "Json", "Xml"}
FUNC_M = {"Excel.CurrentWorkbook", "Excel.Workbook", "File.Contents", "Value.Is", "Value.Type", "Value.Equals", "Value.Compare", "Value.ReplaceType",
          "Value.As", "Value.FromText", "Value.Add", "Value.Subtract", "Value.Multiply", "Value.Divide", "Value.NullableEquals",
          "Value.Metadata", "Value.RemoveMetadata", "Value.ReplaceMetadata"}
PALABRAS_M_VETADAS = {"#shared": "#shared (da acceso a todas las funciones)", "#sections": "#sections", "section": "section"}


def _trozos_m(m):
    """Parte el código M en (tipo, texto): «código», «texto» (entre comillas) e «ident» (#"..."), sin los comentarios."""
    out, i, n, actual = [], 0, len(m), []
    def soltar():
        if actual: out.append(("codigo", "".join(actual))); actual.clear()
    while i < n:
        if m.startswith("//", i):
            j = m.find("\n", i); i = n if j < 0 else j; continue
        if m.startswith("/*", i):
            j = m.find("*/", i + 2)
            if j < 0: raise ValueError("un comentario /* sin cerrar")
            i = j + 2; continue
        if m[i] == '"' or m.startswith('#"', i):
            ident = m[i] == "#"; i += 2 if ident else 1; buf = []
            while True:
                if i >= n: raise ValueError("comillas sin cerrar")
                if m[i] == '"':
                    if i + 1 < n and m[i + 1] == '"': buf.append('"'); i += 2; continue
                    i += 1; break
                buf.append(m[i]); i += 1
            soltar(); out.append(("ident" if ident else "texto", "".join(buf))); continue
        actual.append(m[i]); i += 1
    soltar()
    return out


def validar_m(m, carpeta_datos=None, rutas=True):
    """Revisa una consulta M sin ejecutarla. Solo deja orígenes seguros: tablas y rangos de ESTE libro
    (Excel.CurrentWorkbook) y archivos dentro de la carpeta de datos del curso (File.Contents con la ruta escrita tal
    cual, o «{datos}\\archivo.csv»). Nada de web, bases de datos, carpetas, SharePoint, Expression.Evaluate, #shared…
    Devuelve el M listo (con {datos} cambiado por la carpeta) o lanza ValueError con el motivo."""
    if not isinstance(m, str) or not m.strip(): raise ValueError("la consulta M está vacía")
    if len(m) > 20000: raise ValueError("la consulta M es demasiado larga (máximo 20 000 caracteres)")
    if "{datos}" in m and rutas:
        if not carpeta_datos: raise ValueError("este curso no tiene carpeta de datos («datos» en curso.json): usa Excel.CurrentWorkbook()")
        m = m.replace("{datos}", carpeta_datos.rstrip("\\/"))
    trozos = _trozos_m(m)
    codigo = " ".join(t for k, t in trozos if k == "codigo")
    for p, que in PALABRAS_M_VETADAS.items():
        if re.search(rf"(?<![\w#]){re.escape(p)}\b", codigo, re.I): raise ValueError(f"la consulta usa {que}: no se permite")
    nombres = re.findall(r"(?<![\w.#])([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)+)", codigo)
    nombres += [t for k, t in trozos if k == "ident" and "." in t]
    for nm in nombres:
        partes = nm.split(".")
        if nm in FUNC_M or ".".join(partes[:2]) in FUNC_M: continue
        if partes[0] in NS_M and partes[0] != "Value": continue
        if partes[0] == "Value": raise ValueError(f"«{nm}» no se permite en las consultas del panel")
        raise ValueError(f"«{nm}» no se permite: las consultas solo leen tablas de este libro (Excel.CurrentWorkbook) y archivos de la carpeta de datos del curso")
    # File.Contents solo con una ruta escrita tal cual, dentro de la carpeta de datos
    juntos = "".join(f'"{t}"' if k == "texto" else (f'#"{t}"' if k == "ident" else t) for k, t in trozos)
    usos = len(re.findall(r"\bFile\.Contents\b", juntos))
    lista = re.findall(r'\bFile\.Contents\s*\(\s*"([^"]*)"\s*\)', juntos)
    if usos != len(lista): raise ValueError("File.Contents va con la ruta escrita entre comillas, sin juntar textos: File.Contents(\"{datos}\\ventas.csv\")")
    for ruta in (lista if rutas else []):
        if not carpeta_datos: raise ValueError("este curso no tiene carpeta de datos: solo se pueden usar tablas del libro (Excel.CurrentWorkbook)")
        if "#(" in ruta or not os.path.isabs(ruta): raise ValueError(f"la ruta «{ruta}» tiene que ser completa (usa {{datos}}\\archivo)")
        real, base = os.path.realpath(ruta), os.path.realpath(carpeta_datos)
        if os.path.commonpath([real.lower(), base.lower()]) != base.lower(): raise ValueError(f"«{ruta}» está fuera de la carpeta de datos del curso")
        if not os.path.isfile(real): raise ValueError(f"no existe el archivo «{os.path.basename(ruta)}» en la carpeta de datos")
    return m


NOMBRE_CONSULTA = re.compile(r"^[A-Za-zÁÉÍÓÚÜÑáéíóúüñ_][\wÁÉÍÓÚÜÑáéíóúüñ ]{0,60}$")


def _cargas(wb, nombre):
    """Las tablas (en cualquier hoja) donde está cargada una consulta."""
    out = []
    for s in wb.Worksheets:
        for lo in s.ListObjects:
            c = _t(lambda: lo.QueryTable.Connection, "") or ""
            if f"location={nombre.lower()};" in str(c).lower() or str(c).lower().endswith(f"location={nombre.lower()}"): out.append(lo)
    return out


def consultas(wb):
    """{nombre: fórmula M} de las consultas del libro."""
    try: return {q.Name: q.Formula for q in wb.Queries}
    except Exception: return {}


def conexiones(wb):
    try: return {c.Name for c in wb.Connections}
    except Exception: return set()


def crear_consulta(libro, ws, a):
    """{"consulta": nombre, "m": "...", "cargar_en": "A1"}: crea la consulta (o cambia su M) y, con «cargar_en», la carga
    como tabla en esa celda de la hoja. Si ya estaba cargada, la actualiza."""
    wb = libro.wb; nombre = a["consulta"]; m = validar_m(a["m"], libro.carpeta_datos())
    q = next((x for x in wb.Queries if x.Name.lower() == nombre.lower()), None)
    if q is None: q = wb.Queries.Add(nombre, m, a.get("descripcion", ""))
    else:
        try: q.Formula = m
        except Exception:       # (falla si quedó una conexión suya sin tabla: se quita entera y se crea de nuevo)
            quitar_consulta(libro, q.Name); q = wb.Queries.Add(nombre, m, a.get("descripcion", ""))
        for lo in _cargas(wb, q.Name): lo.QueryTable.Refresh(False)
    if a.get("cargar_en"):
        conn = f'OLEDB;Provider=Microsoft.Mashup.OleDb.1;Data Source=$Workbook$;Location={q.Name};Extended Properties=""'
        lo = ws.ListObjects.Add(0, conn, E, 1, ws.Range(a["cargar_en"]))
        qt = lo.QueryTable; qt.CommandType = 2; qt.CommandText = [f"SELECT * FROM [{q.Name}]"]
        qt.RowNumbers = False; qt.AdjustColumnWidth = True; qt.RefreshStyle = 0          # 0 = sobrescribe (no mueve celdas de alrededor)
        nombre_t = re.sub(r"\W", "_", q.Name)
        if not any(x.Name.lower() == nombre_t.lower() for s in wb.Worksheets for x in s.ListObjects): lo.DisplayName = nombre_t
        qt.Refresh(False)
        try: qt.WorkbookConnection.Name = f"Consulta - {q.Name}"
        except Exception: pass


def actualizar_consulta(libro, nombre):
    wb = libro.wb
    nombres = list(consultas(wb)) if nombre == "todo" else [nombre]
    for n in nombres:
        if n not in consultas(wb): raise ValueError(f"no hay una consulta «{n}»")
        for lo in _cargas(wb, n): lo.QueryTable.Refresh(False)


def quitar_consulta(libro, nombre):
    """Borra una consulta con sus tablas cargadas y su conexión (para deshacer y al rehacer un paso)."""
    wb = libro.wb
    for lo in _cargas(wb, nombre):
        try: lo.Delete()
        except Exception: pass
    for c in list(wb.Connections):
        cs = _t(lambda: str(c.OLEDBConnection.Connection), "") or ""
        if c.Name.lower() == f"consulta - {nombre.lower()}" or f"location={nombre.lower()};" in cs.lower():
            try: c.Delete()
            except Exception: pass
    try: wb.Queries(nombre).Delete()
    except Exception: pass


def tiene_pq(ws):
    return any(_t(lambda: lo.SourceType) == 3 or _t(lambda: lo.QueryTable) is not None for lo in ws.ListObjects)


def revertir_consultas(libro, antes, despues, conex_antes, conex_despues):
    """Deshacer de Power Query: quita las consultas que creó la propuesta (con sus cargas y conexiones) y devuelve las que
    cambió a su M de antes, actualizando sus tablas. No toca lo que cambió la persona después."""
    wb = libro.wb; ahora = consultas(wb)
    for n, f in despues.items():
        if n not in antes and ahora.get(n) == f: quitar_consulta(libro, n)
    for n, f in antes.items():
        if despues.get(n) != f and ahora.get(n) == despues.get(n):
            try:
                wb.Queries(n).Formula = f
                for lo in _cargas(wb, n): lo.QueryTable.Refresh(False)
            except Exception: pass
    for c in conex_despues - conex_antes:
        try:
            if c in conexiones(wb): wb.Connections(c).Delete()
        except Exception: pass


# ---------- Herramientas de análisis ----------
def solver_disponible(xl):
    """¿Está activado el complemento Solver? (nunca se activa solo: lo hace la persona en Archivo → Opciones → Complementos)."""
    try:
        if any(a.Name.lower() == "solver.xlam" and a.Installed for a in xl.AddIns): return True
    except Exception: pass
    try: return any(wb.Name.lower() == "solver.xlam" for wb in xl.Workbooks)
    except Exception: return False


RELACIONES = {"<=": 1, "=": 2, ">=": 3, "entero": 4, "binario": 5, "diferentes": 6}
METODOS = {"grg": 1, "simplex": 2, "evolutivo": 3}


def ejecutar(libro, ws, a):
    """Las acciones nuevas: Power Query y herramientas de análisis (validadas antes con validar_accion)."""
    R = ws.Range
    if "consulta" in a: crear_consulta(libro, ws, a)
    elif "actualizar" in a: actualizar_consulta(libro, a["actualizar"])
    elif "buscar_objetivo" in a:
        if not R(a["buscar_objetivo"]).HasFormula: raise ValueError(f"buscar_objetivo: {a['buscar_objetivo']} tiene que tener una fórmula")
        if R(a["cambiando"]).HasFormula: raise ValueError(f"buscar_objetivo: {a['cambiando']} tiene que ser un valor, no una fórmula")
        if not R(a["buscar_objetivo"]).GoalSeek(float(a["valor"]), R(a["cambiando"])): raise ValueError("Buscar objetivo no encontró una solución")
    elif "tabla_datos" in a:
        R(a["tabla_datos"]).Table(R(a["fila"]) if a.get("fila") else E, R(a["columna"]) if a.get("columna") else E)
    elif "escenario" in a:
        if any(s.Name.lower() == a["escenario"].lower() for s in ws.Scenarios()): raise ValueError(f"ya hay un escenario «{a['escenario']}»")
        ws.Scenarios().Add(a["escenario"], R(a["celdas"]), [str(v) for v in a["valores"]], a.get("comentario", ""), False, False)
    elif "mostrar_escenario" in a:
        try: ws.Scenarios(a["mostrar_escenario"]).Show()
        except Exception: raise ValueError(f"no hay un escenario «{a['mostrar_escenario']}» en la hoja")
    elif "solver" in a:
        xl = libro.xl
        if not solver_disponible(xl): raise ValueError("Solver no está activado (Archivo → Opciones → Complementos → Solver)")
        ws.Parent.Activate(); ws.Activate(); run = lambda nombre, *args: xl.Run(f"Solver.xlam!{nombre}", *args)
        tipo = {"max": 1, "min": 2, "valor": 3}[a.get("tipo", "max")]
        run("SolverReset")
        run("SolverOk", R(a["solver"]).Address, tipo, float(a.get("valor", 0)), R(a["cambiando"]).Address, METODOS[a.get("metodo", "simplex")])
        for rr in a.get("restricciones", []):
            run("SolverAdd", R(rr["celda"]).Address, RELACIONES[rr["es"]], str(rr.get("valor", "")) if rr["es"] not in ("entero", "binario", "diferentes") else E)
        r = run("SolverSolve", True)
        run("SolverFinish", 1)
        if r not in (0, 1, 2): raise ValueError(f"Solver no encontró una solución (código {r})")
    else: raise ValueError(f"acción desconocida: {a}")


ACCIONES = {
    "consulta": ({"m", "cargar_en", "descripcion"}, ("m",)), "actualizar": (set(), ()),
    "buscar_objetivo": ({"valor", "cambiando"}, ("valor", "cambiando")), "tabla_datos": ({"fila", "columna"}, ()),
    "escenario": ({"celdas", "valores", "comentario"}, ("celdas", "valores")), "mostrar_escenario": (set(), ()),
    "solver": ({"tipo", "valor", "cambiando", "restricciones", "metodo"}, ("cambiando",)),
}
COPIA = {"consulta", "buscar_objetivo", "tabla_datos", "escenario", "mostrar_escenario", "solver"}     # se deshacen con la copia de la hoja


def validar_accion(tipo, a, d):
    """Revisa una acción nueva sin Excel (la llama motor._validar_accion). Lanza ValueError."""
    if tipo == "consulta":
        if not isinstance(a["consulta"], str) or not NOMBRE_CONSULTA.match(a["consulta"]) or a["consulta"].lower().startswith(M.COPIA):
            raise ValueError(f"{d}: el nombre de la consulta son letras, números, _ y espacios (máximo 60)")
        if not isinstance(a["m"], str): raise ValueError(f"{d}: «m» es el código M de la consulta")
        validar_m(a["m"], rutas=False)
        if "cargar_en" in a:
            f1, c1, f2, c2 = M.rect(a["cargar_en"])
            if (f1, c1) != (f2, c2): raise ValueError(f"{d}: «cargar_en» es una celda (la esquina de la tabla)")
        if "descripcion" in a and (not isinstance(a["descripcion"], str) or len(a["descripcion"]) > 200): raise ValueError(f"{d}: descripción corta")
    elif tipo == "actualizar":
        if not isinstance(a["actualizar"], str) or not (a["actualizar"] == "todo" or NOMBRE_CONSULTA.match(a["actualizar"])): raise ValueError(f"{d}: el nombre de una consulta (o \"todo\")")
    elif tipo == "buscar_objetivo":
        for c in ("buscar_objetivo", "cambiando"):
            f1, c1, f2, c2 = M.rect(a[c])
            if (f1, c1) != (f2, c2): raise ValueError(f"{d}: «{c}» es una sola celda")
        if not isinstance(a["valor"], (int, float)) or isinstance(a["valor"], bool): raise ValueError(f"{d}: «valor» es un número")
    elif tipo == "tabla_datos":
        f1, c1, f2, c2 = M.rect(a["tabla_datos"])
        if f2 - f1 < 1 or c2 - c1 < 1: raise ValueError(f"{d}: la tabla de datos tiene al menos 2 filas y 2 columnas (con la fórmula en la esquina)")
        if not (a.get("fila") or a.get("columna")): raise ValueError(f"{d}: falta la celda de entrada («fila» o «columna»)")
        for c in ("fila", "columna"):
            if a.get(c):
                g1, h1, g2, h2 = M.rect(a[c])
                if (g1, h1) != (g2, h2): raise ValueError(f"{d}: «{c}» es una sola celda")
    elif tipo in ("escenario", "mostrar_escenario"):
        if not isinstance(a[tipo], str) or not 0 < len(a[tipo]) <= 60: raise ValueError(f"{d}: nombre del escenario (máximo 60)")
        if tipo == "escenario":
            n = len(M.celdas_de(M.rect(a["celdas"])))
            if n > 32: raise ValueError(f"{d}: máximo 32 celdas cambiantes")
            if not isinstance(a["valores"], list) or len(a["valores"]) != n or not all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in a["valores"]):
                raise ValueError(f"{d}: «valores» son {n} números (uno por celda de {a['celdas']})")
            if "comentario" in a: M._texto_seguro(a["comentario"], d, 200)
    elif tipo == "solver":
        f1, c1, f2, c2 = M.rect(a["solver"])
        if (f1, c1) != (f2, c2): raise ValueError(f"{d}: «solver» es la celda objetivo")
        M.rect(a["cambiando"])
        if a.get("tipo", "max") not in ("max", "min", "valor"): raise ValueError(f"{d}: «tipo» es max, min o valor")
        if a.get("metodo", "simplex") not in METODOS: raise ValueError(f"{d}: «metodo» es {', '.join(METODOS)}")
        if "valor" in a and (not isinstance(a["valor"], (int, float)) or isinstance(a["valor"], bool)): raise ValueError(f"{d}: «valor» es un número")
        rs = a.get("restricciones", [])
        if not isinstance(rs, list) or len(rs) > 20: raise ValueError(f"{d}: «restricciones» es una lista (máximo 20)")
        for r in rs:
            if not isinstance(r, dict) or set(r) - {"celda", "es", "valor"} or "celda" not in r or r.get("es") not in RELACIONES:
                raise ValueError(f'{d}: cada restricción es {{"celda": "B2:B5", "es": ">=", "valor": 0}} (es: {", ".join(RELACIONES)})')
            M.rect(r["celda"])
            v = r.get("valor")
            if r["es"] in ("<=", "=", ">="):
                if isinstance(v, str):
                    if not v.startswith("=") or not re.fullmatch(r"=\$?[A-Z]{1,3}\$?\d+", v.replace(" ", "")): raise ValueError(f"{d}: el valor de una restricción es un número o una celda como \"=$B$8\"")
                elif not isinstance(v, (int, float)) or isinstance(v, bool): raise ValueError(f"{d}: el valor de una restricción es un número o una celda")


def describir(a):
    """Una línea en palabras para la tarjeta de permiso (las acciones nuevas)."""
    if "consulta" in a:
        return f"Consulta de Power Query «{a['consulta']}»" + (f", cargada en {a['cargar_en']}" if a.get("cargar_en") else " (solo conexión)") + f" · `{' '.join(a['m'].split())[:160]}`"
    if "actualizar" in a: return "Actualizar " + ("todas las consultas" if a["actualizar"] == "todo" else f"la consulta «{a['actualizar']}»")
    if "buscar_objetivo" in a: return f"Buscar objetivo: que {a['buscar_objetivo']} valga {a['valor']} cambiando {a['cambiando']}"
    if "tabla_datos" in a: return f"Tabla de datos en {a['tabla_datos']}" + (f", fila de entrada {a['fila']}" if a.get("fila") else "") + (f", columna de entrada {a['columna']}" if a.get("columna") else "")
    if "escenario" in a: return f"Crear el escenario «{a['escenario']}»: {a['celdas']} = {', '.join(map(str, a['valores']))}"
    if "mostrar_escenario" in a: return f"Mostrar el escenario «{a['mostrar_escenario']}» (cambia sus celdas)"
    if "solver" in a:
        return (f"Solver: {'maximizar' if a.get('tipo', 'max') == 'max' else 'minimizar' if a.get('tipo') == 'min' else 'llegar a ' + str(a.get('valor', 0))} {a['solver']} "
                f"cambiando {a['cambiando']}" + (f", con {M._cuantas(len(a.get('restricciones', [])), 'restricción')}" if a.get("restricciones") else ""))
    return str(a)


def frases(a):
    """(lo que quiere hacer, lo que hizo) para el resumen de la tarjeta."""
    if "consulta" in a: x = f" la consulta «{a['consulta']}»" + (f" y cargarla en {a['cargar_en']}" if a.get("cargar_en") else ""); return ("crear" + x, "creé" + x.replace("cargarla", "la cargué"))
    if "actualizar" in a: return ("actualizar datos de Power Query", "actualicé datos de Power Query")
    if "buscar_objetivo" in a: return (f"buscar el valor de {a['cambiando']}", f"busqué el valor de {a['cambiando']}")
    if "tabla_datos" in a: return (f"hacer una tabla de datos en {a['tabla_datos']}", f"hice una tabla de datos en {a['tabla_datos']}")
    if "escenario" in a: return (f"crear el escenario «{a['escenario']}»", f"creé el escenario «{a['escenario']}»")
    if "mostrar_escenario" in a: return (f"mostrar el escenario «{a['mostrar_escenario']}»", f"mostré el escenario «{a['mostrar_escenario']}»")
    if "solver" in a: return (f"resolver con Solver ({a['solver']})", f"resolví con Solver ({a['solver']})")
    return ("cambiar", "cambié")


def contenido(a):
    """Las celdas que cambia una acción nueva (para los avisos de la tarjeta), como rectángulos."""
    if "buscar_objetivo" in a: return [M.rect(a["cambiando"])]
    if "tabla_datos" in a: return [M.rect(a["tabla_datos"])]
    if "escenario" in a: return []
    if "solver" in a: return [M.rect(a["cambiando"])]
    return []                    # (una consulta cargada sobrescribe desde su celda; se deshace con la copia de la hoja)


def objetos_extra(ws):
    """Lo nuevo que cuenta Hoja.objetos(): tablas de Power Query, escenarios, tablas de datos y filtros aplicados."""
    out = []
    for lo in ws.ListObjects:
        c = _t(lambda: lo.QueryTable.Connection, "") or ""
        m = re.search(r"Location=([^;]+)", str(c))
        if m: out.append(f"Tabla '{lo.Name}' cargada de la consulta de Power Query «{m.group(1)}» en {_dir(lo.Range.Address)}")
        try:
            f = lo.AutoFilter.Filters; filtradas = [lo.ListColumns(i).Name for i in range(1, f.Count + 1) if f(i).On]
            if filtradas: out.append(f"Tabla '{lo.Name}' filtrada por: {', '.join(filtradas)}")
        except Exception: pass
    try:
        for s in ws.Scenarios():
            out.append(f"Escenario «{s.Name}»: {_dir(s.ChangingCells.Address)} = {', '.join(map(str, s.Values))}")
    except Exception: pass
    return out
