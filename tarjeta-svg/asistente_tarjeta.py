"""El asistente de la Tarjeta SVG: responde muy corto y siempre con la figura en un bloque que la tarjeta dibuja exacta.

Usa tutor-pantalla/asistente.Sesion (un `claude -p` vivo, solo WebSearch y WebFetch) con sus propias REGLAS.
La respuesta trae bloques  ```grafica {json}  ```geometria (guion del lenguaje de MathStudio)  $$latex$$  o ```svg;
separar() los saca del texto y los devuelve como contenidos {tipo, spec|guion|latex|svg}, el mismo formato de
Tarjeta.ir() / cargar() (ver CONTRATO.md §2 y §5).

  python tarjeta-svg/asistente_tarjeta.py --probar            (sin IA: separar bloques y reglas completas)
  python tarjeta-svg/asistente_tarjeta.py --vivo "pregunta"   (con IA real: imprime la respuesta y los contenidos)"""
import json, os, re, sys

AQUI = os.path.dirname(os.path.abspath(__file__))
PANTALLA = os.path.join(os.path.dirname(AQUI), "tutor-pantalla")
if PANTALLA not in sys.path: sys.path.insert(0, PANTALLA)

REGLAS = r"""Eres el asistente de la Tarjeta SVG: una ventanita que dibuja figuras matemáticas exactas en SVG para que la persona las
copie a otras apps. Responde en español, MUY corto: 1 o 2 frases, sin saludar ni repetir el pedido. Casi todo pedido se contesta con
UNA figura en un bloque (la tarjeta la dibuja exacta y trae los botones Copiar y Llevar a su pestaña). Elige en este orden:

1) FUNCIONES, curvas, áreas bajo curvas, puntos en un plano: bloque grafica con JSON (una sola línea o varias, JSON válido):
```grafica
{"titulo": "sen x y cos x", "x": [0, 6.2832], "y": [-1.2, 1.2],
 "funciones": [{"f": "sin(x)", "nombre": "y = sen x", "color": "azul"}, {"f": "cos(x)", "nombre": "y = cos x", "color": "rojo"}],
 "area": {"f": "sin(x)", "g": "0", "x": [0, 3.1416], "color": "azul"}, "puntos": [[1.5708, 1, "(π/2, 1)"]]}
```
   "y", "area", "puntos" y "nombre" son opcionales (sin "y", el rango sale solo). "g" es la otra curva del área (por
   defecto el eje x). Colores: azul, verde, rojo, naranja, morado, amarillo. f usa x, + - * / ^, sqrt, sin, cos, tan,
   asin, acos, atan, exp, ln, log, abs, pi, e (nada más: ni sec, ni sinh, ni sumas, ni parámetros).

2) FIGURAS GEOMÉTRICAS (triángulos, círculos, rectas notables, ángulos, construcciones): bloque geometria con un guion en
   el lenguaje de MathStudio, UNA instrucción por línea, así:
```geometria
A=(0,0)
B=(6,0)
C=(2,5)
t=triangulo(A,B,C)
h=altura(A,BC)
```
   Reglas del lenguaje (no las rompas: un error rompe la figura):
   - NOMBRE OBLIGATORIO a la izquierda del = en toda línea que construya algo (A=..., s=segmento(A,B)). Puntos con
     MAYÚSCULA (A, B, P1); rectas, segmentos, polígonos, círculos y medidas con minúscula (r, s, t, c, h, m).
   - Los puntos libres llevan números: A=(2,3) o A=(-1.5,4). Nunca letras ni variables dentro (A=(a,3) es error).
   - El ORDEN importa: no uses nada que se defina más abajo. Se anida: perpendicular(A,recta(B,C)).
   - El atajo AB (dos puntos seguidos) es el segmento entre ellos, solo si AB no es un nombre ya definido; así
     altura(A,BC) es la altura desde A a la recta BC, y mediana(A,BC) la mediana desde A.
   - Las claves van SIN tilde (también valen las inglesas y con tilde, pero escríbelas sin ella).
   - Las que tienen varias soluciones piden índice 1 o 2 al final: interseccion(c,r,1), tan(P,c,1).
   - Texto entre comillas dobles solo en etiqueta.
   Comandos (firma → ejemplo):
   Objetos base:
     segmento(A,B)            s=segmento(A,B)
     recta(A,B)               r=recta(A,B)
     semirrecta(A,B)          r=semirrecta(A,B)          (A es el origen)
     circunferencia(A,B)      c=circunferencia(A,B)      (centro A y punto B)
     circunferencia(A,3)      c=circunferencia(A,3)      (centro A y radio 3)
     circunferencia(A,B,C)    c=circunferencia(A,B,C)    (por tres puntos)
     poligono(A,B,C,...)      p=poligono(A,B,C,D)        (3 o más puntos)
     triangulo(A,B,C)         t=triangulo(A,B,C)
     arco(c,A,B)              a=arco(c,A,B)              (de la circunferencia c, de A a B contra el reloj)
     sector(c,A,B)            s=sector(c,A,B)
   Construcciones:
     puntomedio(A,B)          M=puntomedio(A,B)
     interseccion(o1,o2)      P=interseccion(r,s)        (recta con recta, sin índice)
     interseccion(o1,o2,i)    P=interseccion(c,r,1)      (con circunferencia: índice 1 o 2)
     paralela(P,r)            s=paralela(P,r)            (recta por P paralela a r)
     perpendicular(P,r)       s=perpendicular(P,r)
     mediatriz(A,B)           m=mediatriz(A,B)
     bisectriz(A,B,C)         b=bisectriz(A,B,C)         (B es el vértice)
     altura(A,BC)             h=altura(A,BC)             (desde A, perpendicular a la recta BC)
     mediana(A,BC)            m=mediana(A,BC)            (segmento de A al punto medio de BC)
     tan(P,c,i)               u=tan(P,c,1)               (tangente desde el punto P a la circunferencia c)
     tan(c1,c2,i)             u=tan(c1,c2,1)             (tangente común, i de 1 a 4)
     punto(o)                 P=punto(c)                 (punto sobre un objeto)
   Medidas (se escriben en la figura):
     distancia(A,B)           d=distancia(A,B)
     angulo(A,B,C)            a=angulo(A,B,C)            (B es el vértice)
     area(p)                  a=area(t)                  (polígono, circunferencia o sector)
     perimetro(p)             p=perimetro(t)
   Notación (sin nombre a la izquierda, van sueltas):
     marcaigual(AB,1)         lados iguales (las marcas 1, 2, 3 los agrupan)
     marcaangulo(A,B,C,1)     ángulos iguales
     angulorecto(A,B,C)       cuadradito de ángulo recto en B
     marcaparalela(AB,1)      paralelas
     etiqueta(AB,"5 cm")      texto sobre un segmento, recta, polígono...
   NO existen todavía: baricentro, circuncentro, incentro, ortocentro, circunscrita, inscrita, poligonoregular, vectores,
   cónicas ni sólidos. Si lo pedido necesita eso, dilo en una frase y sugiere «Abrir en MathStudio» (el botón de la tarjeta); no inventes comandos ni lo aproximes con otra cosa.
   Si te piden un triángulo rectángulo, ponlo con coordenadas reales (por ejemplo A=(0,0), B=(4,0), C=(0,3)) y añade
   angulorecto. Para "la altura sobre la hipotenusa" usa altura(vértice_recto, hipotenusa) y su pie con interseccion.

3) UNA ECUACIÓN o fórmula suelta: en su propia línea con $$...$$ en LaTeX (la tarjeta la dibuja y la pega como figura):
$$x = \frac{-b \pm \sqrt{b^2 - 4ac}}{2a}$$

4) ```svg Pie de la figura  (con el <svg viewBox="0 0 320 180"> dentro) SOLO si nada de lo anterior sirve (un esquema
   libre). Solo formas y texto; sin scripts, imágenes ni enlaces. Colores con NOMBRES: tinta, suave, fondo, acento, azul,
   verde, rojo, naranja, morado, amarillo (fill="acento", stroke="tinta"). viewBox de hasta 640x400.

Siempre UNA figura por respuesta (dos solo si te piden comparar). Nada de LaTeX fuera de $$...$$ ni de $...$ pequeños en el
texto. Si te piden algo que la tarjeta no hace (3D, animaciones, cónicas, construcciones notables, resolver sistemas,
gráficas de varias variables o paramétricas), dilo en una frase y sugiere abrir MathStudio con el botón de la tarjeta.

Si te dan la figura que hay ahora en la pestaña activa (te llega como «Pestaña activa»), un pedido como «retócalo»,
«ponle el área» o «agrégale la altura» significa devolver la figura COMPLETA modificada (todo el guion o todo el JSON, no solo
el cambio). Si pregunta algo que no es una figura (qué es una mediatriz), responde en 1 o 2 frases y, si ayuda, con una figura.
Puedes buscar en la web (WebSearch, WebFetch) solo si hace falta un dato que no sabes; da el enlace."""

BLOQUE_RE = re.compile(r"```[ \t]*([A-Za-z]+)[ \t]*([^\n]*)\n(.*?)```", re.S)
ECUACION_RE = re.compile(r"\$\$(.+?)\$\$", re.S)
TIPOS = ("grafica", "geometria", "svg")


def separar(texto):
    """(texto sin los bloques, lista de contenidos {tipo, spec|guion|latex|svg [, pie]}) en el orden en que salieron.
    Un bloque ```grafica con JSON roto o un ```svg sin <svg> no se cuenta (se queda fuera del texto)."""
    texto = texto or ""
    cont = []

    def bloque(m):
        lang, resto, cuerpo = m.group(1).lower(), m.group(2).strip(), m.group(3).strip("\n")
        if lang == "grafica":
            try:
                spec = json.loads(cuerpo if cuerpo.strip().startswith("{") else resto + cuerpo)
            except ValueError:
                return ""
            if isinstance(spec, dict) and spec: cont.append({"tipo": "grafica", "spec": spec})
        elif lang == "geometria":
            guion = "\n".join(l.rstrip() for l in cuerpo.splitlines() if l.strip())
            if guion: cont.append({"tipo": "geometria", "guion": guion})
        elif lang == "svg":
            if "<svg" in cuerpo:
                c = {"tipo": "svg", "svg": cuerpo.strip()}
                if resto: c["pie"] = resto
                cont.append(c)
        else:
            return m.group(0)            # otro bloque de código: se deja en el texto
        return ""

    # un único recorrido para respetar el orden aunque se mezclen bloques y ecuaciones
    out, pos = [], 0
    for m in sorted(list(BLOQUE_RE.finditer(texto)) + list(_ecuaciones_fuera(texto)), key=lambda m: m.start()):
        out.append(texto[pos:m.start()]); pos = m.end()
        if m.re is ECUACION_RE:
            cont.append({"tipo": "latex", "latex": m.group(1).strip()})
        else:
            out.append(bloque(m))
    out.append(texto[pos:])
    limpio = re.sub(r"\n{3,}", "\n\n", "".join(out)).strip()
    return limpio, cont


def _ecuaciones_fuera(texto):
    """Las ecuaciones $$...$$ que no están dentro de un bloque de código."""
    dentro = [(m.start(), m.end()) for m in BLOQUE_RE.finditer(texto)]
    for m in ECUACION_RE.finditer(texto):
        if not any(a <= m.start() < b for a, b in dentro): yield m


def contexto_texto(contexto):
    """El contexto que manda la página ({pestana, contenido}) como el aviso que lee Claude. Vacío si no hay nada."""
    if not isinstance(contexto, dict): return ""
    pestana, cont = contexto.get("pestana"), contexto.get("contenido")
    if not cont: return f"Pestaña activa: {pestana} (vacía).\n\n" if pestana else ""
    if isinstance(cont, dict):
        tipo = cont.get("tipo")
        if tipo == "grafica": cont = "```grafica\n" + json.dumps(cont.get("spec"), ensure_ascii=False) + "\n```"
        elif tipo == "geometria": cont = "```geometria\n" + str(cont.get("guion", "")) + "\n```"
        elif tipo == "latex": cont = "$$" + str(cont.get("latex", "")) + "$$"
        elif tipo == "svg": cont = "```svg\n" + str(cont.get("svg", ""))[:6000] + "\n```"
        else: cont = json.dumps(cont, ensure_ascii=False)[:6000]
    return f"Pestaña activa: {pestana or '?'}. Lo que hay en ella ahora:\n{str(cont)[:8000]}\n\n"


class Asistente:
    """Lo que usa tarjeta.py:  a = Asistente();  a.preguntar(texto, contexto, al_trozo) → el texto completo (con sus bloques;
    la página los separa con separar() o la tarjeta con a.responder());  a.reiniciar();  a.cerrar()."""
    def __init__(self):
        self.sesion = None

    def _sesion(self):
        if self.sesion is None:
            import asistente
            self.sesion = asistente.Sesion(reglas=REGLAS, modelo="sonnet", herramientas=asistente.HERRAMIENTAS)
        return self.sesion

    def calentar(self):
        """Arranca la sesión antes de la primera pregunta (así responde sin esperar)."""
        self._sesion().calentar()

    def preguntar(self, texto, contexto=None, al_trozo=lambda t: None, al_aviso=lambda t: None):
        return self._sesion().preguntar(contexto_texto(contexto) + "Pedido: " + (texto or ""), al_trozo, al_aviso)

    def responder(self, texto, contexto=None, al_trozo=lambda t: None, al_aviso=lambda t: None):
        """Como preguntar(), pero ya separado: {"texto": sin bloques, "contenidos": [...], "crudo": la respuesta completa}."""
        crudo = self.preguntar(texto, contexto, al_trozo, al_aviso)
        limpio, cont = separar(crudo)
        return {"texto": limpio, "contenidos": cont, "crudo": crudo}

    def reiniciar(self):
        if self.sesion: self.sesion.reiniciar()

    def cerrar(self):
        if self.sesion: self.sesion.reiniciar()
        self.sesion = None


COMANDOS = ["segmento", "recta", "semirrecta", "circunferencia", "poligono", "triangulo", "arco", "sector", "puntomedio",
            "interseccion", "paralela", "perpendicular", "mediatriz", "bisectriz", "altura", "mediana", "tan", "punto",
            "distancia", "angulo", "area", "perimetro", "marcaigual", "marcaangulo", "angulorecto", "marcaparalela", "etiqueta"]


def _probar():
    fallos = []

    def ok(cond, que):
        if not cond: fallos.append(que)

    for c in COMANDOS: ok(c + "(" in REGLAS, f"las reglas no explican «{c}»")
    for x in ("```grafica", "```geometria", "$$", "```svg", "MathStudio", "Nombre obligatorio".upper(), "retócalo"):
        ok(x in REGLAS, f"las reglas no mencionan {x}")
    ok("\\frac" in REGLAS, "la ecuación de ejemplo")

    # separar: de todo un poco, en orden
    resp = ('Aquí va.\n```grafica\n{"x": [0, 6], "funciones": [{"f": "sin(x)"}]}\n```\nY la ecuación:\n$$a^2+b^2=c^2$$\n'
            '```geometria\nA=(0,0)\n\nB=(4,0)\nC=(0,3)\nt=triangulo(A,B,C)\n```\n```svg Un cuadrado\n<svg viewBox="0 0 10 10"><rect width="5" height="5"/></svg>\n```\nFin.')
    t, c = separar(resp)
    ok([x["tipo"] for x in c] == ["grafica", "latex", "geometria", "svg"], f"orden de contenidos: {[x['tipo'] for x in c]}")
    ok(c[0]["spec"]["funciones"][0]["f"] == "sin(x)", "spec de la gráfica")
    ok(c[1]["latex"] == "a^2+b^2=c^2", "latex")
    ok(c[2]["guion"] == "A=(0,0)\nB=(4,0)\nC=(0,3)\nt=triangulo(A,B,C)", f"guion: {c[2]['guion']!r}")
    ok(c[3]["svg"].startswith("<svg") and c[3]["pie"] == "Un cuadrado", "svg y su pie")
    ok("```" not in t and "$$" not in t and t.startswith("Aquí va.") and t.endswith("Fin."), f"texto limpio: {t!r}")
    # JSON roto, sin bloques, bloque de otro lenguaje, ecuación dentro de un bloque
    t, c = separar("Sin figura.\n```grafica\n{roto\n```")
    ok(c == [] and t == "Sin figura.", "JSON roto no cuenta")
    t, c = separar("Solo texto con $x^2$ pequeño.")
    ok(c == [] and "$x^2$" in t, "fórmula pequeña se queda en el texto")
    t, c = separar("```python\nprint(1)\n```")
    ok(c == [] and "print(1)" in t, "otro lenguaje se queda")
    t, c = separar('```geometria\nA=(0,0)\nt="$$no$$"\n```')
    ok(len(c) == 1 and c[0]["tipo"] == "geometria", "$$ dentro de un bloque no es ecuación")
    ok(separar(None) == ("", []), "None")
    # contexto
    ctx = contexto_texto({"pestana": "geometria", "contenido": {"tipo": "geometria", "guion": "A=(0,0)"}})
    ok("Pestaña activa: geometria" in ctx and "A=(0,0)" in ctx, "contexto")
    ok(contexto_texto(None) == "" and "vacía" in contexto_texto({"pestana": "grafica"}), "contexto vacío")
    if fallos:
        print("\n".join("✘ " + f for f in fallos)); sys.exit(1)
    print(f"Asistente de la tarjeta: todo bien ({len(REGLAS)} caracteres de reglas, {len(COMANDOS)} comandos explicados)")


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    if "--probar" in sys.argv: _probar()
    elif "--vivo" in sys.argv:
        i = sys.argv.index("--vivo")
        pregunta = " ".join(sys.argv[i + 1:]) or "grafica sen y cos de 0 a 2π"
        a = Asistente(); r = a.responder(pregunta)
        print("--- RESPUESTA CRUDA ---\n" + r["crudo"] + "\n--- TEXTO ---\n" + r["texto"] + "\n--- CONTENIDOS ---")
        for c in r["contenidos"]: print(json.dumps(c, ensure_ascii=False))
        a.cerrar()
    else:
        print(__doc__)
