"""Las flechas de siempre, ahora en SVG: el sustituto de ../prueba-dia/overlay_dia.py con la misma forma de uso.

Recibe las mismas marcas que overlay_dia ({hwnd, ventana, rect, texto, color, n, evitar}: "ventana" es el área de
cliente en las coordenadas en que vienen "rect" y "evitar"; en Dia, las de GTK) y las convierte en dibujos
"forma": "marca" (CONTRATO-MARCAS.md §2) en coordenadas de cliente. La página del panel las dibuja
(Dibujante.ponerMarcas, formas_marcas.js) y capa.py las pone encima de la app, en el grupo "marcas".

js: función que corre código en la página del panel y devuelve lo que dé (pywebview: ventana.evaluate_js). Sin js,
o si la página aún no tiene Dibujante.ponerMarcas, usa overlay_dia.py como antes: nada se rompe a medio camino."""
import json, sys
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import ojos                                                                     # noqa: E402

COLORES = ("azul", "verde", "rojo", "naranja", "amarillo", "morado")
LADOS = ("arriba", "abajo", "izquierda", "derecha")


def a_cliente(marcas):
    """Las marcas de overlay_dia → dibujos "marca" en píxeles físicos del cliente (misma escala que overlay_dia)."""
    lote = []
    for i, m in enumerate(marcas or []):
        try: h = int(m["hwnd"])
        except (KeyError, TypeError, ValueError): continue
        c = ojos.cliente(h)
        if not c: continue
        gx, gy, gw, gh = m.get("ventana") or c
        s = c[2] / gw if gw else 1.0                      # píxeles físicos por unidad de "ventana" (en Dia, la escala de GTK)
        sy = c[3] / gh if gh else s
        conv = lambda b: [round((b[0] - gx) * s), round((b[1] - gy) * sy), round(b[2] * s), round(b[3] * sy)]
        fuera = m.get("fuera") if m.get("fuera") in LADOS else None
        try: dpi = ojos.u32.GetDpiForWindow(h) or 96
        except Exception: dpi = 96
        r = None if fuera or not m.get("rect") else conv(m["rect"])
        evitar = []                                       # como overlay_dia: los botones chicos que no son el objetivo
        for e in m.get("evitar") or []:
            if len(e) != 4: continue
            e = conv(e)
            choca = r and not (e[0] + e[2] <= r[0] or r[0] + r[2] <= e[0] or e[1] + e[3] <= r[1] or r[1] + r[3] <= e[1])
            if not choca and e[2] * e[3] < 0.2 * c[2] * c[3]: evitar.append(e)
        lote.append({"forma": "marca", "id": str(m.get("id") or f"m{i + 1}"), "hwnd": h, "cliente": [c[2], c[3]],
                     "escala": round(dpi / 96, 3), "r": r,
                     "texto": str(m.get("texto") or "")[:60], "n": m.get("n"),
                     "color": m.get("color") if m.get("color") in COLORES else "azul",
                     "tema": m.get("tema") if m.get("tema") in ("claro", "oscuro") else None, "fuera": fuera,
                     "entrada": m.get("entrada", True), "evitar": evitar[:300]})
    return lote


class Marcador:
    """grupo: «marcas» (las del tutor) u otro que empiece por «marcas» para lo que el panel señala aparte (Dia: «marcas_dia»),
    así no se borran entre sí; sus ids llevan el grupo delante para que el texto enlazado no las confunda."""

    def __init__(self, js=None, grupo="marcas"):
        self.js = js or (lambda codigo: None)
        self.grupo = grupo
        self._viejo = None                                # overlay_dia.py, solo si la página no puede dibujarlas
        self.puestas = []

    def _overlay(self):
        if self._viejo is None:
            import ojos_panel
            self._viejo = ojos_panel.Overlay(ojos_panel.OVERLAY)
        return self._viejo

    def vivo(self):
        return True

    def mostrar(self, marcas, pids=(), panel=None, deslizar=False):
        lote = a_cliente(marcas)
        if not lote: return self.borrar()
        for d in lote:
            if deslizar: d["entrada"] = False             # se desliza a su sitio: la entrada no se repite
            if self.grupo != "marcas": d["id"] = f"{self.grupo}_{d['id']}"
        opc = json.dumps({"deslizar": bool(deslizar), "grupo": self.grupo})
        codigo = (f"(window.Dibujante && Dibujante.ponerMarcas) ? (Dibujante.ponerMarcas({json.dumps({'dibujos': lote}, ensure_ascii=False)}, {opc}), true) : false")
        try: ok = self.js(codigo)
        except Exception: ok = False
        if ok:
            if self._viejo is not None and self._viejo.vivo(): self._viejo.orden({"cmd": "borrar"})
            self.puestas = lote
            return {"ok": True, "dibujadas": len(lote), "svg": True}
        self.puestas = lote                               # respaldo: las flechas de Pillow de siempre (sin «fuera»)
        return self._overlay().orden({"cmd": "mostrar", "pids": list(pids), "panel": panel,
                                      "marcas": [m for m in marcas if not m.get("fuera")]})

    def borrar(self):
        self.puestas = []
        try: self.js(f"window.Dibujante && Dibujante.ponerMarcas && Dibujante.ponerMarcas({{dibujos: []}}, {{grupo: {json.dumps(self.grupo)}}})")
        except Exception: pass
        if self._viejo is not None and self._viejo.vivo(): self._viejo.orden({"cmd": "borrar"})
        return {"ok": True}

    def orden(self, o):
        """La interfaz de ojos_panel.Overlay: {"cmd": "mostrar" | "borrar" | "estado" | "salir"}."""
        cmd = (o or {}).get("cmd")
        if cmd == "mostrar": return self.mostrar(o.get("marcas") or [], o.get("pids") or (), o.get("panel"), o.get("deslizar", False))
        if cmd == "borrar": return self.borrar()
        if cmd == "estado": return {"ok": True, "marcas": [{"id": d["id"], "texto": d["texto"], "r": d["r"], "fuera": d["fuera"]} for d in self.puestas]}
        if cmd == "salir": self.cerrar(); return {"ok": True}
        return {"ok": False, "error": f"orden desconocida {cmd!r}"}

    def cerrar(self):
        if self._viejo is not None: self._viejo.cerrar()


def probar():
    """python marcador.py --probar: la conversión a coordenadas de cliente, con una ventana de esta misma consola."""
    fallos = 0

    def ver(c, txt):
        nonlocal fallos
        print(("  ✔ " if c else "  ✘ ") + txt); fallos += not c

    h = ojos.u32.GetForegroundWindow() or ojos.u32.GetDesktopWindow()
    c = ojos.cliente(int(h))
    if not c: print("  (sin ventana para probar)"); return 0
    x, y, w, hh = c
    lote = a_cliente([{"hwnd": h, "ventana": [x, y, w, hh], "rect": [x + 10, y + 20, 30, 40], "texto": "Negrita", "n": 2, "color": "rojo",
                       "evitar": [[x, y, 5, 5]]},
                      {"hwnd": h, "ventana": [0, 0, w / 2, hh / 2], "rect": [5, 10, 15, 20], "texto": "Mitad"},
                      {"hwnd": h, "ventana": [x, y, w, hh], "rect": [x, y, 1, 1], "texto": "Abajo", "fuera": "abajo", "id": "k9"}])
    ver(lote[0]["r"] == [10, 20, 30, 40] and lote[0]["color"] == "rojo" and lote[0]["evitar"] == [[0, 0, 5, 5]] and lote[0]["id"] == "m1",
        "coordenadas de pantalla → cliente")
    ver(lote[1]["r"] == [10, 20, 30, 40], "escala de «ventana» (Dia/GTK) → píxeles físicos")
    ver(lote[2]["r"] is None and lote[2]["fuera"] == "abajo" and lote[2]["id"] == "k9", "«fuera»: sin caja, con su lado y su id")
    pedidos = []
    mk = Marcador(js=lambda codigo: pedidos.append(codigo) or True)
    r = mk.orden({"cmd": "mostrar", "marcas": [{"hwnd": h, "ventana": [x, y, w, hh], "rect": [x + 1, y + 1, 9, 9], "texto": "A"}], "deslizar": True})
    ver(r.get("svg") and "Dibujante.ponerMarcas" in pedidos[-1] and '"deslizar": true' in pedidos[-1], "con página: van a Dibujante.ponerMarcas")
    ver(mk.orden({"cmd": "estado"})["marcas"][0]["texto"] == "A" and mk.orden({"cmd": "borrar"})["ok"] and not mk.puestas, "estado y borrar")
    print("Marcador: todo bien" if not fallos else f"Marcador: {fallos} fallo(s)")
    return fallos


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    if sys.argv[1:2] == ["--probar"]: sys.exit(1 if probar() else 0)
    print(__doc__)
