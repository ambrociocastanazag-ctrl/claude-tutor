"""Modo práctica: lo comparten los tutores del modo curso (apps y código), Excel y Dia.

Con el modo activo el tutor deja de cuidar el avance de la lección y se dedica a ejercicios nuevos: los propone, los
crea con permiso (un archivo nuevo, una hoja «Práctica N», un diagrama nuevo: lo que sepa crear su panel, con su
tarjeta Aplicar / No) y los revisa con Comprobar. La lección queda guardada donde iba; al salir, el panel vuelve ahí
(módulo, paso y la app en la hoja, pestaña o archivo de ese paso). Lo pidió así el 2026-10-16.

CONTRATO para cada panel (su Api hereda de practica.PracticaApi):
  - self._practica = practica.Practica(<carpeta del curso>)          en __init__ (lee practica.json: sobrevive a cerrar)
  - _pos() -> (m, n)                                                 dónde va la lección ahora
  - _ir_pos(m, n) -> dict                                            vuelve ahí (lección Y app) y devuelve self._estado()
  - _estado() añade "practica": self._practica.info()                la página pinta la barra y bloquea Anterior/Siguiente
  - en preguntar(), el contexto empieza con self._practica.prefijo() ("" si no está activa)
  - en el prompt del tutor (su _intro), practica.REGLAS + lo propio del panel (cómo crea un ejercicio)
  - mientras está activa, ir()/modulo() no mueven la lección (la página ya los bloquea; el panel lo respeta igual)
La página (panel-excel/panel.html) llama a practica_entrar() / practica_salir() y pinta lo que devuelven (un estado)."""
import json, time
from pathlib import Path

REGLAS = """
MODO PRÁCTICA: él puede activarlo con un botón. Cuando el [Estado actual] empieza con [MODO PRÁCTICA], la lección está
en pausa (guardada donde iba; volverá ahí al salir) y tu trabajo cambia:
- No le empujes a avanzar ni le recuerdes el paso de la lección: aquí se practica todo lo que quiera, del tema que pida.
- Si pide ejemplos o ejercicios, NO te quedes en el chat: crea un ejercicio nuevo de verdad, con el mecanismo de tu panel
  (ver más abajo cómo), con su permiso (tarjeta Aplicar / No). Dile en una frase qué tiene que hacer y que pulse Comprobar.
- Un ejercicio cada vez, parecido a lo que estudió y un poco más difícil si el anterior le salió bien. No le des la
  solución hasta que lo intente o la pida; si falla, señala el paso exacto.
- Si te pide salir, dile que pulse «Salir de la práctica» (arriba en la Lección): vuelve solo a donde iba.
Sin [MODO PRÁCTICA] sigues como siempre: el curso manda."""


class Practica:
    """El estado del modo práctica de un curso, guardado en <carpeta>/practica.json."""

    def __init__(self, carpeta):
        self.ruta = Path(carpeta) / "practica.json"
        self.activa, self.volver, self.desde, self.hechos = False, None, None, 0
        try:
            d = json.loads(self.ruta.read_text(encoding="utf-8"))
            self.activa, self.volver, self.desde = bool(d.get("activa")), d.get("volver"), d.get("desde")
            self.hechos = int(d.get("hechos") or 0)
        except (OSError, ValueError): pass
        if self.activa and not (isinstance(self.volver, list) and len(self.volver) == 2): self.activa, self.volver = False, None

    def _guardar(self):
        try: self.ruta.write_text(json.dumps({"activa": self.activa, "volver": self.volver, "desde": self.desde, "hechos": self.hechos},
                                             ensure_ascii=False, indent=1), encoding="utf-8")
        except OSError: pass

    def entrar(self, m, n):
        if not self.activa:
            self.activa, self.volver, self.desde, self.hechos = True, [int(m), int(n)], time.strftime("%Y-%m-%d %H:%M"), 0
            self._guardar()

    def salir(self):
        """(m, n) a donde volver, o None si no estaba activa."""
        if not self.activa: return None
        v = self.volver; self.activa, self.volver = False, None; self._guardar()
        return tuple(v)

    def ejercicio_hecho(self):
        """Lo llama el panel cuando se aplica un ejercicio del tutor durante la práctica (para el «Ejercicio N»)."""
        self.hechos += 1; self._guardar(); return self.hechos

    def info(self, nombres=None):
        """Para la página: None si no está activa; si no, a dónde vuelve (texto) y cuántos ejercicios lleva.
        nombres(m) -> título del módulo (opcional)."""
        if not self.activa: return None
        m, n = self.volver
        mod = f"Módulo {m + 1}" + (f" («{nombres(m)}»)" if nombres else "")
        return {"activa": True, "volver": {"m": m, "n": n}, "texto": f"{mod}, paso {n + 1}", "hechos": self.hechos, "desde": self.desde}

    def prefijo(self):
        if not self.activa: return ""
        m, n = self.volver
        return (f"[MODO PRÁCTICA] Activo desde {self.desde}; lleva {self.hechos} ejercicio(s) tuyos. La lección está en pausa en el "
                f"módulo {m + 1}, paso {n + 1}: no lo empujes a avanzar. Crea ejercicios con tu mecanismo y su permiso.\n")


class PracticaApi:
    """Lo que la página llama. El panel pone self._practica y define _pos() y _ir_pos(m, n) (ver el contrato arriba)."""

    def practica_entrar(self):
        m, n = self._pos()
        self._practica.entrar(m, n)
        e = self._estado(); e["aviso_practica"] = "Modo práctica: pídele al tutor un ejercicio. Tu lección te espera aquí."
        return e

    def practica_salir(self):
        v = self._practica.salir()
        e = self._ir_pos(*v) if v else self._estado()
        if v: e["aviso_practica"] = f"Volviste a tu lección: módulo {v[0] + 1}, paso {v[1] + 1}."
        return e

    def practica_estado(self):
        return self._practica.info()


def probar():
    """python practica.py: pruebas sin ventanas ni IA."""
    import tempfile
    malos = 0
    def ver(c, t):
        nonlocal malos
        print(("  ok " if c else "  ✘ MAL ") + t)
        if not c: malos += 1
    with tempfile.TemporaryDirectory() as t:
        class Api(PracticaApi):
            def __init__(s): s._practica, s.m, s.n, s.fui = Practica(t), 2, 4, None
            def _pos(s): return s.m, s.n
            def _ir_pos(s, m, n): s.m, s.n, s.fui = m, n, (m, n); return s._estado()
            def _estado(s): return {"m": s.m, "n": s.n, "practica": s._practica.info()}
        a = Api()
        ver(a._practica.prefijo() == "" and a.practica_estado() is None, "sin práctica: nada en el contexto")
        e = a.practica_entrar()
        ver(e["practica"]["texto"] == "Módulo 3, paso 5" and "[MODO PRÁCTICA]" in a._practica.prefijo(), "al entrar guarda módulo y paso")
        a.m, a.n = 0, 0                                             # el tutor movió la app (hoja nueva, otra pestaña…)
        a._practica.ejercicio_hecho()
        ver(Practica(t).activa and Practica(t).hechos == 1, "sobrevive a cerrar el panel (practica.json)")
        a.practica_entrar(); ver(a._practica.volver == [2, 4], "entrar dos veces no pisa a dónde volver")
        e = a.practica_salir()
        ver(a.fui == (2, 4) and e["practica"] is None and "módulo 3, paso 5" in e["aviso_practica"], "al salir vuelve a donde iba")
        ver(a.practica_salir()["practica"] is None and a.fui == (2, 4), "salir sin estar activa no mueve nada")
        (Path(t) / "practica.json").write_text('{"activa": true, "volver": "x"}', encoding="utf-8")
        ver(not Practica(t).activa, "un practica.json roto no deja la práctica a medias")
    print("Práctica: todo bien" if not malos else f"Práctica: {malos} MAL")
    return not malos


if __name__ == "__main__":
    import sys
    sys.exit(0 if probar() else 1)
