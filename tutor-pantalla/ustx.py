"""Revisión sin IA de proyectos de OpenUtau (.ustx, YAML) para el «Tu turno» del modo curso: {"tipo": "ustx", ...}.

Todo es opcional menos «archivo»; se cumple si se cumple todo lo que trae:
    "archivo":     ruta relativa a la carpeta del curso (o absoluta); con * se toma el más reciente que coincida
    "pista":       número de pista de voz (1 = la primera); si falta, la primera con «cantante» que coincida y notas
    "cantante":    texto o lista: el cantante de esa pista lo contiene ("Aitzu", "Moonlight")
    "fonemizador": texto o lista: el fonemizador lo contiene ("SpanishVCCV", "Japanese")
    "bpm":         número, o [mínimo, máximo]
    "notas":       ["C4", "C4", "G4", ...]: las primeras notas de la pista, en orden
    "transponer":  false (exactas, lo normal) | "octava" (vale una o más octavas arriba o abajo) | true (cualquier tono)
    "ritmo":       [1, 1, 2, ...]: duración de esas notas en negras (tolerancia de 1/16 de negra)
    "letras":      ["es", "tre", ...]: la letra de esas notas (sin mayúsculas ni acentos)
    "min_notas":   la pista tiene al menos tantas notas
    "vibrato":     al menos tantas notas con vibrato
    "pitch":       true: hay al menos una curva de tono editada (puntos de pitch o la curva PITD)
    "curva":       "dyn" (u otra abreviatura): esa curva de expresión está dibujada (no todo en cero)
    "audio":       true: hay una pista de audio (el instrumental)
    "pistas_voz":  al menos tantas pistas con notas
`revisar(q, base)` → (ok, detalle): el detalle dice lo primero que falla, en una frase para el estudiante.

    python ustx.py --probar      # pruebas con proyectos hechos a propósito
"""
import glob, os, sys, tempfile, unicodedata
from pathlib import Path

try:
    import yaml
except ImportError:                     # sin pyyaml el modo curso funciona igual; solo los turnos «ustx» lo piden
    yaml = None

TIPO = {"ustx": "un proyecto de OpenUtau guardado: {\"tipo\": \"ustx\", \"archivo\": \"mis_proyectos/x.ustx\", \"notas\": [...], \"letras\": [...], \"cantante\": \"Aitzu\", ...} (ver ustx.py)"}
CLAVES = {"tipo", "archivo", "pista", "cantante", "fonemizador", "bpm", "notas", "transponer", "ritmo", "letras", "min_notas",
          "vibrato", "pitch", "curva", "audio", "pistas_voz", "texto", "_base"}
SOSTENIDOS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
SOLFEO = ["do", "do#", "re", "re#", "mi", "fa", "fa#", "sol", "sol#", "la", "la#", "si"]
NOMBRES = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def tono(altura):
    """"C4" → 60, "F#4" → 66, "Bb3" → 58."""
    a = str(altura).strip()
    n, resto = NOMBRES[a[0].upper()], a[1:]
    while resto and resto[0] in "#b":
        n += 1 if resto[0] == "#" else -1
        resto = resto[1:]
    return 12 * (int(resto) + 1) + n


def nombre(t): return f"{SOSTENIDOS[t % 12]}{t // 12 - 1} ({SOLFEO[t % 12]})"


def _n(s):
    """Sin mayúsculas ni acentos («Dón» = «don»), pero sin perder lo que no es latino («テト» sigue siendo «テト»)."""
    s = "".join(ch for ch in unicodedata.normalize("NFKD", str(s)) if not unicodedata.combining(ch))
    return unicodedata.normalize("NFKC", s).lower().strip()


# Kana → romaji (Hepburn) para comparar letras japonesas escritas de cualquiera de las dos formas: «か» = «ka»
_KANA = dict(zip("あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽぁぃぅぇぉゔ",
                 "a i u e o ka ki ku ke ko sa shi su se so ta chi tsu te to na ni nu ne no ha hi fu he ho ma mi mu me mo ya yu yo "
                 "ra ri ru re ro wa o n ga gi gu ge go za ji zu ze zo da ji zu de do ba bi bu be bo pa pi pu pe po a i u e o vu".split()))
_YOON = {"ゃ": "a", "ゅ": "u", "ょ": "o"}


def kana_a_romaji(s):
    s = "".join(chr(ord(ch) - 0x60) if "ァ" <= ch <= "ヶ" else ch for ch in str(s))     # katakana → hiragana
    out, i = "", 0
    while i < len(s):
        ch = s[i]
        if ch in _YOON and out and out[-1] == "i":                 # きゃ → kya, しゃ → sha
            out = out[:-1] + ("" if out[-2:-1] in ("h", "j") else "y") + _YOON[ch]
        elif ch == "っ" and i + 1 < len(s) and s[i + 1] in _KANA: out += "t" if _KANA[s[i + 1]].startswith("ch") else _KANA[s[i + 1]][0]
        elif ch == "ー" and out: out += out[-1]
        else: out += _KANA.get(ch, ch)
        i += 1
    return out


def _letra(s): return _n(kana_a_romaji(str(s).lstrip("+")))     # «+» alarga la sílaba anterior en OpenUtau


def _lista(v): return [v] if isinstance(v, str) else list(v or [])


def validar(q, donde):
    """Lanza ValueError si el «ustx» está mal escrito."""
    if not q.get("archivo"): raise ValueError(f"{donde}: «ustx» necesita «archivo» (p. ej. \"mis_proyectos/estrellita.ustx\")")
    raras = set(q) - CLAVES
    if raras: raise ValueError(f"{donde}: «ustx» no conoce {', '.join(sorted(raras))}")
    for k in ("notas",):
        for a in _lista(q.get(k)):
            try: tono(a)
            except Exception: raise ValueError(f"{donde}: «{a}» no es una nota (C4, F#4, Bb3…)")
    if q.get("ritmo") and q.get("notas") and len(q["ritmo"]) != len(q["notas"]): raise ValueError(f"{donde}: «ritmo» y «notas» tienen distinto largo")
    if q.get("letras") and q.get("notas") and len(q["letras"]) != len(q["notas"]): raise ValueError(f"{donde}: «letras» y «notas» tienen distinto largo")
    if q.get("transponer") not in (None, False, True, "octava"): raise ValueError(f"{donde}: «transponer» es false, \"octava\" o true")


def _ruta(q, base):
    r = Path(q["archivo"])
    if not r.is_absolute(): r = Path(base or ".") / r
    if any(ch in str(r) for ch in "*?["):
        hay = sorted(glob.glob(str(r)), key=os.path.getmtime)
        return Path(hay[-1]) if hay else None
    return r if r.is_file() else None


def leer(ruta):
    """El proyecto: {"bpm", "pistas": [{"cantante", "fonemizador", "notas": [{"tono", "pos", "dur", "letra", "vibrato", "pitch"}], "curvas": {abbr: [ys]}}], "audio": n, "res"}."""
    d = yaml.safe_load(Path(ruta).read_text(encoding="utf-8-sig"))   # OpenUtau guarda con BOM
    res = d.get("resolution", 480)
    pistas = [{"cantante": t.get("singer") or "", "fonemizador": t.get("phonemizer") or "", "notas": [], "curvas": {}} for t in d.get("tracks") or []]
    for p in d.get("voice_parts") or []:
        if p.get("track_no", 0) >= len(pistas): continue
        pista = pistas[p["track_no"]]
        for n in p.get("notes") or []:
            pista["notas"].append({"tono": n["tone"], "pos": p.get("position", 0) + n["position"], "dur": n["duration"], "letra": n.get("lyric", ""),
                                   "vibrato": (n.get("vibrato") or {}).get("length", 0) > 0,
                                   "pitch": any(abs(pt.get("y", 0)) > 0.01 for pt in (n.get("pitch") or {}).get("data") or [])})
        for c in p.get("curves") or []:
            pista["curvas"].setdefault(c.get("abbr"), []).extend(c.get("ys") or [])
    for pista in pistas: pista["notas"].sort(key=lambda n: n["pos"])
    tempos = d.get("tempos") or [{"bpm": d.get("bpm", 120)}]
    return {"bpm": tempos[0]["bpm"], "pistas": pistas, "audio": len(d.get("wave_parts") or []), "res": res}


def revisar(q, base=None):
    """(ok, detalle) de un {"tipo": "ustx", ...}."""
    base = base or q.get("_base")
    ruta = _ruta(q, base)
    if not ruta: return False, f"no encuentro «{q['archivo']}»: guarda el proyecto con ese nombre (Archivo → Guardar como)"
    if yaml is None: return False, "falta la librería pyyaml para leer proyectos de OpenUtau (python -m pip install pyyaml)"
    try: pr = leer(ruta)
    except Exception as e: return False, f"no pude leer «{ruta.name}» ({e.__class__.__name__}); ¿lo guardaste desde OpenUtau?"
    if "bpm" in q:
        lo, hi = (q["bpm"], q["bpm"]) if not isinstance(q["bpm"], list) else q["bpm"]
        if not lo - 0.01 <= pr["bpm"] <= hi + 0.01:
            return False, f"el tempo está en {pr['bpm']:g} BPM y va en {lo:g}" + (f" a {hi:g}" if hi != lo else "")
    if q.get("audio") and not pr["audio"]: return False, "no hay pista de audio: importa el instrumental (Proyecto → Importar audio)"
    con_notas = [p for p in pr["pistas"] if p["notas"]]
    if q.get("pistas_voz") and len(con_notas) < q["pistas_voz"]: return False, f"hay {len(con_notas)} pista(s) con notas y van {q['pistas_voz']}"
    # La pista que se revisa
    if q.get("pista"):
        i = q["pista"] - 1
        if i >= len(pr["pistas"]): return False, f"no hay pista {q['pista']}"
        pista = pr["pistas"][i]
    else:
        quiere = [_n(c) for c in _lista(q.get("cantante"))]
        cand = [p for p in pr["pistas"] if not quiere or any(c in _n(p["cantante"]) for c in quiere)]
        pista = next((p for p in cand if p["notas"]), cand[0] if cand else None)
        if pista is None:
            cantantes = ", ".join(p["cantante"] or "ninguno" for p in pr["pistas"]) or "ninguno"
            return False, f"ninguna pista canta con {' o '.join(_lista(q['cantante']))} (ahora: {cantantes})"
    if q.get("cantante") and not any(_n(c) in _n(pista["cantante"]) for c in _lista(q["cantante"])):
        return False, f"la pista canta con «{pista['cantante'] or 'ningún cantante'}» y va con {' o '.join(_lista(q['cantante']))}"
    if q.get("fonemizador") and not any(_n(f) in _n(pista["fonemizador"]) for f in _lista(q["fonemizador"])):
        fon = pista["fonemizador"].rsplit(".", 1)[-1].replace("Phonemizer", "") or "ninguno"
        return False, f"el fonemizador es {fon} y va {' o '.join(_lista(q['fonemizador']))}"
    notas = pista["notas"]
    if q.get("min_notas") and len(notas) < q["min_notas"]: return False, f"la pista tiene {len(notas)} nota(s) y van al menos {q['min_notas']}"
    largo = max(len(q.get("notas") or []), len(q.get("ritmo") or []), len(q.get("letras") or []))
    if largo and len(notas) < largo: return False, f"hay {len(notas)} nota(s) y van {largo}"
    if q.get("notas"):
        quiere = [tono(a) for a in q["notas"]]
        tiene = [n["tono"] for n in notas[:len(quiere)]]
        corr = tiene[0] - quiere[0] if q.get("transponer") else 0
        if q.get("transponer") == "octava" and corr % 12: corr = 0
        for i, (t, w) in enumerate(zip(tiene, quiere)):
            if t != w + corr:
                return False, f"la nota {i + 1} está en {nombre(t)} y va en {nombre(w + corr)}"
    if q.get("ritmo"):
        for i, (n, b) in enumerate(zip(notas, q["ritmo"])):
            if abs(n["dur"] / pr["res"] - b) > 1 / 16:
                return False, f"la nota {i + 1} dura {n['dur'] / pr['res']:g} tiempo(s) y va de {b:g}"
        for i in range(1, len(q["ritmo"])):
            fin = notas[i - 1]["pos"] + notas[i - 1]["dur"]
            if notas[i]["pos"] - fin > pr["res"] / 16: return False, f"hay un hueco entre la nota {i} y la {i + 1}"
            if fin - notas[i]["pos"] > pr["res"] / 16: return False, f"la nota {i} se monta sobre la {i + 1}"
    if q.get("letras"):
        for i, (n, l) in enumerate(zip(notas, q["letras"])):
            if _letra(n["letra"]) != _letra(l):
                return False, f"la letra de la nota {i + 1} es «{n['letra']}» y va «{l}»"
    if q.get("vibrato"):
        con = sum(n["vibrato"] for n in notas)
        if con < q["vibrato"]: return False, f"hay {con} nota(s) con vibrato y van al menos {q['vibrato']}"
    if q.get("pitch") and not (any(n["pitch"] for n in notas) or any(abs(y) > 0 for y in pista["curvas"].get("pitd", []))):
        return False, "no hay ninguna curva de tono editada"
    if q.get("curva") and not any(abs(y) > 0 for y in pista["curvas"].get(q["curva"], [])):
        return False, f"la curva {q['curva'].upper()} está sin dibujar"
    return True, ""


def probar():
    gen = Path(__file__).resolve().parent.parent / "openutau"          # el generador de proyectos del curso de OpenUtau
    if not (gen / "hacer_ustx.py").exists():
        print("ℹ no está openutau/hacer_ustx.py (el curso de ejemplo): pruebas omitidas"); return
    sys.path.insert(0, str(gen))
    from hacer_ustx import hacer, ESTRELLITA, AITZU_LUNA, ES_VCCV, TETO, JA_PRESAMP
    bien = 0
    def ver(c, txt):
        nonlocal bien
        print(("✔ " if c else "✘ ") + txt); bien += bool(c)
        if not c: raise SystemExit(1)
    with tempfile.TemporaryDirectory() as d:
        notas = [n[0] for n in ESTRELLITA[:7]]; ritmo = [n[1] for n in ESTRELLITA[:7]]; letras = [n[2] for n in ESTRELLITA[:7]]
        q = {"tipo": "ustx", "archivo": "e.ustx", "cantante": "Aitzu", "fonemizador": "SpanishVCCV", "bpm": 100,
             "notas": notas, "ritmo": ritmo, "letras": letras}
        validar(q, "prueba")
        hacer(Path(d) / "e.ustx", 100, [{"cantante": AITZU_LUNA, "fonemizador": ES_VCCV, "notas": ESTRELLITA}])
        ver(revisar(q, d) == (True, ""), "Estrellita bien hecha → bien")
        ok, m = revisar(dict(q, archivo="no.ustx"), d); ver(not ok and "no encuentro" in m, "sin guardar → " + m)
        mal = list(ESTRELLITA); mal[2] = ("F4", 1, "lli")
        hacer(Path(d) / "e.ustx", 100, [{"cantante": AITZU_LUNA, "fonemizador": ES_VCCV, "notas": mal}])
        ok, m = revisar(q, d); ver(not ok and "nota 3" in m and "F4 (fa)" in m and "G4 (sol)" in m, "una nota corrida → " + m)
        alto = [(n[0][:-1] + str(int(n[0][-1]) + 1), n[1], n[2]) for n in ESTRELLITA]
        hacer(Path(d) / "e.ustx", 100, [{"cantante": AITZU_LUNA, "fonemizador": ES_VCCV, "notas": alto}])
        ok, m = revisar(q, d); ver(not ok and "nota 1" in m, "una octava arriba, exacta → " + m)
        ver(revisar(dict(q, transponer="octava"), d)[0], "una octava arriba con «transponer»: \"octava\" → bien")
        largo = list(ESTRELLITA); largo[6] = ("G4", 1, "es")
        hacer(Path(d) / "e.ustx", 100, [{"cantante": AITZU_LUNA, "fonemizador": ES_VCCV, "notas": largo}])
        ok, m = revisar(q, d); ver(not ok and "nota 7 dura 1" in m, "nota larga corta → " + m)
        hueco = list(ESTRELLITA); hueco.insert(3, (None, 1, ""))
        hacer(Path(d) / "e.ustx", 100, [{"cantante": AITZU_LUNA, "fonemizador": ES_VCCV, "notas": hueco}])
        ok, m = revisar(q, d); ver(not ok and "hueco entre la nota 3 y la 4" in m, "silencio de más → " + m)
        letra = list(ESTRELLITA); letra[1] = ("C4", 1, "tr")
        hacer(Path(d) / "e.ustx", 100, [{"cantante": AITZU_LUNA, "fonemizador": ES_VCCV, "notas": letra}])
        ok, m = revisar(q, d); ver(not ok and "nota 2" in m and "«tre»" in m, "sílaba mal → " + m)
        hacer(Path(d) / "e.ustx", 120, [{"cantante": AITZU_LUNA, "fonemizador": ES_VCCV, "notas": ESTRELLITA}])
        ok, m = revisar(q, d); ver(not ok and "120 BPM" in m, "otro tempo → " + m)
        hacer(Path(d) / "e.ustx", 100, [{"cantante": TETO, "fonemizador": JA_PRESAMP, "notas": ESTRELLITA}])
        ok, m = revisar(q, d); ver(not ok and "ninguna pista canta con Aitzu" in m, "otro cantante → " + m)
        vib = [n + (240,) if i == 6 else n for i, n in enumerate(ESTRELLITA)]
        hacer(Path(d) / "e.ustx", 100, [{"cantante": AITZU_LUNA, "fonemizador": ES_VCCV, "notas": vib}], audio=[{"archivo": "fondo.wav"}])
        ver(revisar({"tipo": "ustx", "archivo": "*.ustx", "vibrato": 1, "audio": True}, d)[0], "vibrato y audio, con comodín → bien")
        ok, m = revisar({"tipo": "ustx", "archivo": "e.ustx", "pitch": True}, d); ver(not ok and "curva de tono" in m, "sin pitch → " + m)
        kaeru = [("C4", 1, "か"), ("D4", 1, "え"), ("E4", 1, "る"), ("F4", 1, "の"), ("E4", 1, "う"), ("D4", 1, "た"), ("C4", 2, "が")]
        hacer(Path(d) / "k.ustx", 100, [{"cantante": TETO, "fonemizador": JA_PRESAMP, "notas": kaeru}])
        qk = {"tipo": "ustx", "archivo": "k.ustx", "cantante": "テト", "letras": ["ka", "e", "ru", "no", "u", "ta", "ga"]}
        ver(revisar(qk, d) == (True, ""), "letra en hiragana, pedida en romaji; Teto por «テト» → bien")
        ok, m = revisar(dict(qk, letras=["ka", "e", "ru", "no", "u", "ta", "ka"]), d); ver(not ok and "nota 7" in m, "«が» no es «ka» → " + m)
        ver(kana_a_romaji("きゃしゅっちょー") == "kyashutchoo" and kana_a_romaji("テト") == "teto", "kana → romaji (yōon, っ, ー, katakana)")
        try: validar({"tipo": "ustx", "archivo": "x", "notas": ["H4"]}, "prueba"); ver(False, "nota rara")
        except ValueError as e: ver("H4" in str(e), "«H4» no es una nota → error al cargar")
    print(f"ustx: todo bien ({bien})")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--probar" in sys.argv: probar()
