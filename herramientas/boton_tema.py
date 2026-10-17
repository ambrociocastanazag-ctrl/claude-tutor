"""Mete (o actualiza) el botón de tema claro ↔ oscuro en un artefacto HTML.

El botón vive en boton_tema.js; aquí solo se inserta entre marcas, justo antes
de </body>, para poder volver a ponerlo sin duplicarlo.

Desde un build:
    sys.path.insert(0, str(RAIZ / "herramientas"))
    from boton_tema import poner_boton_tema
    html = poner_boton_tema(html)

Suelto (sobre el archivo que se publica):
    python herramientas/boton_tema.py <archivo.html> [...]
"""
import re
import sys
from pathlib import Path

JS = Path(__file__).with_name("boton_tema.js")
INICIO, FIN = "<!-- boton-tema -->", "<!-- /boton-tema -->"
# Al principio de la página: aplica el tema guardado antes de que corra
# cualquier otro script (sin parpadeo, y las figuras que se recargan al
# cambiar de tema, como el OVNI, no entran en bucle).
PRONTO_INI, PRONTO_FIN = "<!-- boton-tema-pronto -->", "<!-- /boton-tema-pronto -->"
PRONTO = (PRONTO_INI + "<script>try{var t=localStorage.getItem('tema-artefacto');"
          "if(t==='light'||t==='dark')document.documentElement.dataset.theme=t}catch(e){}</script>" + PRONTO_FIN)


def poner_pronto(html: str) -> str:
    html = re.sub(re.escape(PRONTO_INI) + ".*?" + re.escape(PRONTO_FIN), "", html, flags=re.S)
    # Tras <head> si lo hay antes de cualquier <script> (si no, ese <head> es
    # texto dentro de un script); si no, al principio, tras <!doctype>/<html>.
    m = re.search(r"<head(\s[^>]*)?>", html, re.I)
    s = html.lower().find("<script")
    if not m or (0 <= s < m.start()):
        m = re.match(r"\s*(<!doctype[^>]*>)?\s*(<html[^>]*>)?", html, re.I)
    return html[:m.end()] + PRONTO + html[m.end():]


def poner_boton_tema(html: str) -> str:
    html = poner_pronto(html)
    bloque = f"{INICIO}\n<script>\n{JS.read_text(encoding='utf-8')}</script>\n{FIN}"
    if INICIO in html:
        return re.sub(re.escape(INICIO) + ".*?" + re.escape(FIN), lambda _: bloque, html, flags=re.S)
    # Solo un </body> real: si tras él aún hay <script>, es texto dentro de un
    # script (una página que se genera desde JS) y el bloque va al final.
    bajo = html.lower()
    i = bajo.rfind("</body>")
    if i < 0 or "<script" in bajo[i:] or "</script" in bajo[i:]:
        return html.rstrip("\n") + "\n" + bloque + "\n"
    return html[:i] + bloque + "\n" + html[i:]


if __name__ == "__main__":
    for ruta in sys.argv[1:]:
        p = Path(ruta)
        p.write_text(poner_boton_tema(p.read_text(encoding="utf-8")), encoding="utf-8", newline="")
        print("botón de tema en", p)
