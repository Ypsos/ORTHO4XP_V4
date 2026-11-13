# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2024-2026 Roland (Ypsos)
#
# CRÉDIT — AUTEUR : Roland (Ypsos) — Novembre 2026
# Module conçu et spécifié par Roland (Ypsos) pour Ortho4XP V3.
# Cette notice d'auteur et de copyright doit être conservée
# conformément à la GPLv3.
# Licence : GPLv3 + conditions additionnelles (art. 7),
# voir AVERTISSEMENT_LICENCE_LEGAL.md, section 16.
# ============================================================
# Copyright (c) 2024-2026 Roland (Ypsos)
#
# CREDIT — AUTHOR: Roland (Ypsos) — November 2026
# Module designed and specified by Roland (Ypsos) for Ortho4XP V3.
# This authorship and copyright notice must be retained
# in accordance with GPLv3.
# License: GPLv3 + additional terms (Sec. 7),
# see AVERTISSEMENT_LICENCE_LEGAL.md, Section 16.
# ============================================================
"""
O4_Image_Repair_Utils.py — Réparer les images blanches (retéléchargement
ciblé), appelé depuis le Diagnostic.

MODULE AUTONOME (100 % additif) : le moteur n'est pas modifié.

PRINCIPE (lu dans le vrai code)
  - Le moteur signale lui-même, dans Ortho4XP.log, les images en cause :
      « WARNING: <image>.jpg contains N pure white block(s) … »
      « Part of image <image>.jpg could not be obtained … filled with white »
  - À l'étape 3, une texture n'est refaite QUE si son DDS est absent
    (O4_DSF_Utils : « if not os.path.isfile(target_tex): rebuild »), et un
    JPG n'est retéléchargé que s'il est absent.
  - Donc, pour chaque image signalée : on efface le JPG ET le DDS
    correspondant, puis on relance l'étape 3 de la tuile concernée
    (TILE.build_tile, même fonction que le bouton « Construire
    Imagerie/DSF »). Seules ces images sont retéléchargées.

SÉCURITÉ
  - Rien n'est effacé sans la confirmation de l'utilisateur (liste affichée).
  - Seuls les fichiers dont le nom exact figure dans le journal sont
    concernés ; recherche limitée aux dossiers d'Ortho4XP.
  - Une construction déjà en cours bloque la réparation.
"""

import glob
import os
import re

_RX = (re.compile(r"WARNING:\s+(\S+\.jpg)\s+contains\s+\d+\s+pure white"),
       re.compile(r"Part of image\s+(\S+\.jpg)\s+could not be obtained"))
_DONE_TAG = "Repair white images: re-downloading"
_RX_DONE = re.compile(re.escape(_DONE_TAG) + r"\s+(\S+\.jpg)")
_TILE_DIR_RE = re.compile(r"XP_([+-]\d{2})([+-]\d{3})")


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


# ------------------------------------------------------------------------------
# PUR : images signalées dans des lignes de journal
# ------------------------------------------------------------------------------
def white_images_from_lines(lines):
    """PUR. Noms exacts des JPG signalés (ordre d'apparition, sans doublon).
    Une image déjà réparée (ligne « Repair white images: re-downloading »
    écrite par ce module) n'est plus proposée, sauf si elle est de nouveau
    signalée ensuite."""
    out = []
    for ln in lines:
        m = _RX_DONE.search(ln)
        if m:
            name = os.path.basename(m.group(1))
            if name in out:
                out.remove(name)
            continue
        for rx in _RX:
            m = rx.search(ln)
            if m:
                name = os.path.basename(m.group(1))
                if name not in out:
                    out.append(name)
    return out


def white_images_from_log(sessions=1, path=None):
    """Images signalées dans la/les dernière(s) session(s) active(s) du
    journal (même découpage que le Diagnostic). sessions=0 : tout."""
    try:
        import O4_Diagnostics_Utils as DG
    except Exception:
        return []
    lines = DG.read_log_lines(path)
    if not lines:
        return []
    sess = DG.split_sessions(lines)
    if sessions and sessions > 0:
        active = [s for s in sess if any(DG._ACTIVITY.search(l) for l in s)]
        sess = (active or sess)[-sessions:]
    return white_images_from_lines([l for s in sess for l in s])


# ------------------------------------------------------------------------------
# Où sont les fichiers ?
# ------------------------------------------------------------------------------
def locate(names, imagery_dir, working_dir):
    """Pour chaque nom de JPG : chemin du JPG (Orthophotos/<tuile>/<source>/)
    et du DDS (<dossier tuile>/textures/<même nom>.dds, ou pour une source
    combinée le(s) DDS aux mêmes coordonnées <y>_<x>_*.dds). Renvoie une
    liste de dicts {name, jpg, dds, dds_all, tile, build_dir} ;
    les images introuvables des deux côtés sont ignorées. working_dir :
    un dossier ou une liste de dossiers contenant des dossiers de tuiles."""
    tiles = []
    wdirs = [working_dir] if isinstance(working_dir, str) else \
        list(working_dir or [])
    for wd in wdirs:
        try:
            for d in sorted(os.listdir(wd)):
                m = _TILE_DIR_RE.search(d)
                full = os.path.join(wd, d)
                if m and os.path.isdir(os.path.join(full, "textures")) and \
                        all(full != x[1] for x in tiles):
                    tiles.append(((int(m.group(1)), int(m.group(2))), full))
        except Exception:
            pass
    out = []
    for name in names:
        dds_name = name[:-4] + ".dds"
        # Coordonnées de la texture (début du nom « <y>_<x>_ ») : avec une
        # source combinée (.comb), le DDS porte le nom de la combinaison et
        # non celui de l'image ; on le retrouve donc par ses coordonnées.
        m_xy = re.match(r"^(\d+)_(\d+)_", name)
        prefix = (m_xy.group(1) + "_" + m_xy.group(2) + "_") if m_xy else None
        jpg = ""
        try:
            hits = glob.glob(os.path.join(glob.escape(imagery_dir), "*", "*",
                                          glob.escape(name)))
            jpg = hits[0] if hits else ""
        except Exception:
            jpg = ""
        dds, tile, bd = "", None, ""
        dds_list = []
        for (t, d) in tiles:
            p = os.path.join(d, "textures", dds_name)
            if os.path.isfile(p):
                dds_list = [p]
            elif prefix:
                try:
                    dds_list = sorted(glob.glob(os.path.join(
                        glob.escape(os.path.join(d, "textures")),
                        glob.escape(prefix) + "*.dds")))
                except Exception:
                    dds_list = []
            if dds_list:
                dds, tile, bd = dds_list[0], t, d
                break
        if tile is None and jpg:
            m = _TILE_DIR_RE.search(jpg) or re.search(
                r"([+-]\d{2})([+-]\d{3})", jpg)
            if m:
                tile = (int(m.group(1)), int(m.group(2)))
                for (t, d) in tiles:
                    if t == tile:
                        bd = d
                        break
        if jpg or dds:
            out.append({"name": name, "jpg": jpg, "dds": dds,
                        "dds_all": dds_list, "tile": tile, "build_dir": bd})
    return out


def group_by_tile(items):
    g = {}
    for it in items:
        if it["tile"] is not None:
            g.setdefault(it["tile"], []).append(it)
    return g


def delete_files(items, remover=os.remove):
    """Efface JPG + DDS des images confirmées (et le note dans le journal,
    pour ne plus les reproposer). Renvoie le nombre de fichiers effacés."""
    n = 0
    try:
        import O4_UI_Utils as UI
        for it in items:
            UI.logprint(_DONE_TAG, it["name"])
    except Exception:
        pass
    for it in items:
        paths = [it.get("jpg")] + list(it.get("dds_all") or [it.get("dds")])
        for p in paths:
            if p and os.path.isfile(p):
                try:
                    remover(p)
                    n += 1
                except Exception:
                    pass
    return n


def tiles_to_rebuild(items):
    """PUR. Liste ordonnée de ((lat, lon), dossier_tuile) à refaire."""
    out = []
    for it in items:
        if it.get("tile") is not None and it.get("build_dir"):
            key = (it["tile"], it["build_dir"])
            if key not in out:
                out.append(key)
    return out


def _cbd_for(lat, lon, build_dir):
    """Valeur « custom_build_dir » qui redonne exactement ce dossier de tuile
    (même règle que O4_File_Names.build_dir) ; None si le dossier ne suit pas
    le nommage standard (tuiles groupées : non réparées ici)."""
    import O4_File_Names as FNAMES
    bd = os.path.normpath(build_dir)
    if os.path.basename(bd) != FNAMES.tile_dir(lat, lon):
        return None
    parent = os.path.dirname(bd)
    if os.path.normpath(FNAMES.Tile_dir) == parent:
        return ""
    return parent + "/"


def rebuild_tiles(tiles, state=None):
    """Relance l'étape 3 (TILE.build_tile, même fonction que le bouton
    « Construire Imagerie/DSF ») pour chaque ((lat, lon), dossier_tuile).
    À lancer dans un thread de travail. Utilise le .cfg de la tuile."""
    import O4_Config_Utils as CFG
    import O4_File_Names as FNAMES
    import O4_Tile_Utils as TILE
    import O4_UI_Utils as UI
    state = state if state is not None else {}
    state.update({"running": True, "ok": [], "failed": [], "current": ""})
    for ((lat, lon), bd) in tiles:
        name = FNAMES.short_latlon(lat, lon)
        state["current"] = name
        ok = False
        cbd = _cbd_for(lat, lon, bd)
        if cbd is None:
            state["failed"].append(name)
            continue
        try:
            UI.red_flag = False
            tile = CFG.Tile(lat, lon, cbd)
            cfgs = (os.path.join(tile.build_dir, "Ortho4XP_" + name + ".cfg"),
                    os.path.join(tile.build_dir, "Ortho4XP.cfg"))
            if any(os.path.isfile(c) for c in cfgs):
                tile.read_from_config()
            r = TILE.build_tile(tile)
            ok = bool(r) and not UI.red_flag
        except Exception:
            ok = False
        finally:
            try:
                UI.is_working = 0
                UI.red_flag = False
            except Exception:
                pass
        (state["ok"] if ok else state["failed"]).append(name)
    state["running"] = False
    return state
