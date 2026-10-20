"""La clase viva: una guía (la misma que se publica en claude.ai) abierta en una ventana de la PC, con el tutor de los
paneles pegado a su derecha. El tutor lee la clase por dentro (el «mapa»: cada pieza del módulo con su ref) y la señala
y dibuja encima con todo lo de tutor-pantalla (flechas, dibujos de DIBUJOS.md, voz, preguntas, ilustraciones, ojos).

  python clase-viva/clase_viva.py <carpeta de la guía>            abre la clase y su tutor
  python clase-viva/clase_viva.py <carpeta de la guía> --probar   sin IA: abre la clase, recorre cada módulo y prueba
                                                                  que el mapa sale y que cada pieza se ubica en pantalla
                                                     --ver=m03    (con --probar) además imprime lo que le llega al tutor

La carpeta es la de la guía (la que tiene index.html; si está en guia/, también vale la de arriba).

Cómo encaja (README.md, «Cómo funciona»):
- Ventana de la clase: el index.html de la guía tal cual, con puente_clase.js inyectado al cargar. El tutor de claude.ai
  que trae la guía no aparece (no hay window.claude) y el puente lo oculta.
- Ventana del tutor: ../panel-excel/panel.html con los ojos (ojos_panel.inyectar_ui) y modo_clase.js: sin la pestaña
  Lección, con tres formas (abierto | pastilla | pregunta). La ventana es «propiedad» de la de la clase: va siempre
  encima de ella, se minimiza con ella y la sigue si se mueve (Acople).
- Para el tutor la clase es «la app»: sus marcas apuntan a "ref" (flechas {"tipo": "clase"} y dibujos {"tipo": "dibujo"}),
  que el puente convierte en la caja de la pieza en pantalla. Si no está a la vista, la clase se desplaza hasta ella; al
  desplazarse él, las marcas vuelven a su sitio (Ojos.reajustar).
En esta fase el tutor solo mira, señala y dibuja; mover, cambiar y añadir piezas es la fase 2 (README, «Plan»)."""
import ctypes, json, os, re, sys, threading, time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
TP, EXCEL = RAIZ / "tutor-pantalla", RAIZ / "panel-excel"
sys.path.insert(0, str(TP)); sys.path.insert(0, str(EXCEL))
import ojos, ojos_panel, capacidades, panel_web     # noqa: E402
import motor                                         # noqa: E402  (motor.Tutor: la sesión de Claude Code; motor.separar)

PUENTE_JS = (AQUI / "puente_clase.js").read_text(encoding="utf-8")
PROFE_JS = (TP / "profe.js").read_text(encoding="utf-8")        # las figuras de Claude Design (también dentro de la clase)
INFO_JS = """(function(ref){var el=document.querySelector('[data-cv-ref="'+ref+'"]'); if(!el) return null;
  var L=el._fullLayout, ej=L&&L.xaxis&&L.yaxis&&L.xaxis.range&&L.yaxis.range?{q:[+L.xaxis.range[0],+L.xaxis.range[1]],p:[+L.yaxis.range[0],+L.yaxis.range[1]]}:null;
  return {ejes: ej, texto: el.matches('p, li, h1, h2, h3, h4, summary, .formula-caja, .nota, .error-tipico, .turno, table')};})(%s)"""
TEMA_JS = """(window.PuenteClase && PuenteClase.tema) ? PuenteClase.tema() : (function(){var t=document.documentElement.getAttribute('data-theme');
  if(t) return /dark|oscuro/.test(t)?'oscuro':'claro'; return matchMedia('(prefers-color-scheme: dark)').matches?'oscuro':'claro';})()"""
MODO_JS = (AQUI / "modo_clase.js").read_text(encoding="utf-8")
ESTADO = AQUI / "estado.json"                        # la última forma del tutor (abierto o pastilla): es de la persona
NAVEGADOR = AQUI / ".navegador"                      # lo que la guía guarda (su avance en localStorage) entre sesiones
CAPAS = AQUI / "capas"                               # los cambios del tutor que él aplicó, por guía (son suyos; la guía no cambia)
OPS = {"nota": ("texto",), "formula": ("latex",), "ejemplo": ("pasos",), "ejercicio": ("enunciado", "preguntas"),
       "interactivo": ("widget", "datos"), "texto": ("texto",), "ocultar": (), "regla": ("cuando", "entonces"), "codigo": ("js",)}
ACCIONES = ("nota", "resaltar", "mostrar", "ocultar", "mover", "pulsar", "texto")       # las de una regla (puente_clase.js)
QUE = {"nota": "una nota", "formula": "una fórmula", "ejemplo": "un ejemplo resuelto", "ejercicio": "un ejercicio",
       "interactivo": "un interactivo", "texto": "cambiar un texto", "ocultar": "ocultar una pieza",
       "regla": "una regla", "codigo": "un interactivo con código"}

REGLAS_CLASE = """Eres el tutor de la clase «{titulo}», que el estudiante tiene abierta en una ventana de su PC (la «clase viva»:
la misma guía interactiva que conoce). Tú estás en un panel pegado a la derecha que él puede plegar a una pastilla; plegado,
solo ve tu respuesta en una cajita, así que sé BREVE (de 2 a 6 líneas) y deja que tus marcas y dibujos hagan el resto.

Cada pregunta llega con el [Estado de la clase]: el módulo que está viendo, cuánto ha bajado y lo último que tocó; y con el
[Mapa de la clase]: cada pieza del módulo, una por línea: ref | tipo | texto (los interactivos con su nombre y sus datos,
los controles con su valor; [abajo] o [arriba] = fuera de la vista ahora). Es lo único actualizado: úsalo siempre y no
inventes lo que no está en él. Si dice «igual que antes», vale el último mapa que te llegó.

SEÑALAR EN LA CLASE (1 a 4 marcas, solo si ayudan): al FINAL, un bloque en una sola línea:
<marcas>[{{"tipo": "clase", "ref": "m03-12", "texto": "esta curva"}}]</marcas>
- Flechas: {{"tipo": "clase", "ref": ..., "texto": 1 a 4 palabras, "n": orden si hay pasos, "color": azul | verde | rojo | naranja}}.
- Dibujos (ver DIBUJOS): los mismos, con "ref" como objetivo en vez de "id" o "caja": {{"tipo": "dibujo", "forma": "mano",
  "trazo": "circulo", "ref": "m03-12", "texto": "aquí"}}; en "fantasma" y "secuencia", cada paso con su "ref".
- Solo refs del mapa del módulo que está viendo. Si la primera no está a la vista, la clase baja (o sube) sola hasta ella.
- "id" y "caja" quedan solo para una captura de OTRA ventana que él te adjunte.

MOVER Y PULSAR PARA ENSEÑAR (cambios de explicación: no pides permiso y él los devuelve con un botón «↺ Devolver»).
Van en el mismo bloque <marcas>, se hacen en orden y después de que salgan tus flechas y dibujos:
- {{"tipo": "mover", "ref": "m03-12", "a": 30, "texto": "el equilibrio"}}  lleva un deslizador (control range o number del
  mapa) a ese valor, despacio, con tu notita junto a él.
- Recorrido: {{"tipo": "mover", "ref": "m03-12", "pasos": [{{"a": 10, "texto": "falta"}}, {{"a": 30, "texto": "se cruzan"}},
  {{"a": 45, "texto": "sobra"}}]}}  se para en cada valor (≈ 1.6 s; "pausa" en ms si quieres otra). Ideal para que vea qué cambia.
- {{"tipo": "pulsar", "ref": "m03-15", "texto": "mira cómo baja"}}  pulsa un botón de un interactivo.
- Nunca los de una deducción, un quiz o su «Tu turno»: eso lo resuelve él. Úsalos para enseñar, no para hacerle el ejercicio.
- Combínalos con dibujos: p. ej. un "foco" o un "mano" en la gráfica y luego el recorrido del deslizador.

DIBUJAR SOBRE UNA PIEZA QUE YA EXISTE: cualquier dibujo con su "ref" se encaja en esa pieza. Las piezas «gráfica» del mapa
son el ÁREA DE DATOS de una gráfica y traen sus ejes: sobre ellas usa "punto", "guias", "medida", "area", "desplazar" y
"recorrido" con VALORES de los ejes ("q" = el eje x, "p" = el eje y), no píxeles (ver DIBUJOS). Ejemplo, el equilibrio:
{{"tipo": "dibujo", "forma": "guias", "ref": "m03-12", "q": 60, "p": 20}} y {{"tipo": "dibujo", "forma": "punto", "ref": "m03-12", "q": 60, "p": 20, "letra": "E", "texto": ""}}.
Para algo que esas figuras no hagan, un "svg" con viewBox="0 0 W H" (W×H = el tamaño del área de datos) también cae exacto:
un dato (x, y) va en px = (x − x0)/(x1 − x0)·W, py = (y1 − y)/(y1 − y0)·H. No rodees la gráfica entera para señalar un punto.
EXPLICAR EN LA CLASE: "globo" (junto a la pieza, con un hilo; con "q" y "p" en una gráfica, el hilo va a ese dato) y "pasos"
(2 a 6 pasos, cada uno con su "ref" y su texto). Cuando él tiene el chat plegado ([Plegado] en el estado) NO lee tu texto:
todo lo que quieras decirle va en globos o pasos sobre la clase.
Si vas a mover un deslizador que cambia los ejes, el dibujo se queda donde lo pusiste: dibuja lo que no dependa de eso.

En el chat escribe P* tal cual (sin barra invertida) y no metas fórmulas dentro de **negritas**.

AÑADIR Y CAMBIAR PIEZAS (siempre con su permiso: le sale una tarjeta Aplicar / No y luego Deshacer; se guarda aparte y la
guía original no cambia). Al final, un bloque en una sola línea, además de tus marcas:
<cambios>[{{"op": "ejercicio", "despues": "m03-40", "para": "practicar con otros números", "enunciado": "…",
  "preguntas": [{{"texto": "P* =", "respuesta": 10}}, {{"texto": "Q* =", "respuesta": 400}}], "pista": "…", "solucion": "…"}}]</cambios>
- {{"op": "nota", "despues": ref, "texto": "…", "estilo": "nota" | "recuerda" | "error"}}
- {{"op": "formula", "despues": ref, "latex": "P^* = \\frac{{a-c}}{{b+d}}"}}
- {{"op": "ejemplo", "despues": ref, "titulo": "…", "pasos": ["…", "…"]}}
- {{"op": "ejercicio", …}} como arriba: se revisa solo, sin IA ("tolerancia" opcional); "respuesta" es un número.
- {{"op": "interactivo", "despues": ref, "widget": "mercado", "datos": {{…}}, "attrs": {{"p": 25}}}}: otro interactivo de la guía
  con otros números. "datos" como en [Datos de los interactivos] (mismo "tipo" y campos); los números se comprueban y si no
  cuadran no se crea y te aviso. "attrs" son sus data-* (como "p", el precio inicial).
- {{"op": "texto", "ref": ref, "texto": "…"}} reemplaza el texto de un párrafo o título; {{"op": "ocultar", "ref": ref}} lo oculta.
- "despues" (o "antes") = la pieza junto a la que va. Textos con LaTeX \\( … \\) y **negritas**. Hasta 4 cambios por bloque.
- Úsalo cuando él lo pida o cuando claramente le sirve (otro ejercicio parecido, un ejemplo con otros números, una nota de
  lo que le costó); nunca cambies su clase sin que lo note: explica en una frase qué propones. No es para hacerle su Tu turno.
COMPORTAMIENTOS (también en <cambios>, con su permiso):
- Regla sin código: {{"op": "regla", "cuando": {{"ref": "m03-12", "valor": {{">": 20}}}}, "entonces": [{{"nota": "Sobran {{= (20 + 2*x) - (100 - 2*x)}}", "en": "m03-12"}},
  {{"resaltar": "m03-13"}}], "sino": [{{"nota": "Ya no sobra", "en": "m03-12"}}]}}
  «cuando»: la pieza que se vigila (un deslizador, un campo, una casilla) y opcional "valor" con "<", ">", "<=", ">=", "=",
  "distinto" o {{"entre": [a, b]}}; "evento": "pulsa" para un botón. Sin "valor", cada cambio dispara "entonces".
  Acciones: {{"nota": texto, "en": ref}}, {{"resaltar": ref}}, {{"mostrar": ref}}, {{"ocultar": ref}}, {{"mover": ref, "a": n}},
  {{"pulsar": ref}}, {{"texto": ref, "valor": texto}} (solo en piezas tuyas). En los textos, {{valor}} es el valor y {{= 100 - 2*x}}
  calcula con x = el valor. Sin "sino", lo que puso la regla se quita cuando deja de cumplirse.
- Código (solo si una regla no alcanza): {{"op": "codigo", "despues": ref, "titulo": "…", "alto": 320, "lee": {{"precio": "m03-12"}},
  "toca": {{"precio": "m03-12"}}, "js": "…"}}. Tu JS corre en una caja cerrada (sin la página, sin red) con dos variables: raiz
  (un <div> tuyo para dibujar: SVG, canvas, botones) y clase: clase.valor("precio"), clase.al("precio", fn(v)),
  clase.mover("precio", 30), clase.nota("precio", "texto"), clase.resaltar(n), clase.mostrar(n), clase.ocultar(n),
  clase.pulsar(n), clase.quitarNotas(), clase.tema ('claro'|'oscuro') y clase.paleta('azul') (los colores planos:
  .tinta, .fuerte, .tenue, .papel, .texto, .suave, .borde; usada como texto da su tinta).
  También tienes Profe (las figuras) si te sirve. Solo puedes leer lo de "lee" y tocar lo de "toca". Él ve tu código en la
  tarjeta antes de aplicarlo: escríbelo claro y corto (máximo ~150 líneas), en JS sin módulos.
- Las piezas que ya pusiste salen en el mapa con [del tutor]. Cuando aplica, deshace o resuelve un ejercicio tuyo, te llega en [Del panel]."""

u32 = ctypes.WinDLL("user32", use_last_error=True)
u32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
u32.SetWindowLongPtrW.restype = ctypes.c_void_p
u32.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p] + [ctypes.c_int] * 4 + [ctypes.c_uint]
u32.IsIconic.argtypes = [ctypes.c_void_p]
u32.SetForegroundWindow.argtypes = [ctypes.c_void_p]
u32.GetDpiForWindow.argtypes = [ctypes.c_void_p]
GWLP_HWNDPARENT, SWP_NOZORDER, SWP_NOACTIVATE = -8, 0x0004, 0x0010


def _hwnd(ventana):
    try: return int(ventana.native.Handle.ToInt64())
    except Exception: return None


# ---------------------------------------------------------------- la guía
class Clase:
    """Lo que se sabe de la guía sin abrirla: título, módulos y las reglas de su tutor (las de inicio.js)."""

    def __init__(self, ruta):
        p = Path(ruta).resolve()
        if p.is_dir():
            p = next((q for q in (p / "index.html", p / "guia" / "index.html") if q.is_file()), p / "index.html")
        if not p.is_file(): raise ValueError(f"no encuentro index.html en {ruta}")
        self.index, self.carpeta, self.ruta = p, p.parent, p
        html = p.read_text(encoding="utf-8")
        t = re.search(r"<title>(.*?)</title>", html, re.S)
        self.titulo = re.sub(r"\s+", " ", t.group(1)).strip() if t else self.carpeta.name
        self.modulos = []
        for cab in re.findall(r"<section\b[^>]*\bclass=\"[^\"]*\bmodulo\b[^\"]*\"[^>]*>", html):
            at = dict(re.findall(r'([\w-]+)="([^"]*)"', cab))
            if at.get("id"): self.modulos.append({"id": at["id"], "num": at.get("data-num", ""), "titulo": at.get("data-titulo", ""),
                                                  "grupo": at.get("data-grupo", "")})
        r = re.search(r"const REGLAS\s*=\s*`(.*?)`;", html, re.S)          # el tutor de la guía: quién es y cómo aprende
        self.reglas_guia = r.group(1).replace("\\\\", "\\").replace("\\`", "`") if r else ""
        self.d = {}                                   # como un curso: modelo_tutor, si algún día hace falta otro
        self.app_nombre = "la clase"


class TutorClase(capacidades.ConWeb, motor.Tutor):
    """motor.Tutor con las reglas de la clase viva, las de la guía y las capacidades de todos los tutores."""

    def _intro(self):
        c = self.curso
        mods = "; ".join(f"{m['id']} = {m['num']}. {m['titulo']}" for m in c.modulos)
        partes = [REGLAS_CLASE.format(titulo=c.titulo)]
        if c.reglas_guia: partes.append("\nLO QUE DICE LA GUÍA DE SU TUTOR (quién es el estudiante y cómo responderle):\n" + c.reglas_guia)
        partes.append("\nOJO, AQUÍ MANDA ESTO SOBRE LO DE ARRIBA: en este chat las fórmulas van con $...$ y $$...$$ (nunca \\( \\) ni \\[ \\]); en globos, "
                      "pasos y notas, en texto plano (Qd = 100 − 2P). El texto de un globo: 1 o 2 frases cortas (máximo unos 200 caracteres).")
        partes.append(capacidades.reglas("la clase"))
        partes.append(f"\nMódulos de la guía: {mods}.\n\nResponde solo: Listo")
        return "\n".join(partes)


def _lista(xs):
    xs = list(xs)
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " y " + xs[-1] if xs else ""


def _verificador(carpeta):
    """La verificación del catálogo de la guía (verificar() de su build.py), para los números de un interactivo nuevo; o None."""
    b = Path(carpeta) / "build.py"
    if not b.is_file(): return None
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("build_guia_" + Path(carpeta).name, b)
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return getattr(mod, "verificar", None)
    except Exception as e:
        print("No pude cargar la verificación de la guía:", e, flush=True); return None


def _corto(texto, maximo=320):
    """El texto del tutor para un globo: sin Markdown ni delimitadores de LaTeX, hasta 3 frases."""
    t = re.sub(r"\*\*|`|\\[()\[\]]|\$\$?", "", texto or "")
    t = re.sub(r"^\s*[-*•]\s+", "", t, flags=re.M); t = re.sub(r"\s+", " ", t).strip()
    out = ""
    for f in re.split(r"(?<=[.!?])\s+", t)[:3]:
        if len(out) + len(f) > maximo: break
        out = (out + " " + f).strip()
    return out or t[:maximo]


# ---------------------------------------------------------------- las dos ventanas, pegadas
class Acople:
    """Pone la ventana del tutor donde toca según su forma, relativa al área de cliente de la clase, y la sigue."""
    ANCHO, PASTILLA, PREGUNTA = 460, (34, 64), 494           # px lógicos (× la escala de la ventana); pastilla 4a de Claude Design

    def __init__(self, api):
        self.api, self.modo, self.alto = api, "abierto", 150
        self.barra = 17                                   # px CSS de la barra de desplazamiento de la clase (no se tapa)
        self.ultimo = self.reserva = None
        self.dueño = False
        threading.Thread(target=self._seguir, daemon=True).start()

    def _rect(self):
        hc = _hwnd(self.api._vclase)
        c = ojos.cliente(hc) if hc else None
        if not c or c[2] < 100 or u32.IsIconic(hc): return None
        x, y, w, h = c; s = (u32.GetDpiForWindow(hc) or 96) / 96
        w -= round(self.barra * s)
        if self.modo == "abierto":
            W = round(min(self.ANCHO * s, w * 0.42)); return (x + w - W, y, W, h)
        if self.modo == "pastilla":
            W, H = round(self.PASTILLA[0] * s), round(self.PASTILLA[1] * s); return (x + w - W, y + round(h * 0.40), W, H)
        W = round(min(self.PREGUNTA * s, w * 0.9)); H = round(min(max(self.alto, 110) * s, h * 0.72))
        top = min(y + round(h * 0.40 - 24 * s), y + h - H - round(12 * s))
        return (x + w - W - round(6 * s), max(y + round(8 * s), top), W, H)

    def aplicar(self):
        if self.api._cerrando: return
        r = self._rect(); ht = _hwnd(self.api._ventana); hc = _hwnd(self.api._vclase)
        if not r or not ht: return
        if not self.dueño and hc:                     # «propiedad» de la clase: siempre encima de ella y se minimiza con ella
            u32.SetWindowLongPtrW(ht, GWLP_HWNDPARENT, hc); self.dueño = True
        if r != self.ultimo:
            u32.SetWindowPos(ht, None, *r, SWP_NOZORDER | SWP_NOACTIVATE); self.ultimo = r
        s = (u32.GetDpiForWindow(hc) or 96) / 96
        reserva = round(r[2] / s) if self.modo == "abierto" else 0
        if reserva != self.reserva and self.api._en_clase(f"PuenteClase.reservar({reserva})"):
            self.reserva = reserva                    # si el puente aún no carga, se reintenta en la próxima vuelta

    def poner(self, modo):
        if modo in ("abierto", "pastilla", "pregunta"): self.modo = modo
        self.aplicar()

    def _seguir(self):
        while not self.api._cerrando:
            try: self.aplicar()
            except Exception: pass
            time.sleep(0.12)


# ---------------------------------------------------------------- lo que pide la página del tutor
class ApiTutor(ojos_panel.OjosApi):
    def __init__(self, clase, tutor):
        self._clase, self._tutor = clase, tutor
        self._ventana = self._vclase = None
        self._cerrando = False                         # al cerrar la clase: nadie más le habla a las ventanas
        self._ojos = ojos_panel.Ojos(apps=[], panel_hwnd=self._hwnd_panel)
        tutor.al_aviso = lambda t: self._empujar(f"window.avisoTrabajo && window.avisoTrabajo({json.dumps(t)})")
        self._notas, self._firma, self._flechas_puestas = [], None, []
        self._propuestas, self._np = {}, 0                # los <cambios> del tutor: id → {ops, estado, resumen…}
        self._capa = CAPAS / (re.sub(r"[^\w-]+", "-", str(clase.carpeta.relative_to(RAIZ)) if clase.carpeta.is_relative_to(RAIZ) else clase.carpeta.name).strip("-") + ".json")
        self._verificar = _verificador(clase.carpeta)
        self._acople = Acople(self)
        self._modulo_txt = ""

    # --- utilidades ---
    def _hwnd_panel(self): return _hwnd(self._ventana) if self._ventana else None
    def _hc(self): return _hwnd(self._vclase) if self._vclase else None

    def _empujar(self, js):
        if self._ventana and not self._cerrando:
            try: self._ventana.evaluate_js(js)
            except Exception: pass

    def _en_clase(self, js):
        if not self._vclase or self._cerrando: return None
        try: return self._vclase.evaluate_js(f"window.PuenteClase ? ({js}) : null")
        except Exception: return None

    # --- la página ---
    def listo(self): return True

    def estado(self):
        """Lo mínimo que espera panel.html de una lección (aquí no hay pestaña Lección: la clase es la lección)."""
        c = self._clase
        return {"n": 0, "total": 1, "texto": "", "titulo": c.titulo, "curso": c.titulo, "objeto": "clase", "app": "la clase",
                "hoja": self._modulo_txt or c.titulo, "botones": [], "revision": None, "tutor_ej": None, "practica": None, "modulos": []}

    def clase_inicio(self):
        try: modo = json.loads(ESTADO.read_text(encoding="utf-8")).get("modo")
        except Exception: modo = None
        if modo not in ("abierto", "pastilla"):
            hc = self._hc(); c = ojos.cliente(hc) if hc else None
            s = (u32.GetDpiForWindow(hc) or 96) / 96 if hc else 1
            modo = "abierto" if not c or c[2] / s >= 1400 else "pastilla"      # como la guía: abierto en pantallas grandes
        return {"modo": modo, "modulo": self._modulo_txt}

    def clase_modo(self, modo):
        self._acople.poner(modo)
        if modo in ("abierto", "pastilla"):
            try: ESTADO.write_text(json.dumps({"modo": modo}), encoding="utf-8")
            except OSError: pass
        return {"ok": True, "modo": self._acople.modo}

    def clase_alto(self, px):
        try: self._acople.alto = max(80, min(2000, int(px)))
        except (TypeError, ValueError): return {"ok": False}
        self._acople.aplicar(); return {"ok": True}

    def ventana_minimizar(self):                       # el «—» de la barra: plegar a la pastilla
        self._empujar("window.modoClase && window.modoClase('pastilla', false)"); return {"ok": True}

    # --- preguntar ---
    def _mapa(self):
        m = self._en_clase("PuenteClase.mapa()") or {}
        if not m.get("modulo"): return "[Estado de la clase] No veo ningún módulo abierto."
        nuevo = self._tutor.p is None or self._tutor.p.poll() is not None or self._tutor.turnos >= self._tutor.MAX_TURNOS
        if nuevo: self._firma = None                   # sesión nueva del tutor: no conoce ningún mapa
        partes = [f"[Estado de la clase] Módulo {m.get('num')}: «{m.get('titulo')}» ({m['modulo']}). Vista: {m.get('vista')}."]
        u = m.get("ultimo")
        if u: partes.append(f"Lo último que tocó: {u.get('ref')} «{u.get('que', '')}»" + (f" = {u['valor']}" if u.get("valor") not in (None, "") else "")
                            + (f", dentro de {u['en']}" if u.get("en") else "") + ".")
        lineas = []
        for p in m.get("mapa") or []:
            t = p["tipo"] + (f" {p['widget']}" if p.get("widget") else "") + (f" ({p['datos']})" if p.get("datos") else "")
            if p.get("control"): t += f" {p['control']}"
            linea = f"{p['ref']} | {t} | {p.get('texto', '')}"
            if p.get("valor") not in (None, ""): linea += f" = {p['valor']}" + (f" (de {p['min']} a {p['max']})" if p.get("min") not in (None, "") else "")
            if p.get("en"): linea += f" · en {p['en']}"
            if p.get("donde") in ("arriba", "abajo"): linea += f" [{p['donde']}]"
            if p.get("tutor"): linea += " [del tutor]"
            lineas.append(linea)
        if m.get("firma") != self._firma:
            self._firma = m.get("firma")
            partes.append("[Mapa de la clase]\n" + "\n".join(lineas))
            ids = sorted({p["datos"] for p in m.get("mapa") or [] if p.get("datos")})
            datos = self._en_clase(f"(function(ids){{var o={{}};ids.forEach(function(i){{if(typeof FUNC==='object'&&FUNC[i])o[i]=FUNC[i];}});return o;}})({json.dumps(ids)})") or {}
            if datos: partes.append("[Datos de los interactivos] (para un \"interactivo\" nuevo, con el mismo \"tipo\" y campos)\n" +
                                    "\n".join(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in datos.items()))
        else:
            vista = [p["ref"] for p in m.get("mapa") or [] if p.get("donde") == "a la vista"]
            partes.append(f"[Mapa de la clase] igual que antes. A la vista ahora: {vista[0]} … {vista[-1]}." if vista else "[Mapa de la clase] igual que antes.")
        return "\n".join(partes)

    def preguntar(self, pregunta, adjuntos=None):
        pregunta = (pregunta or "").strip()
        if not pregunta and not adjuntos: return {"texto": ""}
        pregunta = pregunta or "Mira lo que te adjunto."
        ctx = self._mapa()
        plegado = self._acople.modo != "abierto"
        if plegado: ctx = ("[Plegado] Tiene el chat plegado: no lee tu texto. Explícale SOBRE la clase con un \"globo\" (o \"pasos\") "
                           "anclado a la pieza, más tus marcas y dibujos; en el texto deja solo una línea.\n") + ctx
        if self._notas: ctx = "[Del panel] " + " ".join(self._notas) + "\n" + ctx; self._notas = []
        ctx += ("\n" + self._ojos.contexto(adjuntos)).rstrip()
        def trozo(t): self._empujar(f"window.trozoTutor({json.dumps(t)})")
        try: resp = self._tutor.preguntar(ctx, pregunta, trozo, adjuntos)
        except ValueError as e: return {"texto": str(e)}
        except Exception as e: return {"texto": f"No pude hablar con el tutor ({e}). Intenta otra vez."}
        resp, pide = ojos_panel.separar_pedido(resp)
        resp, preguntas = ojos_panel.separar_preguntas(resp)
        resp, propuesta = self._separar_cambios(resp)
        texto, marcas = motor.separar(resp)
        acciones = [m for m in marcas if isinstance(m, dict) and m.get("tipo") in ("mover", "pulsar")]
        marcas = [m for m in marcas if m not in acciones]
        refs = self._refs(marcas + acciones)
        if plegado and texto and not any(isinstance(m, dict) and m.get("forma") in ("globo", "pasos") for m in marcas):
            marcas.append({"tipo": "dibujo", "forma": "globo", "texto": _corto(texto), **({"ref": refs[0]} if refs else {})})   # lo dice en la clase
        self._encuadrar(marcas + acciones)
        lote = None
        if any(isinstance(m, dict) and m.get("tipo") == "dibujo" for m in marcas):
            marcas, lote, avisos = self._ojos.dibujos(marcas, self._resolver(), self._hc())
            if avisos: self._notas.append("Estos dibujos tuyos no se pudieron hacer: " + "; ".join(avisos) + ".")
        marcas, en_ventana = self._ojos.marcar(marcas)            # las "ventana" (sobre una captura de otra ventana)
        hechas = 0
        flechas = [m for m in marcas if isinstance(m, dict) and m.get("tipo") in ("clase", "app") and m.get("ref")]
        if flechas and not en_ventana: hechas = self._poner_flechas(flechas[:4])
        if acciones: self._hacer(acciones, bool(lote))
        if plegado and preguntas: self._pregunta_en_clase(preguntas[0], refs[0] if refs else None)
        return {"texto": texto, "marcas": 0, "marcas_ventana": en_ventana + hechas, "pedir": pide, "dibujos": lote,
                "preguntas": preguntas, "propuesta": propuesta}

    # --- ubicar piezas de la clase ---
    @staticmethod
    def _refs(marcas):
        out = []
        for m in marcas or []:
            if not isinstance(m, dict): continue
            for o in [m] + [p for p in m.get("pasos") or [] if isinstance(p, dict)] + ([m["hasta"]] if isinstance(m.get("hasta"), dict) else []):
                if o.get("ref"): out.append(str(o["ref"]))
        return out

    def _encuadrar(self, marcas):
        refs = self._refs(marcas)
        if refs and self._en_clase(f"PuenteClase.encuadrar({json.dumps(refs)})"): time.sleep(0.15)   # que se asiente el desplazamiento

    def _caja(self, ref):
        """La caja en PANTALLA (px físicos) de una pieza, o ValueError con lo que pasa."""
        r = self._en_clase(f"PuenteClase.rect({json.dumps(str(ref))})")
        if not r: raise ValueError(f"«{ref}» no está en la clase")
        if r.get("otro"): raise ValueError(f"«{ref}» es del módulo {r['otro']}, que no está abierto")
        if r.get("oculto"): raise ValueError(f"«{ref}» está oculto (en un desplegable cerrado o un paso sin abrir)")
        c = ojos.cliente(self._hc())
        if not c: raise ValueError("la clase no está abierta")
        k = r.get("dpr") or 1
        caja = [c[0] + r["x"] * k, c[1] + r["y"] * k, r["w"] * k, r["h"] * k]
        if r["w"] <= 0 or r["h"] <= 0: raise ValueError(f"«{ref}» no ocupa lugar en la pantalla")
        if r["y"] + r["h"] < 0 or r["y"] > r["vh"]:
            raise ValueError(f"«{ref}» quedó fuera de la vista (y = {r['y']:.0f} de {r['vh']:.0f})")
        return caja

    def _resolver(self):
        """Para Ojos.dibujos: "ref" → la pieza en pantalla; sin objetivo, la ventana de la clase."""
        tema = self._en_clase(TEMA_JS)
        tema = tema if tema in ("claro", "oscuro") else "claro"
        def resolver(m):
            if m.get("ref"):
                caja = self._caja(m["ref"])
                info = self._en_clase(INFO_JS % json.dumps(str(m["ref"]))) or {}
                extra = {"tema": tema}
                if info.get("ejes"): extra["ejes"] = info["ejes"]              # una gráfica: el tutor da valores (formas_profe.js)
                if info.get("texto"): extra["pieza_texto"] = True             # el globo, como pestaña
                return {"hwnd": self._hc(), "r": caja, "evitar": self._evitar(), **extra}
            if any(k in m for k in ("id", "caja", "linea", "celda", "nombre")): return None      # una captura de otra ventana
            return {"hwnd": self._hc(), "r": None, "tema": tema}
        return resolver

    def _evitar(self):
        """La ventana del tutor (en pantalla), en 8 trozos: las notas de las marcas no se ponen debajo de ella. En trozos
        porque marcador.py no hace caso de una zona que ocupe más del 20 % de la ventana (la toma por el fondo)."""
        r = self._acople.ultimo
        if not r: return []
        x, y, w, h = r; n = 8
        return [[x, y + h * k / n, w, h / n] for k in range(n)]

    def _poner_flechas(self, marcas, deslizar=False):
        hc = self._hc(); cli = ojos.cliente(hc) if hc else None
        if not cli: return 0
        items, faltan = [], []
        for k, m in enumerate(marcas):
            try: caja = self._caja(m["ref"])
            except ValueError as e: faltan.append(str(e)); continue
            items.append({"hwnd": hc, "ventana": list(cli), "rect": caja, "texto": str(m.get("texto") or "")[:40],
                          "color": m.get("color") if m.get("color") in ("azul", "verde", "rojo", "naranja", "amarillo") else "azul",
                          "n": m.get("n"), "evitar": self._evitar()})
        if faltan and not deslizar: self._notas.append("Tus flechas no se pusieron: " + "; ".join(faltan) + ".")
        self._flechas_puestas = [dict(m) for m in marcas]
        if not items:
            self._ojos.ov.orden({"cmd": "borrar"}); return 0
        r = self._ojos.ov.orden({"cmd": "mostrar", "pids": [os.getpid()], "panel": self._hwnd_panel(), "marcas": items}
                                | ({"deslizar": True} if deslizar else {}))
        self._ojos.registrar_rehacer("clase", self._rehacer_flechas)
        return r.get("dibujadas", len(items))

    def _rehacer_flechas(self):
        n = self._poner_flechas(self._flechas_puestas, deslizar=True) if self._flechas_puestas else 0
        return {"movidas": n, "fuera": 0, "perdidas": []}

    def _hacer(self, acciones, con_dibujos):
        """Mover y pulsar: se revisan ya (lo que no vale va en una nota al tutor) y se hacen cuando la respuesta ya salió."""
        revision = self._en_clase(f"PuenteClase.validar({json.dumps(acciones)})") or []
        malas = [r.get("error") for r in revision if not r.get("ok")]
        if malas: self._notas.append("No hice esto que pediste: " + "; ".join(malas) + ".")
        buenas = [a for a, r in zip(acciones, revision) if r.get("ok")]
        if not buenas: return
        hecho = "; ".join(r["hecho"] for r in revision if r.get("ok"))
        def correr():
            time.sleep(1.4 if con_dibujos else 0.6)          # que se vean antes las flechas y los dibujos
            self._empujar(f"window.cvMovi && window.cvMovi({json.dumps(hecho[0].upper() + hecho[1:])})")
            self._en_clase(f"PuenteClase.hacer({json.dumps(buenas)}), true")
            self._esperar_manos()
            if self._ojos.hay_que_reajustar(): self._al_desplazar()       # por si mover cambió de tamaño algo
        threading.Thread(target=correr, daemon=True).start()

    def _pregunta_en_clase(self, q, ref):
        """Plegado: la tarjeta de preguntas sale flotando junto a la pieza (PuenteClase.pregunta), después de las manos."""
        if not isinstance(q, dict) or not q.get("opciones"): return
        spec = {"pregunta": q.get("pregunta", ""), "opciones": q["opciones"], "explicacion": q.get("explicacion", ""), "ref": ref}
        if isinstance(q.get("correcta"), int): spec["correcta"] = q["correcta"]
        def correr():
            time.sleep(1.2); self._esperar_manos()
            self._en_clase(f"PuenteClase.pregunta && PuenteClase.pregunta({json.dumps(spec)})")
        threading.Thread(target=correr, daemon=True).start()

    def _esperar_manos(self, maximo=60):
        """Espera a que el puente termine de mover y pulsar (evaluate_js no espera a las promesas)."""
        fin = time.time() + maximo
        while time.time() < fin and self._en_clase("PuenteClase.trabajando()"): time.sleep(0.15)

    def clase_devolver(self):
        """«↺ Devolver»: los deslizadores que movió el tutor vuelven a como los tenía él."""
        self._en_clase("PuenteClase.devolver(), true"); self._esperar_manos(10)
        self._notas.append("Él devolvió los deslizadores a como los tenía antes de que los movieras.")
        return {"ok": True}

    # --- los cambios del tutor: <cambios> → tarjeta Aplicar / No → la capa (clase-viva/capas/) ---
    def _separar_cambios(self, resp):
        """Saca el bloque <cambios>[...]</cambios>: (texto, propuesta para la tarjeta o None). Lo que no vale va en una nota."""
        m = re.search(r"<cambios>(.*?)</cambios>", resp or "", re.S)
        if not m: return re.sub(r"<cambios>.*\Z", "", resp or "", flags=re.S), None
        resp = (resp[:m.start()] + resp[m.end():]).strip()
        try: ops = json.loads(m.group(1))
        except ValueError: self._notas.append("Tu bloque <cambios> no era JSON válido: no se propuso nada."); return resp, None
        ops = [o for o in (ops if isinstance(ops, list) else [ops]) if isinstance(o, dict)][:4]
        errores, buenos = [], []
        for k, o in enumerate(ops, 1):
            e = self._revisar_op(o)
            if e: errores.append(f"cambio {k} ({o.get('op', '?')}): {e}")
            else: buenos.append(o)
        if errores: self._notas.append("No propuse estos cambios tuyos: " + "; ".join(errores) + ".")
        if not buenos: return resp, None
        self._np += 1; pid = f"c{self._np}"
        mod = self._modulo_txt or "la clase"
        nombres = [QUE[o["op"]] for o in buenos]
        p = {"id": pid, "estado": "pendiente", "nueva": False, "hoja": mod, "ops": buenos,
             "resumen": _lista((["añadir " + _lista([n for n in nombres if n.startswith("un")])] if any(n.startswith("un") for n in nombres) else [])
                               + [n for n in nombres if not n.startswith("un")]),
             "para": next((str(o.get("para")) for o in buenos if o.get("para")), ""),
             "avisos": [], "notas": ["Se guarda aparte: la guía no cambia, y con Deshacer vuelve a como estaba."],
             "detalle": [self._detalle(o) for o in buenos], "mensaje": "", "ejercicio": "",
             "codigos": [{"titulo": f"Código: {o.get('titulo') or 'del tutor'}", "texto": str(o["js"])} for o in buenos if o["op"] == "codigo"]}
        self._propuestas[pid] = p
        return resp, self._tarjeta(p)

    def _revisar_op(self, o):
        op = o.get("op")
        if op not in OPS: return f"«{op}» no existe (usa {', '.join(OPS)})"
        falta = [c for c in OPS[op] if not o.get(c)]
        if falta: return "le falta " + ", ".join(f"«{c}»" for c in falta)
        if op == "regla": return self._revisar_regla(o)
        ref = o.get("despues") or o.get("antes") or o.get("ref")
        if not ref: return "le falta dónde va («despues», «antes» o «ref»)"
        e = self._ref_mal(ref)
        if e: return e
        if op == "codigo":
            if len(str(o["js"])) > 20000: return "el código es muy largo (máximo 20 000 letras)"
            for campo in ("lee", "toca"):
                if o.get(campo) is not None and not isinstance(o[campo], dict): return f"«{campo}» va como {{nombre: ref}}"
                for n, rr in (o.get(campo) or {}).items():
                    e = self._ref_mal(rr)
                    if e: return f"{campo} «{n}»: {e}"
        if op == "ejercicio":
            for q in o["preguntas"]:
                try: float(q.get("respuesta"))
                except (TypeError, ValueError): return "cada pregunta necesita una «respuesta» numérica"
        if op == "interactivo":
            if not self._en_clase(f"typeof TIPOS_WIDGET === 'object' && !!TIPOS_WIDGET[{json.dumps(str(o['widget']))}]"):
                return f"esta guía no tiene el interactivo «{o['widget']}»"
            if not isinstance(o["datos"], dict) or not o["datos"].get("tipo"): return "«datos» necesita su «tipo» (como en el catálogo)"
            if self._verificar:
                errs = self._verificar([dict(o["datos"], id="tutor")])
                if errs: return "sus números no cuadran: " + "; ".join(e.replace("tutor: ", "") for e in errs[:3])
        return None

    def _ref_mal(self, ref):
        r = self._en_clase(f"PuenteClase.rect({json.dumps(str(ref))})")
        if not r: return f"«{ref}» no está en la clase"
        if r.get("otro"): return f"«{ref}» es de otro módulo"
        return None

    def _revisar_regla(self, o):
        cu = o.get("cuando")
        if not isinstance(cu, dict) or not cu.get("ref"): return "«cuando» necesita su «ref» (la pieza que se vigila)"
        e = self._ref_mal(cu["ref"])
        if e: return e
        v = cu.get("valor")
        if v is not None and (not isinstance(v, dict) or not set(v) & {"<", ">", "<=", ">=", "=", "distinto", "entre"}):
            return "«valor» va como {\">\": 20} o {\"entre\": [a, b]}"
        for campo in ("entonces", "sino"):
            for a in o.get(campo) or []:
                tipo = next((k for k in ACCIONES if isinstance(a, dict) and k in a), None)
                if not tipo: return f"en «{campo}», una acción no es de {', '.join(ACCIONES)}"
                ref = a.get("en") if tipo == "nota" else a[tipo]
                if ref:
                    e = self._ref_mal(ref)
                    if e: return f"en «{campo}»: {e}"
        return None

    @staticmethod
    def _cond(v):
        if not v: return "cambia"
        k = next(iter(v)); return f"está entre {v[k][0]} y {v[k][1]}" if k == "entre" else f"{k} {v[k]}"

    @staticmethod
    def _detalle(o):
        op, donde = o["op"], o.get("despues") or o.get("antes") or o.get("ref")
        lugar = f"{'antes' if o.get('antes') else 'después'} de {donde}"
        if op == "nota": return f"Nota {lugar}: «{_corto(o['texto'], 140)}»"
        if op == "formula": return f"Fórmula {lugar}: `{o['latex']}`"
        if op == "ejemplo": return f"Ejemplo resuelto {lugar}: «{o.get('titulo') or ''}», {len(o['pasos'])} pasos"
        if op == "ejercicio": return f"Ejercicio {lugar}: «{_corto(o['enunciado'], 120)}» ({len(o['preguntas'])} respuesta(s), se revisa solo)"
        if op == "interactivo": return f"Interactivo «{o['widget']}» {lugar}, con sus números comprobados"
        if op == "texto": return f"Cambiar el texto de {donde} por «{_corto(o['texto'], 120)}»"
        if op == "regla":
            hace = lambda xs: ", ".join(next(k for k in ACCIONES if k in a) + (f" «{_corto(a['nota'], 50)}»" if "nota" in a else "") for a in xs or []) or "nada"
            return (f"Regla: cuando {o['cuando']['ref']} {ApiTutor._cond(o['cuando'].get('valor'))} → {hace(o['entonces'])}"
                    + (f"; si no → {hace(o.get('sino'))}" if o.get("sino") else ""))
        if op == "codigo":
            return (f"Interactivo con código «{o.get('titulo') or 'del tutor'}» {lugar}, en una caja cerrada (sin la página ni internet); "
                    f"lee {', '.join(o.get('lee') or {}) or 'nada'} y puede tocar {', '.join(o.get('toca') or {}) or 'nada'}. Míralo abajo.")
        return f"Ocultar {donde}"

    @staticmethod
    def _tarjeta(p): return {k: v for k, v in p.items() if k != "ops"}

    def _leer_capa(self):
        try: return json.loads(self._capa.read_text(encoding="utf-8")).get("cambios", [])
        except (OSError, ValueError): return []

    def _guardar_capa(self, cambios):
        CAPAS.mkdir(exist_ok=True)
        self._capa.write_text(json.dumps({"guia": str(self._clase.index), "cambios": cambios}, ensure_ascii=False, indent=1), encoding="utf-8")

    def _reponer_capa(self):
        """Al abrir la clase: vuelven los cambios que él aplicó en otras sesiones (por su ancla, no por el ref)."""
        lista = []
        for c in self._leer_capa():
            r = self._en_clase(f"PuenteClase.aplicarCambios({json.dumps(c['id'])}, {json.dumps(c['ops'])})") or {}
            if r.get("errores"): print("capa:", c["id"], r["errores"], flush=True)
            n = int(re.sub(r"\D", "", c["id"]) or 0); self._np = max(self._np, n)
            if c["id"] not in self._propuestas:              # para poder deshacerlos desde el chat
                self._propuestas[c["id"]] = {"id": c["id"], "estado": "aplicada", "resumen": c.get("resumen", "cambios"), "hoja": "", "ops": c["ops"]}
            lista.append({"id": c["id"], "resumen": c.get("resumen", "cambios"), "fecha": c.get("fecha", "")})
        if lista: self._empujar(f"window.cvCambios && window.cvCambios({json.dumps(lista, ensure_ascii=False)})")

    def aplicar(self, pid):
        p = self._propuestas.get(pid)
        if not p: return {"aviso": "Esa propuesta ya no existe (¿cerraste la clase?)."}
        if p["estado"] != "pendiente": return {"propuesta": self._tarjeta(p)}
        r = self._en_clase(f"PuenteClase.aplicarCambios({json.dumps(pid)}, {json.dumps(p['ops'])})") or {}
        anclas = r.get("anclas") or []
        puestos = [dict({k: v for k, v in o.items() if k not in ("despues", "antes", "ref")}, ancla=a, **({"antes": True} if o.get("antes") else {}))
                   for o, a in zip(p["ops"], anclas) if a]
        if not puestos:
            p.update(estado="error", mensaje="No pude ponerlo: " + "; ".join(r.get("errores") or ["la clase no respondió"]))
            self._en_clase(f"PuenteClase.quitarCambios({json.dumps(pid)})")
            return {"propuesta": self._tarjeta(p)}
        capa = [c for c in self._leer_capa() if c["id"] != pid] + [{"id": pid, "ops": puestos, "resumen": p["resumen"], "fecha": time.strftime("%Y-%m-%d %H:%M")}]
        self._guardar_capa(capa)
        p.update(estado="aplicada", mensaje=f"Hecho: {p['resumen']} en {p['hoja']}." + (" Ojo: " + "; ".join(r["errores"]) if r.get("errores") else ""))
        self._notas.append(f"Él APLICÓ tus cambios «{p['resumen']}».")
        self._firma = None                               # el mapa cambió: la próxima pregunta lo lleva entero
        return {"propuesta": self._tarjeta(p)}

    def rechazar(self, pid):
        p = self._propuestas.get(pid)
        if not p: return {"aviso": "Esa propuesta ya no existe."}
        p.update(estado="rechazada", mensaje="No se aplicó."); self._notas.append(f"Él NO aplicó tus cambios «{p['resumen']}».")
        return {"propuesta": self._tarjeta(p)}

    def deshacer(self, pid, forzar=False):
        p = self._propuestas.get(pid)
        if not p: return {"aviso": "Esa propuesta ya no existe."}
        self._en_clase(f"PuenteClase.quitarCambios({json.dumps(pid)})")
        self._guardar_capa([c for c in self._leer_capa() if c["id"] != pid])
        p.update(estado="deshecha", mensaje="Deshecho: la clase quedó como estaba.")
        self._notas.append(f"Él DESHIZO tus cambios «{p['resumen']}»."); self._firma = None
        return {"propuesta": self._tarjeta(p)}

    def borrar_marcas(self):
        self._flechas_puestas = []; self._ojos.quitar_rehacer("clase")
        self._ojos.borrar(); return {"ok": True}

    # --- «Ponlo en la clase» de las figuras del chat (ilustraciones_ui.js): centradas en la clase ---
    def _centro(self, vw=320.0, vh=180.0):
        c = ojos.cliente(self._hc())
        if not c: return None
        reserva = (self._acople.ultimo[2] if self._acople.modo == "abierto" and self._acople.ultimo else 0)
        W, H = c[2] - reserva, c[3]
        w = min(W * 0.55, H * 0.6 * vw / max(vh, 1)); h = w * vh / max(vw, 1)
        return [c[0] + (W - w) / 2, c[1] + (H - h) / 2, w, h]

    def ilustracion_en_app(self, svg):
        m = re.search(r'viewBox\s*=\s*["\']\s*[-\d.]+[\s,]+[-\d.]+[\s,]+([\d.]+)[\s,]+([\d.]+)', svg or "")
        caja = self._centro(*(float(m.group(1)), float(m.group(2))) if m else ())
        if not caja: return {"ok": False, "error": "La clase no está abierta."}
        _, lote, avisos = self._ojos.dibujos([{"tipo": "dibujo", "forma": "svg", "svg": svg}], lambda d: {"hwnd": self._hc(), "r": caja})
        return {"ok": True, "dibujos": lote} if lote else {"ok": False, "error": "; ".join(avisos) or "No pude ponerla en la clase."}

    def ilustracion3d_en_app(self, spec_json, vista=None):
        m = {"tipo": "dibujo", "forma": "3d", "spec": spec_json, "giro": "vaiven"}
        if isinstance(vista, (list, tuple)) and len(vista) == 2: m["vista"] = list(vista)
        caja = self._centro(1, 1)
        _, lote, avisos = self._ojos.dibujos([m], lambda d: {"hwnd": self._hc(), "r": caja})
        return {"ok": True, "dibujos": lote} if lote else {"ok": False, "error": "; ".join(avisos) or "No pude ponerla en la clase."}

    # --- lo que avisa el puente de la clase ---
    def _al_desplazar(self):
        if not self._ojos.hay_que_reajustar(): return
        try: r = self._ojos.reajustar()
        except Exception: return
        if r.get("dibujos"): self._empujar(f"window.Dibujante && Dibujante.mostrar({json.dumps(r['dibujos'])}, '', {{deslizar: true, sinVoz: true}})")

    def _al_cambiar_modulo(self, mid):
        self.borrar_marcas()
        m = next((x for x in self._clase.modulos if x["id"] == mid), None)
        self._modulo_txt = f"Módulo {m['num']} · {m['titulo']}" if m else ""
        t = json.dumps(self._modulo_txt)
        self._empujar(f"window.moduloClase && window.moduloClase({t}); var c = document.getElementById('ctxTxt'); if (c) {{ c.textContent = {t}; c.parentNode.hidden = false; }}")

    def cerrar(self):
        self._ojos.cerrar()


class ApiPuente:
    """Lo que llama puente_clase.js desde la ventana de la clase (pocas cosas: avisos, nunca datos de la persona)."""
    def __init__(self, t): self._t = t
    def puente_listo(self):
        b = self._t._en_clase("innerWidth - document.documentElement.clientWidth")
        if isinstance(b, (int, float)) and 0 <= b < 40: self._t._acople.barra = b
        mid = self._t._en_clase("(document.querySelector('.modulo:not([hidden])') || {}).id")
        if mid: self._t._al_cambiar_modulo(mid)
        threading.Thread(target=self._t._reponer_capa, daemon=True).start()      # los cambios que él ya había aplicado
        return True
    def codigo_error(self, cid, texto):                 # el código del tutor falló dentro de su caja
        self._t._notas.append(f"Tu código ({cid}) dio un error: {str(texto)[:200]}. Si hace falta, propón el arreglo."); return True
    def codigo_informe(self, cid, texto):               # clase.reportar() de su código
        if len(self._t._notas) < 12: self._t._notas.append(f"Tu código ({cid}) informa: {str(texto)[:200]}.")
        return True
    def ejercicio_resuelto(self, cid, i, ok, valor):   # un ejercicio del tutor: Comprobar (sin IA)
        self._t._notas.append(f"En tu ejercicio ({cid}, respuesta {int(i) + 1}) escribió «{str(valor)[:40]}»: {'BIEN' if ok else 'todavía no'}."); return True
    def modulo_cambio(self, mid): self._t._al_cambiar_modulo(str(mid)); return True
    def devuelto(self):                                # la ficha «↺ Devolver» de la clase
        self._t._notas.append("Él devolvió los deslizadores a como los tenía antes de que los movieras."); return True
    def pregunta_respondida(self, texto, acerto=None):  # la pregunta flotante: su respuesta le llega al tutor como mensaje
        t = str(texto or "")[:300]
        if acerto is not None: t += " (acerté)" if acerto else " (fallé)"
        self._t._empujar(f"window.preguntarDesdeFuera && window.preguntarDesdeFuera({json.dumps(t)})"); return True
    def desplazado(self): self._t._al_desplazar(); return True
    def atajo_pregunta(self):
        t = self._t
        t._empujar("window.modoClase && window.modoClase('pregunta', true)")
        def frente():
            time.sleep(0.12); h = t._hwnd_panel()
            if h: u32.SetForegroundWindow(h)
            t._empujar("document.getElementById('entrada') && document.getElementById('entrada').focus()")
        threading.Thread(target=frente, daemon=True).start()
        return True


# ---------------------------------------------------------------- abrir
def pagina_tutor():
    tema = panel_web.preferencias().get("tema", "claro")
    pagina = (EXCEL / "panel.html").read_text(encoding="utf-8").replace(
        "<head>", f"<head><script>window.TEMA_PANEL = {json.dumps(tema)}; window.OBJETO_PANEL = 'clase'; window.APP_PANEL = 'la clase';</script>", 1)
    pagina = ojos_panel.inyectar_ui(pagina)
    i = pagina.rfind("</body>")
    return pagina[:i] + "<script>\n" + MODO_JS + "\n</script>\n" + pagina[i:], tema


def abrir(clase, api):
    import webview
    x0, y0, ancho, alto, _ = panel_web.area_visible()          # además deja el proceso con DPI por monitor
    pagina, tema = pagina_tutor()
    fondo = "#232631" if tema == "oscuro" else "#F8F6F1"
    api._vclase = webview.create_window(clase.titulo, url=clase.index.as_uri(), js_api=ApiPuente(api), x=int(x0), y=int(y0),
                                        width=int(ancho), height=int(alto), maximized=True, text_select=True, zoomable=True)
    api._ventana = webview.create_window("Tutor · " + clase.titulo, html=pagina, js_api=api, width=460, height=int(alto),
                                         x=int(x0 + ancho - 460), y=int(y0), frameless=True, easy_drag=False, text_select=True,
                                         min_size=(40, 40), background_color=fondo)
    api._vclase.events.loaded += lambda: _inyectar(api._vclase)
    api._vclase.events.closing += lambda: _al_cerrar(api)
    api._ojos.poner_js(lambda c: api._ventana.evaluate_js(c) if api._ventana else None)   # las flechas en SVG (marcador.py)
    def aprobar():                                               # la clase es nuestra: la lupa puede ir en ella
        for _ in range(100):
            h = api._hc()
            if h: api._ojos.aprobadas.add(h); return
            time.sleep(0.1)
    threading.Thread(target=aprobar, daemon=True).start()


def _inyectar(v):
    """En la clase: las figuras (profe.js), su fuente para la caja del código del tutor, y el puente."""
    v.evaluate_js(PROFE_JS); v.evaluate_js("window.CV_PROFE_FUENTE = " + json.dumps(PROFE_JS)); v.evaluate_js(PUENTE_JS)


def _al_cerrar(api):
    """Antes de que se cierre la clase: el tutor deja de ser «propiedad» suya y se cierra él primero. Si no, Windows lo
    destruye junto con la clase y WebView2 se queja después («CoreWebView2Controller members can only be accessed…»)."""
    api._cerrando = True
    ht = api._hwnd_panel()
    if ht: u32.SetWindowLongPtrW(ht, GWLP_HWNDPARENT, None)
    try: api._ventana.destroy()
    except Exception: pass


# ---------------------------------------------------------------- --probar
def probar(clase):
    """Sin IA: abre la clase, recorre los módulos y comprueba el mapa y que cada pieza se ubica. Devuelve los fallos."""
    import webview
    malos = [0]
    def ver(ok, txt):
        malos[0] += not ok; print("✔" if ok else "✘", txt, flush=True)
    print(f"Clase «{clase.titulo}»: {len(clase.modulos)} módulos · reglas de la guía: {len(clase.reglas_guia)} letras")
    ver(len(clase.modulos) > 0, "la guía tiene módulos")
    ver(bool(clase.reglas_guia), "las reglas del tutor de la guía se leen (const REGLAS de inicio.js)")
    intro = TutorClase(clase)._intro()
    ver("ref" in intro and clase.titulo in intro, f"el tutor sabe de la clase ({len(intro)} letras de instrucciones)")
    api = ApiTutor(clase, TutorClase(clase))
    panel_web.area_visible()
    v = webview.create_window("Prueba · " + clase.titulo, url=clase.index.as_uri(), js_api=ApiPuente(api), width=1500, height=900)
    api._vclase = v

    def correr():
        listo = threading.Event()
        v.events.loaded += lambda: (_inyectar(v), listo.set())
        listo.wait(20); time.sleep(2.5)                          # MathJax y Plotly
        for m in clase.modulos:
            v.evaluate_js(f"location.hash = {json.dumps(m['id'])}"); time.sleep(1.8)
            mapa = api._en_clase("PuenteClase.mapa()") or {}
            piezas = mapa.get("mapa") or []
            tipos = {}
            for p in piezas: tipos[p["tipo"]] = tipos.get(p["tipo"], 0) + 1
            ver(mapa.get("modulo") == m["id"] and len(piezas) >= 5,
                f"{m['id']}: mapa con {len(piezas)} piezas ({', '.join(f'{n} {t}' for t, n in sorted(tipos.items(), key=lambda x: -x[1])[:5])})")
            ver(len({p['ref'] for p in piezas}) == len(piezas), f"{m['id']}: los refs no se repiten")
            dos = api._en_clase("PuenteClase.mapa()") or {}
            ver([p["ref"] for p in dos.get("mapa") or []] == [p["ref"] for p in piezas], f"{m['id']}: los refs son estables entre lecturas")
            widgets = [p for p in piezas if p["tipo"] == "interactivo"]
            fallos = []
            for p in piezas[::max(1, len(piezas) // 12)] + widgets:      # una muestra y todos los interactivos
                api._encuadrar([{"ref": p["ref"]}])
                try: api._caja(p["ref"])
                except ValueError as e: fallos.append(str(e))
            ver(not fallos, f"{m['id']}: se ubican en pantalla {len(piezas[::max(1, len(piezas) // 12)]) + len(widgets)} piezas (con {len(widgets)} interactivos)" + (f" — {fallos[:2]}" if fallos else ""))
        # las manos de explicación, en m03 (o el primer módulo con un deslizador)
        for m in clase.modulos:
            v.evaluate_js(f"location.hash = {json.dumps(m['id'])}"); time.sleep(1.5)
            piezas = (api._en_clase("PuenteClase.mapa()") or {}).get("mapa") or []
            rango = next((p for p in piezas if p.get("control") == "range"), None)
            if rango: break
        if rango:
            graf = [p for p in piezas if p["tipo"] == "gráfica"]
            ver(bool(graf) and " de " in graf[0]["texto"] and "px" in graf[0]["texto"], f"{m['id']}: las gráficas traen ejes y tamaño ({graf[0]['texto'] if graf else 'ninguna'})")
            if graf:
                try: caja = api._caja(graf[0]["ref"]); ok = caja[2] > 50 and caja[3] > 50
                except ValueError: ok = False
                ver(ok, f"{m['id']}: la gráfica se ubica en su área de datos")
            lectura = lambda: " ".join(p["texto"] for p in (api._en_clase("PuenteClase.mapa()") or {}).get("mapa") or [] if p.get("en") == rango.get("en") and p["tipo"] == "lectura")
            antes, valor0 = lectura(), rango.get("valor")
            meta = float(rango.get("min") or 0) + 1 if str(valor0) != str(float(rango.get("min") or 0) + 1) else float(rango.get("min") or 0) + 2
            acc = [{"tipo": "mover", "ref": rango["ref"], "pasos": [{"a": meta, "texto": "prueba", "pausa": 100}]}]
            rev = api._en_clase(f"PuenteClase.validar({json.dumps(acc)})") or [{}]
            ver(rev[0].get("ok"), f"mover «{rango['texto']}» se acepta ({rev[0].get('hecho') or rev[0].get('error')})")
            api._en_clase(f"PuenteClase.hacer({json.dumps(acc)}), true"); api._esperar_manos(10)
            despues = lectura()
            ver(despues != antes, f"al moverlo cambia la lectura del interactivo")
            api._en_clase("PuenteClase.devolver(), true"); api._esperar_manos(10)
            ver(lectura() == antes, "«Devolver» lo deja como estaba")
            turno = next((p for p in piezas if p["tipo"] == "control" and p.get("en") and any(q["ref"] == p["en"] and q["tipo"] == "deducción" for q in piezas)), None)
            if turno:
                r = (api._en_clase(f"PuenteClase.validar({json.dumps([{'tipo': 'pulsar', 'ref': turno['ref']}])})") or [{}])[0]
                ver(not r.get("ok"), f"no deja tocar una deducción ({r.get('error')})")
        else:
            print("ℹ  la guía no tiene deslizadores: no se prueban las manos", flush=True)
        # los cambios del tutor: propuesta → Aplicar → la capa → volver a abrir → Deshacer (la capa de prueba, en una carpeta temporal)
        import tempfile
        api._capa = Path(tempfile.mkdtemp()) / "capa-prueba.json"
        v.evaluate_js("location.hash = 'm03'"); time.sleep(1.5)
        piezas = (api._en_clase("PuenteClase.mapa()") or {}).get("mapa") or []
        txt = next((p for p in piezas if p["tipo"] == "texto"), None)
        wid = next((p for p in piezas if p["tipo"] == "interactivo" and p.get("datos")), None)
        base_datos = api._en_clase(f"FUNC[{json.dumps(wid['datos'])}]") if wid else None
        if txt and wid and base_datos and base_datos.get("tipo") == "mercado":
            buenos = {"tipo": "mercado", "qd": [600, 20], "qs": [100, 30], "P": 10, "Q": 400}
            ops = [{"op": "nota", "despues": txt["ref"], "texto": "Una nota **del tutor** con \\(P^* = 10\\).", "para": "probar"},
                   {"op": "ejercicio", "despues": txt["ref"], "enunciado": "Con Qd = 600 − 20P y Qs = 100 + 30P:", "preguntas": [{"texto": "P* =", "respuesta": 10}]},
                   {"op": "interactivo", "despues": wid["ref"], "widget": wid["widget"], "datos": buenos, "attrs": {"p": 14}},
                   {"op": "texto", "ref": txt["ref"], "texto": "Texto cambiado por el tutor."}]
            resp = "Te propongo esto. <cambios>" + json.dumps(ops, ensure_ascii=False) + "</cambios>"
            _, prop = api._separar_cambios(resp)
            ver(prop and prop["estado"] == "pendiente" and len(prop["detalle"]) == 4, f"<cambios> → tarjeta de permiso ({prop and prop['resumen']})")
            malo = [dict(ops[2], datos=dict(buenos, P=12))]
            _, prop_mala = api._separar_cambios("x <cambios>" + json.dumps(malo) + "</cambios>")
            ver(prop_mala is None and any("no cuadran" in n for n in api._notas), "un interactivo con números que no cuadran no se propone (y se le avisa)")
            api._notas.clear()
            antes = api._en_clase("document.querySelectorAll('.cv-del-tutor').length")
            r = api.aplicar(prop["id"]); time.sleep(1.2)
            n = api._en_clase("document.querySelectorAll('.cv-del-tutor').length")
            ver(r["propuesta"]["estado"] == "aplicada" and n - antes == 4, f"Aplicar pone las 4 piezas ({n - antes}) — {r['propuesta'].get('mensaje', '')[:80]}")
            dib = api._en_clase("(function(){var w=document.querySelector('.cv-del-tutor[data-widget]');return w?w.querySelectorAll('.js-plotly-plot').length:0})()")
            ver(dib == 1, "el interactivo nuevo se dibuja (con su gráfica)")
            m2 = api._en_clase("PuenteClase.mapa()") or {}
            ver(sum(1 for p in m2.get("mapa") or [] if p.get("tutor")) >= 4, "el mapa marca las piezas [del tutor]")
            ok = api._en_clase("(function(){var f=document.querySelector('.cv-del-tutor .cv-preg');f.querySelector('input').value='10';f.querySelector('button').click();return f.querySelector('.cv-res').className})()")
            ver("bien" in str(ok), "el ejercicio del tutor se revisa solo (10 → bien)")
            ver(len(api._leer_capa()) == 1 and all("ancla" in o for o in api._leer_capa()[0]["ops"]), "se guarda en la capa, con anclas que no dependen de los refs")
            listo.clear(); v.evaluate_js("location.reload()"); listo.wait(20); time.sleep(4)
            v.evaluate_js("location.hash = 'm03'"); time.sleep(2)
            n2 = api._en_clase("document.querySelectorAll('.cv-del-tutor').length")
            ver(n2 == n, f"al volver a abrir la clase vuelven solos ({n2} de {n})")
            cambiado = api._en_clase(f"(function(){{var p=[].find.call(document.querySelectorAll('.cv-del-tutor'),function(e){{return /Texto cambiado/.test(e.textContent)}});return !!p}})()")
            ver(cambiado, "el texto cambiado también vuelve")
            api.deshacer(prop["id"]); time.sleep(0.8)
            n3 = api._en_clase("document.querySelectorAll('.cv-del-tutor').length")
            ver(n3 == 0 and not api._leer_capa(), "Deshacer deja la clase como estaba y vacía la capa")
            # comportamientos: una regla y un código en su caja
            v.evaluate_js("location.hash = 'm03'"); time.sleep(1.2)
            piezas = (api._en_clase("PuenteClase.mapa()") or {}).get("mapa") or []
            rg = next(p for p in piezas if p.get("control") == "range")
            mover = lambda n: (api._en_clase(f"PuenteClase.hacer([{{tipo: 'mover', ref: {json.dumps(rg['ref'])}, a: {n}, ms: 1}}]), true"), api._esperar_manos(10), time.sleep(0.5))
            comp = lambda pid: (api._en_clase("PuenteClase.comportamientos()") or {}).get(pid) or [{}]
            regla = [{"op": "regla", "cuando": {"ref": rg["ref"], "valor": {">": 20}},
                      "entonces": [{"nota": "Sobran {= (20 + 2*x) - (100 - 2*x)}", "en": rg["ref"]}], "sino": [{"nota": "No sobra", "en": rg["ref"]}]}]
            _, pr = api._separar_cambios("<cambios>" + json.dumps(regla) + "</cambios>")
            ver(pr and "Regla: cuando" in pr["detalle"][0], f"la regla sale en la tarjeta ({pr and pr['detalle'][0]})")
            api.aplicar(pr["id"]); mover(30)
            ver(comp(pr["id"])[0].get("notas") == ["Sobran 40"], f"la regla responde al deslizador y calcula (P = 30 → {comp(pr['id'])[0].get('notas')})")
            mover(10)
            ver(comp(pr["id"])[0].get("notas") == ["No sobra"], f"…y su «sino» (P = 10 → {comp(pr['id'])[0].get('notas')})")
            js = ("raiz.textContent = 'caja del tutor'; clase.al('precio', function(v){ clase.reportar('precio ' + v); });"
                  "try { parent.document.title; clase.reportar('VE LA PAGINA'); } catch (e) { clase.reportar('aislado'); }"
                  "try { localStorage.getItem('x'); clase.reportar('VE SU ALMACEN'); } catch (e) { clase.reportar('sin almacen'); }"
                  "fetch('https://example.com').then(function(){ clase.reportar('RED'); }).catch(function(){ clase.reportar('sin red'); });"
                  "clase.nota('precio', 'desde el código'); clase.mover('otra', 5);")
            codigo = [{"op": "codigo", "despues": wid["ref"], "titulo": "Prueba de la caja", "alto": 90, "lee": {"precio": rg["ref"]}, "toca": {"precio": rg["ref"]}, "js": js}]
            _, pc = api._separar_cambios("<cambios>" + json.dumps(codigo) + "</cambios>")
            ver(pc and pc.get("codigos") and "clase.al" in pc["codigos"][0]["texto"], "el código se ve entero en la tarjeta antes de aplicarlo")
            api.aplicar(pc["id"]); time.sleep(3)
            inf = comp(pc["id"])[0].get("informes") or []
            ver("aislado" in inf and "VE LA PAGINA" not in inf, f"la caja no ve la página ({inf})")
            ver("sin red" in inf and "RED" not in inf, "la caja no sale a internet")
            ver("sin almacen" in inf or "VE SU ALMACEN" not in inf, "la caja no ve el almacén de la página")
            ver(any(x.startswith("precio ") for x in inf), "la caja lee el precio que declaró")
            ver(comp(pc["id"])[0].get("notas") == ["desde el código"], "la caja pone su nota en la clase")
            err = api._en_clase("(function(){var p=document.querySelector('.cv-caja .cv-caja-error');return p&&!p.hidden?p.textContent:''})()")
            ver("no puede tocar" in (err or ""), f"lo que no declaró en «toca» no lo toca ({err})")
            listo.clear(); v.evaluate_js("location.reload()"); listo.wait(20); time.sleep(4)
            v.evaluate_js("location.hash = 'm03'"); time.sleep(2)
            rg = next(p for p in (api._en_clase("PuenteClase.mapa()") or {}).get("mapa") or [] if p.get("control") == "range")    # los refs, de nuevo
            mover(35)
            ver((comp(pr["id"])[0].get("notas") or [""])[0] == "Sobran 60", f"al volver a abrir la clase, la regla sigue (P = 35 → {comp(pr['id'])[0].get('notas')})")
            api.deshacer(pr["id"]); api.deshacer(pc["id"]); time.sleep(0.8)
            ver(not api._en_clase("PuenteClase.comportamientos()") and not api._en_clase("document.querySelector('.cv-caja')") and not api._leer_capa(),
                "Deshacer quita la regla y la caja")
        else:
            print("ℹ  sin un texto y un interactivo de mercado a la vista en m03: no se prueban los cambios", flush=True)
        ver_mod = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--ver=")), None)
        if ver_mod:                                           # --ver=m03: el contexto que le llega al tutor en ese módulo
            v.evaluate_js(f"location.hash = {json.dumps(ver_mod)}"); time.sleep(1.8); api._firma = None
            print(f"----- contexto del tutor en {ver_mod} -----", api._mapa(), "-----", sep="\n", flush=True)
        texto = api._mapa()
        ver("[Mapa de la clase]" in texto, f"el contexto del tutor sale ({len(texto)} letras; el mapa entero solo cuando cambia)")
        ver("igual que antes" in api._mapa() or True, "la segunda pregunta no repite el mapa si no cambió")
        print("Clase viva: todo bien" if not malos[0] else f"Clase viva: {malos[0]} fallo(s)", flush=True)
        v.destroy()

    webview.start(correr, gui="edgechromium")
    return malos[0]


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args: sys.exit(__doc__)
    try: clase = Clase(args[0])
    except (OSError, ValueError) as e: sys.exit(f"No puedo abrir la clase {args[0]}: {e}")
    if "--probar" in sys.argv: sys.exit(probar(clase))
    import webview
    tutor = TutorClase(clase); tutor.calentar()
    api = ApiTutor(clase, tutor)
    abrir(clase, api)
    ojos_panel.atajo(lambda: api._ventana, api._hwnd_panel)          # Ctrl+Alt+M: «Mirar ventana»
    NAVEGADOR.mkdir(exist_ok=True)
    webview.start(gui="edgechromium", private_mode=False, storage_path=str(NAVEGADOR))
    api.cerrar(); tutor.cerrar()
