"""Voz natural para los paneles: el audio (MP3) de una frase con edge-tts, las voces «Neural» de Microsoft que usa
Edge para leer en voz alta (es-MX: Dalia y Jorge). Gratis y sin cuenta, pero necesita internet: el TEXTO va al
servicio de Microsoft (nunca capturas). Si falla o no hay internet, voz.js vuelve a la voz de Windows.

La voz sale de panel-excel/preferencias.json ("voz": "es-MX-JorgeNeural", por ejemplo); por defecto, Dalia.

  python voz_natural.py "texto" salida.mp3 [voz]     guarda una muestra para escucharla
  python voz_natural.py --voces                      las voces en español que hay hoy"""
import asyncio, base64, json, sys, threading
from collections import OrderedDict
from pathlib import Path

VOZ = "es-MX-DaliaNeural"
VELOCIDAD = "+5%"
PREFERENCIAS = Path(__file__).resolve().parent.parent / "panel-excel" / "preferencias.json"
_cache, _cerrojo = OrderedDict(), threading.Lock()          # las frases ya generadas (al repetir o narrar, no se piden otra vez)


def voz_elegida():
    try: return json.loads(PREFERENCIAS.read_text(encoding="utf-8")).get("voz") or VOZ
    except Exception: return VOZ


def mp3(texto, voz=None, velocidad=VELOCIDAD, espera=12):
    """Los bytes MP3 de la frase, o None si no hay edge-tts, internet o el servicio falla."""
    try: import edge_tts
    except ImportError: return None
    voz = voz or voz_elegida()

    async def generar():
        datos = bytearray()
        async for trozo in edge_tts.Communicate(texto, voz, rate=velocidad).stream():
            if trozo["type"] == "audio": datos += trozo["data"]
        return bytes(datos)
    try: datos = asyncio.run(asyncio.wait_for(generar(), espera))
    except Exception: return None
    return datos or None


def audio(texto, voz=None):
    """La frase como data URL para un <audio> de la página (con caché), o None."""
    texto = " ".join(str(texto or "").split())[:1500]
    if not texto: return None
    clave = (texto, voz or voz_elegida())
    with _cerrojo:
        if clave in _cache: _cache.move_to_end(clave); return _cache[clave]
    datos = mp3(texto, clave[1])
    if not datos: return None
    url = "data:audio/mpeg;base64," + base64.b64encode(datos).decode()
    with _cerrojo:
        _cache[clave] = url
        while len(_cache) > 80: _cache.popitem(last=False)
    return url


if __name__ == "__main__":
    try: sys.stdout.reconfigure(encoding="utf-8")
    except Exception: pass
    a = sys.argv[1:]
    if a == ["--voces"]:
        import edge_tts
        for v in asyncio.run(edge_tts.list_voices()):
            if v["Locale"].startswith("es-"): print(v["ShortName"], v["Gender"])
    elif len(a) >= 2:
        d = mp3(a[0], a[2] if len(a) > 2 else None)
        if not d: sys.exit("No se pudo generar el audio (¿internet? ¿python -m pip install edge-tts?)")
        Path(a[1]).write_bytes(d); print(f"Guardado {a[1]} ({len(d) // 1000} KB, voz {a[2] if len(a) > 2 else voz_elegida()})")
    else:
        print(__doc__)
