"""Busca fotos reales con licencia libre en Wikimedia Commons e iNaturalist, y baja la elegida con su crédito.

Buscar (lista id | fuente | licencia | autor | lugar | página):
    python herramientas/buscar_fotos.py "Bothrops asper" ["otra búsqueda" ...] [--lugar Guatemala | --place 6940]
                                        [--fuente ambas|commons|inat] [-n 8]
Bajar una (miniatura de ~1100 px) e imprimir el crédito listo para el pie de foto:
    python herramientas/buscar_fotos.py --bajar <id> <carpeta/archivo.jpg>

- iNaturalist solo trae observaciones de grado «research» y fotos CC0, CC BY, CC BY-SA o CC BY-NC.
- Con --lugar se imprime el lugar que eligió iNaturalist: verifícalo (hay nombres repetidos en otros países).
- Commons solo deja pasar dominio público y CC; el resto se descarta.
- Mira siempre la foto bajada (Read) antes de usarla: que muestre lo que dice el pie.
Solo usa la biblioteca estándar de Python."""
import argparse
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

H = {"User-Agent": "TutorDeEstudio/1.0 (guias de estudio; buscar_fotos.py)"}
COMMONS = "https://commons.wikimedia.org/w/api.php"
INAT = "https://api.inaturalist.org/v1"
LIC_INAT = {"cc0": "CC0", "cc-by": "CC BY", "cc-by-sa": "CC BY-SA", "cc-by-nc": "CC BY-NC"}


def pedir(url, **params):
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(urllib.request.Request(url, headers=H), timeout=30) as r:
        return json.load(r)


def texto(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s or ""))).strip()


def lugar_inat(nombre):
    res = pedir(f"{INAT}/places/autocomplete", q=nombre, per_page=5).get("results", [])
    if not res:
        sys.exit(f"iNaturalist no conoce el lugar «{nombre}»")
    p = res[0]
    print(f"(iNaturalist: lugar {p['id']} = {p.get('display_name') or p['name']}; verifícalo)")
    return p["id"]


def buscar_inat(q, place, n):
    params = dict(taxon_name=q, photo_license="cc0,cc-by,cc-by-sa,cc-by-nc", quality_grade="research",
                  photos="true", per_page=n, order_by="votes")
    if place:
        params["place_id"] = place
    out = []
    for o in pedir(f"{INAT}/observations", **params).get("results", []):
        for f in o.get("photos", [])[:1]:
            lic = LIC_INAT.get((f.get("license_code") or "").lower())
            if not lic:
                continue
            autor = (o.get("user") or {}).get("name") or (o.get("user") or {}).get("login") or "?"
            out.append(dict(id=f"i:{o['id']}/{f['id']}", fuente="iNaturalist", licencia=lic, autor=autor,
                            lugar=o.get("place_guess") or "", pagina=f"https://www.inaturalist.org/photos/{f['id']}",
                            mini=f["url"].replace("square", "large"), especie=(o.get("taxon") or {}).get("name", "")))
    return out


def buscar_commons(q, n):
    d = pedir(COMMONS, action="query", format="json", generator="search", gsrsearch=q, gsrnamespace=6,
              gsrlimit=n, prop="imageinfo", iiprop="url|extmetadata|mime", iiurlwidth=1100)
    out = []
    for p in sorted(d.get("query", {}).get("pages", {}).values(), key=lambda p: p.get("index", 0)):
        ii = (p.get("imageinfo") or [{}])[0]
        if not ii.get("mime", "").startswith("image/"):          # un SVG se baja como PNG (thumburl)
            continue
        m = ii.get("extmetadata", {})
        lic = texto(m.get("LicenseShortName", {}).get("value"))
        if not re.search(r"^(CC|Public domain|PD)", lic, re.I):
            continue
        out.append(dict(id="c:" + p["title"], fuente="Commons", licencia=lic,
                        autor=texto(m.get("Artist", {}).get("value")) or "?",
                        lugar="", pagina=ii.get("descriptionurl", ""), mini=ii.get("thumburl") or ii.get("url"),
                        especie=texto(m.get("ImageDescription", {}).get("value"))[:80]))
    return out


def una(ident):
    if ident.startswith("i:"):
        obs, _, foto = ident[2:].partition("/")
        o = (pedir(f"{INAT}/observations/{obs}").get("results") or [{}])[0]
        f = next((x for x in o.get("photos", []) if str(x["id"]) == foto or not foto), None)
        if not f:
            sys.exit("No encontré esa foto en la observación.")
        lic = LIC_INAT.get((f.get("license_code") or "").lower())
        if not lic:
            sys.exit("Esa foto no tiene licencia libre.")
        autor = (o.get("user") or {}).get("name") or (o.get("user") or {}).get("login") or texto(f.get("attribution"))
        return dict(licencia=lic, autor=autor, lugar=o.get("place_guess") or "",
                    pagina=f"https://www.inaturalist.org/photos/{f['id']}", mini=f["url"].replace("square", "large"))
    if ident.startswith("c:"):
        d = pedir(COMMONS, action="query", format="json", titles=ident[2:], prop="imageinfo",
                  iiprop="url|extmetadata", iiurlwidth=1100)
        p = next(iter(d["query"]["pages"].values()))
        ii = p["imageinfo"][0]; m = ii.get("extmetadata", {})
        return dict(licencia=texto(m.get("LicenseShortName", {}).get("value")), autor=texto(m.get("Artist", {}).get("value")) or "?",
                    lugar="", pagina=ii["descriptionurl"], mini=ii.get("thumburl") or ii["url"])
    sys.exit("El id empieza con i: (iNaturalist) o c: (Commons), como sale en la lista.")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("busquedas", nargs="*")
    ap.add_argument("--lugar"); ap.add_argument("--place", type=int)
    ap.add_argument("--fuente", choices=["ambas", "commons", "inat"], default="ambas")
    ap.add_argument("-n", type=int, default=8)
    ap.add_argument("--bajar", nargs=2, metavar=("ID", "ARCHIVO"))
    a = ap.parse_args()
    if a.bajar:
        ident, archivo = a.bajar
        f = una(ident)
        Path(archivo).parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(urllib.request.Request(f["mini"], headers=H), timeout=60) as r:
            Path(archivo).write_bytes(r.read())
        lugar = f", {f['lugar']}" if f["lugar"] else ""
        print(f"Guardada: {archivo} ({Path(archivo).stat().st_size // 1024} KB). Mírala antes de usarla.")
        print(f'Crédito: <span class="credito">Foto: {html.escape(f["autor"])}{html.escape(lugar)} · '
              f'<a href="{f["pagina"]}" target="_blank" rel="noopener">{f["licencia"]}</a></span>')
        return
    if not a.busquedas:
        ap.error("falta qué buscar (o --bajar ID ARCHIVO)")
    place = a.place or (lugar_inat(a.lugar) if a.lugar and a.fuente != "commons" else None)
    for q in a.busquedas:
        print(f"== {q}")
        res = []
        if a.fuente in ("ambas", "inat"):
            res += buscar_inat(q, place, a.n)
        if a.fuente in ("ambas", "commons"):
            res += buscar_commons(q, a.n)
        if not res:
            print("  (nada con licencia libre)")
        for r in res:
            print(f"  {r['id']} | {r['fuente']} | {r['licencia']} | {r['autor'][:40]} | {r['lugar'][:40]} | {r['pagina']}")


if __name__ == "__main__":
    main()
