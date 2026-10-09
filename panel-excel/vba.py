"""VBA en el panel de Excel (lo usa motor.py; el formato está en README.md). Con cuidado: una macro puede hacer cualquier
cosa en la PC, así que:
- Todo pide que la persona haya activado una vez «Confiar en el acceso al modelo de objetos de proyectos de VBA»
  (Centro de confianza). El panel lo detecta y, si no está, explica cómo activarlo; nunca lo cambia él.
- El tutor LEE los módulos (en el [Estado actual]), MARCA líneas con comentarios temporales «' <- tutor: …» (una línea
  aparte encima, que se quita con Borrar marcas; en ASCII, porque el editor de VBA guarda en ANSI y una «←» quedaba
  como «?» y ya no se reconocía) y PROPONE código con la tarjeta de permiso (Deshacer deja el módulo
  como estaba). Nunca ejecuta nada.
- Antes de insertar o ejecutar código: análisis estático con lista negra fuerte (analizar).
- Comprobar de un ejercicio de VBA (solo al pulsarlo): copia la hoja a un libro temporal, mete ahí el código de la
  persona con un vigía en cada bucle (corta a los pocos segundos) y sin MsgBox/InputBox que se queden esperando,
  la ejecuta, hace lo mismo con la solución y compara los resultados. Los libros temporales se cierran sin guardar.
Todo se usa desde el hilo de Excel (COM)."""
import codecs, ctypes, re, threading, time, unicodedata
import motor as M

ACCESO = ("Para las macros, activa una vez en Excel: Archivo → Opciones → Centro de confianza → Configuración del Centro de "
          "confianza → Configuración de macros → «Confiar en el acceso al modelo de objetos de proyectos de VBA». Después vuelve a pulsar.")
MARCA = "' <- tutor: "          # solo ASCII: el editor de VBA guarda en ANSI
# Se reconocen (y se quitan) la marca de ahora y las de antes: «' ← tutor:», que el editor guardó como «' ? tutor:»
ES_MARCA = re.compile(r"^\s*'\s*(<-|←|\?)\s*tutor:", re.I)
MAX_LINEAS, MAX_CHARS = 400, 20000
NOMBRE_MODULO = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,30}$")
NOMBRE_MACRO = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,60}$")
TIPOS = {1: "módulo", 2: "módulo de clase", 3: "formulario", 100: "hoja o libro"}


def _pagina_ansi():
    """La página de códigos ANSI de Windows (la del editor de VBA): cp1252 en Windows en español o inglés."""
    try: return codecs.lookup(f"cp{ctypes.windll.kernel32.GetACP()}").name
    except Exception: return "cp1252"


PAGINA = _pagina_ansi()
PARECIDOS = {"←": "<-", "→": "->", "↑": "^", "↓": "v", "↔": "<->", "⇒": "=>", "✔": "OK", "✓": "OK", "✘": "X", "✗": "X",
             "≤": "<=", "≥": ">=", "≠": "<>", "·": "-", "•": "-", "…": "..."}


def ansi(texto):
    """El texto tal como lo guarda el editor de VBA (ANSI): lo que no cabe se cambia por algo parecido («→» por «->»,
    una letra con un signo raro por la letra sola) en vez de quedar como «?»."""
    out = []
    for ch in texto:
        try: ch.encode(PAGINA); out.append(ch); continue
        except UnicodeEncodeError: pass
        if ch in PARECIDOS: out.append(PARECIDOS[ch]); continue
        base = "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))
        try: base.encode(PAGINA); out.append(base or "?")
        except UnicodeEncodeError: out.append("?")
    return "".join(out)


def es_marca(linea):
    """¿Es una línea de marca del tutor? (la de ahora o una de antes)."""
    return bool(ES_MARCA.match(linea))


def acceso(wb):
    """¿Activó la persona el acceso al proyecto de VBA? (sin él no se puede leer ni escribir código)."""
    try: wb.VBProject.VBComponents.Count; return True
    except Exception: return False


# ---------- Análisis estático ----------
# palabra (sin distinguir mayúsculas) → qué hace
VETADAS = {
    "shell": "ejecuta programas", "kill": "borra archivos", "rmdir": "borra carpetas", "mkdir": "crea carpetas", "chdir": "cambia de carpeta",
    "chdrive": "cambia de disco", "filecopy": "copia archivos", "setattr": "cambia archivos", "filelen": "lee archivos", "filedatetime": "lee archivos",
    "freefile": "abre archivos", "curdir": "lee carpetas", "environ": "lee datos del sistema", "sendkeys": "simula el teclado",
    "appactivate": "cambia de programa", "declare": "llama al sistema (Declare)", "ptrsafe": "llama al sistema (Declare)",
    "addressof": "usa direcciones de memoria", "varptr": "usa direcciones de memoria", "objptr": "usa direcciones de memoria",
    "strptr": "usa direcciones de memoria", "callbyname": "llama a cualquier cosa por su nombre", "macscript": "ejecuta scripts",
    "savesetting": "escribe en el registro", "getsetting": "lee el registro", "getallsettings": "lee el registro", "deletesetting": "borra del registro",
    "getobject": "abre otros programas o archivos", "vbproject": "cambia el código de VBA", "vbe": "cambia el código de VBA",
    "vbcomponents": "cambia el código de VBA", "codemodule": "cambia el código de VBA", "workbooks": "abre, crea o cierra libros",
    "executeexcel4macro": "ejecuta macros antiguas", "evaluate": "evalúa texto como fórmula", "run": "ejecuta otras macros",
    "onkey": "cambia el teclado de Excel", "ontime": "programa macros para más tarde", "onundo": "cambia Excel", "onrepeat": "cambia Excel",
    "wait": "detiene Excel", "followhyperlink": "abre enlaces", "hyperlinks": "crea enlaces", "addins": "toca los complementos",
    "saveas": "guarda archivos", "savecopyas": "guarda archivos", "exportasfixedformat": "crea archivos", "export": "crea archivos",
    "printout": "imprime", "printpreview": "abre la vista previa", "sendmail": "manda correos", "mailenvelope": "manda correos",
    "connections": "usa conexiones externas", "querytables": "usa consultas externas", "queries": "cambia consultas", "oleobjects": "inserta objetos de otros programas",
    "addpicture": "lee archivos", "getopenfilename": "abre diálogos", "getsaveasfilename": "abre diálogos", "filedialog": "abre diálogos",
    "dialogs": "abre diálogos", "quit": "cierra Excel", "urldownloadtofile": "descarga de internet", "stop": "detiene la macro en el editor",
    "changefileaccess": "cambia el acceso al archivo", "protect": "protege con contraseña", "unprotect": "quita protecciones",
    "automationsecurity": "cambia la seguridad",
}
CREATEOBJECT_OK = {"scripting.dictionary", "vbscript.regexp"}
EVENTOS = re.compile(r"\b(Sub|Function)\s+(Auto_Open|Auto_Close|Auto_Activate|Auto_Deactivate|Workbook_\w+|Worksheet_\w+|App_\w+|Chart_\w+|Class_\w+)\b", re.I)
SENTENCIAS = [
    (re.compile(r"^\s*Open\s+.+\s+For\s+", re.I), "abre archivos (Open … For)"),
    (re.compile(r"^\s*(Print|Write|Put|Get|Input|Line\s+Input|Lock|Unlock|Seek)\s*#", re.I), "lee o escribe archivos"),
    (re.compile(r"^\s*Name\s+\S.*\s+As\s+", re.I), "renombra archivos (Name … As)"),
    (re.compile(r"\.\s*(Close|Save)\b", re.I), "cierra o guarda libros"),
    (re.compile(r"\.\s*Show\b", re.I), "abre formularios o diálogos (.Show)"),
    (re.compile(r"\bDir\s*\$?\s*\(", re.I), "lee carpetas (Dir)"),
    (re.compile(r"\bApplication\s*\.\s*InputBox\b", re.I), "abre un diálogo (Application.InputBox)"),
    (re.compile(r"\bDebug\s*\.\s*Assert\b", re.I), "detiene la macro en el editor (Debug.Assert)"),
]


def _logicas(codigo):
    """Las líneas lógicas (las que siguen con « _» se juntan): [(número de la primera, texto)]."""
    out, actual, inicio = [], "", 1
    for i, linea in enumerate(codigo.replace("\r\n", "\n").replace("\r", "\n").split("\n"), 1):
        if not actual: inicio = i
        if re.search(r"\s_\s*$", linea): actual += re.sub(r"\s_\s*$", " ", linea); continue
        out.append((inicio, actual + linea)); actual = ""
    if actual: out.append((inicio, actual))
    return out


def _sin_textos(linea):
    """(código sin comentarios y con los textos vacíos "", el mismo código con sus textos) de una línea lógica."""
    out, con, i, n = [], [], 0, len(linea)
    while i < n:
        ch = linea[i]
        if ch == '"':
            j = i + 1
            while j < n:
                if linea[j] == '"':
                    if j + 1 < n and linea[j + 1] == '"': j += 2; continue
                    break
                j += 1
            out.append('""'); con.append(linea[i:j + 1]); i = j + 1; continue
        if ch == "'": break
        out.append(ch); con.append(ch); i += 1
    codigo = "".join(out)
    if re.match(r"^\s*Rem\b", codigo, re.I): return "", ""
    return codigo, "".join(con)


def problemas(codigo, quien="tutor"):
    """Lo que no se permite en un código VBA, como [(línea, motivo)]. quien: «tutor» (lo que propone) o «persona»
    (lo que Comprobar va a ejecutar)."""
    out = []
    if not isinstance(codigo, str): return [(0, "el código tiene que ser un texto")]
    if "\x00" in codigo: out.append((0, "el código tiene caracteres raros"))
    for n, linea in _logicas(codigo):
        cod, con_textos = _sin_textos(linea)
        if not cod.strip(): continue
        palabras = {p.lower() for p in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", cod)}
        for p in sorted(palabras & set(VETADAS)): out.append((n, f"«{p}» ({VETADAS[p]})"))
        for rx, motivo in SENTENCIAS:
            for st in re.split(r":(?!=)", cod):
                if rx.search(st): out.append((n, motivo)); break
        if "[" in cod: out.append((n, "[…] evalúa texto como fórmula"))
        usos = len(re.findall(r"\bCreateObject\b", cod, re.I))
        if usos:
            buenos = [t for t in re.findall(r'\bCreateObject\s*\(\s*"([^"]*)"\s*\)', con_textos, re.I) if t.lower() in CREATEOBJECT_OK]
            if len(buenos) != usos: out.append((n, "CreateObject solo vale con \"Scripting.Dictionary\" o \"VBScript.RegExp\""))
        if quien == "tutor" and EVENTOS.search(cod): out.append((n, "una macro que se ejecuta sola (eventos o Auto_Open): no se permite"))
    return out


def analizar(codigo, quien="tutor"):
    """Lanza ValueError con un mensaje claro si el código no pasa la revisión."""
    if isinstance(codigo, str) and (len(codigo) > MAX_CHARS or codigo.count("\n") >= MAX_LINEAS):
        raise ValueError(f"el código es demasiado largo (máximo {MAX_LINEAS} líneas)")
    ps = problemas(codigo, quien)
    if ps:
        lista = "; ".join((f"línea {n}: " if n else "") + m for n, m in ps[:4]) + ("…" if len(ps) > 4 else "")
        raise ValueError(f"por seguridad no se puede usar ese código ({lista})")


# ---------- Leer, marcar y cambiar módulos ----------
def _texto(comp):
    cm = comp.CodeModule; n = cm.CountOfLines
    return cm.Lines(1, n).replace("\r\n", "\n") if n else ""


def _sin_marcas(texto):
    return "\n".join(l for l in texto.split("\n") if not es_marca(l))


def modulos(wb):
    """[(nombre, tipo, código sin las marcas del tutor)] de los módulos que tienen algo más que «Option …»."""
    out = []
    for comp in wb.VBProject.VBComponents:
        t = _sin_marcas(_texto(comp))
        if any(l.strip() and not re.match(r"^\s*Option\s", l, re.I) for l in t.split("\n")): out.append((comp.Name, comp.Type, t))
    return out


def buscar_proc(mods, macro):
    """(módulo, ¿privada?) donde está la Sub o Function «macro», o None."""
    rx = re.compile(rf"^\s*(Public\s+|Private\s+|Friend\s+)?(Static\s+)?(Sub|Function)\s+{re.escape(macro)}\b", re.I | re.M)
    for nombre, tipo, t in mods:
        m = rx.search(t)
        if m: return nombre, tipo, bool(m.group(1) and m.group(1).strip().lower() == "private")
    return None


def contexto(wb, max_lineas=160):
    """Los módulos de la persona con sus líneas numeradas, para el [Estado actual] del tutor."""
    if not acceso(wb): return "VBA: no tengo acceso al código (la persona no activó «Confiar en el acceso al modelo de objetos de proyectos de VBA»)."
    partes, quedan = [], max_lineas
    for nombre, tipo, t in modulos(wb):
        lineas = t.split("\n")
        partes.append(f"Módulo '{nombre}' ({TIPOS.get(tipo, tipo)}):\n" + "\n".join(f"{i:>3}: {l}" for i, l in enumerate(lineas[:quedan], 1))
                      + ("\n    …" if len(lineas) > quedan else ""))
        quedan -= len(lineas)
        if quedan <= 0: break
    return "Código VBA del libro:\n" + "\n".join(partes) if partes else "VBA: el libro todavía no tiene macros."


def borrar_marcas(wb):
    """Quita las líneas «' <- tutor: …» de todos los módulos (también las de antes: «' ← tutor:» y «' ? tutor:»)."""
    if not acceso(wb): return 0
    n = 0
    for comp in wb.VBProject.VBComponents:
        cm = comp.CodeModule; lineas = _texto(comp).split("\n")
        for i in range(len(lineas), 0, -1):
            if es_marca(lineas[i - 1]): cm.DeleteLines(i, 1); n += 1
    return n


def marcar(wb, marcas):
    """Marcas {"tipo": "linea", "modulo", "linea", "texto"}: una línea de comentario encima de esa línea (los números son
    los del [Estado actual], sin marcas). Antes quita las anteriores. Devuelve (hechas, fallos)."""
    if not acceso(wb): return 0, [f"linea: sin acceso al código VBA ({ACCESO})"]
    borrar_marcas(wb); fallos, hechas = [], 0
    comps = {c.Name.lower(): c for c in wb.VBProject.VBComponents}
    for m in sorted(marcas, key=lambda x: -int(x.get("linea", 0) or 0)):
        comp = comps.get(str(m.get("modulo", "")).lower())
        if comp is None: fallos.append(f"linea: no hay un módulo «{m.get('modulo')}»"); continue
        lineas = _texto(comp).split("\n"); k = m.get("linea")
        if not isinstance(k, int) or not 1 <= k <= len(lineas): fallos.append(f"linea: el módulo «{comp.Name}» no tiene la línea {k}"); continue
        while k > 1 and re.search(r"\s_\s*$", lineas[k - 2]): k -= 1          # al principio de la sentencia (las que siguen con « _» van juntas)
        sangria = re.match(r"\s*", lineas[k - 1]).group(0)
        texto = ansi(" ".join(str(m.get("texto", "mira aquí")).split())[:80].replace('"', "'"))
        comp.CodeModule.InsertLines(k, sangria + MARCA + texto); hechas += 1
    return hechas, fallos


def aplicar(wb, a):
    """{"vba": "Módulo", "codigo": "...", "modo": "reemplazar" | "agregar"}: crea o cambia un módulo normal.
    Devuelve lo que hace falta para deshacerlo."""
    if not acceso(wb): raise ValueError(ACCESO)
    analizar(a["codigo"], "tutor")
    vbp = wb.VBProject; comp = next((c for c in vbp.VBComponents if c.Name.lower() == a["vba"].lower()), None)
    if comp is not None and comp.Type != 1: raise ValueError(f"«{comp.Name}» no es un módulo normal (es {TIPOS.get(comp.Type, comp.Type)}): usa otro nombre")
    antes = None if comp is None else _texto(comp)
    if comp is None:
        comp = vbp.VBComponents.Add(1); comp.Name = a["vba"]
    cm = comp.CodeModule; codigo = ansi(a["codigo"]).replace("\r\n", "\n").strip("\n").replace("\n", "\r\n")
    if a.get("modo", "reemplazar") == "reemplazar":
        if cm.CountOfLines: cm.DeleteLines(1, cm.CountOfLines)
        cm.AddFromString(codigo)
    else: cm.InsertLines(cm.CountOfLines + 1, codigo)
    return {"modulo": comp.Name, "antes": antes, "despues": _texto(comp)}


def cambiado(wb, estado):
    """¿Cambió la persona el módulo después de aplicar?"""
    try:
        comp = next((c for c in wb.VBProject.VBComponents if c.Name.lower() == estado["modulo"].lower()), None)
        return comp is None or _sin_marcas(_texto(comp)) != _sin_marcas(estado["despues"])
    except Exception: return False


def restaurar(wb, estado):
    """Deshacer: el módulo vuelve a como estaba (o se quita, si lo creó el tutor)."""
    vbp = wb.VBProject; comp = next((c for c in vbp.VBComponents if c.Name.lower() == estado["modulo"].lower()), None)
    if comp is None: return
    if estado["antes"] is None: vbp.VBComponents.Remove(comp); return
    cm = comp.CodeModule
    if cm.CountOfLines: cm.DeleteLines(1, cm.CountOfLines)
    if estado["antes"]: cm.AddFromString(estado["antes"].replace("\n", "\r\n"))


def validar_accion(a, d):
    if not isinstance(a["vba"], str) or not NOMBRE_MODULO.match(a["vba"]): raise ValueError(f"{d}: el módulo es un nombre sin espacios (Modulo1, Macros…)")
    if a["vba"].lower() in ("thisworkbook", "estelibro") or re.match(r"^(hoja|sheet)\d+$", a["vba"], re.I):
        raise ValueError(f"{d}: el código va en un módulo normal, no en el de una hoja o del libro")
    if a.get("modo", "reemplazar") not in ("reemplazar", "agregar"): raise ValueError(f"{d}: «modo» es reemplazar o agregar")
    if not isinstance(a.get("codigo"), str) or not a["codigo"].strip(): raise ValueError(f"{d}: «codigo» es el código VBA")
    try: analizar(a["codigo"], "tutor")
    except ValueError as e: raise ValueError(f"{d}: {e}") from None


def validar_turno(t, donde="turno"):
    if not isinstance(t["macro"], str) or not NOMBRE_MACRO.match(t["macro"]): raise ValueError(f"{donde}: «macro» es el nombre de la Sub que escribe la persona")
    if "solucion_vba" in t:
        try: analizar(t["solucion_vba"], "tutor")
        except ValueError as e: raise ValueError(f"{donde} (solución): {e}") from None
        if not buscar_proc([("x", 1, t["solucion_vba"])], t["macro"]): raise ValueError(f"{donde}: la «solucion_vba» tiene que tener una Sub {t['macro']}")
    if "entradas" in t and (not isinstance(t["entradas"], list) or len(t["entradas"]) > 10 or not all(isinstance(x, (str, int, float)) for x in t["entradas"])):
        raise ValueError(f"{donde}: «entradas» es una lista de respuestas para InputBox")
    if "limite" in t and (not isinstance(t["limite"], (int, float)) or not 1 <= t["limite"] <= 10): raise ValueError(f"{donde}: «limite» va de 1 a 10 segundos")
    for e in t.get("errores", []):
        if "vba" in e:
            try: analizar(e["vba"], "tutor")
            except ValueError as x: raise ValueError(f"{donde} (error típico): {x}") from None


# ---------- Comprobar de un ejercicio de VBA ----------
VIGIA = '''Option Explicit
Public tutorInicio As Double
Public tutorEntradas As Variant
Public tutorN As Long
Public Sub tutorVigia()
    If Timer < tutorInicio Or Timer - tutorInicio > {limite} Then
        ThisWorkbook.Names.Add Name:="tutorCortado", RefersTo:="=1"
        End
    End If
End Sub
Public Function tutorEntrada() As String
    tutorN = tutorN + 1
    If IsArray(tutorEntradas) Then
        If tutorN - 1 <= UBound(tutorEntradas) Then tutorEntrada = CStr(tutorEntradas(tutorN - 1))
    End If
End Function
Public Sub tutorCorrer()
    On Error GoTo fallo
    tutorInicio = Timer: tutorN = 0
    tutorEntradas = Array({entradas})
    {llamada}
    ThisWorkbook.Names.Add Name:="tutorFin", RefersTo:="=1"
    Exit Sub
fallo:
    ThisWorkbook.Names.Add Name:="tutorError", RefersTo:="=""" & Replace(Left(Err.Description, 200), """", "'") & """"
End Sub
'''
STUBS = '''
Private Function MsgBox(Optional Prompt, Optional Buttons, Optional Title, Optional HelpFile, Optional Context) As Long
    MsgBox = 1
End Function
Private Function InputBox(Optional Prompt, Optional Title, Optional Default, Optional XPos, Optional YPos, Optional HelpFile, Optional Context) As String
    InputBox = tutorEntrada()
End Function
'''


def _sentencias(linea):
    """Parte una línea lógica por «:» fuera de los textos (sin romper «Nombre:=»): (sentencias, comentario)."""
    partes, buf, enc, i = [], "", False, 0
    while i < len(linea):
        ch = linea[i]
        if ch == '"': enc = not enc
        elif not enc and ch == "'": return partes + [buf], linea[i:]
        elif not enc and ch == ":" and linea[i + 1:i + 2] != "=": partes.append(buf); buf = ""; i += 1; continue
        buf += ch; i += 1
    return partes + [buf], ""


def instrumentar(codigo):
    """El código con «Call tutorVigia» antes de cada Next, Loop, Wend, GoTo y Resume (corta los bucles que no terminan)
    y con MsgBox e InputBox de mentira (no se quedan esperando a que alguien pulse Aceptar).
    Va con «Call»: «tutorVigia: Loop» al empezar una sentencia es una ETIQUETA (el editor la manda a la columna 1 y el
    vigía nunca se llamaba)."""
    out = []
    for _, linea in _logicas(codigo):
        cod, _ = _sin_textos(linea)
        if not cod.strip(): out.append(linea); continue
        sentencias, comentario = _sentencias(linea)      # sobre la línea original: los textos y comentarios no se tocan
        nuevas = []
        for st in sentencias:
            if re.match(r"^\s*(Next|Loop|Wend|GoTo|Resume)\b", st, re.I) and not re.match(r"^\s*Resume\s+Next\b", st, re.I):
                st = " Call tutorVigia: " + st.lstrip()
            st = re.sub(r"\b(Then|Else)\s+(GoTo|Resume)\b(?!\s+Next\b)", r"\1 Call tutorVigia: \2", st, flags=re.I)
            nuevas.append(st)
        out.append(":".join(nuevas) + comentario)
    texto = "\n".join(out)
    if not re.search(r"\b(Function|Sub)\s+MsgBox\b", texto, re.I) and not re.search(r"\b(Function|Sub)\s+InputBox\b", texto, re.I): texto += STUBS
    return texto


MODULO_VIGIA = "zzTutorPanel"     # el módulo del vigía: NUNCA con el nombre de uno de sus procedimientos (tutorVigia), o
                                  # «Call tutorVigia» es un error de compilación («se esperaba un procedimiento, no un módulo»)


def _vigilar_dialogos(pid, flujo, parar, res):
    """Mientras corre la macro (en otro hilo): si aparece un aviso de Visual Basic (error de compilación, error en tiempo
    de ejecución), pulsa su botón seguro (Finalizar / Aceptar) y guarda su texto; y si VBA queda en modo interrupción
    (tras un error de compilación o un Debug.Assert), lo restablece, para que Excel no se quede esperando.
    Solo mira ventanas (sin COM) mientras la macro corre; usa Excel por COM (pasado de hilo con `flujo`) solo para
    restablecer, que es cuando Excel acepta llamadas."""
    try:
        import pythoncom, win32com.client, win32gui, win32process, win32con
        pythoncom.CoInitialize()
    except Exception: return
    xl = None
    try: xl = win32com.client.Dispatch(pythoncom.CoGetInterfaceAndReleaseStream(flujo, pythoncom.IID_IDispatch))
    except Exception: pass
    try:
        while not parar.is_set():
            vistos = {"dialogo": False, "interrupcion": False}
            def ver(h, _):
                try:
                    if win32process.GetWindowThreadProcessId(h)[1] != pid or not win32gui.IsWindowVisible(h): return
                    clase, titulo = win32gui.GetClassName(h), win32gui.GetWindowText(h)
                    if clase == "wndclass_desked_gsk" and re.search(r"\[(interrupci|break)", titulo, re.I): vistos["interrupcion"] = True
                    if clase != "#32770" or "visual basic" not in titulo.lower(): return
                    vistos["dialogo"] = True; hijos = []
                    win32gui.EnumChildWindows(h, lambda c, _: hijos.append(c), None)
                    texto = " ".join(t for t in (win32gui.GetWindowText(c).strip() for c in hijos if win32gui.GetClassName(c) == "Static") if t)
                    if texto and not res.get("aviso"): res["aviso"] = " ".join(texto.split())[:200]
                    for b in hijos:
                        if win32gui.GetClassName(b) == "Button" and win32gui.GetWindowText(b).replace("&", "").lower() in ("finalizar", "end", "aceptar", "ok"):
                            win32gui.PostMessage(b, win32con.BM_CLICK, 0, 0); return
                except Exception: pass
            try: win32gui.EnumWindows(ver, None)
            except Exception: pass
            if vistos["interrupcion"] and not vistos["dialogo"] and xl is not None:
                try:
                    xl.VBE.CommandBars.FindControl(1, 228).Execute()        # 228 = Ejecutar → Restablecer
                    res["restablecida"] = True
                    if not res.get("vbe_visible"): xl.VBE.MainWindow.Visible = False
                except Exception: pass
            parar.wait(0.3)
    finally:
        xl = None
        try: pythoncom.CoUninitialize()
        except Exception: pass


def _copia(xl, ws):
    """La hoja copiada a un libro temporal nuevo (sin guardar). Devuelve (libro, hoja)."""
    antes = {w.Name for w in xl.Workbooks}
    a = xl.DisplayAlerts; xl.DisplayAlerts = False
    try: ws.Copy()                                     # sin argumentos: a un libro nuevo
    finally: xl.DisplayAlerts = a
    tmp = next(w for w in xl.Workbooks if w.Name not in antes)
    return tmp, tmp.Worksheets(1)


def _correr(xl, ws, mods, macro, entradas=(), limite=4):
    """Copia la hoja a un libro temporal, mete el código (instrumentado) y ejecuta la macro. Devuelve
    {"wb", "ws", "error", "cortada", "segundos"}; el libro temporal lo cierra quien llama."""
    tmp, hoja = _copia(xl, ws)
    res = {"wb": tmp, "ws": hoja, "error": None, "cortada": False, "segundos": 0.0}
    vbp = tmp.VBProject; donde = None
    for nombre, tipo, codigo in mods:
        if tipo != 1: continue
        comp = vbp.VBComponents.Add(1); comp.Name = nombre
        cm = comp.CodeModule
        if cm.CountOfLines: cm.DeleteLines(1, cm.CountOfLines)
        cm.AddFromString(instrumentar(ansi(codigo)).replace("\n", "\r\n"))
        if donde is None and buscar_proc([(nombre, 1, codigo)], macro): donde = nombre
    if donde is None: res["error"] = f"no encontré la Sub {macro} en un módulo normal"; return res
    lista = ", ".join('"' + str(x).replace('"', '""') + '"' for x in entradas)
    vig = vbp.VBComponents.Add(1); vig.Name = MODULO_VIGIA
    vig.CodeModule.AddFromString(VIGIA.format(limite=float(limite), entradas=lista, llamada=f"{donde}.{macro}").replace("\n", "\r\n"))
    tmp.Activate(); hoja.Activate()
    import pythoncom, win32process
    try: pid = win32process.GetWindowThreadProcessId(xl.Hwnd)[1]
    except Exception: pid = None
    try: res["vbe_visible"] = bool(xl.VBE.MainWindow.Visible)
    except Exception: res["vbe_visible"] = True          # si no se sabe, no se esconde el editor
    parar = threading.Event(); hilo = None
    if pid:
        flujo = pythoncom.CoMarshalInterThreadInterfaceInStream(pythoncom.IID_IDispatch, xl._oleobj_)
        hilo = threading.Thread(target=_vigilar_dialogos, args=(pid, flujo, parar, res), daemon=True); hilo.start()
    eventos = xl.EnableEvents; xl.EnableEvents = False; t0 = time.time()
    try: xl.Run(f"'{tmp.Name}'!{MODULO_VIGIA}.tutorCorrer")
    except Exception as e: res["error"] = M.motivo(e, 160)
    finally:
        xl.EnableEvents = eventos; parar.set(); res["segundos"] = time.time() - t0
        if hilo: hilo.join(2)
    if res.get("restablecida") or res.get("aviso"):
        res["error"] = "Visual Basic no pudo ejecutarla" + (f": {res['aviso']}" if res.get("aviso") else " (¿un error de compilación?)")
    nombres = {n.Name.split("!")[-1].lower(): n for n in tmp.Names}
    if "tutorcortado" in nombres: res["cortada"] = True
    elif "tutorerror" in nombres and not res["error"]:
        res["error"] = str(nombres["tutorerror"].RefersTo).lstrip("=").strip('"') or "error al ejecutar"
    elif "tutorfin" not in nombres and not res["error"]: res["error"] = "la macro se detuvo sin terminar"
    for k in ("tutorcortado", "tutorerror", "tutorfin"):
        if k in nombres:
            try: nombres[k].Delete()
            except Exception: pass
    return res


def _cerrar(xl, wb):
    a = xl.DisplayAlerts; xl.DisplayAlerts = False
    try: wb.Close(False)
    except Exception: pass
    finally: xl.DisplayAlerts = a


PROPS = [("Font.Bold", "en negrita", "sin negrita"), ("Font.Italic", "en cursiva", "sin cursiva"), ("Interior.Color", "con otro relleno", None),
         ("Font.Color", "con otro color de letra", None), ("NumberFormat", "con otro formato de número", None), ("HorizontalAlignment", "con otra alineación", None)]


def _leer(r, ruta):
    for p in ruta.split("."): r = getattr(r, p)
    return r


def comparar(wa, wb_, limite=6):
    """En qué se diferencian dos hojas (la de la persona y la esperada): valores y formato básico, celda por celda
    (leyendo por rangos cuando son iguales), y cuántos gráficos, tablas y formas tienen. [(celda o None, texto)]"""
    ua, ub = wa.UsedRange, wb_.UsedRange
    f2 = min(max(ua.Row + ua.Rows.Count, ub.Row + ub.Rows.Count) - 1, 300); c2 = min(max(ua.Column + ua.Columns.Count, ub.Column + ub.Columns.Count) - 1, 60)
    zona = M.dir_((1, 1, max(f2, 1), max(c2, 1)))
    va, vb = M._como_matriz(wa.Range(zona).Value), M._como_matriz(wb_.Range(zona).Value)
    out = []
    for i, (fa, fb) in enumerate(zip(va, vb)):
        for j, (x, y) in enumerate(zip(fa, fb)):
            if not M.igual(x, y):
                out.append(((i + 1, j + 1), f"{M.col(j + 1)}{i + 1} vale {x if x not in (None, '') else '(vacía)'}: debería ser {y if y not in (None, '') else '(vacía)'}."))
    def dif(ruta, r):
        f1, c1, f2_, c2_ = r
        x, y = _leer(wa.Range(M.dir_(r)), ruta), _leer(wb_.Range(M.dir_(r)), ruta)
        if x is not None and y is not None: return [] if x == y else ([(f1, c1, y)] if (f1, c1) == (f2_, c2_) else partir(ruta, r))
        return partir(ruta, r)
    def partir(ruta, r):
        f1, c1, f2_, c2_ = r
        if (f1, c1) == (f2_, c2_): return []
        if f2_ > f1: return [d for f in range(f1, f2_ + 1) for d in dif(ruta, (f, c1, f, c2_))]
        return [d for c in range(c1, c2_ + 1) for d in dif(ruta, (f1, c, f1, c))]
    for ruta, si, no in PROPS:
        for (f, c, y) in dif(ruta, M.rect(zona))[:20]:
            txt = f"{M.col(c)}{f} debería quedar {si if (y or not no) else no}."
            if ruta == "Font.Bold": txt = f"{M.col(c)}{f} debería quedar {'en negrita' if y else 'sin negrita'}."
            if ruta == "Font.Italic": txt = f"{M.col(c)}{f} debería quedar {'en cursiva' if y else 'sin cursiva'}."
            out.append(((f, c), txt))
    for nombre, f in (("gráfico", lambda s: s.ChartObjects().Count), ("tabla", lambda s: s.ListObjects.Count),
                      ("regla de formato condicional", lambda s: s.Cells.FormatConditions.Count)):
        x, y = f(wa), f(wb_)
        if x != y: out.append((None, f"Debería haber {M._cuantas(y, nombre).replace('regla de formato condicionals', 'reglas de formato condicional')} (hay {x})."))
    return out


def revisar(hoja, turno, dibujar=True):
    """Comprobar de un ejercicio de VBA (turno con «macro»). Solo ejecuta con dibujar=True (al pulsar Comprobar); para
    el tutor (dibujar=False) dice si la macro está escrita, sin ejecutar nada."""
    ws, xl = hoja.ws, hoja.xl; wb = ws.Parent; macro = turno["macro"]
    res = {"ok": 0, "total": 1, "rango": turno.get("rango", "")}
    if not acceso(wb): return dict(res, estado="vacio", mensaje=ACCESO)
    mods = modulos(wb); donde = buscar_proc(mods, macro)
    if donde is None:
        return dict(res, estado="vacio", mensaje=turno.get("al_empezar", f"Escribe la macro «{macro}» en un módulo (Alt+F11 → Insertar → Módulo) y pulsa Comprobar."))
    if donde[1] != 1: return dict(res, estado="mal", mensaje=f"La macro «{macro}» está en «{donde[0]}» ({TIPOS.get(donde[1], '')}): ponla en un módulo normal (Insertar → Módulo).")
    if donde[2]: return dict(res, estado="mal", mensaje=f"La macro «{macro}» es Private: quítale «Private» para poder ejecutarla.")
    if not dibujar: return dict(res, estado="pendiente", mensaje=f"La macro «{macro}» está escrita (en «{donde[0]}»). Se revisa al pulsar Comprobar, ejecutándola en una copia.")
    ps = problemas("\n".join(t for _, _, t in mods), "persona")
    if ps: return dict(res, estado="mal", mensaje="Por seguridad, Comprobar no ejecuta tu macro: " + "; ".join(f"línea {n}: {m}" for n, m in ps[:3]) + ".")
    hoja._borrar("check_"); borrar_marcas(wb)
    activa, activo = xl.ActiveWorkbook, xl.ActiveSheet; temporales = []; puntos = []; dif = []
    xl.ScreenUpdating = False
    try:
        limite = turno.get("limite", 4); entradas = turno.get("entradas", [])
        r = _correr(xl, ws, [(n, t, c) for n, t, c in mods if t == 1], macro, entradas, limite); temporales.append(r["wb"])
        if r["cortada"]: return dict(res, estado="mal", puntos=[M_punto(False, f"La macro tardó más de {limite} s y la corté: ¿un bucle que no termina?")],
                                     mensaje=f"Tu macro tardó más de {limite} s y la corté. Revisa que cada bucle termine.")
        if r["error"]: return dict(res, estado="mal", puntos=[M_punto(False, f"Error al ejecutar: {r['error']}")], mensaje=f"Tu macro da un error al ejecutarse: {r['error']}")
        puntos.append(M_punto(True, f"La macro «{macro}» se ejecutó sin errores ({r['segundos']:.1f} s)."))
        if turno.get("solucion_vba"):
            s = _correr(xl, ws, [("TutorSolucion", 1, turno["solucion_vba"])], macro, entradas, limite); temporales.append(s["wb"])
            if s["error"] or s["cortada"]: puntos.append(M_punto(False, "La solución del ejercicio no se pudo ejecutar: pídele al tutor que la revise."))
            else:
                dif = comparar(r["ws"], s["ws"])
                if dif: puntos += [M_punto(False, t) for _, t in dif[:6]]
                else: puntos.append(M_punto(True, "El resultado es igual al esperado."))
        if turno.get("pide"):
            import avanzado
            tmp = M.Hoja(xl, r["ws"]); tmp.libro = hoja.libro
            puntos += avanzado.revisar_objetos(tmp, {"pide": turno["pide"]}, dibujar=False).get("puntos", [])
        mensaje = None
        if dif:
            for e in turno.get("errores", []):
                if "vba" not in e: continue
                x = _correr(xl, ws, [("TutorError", 1, e["vba"])], macro, entradas, limite); temporales.append(x["wb"])
                if not x["error"] and not x["cortada"] and not comparar(r["ws"], x["ws"]): mensaje = e["dice"]; break
    finally:
        for t in temporales: _cerrar(xl, t)
        xl.ScreenUpdating = True
        try: activa.Activate(); activo.Activate()
        except Exception: pass
    ok = sum(p["ok"] for p in puntos); total = len(puntos)
    if dibujar:
        for (celda, _) in dif[:30]:
            if celda: hoja._marcar_celdas(ws.Cells(*celda), "check_", M.COLORES["rojo"], M.FONDOS["rojo"])
        if ok == total and turno.get("rango"): hoja._marcar_celdas(ws.Range(turno["rango"]), "check_", M.COLORES["verde"], M.FONDOS["verde"])
    res.update(ok=ok, total=total, puntos=puntos)
    if ok == total: return dict(res, estado="bien", mensaje=turno.get("al_terminar", "¡Tu macro hace lo que tiene que hacer!"))
    return dict(res, estado="mal", mensaje=mensaje or next(p["texto"] for p in puntos if not p["ok"]))


def M_punto(ok, texto): return {"ok": bool(ok), "texto": texto}


def huella(hoja, turno):
    """Cambia si la persona cambia su código (el vigía la compara)."""
    try: return tuple((n, t) for n, _, t in modulos(hoja.ws.Parent)) if acceso(hoja.ws.Parent) else ()
    except Exception: return ()
