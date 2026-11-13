# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2024-2026 Roland (Ypsos)
#
# CRÉDIT — AUTEUR : Roland (Ypsos) — Septembre 2026
# Module conçu et spécifié par Roland (Ypsos) pour Ortho4XP V3.
# Cette notice d'auteur et de copyright doit être conservée
# conformément à la GPLv3.
# Licence : GPLv3 + conditions additionnelles (art. 7),
# voir AVERTISSEMENT_LICENCE_LEGAL.md, section 16.
# ============================================================
# Copyright (c) 2024-2026 Roland (Ypsos)
#
# CREDIT — AUTHOR: Roland (Ypsos) — September 2026
# Module designed and specified by Roland (Ypsos) for Ortho4XP V3.
# This authorship and copyright notice must be retained
# in accordance with GPLv3.
# License: GPLv3 + additional terms (Sec. 7),
# see AVERTISSEMENT_LICENCE_LEGAL.md, Section 16.
# ============================================================
# ------------------------------------------------------------------------------
# O4_Tile_Library_Utils.py
# Bibliotheque de tuiles (CDC V3.6, Priorite 2).
# Auteur : Roland (Ypsos) - GPLv3
#
# Un seul module, bilingue (_L interne), 100 % ADDITIF, appele depuis le
# Menu Avance via run_tile_library(parent).
#
# Fonctions offertes :
#   - LISTER les tuiles Ortho4XP (zOrtho4XP_...) et leur etat (active/desactivee),
#     lues dans scenery_packs.ini de X-Plane (lecture seule).
#   - ACTIVER / DESACTIVER une tuile dans X-Plane : on change uniquement
#     SCENERY_PACK <-> SCENERY_PACK_DISABLED sur SA ligne, sans toucher au
#     reste ni a l'ordre. Reversible, instantane, aucun Go deplace.
#   - SUPPRIMER une tuile : symlink -> on retire LE LIEN seulement (jamais les
#     donnees pointees) ; vrai dossier -> suppression du dossier. Confirmation
#     obligatoire, jamais en bloc silencieux. La ligne est retiree du .ini.
#   - VIDER LE CACHE d'une tuile : dossiers OSM_data / Masks / Patches propres a
#     cette tuile (via O4_File_Names, aucun chemin en dur). Confirmation.
#   - (nov. 2026) PLACE : a la selection d'une tuile, la place des images
#     telechargees et du cache s'affiche ; bouton « Liberer les images
#     telechargees » (confirmation, via O4_Build_Comfort_Utils : seuls les
#     JPG source de la tuile, jamais ses DDS ni JPG-Patch).
#   - (nov. 2026) X-PLANE OUVERT : Activer / Desactiver / Supprimer sont
#     refuses tant que X-Plane tourne (il reecrirait scenery_packs.ini).
#
# Securite :
#   - AUCUN chemin code en dur. On lit ce qui est ecrit dans scenery_packs.ini
#     et on utilise O4_File_Names pour les dossiers de cache.
#   - Toute ecriture de scenery_packs.ini fait d'abord une sauvegarde .bak.
#   - On ne suit JAMAIS un symlink pour supprimer des donnees.
#   - Aucun fichier moteur (mer/mesh/masques/DSF) touche.
#
# Le chemin du scenery_packs.ini est memorise dans un petit fichier prive
# (.tile_library_ini a la racine Ortho4XP) -> on ne touche pas a Ortho4XP.cfg
# ni a cfg_vars.
# ------------------------------------------------------------------------------

import math
import os
import re
import shutil

_KW_ON = "SCENERY_PACK"
_KW_OFF = "SCENERY_PACK_DISABLED"
_ORTHO_MARK = "zOrtho4XP_"
_LATLON_RE = re.compile(r"zOrtho4XP_([+-]\d{2})([+-]\d{3})")


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


# ------------------------------------------------------------------------------
# CHAPITRE 1 - coeur PUR (testable en headless)
# ------------------------------------------------------------------------------
def parse_scenery_packs(text):
    """PUR. Liste les entrees SCENERY_PACK : {index, enabled, path, is_ortho}."""
    entries = []
    for i, raw in enumerate(text.splitlines()):
        s = raw.strip()
        if not s:
            continue
        if s.startswith(_KW_OFF):
            path = s[len(_KW_OFF):].strip()
            enabled = False
        elif s.startswith(_KW_ON):
            path = s[len(_KW_ON):].strip()
            enabled = True
        else:
            continue
        entries.append({
            "index": i,
            "enabled": enabled,
            "path": path,
            "is_ortho": _ORTHO_MARK in path,
        })
    return entries


def list_ortho_tiles(text):
    """PUR. Seulement les tuiles Ortho4XP, dans l'ordre du fichier."""
    return [e for e in parse_scenery_packs(text) if e["is_ortho"]]


def set_tile_enabled(text, path, enabled):
    """
    PUR. (nouveau_texte, change?). Met la ligne de chemin == path a l'etat
    voulu. Matching STRICT du chemin (/ final, espaces, suffixes conserves).
    Ne change QUE le mot-cle de cette ligne ; preserve tout le reste.
    """
    lines = text.splitlines(keepends=True)
    changed = False
    for k, raw in enumerate(lines):
        nl = ""
        body = raw
        for end in ("\r\n", "\n", "\r"):
            if raw.endswith(end):
                nl = end
                body = raw[: -len(end)]
                break
        s = body.strip()
        cur = None
        if s.startswith(_KW_OFF):
            cur = s[len(_KW_OFF):].strip()
        elif s.startswith(_KW_ON):
            cur = s[len(_KW_ON):].strip()
        if cur is None or cur != path:
            continue
        kw = _KW_ON if enabled else _KW_OFF
        newbody = kw + " " + cur
        if newbody != body:
            lines[k] = newbody + nl
            changed = True
        break
    return ("".join(lines), changed)


def remove_tile_line(text, path):
    """PUR. (nouveau_texte, retiree?). Retire la ligne SCENERY_PACK[_DISABLED]
    dont le chemin == path (matching strict). Les autres lignes sont intactes."""
    lines = text.splitlines(keepends=True)
    out = []
    removed = False
    for raw in lines:
        body = raw
        for end in ("\r\n", "\n", "\r"):
            if raw.endswith(end):
                body = raw[: -len(end)]
                break
        s = body.strip()
        cur = None
        if s.startswith(_KW_OFF):
            cur = s[len(_KW_OFF):].strip()
        elif s.startswith(_KW_ON):
            cur = s[len(_KW_ON):].strip()
        if (not removed) and cur is not None and cur == path:
            removed = True
            continue  # on saute cette ligne
        out.append(raw)
    return ("".join(out), removed)


def tile_latlon_from_path(pack_path):
    """PUR. (lat, lon) entiers depuis un chemin/paquet zOrtho4XP_+46-003...,
    ou None si non reconnu. Gere les noms longs et ' symlink'."""
    m = _LATLON_RE.search(pack_path)
    if not m:
        return None
    try:
        return (int(m.group(1)), int(m.group(2)))
    except Exception:
        return None


# ------------------------------------------------------------------------------
# Acces disque
# ------------------------------------------------------------------------------
def read_scenery_file(ini_path):
    with open(ini_path, "r", encoding="utf-8") as f:
        return f.read()


def _write_with_bak(ini_path, new_text):
    shutil.copy2(ini_path, ini_path + ".bak")
    with open(ini_path, "w", encoding="utf-8") as f:
        f.write(new_text)


def toggle_tile_in_file(ini_path, path, enabled):
    """PRODUCTION. (ok, message). Sauvegarde .bak avant toute ecriture."""
    if not os.path.isfile(ini_path):
        return (False, _L("scenery_packs.ini introuvable",
                          "scenery_packs.ini not found"))
    text = read_scenery_file(ini_path)
    new_text, changed = set_tile_enabled(text, path, enabled)
    if not changed:
        return (True, _L("deja dans l'etat demande", "already in that state"))
    _write_with_bak(ini_path, new_text)
    return (True, "ok")


def remove_tile_from_file(ini_path, path):
    """PRODUCTION. Retire la ligne de la tuile du .ini (sauvegarde .bak)."""
    if not os.path.isfile(ini_path):
        return (False, _L("scenery_packs.ini introuvable",
                          "scenery_packs.ini not found"))
    text = read_scenery_file(ini_path)
    new_text, removed = remove_tile_line(text, path)
    if not removed:
        return (True, _L("ligne absente", "line absent"))
    _write_with_bak(ini_path, new_text)
    return (True, "ok")


def xplane_root_from_ini(ini_path):
    """Racine X-Plane = parent du dossier 'Custom Scenery' qui contient le .ini."""
    custom_scenery = os.path.dirname(os.path.abspath(ini_path))
    return os.path.dirname(custom_scenery)


def tile_abspath(ini_path, pack_path):
    """Chemin absolu du dossier/paquet a partir de son chemin relatif .ini."""
    root = xplane_root_from_ini(ini_path)
    rel = pack_path.rstrip("/")
    return os.path.join(root, rel)


def delete_tile_folder(ini_path, pack_path):
    """
    PRODUCTION. Supprime le dossier de la tuile de facon symlink-safe :
      - lien symbolique  -> on retire LE LIEN uniquement (os.unlink),
                            jamais les donnees pointees.
      - vrai dossier     -> shutil.rmtree.
    Retourne (ok, message). N'ecrit pas dans le .ini (fait a part).
    """
    target = tile_abspath(ini_path, pack_path)
    try:
        if _is_junction(target):
            # Windows : jonction (lien de dossier) -> on retire la jonction
            # seule (os.rmdir), jamais les données pointées.
            os.rmdir(target)
            return (True, _L("lien retire (donnees intactes)",
                             "link removed (data untouched)"))
        if os.path.islink(target):
            os.unlink(target)  # retire le lien seulement
            return (True, _L("lien retire (donnees intactes)",
                             "link removed (data untouched)"))
        if os.path.isdir(target):
            shutil.rmtree(target)
            return (True, _L("dossier supprime", "folder deleted"))
        return (True, _L("rien a supprimer (deja absent)",
                         "nothing to delete (already gone)"))
    except Exception as e:
        return (False, str(e))


# ------------------------------------------------------------------------------
# CHAPITRE 4 (nov. 2026) - Ajouter des tuiles d'un dossier, deplacer une tuile
# vers un autre disque, reconstruire, routes en double. Bilingue, multi-OS.
# ------------------------------------------------------------------------------
def _is_junction(path):
    """Jonction Windows (lien de dossier) ; toujours False ailleurs."""
    try:
        fn = getattr(os.path, "isjunction", None)
        return bool(fn(path)) if fn else False
    except Exception:
        return False


def is_link(path):
    return os.path.islink(path) or _is_junction(path)


def remove_link(path):
    """Retire un lien (ou une jonction) SANS toucher aux données pointées."""
    if _is_junction(path):
        os.rmdir(path)
    else:
        os.unlink(path)


def find_tile_folders(folder):
    """Dossiers de tuiles Ortho4XP (zOrtho4XP_<tuile> avec « Earth nav
    data ») : le dossier lui-même s'il en est une, sinon ses sous-dossiers
    (un niveau, plus Tiles/ si c'est un dossier Ortho4XP). Triés."""
    out = []

    def _ok(d):
        return (os.path.basename(os.path.normpath(d)).startswith(_ORTHO_MARK)
                and os.path.isdir(os.path.join(d, "Earth nav data")))

    if not folder or not os.path.isdir(folder):
        return out
    if _ok(folder):
        return [os.path.normpath(folder)]
    cands = [folder]
    if os.path.isdir(os.path.join(folder, "Tiles")):
        cands.append(os.path.join(folder, "Tiles"))
    for c in cands:
        try:
            names = sorted(os.listdir(c))
        except Exception:
            continue
        for n in names:
            d = os.path.join(c, n)
            if _ok(d) and os.path.normpath(d) not in out:
                out.append(os.path.normpath(d))
    return out


def folder_stats(path):
    """(nombre de fichiers, octets) d'un dossier, sans suivre les liens."""
    n, b = 0, 0
    for root, dirs, files in os.walk(path):
        for f in files:
            p = os.path.join(root, f)
            if os.path.islink(p):
                continue
            try:
                b += os.path.getsize(p)
                n += 1
            except Exception:
                pass
    return n, b


def copy_tile_verified(src, dest_parent, copier=None):
    """Copie le dossier de tuile src dans dest_parent/<même nom>, puis
    vérifie (même nombre de fichiers, mêmes octets). Renvoie (ok, nouveau
    chemin, message). En cas d'écart, la copie incomplète est retirée."""
    name = os.path.basename(os.path.normpath(src))
    dst = os.path.join(dest_parent, name)
    if os.path.lexists(dst):
        return (False, dst, _L("un dossier « %s » existe déjà à cet endroit"
                               % name, "a « %s » folder already exists "
                               "there" % name))
    n0, b0 = folder_stats(src)
    try:
        free = shutil.disk_usage(dest_parent).free
    except Exception:
        free = None
    if free is not None and free < b0 * 1.05 + 50 * 1024 ** 2:
        return (False, dst, _L("place insuffisante sur ce disque",
                               "not enough space on that disk"))
    try:
        (copier or shutil.copytree)(src, dst, symlinks=True)
    except Exception as e:
        try:
            shutil.rmtree(dst)
        except Exception:
            pass
        return (False, dst, str(e))
    n1, b1 = folder_stats(dst)
    if (n1, b1) != (n0, b0):
        try:
            shutil.rmtree(dst)
        except Exception:
            pass
        return (False, dst, _L("copie incomplète (%d/%d fichiers) : annulée"
                               % (n1, n0), "incomplete copy (%d/%d files): "
                               "cancelled" % (n1, n0)))
    return (True, dst, "ok")


def move_tile(ini_path, pack_path, dest_parent, linker=None, copier=None):
    """Déplace les données d'une tuile installée vers dest_parent (autre
    disque) et fait pointer X-Plane dessus. Étapes, toutes vérifiées :
      1. copie complète + contrôle (copy_tile_verified) ;
      2. dans Custom Scenery : le lien est refait vers la nouvelle copie
         (si la tuile y était un vrai dossier, il est d'abord renommé à
         côté, puis supprimé seulement quand le lien est en place) ;
    Renvoie (ok, ancien_dossier_de_données|None, message). L'ancienne copie
    (hors Custom Scenery) n'est JAMAIS effacée ici : l'interface le
    propose ensuite, « Non » par défaut."""
    target = tile_abspath(ini_path, pack_path)
    if not os.path.lexists(target):
        return (False, None, _L("dossier de la tuile introuvable",
                                "tile folder not found"))
    linked = is_link(target)
    data = os.path.realpath(target)
    if not os.path.isdir(data):
        return (False, None, _L("données de la tuile introuvables (disque "
                                "débranché ?)", "tile data not found (disk "
                                "unplugged?)"))
    dp = os.path.normpath(os.path.realpath(dest_parent))
    if dp == os.path.normpath(data) or \
            dp.startswith(os.path.normpath(data) + os.sep) or \
            dp == os.path.normpath(os.path.dirname(data)):
        return (False, None, _L("choisissez un autre dossier que celui de "
                                "la tuile", "choose a folder other than the "
                                "tile's own"))
    ok, dst, msg = copy_tile_verified(data, dest_parent, copier=copier)
    if not ok:
        return (False, None, msg)
    if linker is None:
        try:
            import O4_Scenery_Installer_Utils as SI
            linker = SI.make_link
        except Exception:
            linker = None
    if linker is None:
        shutil.rmtree(dst, ignore_errors=True)
        return (False, None, "make_link")
    if linked:
        remove_link(target)
        ok, m = linker(os.path.abspath(dst), target)
        if not ok:
            # remettre l'ancien lien : X-Plane retrouve la tuile comme avant
            linker(data, target)
            shutil.rmtree(dst, ignore_errors=True)
            return (False, None, m)
        return (True, data, "ok")
    # vrai dossier dans Custom Scenery : renommé, lien posé, puis supprimé
    aside = target.rstrip("/\\") + ".o4x_old"
    if os.path.lexists(aside):
        shutil.rmtree(dst, ignore_errors=True)
        return (False, None, aside)
    os.rename(target, aside)
    ok, m = linker(os.path.abspath(dst), target)
    if not ok:
        os.rename(aside, target)
        shutil.rmtree(dst, ignore_errors=True)
        return (False, None, m)
    shutil.rmtree(aside, ignore_errors=True)
    return (True, None, "ok")


OVERLAY_HINTS = ("overlay", "x-world", "simheaven", "world2xplane", "w2xp")


def _pack_name(path):
    return path.rstrip("/").split("/")[-1]


def overlay_packs_for_tile(ini_path, lat, lon, text=None):
    """Paquets ACTIVÉS de scenery_packs.ini qui semblent dessiner routes /
    forêts / bâtiments sur cette tuile (nom contenant « overlay »,
    « X-World »… ET un DSF pour cette tuile). Liste de noms."""
    try:
        text = text if text is not None else read_scenery_file(ini_path)
    except Exception:
        return []
    grp = "%+03d%+04d" % (int(math.floor(lat / 10.0)) * 10,
                          int(math.floor(lon / 10.0)) * 10)
    short = "%+03d%+04d" % (lat, lon)
    out = []
    for e in parse_scenery_packs(text):
        if not e["enabled"] or e["is_ortho"]:
            continue
        name = _pack_name(e["path"])
        low = name.lower()
        if not any(h in low for h in OVERLAY_HINTS):
            continue
        dsf = os.path.join(tile_abspath(ini_path, e["path"]),
                           "Earth nav data", grp, short + ".dsf")
        if os.path.isfile(dsf):
            out.append(name)
    return out


def duplicate_overlays(ini_path):
    """{tuile: [paquets]} pour les tuiles Ortho4XP de la liste où AU MOINS
    deux paquets de routes / forêts couvrent la même tuile (routes qui
    clignotent, objets en double). Lecture seule."""
    try:
        text = read_scenery_file(ini_path)
    except Exception:
        return {}
    res = {}
    for e in list_ortho_tiles(text):
        ll = tile_latlon_from_path(e["path"])
        if not ll or ll in res:
            continue
        packs = overlay_packs_for_tile(ini_path, ll[0], ll[1], text=text)
        if len(packs) >= 2:
            res[ll] = packs
    return res


def rebuild_tile(ini_path, pack_path, state=None):
    """Reconstruit une tuile installée (les 4 étapes, TILE.build_all, avec
    son .cfg), dans son dossier. À lancer dans un thread. Renvoie
    (ok, message)."""
    state = state if state is not None else {}
    ll = tile_latlon_from_path(pack_path)
    if not ll:
        return (False, _L("coordonnées non reconnues", "coordinates not "
                          "recognised"))
    data = os.path.realpath(tile_abspath(ini_path, pack_path))
    if not os.path.isdir(data):
        return (False, _L("données de la tuile introuvables",
                          "tile data not found"))
    try:
        import O4_Image_Repair_Utils as IR
        import O4_Config_Utils as CFG
        import O4_File_Names as FNAMES
        import O4_Tile_Utils as TILE
        import O4_UI_Utils as UI
    except Exception as e:
        return (False, str(e))
    if getattr(UI, "is_working", False):
        return (False, _L("une construction est déjà en cours",
                          "a build is already running"))
    cbd = IR._cbd_for(ll[0], ll[1], data)
    if cbd is None:
        return (False, _L("dossier non standard : reconstruisez-la depuis la "
                          "fenêtre principale", "non-standard folder: rebuild "
                          "it from the main window"))
    state["running"] = True
    ok = False
    try:
        UI.red_flag = False
        tile = CFG.Tile(ll[0], ll[1], cbd)
        name = FNAMES.short_latlon(ll[0], ll[1])
        cfgs = (os.path.join(tile.build_dir, "Ortho4XP_" + name + ".cfg"),
                os.path.join(tile.build_dir, "Ortho4XP.cfg"))
        if any(os.path.isfile(c) for c in cfgs):
            tile.read_from_config()
        ok = bool(TILE.build_all(tile)) and not UI.red_flag
    except Exception as e:
        state["running"] = False
        return (False, str(e))
    finally:
        try:
            UI.is_working = 0
            UI.red_flag = False
        except Exception:
            pass
    state["running"] = False
    return (ok, "ok" if ok else _L("échec : voir le journal / Diagnostic",
                                   "failed: see the log / Diagnostic"))


def tile_cache_dirs(lat, lon):
    """
    Dossiers de cache PROPRES a une tuile, via O4_File_Names (aucun chemin en
    dur). Retourne une liste de (libelle, chemin_absolu) existants seulement.
    On reste conservateur : OSM_data / Masks / Patches (pas les Orthophotos
    partagees). Si O4_File_Names est absent, retourne [].
    """
    dirs = []
    try:
        import O4_File_Names as FNAMES
        cand = [
            ("OSM_data", FNAMES.osm_dir(lat, lon)),
            ("Masks", FNAMES.mask_dir(lat, lon)),
            ("Patches", FNAMES.patch_dir(lat, lon)),
        ]
        for label, d in cand:
            if d and os.path.isdir(d):
                dirs.append((label, d))
    except Exception:
        pass
    return dirs


def dir_size_go(path):
    """Taille d'un dossier en Go (0 si absent)."""
    tot = 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                tot += os.path.getsize(os.path.join(root, f))
            except Exception:
                pass
    return tot / 1024.0 ** 3


def tile_space(lat, lon):
    """(liste des JPG source, Go des JPG, Go du cache OSM/Masks/Patches)."""
    jpgs, go_jpg = [], 0.0
    try:
        import O4_Build_Comfort_Utils as BC
        import O4_File_Names as FNAMES
        jpgs = BC.tile_jpgs(lat, lon, FNAMES.Imagery_dir)
        go_jpg = BC.files_size_go(jpgs)
    except Exception:
        pass
    go_cache = sum(dir_size_go(d) for _l, d in tile_cache_dirs(lat, lon))
    return (jpgs, go_jpg, go_cache)


def xplane_is_open():
    try:
        import O4_Scenery_Installer_Utils as SI
        if SI.xplane_running() is True:
            return SI.xplane_open_message()
    except Exception:
        pass
    return ""


def clear_tile_cache(lat, lon):
    """PRODUCTION. Supprime les dossiers de cache de la tuile. (ok, details)."""
    done = []
    for label, d in tile_cache_dirs(lat, lon):
        try:
            shutil.rmtree(d)
            done.append(label)
        except Exception as e:
            return (False, "%s: %s" % (label, e))
    return (True, done)


# ------------------------------------------------------------------------------
# Memorisation du chemin scenery_packs.ini (fichier prive, pas Ortho4XP.cfg)
# ------------------------------------------------------------------------------
def _remember_path_file():
    try:
        import O4_File_Names as FNAMES
        root = FNAMES.Ortho4XP_dir
    except Exception:
        root = os.path.expanduser("~")
    return os.path.join(root, ".tile_library_ini")


def load_saved_ini_path():
    try:
        p = _remember_path_file()
        if os.path.isfile(p):
            with open(p, "r", encoding="utf-8") as f:
                cand = f.read().strip()
            if cand and os.path.isfile(cand):
                return cand
    except Exception:
        pass
    return ""


def save_ini_path(ini_path):
    try:
        with open(_remember_path_file(), "w", encoding="utf-8") as f:
            f.write(ini_path.strip())
        return True
    except Exception:
        return False


def guess_ini_path():
    """Tente de deviner scenery_packs.ini SANS rien coder en dur :
    1) chemin memorise ; 2) via custom_build_dir (config) s'il pointe dans un
    'Custom Scenery'. Sinon "" -> l'utilisateur choisira dans la fenetre."""
    saved = load_saved_ini_path()
    if saved:
        return saved
    try:
        import O4_Config_Utils as CFG
        cbd = getattr(CFG, "custom_build_dir", "") or ""
        if cbd:
            parts = os.path.abspath(cbd).split(os.sep)
            if "Custom Scenery" in parts:
                idx = len(parts) - 1 - parts[::-1].index("Custom Scenery")
                cs = os.sep.join(parts[: idx + 1])
                cand = os.path.join(cs, "scenery_packs.ini")
                if os.path.isfile(cand):
                    return cand
    except Exception:
        pass
    return ""


# ------------------------------------------------------------------------------
# CHAPITRE 3 - Fenetre (Menu Avance). Point d'entree : run_tile_library(parent)
# Import tkinter LOCAL (la fenetre s'ouvre meme si un module optionnel manque).
# ------------------------------------------------------------------------------
def run_tile_library(parent=None):
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    # Couleurs depuis le theme (memes cles + memes defauts que le Menu Avance
    # et les autres fenetres du projet). apply_to_root habille les widgets
    # standards ; le theme ne gere PAS Listbox -> on la colore a la main
    # (cf. Bible O4_Theme_Manager).
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
    SEL_BG = _c("btn_active", HOVER)
    LIST_BG = _c("canvas_bg", BG)
    FONT = ("Helvetica", 12) if ("dar" in __import__("sys").platform) \
        else ("Segoe UI", 10)

    state = {"ini": guess_ini_path(), "rows_on": [], "rows_off": []}

    root_ref = None
    try:
        root_ref = tk._default_root
    except Exception:
        pass
    win = tk.Toplevel(root_ref) if root_ref else tk.Tk()
    win.title(_L("Bibliotheque de tuiles - Ortho4XP V4",
                 "Tile library - Ortho4XP V4"))
    win.configure(bg=BG)
    # Applique le theme aux widgets standards (defensif). La Listbox n'est pas
    # geree par apply_to_root -> couleurs posees a la main plus bas.
    if _TM is not None:
        try:
            _TM.apply_to_root(win)
        except Exception:
            pass
    win.lift()
    try:
        win.focus_force()
    except Exception:
        pass

    # Boutons Mac-safe : sous macOS (Aqua), tk.Button ignore bg/fg -> texte
    # illisible. On utilise CustomTkinter si present (comme toute l'interface
    # Ortho4XP V3), sinon un repli Frame+Label colore (patron valide du projet).
    try:
        import customtkinter as _ctk
        _HAS_CTK = True
    except Exception:
        _HAS_CTK = False

    def _lighten(hexcol, factor):
        try:
            h = hexcol.lstrip("#")
            r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
            r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
            return "#%02x%02x%02x" % (r, g, b)
        except Exception:
            return hexcol

    def _btn(parent_w, text, cmd):
        if _HAS_CTK:
            b = _ctk.CTkButton(
                parent_w, text=text, command=cmd,
                corner_radius=8, border_width=1, height=32,
                fg_color=BTN_BG, hover_color=HOVER,
                border_color=BORDER, text_color=BTN_FG)
            # Correctif macOS : redessin apres mise en page.
            b.after_idle(
                lambda w=b, c=BTN_BG: w.winfo_exists() and w.configure(fg_color=c))
            return b
        frame = tk.Frame(parent_w, bg=BTN_BG, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        lbl = tk.Label(frame, text=text, bg=BTN_BG, fg=BTN_FG, padx=10, pady=6,
                       font=FONT, cursor="hand2")
        lbl.pack(fill="both", expand=True)

        def _enter(e=None):
            frame.configure(bg=HOVER); lbl.configure(bg=HOVER)

        def _leave(e=None):
            frame.configure(bg=BTN_BG); lbl.configure(bg=BTN_BG)

        def _release(e=None):
            _leave()
            if callable(cmd):
                cmd()

        for w in (frame, lbl):
            w.bind("<Enter>", _enter)
            w.bind("<Leave>", _leave)
            w.bind("<ButtonRelease-1>", _release)
        return frame

    # --- ligne du haut : fichier .ini ---
    top = tk.Frame(win, bg=BG)
    top.pack(fill=tk.X, padx=10, pady=(10, 4))
    ini_var = tk.StringVar(value=state["ini"] or _L("(non defini)", "(not set)"))
    tk.Label(top, text=_L("Fichier X-Plane :", "X-Plane file:"),
             bg=BG, fg=FG, font=FONT).pack(side=tk.LEFT)
    tk.Label(top, textvariable=ini_var, bg=BG, fg=FG, font=("TkFixedFont", 10),
             anchor="w", wraplength=560, justify="left").pack(
             side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))

    # --- filtre ---
    filt = tk.Frame(win, bg=BG)
    filt.pack(fill=tk.X, padx=10, pady=(0, 4))
    tk.Label(filt, text=_L("Filtrer :", "Filter:"), bg=BG, fg=FG,
             font=FONT).pack(side=tk.LEFT)
    filter_var = tk.StringVar(value="")
    tk.Entry(filt, textvariable=filter_var, bg="#05330f", fg=FG,
             insertbackground=FG, font=FONT, width=24).pack(
             side=tk.LEFT, padx=(6, 0))

    # --- 2 listes cote a cote : ACTIVEES (gauche) et DESACTIVEES (droite) ---
    # Deux rubriques VISIBLES en meme temps : on voit d'un coup d'oeil lesquelles
    # sont actives et lesquelles reactiver, sans defiler sous les autres. On
    # selectionne une tuile dans une liste, l'autre liste se deselectionne pour
    # que le bouton agisse sans ambiguite. height basse (retour forum petit
    # ecran) : le nombre de lignes visibles suit la taille reelle (expand=True).
    mid = tk.Frame(win, bg=BG)
    mid.pack(fill=tk.BOTH, expand=True, padx=10, pady=4)
    mid.grid_columnconfigure(0, weight=1, uniform="cols")
    mid.grid_columnconfigure(1, weight=1, uniform="cols")
    mid.grid_rowconfigure(1, weight=1)

    hdr_on = tk.StringVar(value=_L("ACTIVEES", "ENABLED"))
    hdr_off = tk.StringVar(value=_L("DESACTIVEES", "DISABLED"))
    tk.Label(mid, textvariable=hdr_on, bg=BG, fg=FG2, font=FONT,
             anchor="w").grid(row=0, column=0, sticky="w", padx=(0, 4))
    tk.Label(mid, textvariable=hdr_off, bg=BG, fg=FG2, font=FONT,
             anchor="w").grid(row=0, column=1, sticky="w", padx=(4, 0))

    left = tk.Frame(mid, bg=BG)
    left.grid(row=1, column=0, sticky="nsew", padx=(0, 4))
    sb_on = tk.Scrollbar(left)
    sb_on.pack(side=tk.RIGHT, fill=tk.Y)
    lb_on = tk.Listbox(left, bg="#05140a", fg=FG, selectbackground=SEL_BG,
                       selectforeground=FG, font=FONT, height=8,
                       yscrollcommand=sb_on.set, activestyle="none",
                       exportselection=False)
    lb_on.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb_on.config(command=lb_on.yview)

    right = tk.Frame(mid, bg=BG)
    right.grid(row=1, column=1, sticky="nsew", padx=(4, 0))
    sb_off = tk.Scrollbar(right)
    sb_off.pack(side=tk.RIGHT, fill=tk.Y)
    lb_off = tk.Listbox(right, bg="#05140a", fg=FG, selectbackground=SEL_BG,
                        selectforeground=FG, font=FONT, height=8,
                        yscrollcommand=sb_off.set, activestyle="none",
                        exportselection=False)
    lb_off.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb_off.config(command=lb_off.yview)

    # Selection exclusive : cliquer dans une liste vide la selection de l'autre.
    lb_on.bind("<<ListboxSelect>>",
               lambda e: lb_off.selection_clear(0, tk.END))
    lb_off.bind("<<ListboxSelect>>",
                lambda e: lb_on.selection_clear(0, tk.END))

    status = tk.Label(win, text="", bg=BG, fg=FG, font=("TkFixedFont", 10),
                      anchor="w")
    status.pack(fill=tk.X, padx=10, pady=(2, 0))

    def _set_status(msg):
        status.config(text=msg)

    def _refresh():
        # Remplit les DEUX listes : actives a gauche, desactivees a droite.
        # Les numeros de tuiles sont conserves. Chaque liste a son propre
        # tableau parallele (rows_on / rows_off) pour retrouver la tuile
        # selectionnee.
        lb_on.delete(0, tk.END)
        lb_off.delete(0, tk.END)
        state["rows_on"] = []
        state["rows_off"] = []
        ini = state["ini"]
        if not ini or not os.path.isfile(ini):
            hdr_on.set(_L("ACTIVEES", "ENABLED"))
            hdr_off.set(_L("DESACTIVEES", "DISABLED"))
            _set_status(_L("Choisis d'abord le fichier scenery_packs.ini.",
                           "Please choose scenery_packs.ini first."))
            return
        try:
            text = read_scenery_file(ini)
        except Exception as e:
            _set_status(_L("Lecture impossible : ", "Cannot read: ") + str(e))
            return
        tiles = list_ortho_tiles(text)
        flt = filter_var.get().strip().lower()
        n_on = 0
        n_off = 0
        for tinfo in tiles:
            name = tinfo["path"].rstrip("/").split("/")[-1]
            if flt and flt not in name.lower():
                continue
            if tinfo["enabled"]:
                lb_on.insert(tk.END, " " + name)
                state["rows_on"].append(tinfo)
                n_on += 1
            else:
                lb_off.insert(tk.END, " " + name)
                state["rows_off"].append(tinfo)
                n_off += 1

        hdr_on.set(_L("ACTIVEES (%d)", "ENABLED (%d)") % n_on)
        hdr_off.set(_L("DESACTIVEES (%d)", "DISABLED (%d)") % n_off)
        _set_status(_L("%d activee(s) / %d desactivee(s).",
                       "%d enabled / %d disabled.") % (n_on, n_off))

    def _selected():
        sel = lb_on.curselection()
        if sel:
            return state["rows_on"][sel[0]]
        sel = lb_off.curselection()
        if sel:
            return state["rows_off"][sel[0]]
        messagebox.showinfo(win.title(),
                            _L("Selectionne une tuile dans une des deux listes.",
                               "Select a tile in one of the two lists."))
        return None

    def _choose_ini():
        p = filedialog.askopenfilename(
            parent=win,
            title=_L("Choisir scenery_packs.ini",
                     "Choose scenery_packs.ini"),
            filetypes=[("scenery_packs.ini", "scenery_packs.ini"),
                       (_L("Tous les fichiers", "All files"), "*")])
        if p:
            state["ini"] = p
            ini_var.set(p)
            save_ini_path(p)
            _refresh()

    def _xp_block():
        msg = xplane_is_open()
        if msg:
            messagebox.showwarning(win.title(), msg)
            return True
        return False

    def _enable(flag):
        if _xp_block():
            return
        t = _selected()
        if not t:
            return
        ok, msg = toggle_tile_in_file(state["ini"], t["path"], flag)
        if not ok:
            messagebox.showerror(win.title(), msg)
        _refresh()
        _set_status((_L("Activee : ", "Enabled: ") if flag
                     else _L("Desactivee : ", "Disabled: ")) + t["path"])

    def _delete_tile():
        if _xp_block():
            return
        t = _selected()
        if not t:
            return
        target = tile_abspath(state["ini"], t["path"])
        is_link = os.path.islink(target)
        if is_link:
            q = _L("Retirer le LIEN de cette tuile ? Les donnees pointees NE "
                   "seront PAS supprimees.\n\n",
                   "Remove this tile's LINK? The pointed data will NOT be "
                   "deleted.\n\n") + t["path"]
        else:
            q = _L("SUPPRIMER definitivement le dossier de cette tuile ?\n\n",
                   "PERMANENTLY delete this tile's folder?\n\n") + target
        if not messagebox.askyesno(win.title(), q):
            return
        ok, msg = delete_tile_folder(state["ini"], t["path"])
        if not ok:
            messagebox.showerror(win.title(), msg)
            return
        remove_tile_from_file(state["ini"], t["path"])
        _refresh()
        _set_status(_L("Supprimee : ", "Deleted: ") + msg)

    def _clear_cache():
        t = _selected()
        if not t:
            return
        ll = tile_latlon_from_path(t["path"])
        if not ll:
            messagebox.showinfo(win.title(),
                                _L("Coordonnees non reconnues pour cette tuile.",
                                   "Could not read this tile's coordinates."))
            return
        (lat, lon) = ll
        dirs = tile_cache_dirs(lat, lon)
        if not dirs:
            _set_status(_L("Aucun cache a vider pour cette tuile.",
                           "No cache to clear for this tile."))
            return
        liste = "\n".join("  - %s : %s" % (lbl, d) for lbl, d in dirs)
        q = _L("Vider le cache de cette tuile ? Dossiers supprimes :\n\n",
               "Clear this tile's cache? Folders to delete:\n\n") + liste
        if not messagebox.askyesno(win.title(), q):
            return
        ok, res = clear_tile_cache(lat, lon)
        if not ok:
            messagebox.showerror(win.title(), str(res))
            return
        _refresh()
        _set_status(_L("Cache vide : ", "Cache cleared: ") + ", ".join(res)
                    if res else _L("Rien a vider.", "Nothing to clear."))

    space = {"key": None, "jpgs": [], "go": 0.0}

    def _show_space(e=None):
        sel = lb_on.curselection() or lb_off.curselection()
        if not sel:
            return
        rows = state["rows_on"] if lb_on.curselection() else state["rows_off"]
        t = rows[sel[0]]
        ll = tile_latlon_from_path(t["path"])
        if not ll:
            return
        space["key"] = ll
        _set_status(_L("Calcul de la place…", "Measuring space…"))

        def _work():
            res = tile_space(*ll)
            try:
                dup = overlay_packs_for_tile(state["ini"], ll[0], ll[1])
            except Exception:
                dup = []

            def _done():
                if space["key"] != ll:
                    return
                space["jpgs"], space["go"] = res[0], res[1]
                msg_ = _L("Images téléchargées : %.1f Go  ·  cache : "
                          "%.1f Go" % (res[1], res[2]),
                          "Downloaded images: %.1f GB  ·  cache: "
                          "%.1f GB" % (res[1], res[2]))
                if len(dup) >= 2:
                    msg_ += _L("  ·  ⚠ routes en double : ",
                               "  ·  ⚠ roads twice: ") + ", ".join(dup)
                _set_status(msg_)
            try:
                win.after(0, _done)
            except Exception:
                pass

        import threading as _th
        _th.Thread(target=_work, daemon=True).start()

    lb_on.bind("<<ListboxSelect>>", _show_space, add="+")
    lb_off.bind("<<ListboxSelect>>", _show_space, add="+")

    def _free_images():
        t = _selected()
        if not t:
            return
        ll = tile_latlon_from_path(t["path"])
        if not ll:
            messagebox.showinfo(win.title(),
                                _L("Coordonnees non reconnues pour cette tuile.",
                                   "Could not read this tile's coordinates."))
            return
        jpgs, go, _c = tile_space(*ll)
        if not jpgs:
            _set_status(_L("Aucune image telechargee pour cette tuile.",
                           "No downloaded image for this tile."))
            return
        if not messagebox.askyesno(
                win.title(),
                _L("Supprimer les images telechargees de cette tuile "
                   "(%.1f Go) ?\n\nLa tuile reste complete dans X-Plane, "
                   "mais la reconstruire plus tard sera plus long : tout sera "
                   "retelecharge." % go,
                   "Delete this tile's downloaded images (%.1f GB)?\n\nThe "
                   "tile stays complete in X-Plane, but rebuilding it later "
                   "will take longer: everything will be downloaded again."
                   % go), default="no"):
            return
        try:
            import O4_Build_Comfort_Utils as BC
            n = BC.delete_files(jpgs)
        except Exception as e:
            messagebox.showerror(win.title(), str(e))
            return
        _set_status(_L("%d image(s) supprimee(s), %.1f Go liberes."
                       % (n, go), "%d image(s) deleted, %.1f GB freed."
                       % (n, go)))

    # --- boutons bas ---
    bot = tk.Frame(win, bg=BG)
    bot.pack(fill=tk.X, padx=10, pady=(4, 10))
    _btn(bot, _L("Choisir scenery_packs.ini", "Choose scenery_packs.ini"),
         _choose_ini).grid(row=0, column=0, padx=4, pady=3, sticky="ew")
    _btn(bot, _L("Rafraichir", "Refresh"),
         _refresh).grid(row=0, column=1, padx=4, pady=3, sticky="ew")
    _btn(bot, _L("Activer", "Enable"),
         lambda: _enable(True)).grid(row=1, column=0, padx=4, pady=3, sticky="ew")
    _btn(bot, _L("Desactiver", "Disable"),
         lambda: _enable(False)).grid(row=1, column=1, padx=4, pady=3, sticky="ew")
    _btn(bot, _L("Supprimer la tuile", "Delete tile"),
         _delete_tile).grid(row=2, column=0, padx=4, pady=3, sticky="ew")
    _btn(bot, _L("Vider le cache", "Clear cache"),
         _clear_cache).grid(row=2, column=1, padx=4, pady=3, sticky="ew")
    _btn(bot, _L("Liberer les images telechargees",
                 "Free downloaded images"),
         _free_images).grid(row=3, column=0, columnspan=2, padx=4, pady=3,
                            sticky="ew")

    # --- (nov. 2026) ajouter / déplacer / reconstruire / routes en double ---
    def _busy_block():
        try:
            import O4_UI_Utils as UI
            if getattr(UI, "is_working", False):
                messagebox.showwarning(win.title(), _L(
                    "Une construction est en cours : attendez la fin.",
                    "A build is running: wait for it to end."))
                return True
        except Exception:
            pass
        return False

    def _add_folder():
        if _xp_block() or _busy_block():
            return
        if not state["ini"] or not os.path.isfile(state["ini"]):
            _choose_ini()
            if not state["ini"] or not os.path.isfile(state["ini"]):
                return
        d = filedialog.askdirectory(
            parent=win, title=_L("Dossier qui contient vos tuiles (dossier "
                                 "Ortho4XP, Tiles, ou un disque de tuiles)",
                                 "Folder holding your tiles (Ortho4XP "
                                 "folder, Tiles, or a disk of tiles)"))
        if not d:
            return
        found = find_tile_folders(d)
        if not found:
            messagebox.showinfo(win.title(), _L(
                "Aucune tuile Ortho4XP (zOrtho4XP_…) trouvée dans ce dossier.",
                "No Ortho4XP tile (zOrtho4XP_…) found in this folder."))
            return
        names = ", ".join(os.path.basename(x) for x in found[:10]) + (
            " …" if len(found) > 10 else "")
        if not messagebox.askyesno(win.title(), _L(
                "Ajouter %d tuile(s) à X-Plane ?\n\n%s\n\nUn lien est créé "
                "dans Custom Scenery (aucune copie) ; scenery_packs.ini est "
                "sauvegardé avant (.bak)." % (len(found), names),
                "Add %d tile(s) to X-Plane?\n\n%s\n\nA link is made in "
                "Custom Scenery (no copy); scenery_packs.ini is backed up "
                "first (.bak)." % (len(found), names))):
            return
        try:
            import O4_Scenery_Installer_Utils as SI
            rep_ = SI.install_tiles(found, ini_path=state["ini"])
        except Exception as e:
            messagebox.showerror(win.title(), str(e))
            return
        ok_n = sum(1 for r in rep_ if r[1])
        ko = ["%s : %s" % (r[0], r[2]) for r in rep_ if not r[1]]
        _refresh()
        (messagebox.showinfo if not ko else messagebox.showwarning)(
            win.title(), _L("%d tuile(s) ajoutée(s).", "%d tile(s) added.")
            % ok_n + ("\n" + "\n".join(ko[:10]) if ko else ""))

    def _move():
        if _xp_block() or _busy_block():
            return
        t_ = _selected()
        if not t_:
            return
        d = filedialog.askdirectory(
            parent=win, title=_L("Nouveau dossier pour cette tuile (autre "
                                 "disque)", "New folder for this tile "
                                 "(another disk)"))
        if not d:
            return
        target = tile_abspath(state["ini"], t_["path"])
        data = os.path.realpath(target)
        n, b = folder_stats(data) if os.path.isdir(data) else (0, 0)
        warn = "" if is_link(target) else _L(
            "\n\nLa tuile est aujourd'hui un vrai dossier dans Custom "
            "Scenery : il sera SUPPRIMÉ une fois la copie vérifiée et le lien "
            "posé.", "\n\nThe tile is today a real folder in Custom "
            "Scenery: it will be DELETED once the copy is checked and the "
            "link is in place.")
        if not messagebox.askyesno(win.title(), _L(
                "Déplacer %s (%d fichiers, %.1f Go) vers :\n%s ?\n\nLa "
                "copie est vérifiée avant que X-Plane ne pointe dessus."
                % (_pack_name(t_["path"]), n, b / 1024.0 ** 3, d),
                "Move %s (%d files, %.1f GB) to:\n%s?\n\nThe copy is "
                "checked before X-Plane points to it."
                % (_pack_name(t_["path"]), n, b / 1024.0 ** 3, d)) + warn,
                default="no"):
            return
        _set_status(_L("Copie en cours…", "Copying…"))
        box = {}

        def _work():
            box["r"] = move_tile(state["ini"], t_["path"], d)

        import threading as _th
        th = _th.Thread(target=_work, daemon=True)
        th.start()

        def _poll():
            if th.is_alive():
                win.after(500, _poll)
                return
            ok, old, msg = box.get("r", (False, None, "?"))
            if not ok:
                _set_status(_L("Déplacement annulé : ", "Move cancelled: ")
                            + str(msg))
                messagebox.showwarning(win.title(), _L(
                    "Déplacement annulé, rien n'a changé : ",
                    "Move cancelled, nothing changed: ") + str(msg))
                return
            _set_status(_L("Tuile déplacée.", "Tile moved."))
            if old and os.path.isdir(old) and messagebox.askyesno(
                    win.title(), _L(
                        "La tuile est déplacée et X-Plane la lit au nouvel "
                        "endroit.\n\nEffacer l'ancienne copie pour libérer "
                        "la place ?\n%s" % old,
                        "The tile is moved and X-Plane reads it at the new "
                        "place.\n\nDelete the old copy to free the space?"
                        "\n%s" % old), default="no"):
                try:
                    shutil.rmtree(old)
                    _set_status(_L("Tuile déplacée, ancienne copie effacée.",
                                   "Tile moved, old copy deleted."))
                except Exception as e:
                    messagebox.showerror(win.title(), str(e))
            _refresh()

        win.after(500, _poll)

    def _rebuild():
        if _xp_block() or _busy_block():
            return
        t_ = _selected()
        if not t_:
            return
        if not messagebox.askyesno(win.title(), _L(
                "Reconstruire %s avec les réglages de son .cfg ?\n\nLes "
                "images déjà téléchargées sont réutilisées. Le détail "
                "s'affiche dans la fenêtre principale."
                % _pack_name(t_["path"]),
                "Rebuild %s with the settings of its .cfg?\n\nImages "
                "already downloaded are reused. Details show in the main "
                "window." % _pack_name(t_["path"]))):
            return
        _set_status(_L("Reconstruction en cours…", "Rebuilding…"))
        box = {}

        def _work():
            box["r"] = rebuild_tile(state["ini"], t_["path"])

        import threading as _th
        th = _th.Thread(target=_work, daemon=True)
        th.start()

        def _poll():
            if th.is_alive():
                win.after(1000, _poll)
                return
            ok, msg = box.get("r", (False, "?"))
            _set_status((_L("Reconstruite : ", "Rebuilt: ") if ok else
                         _L("Reconstruction : ", "Rebuild: ")) + str(msg))
            try:
                import O4_Build_Comfort_Utils as BC
                BC.notify("Ortho4XP V4", _L("Reconstruction terminée",
                                            "Rebuild finished"))
            except Exception:
                pass

        win.after(1000, _poll)

    def _check_dups():
        if not state["ini"] or not os.path.isfile(state["ini"]):
            _choose_ini()
            return
        res = duplicate_overlays(state["ini"])
        if not res:
            messagebox.showinfo(win.title(), _L(
                "Aucune route en double repérée sur vos tuiles Ortho4XP.",
                "No roads drawn twice found on your Ortho4XP tiles."))
            return
        lines = ["%s : %s" % ("%+03d%+04d" % k, ", ".join(v))
                 for k, v in sorted(res.items())]
        messagebox.showwarning(win.title(), _L(
            "Routes / forêts / bâtiments dessinés deux fois (elles "
            "clignotent) sur %d tuile(s) :\n\n%s\n\nDésactivez l'un des "
            "paquets ci-dessus pour ces tuiles (rien n'a été changé)."
            % (len(res), "\n".join(lines[:15])),
            "Roads / forests / buildings drawn twice (they flicker) on %d "
            "tile(s):\n\n%s\n\nDisable one of the packs above for these "
            "tiles (nothing was changed)." % (len(res),
                                               "\n".join(lines[:15]))))

    _btn(bot, _L("📂 Ajouter des tuiles d'un dossier…",
                 "📂 Add tiles from a folder…"),
         _add_folder).grid(row=4, column=0, padx=4, pady=3, sticky="ew")
    _btn(bot, _L("🚚 Déplacer vers un autre disque…",
                 "🚚 Move to another disk…"),
         _move).grid(row=4, column=1, padx=4, pady=3, sticky="ew")
    _btn(bot, _L("🔁 Reconstruire la tuile", "🔁 Rebuild the tile"),
         _rebuild).grid(row=5, column=0, padx=4, pady=3, sticky="ew")
    _btn(bot, _L("🔎 Routes en double ?", "🔎 Roads drawn twice?"),
         _check_dups).grid(row=5, column=1, padx=4, pady=3, sticky="ew")
    bot.grid_columnconfigure(0, weight=1)
    bot.grid_columnconfigure(1, weight=1)

    filter_var.trace_add("write", lambda *a: _refresh())

    # Taille souhaitee 720x560, PLAFONNEE a l'ecran reel (universel, multi-OS).
    # Sur grand ecran : min() garde 720x560 -> aucune regression. Sur ecran
    # scaled/petit (retour forum Windows 175 %) : la fenetre ne deborde plus,
    # les boutons du bas restent visibles, la liste defile.
    _want_w, _want_h = 720, 660   # nov. 2026 : 2 rangées de boutons en plus
    try:
        _win_w = min(_want_w, int(win.winfo_screenwidth() * 0.95))
        _win_h = min(_want_h, int(win.winfo_screenheight() * 0.90))
    except Exception:
        _win_w, _win_h = _want_w, _want_h
    win.geometry("%dx%d" % (_win_w, _win_h))
    try:
        win.minsize(min(480, _win_w), min(360, _win_h))
    except Exception:
        pass
    if not state["ini"]:
        _set_status(_L("Choisis le fichier scenery_packs.ini pour commencer.",
                       "Choose scenery_packs.ini to start."))
    else:
        _refresh()
    return win


# ------------------------------------------------------------------------------
# AUTO-TEST HEADLESS (coeur uniquement ; la fenetre se teste chez Roland)
# ------------------------------------------------------------------------------
if __name__ == "__main__":
    sample = (
        "I\n"
        "1000 Version\n"
        "SCENERY\n"
        "\n"
        "SCENERY_PACK Custom Scenery/Aerosoft - LFMN Nice/\n"
        "SCENERY_PACK Custom Scenery/zOrtho4XP_+46-003/\n"
        "SCENERY_PACK *GLOBAL_AIRPORTS*\n"
        "SCENERY_PACK Custom Scenery/zOrtho4XP_+47+005_17_Dijon_XP12_2025-11 symlink/\n"
        "SCENERY_PACK_DISABLED Custom Scenery/zOrtho4XP_+61+023/\n"
    )
    ok = True

    tiles = list_ortho_tiles(sample)
    print("Tuiles Ortho :", len(tiles), "(attendu 3)")
    ok &= (len(tiles) == 3)

    # desactiver
    t2, ch = set_tile_enabled(sample, "Custom Scenery/zOrtho4XP_+46-003/", False)
    ok &= ch and ("SCENERY_PACK_DISABLED Custom Scenery/zOrtho4XP_+46-003/" in t2)
    ok &= (t2.count("\n") == sample.count("\n"))
    ok &= ("SCENERY_PACK Custom Scenery/Aerosoft - LFMN Nice/" in t2)
    ok &= ("*GLOBAL_AIRPORTS*" in t2)
    ok &= ("zOrtho4XP_+47+005_17_Dijon_XP12_2025-11 symlink/" in t2)
    print("Desactivation +46-003 : OK")

    # reactiver un OFF
    t3, ch3 = set_tile_enabled(sample, "Custom Scenery/zOrtho4XP_+61+023/", True)
    ok &= ch3 and ("SCENERY_PACK Custom Scenery/zOrtho4XP_+61+023/" in t3)
    ok &= ("SCENERY_PACK_DISABLED Custom Scenery/zOrtho4XP_+61+023/" not in t3)

    # idempotence + matching strict
    _, ch4 = set_tile_enabled(sample, "Custom Scenery/zOrtho4XP_+61+023/", False)
    ok &= (ch4 is False)
    _, ch5 = set_tile_enabled(sample, "Custom Scenery/zOrtho4XP_+99+099/", False)
    ok &= (ch5 is False)

    # retrait de ligne
    t6, rm = remove_tile_line(sample, "Custom Scenery/zOrtho4XP_+46-003/")
    ok &= rm and ("zOrtho4XP_+46-003/" not in t6)
    ok &= (t6.count("\n") == sample.count("\n") - 1)
    print("Retrait de ligne +46-003 : OK")

    # lat/lon depuis nom (simple + long + symlink)
    ok &= (tile_latlon_from_path("Custom Scenery/zOrtho4XP_+46-003/") == (46, -3))
    ok &= (tile_latlon_from_path("zOrtho4XP_+47+005_17_Dijon_XP12_2025-11 symlink/") == (47, 5))
    ok &= (tile_latlon_from_path("Custom Scenery/Aerosoft - LFMN Nice/") is None)
    print("Extraction lat/lon : OK")

    # xplane root / abspath
    ini = "/X/Custom Scenery/scenery_packs.ini"
    ok &= (xplane_root_from_ini(ini) == "/X")
    ok &= (tile_abspath(ini, "Custom Scenery/zOrtho4XP_+46-003/")
           == "/X/Custom Scenery/zOrtho4XP_+46-003")
    print("Chemins X-Plane : OK")

    # cycle fichier reel (tmp) : toggle + .bak + remove
    import tempfile
    d = tempfile.mkdtemp()
    p = os.path.join(d, "scenery_packs.ini")
    with open(p, "w", encoding="utf-8") as f:
        f.write(sample)
    r1 = toggle_tile_in_file(p, "Custom Scenery/zOrtho4XP_+46-003/", False)
    ok &= (r1[0] is True)
    ok &= os.path.isfile(p + ".bak")
    ok &= ("SCENERY_PACK_DISABLED Custom Scenery/zOrtho4XP_+46-003/"
           in read_scenery_file(p))
    r2 = remove_tile_from_file(p, "Custom Scenery/zOrtho4XP_+61+023/")
    ok &= (r2[0] is True) and ("zOrtho4XP_+61+023/" not in read_scenery_file(p))
    print("Cycle fichier reel (.bak + ecriture) : OK")
    shutil.rmtree(d, ignore_errors=True)

    print("\n=== RESULTAT :", "TOUT VERT" if ok else "ECHEC", "===")
