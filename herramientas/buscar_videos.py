"""Busca videos en YouTube y muestra solo los que existen (verificados con oEmbed): id | canal | título.

Uso: python herramientas/buscar_videos.py "búsqueda 1" ["búsqueda 2" ...]
Elige de canales serios (Deep Look, BBC Earth, National Geographic, NSF, universidades, museos)."""
import json
import re
import sys
import urllib.parse
import urllib.request

H = {"User-Agent": "Mozilla/5.0", "Accept-Language": "es,en"}
for q in sys.argv[1:]:
    pagina = urllib.request.urlopen(urllib.request.Request(
        "https://www.youtube.com/results?" + urllib.parse.urlencode({"search_query": q}), headers=H)).read().decode("utf-8", "ignore")
    print("==", q)
    for v in list(dict.fromkeys(re.findall(r'"videoId":"([\w-]{11})"', pagina)))[:8]:
        try:
            d = json.load(urllib.request.urlopen(urllib.request.Request(
                "https://www.youtube.com/oembed?format=json&url=https://www.youtube.com/watch?v=" + v, headers=H)))
            print(f"  https://www.youtube.com/watch?v={v} | {d['author_name']} | {d['title']}")
        except Exception:
            pass
