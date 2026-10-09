"""Capturas de un curso: arma cada módulo con Dia en vivo (como lo hace el panel) y guarda un PNG por paso y por «Tu turno».

    python prueba-dia/panel_dia.py <curso.json> --capturas <carpeta> [módulos]

`módulos` es opcional: ids o números separados por comas (`m5,m6`, `5,6`, `capas`). Sin él, todos.
Trabaja sobre una COPIA del curso, en un Dia propio con su propia carpeta de órdenes (aunque haya otro Dia abierto, el de la persona):
no toca `pasos/`, `mis_diagramas/` ni `progreso.json` del curso. Guarda:
  mN_pasoK.png            el diagrama de la lección en ese paso (se saltan los pasos que no cambian nada, y lo dice)
  mN_turno_inicial.png    el diagrama con el que empieza la persona (solo si el «Tu turno» trae `inicial`)
  mN_turno_solucion.png   la `solucion` aplicada sobre el `inicial`, como lo dibujaría la persona
El dibujo es el de Dia (SVG exportado) pasado a PNG con Chrome o Edge sin ventana (no hace falta Node). Sirve para ver el resultado
real de los pasos (colocación, líneas, rótulos) antes de dárselo a nadie."""
import html, re, shutil, subprocess, sys, tempfile, time
from pathlib import Path

import dia_uml as du
import curso_dia as cu
import cambios_dia as cd

NAVEGADORES = [r"C:\Program Files\Google\Chrome\Application\chrome.exe", r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
               r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe", r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]


def analizar_argumentos(argv):
    """['curso.json', '--capturas', 'carpeta', 'm5,6'] → (curso, carpeta, [módulos]). ValueError con un mensaje claro si falta algo."""
    args = [a for a in argv if a != "--capturas"]
    if "--capturas" not in argv: raise ValueError("falta --capturas <carpeta>")
    pos = [a for a in argv[argv.index("--capturas") + 1:] if not a.startswith("--")]
    resto = [a for a in args if not a.startswith("--") and a not in pos]
    if not pos: raise ValueError("--capturas necesita una carpeta donde guardar las imágenes")
    if not resto: raise ValueError("falta el curso.json")
    carpeta, mods = pos[0], [x for p in pos[1:] for x in re.split(r"[,\s]+", p) if x]
    return resto[0], carpeta, mods


def elegir_modulos(curso, pedidos):
    """Los (número, módulo) que se piden: por número («5», «m5») o por id («capas»). Sin pedidos, todos. ValueError si alguno no existe."""
    todos = list(enumerate(curso.modulos, 1))
    if not pedidos: return todos
    out = []
    for p in pedidos:
        m = re.fullmatch(r"m?(\d+)", p.strip().lower())
        hay = [(k, mod) for k, mod in todos if (m and k == int(m.group(1))) or mod.id == p.strip().lower()]
        if not hay:
            raise ValueError(f"no hay un módulo «{p}» (hay {', '.join(f'{k} = {mod.id}' for k, mod in todos)})")
        out += [x for x in hay if x not in out]
    return sorted(out, key=lambda x: x[0])


def navegador():
    for n in NAVEGADORES:
        if Path(n).exists(): return n
    return None


def svg_a_png(svg, png, escala=1.5):
    """SVG de Dia → PNG con Chrome o Edge sin ventana. True si salió."""
    nav = navegador()
    if not nav: return False
    t = Path(svg).read_text(encoding="utf-8", errors="replace")
    vb = re.search(r'viewBox="([-\d.]+) ([-\d.]+) ([\d.]+) ([\d.]+)"', t)
    if not vb: return False
    w, h = int(float(vb.group(3)) + 1), int(float(vb.group(4)) + 1)
    cuerpo = re.sub(r"<\?xml[^>]*>|<!DOCTYPE[^>]*>", "", t)
    cuerpo = re.sub(r'width="[\d.]+cm" height="[\d.]+cm"', f'width="{w}" height="{h}"', cuerpo, count=1)
    pagina = Path(svg).with_suffix(".html")
    pagina.write_text(f'<html><head><meta charset="utf-8"><style>text{{white-space:pre}}body{{margin:0;background:#fff}}</style></head><body>{cuerpo}</body></html>', encoding="utf-8")
    perfil = tempfile.mkdtemp(prefix="capt-")
    try:
        subprocess.run([nav, "--headless=new", "--disable-gpu", f"--user-data-dir={perfil}", f"--force-device-scale-factor={escala}",
                        f"--window-size={w},{h}", f"--screenshot={png}", pagina.as_uri()], capture_output=True, timeout=90)
    except Exception: return False
    finally:
        shutil.rmtree(perfil, ignore_errors=True)
        try: pagina.unlink()
        except OSError: pass
    return Path(png).exists()


def capturar(ruta_curso, carpeta, pedidos=()):
    """Arma los módulos pedidos con un Dia propio y guarda las imágenes en `carpeta`. Devuelve la lista de archivos."""
    import tutor_dia
    aqui = Path(__file__).resolve().parent
    curso0 = cu.Curso(ruta_curso)
    elegidos = elegir_modulos(curso0, pedidos)
    carpeta = Path(carpeta).resolve(); carpeta.mkdir(parents=True, exist_ok=True)
    if not navegador(): raise RuntimeError("no encuentro Chrome ni Edge para pasar el dibujo de Dia a PNG")
    imagenes = []
    with tempfile.TemporaryDirectory(prefix="capturas-curso-") as tmp:
        copia = Path(tmp) / "curso"
        shutil.copytree(curso0.carpeta, copia, ignore=shutil.ignore_patterns("pasos", "mis_diagramas", "tutor", "progreso.json", "__pycache__", ".git"))
        c = cu.Curso(copia / curso0.ruta.name)
        c.pasos_dir.mkdir(parents=True, exist_ok=True)
        du.escribir(c.en_vivo, [])
        dia = tutor_dia.Dia(carpeta_ordenes=str(Path(tmp) / "ordenes"), carpeta_plugin=str(aqui / "plugin-dia"))
        try:
            dia.abrir(str(c.en_vivo))
        except Exception as e:
            raise RuntimeError(f"no pude abrir un Dia con el plugin ({e})")

        class Vivo:                                   # lo que pide cambios_dia.Cambios de un Dia en vivo
            modo = "plugin"
            def orden(self, t): return dia.orden(t, timeout=60)
        cam = cd.Cambios(Vivo(), {"mio": copia / "x.dia", "leccion": c.en_vivo, "tutor": c.tutor_dir})
        pestana = c.en_vivo.name
        svgs = []

        def exportar(nombre):
            f = carpeta / f"{nombre}.svg"
            r = dia.orden(f'@{pestana} exportar "{f}"', timeout=60)
            if r.startswith("ok"): svgs.append((nombre, f))
            else: print(f"  no pude exportar {nombre}: {r[:80]}")

        try:
            for k, _ in elegidos:
                mod = c.modulos[k - 1]
                t0 = time.time()
                cu.construir(mod, cam, pestana, forzar=True)
                print(f"== m{k} {mod.titulo} ({mod.id}): {len(mod.pasos)} pasos")
                for n, p in enumerate(mod.pasos, 1):
                    t = p.get("_turno")
                    if p.get("_cambios") or p.get("diagrama") is not None:
                        dia.orden(f'@{pestana} cargar "{mod.archivo_paso(n - 1)}"'); exportar(f"m{k}_paso{n}")
                    elif not t:
                        print(f"  paso {n} («{p.get('titulo', '')}»): no cambia nada, se salta")
                    if t:
                        vacio = mod.carpeta_pasos / "_vacio_capt.dia"; du.escribir(vacio, [])
                        base = vacio
                        dia.orden(f'@{pestana} cargar "{vacio}"')
                        if t.get("_inicial"):
                            plan = cu._plan(cam, t["_inicial"], du.leer(vacio), "i0")
                            if cam._ordenes_plan(pestana, plan, "i0"): print(f"  paso {n}: el inicial no se pudo dibujar")
                            exportar(f"m{k}_turno_inicial")
                            base = mod.carpeta_pasos / "_inicial_capt.dia"
                            dia.orden(f'@{pestana} copia "{base}"')
                        if t.get("_solucion"):
                            dia.orden(f'@{pestana} cargar "{base}"')
                            plan = cu._plan(cam, t["_solucion"], du.leer(base), "s0")
                            if cam._ordenes_plan(pestana, plan, "s0"): print(f"  paso {n}: la solución no se pudo dibujar")
                            exportar(f"m{k}_turno_solucion")
                        elif not t.get("_inicial"): print(f"  paso {n} (Tu turno): sin inicial ni solución, no hay nada que dibujar")
                print(f"   m{k}: {time.time() - t0:.1f} s")
        finally:                                      # cerrar el Dia propio sin preguntas
            try:
                dia.orden(f"@{pestana} cerrar forzar", timeout=5)
                dia.orden("accion FileQuit", timeout=3)
            except Exception: pass
            try:
                if dia.proc and dia.proc.poll() is None:
                    time.sleep(1); dia.proc.terminate()
            except Exception: pass
        for nombre, f in svgs:
            png = carpeta / f"{nombre}.png"
            if svg_a_png(f, png): imagenes.append(png)
            else: print(f"  no pude pasar {nombre} a PNG")
            try: f.unlink()
            except OSError: pass
    print(f"Carpeta: {carpeta}")
    for i in imagenes: print("  " + i.name)
    return imagenes


def main(argv):
    try: ruta, carpeta, mods = analizar_argumentos(argv)
    except ValueError as e: sys.exit(f"--capturas: {e}")
    try: capturar(ruta, carpeta, mods)
    except (ValueError, RuntimeError, OSError) as e: sys.exit(f"--capturas: {e}")
