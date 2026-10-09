"""Genera ../catalogo_dia.json: todos los tipos de objeto de ESTE Dia 0.97.2 (UML, Standard, Flowchart, ER,
Network, Cisco, BPMN…), cada uno con sus propiedades (nombre, tipo, si se ve en el diálogo, descripción y
opciones de los enum) y el XML exacto de un objeto con sus valores por defecto (orden «plantilla» del plugin).

Con ese catálogo el panel valida y crea objetos de cualquier tipo sin Dia abierto (modo libre del tutor):
solo tipos que existen, solo propiedades que el tipo tiene, y el XML sale de la plantilla de Dia.

Uso:  python catalogo.py     (abre un Dia propio y aparte, con su propia carpeta de órdenes, y lo cierra al final)
El catálogo se genera una vez por versión de Dia: no hace falta repetirlo salvo que se instalen hojas nuevas."""
import gzip, json, os, re, sys, tempfile
import xml.etree.ElementTree as ET

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import tutor_dia

SALIDA = os.path.join(os.path.dirname(AQUI), "catalogo_dia.json")
NS = "{http://www.lysator.liu.se/~alla/dia/}"
ET.register_namespace("dia", NS[1:-1])
FUERA = {"Group"}                     # no se crean sueltos


def objeto_xml(ruta):
    """El <dia:object> de una plantilla, sin el id, como texto compacto."""
    crudo = open(ruta, "rb").read()
    if crudo[:2] == b"\x1f\x8b": crudo = gzip.decompress(crudo)      # Dia guarda comprimido por defecto
    raiz = ET.fromstring(crudo)
    o = next(raiz.iter(NS + "object"))
    o.attrib.pop("id", None)
    t = ET.tostring(o, encoding="unicode").replace(' xmlns:dia="http://www.lysator.liu.se/~alla/dia/"', "")
    return re.sub(r">\s+<", "><", t).replace(" />", "/>")


def generar(dia):
    tipos = sorted(l.split("\t", 1)[1] for l in dia.orden("tipos").splitlines() if l.startswith("tipo\t"))
    cat, fallos = {}, []
    tmp = tempfile.mkdtemp(prefix="dia-catalogo-")
    for i, t in enumerate(tipos):
        if t in FUERA: continue
        ruta = os.path.join(tmp, f"p{i}.dia")
        r = dia.orden(f'plantilla "{t}" "{ruta}"', timeout=10)
        if not r.startswith("ok") or not os.path.exists(ruta):
            fallos.append((t, r[:80])); continue
        props = []
        for l in dia.orden(f'propiedades "{t}"', timeout=10).splitlines():
            p = l.split("\t")
            if p[0] != "prop" or len(p) < 5: continue
            props.append({"n": p[1], "t": p[2], "f": int(p[3]), "d": p[4],
                          **({"e": {k: int(v) for k, _, v in (x.partition("=") for x in p[5:])}} if len(p) > 5 else {})})
        cat[t] = {"props": props, "xml": objeto_xml(ruta)}
        if i % 50 == 0: print(f"{i}/{len(tipos)}", t, flush=True)
    return cat, fallos


if __name__ == "__main__":
    ordenes = tempfile.mkdtemp(prefix="dia-catalogo-ordenes-")
    dia = tutor_dia.Dia(carpeta_ordenes=ordenes)
    vacio = os.path.join(ordenes, "vacio.dia")
    open(vacio, "w", encoding="utf-8").write('<?xml version="1.0" encoding="UTF-8"?><dia:diagram xmlns:dia="http://www.lysator.liu.se/~alla/dia/">'
                                             '<dia:layer name="Fondo" visible="true" active="true"/></dia:diagram>')
    dia.abrir(vacio)
    try:
        cat, fallos = generar(dia)
    finally:
        try: dia.orden("@vacio.dia cerrar forzar", timeout=3); dia.orden("accion FileQuit", timeout=3)
        except Exception: pass
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump({"dia": "0.97.2", "tipos": cat}, f, ensure_ascii=False, separators=(",", ":"))
    print(f"ok: {len(cat)} tipos en {SALIDA} ({os.path.getsize(SALIDA) // 1024} KB); fallaron: {fallos}")
