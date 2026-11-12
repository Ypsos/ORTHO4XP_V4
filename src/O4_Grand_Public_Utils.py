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
O4_Grand_Public_Utils.py — Interface « Grand public » (débutant) avec carte.

MODULE AUTONOME (100 % additif) :
  - n'est importé par aucun fichier existant tant qu'on ne le raccorde pas ;
  - ne modifie AUCUN fichier existant ; aucun nouveau moteur : il appelle
    les fonctions déjà validées (CFG.Tile, TILE.build_all, OVL.build_overlay,
    O4_Estimation_Utils, O4_Mount_Check_Utils, O4_Diagnostics_Utils) ;
  - la fenêtre principale (interface Expert) reste strictement inchangée.

PARCOURS EN 4 ÉTAPES (inspiré de la simplicité d'OrthoStudio XP, sans son
code) :
  1. Choisir ses tuiles sur une carte du monde (clic = choisir/retirer,
     glisser = déplacer la carte). Champ « Aller à » : une tuile (+46-003),
     une position (46.7, -2.3), ou un aéroport / une ville (LFEY, Nantes),
     recherche HORS LIGNE dans apt.dat de X-Plane (O4_Airport_Search_Utils).
     Les tuiles déjà construites sont en vert.
  2. Choisir une qualité : Rapide / Équilibrée / Haute. Ce sont EXACTEMENT
     les 3 profils validés du Point 4 (même valeurs que le simulateur).
  3. Vérifier : résumé (tuiles, source d'imagerie, qualité, dossier,
     estimation disque/durée, disques accessibles, machine, et alerte si la
     qualité des textures de X-Plane est sous le maximum).
  4. Construire : enchaîne pour chaque tuile la même séquence que
     « Tout construire » (TILE.build_all), puis l'overlay si demandé.
     Progression en langage courant, bouton Arrêter.

OPTIONS (novembre 2026) :
  - File d'attente : « Construire » pendant une construction ajoute les
    nouvelles tuiles choisies à la suite. Seules les tuiles dont toutes les
    images ont été obtenues sont installées dans X-Plane (journal : « could
    not be obtained ») ; les autres sont signalées avec la marche à suivre.
  - Plusieurs tuiles en même temps (machine ≥ 8 cœurs et 16 Go : 2 ; ≥ 12
    cœurs et 32 Go : 3) : étapes 1 à 2.5 une tuile après l'autre, puis
    étape 3 de chaque tuile dans son propre processus (O4_Build_Worker.py),
    journal dans <dossier tuile>/Ortho4XP_mode_simple_etape3.log.
  - Vitesse : plusieurs images téléchargées en même temps (max_download_slots
    = 3, ou 2 si moins de 12 Go de mémoire) et conversions DDS selon les
    cœurs (max_convert_slots) ; réglages relevés pendant la construction,
    jamais abaissés, rétablis à la fin.
  - Pendant la construction, l'ordinateur ne se met pas en veille ; à la
    fin, son + notification ; durée estimée d'après les vraies durées
    passées ; « Aperçu » de la tuile (basse résolution) avant construction ;
    après construction, proposition (Oui/Non) d'effacer les images
    téléchargées — via O4_Build_Comfort_Utils.
  - Carte : zoom 25 % / 50 % / 100 % / 200 % (boutons ＋ / － sur la carte ou
    molette ; une étape par geste) ; seuls les morceaux visibles sont chargés.
  - Source des images « automatique » : par tuile, la source combinée de la
    fenêtre expert si c'en est une (.comb), sinon la source qui apporte le
    plus d'imagerie nationale sur la tuile (source simple dont l'emprise
    couvre toute la tuile, ou source combinée qui couvre toute la tuile ;
    emprises lues par IMG.has_data ; à égalité : note du Scoring, puis
    max_zl), sinon la source de la fenêtre expert. Choix par défaut : la
    source de la fenêtre expert ; « automatique » se coche à la main. Le résumé « Vérifier » affiche le choix pour chaque tuile.
  - Tuile déjà à jour : après une construction réussie, les réglages de la
    tuile sont notés dans <dossier tuile>/.grand_public_build.json ; une
    tuile dont les réglages n'ont pas changé (et dont le DSF et les textures
    sont là) n'est pas refaite, sauf case « Refaire aussi les tuiles déjà à
    jour ».
  - Installation dans X-Plane à la fin (case cochée par défaut) et bouton
    « Installer / réinstaller » : lien dans Custom Scenery + ligne activée
    dans scenery_packs.ini, copie .bak (O4_Scenery_Installer_Utils).

RÈGLES DE CONSTRUCTION (identiques au mode Expert) :
  - la tuile part des réglages globaux, puis de SON .cfg s'il existe
    (custom_dem, zones ZL… sont donc respectés) ;
  - par-dessus : la source d'imagerie de la fenêtre principale et les
    5 réglages du profil de qualité choisi ;
  - mesh_zl est relevé si besoin au ZL le plus haut utilisé (même règle que
    la fenêtre des zones ZL : évite les triangles dans X-Plane) ;
  - le .cfg de la tuile est complété au début (même méthode que l'Expert).

Lancé par le lanceur « Création de tuiles mode simple » (variable
O4X_START_MODE=simple) : la fenêtre expert est cachée ; un bouton « Passer
en mode expert » la fait réapparaître ; fermer la fenêtre simple quitte
Ortho4XP (même fermeture que la fenêtre expert, exit_prg). Ouvert depuis le
menu Outils : la fenêtre expert reste visible, rien ne change.

Langue : sélecteur 🌐 Français / English en haut de la fenêtre ; le choix
est enregistré dans Ortho4XP.cfg (O4_Lang._write_lang_to_cfg) puis Ortho4XP
redémarre seul dans le même mode.

Rappel de licence : affiché UNE SEULE FOIS (case « Ne plus afficher »),
mémorisé dans un petit fichier privé .grand_public_licence_ok (Ortho4XP.cfg
n'est pas touché).

POINT D'ENTRÉE (à raccorder plus tard) : run_grand_public(parent=None)
"""

import math
import os
import re
import sys
import threading
import time


# ------------------------------------------------------------------------------
# Bilingue interne (ne touche pas aux fichiers O4_Lang_*)
# ------------------------------------------------------------------------------
def _lang_code():
    for modname, attr in (("O4_Lang", "_current_lang"),
                          ("O4_UI_Utils", "lang")):
        try:
            mod = __import__(modname)
            code = getattr(mod, attr, None)
            if isinstance(code, str) and code:
                return code[:2].lower()
        except Exception:
            pass
    return "en"


def _L(fr, en):
    return fr if _lang_code() == "fr" else en


def _root_dir():
    try:
        import O4_File_Names as FNAMES
        return FNAMES.Ortho4XP_dir
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# ------------------------------------------------------------------------------
# CHAPITRE 1 — Cœur PUR (testable en headless)
# ------------------------------------------------------------------------------
# Les 3 profils validés (Point 4, O4_Simulator_Utils._PRESETS) : mêmes valeurs.
QUALITIES = {
    "fast": {
        "default_zl": 16, "limit_tris": 1, "iterate": 0,
        "cover_airports_with_highres": "False", "cover_zl": 17,
    },
    "balanced": {
        "default_zl": 17, "limit_tris": 2, "iterate": 1,
        "cover_airports_with_highres": "False", "cover_zl": 18,
    },
    "quality": {
        "default_zl": 18, "limit_tris": 3, "iterate": 2,
        "cover_airports_with_highres": "True", "cover_zl": 18,
    },
}
QUALITY_ORDER = ("fast", "balanced", "quality")
DEFAULT_QUALITY = "balanced"


# Netteté choisie à la main (optionnel), par-dessus le profil. Le profil
# reste le nom de base ; le choix est noté « base;zl=17;apt=19 ».
ZL_CHOICES = (16, 17, 18, 19)
APT_CHOICES = (18, 19, 20)


def parse_quality(spec):
    """PUR. « balanced;zl=17;apt=19 » -> ("balanced", 17, 19).
    zl / apt = None : valeur du profil ; apt = 0 : pas de netteté en plus."""
    parts = str(spec or "").split(";")
    base = parts[0] if parts[0] in QUALITIES else DEFAULT_QUALITY
    zl = apt = None
    for p in parts[1:]:
        k, _, v = p.partition("=")
        try:
            v = int(v)
        except Exception:
            continue
        if k == "zl" and v in ZL_CHOICES:
            zl = v
        elif k == "apt" and (v == 0 or v in APT_CHOICES):
            apt = v
    return (base, zl, apt)


def quality_spec(base, zl=None, apt=None, icao=False):
    """PUR. Inverse de parse_quality (+ « icao=1 » : seulement les aéroports
    avec un code OACI, réglage « ICAO » existant du moteur)."""
    s = base if base in QUALITIES else DEFAULT_QUALITY
    if zl in ZL_CHOICES:
        s += ";zl=%d" % zl
    if apt == 0 or apt in APT_CHOICES:
        s += ";apt=%d" % apt
    if icao:
        s += ";icao=1"
    return s


def quality_icao(spec):
    """PUR. Le choix « seulement les aéroports OACI » est-il demandé ?"""
    return "icao=1" in str(spec or "").split(";")[1:]


def quality_vals(spec):
    """PUR. Réglages moteur d'un choix de qualité (profil + netteté à la
    main). Profil seul : valeurs du profil, inchangées. Choix à la main :
    les aéroports ne passent plus nets que s'ils dépassent le paysage."""
    base, zl, apt = parse_quality(spec)
    vals = dict(QUALITIES[base])
    if zl is not None:
        vals["default_zl"] = zl
    if apt is not None:
        if apt == 0:
            vals["cover_airports_with_highres"] = "False"
        else:
            vals["cover_airports_with_highres"] = "True"
            vals["cover_zl"] = apt
    if (zl is not None or apt is not None) and \
            str(vals["cover_airports_with_highres"]) != "False" and \
            int(vals["cover_zl"]) <= int(vals["default_zl"]):
        vals["cover_airports_with_highres"] = "False"
    if quality_icao(spec) and \
            str(vals["cover_airports_with_highres"]) != "False":
        vals["cover_airports_with_highres"] = "ICAO"
    return vals


def zl_summary(spec):
    """PUR. « ZL17 · aéroports ZL19 » (ou « ZL17 » seul)."""
    v = quality_vals(spec)
    s = "ZL%d" % int(v["default_zl"])
    if str(v["cover_airports_with_highres"]) != "False":
        s += _L(" · aéroports ZL%d", " · airports ZL%d") % int(v["cover_zl"])
        if v["cover_airports_with_highres"] == "ICAO":
            s += _L(" (OACI seulement)", " (ICAO only)")
    return s


# Couleurs « comme la source / adoucies / très adoucies » : réglage de
# saturation EXISTANT de Color Normalize (CNORM.saturation_*, le même que le
# curseur « Saturation » de la fenêtre expert). Rien d'autre n'est changé.
COLOUR_CHOICES = ("source", "soft", "softer")
COLOUR_SAT = {"soft": 0.85, "softer": 0.67}


def colour_label(c):
    return {"source": _L("comme la source", "as the source"),
            "soft": _L("adoucies", "toned down"),
            "softer": _L("très adoucies", "toned down a lot")}.get(c, c)


def cnorm_snapshot():
    """Réglages couleur actuels (Color Normalize), ou None si absent."""
    try:
        import O4_Color_Normalize as CN
        return {"enabled": bool(CN.color_normalization_enabled),
                "strength": float(CN.CORRECTION_STRENGTH),
                "sat_on": bool(CN.saturation_enabled),
                "sat": float(CN.saturation_strength)}
    except Exception:
        return None


def cnorm_apply(snap):
    """Remet des réglages couleur (après une construction, ou dans le
    processus séparé de l'étape 3). Sans effet si snap est None."""
    if not snap:
        return False
    try:
        import O4_Color_Normalize as CN
        CN.color_normalization_enabled = bool(snap["enabled"])
        CN.CORRECTION_STRENGTH = float(snap["strength"])
        CN.saturation_enabled = bool(snap["sat_on"])
        CN.saturation_strength = float(snap["sat"])
        return True
    except Exception:
        return False


def cnorm_for_colour(colour, base):
    """PUR. Réglages couleur à utiliser : ceux de la fenêtre expert (base),
    avec la saturation du choix « adoucies » si demandé."""
    if not base:
        return None
    snap = dict(base)
    if colour in COLOUR_SAT:
        snap["sat_on"] = True
        snap["sat"] = COLOUR_SAT[colour]
    return snap


def colour_preview(img, colour):
    """Image « avec vos couleurs » (même opération que le moteur :
    ImageEnhance.Color). Indicatif : l'aperçu est en basse résolution."""
    if colour not in COLOUR_SAT:
        return img
    from PIL import ImageEnhance
    return ImageEnhance.Color(img.convert("RGB")).enhance(COLOUR_SAT[colour])


_PROFILES_FILE = ".grand_public_profiles.json"
PROFILE_KEYS = ("quality", "src", "colour", "overlay", "install")


def profiles_path():
    return os.path.join(_root_dir(), _PROFILES_FILE)


def load_profiles(path=None):
    """{nom: réglages}. Fichier absent ou abîmé -> {}."""
    import json
    try:
        with open(path or profiles_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d, dict):
            return {}
        out = {}
        for k, v in d.items():
            if isinstance(k, str) and isinstance(v, dict):
                out[k[:40]] = {kk: v[kk] for kk in PROFILE_KEYS if kk in v}
        return out
    except Exception:
        return {}


def save_profiles(profiles, path=None):
    import json
    p = path or profiles_path()
    try:
        tmp = p + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(profiles, f, ensure_ascii=False, indent=1,
                      sort_keys=True)
        os.replace(tmp, p)
        return True
    except Exception:
        return False


def quality_label(q):
    q = parse_quality(q)[0] if ";" in str(q) else q
    return {
        "fast": _L("🐇  Rapide", "🐇  Fast"),
        "balanced": _L("⚖  Équilibrée (conseillée)", "⚖  Balanced (advised)"),
        "quality": _L("💎  Haute", "💎  High"),
    }.get(q, q)


def quality_help(q):
    q = parse_quality(q)[0] if ";" in str(q) else q
    return {
        "fast": _L("Netteté standard. Construction la plus courte et la plus "
                   "légère.",
                   "Standard sharpness. Shortest and lightest build."),
        "balanced": _L("Bonne netteté, bon compromis temps / place disque.",
                       "Good sharpness, good time / disk compromise."),
        "quality": _L("Très net, aéroports encore plus nets. Plus long et "
                      "beaucoup plus lourd.",
                      "Very sharp, airports even sharper. Longer and much "
                      "heavier."),
    }.get(q, "")


def short_latlon(lat, lon):
    """PUR. Même format que FNAMES.short_latlon : +46-003."""
    return "%+03d%+04d" % (lat, lon)


def tile_of_point(lat, lon):
    """PUR. Tuile 1°×1° qui contient le point (coin sud-ouest)."""
    return (int(math.floor(lat)), int(math.floor(lon)))


def valid_tile(lat, lon):
    return -85 <= lat <= 84 and -180 <= lon <= 179


_GOTO_TILE = re.compile(r"^\s*([+-]\d{1,2})\s*([+-]\d{1,3})\s*$")
_GOTO_NUM = re.compile(
    r"^\s*([+-]?\d+(?:[.,]\d+)?)\s*[;, ]\s*([+-]?\d+(?:[.,]\d+)?)\s*$")


_TILE_TOKEN = re.compile(r"([+-]\d{1,2})\s*([+-]\d{1,3})")


def parse_tile_list(text):
    """PUR. Plusieurs tuiles tapées d'un coup (« +43+005 +43+006,+44+005 »)
    -> liste de (lat, lon) valides, sans doublon, dans l'ordre. Une seule
    tuile, ou du texte qui n'est pas une liste de tuiles -> []."""
    if not text:
        return []
    parts = [p for p in re.split(r"[\s,;]+", text.strip()) if p]
    out = []
    for p in parts:
        m = _TILE_TOKEN.fullmatch(p)
        if not m:
            return []
        t = (int(m.group(1)), int(m.group(2)))
        if not valid_tile(*t):
            return []
        if t not in out:
            out.append(t)
    return out if len(out) >= 2 else []


def parse_goto(text):
    """PUR. « +46-003 », « 46 -3 », « 46.7, -2.35 » -> (lat, lon) du point,
    ou None. La longitude est la seconde valeur."""
    if not text:
        return None
    m = _GOTO_TILE.match(text)
    if m:
        lat, lon = int(m.group(1)), int(m.group(2))
        return (lat + 0.5, lon + 0.5) if valid_tile(lat, lon) else None
    m = _GOTO_NUM.match(text)
    if m:
        try:
            lat = float(m.group(1).replace(",", "."))
            lon = float(m.group(2).replace(",", "."))
        except ValueError:
            return None
        if -85 <= lat <= 85 and -180 <= lon <= 180:
            return (lat, lon)
    return None


# --- Projection de la carte (même formule que O4_Geo_Utils, ZL6) ---
MAP_ZL = 6
MAP_SIZE = 2 ** (MAP_ZL + 8)          # 16384 px
CHUNK = MAP_SIZE // 8                 # 2048 px par image Earth2_ZL6_x_y.jpg


def latlon_to_pix(lat, lon, zl=MAP_ZL):
    rat_x = lon / 180.0
    rat_y = math.log(math.tan((90 + lat) * math.pi / 360.0)) / math.pi
    return ((rat_x + 1) * (2 ** (zl + 7)), (1 - rat_y) * (2 ** (zl + 7)))


def pix_to_latlon(px, py, zl=MAP_ZL):
    rat_x = px / (2 ** (zl + 7)) - 1
    rat_y = 1 - py / (2 ** (zl + 7))
    lon = rat_x * 180.0
    lat = 360.0 / math.pi * math.atan(math.exp(math.pi * rat_y)) - 90
    return (lat, lon)


def tile_rect_pix(lat, lon):
    """PUR. Rectangle (x0, y0, x1, y1) de la tuile sur la carte."""
    x0, y0 = latlon_to_pix(lat + 1, lon)
    x1, y1 = latlon_to_pix(lat, lon + 1)
    return (x0, y0, x1, y1)


ZOOMS = (0.25, 0.5, 1.0, 2.0)          # 1.0 = images Earth à taille réelle
DEFAULT_ZOOM = 1.0


def next_zoom(z, direction):
    """PUR. Niveau de zoom voisin (direction +1 = agrandir, -1 = réduire)."""
    try:
        i = ZOOMS.index(z)
    except ValueError:
        i = ZOOMS.index(DEFAULT_ZOOM)
    return ZOOMS[max(0, min(len(ZOOMS) - 1, i + (1 if direction > 0 else -1)))]


def piece_src_size(zoom):
    """PUR. Taille (px source) d'un morceau d'image : 1 image Earth entière
    jusqu'au zoom 1, un quart d'image au-delà (morceau affiché ≤ 2048 px,
    mémoire limitée)."""
    return CHUNK if zoom <= 1.0 else CHUNK // 2


def pieces_for_view(x0, y0, x1, y1, zoom):
    """PUR. Morceaux visibles pour une vue en coordonnées ÉCRAN (déjà
    zoomées) : liste de (i, j) dans la grille de morceaux de taille
    piece_src_size(zoom) (coordonnées source = écran / zoom)."""
    s = piece_src_size(zoom)
    n = MAP_SIZE // s
    bx0, by0, bx1, by1 = x0 / zoom, y0 / zoom, x1 / zoom, y1 / zoom
    out = []
    for i in range(max(0, int(bx0 // s)), min(n - 1, int(bx1 // s)) + 1):
        for j in range(max(0, int(by0 // s)), min(n - 1, int(by1 // s)) + 1):
            out.append((i, j))
    return out


def piece_source(i, j, zoom):
    """PUR. Image Earth (nx, ny) et zone à découper (x0, y0, x1, y1) en px
    de cette image pour le morceau (i, j)."""
    s = piece_src_size(zoom)
    nx, ny = (i * s) // CHUNK, (j * s) // CHUNK
    cx, cy = i * s - nx * CHUNK, j * s - ny * CHUNK
    return (nx, ny), (cx, cy, cx + s, cy + s)


def chunks_for_view(x0, y0, x1, y1):
    """PUR. Indices (nx, ny) des images Earth visibles dans la vue."""
    out = []
    for nx in range(max(0, int(x0 // CHUNK)), min(7, int(x1 // CHUNK)) + 1):
        for ny in range(max(0, int(y0 // CHUNK)), min(7, int(y1 // CHUNK)) + 1):
            out.append((nx, ny))
    return out


def toggle(selection, tile):
    """PUR. Ajoute ou retire une tuile d'un ensemble ; renvoie True si
    ajoutée."""
    if tile in selection:
        selection.discard(tile)
        return False
    selection.add(tile)
    return True


def sorted_tiles(selection):
    """PUR. Ordre de construction : du nord au sud, d'ouest en est."""
    return sorted(selection, key=lambda t: (-t[0], t[1]))


_DIR_RE = re.compile(r"XP_([+-]\d{2})([+-]\d{3})")


def scan_built_tiles(working_dir, long_latlon=None):
    """Tuiles déjà construites dans working_dir (même règle que la fenêtre
    Expert « Tiles collection » : un dossier ...XP_+LL+LLL contenant
    Earth nav data/+LL+LLL.dsf). Lecture seule."""
    out = set()
    try:
        names = os.listdir(working_dir)
    except Exception:
        return out
    for name in names:
        m = _DIR_RE.search(name)
        if not m:
            continue
        lat, lon = int(m.group(1)), int(m.group(2))
        if long_latlon is None:
            dsf_name = "%+03d%+04d.dsf" % (lat, lon)
        else:
            dsf_name = long_latlon(lat, lon) + ".dsf"
        if os.path.isfile(os.path.join(working_dir, name, "Earth nav data",
                                       dsf_name)):
            out.add((lat, lon))
    return out


def built_tiles_map(dirs, long_latlon=None):
    """Tuiles déjà construites dans PLUSIEURS dossiers (même règle que
    scan_built_tiles) -> {(lat, lon): dossier de la tuile}. Le premier
    dossier de la liste qui contient la tuile est gardé. Lecture seule."""
    out = {}
    for wd in dirs:
        if not wd:
            continue
        try:
            names = sorted(os.listdir(wd))
        except Exception:
            continue
        for name in names:
            m = _DIR_RE.search(name)
            if not m:
                continue
            lat, lon = int(m.group(1)), int(m.group(2))
            if (lat, lon) in out:
                continue
            if long_latlon is None:
                dsf_name = "%+03d%+04d.dsf" % (lat, lon)
            else:
                dsf_name = long_latlon(lat, lon) + ".dsf"
            try:
                ok = os.path.isfile(os.path.join(wd, name, "Earth nav data",
                                                 dsf_name))
            except Exception:
                ok = False
            if ok:
                out[(lat, lon)] = os.path.join(wd, name)
    return out


def built_scan_dirs(cbd):
    """Dossiers où chercher les tuiles déjà construites, dans l'ordre :
    dossier de construction choisi (s'il n'est pas groupé), dossier Tiles
    d'Ortho4XP, puis « Custom Scenery » du X-Plane choisi. Sans doublon."""
    dirs = []
    try:
        if not is_grouped(cbd):
            dirs.append(working_dir(cbd))
    except Exception:
        pass
    try:
        import O4_File_Names as FNAMES
        dirs.append(FNAMES.Tile_dir)
    except Exception:
        dirs.append(os.path.join(_root_dir(), "Tiles"))
    try:
        root = xplane_root_of_ini(xplane_ini())
        if root:
            dirs.append(os.path.join(root, "Custom Scenery"))
    except Exception:
        pass
    out, seen = [], set()
    for d in dirs:
        if not d:
            continue
        try:
            k = os.path.normcase(os.path.realpath(d))
        except Exception:
            k = d
        if k in seen:
            continue
        seen.add(k)
        out.append(d)
    return out


def needed_mesh_zl(current_mesh_zl, quality_vals, zone_list):
    """PUR. ZL le plus haut réellement utilisé -> mesh_zl minimal (même règle
    que la fenêtre des zones ZL, §31)."""
    zls = [int(quality_vals.get("default_zl", 16))]
    if str(quality_vals.get("cover_airports_with_highres", "False")) != "False":
        zls.append(int(quality_vals.get("cover_zl", 18)))
    for z in (zone_list or []):
        try:
            zls.append(int(z[1]))
        except Exception:
            pass
    try:
        cur = int(current_mesh_zl)
    except Exception:
        cur = 19
    return max([cur] + zls)


def apply_quality(tile, quality, provider):
    """Applique le profil + la source d'imagerie à un objet tuile (sans rien
    écrire sur disque). Renvoie la tuile."""
    vals = quality_vals(quality)
    for key, v in vals.items():
        setattr(tile, key, v)
    if provider:
        tile.default_website = provider
    tile.mesh_zl = needed_mesh_zl(getattr(tile, "mesh_zl", 19), vals,
                                  getattr(tile, "zone_list", []))
    return tile


def is_in_custom_scenery(path):
    """PUR. Le dossier de construction est-il dans un « Custom Scenery » ?"""
    if not path:
        return False
    parts = os.path.abspath(path).replace("\\", "/").split("/")
    return "Custom Scenery" in parts


def fmt_duration(sec):
    sec = int(max(0, sec))
    h, m = sec // 3600, (sec % 3600) // 60
    if h:
        return "%dh%02d" % (h, m)
    if m:
        return "%d min" % m
    return "%d s" % sec


# ------------------------------------------------------------------------------
# Suivi de l'avancement (lecture seule du journal Ortho4XP.log)
# ------------------------------------------------------------------------------
# Les étapes du moteur, dans l'ordre (mêmes noms que dans le journal).
STEP_ORDER = ("1", "2", "2.1", "2.5", "3")
# Part de chaque étape dans la barre d'avancement de la tuile (début, fin, %).
STEP_SPAN = {"1": (0, 8), "2": (8, 15), "2.1": (15, 35), "2.5": (35, 45),
             "3": (45, 100)}
# Barre du moteur (UI.progress_bar) utilisée par chaque étape.
STEP_BAR = {"2.1": 2, "2.5": 2, "3": 3}

_RX_STEP_RUN = re.compile(r"Step (\d(?:\.\d)?) for tile lat= *(-?\d+) *, *"
                          r"lon= *(-?\d+) *: *(starting|normal exit)")
_RX_STEP_HEAD = re.compile(r"Step (\d(?:\.\d)?) :.*?([+-]\d{2}[+-]\d{3})")


def step_label(step):
    """Nom simple d'une étape, dans la langue de l'interface."""
    names = {"1": ("carte : routes, eau, aéroports",
                   "map: roads, water, airports"),
             "2": ("maillage 3D du relief", "3D terrain mesh"),
             "2.1": ("bords de mer", "coastline"),
             "2.5": ("masques d'eau", "water masks"),
             "3": ("images : téléchargement et conversion",
                   "imagery: download and conversion")}
    fr, en = names.get(step, (step, step))
    return _L(fr, en)


def parse_step_lines(lines, status=None):
    """PUR. Met à jour {tuile: {"step": "2.1", "done": False}} d'après les
    lignes du journal (seules les lignes « Step … » du moteur comptent)."""
    status = status if status is not None else {}
    for ln in lines:
        m = _RX_STEP_RUN.search(ln)
        if m:
            name = short_latlon(int(m.group(2)), int(m.group(3)))
            status[name] = {"step": m.group(1),
                            "done": m.group(4) == "normal exit"}
            continue
        m = _RX_STEP_HEAD.search(ln)
        if m and m.group(1) in STEP_SPAN:
            status[m.group(2)] = {"step": m.group(1), "done": False}
    return status


def step_progress(step, done, pct):
    """PUR. Avancement de la tuile en % (0-100) d'après l'étape en cours et,
    si connu, le % de cette étape."""
    a, b = STEP_SPAN.get(step, (0, 0))
    if done:
        return float(b)
    if pct is None:
        return float(a)
    pct = max(0.0, min(100.0, float(pct)))
    return a + (b - a) * pct / 100.0


def step_line(step, done, pct, remaining):
    """PUR. « Étape 3 / 5 : images … — 48 % — reste ~2 min »."""
    try:
        idx = STEP_ORDER.index(step) + 1
    except ValueError:
        return ""
    txt = _L("Étape %d / %d : %s", "Step %d / %d: %s") % (
        idx, len(STEP_ORDER), step_label(step))
    if done:
        return txt + _L(" — terminée", " — done")
    if pct is not None:
        txt += " — %d %%" % int(pct)
        if remaining is not None and remaining > 0:
            txt += _L(" — reste ~", " — left ~") + fmt_duration(remaining)
    return txt


def engine_bar_percent(nbr, now=None):
    """% en cours d'une barre du moteur (même processus) et temps restant
    estimé, lus dans le suivi existant de O4_UI_Utils (lecture seule).
    Renvoie (pct, reste_s) ou (None, None)."""
    try:
        import O4_UI_Utils as UI
        stt = dict(getattr(UI, "_eta_state", {}).get(nbr) or {})
    except Exception:
        return (None, None)
    if not stt:
        return (None, None)
    p = stt.get("last_p")
    if p is None:
        return (None, None)
    now = now if now is not None else time.time()
    rem = None
    try:
        el = now - stt["t0"]
        gained = p - stt["p0"]
        if el > 0 and gained > 0 and p >= 3:
            rem = (100 - p) / (gained / el)
    except Exception:
        rem = None
    return (p, rem)


def log_file_path():
    try:
        import O4_UI_Utils as UI
        return os.path.join(UI._LOG_ROOT, "Ortho4XP.log")
    except Exception:
        return os.path.join(_root_dir(), "Ortho4XP.log")


def read_new_log_lines(path, pos, max_bytes=262144):
    """Lignes ajoutées au journal depuis la position pos. Renvoie
    (lignes, nouvelle_position). Jamais d'erreur (fichier absent → [])."""
    try:
        size = os.path.getsize(path)
    except Exception:
        return ([], pos)
    if pos is None or size < pos:
        pos = size
    if size == pos:
        return ([], pos)
    start = max(pos, size - max_bytes)
    try:
        with open(path, "rb") as f:
            f.seek(start)
            data = f.read(size - start)
    except Exception:
        return ([], pos)
    cut = data.rfind(b"\n")
    if cut < 0:
        return ([], start)
    text = data[:cut + 1].decode("utf-8", "replace")
    return (text.splitlines(), start + cut + 1)


# --- Rappel de licence (une seule fois) ---
_LICENCE_FLAG = ".grand_public_licence_ok"


def licence_flag_path():
    return os.path.join(_root_dir(), _LICENCE_FLAG)


def licence_already_ok():
    try:
        return os.path.isfile(licence_flag_path())
    except Exception:
        return False


def set_licence_ok():
    try:
        with open(licence_flag_path(), "w", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S") + "\n")
        return True
    except Exception:
        return False


def licence_text():
    return _L(
        "Ortho4XP ne fournit aucune imagerie. Les sources proposées sont des "
        "services tiers, chacun soumis à sa propre licence.\n\n"
        "Les tuiles fabriquées sont destinées à un usage strictement "
        "personnel et ne doivent pas être diffusées.\n\n"
        "Il appartient à chaque utilisateur de vérifier et de respecter les "
        "conditions de la source qu'il utilise.\n\n"
        "La liste des sources est personnalisable (menu Outils → « Créer / "
        "modifier un provider (.lay) »).",
        "Ortho4XP provides no imagery. The listed sources are third-party "
        "services, each under its own licence.\n\n"
        "Tiles you build are for strictly personal use and must not be "
        "redistributed.\n\n"
        "Each user is responsible for checking and respecting the terms of "
        "the source they use.\n\n"
        "The source list can be customised (Tools menu → \"Create / edit a "
        "provider (.lay)\").")


# ------------------------------------------------------------------------------
# CHAPITRE 2 — Liaison avec l'existant (défensive, aucune modification)
# ------------------------------------------------------------------------------
def current_provider():
    """Source d'imagerie de la fenêtre principale, sinon globale, sinon BI."""
    try:
        import O4_UI_Utils as UI
        g = getattr(UI, "gui", None)
        if g is not None and hasattr(g, "default_website"):
            v = g.default_website.get()
            if v:
                return v
    except Exception:
        pass
    try:
        import O4_Config_Utils as CFG
        v = getattr(CFG, "default_website", "") or ""
        if v:
            return v
    except Exception:
        pass
    return "BI"


def current_build_dir():
    try:
        import O4_UI_Utils as UI
        g = getattr(UI, "gui", None)
        if g is not None and hasattr(g, "custom_build_dir"):
            return g.custom_build_dir.get() or ""
    except Exception:
        pass
    try:
        import O4_Config_Utils as CFG
        return getattr(CFG, "custom_build_dir", "") or ""
    except Exception:
        return ""


def working_dir(cbd):
    if cbd:
        return cbd
    try:
        import O4_File_Names as FNAMES
        return FNAMES.Tile_dir
    except Exception:
        return os.path.join(_root_dir(), "Tiles")


def is_grouped(cbd):
    return bool(cbd) and cbd[-1] not in ("/", "\\")


def overlay_source():
    """Dossier Global Scenery pour l'overlay (réglage existant), ou ""."""
    try:
        import O4_Overlay_Utils as OVL
        src = getattr(OVL, "custom_overlay_src", "") or ""
    except Exception:
        src = ""
    if src and os.path.isdir(os.path.join(src, "Earth nav data")):
        return src
    return ""


def make_tile(lat, lon, cbd, quality, provider):
    """Tuile prête à construire, comme l'Expert : globaux -> .cfg tuile s'il
    existe -> source + profil choisis par-dessus."""
    import O4_Config_Utils as CFG
    import O4_File_Names as FNAMES
    provider = resolve_provider(lat, lon, provider)
    tile = CFG.Tile(lat, lon, cbd)
    tile_cfg = os.path.join(tile.build_dir, "Ortho4XP_"
                            + FNAMES.short_latlon(lat, lon) + ".cfg")
    gen_cfg = os.path.join(tile.build_dir, "Ortho4XP.cfg")
    if os.path.isfile(tile_cfg) or os.path.isfile(gen_cfg):
        try:
            tile.read_from_config()
        except Exception:
            pass
    return apply_quality(tile, quality, provider)


def estimate_tiles(tiles, cbd, quality, provider):
    """Estimation par tuile via O4_Estimation_Utils (moteur réel).
    Renvoie (liste [(tile, est|None)], total_min_go, total_max_go,
    total_tmin_s, total_tmax_s)."""
    res = []
    gmin = gmax = tmin = tmax = 0.0
    try:
        import O4_Estimation_Utils as EST
    except Exception:
        EST = None
    for (lat, lon) in tiles:
        est = None
        if EST is not None:
            try:
                t = make_tile(lat, lon, cbd, quality, provider)
                est = EST.estimate(t)
            except Exception:
                est = None
        if est:
            gmin += est["disque_go_min"]; gmax += est["disque_go_max"]
            tmin += est["temps_s_min"]; tmax += est["temps_s_max"]
        res.append(((lat, lon), est))
    return res, gmin, gmax, tmin, tmax


def free_space_go(path):
    p = path or _root_dir()
    while p and not os.path.isdir(p):
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    try:
        import shutil
        return shutil.disk_usage(p or _root_dir()).free / 1024.0 ** 3
    except Exception:
        return None


def mount_check(tile):
    try:
        import O4_Mount_Check_Utils as MC
        return MC.check_paths_before_build(tile)
    except Exception:
        return (True, "")


# ------------------------------------------------------------------------------
# CHAPITRE 2b — Source d'imagerie automatique, tuile déjà à jour, installation
# ------------------------------------------------------------------------------
AUTO = "__auto__"          # « Automatique » : meilleure source par tuile
# Une source retenue doit couvrir TOUTE la tuile : une texture sans aucune
# donnée ferait échouer l'étape 3 (data_found=False). 0.999 = marge
# d'arrondi du masque de contrôle (128 × 128 points).
MIN_COVER = 0.999
_AUTO_CACHE = {}


def _img():
    try:
        import O4_Imagery_Utils as IMG
        return IMG
    except Exception:
        return None


def provider_scores(path=None):
    """Note moyenne /100 de chaque source mesurée par le Scoring
    (_score_exports/_score_log.json), ou {} si absent. Lecture seule."""
    import json
    p = path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "_score_exports", "_score_log.json")
    acc = {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        for e in (data if isinstance(data, list) else []):
            code, g = e.get("provider_code"), e.get("global_score")
            if code and isinstance(g, (int, float)):
                acc.setdefault(code, []).append(float(g))
    except Exception:
        return {}
    return {k: sum(v) / len(v) for k, v in acc.items()}


def _layer_mask(img, ext, lat, lon, size=128):
    """Masque (image « L ») de la partie de la tuile couverte par l'emprise
    `ext`, lu avec la fonction du moteur IMG.has_data ; "full" pour
    « global » ; None si l'emprise ne touche pas la tuile."""
    if ext == "global":
        return "full"
    code = ext[1:] if ext.startswith("!") else ext
    e = getattr(img, "extents_dict", {}).get(code)
    if not e or "mask_bounds" not in e:
        return None
    if not ext.startswith("!"):
        (xmin, ymin, xmax, ymax) = e["mask_bounds"]
        if lon >= xmax or lon + 1 <= xmin or lat >= ymax or lat + 1 <= ymin:
            return None
    try:
        m = img.has_data((lon, lat + 1, lon + 1, lat), ext, return_mask=True,
                         mask_size=(size, size))
    except Exception:
        return None
    if m is True:
        return "full"
    return m or None


def _fraction(mask):
    if mask == "full":
        return 1.0
    if mask is None:
        return 0.0
    try:
        data = list(mask.getdata())
        return sum(1 for v in data if v > 127) / float(len(data) or 1)
    except Exception:
        return 0.0


def _union(a, b):
    if a == "full" or b == "full":
        return "full"
    if a is None:
        return b
    if b is None:
        return a
    try:
        from PIL import ImageChops
        return ImageChops.lighter(a, b)
    except Exception:
        return a


def coverage(img, provider_code, lat, lon, size=128):
    """Part (0..1) de la tuile couverte par l'emprise déclarée dans le .lay
    de la source (« extent= »). Source sans emprise (« global ») = 1."""
    try:
        ext = img.providers_dict[provider_code].get("extent", "global")
    except Exception:
        return 0.0
    return _fraction(_layer_mask(img, ext, lat, lon, size))


def combo_coverage(img, comb_code, lat, lon, size=128):
    """Source combinée (.comb) : (part couverte par ses couches à emprise
    précise = sources nationales, part couverte au total y compris les
    couches « global » de remplissage)."""
    national = None
    total = None
    for layer in getattr(img, "combined_providers_dict", {}).get(comb_code,
                                                                 []):
        m = _layer_mask(img, layer.get("extent_code", "global"), lat, lon,
                        size)
        if m is None:
            continue
        total = _union(total, m)
        if layer.get("extent_code", "global") != "global":
            national = _union(national, m)
    return (_fraction(national), _fraction(total))


def candidate_providers(img, lat, lon, scores=None, min_cover=MIN_COVER):
    """Sources qui apportent de l'imagerie NATIONALE (emprise précise) sur la
    tuile, de la meilleure à la moins bonne. [(code, part_nationale)].
      - source simple affichée dans la liste, avec « extent= » dans son .lay,
        qui couvre toute la tuile ;
      - source combinée (.comb) qui couvre TOUTE la tuile (ses couches
        « global » comblent le reste) avec une partie nationale.
    Classement : part nationale, puis note du Scoring, puis max_zl, puis
    nom."""
    scores = scores or {}
    out = []
    for code, prov in sorted(getattr(img, "providers_dict", {}).items()):
        try:
            if not prov.get("in_GUI", True):
                continue
            if prov.get("extent", "global") == "global":
                continue
            if prov.get("request_type") == "local_tms":
                continue
        except Exception:
            continue
        c = coverage(img, code, lat, lon)
        if c >= min_cover:
            out.append((code, c))
    for code in sorted(getattr(img, "combined_providers_dict", {})):
        nat, tot = combo_coverage(img, code, lat, lon)
        if tot >= min_cover and nat > 0.0:
            out.append((code, nat))

    def _key(item):
        code = item[0]
        try:
            mz = int(img.providers_dict.get(code, {}).get("max_zl", 0))
        except Exception:
            mz = 0
        return (-round(item[1], 2), -scores.get(code, -1.0), -mz, code)

    return sorted(out, key=_key)


def best_provider(lat, lon, fallback, img=None, scores=None):
    """Source retenue pour une tuile en mode « Automatique » :
      - la source de la fenêtre principale si c'est une source COMBINÉE
        (.comb : déjà prévue pour mélanger les meilleures sources) ;
      - sinon la source qui apporte le plus d'imagerie nationale sur la
        tuile (source simple à emprise, ou source combinée .comb) ;
      - sinon la source de la fenêtre principale.
    Renvoie (code, raison) avec raison dans {"comb", "national", "defaut"}."""
    img = img if img is not None else _img()
    if img is None:
        return (fallback, "defaut")
    if fallback in getattr(img, "combined_providers_dict", {}):
        return (fallback, "comb")
    key = (lat, lon, fallback)
    if key in _AUTO_CACHE:
        return _AUTO_CACHE[key]
    cands = candidate_providers(img, lat, lon, scores
                                if scores is not None else provider_scores())
    res = (cands[0][0], "national") if cands else (fallback, "defaut")
    _AUTO_CACHE[key] = res
    return res


def resolve_provider(lat, lon, provider):
    if provider == AUTO:
        return best_provider(lat, lon, current_provider())[0]
    return provider


FP_NAME = ".grand_public_build.json"


def tile_fingerprint(tile):
    """PUR. Réglages qui décident du contenu de la tuile (tous les réglages
    tuile du moteur : CFG.list_tile_vars, dont source, ZL, zones, DEM)."""
    try:
        import O4_Config_Utils as CFG
        keys = list(CFG.list_tile_vars)
    except Exception:
        keys = []
    for k in ("default_website", "default_zl", "zone_list", "mesh_zl"):
        if k not in keys:
            keys.append(k)
    return {k: repr(getattr(tile, k, None)) for k in sorted(keys)}


def _dsf_path(tile):
    try:
        import O4_File_Names as FNAMES
        name = FNAMES.long_latlon(tile.lat, tile.lon) + ".dsf"
    except Exception:
        name = short_latlon(tile.lat, tile.lon) + ".dsf"
    return os.path.join(tile.build_dir, "Earth nav data", name)


def is_up_to_date(tile):
    """La tuile a déjà été construite par le mode simple avec exactement les
    mêmes réglages, et son DSF + ses textures sont toujours là."""
    import json
    fp = os.path.join(tile.build_dir, FP_NAME)
    dsf = _dsf_path(tile)
    try:
        if not (os.path.isfile(fp) and os.path.isfile(dsf)):
            return False
        with open(fp, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if saved != tile_fingerprint(tile):
            return False
        if os.path.getmtime(dsf) > os.path.getmtime(fp) + 1:
            return False        # refaite entre-temps par l'Expert
        tex = os.path.join(tile.build_dir, "textures")
        return any(n.endswith(".dds") for n in os.listdir(tex))
    except Exception:
        return False


def save_fingerprint(tile, fingerprint=None):
    """Écrit l'empreinte (celle calculée AVANT la construction si fournie :
    le moteur peut compléter l'objet tuile pendant la construction)."""
    import json
    try:
        with open(os.path.join(tile.build_dir, FP_NAME), "w",
                  encoding="utf-8") as f:
            json.dump(fingerprint or tile_fingerprint(tile), f, indent=1,
                      sort_keys=True)
        return True
    except Exception:
        return False


def install_in_xplane(build_dirs):
    """Installe / réinstalle des tuiles construites dans X-Plane (lien dans
    Custom Scenery + ligne activée dans scenery_packs.ini, copie .bak), via
    O4_Scenery_Installer_Utils. Renvoie [(nom, ok, message)]."""
    try:
        import O4_Scenery_Installer_Utils as SI
    except Exception as e:
        return [("", False, str(e))]
    dirs = []
    for d in build_dirs:
        if d and d not in dirs:
            dirs.append(d)
    if not dirs:
        return []
    try:
        return SI.install_tiles(dirs)
    except Exception as e:
        return [("", False, str(e))]


def xplane_ini():
    """scenery_packs.ini du X-Plane utilisé (même choix mémorisé que la
    Bibliothèque de tuiles). "" si inconnu."""
    try:
        import O4_Scenery_Installer_Utils as SI
        return SI.find_ini() or ""
    except Exception:
        return ""


def xplane_root_of_ini(ini):
    """PUR. Dossier X-Plane d'après …/X-Plane 12/Custom Scenery/
    scenery_packs.ini ("" si le chemin ne suit pas ce modèle)."""
    if not ini:
        return ""
    cs = os.path.dirname(os.path.normpath(ini))
    if os.path.basename(cs) != "Custom Scenery":
        return ""
    return os.path.dirname(cs)


def valid_ini_choice(path):
    """PUR (sauf existence du fichier). Vrai si c'est bien le
    scenery_packs.ini d'un dossier « Custom Scenery »."""
    return (bool(path) and os.path.basename(path) == "scenery_packs.ini"
            and bool(xplane_root_of_ini(path)) and os.path.isfile(path))


def remember_xplane_ini(path):
    """Mémorise le X-Plane choisi (même fichier que la Bibliothèque de
    tuiles : un seul choix pour tout Ortho4XP)."""
    try:
        import O4_Tile_Library_Utils as TL
        return bool(TL.save_ini_path(path))
    except Exception:
        return False


def install_report_text(report):
    """PUR. Compte rendu lisible de install_in_xplane."""
    ok = [n + " (" + m + ")" for (n, k, m) in report if k]
    ko = [(n + " : " if n else "") + str(m) for (n, k, m) in report if not k]
    out = ""
    if ok:
        out += _L("📥 Dans X-Plane : ", "📥 In X-Plane: ") + ", ".join(ok)
        root = xplane_root_of_ini(xplane_ini())
        if root:
            out += _L("\n   X-Plane utilisé : ", "\n   X-Plane used: ") + root
        out += _L("\n   (relancez X-Plane s'il est ouvert)",
                  "\n   (restart X-Plane if it is open)")
    if ko:
        out += ("\n" if out else "") + _L("⚠ Installation impossible : ",
                                          "⚠ Installation impossible: ")
        out += " ; ".join(ko)
    return out


def _comfort():
    try:
        import O4_Build_Comfort_Utils as BC
        return BC
    except Exception:
        return None


def suggested_convert_slots(cpu, current):
    """PUR. Conversions JPG → DDS en parallèle pour le mode simple : on garde
    2 cœurs libres, au plus 8 (limite du réglage moteur max_convert_slots),
    et on ne descend JAMAIS sous le réglage de l'utilisateur."""
    try:
        cur = int(current)
    except Exception:
        cur = 4
    if not cpu:
        return cur
    return max(cur, min(8, int(cpu) - 2))


def total_ram_go():
    """Mémoire vive totale en Go, ou None."""
    try:
        import psutil
        return psutil.virtual_memory().total / 1024.0 ** 3
    except Exception:
        pass
    try:
        return (os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
                / 1024.0 ** 3)
    except Exception:
        return None


def suggested_download_slots(ram_go, current):
    """PUR. Images téléchargées en même temps en mode simple : 3 (2 si moins
    de 12 Go de mémoire ou mémoire inconnue) ; jamais moins que le réglage
    de l'utilisateur (max_download_slots), jamais plus de 8."""
    try:
        cur = int(current)
    except Exception:
        cur = 1
    target = 3 if (ram_go and ram_go >= 12) else 2
    return min(8, max(cur, target))


def history_time(total_textures):
    """(min_s, max_s, n) d'après les vraies durées passées, ou None."""
    BC = _comfort()
    if BC is None or not total_textures:
        return None
    try:
        return BC.estimate_seconds(total_textures)
    except Exception:
        return None


PREVIEW_ZL = 12


def preview_source(lat, lon, provider, img=None):
    """Source à utiliser pour l'aperçu : la source elle-même si elle est
    simple ; pour une source combinée (.comb), sa couche qui couvre le plus
    la tuile (l'aperçu du moteur ne sait lire qu'une source simple).
    Renvoie (code, note) ; code vide si aucun aperçu possible."""
    img = img if img is not None else _img()
    if img is None:
        return ("", _L("Aperçu indisponible.", "Preview unavailable."))
    if provider in getattr(img, "providers_dict", {}):
        return (provider, "")
    layers = getattr(img, "combined_providers_dict", {}).get(provider)
    if not layers:
        return ("", _L("Aperçu indisponible pour la source %s." % provider,
                       "Preview unavailable for source %s." % provider))
    best, best_f = "", -1.0
    for layer in layers:
        code = layer.get("layer_code", "")
        if code not in img.providers_dict:
            continue
        f = _fraction(_layer_mask(img, layer.get("extent_code", "global"),
                                  lat, lon))
        if layer.get("extent_code", "global") == "global":
            f = min(f, 0.5)     # une couche nationale passe avant le fond
        if f > best_f:
            best, best_f = code, f
    if not best:
        return ("", _L("Aperçu indisponible pour la source %s." % provider,
                       "Preview unavailable for source %s." % provider))
    return (best, _L("Source combinée %s : aperçu de sa couche principale "
                     "sur cette tuile (%s)." % (provider, best),
                     "Combined source %s: preview of its main layer on this "
                     "tile (%s)." % (provider, best)))


def log_path():
    try:
        import O4_UI_Utils as UI
        root = getattr(UI, "_LOG_ROOT", "") or _root_dir()
    except Exception:
        root = _root_dir()
    return os.path.join(root, "Ortho4XP.log")


def log_size(path=None):
    try:
        return os.path.getsize(path or log_path())
    except Exception:
        return 0


_RX_MISSING = re.compile(r"Part of image\s+(\S+\.jpg)\s+could not be obtained")


def missing_pieces_since(offset, path=None):
    """Noms des images dont une partie n'a pas pu être téléchargée (remplie
    de blanc), d'après les lignes du journal écrites depuis `offset`."""
    out = []
    try:
        with open(path or log_path(), "rb") as f:
            f.seek(max(0, int(offset)))
            data = f.read().decode("utf-8", "replace")
    except Exception:
        return out
    for m in _RX_MISSING.finditer(data):
        name = os.path.basename(m.group(1))
        if name not in out:
            out.append(name)
    return out


def suggested_parallel_tiles(cpu, ram_go, n_tiles):
    """PUR. Nombre de tuiles construites EN MÊME TEMPS (étape 3, un processus
    par tuile) : 1 tant qu'il n'y a qu'une tuile ou une petite machine ;
    2 avec 8 cœurs et 16 Go ; 3 avec 12 cœurs et 32 Go."""
    try:
        n = int(n_tiles)
    except Exception:
        n = 1
    if n < 2 or not cpu or not ram_go:
        return 1
    if cpu >= 12 and ram_go >= 32:
        k = 3
    elif cpu >= 8 and ram_go >= 16:
        k = 2
    else:
        k = 1
    return max(1, min(k, n))


def prepare_tile_steps(tile):
    """Étapes 1, 2, 2.1 et 2.5 d'une tuile, exactement comme TILE.build_all
    (même ordre, mêmes contrôles), SANS l'étape 3. Renvoie 1 / 0."""
    import O4_UI_Utils as UI
    import O4_Vector_Map as VMAP
    import O4_Mesh_Utils as MESH
    import O4_Mask_Utils as MASK
    import O4_Tile_Utils as TILE
    for step in (VMAP.build_poly_file, MESH.build_mesh,
                 TILE.build_sea_patches, MASK.build_masks):
        step(tile)
        if UI.red_flag:
            try:
                UI.exit_message_and_bottom_line("")
            except Exception:
                pass
            return 0
    UI.is_working = 0
    return 1


WORKER_LOG = "Ortho4XP_mode_simple_etape3.log"


def worker_command(params, python=None):
    """PUR. Commande qui lance l'étape 3 d'une tuile dans un processus
    séparé (O4_Build_Worker.py, même Python que Ortho4XP)."""
    import json
    worker = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "O4_Build_Worker.py")
    return [python or sys.executable, worker,
            json.dumps(params, sort_keys=True)]


class BuildRunner(object):
    """Construit une liste de tuiles dans UN thread de travail (comme les
    boutons de l'Expert). L'interface lit self.state toutes les 0,5 s : aucun
    appel Tk depuis le thread."""

    def __init__(self, tiles, cbd, quality, provider, do_overlay,
                 force=False, install=False, parallel=1, popen=None,
                 colour="source"):
        self.tiles = list(tiles)
        self.cbd = cbd
        self.quality = quality
        self.provider = provider
        self.do_overlay = do_overlay
        self.force = force
        self.install = install
        self.parallel = max(1, int(parallel or 1))
        self._popen = popen
        self.colour = colour if colour in COLOUR_CHOICES else "source"
        self._started = set()
        self._cnorm = None
        self.stop_asked = False
        self.state = {"running": False, "k": 0, "n": len(self.tiles),
                      "current": "", "ok": [], "failed": [], "skipped": [],
                      "sources": {}, "built_dirs": [], "install": [],
                      "incomplete": {}, "t0": None, "done": False,
                      "message": ""}
        self._lock = threading.Lock()

    def remove_tiles(self, tiles):
        """File d'attente : retire des tuiles PAS ENCORE commencées. Renvoie
        la liste des tuiles retirées (une tuile commencée n'est jamais
        retirée : « Arrêter » sert à l'interrompre)."""
        removed = []
        with self._lock:
            for t in tiles:
                if t in self.tiles and t not in self._started:
                    self.tiles.remove(t)
                    removed.append(t)
            self.state["n"] = len(self.tiles)
        return removed

    def pending_tiles(self):
        with self._lock:
            return [t for t in self.tiles if t not in self._started]

    def add_tiles(self, tiles):
        """File d'attente : ajoute des tuiles pendant la construction (elles
        partent à la suite). Renvoie la liste des tuiles réellement
        ajoutées (une tuile déjà prévue n'est jamais ajoutée deux fois)."""
        added = []
        with self._lock:
            for t in tiles:
                if t not in self.tiles:
                    self.tiles.append(t)
                    added.append(t)
            self.state["n"] = len(self.tiles)
        return added

    def start(self):
        try:
            import O4_UI_Utils as UI
            if getattr(UI, "is_working", False):
                self.state["message"] = _L(
                    "Une construction est déjà en cours.",
                    "A build is already running.")
                self.state["done"] = True
                return False
        except Exception:
            pass
        self.state["running"] = True
        self.state["t0"] = time.time()
        # Suivi de l'avancement : on ne lira que la suite du journal.
        try:
            self.state["log_pos"] = os.path.getsize(log_file_path())
        except Exception:
            self.state["log_pos"] = None
        self.state["steps"] = {}
        th = threading.Thread(target=self._run, daemon=True)
        th.start()
        return True

    def stop(self):
        self.stop_asked = True
        try:
            import O4_UI_Utils as UI
            UI.red_flag = True     # même effet que le bouton « Red flag »
        except Exception:
            pass

    def _run(self):
        try:
            import O4_UI_Utils as UI
            import O4_Tile_Utils as TILE
        except Exception as e:
            self.state["message"] = str(e)
            self.state["running"] = False
            self.state["done"] = True
            return
        g = getattr(UI, "gui", None)
        BC = _comfort()
        awake = None
        if BC is not None:
            try:
                awake = BC.KeepAwake()
                self.state["keep_awake"] = awake.start()
            except Exception:
                awake = None
        # Vitesse : plus de conversions DDS en parallèle sur les machines à
        # nombreux cœurs (réglage moteur existant, rétabli à la fin).
        slots_before = getattr(TILE, "max_convert_slots", None)
        dl_before = getattr(TILE, "max_download_slots", None)
        try:
            if slots_before is not None:
                TILE.max_convert_slots = suggested_convert_slots(
                    os.cpu_count(), slots_before)
                self.state["convert_slots"] = TILE.max_convert_slots
            if dl_before is not None:
                TILE.max_download_slots = suggested_download_slots(
                    total_ram_go(), dl_before)
                self.state["download_slots"] = TILE.max_download_slots
        except Exception:
            pass
        # Couleurs : réglages de la fenêtre expert, « adoucies » par-dessus
        # pour CETTE construction ; remis tels quels à la fin.
        cn_before = cnorm_snapshot()
        self._cnorm = cnorm_for_colour(self.colour, cn_before)
        if self.colour != "source":
            cnorm_apply(self._cnorm)
        try:
            if self.parallel > 1:
                self._loop_parallel(UI, TILE, g, BC)
            else:
                self._loop(UI, TILE, g, BC)
        finally:
            if self.colour != "source":
                cnorm_apply(cn_before)
            if awake is not None:
                awake.stop()
            if slots_before is not None:
                try:
                    TILE.max_convert_slots = slots_before
                except Exception:
                    pass
            if dl_before is not None:
                try:
                    TILE.max_download_slots = dl_before
                except Exception:
                    pass
        if self.install and self.state["built_dirs"] and not self.stop_asked:
            self.state["current"] = _L("installation dans X-Plane",
                                       "installing into X-Plane")
            self.state["install"] = install_in_xplane(self.state["built_dirs"])
        if BC is not None and not self.stop_asked:
            try:
                ko = len(self.state["failed"])
                BC.notify("Ortho4XP V4",
                          _L("Construction terminée", "Build finished")
                          + (_L(" — %d échec(s)" % ko, " — %d failure(s)" % ko)
                             if ko else " ✅"))
            except Exception:
                pass
        self.state["running"] = False
        self.state["done"] = True

    # ---------------- construction de plusieurs tuiles en même temps --------
    def _loop_parallel(self, UI, TILE, g, BC):
        """Étapes 1 à 2.5 une tuile après l'autre ici ; étape 3 de chaque
        tuile prête dans son propre processus (au plus self.parallel à la
        fois). Pendant qu'une tuile fait son étape 3, la suivante se
        prépare."""
        import subprocess
        popen = self._popen or subprocess.Popen
        ram = total_ram_go()
        per_dl = 2
        per_conv = max(2, suggested_convert_slots(os.cpu_count(), 4)
                       // self.parallel)
        running = {}
        ready = []
        k = 0
        self.state["phase3"] = []
        while True:
            self._reap(running, UI)
            if self.stop_asked:
                for name, job in list(running.items()):
                    self._kill(job)
                    self.state["failed"].append(name)
                    running.pop(name, None)
                break
            while ready and len(running) < self.parallel:
                name, tile, fp = ready.pop(0)
                job = self._launch(popen, name, tile, fp, per_dl, per_conv)
                if job is None:
                    self.state["failed"].append(name)
                else:
                    running[name] = job
            self.state["phase3"] = sorted(running)
            with self._lock:
                has_next = k < len(self.tiles)
                if has_next:
                    (lat, lon) = self.tiles[k]
                    self._started.add((lat, lon))
            if has_next:
                k += 1
                item = self._prepare(lat, lon, UI, g)
                if item is not None:
                    ready.append(item)
                continue
            if not ready and not running:
                break
            time.sleep(1.0)
        self.state["phase3"] = []
        self.state["current"] = ""
        _ = ram

    def _prepare(self, lat, lon, UI, g):
        name = short_latlon(lat, lon)
        self.state["current"] = name
        tile = None
        try:
            tile = make_tile(lat, lon, self.cbd, self.quality, self.provider)
            self.state["sources"][name] = getattr(tile, "default_website", "")
            fp = tile_fingerprint(tile)
            if not self.force and is_up_to_date(tile):
                self.state["skipped"].append(name)
                if tile.build_dir not in self.state["built_dirs"]:
                    self.state["built_dirs"].append(tile.build_dir)
                self.state["k"] += 1
                return None
            if g is not None and hasattr(g, "_ensure_tile_cfg_complete"):
                try:
                    g._ensure_tile_cfg_complete(tile)
                except Exception:
                    pass
            UI.red_flag = False
            ok = bool(prepare_tile_steps(tile)) and not UI.red_flag
        except Exception as e:
            try:
                UI.vprint(0, "   [Grand public] " + name + " : " + str(e))
            except Exception:
                pass
            ok = False
        finally:
            try:
                UI.is_working = False
                if not self.stop_asked:
                    UI.red_flag = False
            except Exception:
                pass
        if not ok:
            self.state["failed"].append(name)
            self.state["k"] += 1
            return None
        return (name, tile, fp)

    def _launch(self, popen, name, tile, fp, per_dl, per_conv):
        params = {"lat": tile.lat, "lon": tile.lon, "cbd": self.cbd,
                  "quality": self.quality,
                  "provider": getattr(tile, "default_website", ""),
                  "download_slots": per_dl, "convert_slots": per_conv}
        if self._cnorm:
            params["cnorm"] = self._cnorm
        log = os.path.join(tile.build_dir, WORKER_LOG)
        try:
            fh = open(log, "w", encoding="utf-8")
        except Exception:
            return None
        kw = {"stdout": fh, "stderr": -2,   # -2 = subprocess.STDOUT
              "cwd": _root_dir()}
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUNBUFFERED"] = "1"
        kw["env"] = env
        if sys.platform.startswith("win"):
            kw["creationflags"] = 0x08000000      # CREATE_NO_WINDOW
        try:
            proc = popen(worker_command(params), **kw)
        except Exception as e:
            fh.close()
            try:
                import O4_UI_Utils as UI
                UI.vprint(0, "   [Grand public] " + name + " : " + str(e))
            except Exception:
                pass
            return None
        return {"proc": proc, "tile": tile, "fp": fp, "log": log, "fh": fh}

    def _kill(self, job):
        try:
            job["proc"].terminate()
            try:
                job["proc"].wait(timeout=15)
            except Exception:
                job["proc"].kill()
        except Exception:
            pass
        try:
            job["fh"].close()
        except Exception:
            pass

    def _reap(self, running, UI):
        for name, job in list(running.items()):
            rc = job["proc"].poll()
            if rc is None:
                continue
            running.pop(name, None)
            try:
                job["fh"].close()
            except Exception:
                pass
            ok = (rc == 0)
            self.state["k"] += 1
            if not ok:
                self.state["failed"].append(name)
                continue
            tile = job["tile"]
            save_fingerprint(tile, job["fp"])
            self.state["ok"].append(name)
            miss = missing_pieces_since(0, job["log"])
            if miss:
                self.state["incomplete"][name] = miss
            elif tile.build_dir not in self.state["built_dirs"]:
                self.state["built_dirs"].append(tile.build_dir)
            if self.do_overlay and not self.stop_asked:
                try:
                    import O4_Overlay_Utils as OVL
                    OVL.build_overlay(tile.lat, tile.lon)
                except Exception:
                    pass
                try:
                    UI.is_working = False
                    UI.red_flag = False
                except Exception:
                    pass

    def _loop(self, UI, TILE, g, BC):
        k = 0
        while True:
            with self._lock:
                if k >= len(self.tiles):
                    break
                (lat, lon) = self.tiles[k]
                self._started.add((lat, lon))
            k += 1
            if self.stop_asked:
                break
            name = short_latlon(lat, lon)
            self.state["k"] = k
            self.state["current"] = name
            ok = False
            skipped = False
            try:
                tile = make_tile(lat, lon, self.cbd, self.quality,
                                 self.provider)
                self.state["sources"][name] = getattr(tile, "default_website",
                                                      "")
                fp_before = tile_fingerprint(tile)
                if not self.force and is_up_to_date(tile):
                    skipped = True
                    ok = True
                    UI.vprint(0, "   [Grand public] " + name + " : "
                              + _L("déjà à jour, non reconstruite.",
                                   "already up to date, not rebuilt."))
                    raise StopIteration
                # Même complétion du .cfg tuile que l'Expert au Step 1
                if g is not None and hasattr(g, "_ensure_tile_cfg_complete"):
                    try:
                        g._ensure_tile_cfg_complete(tile)
                    except Exception:
                        pass
                n_tex = 0
                try:
                    import O4_Estimation_Utils as EST
                    n_tex = int(EST.estimate(tile)["total_textures"])
                except Exception:
                    n_tex = 0
                UI.red_flag = False
                t_start = time.time()
                log_off = log_size()
                ok = bool(TILE.build_all(tile)) and not UI.red_flag
                if ok:
                    miss = missing_pieces_since(log_off)
                    if miss:
                        self.state["incomplete"][name] = miss
                if ok:
                    save_fingerprint(tile, fp_before)
                    if BC is not None and n_tex:
                        BC.record_build(name, n_tex, time.time() - t_start,
                                        self.quality)
                if ok and self.do_overlay and not self.stop_asked:
                    try:
                        import O4_Overlay_Utils as OVL
                        OVL.build_overlay(lat, lon)
                    except Exception:
                        pass
            except StopIteration:
                pass
            except Exception as e:
                try:
                    UI.vprint(0, "   [Grand public] " + name + " : " + str(e))
                except Exception:
                    pass
                ok = False
            finally:
                try:
                    UI.is_working = False
                except Exception:
                    pass
            if skipped:
                self.state["skipped"].append(name)
            else:
                (self.state["ok"] if ok else self.state["failed"]).append(name)
            if ok and name not in self.state["incomplete"]:
                # Seules les tuiles complètes sont installées dans X-Plane.
                try:
                    if tile.build_dir not in self.state["built_dirs"]:
                        self.state["built_dirs"].append(tile.build_dir)
                except Exception:
                    pass
            try:
                UI.red_flag = False
            except Exception:
                pass


# ------------------------------------------------------------------------------
# CHAPITRE 3 — Fenêtre. Point d'entrée : run_grand_public(parent)
# Import tkinter LOCAL (le module reste importable sans interface).
# ------------------------------------------------------------------------------
def _show_licence_once(tk, win, colors, btn_factory, FONT, on_ok):
    """Affiche le rappel de licence si pas encore accepté avec « Ne plus
    afficher ». on_ok() est appelé quand l'utilisateur clique OK."""
    if licence_already_ok():
        on_ok()
        return
    BG, FG = colors
    dlg = tk.Toplevel(win)
    dlg.title(_L("À lire avant de commencer", "Please read before starting"))
    dlg.configure(bg=BG)
    tk.Label(dlg, text=licence_text(), bg=BG, fg=FG, font=FONT,
             justify="left", wraplength=480).pack(padx=18, pady=(18, 10))
    never = tk.BooleanVar(value=True)
    tk.Checkbutton(dlg, text=_L("Ne plus afficher", "Do not show again"),
                   variable=never, bg=BG, fg=FG, selectcolor=BG,
                   activebackground=BG, activeforeground=FG,
                   highlightthickness=0, font=FONT).pack(padx=18, anchor="w")

    def _ok():
        if never.get():
            set_licence_ok()
        try:
            dlg.destroy()
        except Exception:
            pass
        on_ok()

    btn_factory(dlg, _L("J'ai compris", "I understand"), _ok).pack(
        padx=18, pady=(10, 18))
    try:
        dlg.transient(win)
        dlg.grab_set()
    except Exception:
        pass


def run_grand_public(parent=None):
    import tkinter as tk
    from tkinter import messagebox
    try:
        from tkinter import ttk
    except Exception:
        ttk = None
    try:
        from PIL import Image, ImageTk
    except Exception:
        Image = ImageTk = None

    _TM = None
    try:
        import O4_Theme_Manager as _TM
        _t = _TM.get_theme()
    except Exception:
        _t = {}

    def _c(key, fallback):
        try:
            return _t.get(key, fallback)
        except Exception:
            return fallback

    BG = _c("bg", "#3b5b49")
    FG = _c("fg", "#e8f0ec")
    FG2 = _c("fg_secondary", "#a6e3a1")
    BTN_BG = _c("btn_bg", "#4a6b59")
    BTN_FG = _c("btn_fg", "#ffffff")
    HOVER = _c("accent", "#5a7b69")
    BORDER = _c("border", BTN_BG)
    IS_MAC = sys.platform.startswith("dar")
    FONT = ("Helvetica", 13) if IS_MAC else ("Segoe UI", 10)
    FONT_S = ("Helvetica", 11) if IS_MAC else ("Segoe UI", 9)
    FONT_T = ("Helvetica", 15, "bold") if IS_MAC else ("Segoe UI", 12, "bold")
    COL_SEL = "#FF9100"      # orange (tuile choisie) — visible sur la carte
    COL_DONE = "#40C057"     # vert (tuile déjà construite)

    root_ref = parent
    if root_ref is None:
        try:
            root_ref = tk._default_root
        except Exception:
            root_ref = None
    win = tk.Toplevel(root_ref) if root_ref else tk.Tk()
    win.title(_L("Ortho4XP V4 — Mode simple", "Ortho4XP V4 — Simple mode"))
    win.configure(bg=BG)
    if _TM is not None:
        try:
            _TM.apply_to_root(win)
        except Exception:
            pass

    try:
        import customtkinter as _ctk
        _HAS_CTK = True
    except Exception:
        _HAS_CTK = False

    def _btn(parent_w, text, cmd, bg=None, width=None):
        bgc = bg or BTN_BG
        if _HAS_CTK:
            extra = {"width": width} if width else {}
            b = _ctk.CTkButton(parent_w, text=text, command=cmd,
                               corner_radius=8, border_width=1, height=34,
                               fg_color=bgc, hover_color=HOVER,
                               border_color=BORDER, text_color=BTN_FG,
                               **extra)
            b.after_idle(lambda w=b, c=bgc:
                         w.winfo_exists() and w.configure(fg_color=c))
            return b
        frame = tk.Frame(parent_w, bg=bgc, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        lbl = tk.Label(frame, text=text, bg=bgc, fg=BTN_FG, padx=10, pady=6,
                       font=FONT, cursor="hand2")
        lbl.pack(fill="both", expand=True)

        def _enter(e=None):
            frame.configure(bg=HOVER); lbl.configure(bg=HOVER)

        def _leave(e=None):
            frame.configure(bg=bgc); lbl.configure(bg=bgc)

        def _release(e=None):
            _leave()
            if callable(cmd):
                cmd()

        for w in (frame, lbl):
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
            w.bind("<ButtonRelease-1>", _release)
        return frame

    cbd = current_build_dir()
    st = {
        "sel": set(),
        "done": set(), "done_dirs": {},
        "rects": {},          # (lat,lon) -> id rectangle sélection
        "done_rects": {},
        "chunks": {},         # (nx,ny) -> (id_image, PhotoImage)
        "quality": DEFAULT_QUALITY,
        "press": None,
        "panning": False,
        "runner": None,
        "est_text": None,
    }
    win._gp_state = st        # garde les PhotoImage en vie (garbage collector)
    # Lancé par « Création de tuiles mode simple » (lanceur) : la fenêtre
    # expert est cachée pour le débutant (elle reste active : c'est elle qui
    # construit). Ouvert depuis le menu Outils : rien n'est caché.
    expert_win = parent if parent is not None else root_ref
    st["hide_expert"] = (os.environ.get("O4X_START_MODE", "") == "simple"
                         and expert_win is not None)

    # ============== mise en page : panneau gauche + carte à droite ==========
    win.columnconfigure(2, weight=1)
    win.rowconfigure(0, weight=1)
    # Onglets des 4 étapes, en colonne au bord gauche de la fenêtre (le
    # panneau ne montre que l'étape choisie : plus rien de caché plus bas).
    tabs_f = tk.Frame(win, bg=BG)
    tabs_f.grid(row=0, column=0, sticky="nsw", padx=(12, 0), pady=12)
    # Panneau gauche DÉFILANT (règle Bible : jamais de hauteur figée ; sur
    # un petit écran les derniers boutons restent atteignables à la molette
    # ou avec l'ascenseur).
    left_outer = tk.Frame(win, bg=BG)
    left_outer.grid(row=0, column=1, sticky="nsw", padx=(8, 6), pady=12)
    left_outer.rowconfigure(0, weight=1)
    left_cv = tk.Canvas(left_outer, bg=BG, highlightthickness=0, bd=0,
                        yscrollincrement=20)
    left_cv.grid(row=0, column=0, sticky="ns")
    left_sb = tk.Scrollbar(left_outer, orient="vertical",
                           command=left_cv.yview)
    left_sb.grid(row=0, column=1, sticky="ns", padx=(10, 0))
    left_cv.configure(yscrollcommand=left_sb.set)
    left = tk.Frame(left_cv, bg=BG)
    left_win = left_cv.create_window((0, 0), window=left, anchor="nw")

    def _left_resize(e=None):
        try:
            left_cv.configure(scrollregion=left_cv.bbox("all"),
                              width=left.winfo_reqwidth())
        except Exception:
            pass

    def _left_fit(e=None):
        # Le contenu suit la largeur RÉELLE du panneau : si la fenêtre
        # rétrécit la colonne, les boutons rétrécissent au lieu d'être
        # coupés à droite (la marge droite reste visible).
        try:
            w = int(left_cv.winfo_width())
            if w > 1:
                left_cv.itemconfigure(left_win, width=w)
        except Exception:
            pass

    left.bind("<Configure>", _left_resize)
    left_cv.bind("<Configure>", _left_fit)

    def _left_wheel(e):
        try:
            if getattr(e, "num", None) == 4:
                step = -1
            elif getattr(e, "num", None) == 5:
                step = 1
            else:
                d = int(getattr(e, "delta", 0) or 0)
                if d == 0:
                    return
                step = -1 if d > 0 else 1
                if not IS_MAC and abs(d) >= 120:
                    step = -int(d / 120)
            first, last = left_cv.yview()
            if first <= 0.0 and last >= 1.0:
                return          # tout est visible : rien à faire défiler
            left_cv.yview_scroll(step, "units")
        except Exception:
            pass

    def _wheel_on(e=None):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            left_cv.bind_all(seq, _left_wheel)

    def _wheel_off(e=None):
        for seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            try:
                left_cv.unbind_all(seq)
            except Exception:
                pass

    left_outer.bind("<Enter>", _wheel_on)
    left_outer.bind("<Leave>", _wheel_off)
    right = tk.Frame(win, bg=BG)
    right.grid(row=0, column=2, sticky="nsew", padx=(6, 12), pady=12)
    right.rowconfigure(0, weight=1)
    right.columnconfigure(0, weight=1)

    def _title(txt):
        tk.Label(left, text=txt, bg=BG, fg=FG2, font=FONT_T,
                 anchor="w").pack(fill=tk.X, pady=(10, 2))

    # --- Langue (FR / EN) : enregistrée dans Ortho4XP.cfg par O4_Lang, puis
    #     redémarrage automatique dans le même mode (libellés construits au
    #     démarrage, comme partout dans Ortho4XP). ---
    lang_f = tk.Frame(left, bg=BG)
    lang_f.pack(fill=tk.X, pady=(0, 4))
    tk.Label(lang_f, text="🌐", bg=BG, fg=FG, font=FONT).pack(side=tk.LEFT)
    lang_var = tk.StringVar(value="FR" if _lang_code() == "fr" else "EN")
    for code, txt in (("FR", "Français"), ("EN", "English")):
        tk.Radiobutton(lang_f, text=txt, variable=lang_var, value=code,
                       bg=BG, fg=FG, selectcolor=BG, activebackground=BG,
                       activeforeground=FG, highlightthickness=0,
                       font=FONT_S,
                       command=lambda: _switch_lang(lang_var.get())
                       ).pack(side=tk.LEFT, padx=(6, 0))

    # --- Nouvelle version ? (une ligne, rien n'est installé tout seul) ---
    upd_var = tk.StringVar(value="")
    upd_lbl = tk.Label(left, textvariable=upd_var, bg=BG, fg=FG, font=FONT_S,
                       justify="left", anchor="w", wraplength=300,
                       cursor="hand2")
    upd_lbl.pack(fill=tk.X)
    upd_box = {}

    def _upd_work():
        try:
            import O4_Update_Utils as UPD
            upd_box["found"] = UPD.check()
        except Exception:
            upd_box["found"] = None

    def _upd_poll():
        if "found" not in upd_box:
            try:
                win.after(1000, _upd_poll)
            except Exception:
                pass
            return
        if upd_box["found"]:
            try:
                import O4_Update_Utils as UPD
                upd_var.set(UPD.message(upd_box["found"]))
            except Exception:
                pass

    def _upd_click(e=None):
        if upd_box.get("found"):
            try:
                import O4_Update_Utils as UPD
                UPD.open_page(upd_box["found"])
            except Exception:
                pass

    upd_lbl.bind("<ButtonRelease-1>", _upd_click)
    threading.Thread(target=_upd_work, daemon=True).start()
    win.after(1000, _upd_poll)

    # --- Les 4 pages (une par onglet) ---
    left_head = left
    pages = [tk.Frame(left_head, bg=BG) for _i in range(4)]
    st["tab"] = 0

    def _next_btn(page, k):
        _btn(page, _L("Suivant →", "Next →"),
             lambda: _show_tab(k)).pack(fill=tk.X, pady=(12, 2))

    # --- 1. Tuiles ---
    left = pages[0]
    _title(_L("1. Choisissez vos tuiles", "1. Choose your tiles"))
    tk.Label(left, text=_L("Clic sur la carte = choisir / retirer une tuile.\n"
                           "Glisser = déplacer la carte.\n"
                           "Molette ou ＋ / － = agrandir / réduire.\n"
                           "Orange avec croix = choisie.\n"
                           "Vert = déjà construite.",
                           "Click on the map = choose / remove a tile.\n"
                           "Drag = move the map.\n"
                           "Wheel or ＋ / － = zoom in / out.\n"
                           "Orange with a cross = chosen.\n"
                           "Green = already built."),
             bg=BG, fg=FG, font=FONT_S, justify="left",
             anchor="w").pack(fill=tk.X)
    goto_f = tk.Frame(left, bg=BG)
    goto_f.pack(fill=tk.X, pady=(6, 2))
    tk.Label(goto_f, text=_L("Aller à :", "Go to:"), bg=BG, fg=FG,
             font=FONT).pack(side=tk.LEFT)
    goto_var = tk.StringVar(value="")
    goto_entry = tk.Entry(goto_f, textvariable=goto_var, width=14,
                          bg="#05330f", fg=FG, insertbackground=FG, font=FONT)
    goto_entry.pack(side=tk.LEFT, padx=6)
    tk.Label(left, text=_L("ex. LFEY, Nantes, +46-003, 46.7, -2.3 — ou "
                           "plusieurs tuiles : +43+005 +43+006",
                           "e.g. LFEY, Nantes, +46-003, 46.7, -2.3 — or "
                           "several tiles: +43+005 +43+006"),
             bg=BG, fg=FG, font=FONT_S, anchor="w").pack(fill=tk.X)
    # Résultats de la recherche d'aéroport / de ville (cachés tant que vides)
    res_f = tk.Frame(left, bg=BG)
    res_lb = tk.Listbox(res_f, height=5, bg="#05140a", fg=FG,
                        selectbackground=HOVER, selectforeground=FG,
                        font=FONT_S, activestyle="none", exportselection=False,
                        highlightthickness=0)
    res_lb.pack(fill=tk.X)
    res_info = tk.StringVar(value="")
    tk.Label(res_f, textvariable=res_info, bg=BG, fg=FG, font=FONT_S,
             anchor="w", justify="left", wraplength=300).pack(fill=tk.X)
    more_f = tk.Frame(left, bg=BG)
    more_f.pack(fill=tk.X, pady=(4, 0))
    _btn(more_f, _L("✈ Tuiles autour d'un aéroport…",
                    "✈ Tiles around an airport…"),
         lambda: _open_route()).pack(fill=tk.X, pady=3)
    _btn(more_f, _L("✏ Zones plus nettes sur la tuile choisie…",
                    "✏ Sharper zones on the chosen tile…"),
         lambda: _open_zones()).pack(fill=tk.X, pady=3)
    _btn(more_f, _L("☁ Nuages sur la tuile choisie…",
                    "☁ Clouds on the chosen tile…"),
         lambda: _open_clouds()).pack(fill=tk.X, pady=3)
    _btn(more_f, _L("🖼 Imagerie de la source sur la carte (oui / non)",
                    "🖼 Source imagery on the map (on / off)"),
         lambda: _toggle_imagery()).pack(fill=tk.X, pady=3)
    sel_var = tk.StringVar(value="")
    tk.Label(left, textvariable=sel_var, bg=BG, fg=FG, font=FONT,
             justify="left", anchor="w", wraplength=300).pack(fill=tk.X,
                                                              pady=(6, 2))

    _next_btn(pages[0], 1)

    # --- 2. Qualité ---
    left = pages[1]
    _title(_L("2. Choisissez la qualité", "2. Choose the quality"))
    q_var = tk.StringVar(value=DEFAULT_QUALITY)
    q_help = tk.StringVar(value=quality_help(DEFAULT_QUALITY))
    for q in QUALITY_ORDER:
        tk.Radiobutton(left, text=quality_label(q), variable=q_var, value=q,
                       bg=BG, fg=FG, selectcolor=BG, activebackground=BG,
                       activeforeground=FG, highlightthickness=0, font=FONT,
                       anchor="w",
                       command=lambda: _on_quality()).pack(fill=tk.X)
    tk.Label(left, textvariable=q_help, bg=BG, fg=FG, font=FONT_S,
             justify="left", anchor="w", wraplength=300).pack(fill=tk.X)
    # Netteté à la main (facultatif) : paysage + aéroports.
    PROFILE_TXT = _L("selon la qualité", "as the quality")
    NO_APT_TXT = _L("pas plus net", "not sharper")
    zl_vals = [PROFILE_TXT] + ["ZL%d" % z for z in ZL_CHOICES]
    apt_vals = [PROFILE_TXT, NO_APT_TXT] + ["ZL%d" % z for z in APT_CHOICES]
    zl_var = tk.StringVar(value=PROFILE_TXT)
    apt_var = tk.StringVar(value=PROFILE_TXT)
    zl_f = tk.Frame(left, bg=BG)
    zl_f.pack(fill=tk.X, pady=(4, 0))
    for row, (txt, var, vals_) in enumerate((
            (_L("Netteté du paysage :", "Scenery sharpness:"), zl_var,
             zl_vals),
            (_L("Netteté des aéroports :", "Airport sharpness:"), apt_var,
             apt_vals))):
        tk.Label(zl_f, text=txt, bg=BG, fg=FG, font=FONT_S,
                 anchor="w").grid(row=row, column=0, sticky="w")
        if ttk is not None:
            try:
                cb = ttk.Combobox(zl_f, textvariable=var, values=vals_,
                                  state="readonly", width=16)
                cb.grid(row=row, column=1, sticky="w", padx=(4, 0), pady=1)
                cb.bind("<<ComboboxSelected>>", lambda e: _on_quality())
            except Exception:
                pass

    icao_var = tk.BooleanVar(value=False)
    tk.Checkbutton(zl_f, text=_L("aéroports avec code OACI seulement",
                                 "only airports with an ICAO code"),
                   variable=icao_var, bg=BG, fg=FG, selectcolor=BG,
                   activebackground=BG, activeforeground=FG,
                   highlightthickness=0, font=FONT_S, anchor="w",
                   command=lambda: _on_quality()).grid(row=3, column=0,
                                                       columnspan=2,
                                                       sticky="w")

    def _zl_from(txt):
        if txt == NO_APT_TXT:
            return 0
        if str(txt).startswith("ZL"):
            try:
                return int(str(txt)[2:])
            except Exception:
                return None
        return None

    # Couleurs (saturation de Color Normalize, comme le curseur expert)
    colour_names = [colour_label(c) for c in COLOUR_CHOICES]
    colour_var = tk.StringVar(value=colour_label("source"))
    tk.Label(zl_f, text=_L("Couleurs des photos :", "Photo colours:"), bg=BG,
             fg=FG, font=FONT_S, anchor="w").grid(row=2, column=0,
                                                  sticky="w")
    if ttk is not None:
        try:
            cbc = ttk.Combobox(zl_f, textvariable=colour_var,
                               values=colour_names, state="readonly",
                               width=16)
            cbc.grid(row=2, column=1, sticky="w", padx=(4, 0), pady=1)
        except Exception:
            pass

    def _colour():
        v = colour_var.get()
        for c in COLOUR_CHOICES:
            if colour_label(c) == v:
                return c
        return "source"

    # Mes réglages enregistrés (profils)
    prof_f = tk.Frame(left, bg=BG)
    prof_f.pack(fill=tk.X, pady=(6, 0))
    tk.Label(prof_f, text=_L("Mes réglages :", "My settings:"), bg=BG, fg=FG,
             font=FONT_S).grid(row=0, column=0, sticky="w")
    NO_PROF_TXT = _L("(aucun — cliquez 💾 Enregistrer)",
                     "(none — click 💾 Save)")
    _profs0 = sorted(load_profiles())
    prof_var = tk.StringVar(value="" if _profs0 else NO_PROF_TXT)
    prof_cb = None
    if ttk is not None:
        try:
            prof_cb = ttk.Combobox(prof_f, textvariable=prof_var,
                                   values=_profs0 or [NO_PROF_TXT],
                                   state="readonly", width=22)
            prof_cb.grid(row=0, column=1, sticky="w", padx=(4, 0))
            prof_cb.bind("<<ComboboxSelected>>",
                         lambda e: _apply_profile(prof_var.get()))
        except Exception:
            prof_cb = None
    prof_b = tk.Frame(left, bg=BG)
    prof_b.pack(fill=tk.X)
    prof_b.columnconfigure(0, weight=1)
    prof_b.columnconfigure(1, weight=1)
    _btn(prof_b, _L("💾 Enregistrer…", "💾 Save…"),
         lambda: _save_profile()).grid(row=0, column=0, sticky="ew",
                                       padx=(0, 5), pady=4)
    _btn(prof_b, _L("🗑 Supprimer", "🗑 Delete"),
         lambda: _delete_profile()).grid(row=0, column=1, sticky="ew",
                                         padx=(5, 0), pady=4)
    # Par défaut : la source de la fenêtre expert (comportement éprouvé) ;
    # « automatique » au choix de l'utilisateur.
    EXPERT_SRC = "__expert__"
    src_var = tk.StringVar(value=EXPERT_SRC)
    src_f = tk.Frame(left, bg=BG)
    src_f.pack(fill=tk.X, pady=(6, 0))
    tk.Label(src_f, text=_L("Source des images :", "Image source:"), bg=BG,
             fg=FG, font=FONT_S).pack(side=tk.LEFT)
    for val, txt in ((AUTO, _L("automatique", "automatic")),
                     (EXPERT_SRC, _L("fenêtre expert", "expert window"))):
        tk.Radiobutton(src_f, text=txt, variable=src_var, value=val, bg=BG,
                       fg=FG, selectcolor=BG, activebackground=BG,
                       activeforeground=FG, highlightthickness=0,
                       font=FONT_S).pack(side=tk.LEFT, padx=(4, 0))
    ovl_src = overlay_source()
    ovl_var = tk.BooleanVar(value=bool(ovl_src))
    ovl_cb = tk.Checkbutton(
        left, text=_L("Ajouter routes et forêts X-Plane (overlay)",
                      "Add X-Plane roads and forests (overlay)"),
        variable=ovl_var, bg=BG, fg=FG, selectcolor=BG, activebackground=BG,
        activeforeground=FG, highlightthickness=0, font=FONT_S, anchor="w")
    ovl_cb.pack(fill=tk.X, pady=(6, 0))
    if not ovl_src:
        try:
            ovl_cb.configure(state="disabled")
        except Exception:
            pass

    _next_btn(pages[1], 2)
    # options de construction : rangées dans l'onglet 4, au-dessus des
    # boutons « Construire » / « Arrêter »
    left = pages[3]
    _title(_L("4. Construisez", "4. Build"))
    inst_var = tk.BooleanVar(value=True)
    tk.Checkbutton(
        left, text=_L("Installer dans X-Plane à la fin",
                      "Install into X-Plane at the end"),
        variable=inst_var, bg=BG, fg=FG, selectcolor=BG, activebackground=BG,
        activeforeground=FG, highlightthickness=0, font=FONT_S,
        anchor="w").pack(fill=tk.X)
    xp_var = tk.StringVar(value="")
    xp_f = tk.Frame(left, bg=BG)
    xp_f.pack(fill=tk.X)
    tk.Label(xp_f, textvariable=xp_var, bg=BG, fg=FG, font=FONT_S,
             justify="left", anchor="w", wraplength=300).pack(fill=tk.X)

    def _refresh_xp():
        root_ = xplane_root_of_ini(xplane_ini())
        xp_var.set(_L("X-Plane utilisé : ", "X-Plane used: ")
                   + (root_ or _L("pas encore choisi", "not chosen yet")))

    def _change_xp():
        try:
            from tkinter import filedialog
            p = filedialog.askopenfilename(
                parent=win,
                title=_L("Choisir le scenery_packs.ini du X-Plane à utiliser "
                         "(dossier Custom Scenery)",
                         "Choose the scenery_packs.ini of the X-Plane to use "
                         "(Custom Scenery folder)"),
                filetypes=[("scenery_packs.ini", "scenery_packs.ini"),
                           (_L("Tous les fichiers", "All files"), "*")])
        except Exception:
            p = ""
        if not p:
            return
        if not valid_ini_choice(p):
            messagebox.showwarning(
                "X-Plane",
                _L("Choisissez le fichier « scenery_packs.ini » qui se trouve "
                   "dans le dossier « Custom Scenery » de votre X-Plane.",
                   "Choose the « scenery_packs.ini » file located in the "
                   "« Custom Scenery » folder of your X-Plane."), parent=win)
            return
        remember_xplane_ini(p)
        _refresh_xp()

    _btn(xp_f, _L("Changer de X-Plane…", "Change X-Plane…"),
         _change_xp).pack(anchor="w", pady=(2, 4))
    _refresh_xp()
    force_var = tk.BooleanVar(value=False)
    tk.Checkbutton(
        left, text=_L("Refaire aussi les tuiles déjà à jour",
                      "Also redo tiles already up to date"),
        variable=force_var, bg=BG, fg=FG, selectcolor=BG, activebackground=BG,
        activeforeground=FG, highlightthickness=0, font=FONT_S,
        anchor="w").pack(fill=tk.X)

    def _provider_choice():
        v = src_var.get()
        return AUTO if v == AUTO else current_provider()

    # --- 3. Vérifier ---
    left = pages[2]
    _title(_L("3. Vérifiez", "3. Check"))
    chk_row = tk.Frame(left, bg=BG)
    chk_row.pack(fill=tk.X)
    chk_row.columnconfigure(0, weight=2)
    chk_row.columnconfigure(1, weight=1)
    _btn(chk_row, _L("🔍 Vérifier le projet", "🔍 Check the project"),
         lambda: _check()).grid(row=0, column=0, sticky="ew", padx=(0, 5),
                                pady=4)
    _btn(chk_row, _L("👁 Aperçu", "👁 Preview"),
         lambda: _preview()).grid(row=0, column=1, sticky="ew", padx=(5, 0),
                                  pady=4)

    tk.Label(left, text=_L("Le résultat s'affiche sous la carte.",
                           "The result shows under the map."), bg=BG, fg=FG,
             font=FONT_S, anchor="w").pack(fill=tk.X, pady=(4, 0))
    _next_btn(pages[2], 3)

    # --- 4. Construire ---
    left = pages[3]
    run_row = tk.Frame(left, bg=BG)
    run_row.pack(fill=tk.X)
    run_row.columnconfigure(0, weight=2)
    run_row.columnconfigure(1, weight=1)
    _btn(run_row, _L("▶  Construire", "▶  Build"),
         lambda: _build()).grid(row=0, column=0, sticky="ew", padx=(0, 5),
                                pady=4)
    _btn(run_row, _L("⏹  Arrêter", "⏹  Stop"),
         lambda: _stop()).grid(row=0, column=1, sticky="ew", padx=(5, 0),
                               pady=4)
    _btn(left, _L("⏏ Retirer de la file les tuiles décochées",
                  "⏏ Remove the unticked tiles from the queue"),
         lambda: _unqueue()).pack(fill=tk.X, pady=(2, 4))
    prog_var = tk.StringVar(value="")
    tk.Label(left, textvariable=prog_var, bg=BG, fg=FG, font=FONT,
             justify="left", anchor="w", wraplength=300).pack(fill=tk.X,
                                                              pady=(4, 2))
    pbar = None
    if ttk is not None:
        try:
            pbar = ttk.Progressbar(left, orient="horizontal", mode="determinate",
                                   maximum=100, length=260)
            pbar.pack(fill=tk.X, pady=4)
        except Exception:
            pbar = None
    end_f = tk.Frame(left, bg=BG)
    end_f.pack(fill=tk.X, pady=(8, 0))
    _btn(end_f, _L("📥 Installer / réinstaller dans X-Plane",
                   "📥 Install / reinstall into X-Plane"),
         lambda: _install()).pack(fill=tk.X, pady=4)
    row2 = tk.Frame(end_f, bg=BG)
    row2.pack(fill=tk.X)
    row2.columnconfigure(0, weight=1)
    row2.columnconfigure(1, weight=1)
    _btn(row2, _L("📂 Dossier", "📂 Folder"),
         lambda: _open_path(working_dir(cbd))).grid(row=0, column=0,
                                                     sticky="ew", padx=(0, 5),
                                                     pady=4)
    _btn(row2, _L("🗃 Bibliothèque", "🗃 Library"),
         lambda: _open_module("O4_Tile_Library_Utils",
                              "run_tile_library")).grid(row=0, column=1,
                                                        sticky="ew",
                                                        padx=(5, 0), pady=4)
    _btn(end_f, _L("🩺 Diagnostic", "🩺 Diagnostic"),
         lambda: _open_module("O4_Diagnostics_Utils",
                              "run_diagnostics")).pack(fill=tk.X, pady=4)
    _btn(end_f, _L("🧹 Grand nettoyage (libérer de la place)",
                   "🧹 Big cleanup (free up space)"),
         lambda: _open_module("O4_Cleanup_Utils",
                              "run_cleanup")).pack(fill=tk.X, pady=4)

    def _show_expert():
        """Fait réapparaître la fenêtre expert (détail technique, réglages)."""
        try:
            expert_win.deiconify()
            expert_win.lift()
        except Exception:
            pass
        st["hide_expert"] = False

    if st["hide_expert"]:
        _btn(end_f, _L("🛠 Passer en mode expert", "🛠 Switch to expert mode"),
             _show_expert).pack(fill=tk.X, pady=(10, 2))

    # --- Onglets (colonne au bord gauche) ---
    TAB_NAMES = (_L("1 · Tuiles", "1 · Tiles"),
                 _L("2 · Qualité", "2 · Quality"),
                 _L("3 · Vérification", "3 · Check"),
                 _L("4 · Construction", "4 · Build"))
    tab_btns = []
    TAB_ON = BTN_BG
    TAB_OFF = BG

    def _tab_style(b, on):
        col = TAB_ON if on else TAB_OFF
        try:
            if _HAS_CTK:
                b.configure(fg_color=col, border_width=(2 if on else 1))
            else:
                b.configure(bg=col)
                for ch in b.winfo_children():
                    ch.configure(bg=col)
        except Exception:
            pass

    def _show_tab(k):
        k = max(0, min(3, int(k)))
        st["tab"] = k
        for i, pg in enumerate(pages):
            try:
                if i == k:
                    pg.pack(fill=tk.X, padx=(2, 16))
                else:
                    pg.pack_forget()
            except Exception:
                pass
            if i < len(tab_btns):
                _tab_style(tab_btns[i], i == k)
        try:
            left_cv.yview_moveto(0.0)
            win.after_idle(_left_resize)
        except Exception:
            pass

    def _tab_text(i):
        if i == 0 and st["sel"]:
            return TAB_NAMES[0] + " (%d)" % len(st["sel"])
        return TAB_NAMES[i]

    def _refresh_tab_labels():
        for i, b in enumerate(tab_btns):
            try:
                if _HAS_CTK:
                    b.configure(text=_tab_text(i))
                else:
                    for ch in b.winfo_children():
                        ch.configure(text=_tab_text(i))
            except Exception:
                pass

    for i in range(4):
        b = _btn(tabs_f, TAB_NAMES[i], lambda k=i: _show_tab(k), width=150)
        b.pack(fill=tk.X, pady=5)
        tab_btns.append(b)
    mini_var = tk.StringVar(value="")
    tk.Label(tabs_f, textvariable=mini_var, bg=BG, fg=FG2, font=FONT_S,
             justify="left", anchor="w", wraplength=150).pack(fill=tk.X,
                                                              pady=(10, 0))
    _show_tab(0)

    # Barre de menus : la même que l'Expert, posée aussi sur cette fenêtre
    # (sur Mac, la barre suit la fenêtre active : sans cela elle disparaît
    # quand le mode simple est ouvert). Une commande de la fenêtre expert
    # fait d'abord réapparaître la fenêtre expert si elle est cachée.
    def _reveal_expert():
        if st["hide_expert"]:
            _show_expert()

    if expert_win is not None:
        try:
            import O4_Menu_Bar as _MB
            _MB.install_menubar(expert_win, host=win, before=_reveal_expert)
        except Exception:
            pass

    # ============== carte ==============
    canvas = tk.Canvas(right, bg="#2b3a33", highlightthickness=0,
                       width=820, height=620,
                       scrollregion=(0, 0, MAP_SIZE, MAP_SIZE))
    canvas.grid(row=0, column=0, sticky="nsew")
    st["zoom"] = DEFAULT_ZOOM
    # Boutons de zoom posés sur la carte (coin haut droit)
    zoom_f = tk.Frame(right, bg=BG)
    zoom_f.place(in_=canvas, relx=1.0, x=-10, y=10, anchor="ne")
    hover_var = tk.StringVar(value="")
    tk.Label(right, textvariable=hover_var, bg=BG, fg=FG, font=FONT_S,
             anchor="w").grid(row=1, column=0, sticky="ew")
    summary_box = tk.Text(right, height=9, wrap="word", bg="#05140a", fg=FG,
                          font=FONT_S, relief="flat", padx=8, pady=6,
                          highlightthickness=0)
    summary_box.grid(row=2, column=0, sticky="ew", pady=(6, 0))
    summary_box.insert("1.0", _L(
        "COMMENT CRÉER UNE TUILE (une tuile = une case de la carte) :\n"
        "  1. Cliquez sur une case de la carte ci-dessus : elle devient "
        "orange avec une croix.\n"
        "     Pour trouver un endroit, tapez un aéroport ou une ville dans "
        "« Aller à » (ex. LFEY, Nantes).\n"
        "  2. Choisissez la qualité (à gauche) : « Équilibrée » convient "
        "dans la plupart des cas.\n"
        "  3. Cliquez « 🔍 Vérifier le projet » : le résumé (place disque, "
        "durée, problèmes) s'affiche ici.\n"
        "  4. Cliquez « ▶ Construire ». À la fin, la tuile est installée "
        "dans X-Plane : lancez le vol.",
        "HOW TO CREATE A TILE (a tile = one square of the map):\n"
        "  1. Click on a square of the map above: it turns orange with a "
        "cross.\n"
        "     To find a place, type an airport or a city in « Go to » "
        "(e.g. LFEY, Nantes).\n"
        "  2. Choose the quality (on the left): « Balanced » suits most "
        "cases.\n"
        "  3. Click « 🔍 Check the project »: the summary (disk space, "
        "time, problems) appears here.\n"
        "  4. Click « ▶ Build ». At the end the tile is installed into "
        "X-Plane: go and fly."))
    summary_box.config(state="disabled")

    earth_prefix = os.path.join(_root_dir(), "Utils", "Earth",
                                "Earth2_ZL%d_" % MAP_ZL)

    def _z():
        return st.get("zoom", DEFAULT_ZOOM)

    def _pix(lat, lon):
        x, y = latlon_to_pix(lat, lon)
        return (x * _z(), y * _z())

    def _ll(cx, cy):
        return pix_to_latlon(cx / _z(), cy / _z())

    def _rect(lat, lon):
        return tuple(v * _z() for v in tile_rect_pix(lat, lon))

    def _view_box():
        x0 = canvas.canvasx(0)
        y0 = canvas.canvasy(0)
        w = max(1, canvas.winfo_width())
        h = max(1, canvas.winfo_height())
        return (x0, y0, x0 + w, y0 + h)

    def _load_chunks():
        if Image is None or ImageTk is None:
            return
        z = _z()
        want = pieces_for_view(*(_view_box() + (z,)))
        disp = int(round(piece_src_size(z) * z))
        for key in want:
            if key in st["chunks"]:
                continue
            (nx, ny), box = piece_source(key[0], key[1], z)
            fn = earth_prefix + "%d_%d.jpg" % (nx, ny)
            try:
                im = Image.open(fn)
                if box == (0, 0, CHUNK, CHUNK) and disp < CHUNK:
                    try:
                        im.draft("RGB", (disp, disp))   # JPEG lu réduit : rapide
                    except Exception:
                        pass
                elif box != (0, 0, CHUNK, CHUNK):
                    im = im.crop(box)
                if im.size != (disp, disp):
                    im = im.resize((disp, disp), Image.BILINEAR)
                ph = ImageTk.PhotoImage(im)
            except Exception:
                continue
            iid = canvas.create_image(key[0] * disp, key[1] * disp,
                                      anchor="nw", image=ph)
            canvas.tag_lower(iid)
            st["chunks"][key] = (iid, ph)
        # garder au plus 12 morceaux en mémoire (chacun ≤ ~16 Mo)
        if len(st["chunks"]) > 12:
            for key in list(st["chunks"].keys()):
                if key not in want and len(st["chunks"]) > 12:
                    iid, _ph = st["chunks"].pop(key)
                    try:
                        canvas.delete(iid)
                    except Exception:
                        pass

    def _draw_grid():
        # Lignes de 1° légères : méridiens et parallèles sur toute la carte
        size = MAP_SIZE * _z()
        for lon in range(-180, 181):
            x, _y = _pix(0, lon)
            canvas.create_line(x, 0, x, size, fill="#1e2a24", width=1,
                               tags=("grid",))
        for lat in range(-85, 86):
            _x, y = _pix(lat, 0)
            canvas.create_line(0, y, size, y, fill="#1e2a24", width=1,
                               tags=("grid",))

    def _outlined_rect(lat, lon, color, width):
        """Contour vif + liseré noir dessous (règle §31 : visible sur la
        carte claire comme sombre). Pas de remplissage hachuré : non pris
        en charge par Tk sous macOS. Renvoie la liste des id."""
        box = _rect(lat, lon)
        a = canvas.create_rectangle(*box, outline="#000000", width=width + 2)
        b = canvas.create_rectangle(*box, outline=color, width=width)
        return [a, b]

    def _delete_ids(ids):
        for iid in (ids or []):
            try:
                canvas.delete(iid)
            except Exception:
                pass

    def _draw_done():
        for ids in st["done_rects"].values():
            _delete_ids(ids)
        st["done_rects"] = {}
        try:
            import O4_File_Names as FNAMES
            ll = FNAMES.long_latlon
        except Exception:
            ll = None
        # Vert = tuile trouvée dans le dossier de construction, dans Tiles
        # OU déjà dans le Custom Scenery du X-Plane choisi (quelle que soit
        # la langue et même si le champ « dossier de construction » change).
        st["done_dirs"] = built_tiles_map(built_scan_dirs(cbd), ll)
        st["done"] = set(st["done_dirs"])
        for (lat, lon) in st["done"]:
            st["done_rects"][(lat, lon)] = _outlined_rect(lat, lon, COL_DONE, 2)
        # les tuiles choisies restent au-dessus
        for ids in st["rects"].values():
            for iid in ids:
                try:
                    canvas.tag_raise(iid)
                except Exception:
                    pass

    def _refresh_sel_label():
        try:
            _refresh_tab_labels()
        except Exception:
            pass
        n = len(st["sel"])
        if not n:
            sel_var.set(_L("Aucune tuile choisie : cliquez une case de la "
                           "carte (à droite).",
                           "No tile chosen: click a square of the map (on "
                           "the right)."))
            return
        names = [short_latlon(*t) for t in sorted_tiles(st["sel"])]
        shown = ", ".join(names[:8]) + (" …" if n > 8 else "")
        sel_var.set(_L("%d tuile(s) : " % n, "%d tile(s): " % n) + shown
                    + _L("\n→ Ensuite : qualité, puis « Vérifier » et "
                         "« Construire ».",
                         "\n→ Next: quality, then « Check » and « Build »."))

    def _toggle_tile(lat, lon):
        if not valid_tile(lat, lon):
            return
        t = (lat, lon)
        if toggle(st["sel"], t):
            st["rects"][t] = _sel_marks(lat, lon)
        else:
            _delete_ids(st["rects"].pop(t, None))
        _refresh_sel_label()

    def _sel_marks(lat, lon):
        ids = _outlined_rect(lat, lon, COL_SEL, 3)
        # croix fine au centre : la tuile choisie se repère d'un coup d'œil
        x0, y0, x1, y1 = _rect(lat, lon)
        m = min(4.0, (x1 - x0) / 5.0)
        ids.append(canvas.create_line(x0 + m, y0 + m, x1 - m, y1 - m,
                                      fill=COL_SEL, width=2))
        ids.append(canvas.create_line(x0 + m, y1 - m, x1 - m, y0 + m,
                                      fill=COL_SEL, width=2))
        return ids

    def _set_zoom(new_z, anchor=None):
        """Change le zoom en gardant sous la souris (ou au centre) le même
        point de la carte. Tout est redessiné à la nouvelle échelle."""
        old_z = _z()
        if new_z == old_z:
            return
        x0, y0, x1, y1 = _view_box()
        if anchor is None:
            ax, ay = (x1 - x0) / 2.0, (y1 - y0) / 2.0
        else:
            ax, ay = anchor
        lat, lon = _ll(x0 + ax, y0 + ay)
        st["zoom"] = new_z
        for iid, _ph in st["chunks"].values():
            try:
                canvas.delete(iid)
            except Exception:
                pass
        st["chunks"] = {}
        canvas.delete("grid")
        for ids in st["rects"].values():
            _delete_ids(ids)
        size = MAP_SIZE * new_z
        canvas.configure(scrollregion=(0, 0, size, size))
        _draw_grid()
        _draw_done()
        st["rects"] = {}
        if st.get("ovl"):
            _draw_ovl()
        for t in sorted_tiles(st["sel"]):
            st["rects"][t] = _sel_marks(*t)
        px, py = _pix(lat, lon)
        canvas.xview_moveto(max(0.0, (px - ax) / size))
        canvas.yview_moveto(max(0.0, (py - ay) / size))
        _load_chunks()
        _zoom_label()

    def _zoom_step(direction, anchor=None):
        _set_zoom(next_zoom(_z(), direction), anchor)

    def _center_on(lat, lon):
        x, y = _pix(lat, lon)
        x0, y0, x1, y1 = _view_box()
        w, h = x1 - x0, y1 - y0
        size = MAP_SIZE * _z()
        canvas.xview_moveto(max(0.0, (x - w / 2.0) / size))
        canvas.yview_moveto(max(0.0, (y - h / 2.0) / size))
        _load_chunks()

    def _on_press(e):
        st["press"] = (e.x, e.y)
        st["panning"] = False
        canvas.scan_mark(e.x, e.y)

    def _on_motion_drag(e):
        if st["press"] is None:
            return
        dx = abs(e.x - st["press"][0]); dy = abs(e.y - st["press"][1])
        if st["panning"] or dx > 4 or dy > 4:
            st["panning"] = True
            canvas.scan_dragto(e.x, e.y, gain=1)

    def _on_release(e):
        if st["press"] is None:
            return
        if st["panning"]:
            _load_chunks()
        else:
            lat, lon = _ll(canvas.canvasx(e.x), canvas.canvasy(e.y))
            _toggle_tile(*tile_of_point(lat, lon))
        st["press"] = None
        st["panning"] = False

    def _on_hover(e):
        try:
            lat, lon = _ll(canvas.canvasx(e.x), canvas.canvasy(e.y))
            t = tile_of_point(lat, lon)
            if valid_tile(*t):
                extra = ""
                if t in st["done"]:
                    extra = _L("  — déjà construite", "  — already built")
                if t in st["sel"]:
                    extra += _L("  — choisie", "  — chosen")
                hover_var.set(_L("Sous la souris : tuile ",
                                 "Under the mouse: tile ")
                              + short_latlon(*t) + extra)
        except Exception:
            pass

    canvas.bind("<ButtonPress-1>", _on_press)
    canvas.bind("<B1-Motion>", _on_motion_drag)
    canvas.bind("<ButtonRelease-1>", _on_release)
    canvas.bind("<Motion>", _on_hover)
    canvas.bind("<Leave>", lambda e: hover_var.set(""))
    canvas.bind("<Configure>", lambda e: _load_chunks())

    # ---- zoom : boutons + / − sur la carte, molette sur la carte ----
    zoom_txt = tk.StringVar(value="")

    def _zoom_label():
        zoom_txt.set("%d %%" % int(round(_z() * 100)))

    _btn(zoom_f, "＋", lambda: _zoom_step(+1),
         width=44).pack(fill=tk.X, pady=(0, 2))
    tk.Label(zoom_f, textvariable=zoom_txt, bg=BG, fg=FG,
             font=FONT_S).pack(fill=tk.X)
    _btn(zoom_f, "－", lambda: _zoom_step(-1),
         width=44).pack(fill=tk.X, pady=(2, 0))
    _zoom_label()
    wheel = {"t": 0.0}

    def _on_map_wheel(e):
        # Une seule étape de zoom par geste (un pavé tactile envoie des
        # dizaines d'événements d'affilée).
        try:
            if getattr(e, "num", None) == 4:
                d = 1
            elif getattr(e, "num", None) == 5:
                d = -1
            else:
                d = 1 if int(getattr(e, "delta", 0) or 0) > 0 else -1
                if not int(getattr(e, "delta", 0) or 0):
                    return
            now = time.time()
            if now - wheel["t"] < 0.35:
                return
            wheel["t"] = now
            _zoom_step(d, (e.x, e.y))
        except Exception:
            pass

    for _seq in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
        canvas.bind(_seq, _on_map_wheel)

    # ---- recherche d'aéroport / de ville (hors ligne, apt.dat de X-Plane) ----
    apt = {"index": None, "loading": False, "results": []}

    def _show_results(items, info):
        apt["results"] = items
        res_lb.delete(0, tk.END)
        try:
            import O4_Airport_Search_Utils as AS
            for a in items:
                res_lb.insert(tk.END, AS.label(a))
        except Exception:
            pass
        res_info.set(info)
        try:
            res_f.pack(fill=tk.X, pady=(2, 2), after=goto_f)
        except Exception:
            res_f.pack(fill=tk.X, pady=(2, 2))

    def _pick_result(e=None):
        sel = res_lb.curselection()
        if not sel:
            return
        a = apt["results"][sel[0]]
        _center_on(a["lat"], a["lon"])
        t = tile_of_point(a["lat"], a["lon"])
        if t not in st["sel"]:
            _toggle_tile(*t)

    res_lb.bind("<<ListboxSelect>>", _pick_result)

    def _add_tiles(tiles):
        """Tuiles venues de la fenêtre « autour d'un aéroport »."""
        added = 0
        for (la, lo) in tiles:
            if (la, lo) not in st["sel"] and valid_tile(la, lo):
                _toggle_tile(la, lo)
                added += 1
        if tiles:
            try:
                _center_on(tiles[0][0] + 0.5, tiles[0][1] + 0.5)
            except Exception:
                pass
        return added

    def _open_route():
        try:
            import O4_Route_Utils as RT
            RT.run_route_picker(win, _add_tiles)
        except Exception as e:
            messagebox.showinfo(_L("Tuiles", "Tiles"), str(e), parent=win)

    MAP_IMG_MAX = 8

    def _draw_ovl():
        """Images basse résolution de la source posées sur les tuiles
        choisies (au-dessus du fond de carte, sous la grille et les
        contours). Redessinées à chaque zoom."""
        canvas.delete("ovl")
        st.setdefault("ovl_ph", {})
        st["ovl_ph"] = {}
        if Image is None or ImageTk is None:
            return
        for t_, im in list(st.get("ovl", {}).items()):
            try:
                x0, y0, x1, y1 = _rect(*t_)
                w_, h_ = max(1, int(x1 - x0)), max(1, int(y1 - y0))
                if w_ > 2048 or h_ > 2048:
                    continue
                ph = ImageTk.PhotoImage(im.resize((w_, h_)))
                canvas.create_image(x0, y0, anchor="nw", image=ph,
                                    tags=("ovl",))
                st["ovl_ph"][t_] = ph        # garder l'image (Tk)
            except Exception:
                pass
        try:
            canvas.tag_raise("grid")
            for ids in list(st["done_rects"].values()) + \
                    list(st["rects"].values()):
                for i_ in ids:
                    canvas.tag_raise(i_)
        except Exception:
            pass

    def _toggle_imagery():
        if st.get("ovl"):
            st["ovl"] = {}
            _draw_ovl()
            return
        tiles = sorted_tiles(st["sel"])[:MAP_IMG_MAX]
        if not tiles:
            messagebox.showinfo(_L("Imagerie", "Imagery"), _L(
                "Choisissez d'abord une ou plusieurs tuiles sur la carte "
                "(%d au plus)." % MAP_IMG_MAX,
                "First choose one or more tiles on the map (%d at most)."
                % MAP_IMG_MAX), parent=win)
            return
        jobs = []
        for (la, lo) in tiles:
            prov = resolve_provider(la, lo, _provider_choice())
            code, _note = preview_source(la, lo, prov)
            if code:
                jobs.append(((la, lo), code))
        box = {"done": 0, "res": {}}

        def _work():
            try:
                import O4_Imagery_Utils as IMG
                import O4_File_Names as FNAMES
            except Exception:
                box["done"] = len(jobs)
                return
            for (t_, code) in jobs:
                try:
                    f = FNAMES.preview(t_[0], t_[1], PREVIEW_ZL, code)
                    if not os.path.isfile(f):
                        IMG.create_tile_preview(t_[0], t_[1], PREVIEW_ZL,
                                                code)
                    if os.path.isfile(f):
                        im = Image.open(f).convert("RGB")
                        im.thumbnail((512, 512))
                        box["res"][t_] = im
                except Exception:
                    pass
                box["done"] += 1

        threading.Thread(target=_work, daemon=True).start()

        def _poll():
            prog_var.set(_L("🖼 Imagerie : %d / %d tuile(s)…",
                            "🖼 Imagery: %d / %d tile(s)…")
                         % (box["done"], len(jobs)))
            if box["done"] < len(jobs):
                win.after(400, _poll)
                return
            prog_var.set("")
            st["ovl"] = dict(box["res"])
            _draw_ovl()
            if not st["ovl"]:
                messagebox.showwarning(_L("Imagerie", "Imagery"), _L(
                    "La source n'a pas répondu.", "The source did not "
                    "answer."), parent=win)

        win.after(400, _poll)

    def _open_clouds():
        """Fenêtre des nuages (O4_Cloud_Utils) pour la tuile choisie (ou
        vide : la tuile se tape dans la fenêtre)."""
        tiles = sorted_tiles(st["sel"])
        try:
            import O4_Cloud_Utils as CL
            CL.run_cloud_window(win, tiles[0] if len(tiles) == 1 else None,
                                cbd=cbd)
        except Exception as e:
            messagebox.showinfo(_L("Nuages", "Clouds"), str(e), parent=win)

    def _open_zones():
        """Fenêtre des zones ZL de l'Expert (même fenêtre, mêmes règles,
        enregistrement dans le .cfg de la tuile) pour LA tuile choisie."""
        tiles = sorted_tiles(st["sel"])
        if len(tiles) != 1:
            messagebox.showinfo(
                _L("Zones plus nettes", "Sharper zones"),
                _L("Choisissez UNE seule tuile sur la carte, puis cliquez de "
                   "nouveau. Les zones dessinées sont enregistrées avec la "
                   "tuile et reprises par « Construire ».",
                   "Choose ONE tile only on the map, then click again. The "
                   "zones you draw are saved with the tile and used by "
                   "« Build »."), parent=win)
            return
        la, lo = tiles[0]
        try:
            w = getattr(expert_win, "custom_zl_window", None)
            try:
                w_open = w is not None and bool(w.winfo_exists())
            except Exception:
                w_open = False
            if w_open and \
                    (getattr(w, "lat", la), getattr(w, "lon", lo)) != (la, lo):
                messagebox.showinfo(
                    _L("Zones plus nettes", "Sharper zones"),
                    _L("La fenêtre des zones est déjà ouverte pour %s : "
                       "fermez-la d'abord." % short_latlon(w.lat, w.lon),
                       "The zones window is already open for %s: close it "
                       "first." % short_latlon(w.lat, w.lon)), parent=win)
                return
            expert_win.lat.set(la)
            expert_win.lon.set(lo)
            expert_win.open_custom_zl_window()
        except Exception as e:
            messagebox.showinfo(_L("Zones plus nettes", "Sharper zones"),
                                str(e), parent=win)

    def _search_airport(text):
        if apt["index"] is not None:
            try:
                import O4_Airport_Search_Utils as AS
                found = AS.search(text, apt["index"], limit=12)
            except Exception:
                found = []
            if found:
                _show_results(found, _L("Cliquez un résultat : la carte y va "
                                        "et sa tuile est choisie.",
                                        "Click a result: the map goes there "
                                        "and its tile is chosen."))
            else:
                _show_results([], _L("Aucun aéroport ni ville trouvé.",
                                     "No airport or city found."))
            return
        if apt["loading"]:
            return
        apt["loading"] = True
        box = {}

        def _work():
            try:
                import O4_Airport_Search_Utils as AS
                box["idx"] = AS.load_or_build_index(
                    progress=lambda f: box.__setitem__("p", f))
            except Exception:
                box["idx"] = []

        th = threading.Thread(target=_work, daemon=True)
        th.start()
        _show_results([], _L("Préparation de la liste des aéroports de "
                             "X-Plane (une seule fois, quelques secondes)…",
                             "Preparing X-Plane's airport list (once only, a "
                             "few seconds)…"))

        def _poll():
            if th.is_alive():
                if "p" in box:
                    res_info.set(_L("Préparation de la liste des aéroports… "
                                    "%d %%" % int(100 * box["p"]),
                                    "Preparing the airport list… %d %%"
                                    % int(100 * box["p"])))
                win.after(300, _poll)
                return
            apt["loading"] = False
            apt["index"] = box.get("idx") or []
            if not apt["index"]:
                apt["index"] = None
                _show_results([], _L(
                    "Liste des aéroports introuvable : indiquez une fois le "
                    "fichier scenery_packs.ini dans la Bibliothèque de tuiles "
                    "(Ortho4XP retrouvera X-Plane), ou tapez +46-003.",
                    "Airport list not found: set scenery_packs.ini once in the "
                    "Tile library (Ortho4XP will find X-Plane), or type "
                    "+46-003."))
                return
            _search_airport(text)

        win.after(300, _poll)

    def _goto(e=None):
        text = goto_var.get().strip()
        if not text:
            return
        many = parse_tile_list(text)
        if many:
            n = _add_tiles(many)
            res_info.set(_L("%d tuile(s) ajoutée(s) à la sélection.",
                            "%d tile(s) added to the selection.") % n)
            return
        p = parse_goto(text)
        if p is not None:
            _center_on(*p)
            return
        _search_airport(text)

    goto_entry.bind("<Return>", _goto)
    _btn(goto_f, "→", _goto).pack(side=tk.LEFT)

    def _current_settings():
        return {"quality": quality_spec(q_var.get(), _zl_from(zl_var.get()),
                                        _zl_from(apt_var.get()),
                                        bool(icao_var.get())),
                "src": src_var.get(), "colour": _colour(),
                "overlay": bool(ovl_var.get()),
                "install": bool(inst_var.get())}

    def _refresh_profiles(select=""):
        names = sorted(load_profiles())
        if prof_cb is not None:
            try:
                prof_cb.configure(values=names or [NO_PROF_TXT])
            except Exception:
                pass
        prof_var.set(select if select in names else
                     ("" if names else NO_PROF_TXT))

    def _apply_profile(name):
        d = load_profiles().get(name)
        if not d:
            return
        base, zl, apt = parse_quality(d.get("quality", DEFAULT_QUALITY))
        q_var.set(base)
        zl_var.set("ZL%d" % zl if zl else PROFILE_TXT)
        apt_var.set(NO_APT_TXT if apt == 0 else
                    ("ZL%d" % apt if apt else PROFILE_TXT))
        icao_var.set(quality_icao(d.get("quality", "")))
        if d.get("src") in (AUTO, EXPERT_SRC):
            src_var.set(d["src"])
        if d.get("colour") in COLOUR_CHOICES:
            colour_var.set(colour_label(d["colour"]))
        if "overlay" in d and ovl_src:
            ovl_var.set(bool(d["overlay"]))
        if "install" in d:
            inst_var.set(bool(d["install"]))
        _on_quality()

    def _ask_name(title, prompt, initial=""):
        """Petite fenêtre « nom » aux couleurs du thème (la boîte standard
        de Tk est illisible sur Mac avec un thème sombre). Renvoie le texte
        ou None (Annuler / fermeture)."""
        res = {"v": None}
        dlg = tk.Toplevel(win)
        dlg.title(title)
        dlg.configure(bg=BG)
        try:
            dlg.transient(win)
        except Exception:
            pass
        tk.Label(dlg, text=prompt, bg=BG, fg=FG, font=FONT, justify="left",
                 anchor="w", wraplength=340).pack(fill=tk.X, padx=14,
                                                  pady=(14, 6))
        var = tk.StringVar(value=initial or "")
        ent = tk.Entry(dlg, textvariable=var, width=32, font=FONT,
                       bg="#ffffff", fg="#000000", insertbackground="#000000",
                       highlightthickness=1, relief="flat")
        ent.pack(fill=tk.X, padx=14)
        row_ = tk.Frame(dlg, bg=BG)
        row_.pack(fill=tk.X, padx=14, pady=12)
        row_.columnconfigure(0, weight=1)
        row_.columnconfigure(1, weight=1)

        def _ok(e=None):
            res["v"] = var.get()
            dlg.destroy()

        def _cancel(e=None):
            dlg.destroy()

        _btn(row_, _L("Enregistrer", "Save"), _ok).grid(
            row=0, column=0, sticky="ew", padx=(0, 4))
        _btn(row_, _L("Annuler", "Cancel"), _cancel).grid(
            row=0, column=1, sticky="ew", padx=(4, 0))
        ent.bind("<Return>", _ok)
        dlg.bind("<Escape>", _cancel)
        try:
            dlg.protocol("WM_DELETE_WINDOW", _cancel)
            ent.focus_set()
            dlg.grab_set()
            win.wait_window(dlg)
        except Exception:
            pass
        return res["v"]

    win._gp_ask_name = _ask_name

    def _save_profile():
        try:
            name = win._gp_ask_name(
                _L("Mes réglages", "My settings"),
                _L("Nom de ces réglages (ex. « Aéroports nets ») :",
                   "Name for these settings (e.g. « Sharp airports »):"),
                prof_var.get() if prof_var.get() != NO_PROF_TXT else "")
        except Exception:
            name = None
        name = (name or "").strip()[:40]
        if not name:
            return
        profs = load_profiles()
        profs[name] = _current_settings()
        if save_profiles(profs):
            _refresh_profiles(name)
        else:
            messagebox.showwarning(_L("Mes réglages", "My settings"),
                                   _L("Enregistrement impossible.",
                                      "Could not save."), parent=win)

    def _delete_profile():
        name = prof_var.get()
        profs = load_profiles()
        if not name or name not in profs:
            return
        if not messagebox.askyesno(_L("Mes réglages", "My settings"),
                                   _L("Supprimer « %s » ?" % name,
                                      "Delete « %s »?" % name),
                                   default="no", parent=win):
            return
        profs.pop(name, None)
        save_profiles(profs)
        _refresh_profiles()

    def _on_quality():
        st["quality"] = quality_spec(q_var.get(), _zl_from(zl_var.get()),
                                     _zl_from(apt_var.get()),
                                     bool(icao_var.get()))
        q_help.set(quality_help(st["quality"]) + "\n→ "
                   + zl_summary(st["quality"]))

    # ============== 3. Vérification ==============
    def _set_summary(text):
        summary_box.config(state="normal")
        summary_box.delete("1.0", tk.END)
        summary_box.insert("1.0", text)
        summary_box.config(state="disabled")

    def _summary_lines(est_pack, extra=None):
        tiles = sorted_tiles(st["sel"])
        prov = _provider_choice()
        q = st["quality"]
        vals = quality_vals(q)
        lines = []
        lines.append(_L("Tuiles : ", "Tiles: ") + "%d  (%s)" % (
            len(tiles), ", ".join(short_latlon(*t) for t in tiles[:10])
            + (" …" if len(tiles) > 10 else "")))
        lines.append(_L("Qualité : ", "Quality: ") + quality_label(q).strip()
                     + "  (" + zl_summary(q) + ")")
        col = _colour()
        if col != "source":
            cs = cnorm_snapshot()
            lines.append(_L("Couleurs : ", "Colours: ") + colour_label(col)
                         + ("" if (cs is None or cs["enabled"]) else _L(
                             "  ⚠ sans effet : Color Normalize est désactivé "
                             "dans la fenêtre expert",
                             "  ⚠ no effect: Color Normalize is turned off "
                             "in the expert window")))
        if prov == AUTO:
            reason_txt = {
                "comb": _L("source combinée de la fenêtre expert",
                           "combined source of the expert window"),
                "national": _L("imagerie nationale sur la tuile",
                               "national imagery on the tile"),
                "defaut": _L("aucune source nationale ne couvre toute la "
                             "tuile → source de la fenêtre expert",
                             "no national source covers the whole tile → "
                             "expert window source")}
            lines.append(_L("Source d'imagerie (automatique) :",
                            "Imagery source (automatic):"))
            auto = (extra or {}).get("auto")
            if auto is None:
                lines.append(_L("   recherche de la meilleure source…",
                                "   looking for the best source…"))
            else:
                for t in tiles[:10]:
                    code, why = auto.get(t, (current_provider(), "defaut"))
                    lines.append("   %s : %s  (%s)" % (
                        short_latlon(*t), code, reason_txt.get(why, why)))
        else:
            lines.append(_L("Source d'imagerie : ", "Imagery source: ") + prov
                         + _L("  (choisie dans la fenêtre principale)",
                              "  (chosen in the main window)"))
        wd = working_dir(cbd)
        lines.append(_L("Dossier des tuiles : ", "Tiles folder: ") + wd)
        if inst_var.get():
            lines.append(_L("   ℹ Les tuiles seront installées dans X-Plane "
                            "à la fin (Custom Scenery + liste des scènes).",
                            "   ℹ The tiles will be installed into X-Plane at "
                            "the end (Custom Scenery + scenery list)."))
            xr = xplane_root_of_ini(xplane_ini())
            lines.append(_L("   X-Plane utilisé : ", "   X-Plane used: ")
                         + (xr or _L("pas encore choisi → « Changer de "
                                     "X-Plane… »",
                                     "not chosen yet → « Change X-Plane… »")))
        elif not is_in_custom_scenery(wd):
            lines.append(_L(
                "   ℹ Ce dossier n'est pas dans X-Plane : après la "
                "construction, cliquez « 📥 Installer / réinstaller dans "
                "X-Plane ».",
                "   ℹ This folder is not inside X-Plane: after the build, "
                "click « 📥 Install / reinstall into X-Plane »."))
        uptodate = (extra or {}).get("uptodate", [])
        rebuilt = [short_latlon(*t) for t in tiles if t in st["done"]
                   and short_latlon(*t) not in uptodate]
        if uptodate:
            lines.append(_L("   ℹ Déjà à jour (ne seront pas refaites) : ",
                            "   ℹ Already up to date (will not be redone): ")
                         + ", ".join(uptodate))
        if rebuilt:
            lines.append(_L("   ℹ Déjà construites (seront refaites) : ",
                            "   ℹ Already built (will be redone): ")
                         + ", ".join(rebuilt))
        if est_pack is None:
            lines.append(_L("Estimation : calcul en cours…",
                            "Estimate: computing…"))
        else:
            _res, gmin, gmax, tmin, tmax = est_pack
            n_ok = len([1 for _t, e in _res if e])
            if n_ok:
                lines.append(_L("Place disque estimée : ",
                                "Estimated disk space: ")
                             + "%.0f – %.0f Go" % (gmin, gmax))
                ntex = sum(int(e.get("total_textures", 0) or 0)
                           for _t, e in _res if e)
                ht = history_time(ntex)
                if ht:
                    tmin, tmax, nh = ht
                    lines.append(_L("Durée estimée : ", "Estimated time: ")
                                 + "%s – %s" % (fmt_duration(tmin),
                                                 fmt_duration(tmax))
                                 + _L("  (d'après vos %d dernières tuiles "
                                      "construites)" % nh,
                                      "  (from your last %d built tiles)"
                                      % nh))
                else:
                    lines.append(_L("Durée estimée : ", "Estimated time: ")
                                 + "%s – %s" % (fmt_duration(tmin),
                                                 fmt_duration(tmax))
                                 + _L("  (moyenne générale ; plus juste "
                                      "après votre première tuile)",
                                      "  (general average; more accurate "
                                      "after your first tile)"))
                if n_ok < len(_res):
                    lines.append(_L(
                        "   (estimation partielle : %d tuile(s) sur %d)"
                        % (n_ok, len(_res)),
                        "   (partial estimate: %d tile(s) of %d)"
                        % (n_ok, len(_res))))
            else:
                lines.append(_L("Estimation : indisponible (elle sera faite "
                                "au début de la construction).",
                                "Estimate: unavailable (it will be done at "
                                "the start of the build)."))
            free = free_space_go(wd)
            if free is not None:
                warn = ""
                if n_ok and free < gmin:
                    warn = _L("  ⚠ INSUFFISANT", "  ⚠ NOT ENOUGH")
                lines.append(_L("Place libre : ", "Free space: ")
                             + "%.0f Go" % free + warn)
        if vals["default_zl"] >= 17:
            try:
                import O4_Diagnostics_Utils as DG
                lvl = DG.xplane_texture_level()
                if lvl is not None and lvl < DG.TEX_MAX:
                    lines.append(_L(
                        "⚠ Qualité des textures de X-Plane réglée sur %d/%d : "
                        "cette netteté ne sera pas entièrement visible. Mettez "
                        "« Maximum » dans X-Plane ou choisissez « Rapide »."
                        % (lvl, DG.TEX_MAX),
                        "⚠ X-Plane texture quality set to %d/%d: this "
                        "sharpness will not be fully visible. Set « Maximum » "
                        "in X-Plane or choose « Fast »." % (lvl, DG.TEX_MAX)))
            except Exception:
                pass
        lines.append(_L("Estimations indicatives, jamais garanties.",
                        "Indicative estimates, never guaranteed."))
        return lines

    def _check():
        if not st["sel"]:
            _set_summary(_L("Choisissez d'abord au moins une tuile sur la "
                            "carte.", "First choose at least one tile on the "
                            "map."))
            return
        st["est_text"] = None
        _set_summary("\n".join(_summary_lines(None)))
        tiles = sorted_tiles(st["sel"])
        q = st["quality"]
        prov = _provider_choice()
        box = {}

        force = bool(force_var.get())

        def _work():
            extra = {"auto": None, "uptodate": []}
            if prov == AUTO:
                auto = {}
                for t in tiles:
                    try:
                        auto[t] = best_provider(t[0], t[1], current_provider())
                    except Exception:
                        auto[t] = (current_provider(), "defaut")
                extra["auto"] = auto
            for t in tiles:
                if force or t not in st["done"]:
                    continue
                try:
                    if is_up_to_date(make_tile(t[0], t[1], cbd, q, prov)):
                        extra["uptodate"].append(short_latlon(*t))
                except Exception:
                    pass
            box["extra"] = extra
            try:
                todo = [t for t in tiles
                        if short_latlon(*t) not in extra["uptodate"]]
                box["est"] = estimate_tiles(todo, cbd, q, prov)
            except Exception:
                box["est"] = ([], 0, 0, 0, 0)
            probs = []
            try:
                ok, msg = mount_check(make_tile(tiles[0][0], tiles[0][1],
                                                cbd, q, prov))
                if not ok and msg:
                    probs.append(msg)
            except Exception:
                pass
            try:
                import O4_Diagnostics_Utils as DG
                for f in DG.check_machine():
                    if f["sev"] in ("rouge", "orange"):
                        probs.append(DG.SEV_ICON.get(f["sev"], "") + " "
                                     + f["title"] + " — " + f["solution"])
                for f in DG.check_scenery():
                    if f["sev"] in ("rouge", "orange") and \
                            f.get("id") in ("dup_tiles", "order"):
                        probs.append(DG.SEV_ICON.get(f["sev"], "") + " "
                                     + f["title"] + " — " + _L(
                                         "Diagnostic → bouton 🔧.",
                                         "Diagnostic → 🔧 button."))
            except Exception:
                pass
            box["probs"] = probs

        th = threading.Thread(target=_work, daemon=True)
        th.start()

        def _poll():
            if th.is_alive():
                win.after(300, _poll)
                return
            lines = _summary_lines(box.get("est"), box.get("extra"))
            probs = box.get("probs") or []
            lines.append("")
            if probs:
                lines.append(_L("Problèmes détectés :", "Problems found:"))
                lines.extend("  " + p for p in probs)
            else:
                lines.append(_L("✅ Aucun problème détecté : vous pouvez "
                                "construire.",
                                "✅ No problem found: you can build."))
            _set_summary("\n".join(lines))

        win.after(300, _poll)

    # ============== 4. Construction ==============
    def _mini(txt):
        try:
            mini_var.set(txt)
        except Exception:
            pass

    def _poll_build():
        r = st["runner"]
        if r is None:
            return
        s = r.state
        n = max(1, s["n"])
        el = time.time() - (s["t0"] or time.time())
        if s["running"]:
            # Étape en cours de chaque tuile (lecture seule du journal).
            try:
                new, s["log_pos"] = read_new_log_lines(log_file_path(),
                                                       s.get("log_pos"))
                parse_step_lines(new, s.setdefault("steps", {}))
            except Exception:
                pass
            steps = s.get("steps") or {}
            keep = _L("Le travail continue même si l'écran semble figé : "
                      "ne fermez pas Ortho4XP.\n",
                      "Work goes on even if the screen seems frozen: do "
                      "not close Ortho4XP.\n")
            if st["hide_expert"]:
                detail = _L("Détail technique : bouton « Passer en mode "
                            "expert ».",
                            "Technical details: « Switch to expert mode » "
                            "button.")
            else:
                detail = _L("Le détail s'affiche dans la fenêtre principale.",
                            "Details are shown in the main window.")
            if getattr(r, "parallel", 1) > 1:
                ph3 = ", ".join(s.get("phase3") or []) or "—"
                prep = s["current"] or "—"
                per = []
                for name in ([prep] if prep != "—" else []) + list(
                        s.get("phase3") or []):
                    sd = steps.get(name)
                    if sd and name not in [x.split(" ")[0] for x in per]:
                        try:
                            idx = STEP_ORDER.index(sd["step"]) + 1
                        except ValueError:
                            continue
                        per.append(_L("%s : étape %d / %d (%s)",
                                      "%s: step %d / %d (%s)")
                                   % (name, idx, len(STEP_ORDER),
                                      step_label(sd["step"])))
                prog_var.set(_L("Tuiles terminées : %d / %d\n"
                                "Préparation : %s · Images (en même "
                                "temps) : %s\n(%s écoulées)\n"
                                % (s["k"], n, prep, ph3, fmt_duration(el)),
                                "Tiles finished: %d / %d\n"
                                "Preparing: %s · Imagery (at the same "
                                "time): %s\n(%s elapsed)\n"
                                % (s["k"], n, prep, ph3, fmt_duration(el)))
                             + ("\n".join(per) + "\n" if per else "")
                             + keep + detail)
                frac = 100.0 * s["k"] / n
                _mini(_L("▶ %d / %d tuile(s) terminée(s)",
                         "▶ %d / %d tile(s) done") % (s["k"], n))
            else:
                sd = steps.get(s["current"])
                sline, tile_pct = "", 0.0
                if sd:
                    pct, rem = (None, None)
                    nbr = STEP_BAR.get(sd["step"])
                    if nbr and not sd["done"]:
                        pct, rem = engine_bar_percent(nbr)
                    sline = step_line(sd["step"], sd["done"], pct, rem)
                    tile_pct = step_progress(sd["step"], sd["done"], pct)
                prog_var.set(_L("Tuile %d / %d : %s\nConstruction en cours… "
                                "(%s écoulées)\n"
                                % (s["k"], n, s["current"], fmt_duration(el)),
                                "Tile %d / %d: %s\nBuilding… (%s elapsed)\n"
                                % (s["k"], n, s["current"], fmt_duration(el)))
                             + (sline + "\n" if sline else "")
                             + keep + detail)
                frac = (100.0 * (s["k"] - 1) + tile_pct) / n
                mini = "▶ " + str(s["current"])
                if sd:
                    try:
                        mini += _L(" · étape %d/5", " · step %d/5") % (
                            STEP_ORDER.index(sd["step"]) + 1)
                    except ValueError:
                        pass
                mini += " · %d %%" % int(frac)
                _mini(mini)
            if pbar is not None:
                try:
                    pbar["value"] = frac
                except Exception:
                    pass
            win.after(500, _poll_build)
            return
        if pbar is not None:
            try:
                pbar["value"] = 100.0 * len(s["ok"]) / n
            except Exception:
                pass
        _mini((_L("✅ Terminé", "✅ Finished") if not s["failed"] else
               _L("⚠ Terminé avec échec(s)", "⚠ Finished with failure(s)"))
              + _L(" — onglet 4", " — tab 4"))
        msg = s.get("message") or ""
        res = _L("Terminé en %s.\n" % fmt_duration(el),
                 "Finished in %s.\n" % fmt_duration(el))
        res += _L("✅ Réussies : ", "✅ Succeeded: ") + (
            ", ".join(s["ok"]) or "—") + "\n"
        if s.get("skipped"):
            res += _L("⏭ Déjà à jour (non refaites) : ",
                      "⏭ Already up to date (not redone): ") + ", ".join(
                s["skipped"]) + "\n"
        if s.get("install"):
            res += install_report_text(s["install"]) + "\n"
        if s.get("incomplete"):
            res += _L("⚠ Images incomplètes (non installées dans X-Plane) : ",
                      "⚠ Incomplete images (not installed into X-Plane): ") \
                + ", ".join("%s (%d)" % (t, len(v)) for t, v in
                            sorted(s["incomplete"].items())) \
                + _L("\n→ Diagnostic → « 🔧 Réparer les images blanches », "
                     "puis « 📥 Installer ».",
                     "\n→ Diagnostic → « 🔧 Repair white images », then "
                     "« 📥 Install ».") + "\n"
        if s["failed"]:
            res += _L("❌ En échec : ", "❌ Failed: ") + ", ".join(s["failed"])
            res += _L("\n→ Ouvrez le Diagnostic pour savoir pourquoi.",
                      "\n→ Open the Diagnostic to find out why.")
        if r.stop_asked:
            res += _L("\n(Construction arrêtée à votre demande.)",
                      "\n(Build stopped at your request.)")
        if r.stop_asked or s["failed"]:
            res += _L("\n↻ Pour reprendre : gardez la même sélection et "
                      "cliquez « Construire » — les tuiles déjà terminées "
                      "seront sautées.",
                      "\n↻ To resume: keep the same selection and click "
                      "« Build » — tiles already finished will be skipped.")
        prog_var.set((msg + "\n" if msg else "") + res)
        st["runner"] = None
        _draw_done()
        if s["ok"] and not r.stop_asked:
            try:
                win.after(400, lambda: _offer_cleanup(list(s["ok"])))
            except Exception:
                pass

    def _offer_cleanup(names):
        """Point 6 : proposer d'effacer les images téléchargées des tuiles
        qui viennent d'être construites (jamais sans accord)."""
        BC = _comfort()
        if BC is None:
            return
        try:
            import O4_File_Names as FNAMES
            imagery = FNAMES.Imagery_dir
        except Exception:
            return
        paths = []
        for name in names:
            m = re.match(r"^([+-]\d\d)([+-]\d\d\d)$", name)
            if m:
                paths += BC.tile_jpgs(int(m.group(1)), int(m.group(2)),
                                      imagery)
        if not paths:
            return
        go = BC.files_size_go(paths)
        if not messagebox.askyesno(
                _L("Images téléchargées", "Downloaded images"),
                _L("La construction est finie. Les images téléchargées pour "
                   "%s occupent %.1f Go.\n\n"
                   "Souhaitez-vous les SUPPRIMER pour libérer la place ?\n\n"
                   "• Oui : place libérée. La tuile reste complète dans "
                   "X-Plane, mais la reconstruire plus tard (autre qualité, "
                   "correction) sera plus long : tout sera retéléchargé.\n"
                   "• Non : les images sont conservées (reconstruction "
                   "rapide)." % (", ".join(names), go),
                   "The build is finished. The images downloaded for %s use "
                   "%.1f GB.\n\n"
                   "Do you want to DELETE them to free the space?\n\n"
                   "• Yes: space freed. The tile stays complete in X-Plane, "
                   "but rebuilding it later (other quality, correction) will "
                   "take longer: everything will be downloaded again.\n"
                   "• No: the images are kept (fast rebuild)."
                   % (", ".join(names), go)),
                default="no", parent=win):
            return
        n = BC.delete_files(paths)
        messagebox.showinfo(_L("Images téléchargées", "Downloaded images"),
                            _L("%d image(s) supprimée(s), %.1f Go libérés."
                               % (n, go),
                               "%d image(s) deleted, %.1f GB freed."
                               % (n, go)), parent=win)

    def _build():
        if st["runner"] is not None:
            r0 = st["runner"]
            new = [t for t in sorted_tiles(st["sel"]) if t not in r0.tiles]
            if not new:
                messagebox.showinfo(_L("Construction", "Build"),
                                    _L("Une construction est en cours. "
                                       "Choisissez d'autres tuiles pour les "
                                       "mettre en file d'attente.",
                                       "A build is running. Choose other "
                                       "tiles to queue them."), parent=win)
                return
            if messagebox.askyesno(
                    _L("File d'attente", "Queue"),
                    _L("Une construction est en cours. Ajouter %d tuile(s) "
                       "à la file d'attente ? Elles seront construites à la "
                       "suite : %s" % (len(new), ", ".join(
                           short_latlon(*t) for t in new[:8])),
                       "A build is running. Add %d tile(s) to the queue? "
                       "They will be built afterwards: %s" % (len(new),
                       ", ".join(short_latlon(*t) for t in new[:8]))),
                    parent=win):
                r0.add_tiles(new)
            return
        if not st["sel"]:
            messagebox.showinfo(_L("Construction", "Build"),
                                _L("Choisissez d'abord au moins une tuile sur "
                                   "la carte.",
                                   "First choose at least one tile on the "
                                   "map."), parent=win)
            return
        tiles = sorted_tiles(st["sel"])
        q = st["quality"]
        if not messagebox.askyesno(
                _L("Construire", "Build"),
                _L("Construire %d tuile(s) en qualité « %s » ?\n\nCela peut "
                   "prendre longtemps. Vous pouvez continuer à utiliser "
                   "l'ordinateur." % (len(tiles), quality_label(q).strip()),
                   "Build %d tile(s) in « %s » quality?\n\nThis can take a "
                   "long time. You can keep using the computer."
                   % (len(tiles), quality_label(q).strip())), parent=win):
            return
        r = BuildRunner(tiles, cbd, q, _provider_choice(),
                        bool(ovl_var.get()) and bool(ovl_src),
                        force=bool(force_var.get()),
                        install=bool(inst_var.get()),
                        parallel=(1 if getattr(sys, "frozen", False) else
                                  suggested_parallel_tiles(
                                      os.cpu_count(), total_ram_go(),
                                      len(tiles))),
                        colour=_colour())
        st["runner"] = r
        try:
            _show_tab(3)
        except Exception:
            pass
        if not r.start():
            st["runner"] = None
            messagebox.showinfo(_L("Construction", "Build"),
                                r.state.get("message", ""), parent=win)
            return
        win.after(300, _poll_build)

    def _preview():
        """Point 2 : image basse résolution de la tuile avec la source
        retenue (fonction du moteur IMG.create_tile_preview, fichier rangé
        dans Previews/ comme l'Expert). Téléchargement en arrière-plan."""
        tiles = sorted_tiles(st["sel"])
        if not tiles:
            messagebox.showinfo(_L("Aperçu", "Preview"),
                                _L("Choisissez d'abord une tuile sur la "
                                   "carte.",
                                   "First choose a tile on the map."),
                                parent=win)
            return
        lat, lon = tiles[0]
        prov = resolve_provider(lat, lon, _provider_choice())
        code, note = preview_source(lat, lon, prov)
        if not code:
            messagebox.showinfo(_L("Aperçu", "Preview"), note, parent=win)
            return
        box = {"done": False, "ok": False, "file": ""}

        def _work():
            try:
                import O4_Imagery_Utils as IMG
                import O4_File_Names as FNAMES
                box["file"] = FNAMES.preview(lat, lon, PREVIEW_ZL, code)
                box["ok"] = bool(IMG.create_tile_preview(lat, lon, PREVIEW_ZL,
                                                         code))
            except Exception:
                box["ok"] = False
            box["done"] = True

        threading.Thread(target=_work, daemon=True).start()
        prog_var.set(_L("👁 Aperçu de %s en préparation (source %s)…",
                        "👁 Preparing preview of %s (source %s)…")
                     % (short_latlon(lat, lon), code))

        def _poll():
            if not box["done"]:
                win.after(500, _poll)
                return
            prog_var.set("")
            if not (box["ok"] and os.path.isfile(box["file"])):
                messagebox.showwarning(
                    _L("Aperçu", "Preview"),
                    _L("Aperçu impossible : la source %s n'a pas répondu."
                       % code, "Preview impossible: source %s did not "
                       "answer." % code), parent=win)
                return
            _show_preview(box["file"], lat, lon, code, note)

        win.after(500, _poll)

    def _show_preview(path, lat, lon, code, note):
        if Image is None or ImageTk is None:
            return
        try:
            im = Image.open(path)
            side = int(min(win.winfo_screenwidth(),
                           win.winfo_screenheight()) * 0.7)
            im.thumbnail((side, side))
            ph = ImageTk.PhotoImage(im)
        except Exception:
            return
        top = tk.Toplevel(win)
        top.title(_L("Aperçu ", "Preview ") + short_latlon(lat, lon)
                  + " — " + code)
        top.configure(bg=BG)
        col = _colour()
        if col != "source":
            # Avant / après, côte à côte (moitié de la place chacun)
            try:
                im2 = im.copy()
                im2.thumbnail((side // 2, side // 2))
                ph_a = ImageTk.PhotoImage(im2)
                ph_b = ImageTk.PhotoImage(colour_preview(im2, col))
            except Exception:
                ph_a = ph_b = None
            if ph_a is not None:
                row_ = tk.Frame(top, bg=BG)
                row_.pack(padx=8, pady=8)
                for i_, (ph_, txt_) in enumerate((
                        (ph_a, _L("Comme la source", "As the source")),
                        (ph_b, _L("Avec vos couleurs (%s)",
                                  "With your colours (%s)")
                         % colour_label(col)))):
                    tk.Label(row_, text=txt_, bg=BG, fg=FG,
                             font=FONT_S).grid(row=0, column=i_)
                    lbx = tk.Label(row_, image=ph_, bg=BG)
                    lbx.image = ph_      # garder l'image (ramasse-miettes Tk)
                    lbx.grid(row=1, column=i_, padx=4)
                top._gp_images = [ph, ph_a, ph_b]
                tk.Label(top, text=(note + "\n" if note else "") + _L(
                    "Image basse résolution, couleurs indicatives : la tuile "
                    "construite sera bien plus nette.",
                    "Low-resolution image, colours as a guide: the built "
                    "tile will be much sharper."), bg=BG, fg=FG,
                    font=FONT_S, wraplength=max(300, side)).pack(
                    padx=8, pady=(0, 8))
                return
        lb = tk.Label(top, image=ph, bg=BG)
        lb.image = ph                    # garder l'image (ramasse-miettes Tk)
        lb.pack(padx=8, pady=8)
        tk.Label(top, text=(note + "\n" if note else "") + _L(
            "Image basse résolution : la tuile construite sera bien plus "
            "nette.", "Low-resolution image: the built tile will be much "
            "sharper."), bg=BG, fg=FG, font=FONT_S,
            wraplength=max(300, im.size[0])).pack(padx=8, pady=(0, 8))

    def _install():
        if st["runner"] is not None:
            messagebox.showinfo(_L("Installer", "Install"),
                                _L("Attendez la fin de la construction.",
                                   "Wait until the build ends."), parent=win)
            return
        _draw_done()
        tiles = [t for t in sorted_tiles(st["sel"]) if t in st["done"]]
        if not tiles:
            messagebox.showinfo(
                _L("Installer", "Install"),
                _L("Choisissez sur la carte une ou plusieurs tuiles déjà "
                   "construites (en vert).",
                   "Choose on the map one or more tiles already built "
                   "(green)."), parent=win)
            return
        try:
            import O4_Config_Utils as CFG
            found = st.get("done_dirs") or {}
            dirs = []
            for t in tiles:
                bd = CFG.Tile(t[0], t[1], cbd).build_dir
                if not os.path.isdir(bd) and found.get(t):
                    bd = found[t]
                dirs.append(bd)
        except Exception as e:
            messagebox.showerror(_L("Installer", "Install"), str(e),
                                 parent=win)
            return
        rep_ = install_in_xplane(dirs)
        txt_ = install_report_text(rep_) or _L("Rien à faire.",
                                               "Nothing to do.")
        (messagebox.showinfo if all(k for (_n, k, _m) in rep_)
         else messagebox.showwarning)(_L("Installer", "Install"), txt_,
                                      parent=win)

    def _unqueue():
        """Les tuiles en attente que l'utilisateur a retirées de la carte
        (clic) sortent de la file. Celles déjà commencées restent."""
        r = st["runner"]
        if r is None or not r.state.get("running"):
            messagebox.showinfo(_L("File d'attente", "Queue"), _L(
                "Aucune construction en cours.", "No build running."),
                parent=win)
            return
        gone = [t for t in r.pending_tiles() if t not in st["sel"]]
        if not gone:
            messagebox.showinfo(_L("File d'attente", "Queue"), _L(
                "Pour retirer une tuile en attente : cliquez-la sur la carte "
                "(elle n'est plus choisie), puis ce bouton.",
                "To remove a waiting tile: click it on the map (it is no "
                "longer chosen), then this button."), parent=win)
            return
        removed = r.remove_tiles(gone)
        messagebox.showinfo(_L("File d'attente", "Queue"), _L(
            "Retirée(s) de la file : ", "Removed from the queue: ")
            + ", ".join(short_latlon(*t) for t in removed), parent=win)

    def _stop():
        r = st["runner"]
        if r is None:
            return
        if messagebox.askyesno(
                _L("Arrêter", "Stop"),
                _L("Arrêter la construction ? La tuile en cours ne sera pas "
                   "terminée.",
                   "Stop the build? The current tile will not be finished."),
                parent=win):
            r.stop()

    def _open_module(mod_name, entry):
        try:
            import importlib
            mod = importlib.import_module(mod_name)
            fn = getattr(mod, entry, None)
            if callable(fn):
                fn(win)
        except Exception:
            pass

    def _switch_lang(code):
        """Change la langue (FR/EN) puis redémarre Ortho4XP dans le même
        mode. Refusé pendant une construction."""
        cur = "FR" if _lang_code() == "fr" else "EN"
        if code == cur:
            return
        if st["runner"] is not None and st["runner"].state.get("running"):
            messagebox.showinfo(
                _L("Langue", "Language"),
                _L("Attendez la fin de la construction pour changer de "
                   "langue.", "Wait for the build to finish before changing "
                   "the language."), parent=win)
            lang_var.set(cur)
            return
        if not messagebox.askyesno(
                _L("Langue", "Language"),
                _L("Ortho4XP va redémarrer en anglais. Continuer ?",
                   "Ortho4XP will restart in French. Continue?"),
                parent=win):
            lang_var.set(cur)
            return
        if not restart_with_lang(code, simple=st["hide_expert"]):
            messagebox.showerror(
                _L("Langue", "Language"),
                _L("Redémarrage impossible : relancez Ortho4XP vous-même.",
                   "Restart impossible: start Ortho4XP again yourself."),
                parent=win)
            return
        try:
            fn = getattr(expert_win, "exit_prg", None)
            if callable(fn):
                fn()
            else:
                (expert_win or win).destroy()
        except Exception:
            try:
                win.destroy()
            except Exception:
                pass

    def _on_close():
        running = (st["runner"] is not None
                   and st["runner"].state.get("running"))
        if st["hide_expert"]:
            # Fenêtre expert cachée : fermer = quitter Ortho4XP (sinon un
            # Ortho4XP invisible resterait ouvert à l'insu du débutant).
            if running and not messagebox.askyesno(
                    _L("Quitter", "Quit"),
                    _L("Une construction est en cours : quitter Ortho4XP "
                       "l'arrêtera. Quitter quand même ?",
                       "A build is running: quitting Ortho4XP will stop it. "
                       "Quit anyway?"), parent=win):
                return
            try:
                fn = getattr(expert_win, "exit_prg", None)
                if callable(fn):
                    fn()          # même fermeture que la fenêtre expert
                else:
                    expert_win.destroy()
            except Exception:
                try:
                    win.destroy()
                except Exception:
                    pass
            return
        if running:
            if not messagebox.askyesno(
                    _L("Fermer", "Close"),
                    _L("Une construction est en cours. Elle continuera en "
                       "arrière-plan. Fermer cette fenêtre ?",
                       "A build is running. It will continue in the "
                       "background. Close this window?"), parent=win):
                return
        try:
            win.destroy()
        except Exception:
            pass

    try:
        win.protocol("WM_DELETE_WINDOW", _on_close)
    except Exception:
        pass

    # Taille plafonnée à l'écran réel (règle Bible)
    try:
        w = min(1280, int(win.winfo_screenwidth() * 0.95))
        h = min(860, int(win.winfo_screenheight() * 0.90))
        win.geometry("%dx%d" % (w, h))
        win.minsize(min(760, w), min(520, h))
    except Exception:
        pass

    _draw_grid()
    _draw_done()
    _refresh_sel_label()
    # Centre initial : tuile active de la fenêtre principale, sinon Europe
    lat0, lon0 = 46.5, 2.5
    try:
        import O4_UI_Utils as UI
        g = getattr(UI, "gui", None)
        if g is not None:
            lat0 = int(g.lat.get()) + 0.5
            lon0 = int(g.lon.get()) + 0.5
    except Exception:
        pass
    win.update_idletasks()
    _center_on(lat0, lon0)
    win.lift()
    try:
        win.focus_force()
    except Exception:
        pass
    if st["hide_expert"]:
        try:
            expert_win.withdraw()
        except Exception:
            st["hide_expert"] = False
    _show_licence_once(tk, win, (BG, FG), _btn, FONT, lambda: None)
    return win


def restart_with_lang(code, simple=True, popen=None):
    """Enregistre la langue (O4_Lang._write_lang_to_cfg, fonction existante)
    puis relance Ortho4XP.py avec le même Python, dans le même mode
    (O4X_START_MODE=simple, ou expert si simple=False). Renvoie True si la
    relance est partie. popen injectable pour les tests."""
    try:
        import O4_Lang
        O4_Lang._write_lang_to_cfg(code)
    except Exception:
        return False
    root = _root_dir()
    script = os.path.join(root, "Ortho4XP.py")
    if not os.path.isfile(script):
        return False
    env = os.environ.copy()
    env["PYTHONPATH"] = os.path.join(root, "src")
    if simple:
        env["O4X_START_MODE"] = "simple"
    else:
        env.pop("O4X_START_MODE", None)
    try:
        if popen is None:
            import subprocess
            popen = subprocess.Popen
        popen([sys.executable, script], cwd=root, env=env)
        return True
    except Exception:
        return False


def _open_path(p):
    try:
        if sys.platform.startswith("dar"):
            import subprocess
            subprocess.Popen(["open", p])
        elif sys.platform.startswith("win"):
            os.startfile(p)  # noqa
        else:
            import subprocess
            subprocess.Popen(["xdg-open", p])
    except Exception:
        pass
