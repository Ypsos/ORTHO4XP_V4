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
O4_Build_Worker.py — Étape 3 d'UNE tuile dans un processus séparé.

MODULE AUTONOME (100 % additif), lancé par le mode simple
(O4_Grand_Public_Utils) pour construire plusieurs tuiles EN MÊME TEMPS :
chaque tuile a son propre processus Python, donc sa propre mémoire et son
propre état du moteur (aucun mélange possible entre deux tuiles).

Les étapes 1, 2, 2.1 et 2.5 (vecteurs, maillage, patchs mer, masques) sont
faites AVANT par le mode simple, une tuile après l'autre (téléchargements
OSM et altitudes jamais en double). Ce processus ne fait que l'étape 3
(TILE.build_tile, fonction inchangée du moteur), avec le .cfg de la tuile.

Utilisation (par le mode simple, jamais à la main) :
    python O4_Build_Worker.py '<json>'
    json = {"lat", "lon", "cbd", "quality", "provider",
            "download_slots", "convert_slots", "cnorm" (facultatif)}
    cnorm = réglages couleur du processus principal (Color Normalize :
    enabled, strength, sat_on, sat), pour que l'étape 3 en parallèle donne
    les mêmes couleurs que l'étape 3 faite dans Ortho4XP.
Code de sortie : 0 = tuile construite, 1 = échec, 2 = paramètres invalides.
Tous les messages du moteur vont sur la sortie standard (que le mode simple
range dans un fichier journal du dossier de la tuile).
"""

import json
import os
import sys


def parse_args(argv):
    """PUR. Lit et contrôle les paramètres ; lève ValueError si invalides."""
    if len(argv) < 2:
        raise ValueError("missing json argument")
    p = json.loads(argv[1])
    lat, lon = int(p["lat"]), int(p["lon"])
    if not (-90 <= lat < 90 and -180 <= lon < 180):
        raise ValueError("bad tile")
    out = {
        "lat": lat, "lon": lon,
        "cbd": str(p.get("cbd", "") or ""),
        "quality": str(p.get("quality", "balanced")),
        "provider": str(p["provider"]),
        "download_slots": max(1, min(8, int(p.get("download_slots", 1)))),
        "convert_slots": max(1, min(8, int(p.get("convert_slots", 4)))),
    }
    if not out["provider"]:
        raise ValueError("bad provider")
    cn = p.get("cnorm")
    if isinstance(cn, dict):
        try:
            out["cnorm"] = {
                "enabled": bool(cn["enabled"]),
                "strength": max(0.0, min(1.0, float(cn["strength"]))),
                "sat_on": bool(cn["sat_on"]),
                "sat": max(0.0, min(2.0, float(cn["sat"]))),
            }
        except Exception:
            raise ValueError("bad cnorm")
    return out


def _setup_paths():
    src = os.path.dirname(os.path.abspath(__file__))
    if src not in sys.path:
        sys.path.insert(0, src)
    import O4_File_Names as FNAMES
    if FNAMES.Provider_dir not in sys.path:
        sys.path.append(FNAMES.Provider_dir)


def run(params):
    """Construit l'étape 3 de la tuile. Renvoie 0 (succès) ou 1 (échec)."""
    _setup_paths()
    # Même ordre d'initialisation que Ortho4XP.py (CFG en dernier : il
    # applique Ortho4XP.cfg aux modules du moteur).
    import O4_Imagery_Utils as IMG
    import O4_Vector_Map as VMAP        # noqa: F401
    import O4_Mesh_Utils as MESH        # noqa: F401
    import O4_Mask_Utils as MASK        # noqa: F401
    import O4_Tile_Utils as TILE
    import O4_Config_Utils as CFG       # noqa: F401
    import O4_UI_Utils as UI
    try:
        import O4_Lang
        saved = O4_Lang._read_lang_from_cfg()
        O4_Lang._load_lang(saved or O4_Lang._resolve_startup_lang())
    except Exception:
        pass
    try:
        IMG.initialize_extents_dict()
        IMG.initialize_color_filters_dict()
        IMG.initialize_providers_dict()
        IMG.initialize_combined_providers_dict()
    except Exception as e:
        print("WARNING providers:", e)
    import O4_Grand_Public_Utils as GP
    tile = GP.make_tile(params["lat"], params["lon"], params["cbd"],
                        params["quality"], params["provider"])
    if params.get("cnorm"):
        GP.cnorm_apply(params["cnorm"])
    TILE.max_download_slots = params["download_slots"]
    TILE.max_convert_slots = params["convert_slots"]
    UI.red_flag = False
    ok = bool(TILE.build_tile(tile)) and not UI.red_flag
    return 0 if ok else 1


def main(argv=None):
    argv = sys.argv if argv is None else argv
    try:
        params = parse_args(argv)
    except Exception as e:
        print("O4_Build_Worker: invalid parameters:", e)
        return 2
    try:
        return run(params)
    except Exception:
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
