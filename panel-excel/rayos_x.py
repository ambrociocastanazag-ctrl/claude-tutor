"""Lo que necesitan los dibujos de fórmulas (tutor-pantalla/formas_formulas.js) y que solo Excel sabe: la fórmula
en LaTeX, de qué celdas viene un resultado, dónde está cada celda en la pantalla y los números para una mini gráfica.

SOLO LEE: nunca escribe, guarda, selecciona ni cierra nada del libro del estudiante.

  a_latex(formula)                       fórmula de Excel en inglés → LaTeX para MathJax (nunca rompe)
  caja_celda(xl, rango, hoja=None)       [x, y, w, h] en píxeles físicos de PANTALLA, o None si no se ve
  datos_rayos_x(xl, ref, hoja=None)      {"r", "valor", "formula", "fuentes": [{"ref", "r", "valor"}]}
  datos_formula(xl, ref, grafica=False, hoja=None)   {"r", "latex", "grafica": {...} | None}
  datos_desarmar(xl, ref, hoja=None)     {"r", "original"}
  excel_de_ventana(hwnd)                 el Application cuyo Hwnd es ese (o None)
  resolver(xl, marca)                    los campos del lote para una marca {"tipo": "dibujo", "forma": ...}

  python panel-excel/rayos_x.py --probar            pruebas de a_latex (sin Excel)
  python panel-excel/rayos_x.py --probar --excel    además, en SU PROPIA instancia de Excel (no toca la del estudiante)
"""
import re, statistics, sys

# ---------------------------------------------------------------- fórmula → LaTeX
ES = {  # nombre en inglés → nombre en español (el que ve la persona en su Excel)
    "SUM": "SUMA", "AVERAGE": "PROMEDIO", "COUNT": "CONTAR", "COUNTA": "CONTARA", "COUNTBLANK": "CONTAR.BLANCO",
    "IF": "SI", "IFERROR": "SI.ERROR", "IFS": "SI.CONJUNTO", "IFNA": "SI.ND", "VLOOKUP": "BUSCARV", "HLOOKUP": "BUSCARH",
    "XLOOKUP": "BUSCARX", "LOOKUP": "BUSCAR", "INDEX": "INDICE", "MATCH": "COINCIDIR", "XMATCH": "COINCIDIRX",
    "ROUND": "REDONDEAR", "ROUNDUP": "REDONDEAR.MAS", "ROUNDDOWN": "REDONDEAR.MENOS", "SUMIF": "SUMAR.SI",
    "SUMIFS": "SUMAR.SI.CONJUNTO", "COUNTIF": "CONTAR.SI", "COUNTIFS": "CONTAR.SI.CONJUNTO", "AVERAGEIF": "PROMEDIO.SI",
    "AVERAGEIFS": "PROMEDIO.SI.CONJUNTO", "AND": "Y", "OR": "O", "NOT": "NO", "XOR": "XO", "TRUE": "VERDADERO",
    "FALSE": "FALSO", "MAX": "MAX", "MIN": "MIN", "MEDIAN": "MEDIANA", "MODE": "MODA", "LEFT": "IZQUIERDA",
    "RIGHT": "DERECHA", "MID": "EXTRAE", "LEN": "LARGO", "FIND": "ENCONTRAR", "SEARCH": "HALLAR", "TRIM": "ESPACIOS",
    "UPPER": "MAYUSC", "LOWER": "MINUSC", "PROPER": "NOMPROPIO", "SUBSTITUTE": "SUSTITUIR", "REPLACE": "REEMPLAZAR",
    "CONCAT": "CONCAT", "CONCATENATE": "CONCATENAR", "TEXTJOIN": "UNIRCADENAS", "TEXT": "TEXTO", "VALUE": "VALOR",
    "TODAY": "HOY", "NOW": "AHORA", "DATE": "FECHA", "YEAR": "AÑO", "MONTH": "MES", "DAY": "DIA", "WEEKDAY": "DIASEM",
    "DATEDIF": "SIFECHA", "EDATE": "FECHA.MES", "EOMONTH": "FIN.MES", "NETWORKDAYS": "DIAS.LAB", "INT": "ENTERO",
    "MOD": "RESIDUO", "POWER": "POTENCIA", "SQRT": "RAIZ", "ABS": "ABS", "PI": "PI", "RAND": "ALEATORIO",
    "RANDBETWEEN": "ALEATORIO.ENTRE", "STDEV": "DESVEST", "VAR": "VAR", "LARGE": "K.ESIMO.MAYOR",
    "SMALL": "K.ESIMO.MENOR", "RANK": "JERARQUIA", "PRODUCT": "PRODUCTO", "SUMPRODUCT": "SUMAPRODUCTO",
    "CHOOSE": "ELEGIR", "OFFSET": "DESREF", "INDIRECT": "INDIRECTO", "ROW": "FILA", "COLUMN": "COLUMNA",
    "ROWS": "FILAS", "COLUMNS": "COLUMNAS", "ISBLANK": "ESBLANCO", "ISNUMBER": "ESNUMERO", "ISTEXT": "ESTEXTO",
    "ISERROR": "ESERROR", "FILTER": "FILTRAR", "SORT": "ORDENAR", "UNIQUE": "UNICOS", "SEQUENCE": "SECUENCIA",
    "TRANSPOSE": "TRANSPONER", "LET": "LET", "TRUNC": "TRUNCAR", "CEILING": "MULTIPLO.SUPERIOR",
    "FLOOR": "MULTIPLO.INFERIOR", "EXP": "EXP", "LN": "LN", "LOG": "LOG", "LOG10": "LOG10", "SIN": "SENO",
    "COS": "COS", "TAN": "TAN", "PMT": "PAGO", "FV": "VF", "PV": "VA", "NPV": "VNA", "IRR": "TIR", "RATE": "TASA",
}
COMP = {"=": "=", "<": "<", ">": ">", "<=": r"\le", ">=": r"\ge", "<>": r"\ne"}
_REF = re.compile(r"^(?:(?:'[^']+'|[A-Za-z0-9_.]+)!)?\$?[A-Za-z]{1,3}\$?\d+(?::\$?[A-Za-z]{1,3}\$?\d+)?$")


def _texto(s):
    """Texto literal para MathJax: lo normal dentro de \\text{}, y lo especial como comandos de matemáticas."""
    esp = {"\\": r"\backslash ", "{": r"\{", "}": r"\}", "$": r"\$", "&": r"\&", "#": r"\#", "_": r"\_", "%": r"\%",
           "^": r"\wedge ", "~": r"\sim "}
    out, buf = [], ""
    for ch in str(s):
        if ch in esp:
            if buf: out.append(r"\text{" + buf + "}"); buf = ""
            out.append(esp[ch])
        elif ord(ch) < 32: buf += " "
        else: buf += ch
    if buf: out.append(r"\text{" + buf + "}")
    return "".join(out) or r"\text{}"



class _Parser:
    """Árbol de expresión a partir de los tokens de openpyxl. Precedencia de Excel (menor → mayor):
    comparación, &, + −, * /, ^, %, signo."""

    def __init__(self, tokens):
        self.t = [k for k in tokens if k.type != "WHITE-SPACE"]
        self.i = 0

    def ver(self):
        return self.t[self.i] if self.i < len(self.t) else None

    def toma(self):
        k = self.ver(); self.i += 1; return k

    def expr(self):
        return self.comp()

    def _bin(self, sub, ops):
        a = sub()
        while True:
            k = self.ver()
            if k is not None and k.type == "OPERATOR-INFIX" and k.value in ops:
                self.toma(); a = ("bin", k.value, a, sub())
            else: return a

    def comp(self): return self._bin(self.concat, ("=", "<", ">", "<=", ">=", "<>"))
    def concat(self): return self._bin(self.suma, ("&",))
    def suma(self): return self._bin(self.mul, ("+", "-"))
    def mul(self): return self._bin(self.pot, ("*", "/"))
    def pot(self): return self._bin(self.pct, ("^",))

    def pct(self):
        a = self.unario()
        while self.ver() is not None and self.ver().type == "OPERATOR-POSTFIX":
            self.toma(); a = ("pct", a)
        return a

    def unario(self):
        k = self.ver()
        if k is not None and k.type == "OPERATOR-PREFIX":
            self.toma(); return ("un", k.value, self.unario())
        return self.primario()

    def primario(self):
        k = self.toma()
        if k is None: raise ValueError("fin inesperado")
        if k.type == "OPERAND":
            if k.subtype == "NUMBER": return ("num", k.value)
            if k.subtype == "TEXT": return ("text", k.value[1:-1].replace('""', '"'))
            if k.subtype == "LOGICAL": return ("bool", k.value)
            if k.subtype == "ERROR": return ("err", k.value)
            return ("ref", k.value)
        if k.type == "FUNC" and k.subtype == "OPEN":
            nombre = k.value[:-1]; args = []
            if self.ver() is not None and self.ver().type == "FUNC" and self.ver().subtype == "CLOSE":
                self.toma(); return ("call", nombre, args)
            while True:
                if self.ver() is not None and self.ver().type == "SEP":   # argumento vacío
                    args.append(("vacio",))
                else: args.append(self.expr())
                s = self.toma()
                if s is None: raise ValueError("falta )")
                if s.type == "FUNC" and s.subtype == "CLOSE": return ("call", nombre, args)
                if s.type != "SEP": raise ValueError("se esperaba ; o )")
        if k.type == "PAREN" and k.subtype == "OPEN":
            e = self.expr(); c = self.toma()
            if c is None or c.type != "PAREN": raise ValueError("falta )")
            return ("paren", e)
        if k.type == "ARRAY" and k.subtype == "OPEN":
            filas, fila = [], []
            while True:
                fila.append(self.expr()); s = self.toma()
                if s is None: raise ValueError("falta }")
                if s.type == "ARRAY" and s.subtype == "CLOSE": filas.append(fila); return ("arr", filas)
                if s.type == "SEP" and s.subtype == "ROW": filas.append(fila); fila = []
        raise ValueError("token inesperado " + str(k.value))


def _ref_tex(ref):
    r = ref.replace("$", "")
    m = re.match(r"^'([^']+)'!(.*)$", r)
    if m: r = m.group(1) + "!" + m.group(2)
    if ":" in r and _REF.match(ref.replace("$", "")):
        a, b = r.split(":", 1)
        return _texto(a) + r"{:}" + _texto(b)
    return _texto(r)


def _sin_paren(n):
    while n[0] == "paren": n = n[1]
    return n


def _suma_rango(args):
    """\\sum con índices si SUM recibe un solo rango de una columna o de una fila."""
    if len(args) != 1 or args[0][0] != "ref": return None
    m = re.match(r"^(?:(?:'[^']+'|[^!]+)!)?\$?([A-Za-z]{1,3})\$?(\d+):\$?([A-Za-z]{1,3})\$?(\d+)$", args[0][1])
    if not m: return None
    c1, f1, c2, f2 = m.group(1).upper(), int(m.group(2)), m.group(3).upper(), int(m.group(4))
    if c1 == c2 and f1 < f2:
        return r"\sum_{i=%d}^{%d} %s_{i}" % (f1, f2, c1)
    if f1 == f2 and c1 != c2:
        return r"\sum_{j=\text{%s}}^{\text{%s}} x_{j,%d}" % (c1, c2, f1)
    return None


def _tex(n):
    t = n[0]
    if t == "num": return n[1]
    if t == "text": return _texto("“" + n[1] + "”")
    if t == "bool": return r"\text{" + ES.get(n[1].upper(), n[1]) + "}"
    if t == "err": return _texto(n[1])
    if t == "ref": return _ref_tex(n[1])
    if t == "vacio": return ""
    if t == "paren": return r"\left(" + _tex(n[1]) + r"\right)"
    if t == "pct": return _tex(n[1]) + r"\%"
    if t == "un": return n[1] + _tex(n[2])
    if t == "arr":
        return r"\left\{" + " ; ".join(" , ".join(_tex(x) for x in f) for f in n[1]) + r"\right\}"
    if t == "bin":
        op, a, b = n[1], n[2], n[3]
        if op == "/": return r"\frac{" + _tex(_sin_paren(a)) + "}{" + _tex(_sin_paren(b)) + "}"
        if op == "^":
            base = _tex(a)
            if a[0] in ("bin", "un", "pct") and a[0] != "paren": base = "{" + base + "}"
            if a[0] == "bin" and a[1] == "^": base = "{" + _tex(a) + "}"
            return base + "^{" + _tex(_sin_paren(b)) + "}"
        if op == "*": return _tex(a) + r" \cdot " + _tex(b)
        if op == "&": return _tex(a) + r" \mathbin{\&} " + _tex(b)
        if op in COMP: return _tex(a) + " " + COMP[op] + " " + _tex(b)
        return _tex(a) + " " + op + " " + _tex(b)
    if t == "call": return _llamada(n[1], n[2])
    raise ValueError("nodo " + t)


def _llamada(nombre, args):
    nom = re.sub(r"^_xl(fn|ws)\.", "", nombre).upper()
    n = len(args)
    if nom == "SQRT" and n == 1: return r"\sqrt{" + _tex(_sin_paren(args[0])) + "}"
    if nom == "ABS" and n == 1: return r"\left|" + _tex(args[0]) + r"\right|"
    if nom == "POWER" and n == 2:
        base = _tex(args[0])
        if args[0][0] in ("bin", "un", "pct"): base = "{" + base + "}"
        return base + "^{" + _tex(_sin_paren(args[1])) + "}"
    if nom == "SUM":
        s = _suma_rango(args)
        if s: return s
    if nom == "IF" and n >= 2:
        filas, cur = [], args
        while True:
            filas.append(_tex(cur[1]) + r" & \text{si } " + _tex(cur[0]))
            sino = cur[2] if len(cur) > 2 else None
            if sino is not None and sino[0] == "call" and sino[1].upper() == "IF" and len(sino[2]) >= 2:
                cur = sino[2]; continue
            filas.append((_tex(sino) if sino is not None and sino[0] != "vacio" else r"\text{FALSO}") + r" & \text{en otro caso}")
            break
        return r"\begin{cases} " + r" \\ ".join(filas) + r" \end{cases}"
    es = ES.get(nom, nom.replace("_", "."))
    cuerpo = " ; ".join(_tex(a) for a in args)
    return r"\operatorname{" + es + r"}\left(" + cuerpo + r"\right)"


def a_latex(formula):
    """Fórmula de Excel en inglés (`Range.Formula`) → LaTeX. Si algo no se entiende, la fórmula literal escapada."""
    f = "" if formula is None else str(formula)
    try:
        from openpyxl.formula.tokenizer import Tokenizer
        s = f.replace("@", "").strip()
        if not s.startswith("="): return _texto(f) if not s else _tex(("num", s)) if re.match(r"^-?\d+(\.\d+)?$", s) else _texto(f)
        p = _Parser(Tokenizer(s).items)
        arbol = p.expr()
        if p.i < len(p.t): raise ValueError("sobra " + str(p.ver().value))
        return _tex(arbol)
    except Exception:
        return _texto(f)


# ---------------------------------------------------------------- Excel por COM (solo lectura)
def _hoja(xl, hoja=None):
    wb = xl.ActiveWorkbook if hasattr(xl, "ActiveWorkbook") and xl.__class__.__name__ != "_Workbook" else xl
    try:
        return wb.Worksheets(hoja) if hoja else wb.ActiveSheet
    except Exception:
        raise ValueError(f"No encuentro la hoja «{hoja}»")


def _dir(rg):
    """Dirección relativa ('B2:B9'): Address es propiedad en el enlace tardío de pywin32."""
    return str(rg.Address).replace("$", "")


def _app(xl):
    try: return xl.Application
    except Exception: return xl


def _rango(xl, ref, hoja=None):
    ws = _hoja(xl, hoja)
    try:
        return ws.Range(str(ref).replace("$", ""))
    except Exception:
        raise ValueError(f"No entiendo la celda «{ref}»")


def caja_celda(xl, rango, hoja=None):
    """[x, y, w, h] (píxeles físicos de pantalla) de la celda o rango, o None si no se ve.
    Usa el panel (Pane) que contiene la celda, así sirve con paneles inmovilizados o divididos."""
    try:
        app = _app(xl)
        if not app.Visible or app.WindowState == -4140: return None          # oculto o minimizado
        rg = _rango(xl, rango, hoja)
        ws = rg.Worksheet
        if ws.Name != app.ActiveSheet.Name: return None                       # solo la hoja que se está viendo
        win = app.ActiveWindow
        for k in range(1, int(win.Panes.Count) + 1):
            pane = win.Panes(k)
            vis = pane.VisibleRange
            inter = app.Intersect(rg, vis)
            if inter is None: continue
            x0 = pane.PointsToScreenPixelsX(inter.Left); y0 = pane.PointsToScreenPixelsY(inter.Top)
            x1 = pane.PointsToScreenPixelsX(inter.Left + inter.Width); y1 = pane.PointsToScreenPixelsY(inter.Top + inter.Height)
            if x1 > x0 and y1 > y0: return [int(x0), int(y0), int(x1 - x0), int(y1 - y0)]
        return None
    except ValueError:
        raise
    except Exception:
        return None                                                           # Excel ocupado (editando una celda…)


def celdas_con_datos(xl, maximo=300):
    """Cajas de pantalla [x, y, w, h] de las celdas con algo que se ven en la hoja activa (una caja por tramo seguido
    de una fila): las tarjetas y notas de los dibujos no deben taparlas. Pocas llamadas COM: una por fila y columna."""
    out = []
    try:
        app = _app(xl); win = app.ActiveWindow; usada = app.ActiveSheet.UsedRange
        for k in range(1, int(win.Panes.Count) + 1):
            pane = win.Panes(k)
            inter = app.Intersect(usada, pane.VisibleRange)
            if inter is None: continue
            vals = inter.Value2
            if not isinstance(vals, tuple): vals = ((vals,),)
            filas, cols = inter.Rows.Count, inter.Columns.Count
            if filas * cols > 6000: continue                                    # demasiado: mejor nada que lento
            xs = [pane.PointsToScreenPixelsX(inter.Columns(j).Left) for j in range(1, cols + 1)]
            xs.append(pane.PointsToScreenPixelsX(inter.Left + inter.Width))
            ys = [pane.PointsToScreenPixelsY(inter.Rows(i).Top) for i in range(1, filas + 1)]
            ys.append(pane.PointsToScreenPixelsY(inter.Top + inter.Height))
            for i, fila in enumerate(vals):
                j = 0
                while j < len(fila):
                    if fila[j] in (None, ""): j += 1; continue
                    a = j
                    while j < len(fila) and fila[j] not in (None, ""): j += 1
                    if ys[i + 1] > ys[i] and xs[j] > xs[a]: out.append([int(xs[a]), int(ys[i]), int(xs[j] - xs[a]), int(ys[i + 1] - ys[i])])
                    if len(out) >= maximo: return out
    except Exception:
        pass                                                                  # Excel ocupado: sin cajas, no pasa nada
    return out


def _celda_con_formula(xl, ref, hoja):
    rg = _rango(xl, ref, hoja).Cells(1, 1)
    try:
        tiene = bool(rg.HasFormula)
    except Exception:
        raise ValueError("Excel está ocupado (¿estás escribiendo en una celda?). Pulsa Enter e inténtalo otra vez")
    if not tiene:
        raise ValueError(f"La celda {_dir(rg)} no tiene fórmula")
    return rg


def _formula_en(rg):
    try: return rg.Formula2
    except Exception: return rg.Formula


def _ref_partes(ref):
    """('Hoja2' | None, 'A1:B3') de un operando de fórmula."""
    m = re.match(r"^(?:('[^']+'|[^!]+)!)?(.+)$", ref)
    h = m.group(1)
    if h and h.startswith("'"): h = h[1:-1].replace("''", "'")
    return h, m.group(2).replace("$", "")


def _operandos(formula):
    """Las referencias (como texto) que aparecen en la fórmula, en orden."""
    from openpyxl.formula.tokenizer import Tokenizer
    out = []
    try:
        for k in Tokenizer(formula.replace("@", "")).items:
            if k.type == "OPERAND" and k.subtype == "RANGE" and _REF.match(k.value.replace("$", "")): out.append(k.value)
    except Exception:
        pass
    return out


def _txt(c):
    try: return c.Text
    except Exception: return ""


def datos_rayos_x(xl, ref, hoja=None):
    """{"r", "valor", "formula", "fuentes": [{"ref", "r" | None, "valor"}]}: las celdas de las que depende la fórmula."""
    rg = _celda_con_formula(xl, ref, hoja)
    ws = rg.Worksheet
    nombre = ws.Name
    fuentes, vistos = [], []
    try:
        prec = rg.DirectPrecedents
    except Exception:
        prec = None                                              # sin precedentes en esta hoja
    texto = _formula_en(rg).upper().replace("$", "")
    if prec is not None:
        for area in prec.Areas:
            n = int(area.Count)
            dir_ = _dir(area)
            # Excel junta en un área las celdas vecinas aunque la fórmula las use sueltas (=B2*2+B3 → B2:B3): si ese
            # rango no está escrito en la fórmula y son pocas, va cada celda por su lado
            celdas = [area.Cells(k) for k in range(1, n + 1)] if 1 < n <= 6 and dir_.upper() not in texto else [area]
            for c in celdas:
                d_ = _dir(c)
                v = _txt(c) if int(c.Count) == 1 else f"{int(c.Count)} valores"
                fuentes.append({"ref": d_, "r": caja_celda(xl, d_, nombre), "valor": v})
                vistos.append(d_)
    for o in _operandos(_formula_en(rg)):                        # referencias a otras hojas
        h, r = _ref_partes(o)
        if h and h.lower() != nombre.lower():
            try:
                c = ws.Parent.Worksheets(h).Range(r)
                v = _txt(c) if c.Count == 1 else f"{int(c.Count)} valores"
            except Exception:
                v = ""
            fuentes.append({"ref": f"{h}!{r}", "r": None, "valor": v})
    def clave(f):
        k = texto.find(f["ref"].upper().split("!")[-1])
        return k if k >= 0 else 10 ** 6
    fuentes.sort(key=clave)
    return {"r": caja_celda(xl, _dir(rg), nombre), "valor": _txt(rg), "formula": rg.FormulaLocal, "fuentes": fuentes}


def _numeros(rg):
    v = rg.Value
    if not isinstance(v, tuple): v = ((v,),)
    return [x for fila in v for x in fila]


def _es_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _grafica(xl, rg, formula):
    """La mini gráfica del primer rango de la fórmula con 2 o más números (o None)."""
    ws = rg.Worksheet
    for o in _operandos(formula):
        h, r = _ref_partes(o)
        if ":" not in r: continue
        try:
            hoja = ws.Parent.Worksheets(h) if h else ws
            rr = hoja.Range(r)
            vals = _numeros(rr)
        except Exception:
            continue
        nums = [x for x in vals if _es_num(x)]
        if len(nums) < 2: continue
        filas, cols = int(rr.Rows.Count), int(rr.Columns.Count)
        etiquetas = None
        lados = ([(0, -1), (0, cols)] if cols == 1 else [(-1, 0), (filas, 0)] if filas == 1 else [])
        for df, dc in lados:
            try:
                f0, c0 = int(rr.Row) + df, int(rr.Column) + dc
                if f0 < 1 or c0 < 1: continue
                lado = hoja.Range(hoja.Cells(f0, c0), hoja.Cells(f0 + (filas - 1 if cols == 1 else 0), c0 + (cols - 1 if filas == 1 else 0)))
                lv = [x for x in _numeros(lado)]
                if len(lv) == len(vals) and any(isinstance(x, str) and x.strip() for x in lv):
                    etiquetas = [str(x) if x is not None else "" for x in lv]; break
            except Exception:
                continue
        if etiquetas is None:
            etiquetas = [_dir(c) for c in rr.Cells]
        valores = [float(x) if _es_num(x) else 0.0 for x in vals]
        linea = None
        limpio = formula.replace("$", "").replace("'", "").upper()
        alvo = (h.upper() + "!" if h else "") + r.upper()
        m = re.search(r"(AVERAGE|MEDIAN|MAX|MIN)\(\s*" + re.escape(alvo) + r"\s*\)", limpio)
        if m:
            f = {"AVERAGE": (statistics.mean, "promedio"), "MEDIAN": (statistics.median, "mediana"),
                 "MAX": (max, "máximo"), "MIN": (min, "mínimo")}[m.group(1)]
            linea = {"valor": float(f[0](nums)), "texto": f[1]}
        return {"valores": valores, "etiquetas": etiquetas, "linea": linea}
    return None


def datos_formula(xl, ref, grafica=False, hoja=None):
    """{"r", "latex", "grafica": {"valores", "etiquetas", "linea"} | None}."""
    rg = _celda_con_formula(xl, ref, hoja)
    f = _formula_en(rg)
    return {"r": caja_celda(xl, _dir(rg), rg.Worksheet.Name), "latex": a_latex(f),
            "grafica": _grafica(xl, rg, f) if grafica else None}


def datos_desarmar(xl, ref, hoja=None):
    """{"r", "original"}: la fórmula como la ve la persona (FormulaLocal); las `partes` las pone el tutor."""
    rg = _rango(xl, ref, hoja).Cells(1, 1)
    try: orig = rg.FormulaLocal
    except Exception: raise ValueError("Excel está ocupado (¿estás escribiendo en una celda?)")
    if orig is None or str(orig) == "": raise ValueError(f"La celda {_dir(rg)} está vacía")
    return {"r": caja_celda(xl, _dir(rg), rg.Worksheet.Name), "original": str(orig)}


def excel_de_ventana(hwnd):
    """El Application de Excel cuya ventana principal es `hwnd`, o None. Solo lee: primero la ventana EXCEL7 (objeto
    nativo, sirve aunque el libro no esté guardado) y luego la tabla de objetos en ejecución (libros guardados)."""
    hwnd = int(hwnd)
    try:
        import win32gui, pythoncom, win32com.client, ctypes
        raiz = win32gui.GetAncestor(hwnd, 2) or hwnd                          # GA_ROOT
        hijos = []
        win32gui.EnumChildWindows(raiz, lambda h, _: hijos.append(h) or True, None)
        for h in hijos:
            if win32gui.GetClassName(h) != "EXCEL7": continue
            try:
                class GUID(ctypes.Structure):
                    _fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]
                iid = GUID(0x00020400, 0, 0, (ctypes.c_ubyte * 8)(0xC0, 0, 0, 0, 0, 0, 0, 0x46))   # IID_IDispatch
                ptr = ctypes.c_void_p()
                if ctypes.oledll.oleacc.AccessibleObjectFromWindow(h, 0xFFFFFFF0, ctypes.byref(iid), ctypes.byref(ptr)) != 0: continue
                disp = pythoncom.ObjectFromAddress(ptr.value, pythoncom.IID_IDispatch)
                app = win32com.client.Dispatch(disp).Application
                if int(app.Hwnd) == int(raiz): return app
            except Exception:
                continue
        rot = pythoncom.GetRunningObjectTable(); ctx = pythoncom.CreateBindCtx(0)
        for mk in rot.EnumRunning():
            try:
                nombre = mk.GetDisplayName(ctx, None)
                if not re.search(r"\.(xls[xmb]?|xlt[xm]?|csv)$", nombre, re.I): continue
                obj = rot.GetObject(mk).QueryInterface(pythoncom.IID_IDispatch)
                app = win32com.client.Dispatch(obj).Application
                if int(app.Hwnd) == int(raiz): return app
            except Exception:
                continue
    except Exception:
        return None
    return None


def resolver(xl, marca):
    """Los campos del lote para una marca de dibujo de Excel. Errores → ValueError con mensaje corto en español."""
    forma = marca.get("forma"); celda = marca.get("celda"); hoja = marca.get("hoja")
    if forma == "formula":
        if marca.get("latex") and not celda: return {"latex": marca["latex"], "grafica": marca.get("grafica") if isinstance(marca.get("grafica"), dict) else None, "r": None}
        if not celda: raise ValueError("Falta la celda de la fórmula")
        d = datos_formula(xl, celda, bool(marca.get("grafica")), hoja)
        if marca.get("latex"): d["latex"] = marca["latex"]
        return d
    if forma == "rayos_x":
        if not celda: raise ValueError("Falta la celda para los rayos X")
        d = datos_rayos_x(xl, celda, hoja)
        pasos = [{"decir": (f"Estas celdas, {f['ref']}, son {f['valor']}." if "valores" in str(f["valor"]) else f"Esta celda, {f['ref']}, vale {f['valor']}.")} for f in d["fuentes"]]
        pasos.append({"decir": f"Con todo eso, la fórmula da {d['valor']}."})
        d["pasos"] = pasos
        return d
    if forma == "desarmar":
        if celda:
            d = datos_desarmar(xl, celda, hoja)
            if marca.get("original") and marca["original"] != d["original"]: pass
            return d
        if not marca.get("original"): raise ValueError("Falta el texto o la celda a desarmar")
        return {"r": None, "original": marca["original"]}
    raise ValueError(f"Forma desconocida: {forma}")


# ---------------------------------------------------------------- pruebas
CASOS = [  # (fórmula en inglés, LaTeX esperado)
    ("=SUM(B2:B9)/COUNT(B2:B9)", r'\frac{\sum_{i=2}^{9} B_{i}}{\operatorname{CONTAR}\left(\text{B2}{:}\text{B9}\right)}'),
    ("=A1+B1", r'\text{A1} + \text{B1}'),
    ("=A1-B1*C1", r'\text{A1} - \text{B1} \cdot \text{C1}'),
    ("=(A1+B1)*C1", r'\left(\text{A1} + \text{B1}\right) \cdot \text{C1}'),
    ("=(A1+B1)/C1", r'\frac{\text{A1} + \text{B1}}{\text{C1}}'),
    ("=A1/B1/C1", r'\frac{\frac{\text{A1}}{\text{B1}}}{\text{C1}}'),
    ("=A1^2", r'\text{A1}^{2}'),
    ("=(A1+1)^(1/2)", r"\left(\text{A1} + 1\right)^{\frac{1}{2}}"),
    ("=A1^2^3", r'{\text{A1}^{2}}^{3}'),
    ("=SQRT(A1^2+B1^2)", r'\sqrt{\text{A1}^{2} + \text{B1}^{2}}'),
    ("=ABS(A1-B1)", r'\left|\text{A1} - \text{B1}\right|'),
    ("=SUM(B2:H2)", r'\sum_{j=\text{B}}^{\text{H}} x_{j,2}'),
    ("=SUM(A1:B9)", r'\operatorname{SUMA}\left(\text{A1}{:}\text{B9}\right)'),
    ("=SUM(A1;A2)".replace(";", ","), r'\operatorname{SUMA}\left(\text{A1} ; \text{A2}\right)'),
    ("=AVERAGE($B$2:$B$9)", r'\operatorname{PROMEDIO}\left(\text{B2}{:}\text{B9}\right)'),
    ("=A1<=B1", r'\text{A1} \le \text{B1}'),
    ("=A1>=10", r'\text{A1} \ge 10'),
    ("=A1<>B1", r'\text{A1} \ne \text{B1}'),
    ("=IF(A1>10,\"Alto\",\"Bajo\")", r'\begin{cases} \text{“Alto”} & \text{si } \text{A1} > 10 \\ \text{“Bajo”} & \text{en otro caso} \end{cases}'),
    ("=IF(A1>90,\"A\",IF(A1>70,\"B\",\"C\"))",
     r'\begin{cases} \text{“A”} & \text{si } \text{A1} > 90 \\ \text{“B”} & \text{si } \text{A1} > 70 \\ \text{“C”} & \text{en otro caso} \end{cases}'),
    ("=VLOOKUP(A2,Hoja2!A1:C9,3,FALSE)", r'\operatorname{BUSCARV}\left(\text{A2} ; \text{Hoja2!A1}{:}\text{C9} ; 3 ; \text{FALSO}\right)'),
    ("=Hoja2!A1+1", r'\text{Hoja2!A1} + 1'),
    ("='Mi Hoja'!B3*2", r'\text{Mi Hoja!B3} \cdot 2'),
    ("=ROUND(A1/B1,2)", r'\operatorname{REDONDEAR}\left(\frac{\text{A1}}{\text{B1}} ; 2\right)'),
    ("=A1&\" \"&B1", r'\text{A1} \mathbin{\&} \text{“ ”} \mathbin{\&} \text{B1}'),
    ("=A1*10%", r'\text{A1} \cdot 10\%'),
    ("=-A1", r'-\text{A1}'),
    ("=-A1^2", r'{-\text{A1}}^{2}'),
    ("=SUMIF(A1:A9,\">5\",B1:B9)", r'\operatorname{SUMAR.SI}\left(\text{A1}{:}\text{A9} ; \text{“>5”} ; \text{B1}{:}\text{B9}\right)'),
    ("=IFERROR(A1/B1,0)", r'\operatorname{SI.ERROR}\left(\frac{\text{A1}}{\text{B1}} ; 0\right)'),
    ("=MAX(A1:A9)-MIN(A1:A9)", r'\operatorname{MAX}\left(\text{A1}{:}\text{A9}\right) - \operatorname{MIN}\left(\text{A1}{:}\text{A9}\right)'),
    ("=TODAY()", r'\operatorname{HOY}\left(\right)'),
    ("=LEFT(A1,3)&\"_x\"", r'\operatorname{IZQUIERDA}\left(\text{A1} ; 3\right) \mathbin{\&} \text{“}\_\text{x”}'),
    ("=IF(AND(A1>1,B1<5),1,0)",
     r"\begin{cases} 1 & \text{si } \operatorname{Y}\left(\text{A1} > 1 ; \text{B1} < 5\right) \\ 0 & \text{en otro caso} \end{cases}"),
    ("=POWER(A1,3)", r'\text{A1}^{3}'),
    ("=FOO(A1,B1", None),                                         # mal formada: no debe romper
    ("=1+*", None),
]


def _probar_latex():
    ok = mal = 0
    for f, esperado in CASOS:
        try:
            r = a_latex(f)
        except Exception as e:
            r = f"EXCEPCIÓN {e}"
        if esperado is None:
            bien = isinstance(r, str) and r and "EXCEPCIÓN" not in r
        else:
            bien = r == esperado
        print(("✔" if bien else "✘"), f, "→", r if (not bien or esperado is None) else "")
        if not bien and esperado is not None: print("    esperado:", esperado)
        ok += bien; mal += not bien
    return mal == 0


def _probar_mathjax():
    """Cada salida de a_latex de la tabla debe compilar en MathJax (el mismo que usa la página), en el Chrome instalado."""
    import json, shutil, subprocess, tempfile
    from pathlib import Path
    raiz = Path(__file__).resolve().parent.parent
    if not shutil.which("node") or not (raiz / "herramientas" / "captura.js").exists():
        print("· MathJax: sin Node o sin herramientas/, se salta"); return True
    tp = raiz / "tutor-pantalla"
    lista = [a_latex(f) for f, _ in CASOS]
    with tempfile.TemporaryDirectory() as tmp:
        html = ('<!doctype html><meta charset="utf-8"><script>window.DIB_VENDOR=%s;window.LISTA=%s;</script><script src="%s"></script>'
                % (json.dumps((tp / "vendor").as_uri() + "/"), json.dumps(lista), (tp / "dibujante.js").as_uri()))
        banco = Path(tmp) / "banco.html"; banco.write_text(html, encoding="utf-8")
        expr = ("Promise.all(window.LISTA.map(function(l){ return Dibujante.U.tex(l,{px:20}).then(function(){return null;},"
                "function(e){return l;}); })).then(function(r){ return JSON.stringify(r); })")
        p = subprocess.run(["node", str(raiz / "herramientas" / "captura.js"), banco.as_uri(), str(Path(tmp) / "x.png"), "300", expr],
                           capture_output=True, text=True, encoding="utf-8", timeout=180)
        try:
            malas = [x for x in json.loads(json.loads(p.stdout.strip().splitlines()[-1])["valor"]) if x]
        except Exception:
            print("✘ MathJax: no pude comprobar:", (p.stderr or p.stdout)[-300:]); return False
    for m in malas: print("✘ MathJax no compila:", m)
    if not malas: print(f"✔ MathJax compila las {len(lista)} salidas")
    return not malas


def _probar_excel():
    import pythoncom, win32com.client
    pythoncom.CoInitialize()
    xl = win32com.client.DispatchEx("Excel.Application")
    bien = True

    def chk(nombre, cond, extra=""):
        nonlocal bien
        print(("✔" if cond else "✘"), nombre, extra); bien = bien and bool(cond)
    try:
        xl.Visible = True; xl.DisplayAlerts = False
        wb = xl.Workbooks.Add()
        ws = wb.Worksheets(1); ws.Name = "Datos"
        h2 = wb.Worksheets.Add(After=ws); h2.Name = "Hoja2"; h2.Range("A1").Value = 100
        ws.Activate()
        xl.WindowState = -4143; xl.ActiveWindow.Zoom = 100
        ws.Range("A1").Value = "Mes"; ws.Range("B1").Value = "Ventas"
        for i, (m, v) in enumerate(zip("ENE FEB MAR ABR MAY JUN JUL AGO".split(), [15, 20, 12, 30, 25, 18, 40, 22])):
            ws.Cells(2 + i, 1).Value = m; ws.Cells(2 + i, 2).Value = v
        ws.Range("D2").Formula = "=AVERAGE(B2:B9)"
        ws.Range("D3").Formula = "=SUM(B2:B9)/COUNT(B2:B9)"
        ws.Range("D4").Formula = '=IF(B2>10,"Alto","Bajo")'
        ws.Range("D5").Formula = "=B2+Hoja2!A1"
        ws.Range("D6").Formula = "=MAX(B2:B9)"
        ws.Range("D7").Value = 5
        a = xl.Hwnd
        # ---- datos
        d = datos_rayos_x(xl, "D5")
        chk("rayos_x D5: valor y fuentes", d["valor"] == "115" and [f["ref"] for f in d["fuentes"]] == ["B2", "Hoja2!A1"],
            f"{d['valor']} {[(f['ref'], f['valor'], bool(f['r'])) for f in d['fuentes']]}")
        chk("rayos_x D5: la de otra hoja sin caja", d["fuentes"][1]["r"] is None and d["fuentes"][1]["valor"] == "100")
        d = datos_rayos_x(xl, "D2")
        chk("rayos_x D2: un bloque de 8 valores con caja", len(d["fuentes"]) == 1 and d["fuentes"][0]["valor"] == "8 valores" and d["fuentes"][0]["r"], str(d["fuentes"]))
        chk("formula local", "PROMEDIO" in d["formula"] or "AVERAGE" in d["formula"], d["formula"])
        try: datos_rayos_x(xl, "D7"); chk("sin fórmula → ValueError", False)
        except ValueError as e: chk("sin fórmula → ValueError", True, str(e))
        g = datos_formula(xl, "D2", grafica=True)
        chk("gráfica D2: 8 valores, etiquetas de meses y línea promedio",
            g["grafica"] and len(g["grafica"]["valores"]) == 8 and g["grafica"]["etiquetas"][0] == "ENE"
            and g["grafica"]["linea"] and g["grafica"]["linea"]["texto"] == "promedio" and abs(g["grafica"]["linea"]["valor"] - 22.75) < 1e-9, str(g["grafica"]["linea"]))
        g = datos_formula(xl, "D6", grafica=True)
        chk("gráfica D6: línea máximo", g["grafica"]["linea"] == {"valor": 40.0, "texto": "máximo"})
        g = datos_formula(xl, "D3", grafica=True)
        chk("gráfica D3: sin línea (no es promedio)", g["grafica"] and g["grafica"]["linea"] is None)
        chk("latex de D3", g["latex"] == CASOS[0][1], g["latex"])
        g = datos_formula(xl, "D4", grafica=True)
        chk("gráfica D4: ninguna", g["grafica"] is None)
        o = datos_desarmar(xl, "D3")
        chk("desarmar D3: original local", "B2:B9" in o["original"], o["original"])
        # ---- cajas: verificar que caen EXACTO en la celda (comparando con el rectángulo real por UI)
        import ctypes
        from ctypes import wintypes as W
        for zoom in (100, 70, 150):
            xl.ActiveWindow.Zoom = zoom
            c1 = caja_celda(xl, "B2"); c2 = caja_celda(xl, "D5"); c3 = caja_celda(xl, "B2:B9")
            ok = c1 and c2 and c3 and c3[3] > c1[3] * 7 and c2[0] > c1[0] and c3[0] == c1[0]
            chk(f"cajas zoom {zoom} %", ok, f"B2={c1} D5={c2} B2:B9={c3}")
            # tamaño esperado de la celda: ancho en puntos → píxeles físicos (ppp del sistema)
            if c1:
                ppp = ctypes.windll.user32.GetDpiForWindow(xl.Hwnd) if hasattr(ctypes.windll.user32, "GetDpiForWindow") else 96
                esp_w = ws.Range("B2").Width * ppp / 72 * zoom / 100
                esp_h = ws.Range("B2").Height * ppp / 72 * zoom / 100
                chk(f"  tamaño B2 ≈ puntos×ppp×zoom (zoom {zoom})", abs(c1[2] - esp_w) <= 2 and abs(c1[3] - esp_h) <= 2,
                    f"{c1[2]}x{c1[3]} esperado {esp_w:.1f}x{esp_h:.1f} (ppp {ppp})")
        xl.ActiveWindow.Zoom = 100
        chk("celda lejana fuera de pantalla → None", caja_celda(xl, "AZ900") is None)
        chk("otra hoja → None", caja_celda(xl, "A1", "Hoja2") is None)
        # ---- paneles inmovilizados
        ws.Activate(); xl.ActiveWindow.ScrollRow = 1; xl.ActiveWindow.ScrollColumn = 1
        ws.Range("C3").Select()
        xl.ActiveWindow.FreezePanes = True
        pre = caja_celda(xl, "B2"); pre_d = caja_celda(xl, "D5")
        xl.ActiveWindow.ScrollRow = 6                              # el panel de abajo se desplaza
        c_fija = caja_celda(xl, "B2"); c_scroll = caja_celda(xl, "B8"); c_oculta = caja_celda(xl, "B3")
        chk("paneles: celda del panel fijo sigue en su sitio", c_fija == pre, f"{pre} → {c_fija}")
        chk("paneles: celda del panel que se desplaza se ve", c_scroll is not None and c_scroll[1] > c_fija[1], str(c_scroll))
        chk("paneles: fila escondida por el desplazamiento → None", c_oculta is None, str(c_oculta))
        xl.ActiveWindow.FreezePanes = False; xl.ActiveWindow.ScrollRow = 1
        # ---- excel_de_ventana (solo con mi hwnd)
        app = excel_de_ventana(a)
        chk("excel_de_ventana(mi hwnd)", app is not None and int(app.Hwnd) == int(a))
        chk("excel_de_ventana(hwnd cualquiera) → None", excel_de_ventana(1) is None)
        # ---- resolver
        r = resolver(xl, {"tipo": "dibujo", "forma": "rayos_x", "celda": "D3"})
        chk("resolver rayos_x", r["valor"] == "22.75" or r["valor"].startswith("22"), str(r["valor"]) + " " + str(len(r["pasos"])) + " pasos")
        r = resolver(xl, {"tipo": "dibujo", "forma": "formula", "celda": "D2", "grafica": True})
        chk("resolver formula", r["latex"] and r["grafica"])
        r = resolver(xl, {"tipo": "dibujo", "forma": "formula", "latex": r"x^2"})
        chk("resolver formula con latex propio y sin celda", r["latex"] == "x^2" and r["r"] is None)
        r = resolver(xl, {"tipo": "dibujo", "forma": "desarmar", "celda": "D4"})
        chk("resolver desarmar", r["original"].count("Alto") == 1, r["original"])
        try: resolver(xl, {"forma": "rayos_x", "celda": "D7"}); chk("resolver sin fórmula → ValueError", False)
        except ValueError: chk("resolver sin fórmula → ValueError", True)
        # solo lectura: el libro no cambió
        chk("el libro sigue sin guardar y sin cambios de contenido", ws.Range("D2").Formula == "=AVERAGE(B2:B9)" and wb.Saved is False)
    finally:
        try: wb.Close(SaveChanges=False)
        except Exception: pass
        try: xl.Quit()
        except Exception: pass
    return bien


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    if "--probar" in sys.argv:
        todo = _probar_latex()
        todo = _probar_mathjax() and todo
        if "--excel" in sys.argv: todo = _probar_excel() and todo
        print("Rayos X: todo bien" if todo else "Rayos X: HAY FALLOS")
        sys.exit(0 if todo else 1)
    print(__doc__)
