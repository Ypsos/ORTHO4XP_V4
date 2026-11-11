# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2024-2026 Roland (Ypsos)
#
# CRÉDIT — AUTEUR : Roland (Ypsos) — Novembre 2026
# Module conçu et spécifié par Roland (Ypsos) pour Ortho4XP V3.
# Cette notice d'auteur et de copyright doit être conservée
# conformément à la GPLv3.
# ============================================================
# Copyright (c) 2024-2026 Roland (Ypsos)
#
# CREDIT — AUTHOR: Roland (Ypsos) — November 2026
# Module designed and specified by Roland (Ypsos) for Ortho4XP V3.
# This authorship and copyright notice must be retained
# in accordance with GPLv3.
# ============================================================
"""
O4_Airport_Search_Utils.py — Recherche d'un aéroport ou d'une ville,
HORS LIGNE, à partir du fichier apt.dat de X-Plane 12.

MODULE AUTONOME (100 % additif, LECTURE SEULE sur X-Plane) :
  - lit Global Scenery/Global Airports/Earth nav data/apt.dat (jamais modifié) ;
  - fabrique UNE FOIS un petit index (code OACI, nom, ville, pays, position)
    dans <Ortho4XP>/.airport_index.json ; il est refait seul si apt.dat change
    (mise à jour de X-Plane) ;
  - aucun accès réseau, aucun service extérieur.

La recherche de ville passe par la ville des aéroports (champ « city »
de apt.dat) : taper « Nantes » trouve LFRS Nantes Atlantique, etc.

POINTS D'ENTRÉE :
  find_apt_dat()                       -> chemin de apt.dat ou ""
  load_or_build_index(progress=None)   -> liste d'aéroports (dict)
  search(query, index, limit=20)       -> meilleurs résultats
"""

import json
import os
import re
import unicodedata

INDEX_NAME = ".airport_index.json"
INDEX_VERSION = 2


def _root_dir():
    try:
        import O4_File_Names as FNAMES
        return FNAMES.Ortho4XP_dir
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def index_path():
    return os.path.join(_root_dir(), INDEX_NAME)


# ------------------------------------------------------------------------------
# Où est X-Plane ? (aucun chemin en dur : déduit des réglages existants)
# ------------------------------------------------------------------------------
def xplane_root_candidates():
    """Racines X-Plane possibles, déduites de scenery_packs.ini (Bibliothèque
    de tuiles) et du dossier overlay (custom_overlay_src)."""
    out = []
    try:
        import O4_Tile_Library_Utils as TL
        ini = TL.guess_ini_path()
        if ini:
            out.append(os.path.dirname(os.path.dirname(ini)))
    except Exception:
        pass
    for modname in ("O4_Overlay_Utils", "O4_Config_Utils"):
        try:
            mod = __import__(modname)
            src = getattr(mod, "custom_overlay_src", "") or ""
            if src:
                # .../X-Plane 12/Global Scenery/X-Plane 12 Global Scenery
                out.append(os.path.dirname(os.path.dirname(
                    os.path.abspath(src.rstrip("/\\")))))
        except Exception:
            pass
    seen, res = set(), []
    for p in out:
        if p and p not in seen and os.path.isdir(p):
            seen.add(p)
            res.append(p)
    return res


def find_apt_dat(roots=None):
    for root in (roots if roots is not None else xplane_root_candidates()):
        p = os.path.join(root, "Global Scenery", "Global Airports",
                         "Earth nav data", "apt.dat")
        if os.path.isfile(p):
            return p
    return ""


# ------------------------------------------------------------------------------
# Lecture de apt.dat (PUR sur un flux de lignes : testable)
# ------------------------------------------------------------------------------
_HEADERS = (b"1", b"16", b"17")   # aéroport terrestre / hydrobase / héliport


import math


def _rwy_len_m(p):
    """Longueur (m) d'une piste de ligne 100 (deux extrémités lat/lon)."""
    try:
        la1, lo1, la2, lo2 = float(p[9]), float(p[10]), float(p[18]), float(p[19])
    except Exception:
        return 0
    dy = (la2 - la1) * 111320.0
    dx = (lo2 - lo1) * 111320.0 * math.cos(math.radians((la1 + la2) / 2.0))
    return int(math.hypot(dx, dy))


def _f(x):
    try:
        return float(x)
    except Exception:
        return None


def parse_apt_lines(lines):
    """PUR. lines = itérable de lignes bytes. Renvoie la liste des aéroports :
    {id, icao, name, city, country, lat, lon, kind}."""
    out = []
    cur = None

    def _close(a):
        if a is None:
            return
        if a.get("lat") is None and a.get("_rlat") is not None:
            a["lat"], a["lon"] = a["_rlat"], a["_rlon"]
        a.pop("_rlat", None)
        a.pop("_rlon", None)
        if a.get("lat") is not None and a.get("lon") is not None:
            out.append(a)

    for raw in lines:
        if not raw or raw[:1] in (b"\n", b"\r"):
            continue
        sp = raw.split(None, 1)
        if not sp:
            continue
        code = sp[0]
        if code in _HEADERS:
            _close(cur)
            parts = raw.split(None, 5)
            if len(parts) < 5:
                cur = None
                continue
            ident = parts[4].decode("utf-8", "replace")
            name = parts[5].decode("utf-8", "replace").strip() \
                if len(parts) > 5 else ""
            cur = {"id": ident, "icao": "", "name": name, "city": "",
                   "country": "", "lat": None, "lon": None,
                   "kind": {b"1": "A", b"16": "S", b"17": "H"}[code],
                   "_rlat": None, "_rlon": None, "rwy": 0}
            continue
        if cur is None:
            continue
        if code == b"1302":
            kv = raw.split(None, 2)
            if len(kv) < 3:
                continue
            key = kv[1]
            val = kv[2].decode("utf-8", "replace").strip()
            if key == b"icao_code":
                cur["icao"] = val
            elif key == b"city":
                cur["city"] = val
            elif key == b"country":
                cur["country"] = val
            elif key == b"datum_lat":
                cur["lat"] = _f(val)
            elif key == b"datum_lon":
                cur["lon"] = _f(val)
        elif code == b"100":
            p = raw.split()
            if len(p) > 10 and cur["_rlat"] is None:
                cur["_rlat"], cur["_rlon"] = _f(p[9]), _f(p[10])
            if len(p) > 19:
                cur["rwy"] = max(cur["rwy"], _rwy_len_m(p))
        elif cur["_rlat"] is None:
            if code == b"101":
                p = raw.split()
                if len(p) > 5:
                    cur["_rlat"], cur["_rlon"] = _f(p[4]), _f(p[5])
            elif code == b"102":
                p = raw.split()
                if len(p) > 3:
                    cur["_rlat"], cur["_rlon"] = _f(p[2]), _f(p[3])
    _close(cur)
    return out


def build_index(apt_path, out_path=None, progress=None):
    """Lit apt.dat (lecture seule) et écrit l'index. progress(fraction)
    est appelé de temps en temps. Renvoie la liste."""
    out_path = out_path or index_path()
    size = max(1, os.path.getsize(apt_path))
    state = {"n": 0}

    def _lines():
        with open(apt_path, "rb") as f:
            for ln in f:
                state["n"] += len(ln)
                if progress is not None and (state["n"] & 0xFFFFF) < len(ln):
                    try:
                        progress(min(1.0, state["n"] / float(size)))
                    except Exception:
                        pass
                yield ln

    airports = parse_apt_lines(_lines())
    st = os.stat(apt_path)
    data = {"version": INDEX_VERSION, "source": apt_path,
            "size": st.st_size, "mtime": int(st.st_mtime),
            "airports": [[a["id"], a["icao"], a["name"], a["city"],
                          a["country"], round(a["lat"], 5), round(a["lon"], 5),
                          a["kind"], a.get("rwy", 0)] for a in airports]}
    try:
        tmp = out_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
        os.replace(tmp, out_path)
    except Exception:
        pass
    return airports


def _from_json(data):
    return [{"id": r[0], "icao": r[1], "name": r[2], "city": r[3],
             "country": r[4], "lat": r[5], "lon": r[6], "kind": r[7],
             "rwy": r[8] if len(r) > 8 else 0}
            for r in data.get("airports", [])]


def load_index(apt_path=None, path=None):
    """Index en cache s'il correspond toujours à apt.dat, sinon None."""
    path = path or index_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return None
    if data.get("version") != INDEX_VERSION:
        return None
    if apt_path:
        try:
            st = os.stat(apt_path)
            if data.get("size") != st.st_size or \
                    data.get("mtime") != int(st.st_mtime):
                return None
        except Exception:
            pass
    return _from_json(data)


def load_or_build_index(progress=None, apt_path=None):
    apt = apt_path or find_apt_dat()
    idx = load_index(apt or None)
    if idx is not None:
        return idx
    if not apt:
        return []
    return build_index(apt, progress=progress)


# ------------------------------------------------------------------------------
# Recherche (PURE)
# ------------------------------------------------------------------------------
_TRANSLIT = {"ø": "o", "Ø": "o", "æ": "ae", "Æ": "ae", "œ": "oe", "Œ": "oe",
             "ß": "ss", "ł": "l", "Ł": "l", "đ": "d", "Đ": "d", "þ": "th",
             "ð": "d", "ı": "i"}


def norm(text):
    """Minuscules, sans accents ni ponctuation (« Saint-Étienne » ->
    « saint etienne », « Rørvik » -> « rorvik »)."""
    t = "".join(_TRANSLIT.get(c, c) for c in (text or ""))
    t = unicodedata.normalize("NFKD", t)
    t = "".join(c for c in t if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def search(query, index, limit=20):
    """Classement : code exact > code qui commence par > ville/nom exacts >
    commence par > contient (tous les mots). Aéroports avant héliports."""
    q = norm(query)
    if not q or not index:
        return []
    words = q.split()
    qcode = q.replace(" ", "").upper()
    scored = []
    for a in index:
        codes = {a["id"].upper(), (a.get("icao") or "").upper()}
        codes.discard("")
        city_raw = a.get("city", "") or ""
        city = norm(city_raw)
        city_parts = [norm(c) for c in city_raw.split("/")]
        name = norm(a.get("name", ""))
        hay = city + " " + name
        if qcode in codes:
            s = 0
        elif any(c.startswith(qcode) for c in codes) and len(qcode) >= 2:
            s = 1
        elif q == city or q == name or q in city_parts:
            s = 2
        elif city.startswith(q) or name.startswith(q):
            s = 3
        elif all(w in hay for w in words):
            s = 4
        else:
            continue
        kind_pen = 0 if a.get("kind") == "A" else 1
        # vrai code OACI (4 lettres) avant les codes locaux
        icao_pen = 0 if re.match(r"^[A-Z]{4}$", (a.get("icao") or a["id"]).upper()) else 1
        # à score égal : les plus grandes pistes d'abord (grands aéroports)
        scored.append((s, kind_pen, icao_pen, -int(a.get("rwy", 0) or 0),
                       a["id"], a))
    scored.sort(key=lambda t: t[:5])
    return [t[5] for t in scored[:limit]]


def label(a):
    """Libellé court pour une liste : « LFEY  Île d'Yeu (L'Île-d'Yeu) »."""
    code = a.get("icao") or a["id"]
    txt = "%-5s %s" % (code, a.get("name", ""))
    if a.get("city") and norm(a["city"]) not in norm(a.get("name", "")):
        txt += " (" + a["city"] + ")"
    return txt
