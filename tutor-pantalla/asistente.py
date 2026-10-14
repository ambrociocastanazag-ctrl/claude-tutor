"""La sesión de Claude que responde en el panel (modo asistente) y cómo se leen sus marcas.

Como el tutor de panel-excel (motor.Tutor): un proceso `claude -p` con stream-json que arranca una vez y
responde a trozos; sin MCP y sin ajustes, para que no cargue hooks ni avisos de nadie.
Puede buscar en la web y leer enlaces (WebSearch y WebFetch, sin permisos que pedir); nada más.
Para señalar, Claude termina su respuesta con una línea  MARCAS: [...]  que el panel quita del texto y
convierte en flechas encima de la ventana (ver marcas())."""
import json, re, shutil, subprocess, tempfile, threading

REGLAS = """Eres el asistente personal de una persona en su PC con Windows. No tienes una tarea fija: ayudas con lo que
pida (un programa, un error, un formulario, una duda cualquiera). Responde en español, cercano y corto (unas pocas
líneas; listas numeradas si son pasos). Fórmulas en texto plano, sin LaTeX.

A veces te manda, con su permiso, la captura de UNA ventana y la lista de sus controles (id | tipo | nombre | caja
x,y,w,h en píxeles de la captura). Solo puedes mirar y señalar: nunca digas que hiciste clic, escribiste o cambiaste
algo; explica qué tiene que hacer él.

Para señalar en la ventana, termina tu respuesta con UNA línea así (y nada después):
MARCAS: [{"id": 12, "texto": "Negrita"}, {"id": 30, "texto": "Luego aquí", "n": 2}]
- Usa el "id" de la lista siempre que el control exista; si no está en la lista, usa "caja": [x, y, w, h] en
  píxeles de la captura (mira bien la imagen).
- Máximo 4 marcas; "texto" de 1 a 4 palabras; "n" si hay un orden; "color" opcional: azul (por defecto), verde
  (correcto), rojo (error), naranja (atención).
- Si no hay nada que señalar o no tienes captura, no pongas la línea MARCAS.
Las marcas se refieren a la última captura que te mandó.

Puedes investigar: WebSearch para buscar en internet y WebFetch para leer una página (por ejemplo, un enlace que te
pase). Úsalos cuando la respuesta dependa de algo actual, de una página concreta o de datos que no sabes seguro; no
busques lo que ya sabes. Cuando uses una fuente, da su enlace completo (https://...) para que pueda abrirlo, y si
recomiendas descargar o comprar algo, enlaza la página oficial."""
HERRAMIENTAS = "WebSearch,WebFetch"         # solo leer la web: nada que toque su PC
AVISOS = {"WebSearch": "Buscando en la web…", "WebFetch": "Leyendo la página…"}

MARCA_RE = re.compile(r"\n?\s*MARCAS:\s*(\[.*\])\s*$", re.S)


def separar(texto):
    """(texto sin la línea MARCAS, lista de marcas tal como las escribió Claude)."""
    m = MARCA_RE.search(texto or "")
    if not m: return (texto or "").strip(), []
    try: lista = json.loads(m.group(1))
    except ValueError: lista = []
    return texto[:m.start()].strip(), [x for x in lista if isinstance(x, dict)][:4]


def marcas(lista, cap):
    """Las marcas de Claude → cajas en píxeles de la captura [x, y, w, h], con su texto. Descarta lo que no exista."""
    out = []
    for m in lista:
        caja = None
        if "id" in m:
            try: c = cap.control(int(m["id"]))
            except (TypeError, ValueError): c = None
            if c: caja = c["caja"]
        if caja is None and isinstance(m.get("caja"), list) and len(m["caja"]) == 4:
            try: caja = [float(v) for v in m["caja"]]
            except (TypeError, ValueError): caja = None
        if caja is None or caja[2] <= 0 or caja[3] <= 0: continue
        texto = str(m.get("texto") or "")[:40]
        if m.get("n"): texto = re.sub(r"^\s*\d+\s*[.)]\s*", "", texto)      # el overlay ya pone «2.» delante
        out.append({"caja": caja, "texto": texto, "n": m.get("n"),
                    "color": m.get("color") if m.get("color") in ("azul", "verde", "rojo", "naranja", "amarillo") else "azul"})
    return out


class Sesion:
    """Un `claude -p` vivo. preguntar() acepta texto o bloques (imagen + texto) y llama a al_trozo con cada trozo."""
    MAX_TURNOS = 20

    def __init__(self, reglas=REGLAS, modelo="sonnet", herramientas=HERRAMIENTAS):
        self.reglas, self.modelo, self.herramientas = reglas, modelo, herramientas
        self.p = None; self.turnos = 0; self.cerrojo = threading.Lock()

    def _arrancar(self):
        exe = shutil.which("claude")
        if not exe: raise RuntimeError("No encuentro Claude Code (el comando 'claude') en esta PC.")
        cmd = [exe, "-p", "--input-format", "stream-json", "--output-format", "stream-json", "--verbose",
               "--include-partial-messages", "--tools", self.herramientas, "--allowedTools", self.herramientas,
               "--model", self.modelo,
               "--strict-mcp-config", "--no-session-persistence", "--setting-sources", ""]
        self.p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                  text=True, encoding="utf-8", bufsize=1, cwd=tempfile.gettempdir(),
                                  creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.turnos = 0
        self._turno(self.reglas + "\n\nResponde solo: Listo", lambda t: None)

    def _turno(self, contenido, al_trozo, al_aviso=lambda t: None):
        """al_aviso: «Buscando en la web…» cuando usa una herramienta (el panel lo enseña mientras espera)."""
        self.p.stdin.write(json.dumps({"type": "user", "message": {"role": "user", "content": contenido}}) + "\n")
        self.p.stdin.flush(); partes = []
        for linea in self.p.stdout:
            try: ev = json.loads(linea)
            except ValueError: continue
            if ev.get("type") == "stream_event":
                e = ev["event"]; bloque = e.get("content_block") or {}
                if e.get("type") == "content_block_start" and bloque.get("type") == "tool_use":
                    al_aviso(AVISOS.get(bloque.get("name"), "Investigando…"))
                    if partes and not "".join(partes).endswith("\n\n"): partes.append("\n\n"); al_trozo("\n\n")
                dl = e.get("delta", {})
                if dl.get("type") == "text_delta": partes.append(dl["text"]); al_trozo(dl["text"])
            elif ev.get("type") == "result":
                self.turnos += 1
                if ev.get("is_error"): self.turnos = self.MAX_TURNOS     # la próxima pregunta abre una sesión limpia
                return "".join(partes) or ev.get("result", "")
        raise RuntimeError("La sesión del asistente se cerró.")

    def _asegurar(self):
        if self.p is None or self.p.poll() is not None or self.turnos >= self.MAX_TURNOS:
            self.cerrar(); self._arrancar()

    def calentar(self):
        threading.Thread(target=lambda: self._con_cerrojo(self._asegurar), daemon=True).start()

    def _con_cerrojo(self, f):
        with self.cerrojo: return f()

    def preguntar(self, contenido, al_trozo=lambda t: None, al_aviso=lambda t: None):
        def hacer():
            for intento in range(2):              # si la sesión murió, se reinicia una vez
                try:
                    self._asegurar()
                    return self._turno(contenido, al_trozo, al_aviso)
                except (RuntimeError, OSError, ValueError):
                    self.cerrar()
                    if intento: raise
        return self._con_cerrojo(hacer)

    def reiniciar(self):
        self._con_cerrojo(self.cerrar)

    def cerrar(self):
        if self.p and self.p.poll() is None:
            try: self.p.stdin.close(); self.p.wait(timeout=5)
            except Exception: self.p.kill()
        self.p = None
