"""Compila dia-tutor.dll (plugin de Dia 0.97.2, 32 bits) con el MinGW que hay en C:\\MinGW.

La primera vez descarga a %LOCALAPPDATA%\\dia-tutor-sdk (unos 45 MB) lo que hace falta para compilar:
  - cabeceras de las fuentes de Dia 0.97.2 (solo lib/*.h y app/*.h),
  - el paquete GTK+ 2.24.10 para win32 (la misma GTK con la que se construyo este Dia),
  - cabeceras de libxml2.
Las bibliotecas contra las que se enlaza son las del propio Dia instalado (libdia.dll y dia-app.dll).

Uso:  python compilar.py
"""
import os
import subprocess
import sys
import tarfile
import urllib.request
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.join(os.environ.get("LOCALAPPDATA", AQUI), "dia-tutor-sdk")
DIA_BIN = r"C:\Program Files (x86)\Dia\bin"
GCC = r"C:\MinGW\bin\gcc.exe"
FUENTES = [
    ("dia-0.97.2.tar.xz", "https://download.gnome.org/sources/dia/0.97/dia-0.97.2.tar.xz"),
    ("gtk-bundle.zip", "https://download.gnome.org/binaries/win32/gtk+/2.24/gtk+-bundle_2.24.10-20120208_win32.zip"),
    ("libxml2-dev.zip", "https://download.gnome.org/binaries/win32/dependencies/libxml2-dev_2.9.0-1_win32.zip"),
]


def preparar():
    os.makedirs(SDK, exist_ok=True)
    for nombre, url in FUENTES:
        destino = os.path.join(SDK, nombre)
        if not os.path.exists(destino):
            print("descargando", url)
            urllib.request.urlretrieve(url, destino)
    if not os.path.isdir(os.path.join(SDK, "dia-0.97.2", "lib")):
        with tarfile.open(os.path.join(SDK, "dia-0.97.2.tar.xz")) as t:
            miembros = [m for m in t.getmembers()
                        if m.name.startswith(("dia-0.97.2/lib/", "dia-0.97.2/app/")) and m.name.endswith(".h")]
            t.extractall(SDK, members=miembros, filter="data")
    if not os.path.isdir(os.path.join(SDK, "gtk", "include")):
        with zipfile.ZipFile(os.path.join(SDK, "gtk-bundle.zip")) as z:
            z.extractall(os.path.join(SDK, "gtk"), members=[n for n in z.namelist() if n.startswith(("include/", "lib/"))])
    if not os.path.isdir(os.path.join(SDK, "xml2", "include")):
        with zipfile.ZipFile(os.path.join(SDK, "libxml2-dev.zip")) as z:
            z.extractall(os.path.join(SDK, "xml2"), members=[n for n in z.namelist() if n.startswith("include/")])


def compilar():
    src = os.path.join(SDK, "dia-0.97.2")
    g = os.path.join(SDK, "gtk")
    inc = [f"{src}/lib", f"{src}/app", src, f"{g}/include/gtk-2.0", f"{g}/include/glib-2.0",
           f"{g}/lib/glib-2.0/include", f"{g}/lib/gtk-2.0/include", f"{g}/include/cairo",
           f"{g}/include/pango-1.0", f"{g}/include/atk-1.0", f"{g}/include/gdk-pixbuf-2.0",
           f"{SDK}/xml2/include/libxml2", f"{g}/include"]
    cmd = ([GCC, "-O1", "-Wall", "-Wno-unused", "-shared", "-static-libgcc",
            "-o", os.path.join(AQUI, "dia-tutor.dll"), os.path.join(AQUI, "dia-tutor.c")]
           + [f"-I{i}" for i in inc]
           + [f"-L{DIA_BIN}", "-ldia-app", "-ldia", f"-L{g}/lib", "-lgtk-win32-2.0", "-lgdk-win32-2.0",
              "-lgobject-2.0", "-lglib-2.0", "-lgmodule-2.0", "-lintl"])
    r = subprocess.run(cmd, capture_output=True, text=True)
    # el aviso de isinf viene de geometry.h de Dia contra math.h de MinGW: es inofensivo
    avisos = [l for l in r.stderr.splitlines() if "warning" in l and "isinf" not in l]
    if r.returncode:
        print(r.stderr)
        print("ERROR al compilar")
    else:
        print("ok: dia-tutor.dll", *avisos, sep="\n")
    return r.returncode


if __name__ == "__main__":
    if not os.path.exists(GCC):
        sys.exit("No encuentro el gcc de MinGW en " + GCC)
    preparar()
    sys.exit(compilar())
