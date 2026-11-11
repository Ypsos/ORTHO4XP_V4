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
O4_XP12_Relief_Utils.py — Relief d'X-Plane 12 comme source d'altitude.

MODULE AUTONOME (100 % additif). Utilisé par O4_DEM_Utils (source « XP12 »
du menu custom_dem). Aucun accès réseau, aucun tkinter, AUCUNE écriture dans
X-Plane : le fichier DSF de la scène mondiale d'X-Plane 12 est seulement LU.

Principe
  1. Trouver le DSF de la tuile dans la scène mondiale installée :
     <X-Plane 12>/Global Scenery/X-Plane 12 Global Scenery/Earth nav data/
     <+L0+LL0>/<+LL+LLL>.dsf
     (dossier X-Plane déduit de « custom_scenery_dir » de la configuration,
     sinon du scenery_packs.ini mémorisé par la Bibliothèque de tuiles).
  2. L'outil DSFTool fourni avec Ortho4XP (Utils/mac|win|lin) le convertit
     en texte dans un dossier temporaire ; il écrit à part la grille
     d'altitude « elevation » (fichier .raw, décrit par une ligne
     RASTER_DATA : largeur, hauteur, octets par point, signé, échelle).
  3. La grille est enregistrée au format .hgt (entiers 16 bits, nord en
     haut), que le moteur sait déjà lire sans aucun module externe
     (read_elevation_from_file, branche .hgt).
Le fichier obtenu est rangé à côté des autres données d'altitude
(<base>_XP12.hgt) et réutilisé aux constructions suivantes.

Compatible macOS, Windows, Linux (DSFTool de chaque système).
"""

import os
import re
import sys
import shutil
import tempfile
import subprocess


def _L(fr, en):
    try:
        from O4_Lang import current_lang
        return fr if str(current_lang()).upper().startswith("FR") else en
    except Exception:
        return fr


# ------------------------------------------------------------------------------
# Chemins
# ------------------------------------------------------------------------------
def _tile_names(lat, lon):
    short = "%+03d%+04d" % (lat, lon)
    rlat = (lat // 10) * 10
    rlon = (lon // 10) * 10
    return "%+03d%+04d" % (rlat, rlon), short


def global_dsf_path(xplane_root, lat, lon):
    """PUR. Chemin du DSF de la tuile dans la scène mondiale X-Plane 12."""
    folder, short = _tile_names(lat, lon)
    return os.path.join(xplane_root, "Global Scenery",
                        "X-Plane 12 Global Scenery", "Earth nav data",
                        folder, short + ".dsf")


def _is_xplane_root(path):
    return bool(path) and os.path.isdir(os.path.join(
        path, "Global Scenery", "X-Plane 12 Global Scenery", "Earth nav data"))


def find_xplane_root():
    """Dossier racine d'X-Plane 12, ou "" si introuvable."""
    cands = []
    try:
        import O4_Config_Utils as CFG
        csd = getattr(CFG, "custom_scenery_dir", "") or ""
        if csd:
            cands.append(os.path.dirname(os.path.normpath(csd)))
    except Exception:
        pass
    try:
        import O4_Tile_Library_Utils as TL
        ini = TL.load_saved_ini_path() or TL.guess_ini_path()
        if ini:
            cands.append(os.path.dirname(os.path.dirname(
                os.path.normpath(ini))))
    except Exception:
        pass
    for c in cands:
        if _is_xplane_root(c):
            return c
    return ""


def dsftool_path():
    try:
        import O4_File_Names as FNAMES
        utils = FNAMES.Utils_dir
    except Exception:
        utils = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "Utils")
    if sys.platform == "darwin":
        return os.path.join(utils, "mac", "DSFTool")
    if sys.platform.startswith("win"):
        return os.path.join(utils, "win", "DSFTool.exe")
    return os.path.join(utils, "lin", "DSFTool")


def xp12_file_name(lat, lon):
    import O4_File_Names as FNAMES
    return FNAMES.base_file_name(lat, lon) + "_XP12.hgt"


# ------------------------------------------------------------------------------
# Lecture de la grille d'altitude
# ------------------------------------------------------------------------------
_RX_RASTER = re.compile(
    r"^RASTER_DATA\s+version=(\d+)\s+bpp=(\d+)\s+flags=(\d+)\s+width=(\d+)"
    r"\s+height=(\d+)\s+scale=([-0-9.eE+]+)\s+offset=([-0-9.eE+]+)\s+(.+)$")


def raster_defs(text_lines):
    """PUR. [(nom, {bpp, flags, width, height, scale, offset, file})] dans
    l'ordre du fichier texte DSFTool (les RASTER_DEF donnent les noms, les
    RASTER_DATA, dans le même ordre, la description)."""
    names, datas = [], []
    for ln in text_lines:
        ln = ln.strip()
        if ln.startswith("RASTER_DEF "):
            names.append(ln.split(None, 1)[1].strip())
        else:
            m = _RX_RASTER.match(ln)
            if m:
                datas.append({"bpp": int(m.group(2)),
                              "flags": int(m.group(3)),
                              "width": int(m.group(4)),
                              "height": int(m.group(5)),
                              "scale": float(m.group(6)),
                              "offset": float(m.group(7)),
                              "file": m.group(8).strip()})
    return list(zip(names, datas))


def raw_to_hgt(raw_path, info, hgt_path):
    """Grille DSF (ligne 0 = SUD, petit-boutiste) → .hgt (ligne 0 = NORD,
    gros-boutiste, entiers 16 bits signés, mètres). Renvoie (min, max)."""
    import numpy
    bpp, flags = info["bpp"], info["flags"]
    w, h = info["width"], info["height"]
    signed = bool(flags & 1)
    if bpp == 2:
        dt = numpy.dtype("<i2" if signed else "<u2")
    elif bpp == 1:
        dt = numpy.dtype("i1" if signed else "u1")
    elif bpp == 4:
        dt = numpy.dtype("<f4")
    else:
        raise ValueError("bpp %d" % bpp)
    a = numpy.fromfile(raw_path, dtype=dt)
    if a.size != w * h:
        raise ValueError("raster size %d != %d x %d" % (a.size, w, h))
    a = a.reshape((h, w)).astype(numpy.float64)
    a = a * info["scale"] + info["offset"]
    a = numpy.flipud(a)
    out = numpy.clip(numpy.round(a), -32767, 32767).astype(">i2")
    d = os.path.dirname(hgt_path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    tmp = hgt_path + ".tmp"
    out.tofile(tmp)
    os.replace(tmp, hgt_path)
    return (float(a.min()), float(a.max()))


def extract_elevation(lat, lon, hgt_path=None, xplane_root=None,
                      dsftool=None, run=None, log=None):
    """Fabrique le .hgt de la tuile depuis X-Plane 12. Renvoie le chemin du
    .hgt, ou "" (message dans log) si impossible."""
    log = log or (lambda *a: None)
    run = run or subprocess.run
    root = xplane_root if xplane_root is not None else find_xplane_root()
    if not root:
        log(_L("    X-Plane 12 introuvable (réglez « custom_scenery_dir » "
               "dans la configuration).",
               "    X-Plane 12 not found (set « custom_scenery_dir » in the "
               "configuration)."))
        return ""
    dsf = global_dsf_path(root, lat, lon)
    if not os.path.isfile(dsf):
        log(_L("    Pas de scène X-Plane 12 pour cette tuile : ",
               "    No X-Plane 12 scenery for this tile: ") + dsf)
        return ""
    tool = dsftool or dsftool_path()
    if not os.path.isfile(tool):
        log(_L("    Outil DSFTool absent : ", "    DSFTool missing: ") + tool)
        return ""
    hgt_path = hgt_path or xp12_file_name(lat, lon)
    tmp = tempfile.mkdtemp(prefix="o4x_xp12_")
    try:
        out_txt = os.path.join(tmp, "dsf.txt")
        kw = {"capture_output": True, "timeout": 600}
        if sys.platform.startswith("win") and \
                hasattr(subprocess, "CREATE_NO_WINDOW"):
            kw["creationflags"] = subprocess.CREATE_NO_WINDOW
        r = run([tool, "--dsf2text", dsf, out_txt], **kw)
        if getattr(r, "returncode", 1) != 0 or not os.path.isfile(out_txt):
            log(_L("    DSFTool n'a pas pu lire ", "    DSFTool could not "
                   "read ") + dsf)
            return ""
        with open(out_txt, "r", encoding="utf-8", errors="replace") as f:
            head = []
            n_def = n_data = 0
            for ln in f:
                if ln.startswith("RASTER_DEF"):
                    head.append(ln)
                    n_def += 1
                elif ln.startswith("RASTER_DATA"):
                    head.append(ln)
                    n_data += 1
                elif n_def and n_data >= n_def:
                    break
        defs = dict(raster_defs(head))
        info = defs.get("elevation")
        if not info:
            log(_L("    Pas d'altitudes dans ", "    No elevation in ") + dsf)
            return ""
        raw = info["file"]
        if not os.path.isabs(raw):
            raw = os.path.join(tmp, os.path.basename(raw))
        if not os.path.isfile(raw):
            raw = out_txt + ".elevation.raw"
        mn, mx = raw_to_hgt(raw, info, hgt_path)
        log(_L("    Relief X-Plane 12 : %s (min %.0f m / max %.0f m)",
               "    X-Plane 12 relief: %s (min %.0f m / max %.0f m)")
            % (os.path.basename(hgt_path), mn, mx))
        return hgt_path
    except Exception as e:
        log(_L("    Relief X-Plane 12 impossible : ",
               "    X-Plane 12 relief impossible: ") + str(e))
        return ""
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
