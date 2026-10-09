"""Cliente del plugin dia-tutor: abre Dia con el plugin cargado y le manda ordenes.

    from tutor_dia import Dia
    dia = Dia()
    dia.abrir(r"C:\\...\\diagrama.dia")        # diaw.exe --integrated con el plugin
    dia.orden("clase 3 2 Estudiante")
    dia.orden('cargar "C:/.../paso_3.dia"')   # sustituye el contenido del diagrama
    dia.orden("seleccionar Estudiante")       # resalta
    dia.orden("accion ObjectsProperties")     # abre Propiedades del objeto seleccionado
    dia.orden("pulsar Atributos")             # cambia de pestana (o pulsa un boton por su texto)
    dia.widgets()                             # posicion en pantalla de menus, botones, pestanas...
    dia.orden("@mi_diagrama.dia cajas")       # caja actual (cm) de cada clase y de cada fila
    dia.orden('@mi_diagrama.dia nota 14 3 "deberia ser privado" rojo 12.9 3.9')   # marcas del tutor
    dia.orden("@mi_diagrama.dia borrar_marcas")                                   # (capa "Tutor")

Las ordenes de marcas (recuadro, flecha, nota, borrar_marcas, cajas, capas) estan en la cabecera
de dia-tutor.c; las del tutor del panel se traducen con dia_uml.ordenes_marcas. Las de la version 4
(poner, medir, exportar, tipos, plantilla, propiedades) tambien; las usan ../cambios_dia.py, ../panel_dia.py
y catalogo.py.
Las de la version 5 (widgets con el HWND de cada ventana, pantalla, seleccionar con varias REF, hoja) las usan
../interfaz_dia.py y ../panel_dia.py (flechas encima de Dia y «hazlo por mi»).

El plugin no necesita instalarse: se carga desde esta carpeta con la variable DIA_LIB_PATH.
Las ordenes van por archivo (orden.txt / respuesta.txt) en %LOCALAPPDATA%\\dia-tutor.
"""
import os
import re
import subprocess
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
DIA_BIN = r"C:\Program Files (x86)\Dia\bin"
DIAW = os.path.join(DIA_BIN, "diaw.exe")
CARPETA_ORDENES = os.path.join(os.environ.get("LOCALAPPDATA", AQUI), "dia-tutor")
_LINEA = re.compile(r'^(widget|pestana|ventana) (\S+) x=(-?\d+) y=(-?\d+) w=(\d+) h=(\d+)(.*)$')
_CLAVE = re.compile(r'(\w+)="([^"]*)"')


class Dia:
    def __init__(self, carpeta_ordenes=CARPETA_ORDENES, carpeta_plugin=AQUI):
        self.carpeta = carpeta_ordenes
        self.carpeta_plugin = carpeta_plugin
        self.proc = None
        os.makedirs(self.carpeta, exist_ok=True)

    def _ruta(self, nombre):
        return os.path.join(self.carpeta, nombre)

    def abrir(self, archivo, integrated=True, timeout=40):
        """Lanza diaw.exe con el plugin y espera a que responda al ping."""
        for f in ("orden.txt", "respuesta.txt"):
            try:
                os.remove(self._ruta(f))
            except FileNotFoundError:
                pass
        env = os.environ.copy()
        env["DIA_LIB_PATH"] = self.carpeta_plugin + ";" + os.path.join(os.path.dirname(DIA_BIN), "dia")
        env["DIA_TUTOR_DIR"] = self.carpeta
        args = [DIAW] + (["--integrated"] if integrated else []) + [archivo]
        self.proc = subprocess.Popen(args, env=env, cwd=DIA_BIN)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.proc.poll() is not None:
                raise RuntimeError("Dia se cerro al arrancar")
            if self.orden("ping", timeout=1).startswith("ok"):
                return self.proc
        raise RuntimeError("el plugin no responde: falta dia-tutor.dll en %s o es otro Dia" % self.carpeta_plugin)

    def orden(self, texto, timeout=8):
        """Manda una o varias lineas y devuelve la respuesta del plugin (texto)."""
        tmp, fin, resp = self._ruta("orden.tmp"), self._ruta("orden.txt"), self._ruta("respuesta.txt")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(texto + "\n")
        os.replace(tmp, fin)
        t0 = time.time()
        while time.time() - t0 < timeout:
            if os.path.exists(resp):
                time.sleep(0.03)
                try:
                    with open(resp, encoding="utf-8") as f:
                        r = f.read()
                    os.remove(resp)
                except FileNotFoundError:   # otro cliente la leyó antes: se sigue esperando, no es un fallo del plugin
                    continue
                return r.strip()
            time.sleep(0.02)
        return "error sin respuesta del plugin"

    def widgets(self):
        """Lista de dicts con lo que hay en pantalla: tipo (ventana/widget/pestana), clase GTK,
        x, y, w, h (pixeles de pantalla) y texto/tip/tipo de objeto Dia."""
        res = []
        for linea in self.orden("widgets", timeout=10).splitlines():
            m = _LINEA.match(linea)
            if not m:
                continue
            d = {"tipo": m.group(1), "clase": m.group(2), "x": int(m.group(3)), "y": int(m.group(4)),
                 "w": int(m.group(5)), "h": int(m.group(6)), "activa": " activa" in m.group(7)}
            d.update({k: v for k, v in _CLAVE.findall(m.group(7))})
            res.append(d)
        return res

    def buscar(self, **criterios):
        """Primer widget en pantalla que cumple los criterios, p. ej. buscar(texto="Nuevo") o
        buscar(objeto="UML - Class") (la clave 'objeto' mira el campo 'tipo' del plugin)."""
        for w in self.widgets():
            ok = True
            for k, v in criterios.items():
                campo = "tipo" if k == "objeto" else k
                if k == "tipo" and w.get("tipo") != v:
                    ok = False
                elif k != "tipo" and w.get(campo) != v:
                    ok = False
            if ok:
                return w
        return None

    def cerrar(self):
        """Cierra la ventana de Dia que abrio este cliente (como la X; Dia pregunta si hay cambios)."""
        if self.proc and self.proc.poll() is None:
            try:
                self.orden("accion FileQuit", timeout=2)
                self.proc.wait(timeout=5)
            except Exception:
                pass
