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
O4_Scenery_Installer_Utils.py — Installation des tuiles dans X-Plane 12.

MODULE AUTONOME (100 % additif). Utilisé par le mode simple (installation
automatique après construction, bouton « Installer / réinstaller ») et par
le Diagnostic (boutons « Corriger »).

CE QU'IL FAIT
  0. Refuse toute modification de la liste des scènes quand X-Plane est
     ouvert (xplane_running : pgrep sous Mac/Linux, tasklist sous Windows ;
     si l'outil manque, rien n'est bloqué).
  1. Installer / réinstaller une tuile : si la tuile est construite hors de
     « Custom Scenery », un LIEN y est créé vers elle (même méthode que la
     fenêtre Expert « Tiles collection », Ctrl+clic : ln -s sous Mac/Linux,
     MKLINK /J sous Windows ; aucune donnée copiée ni déplacée). Puis la
     ligne SCENERY_PACK de la tuile est ajoutée/réactivée dans
     scenery_packs.ini, À LA BONNE PLACE (avec les autres tuiles photo, sous
     les overlays et Global Airports).
  2. Remettre l'ordre : les tuiles photo (Ortho4XP, AutoOrtho, OrthoStudio)
     placées au-dessus d'overlays / SimHeaven / Global Airports sont
     redescendues sous eux. L'ordre relatif des autres lignes ne change pas.
  3. Doublons : quand une même tuile Ortho4XP est activée plusieurs fois, on
     garde la PREMIÈRE (celle que X-Plane affiche déjà) et on désactive les
     autres (SCENERY_PACK_DISABLED : réversible, rien n'est supprimé).

SÉCURITÉ
  - Toute écriture de scenery_packs.ini est précédée d'une sauvegarde
    scenery_packs.ini.bak (même règle que la Bibliothèque de tuiles).
  - Aucune suppression de dossier ou de donnée. Un lien existant vers la
    même tuile est laissé tel quel ; un nom déjà pris par un VRAI dossier
    n'est jamais écrasé.
  - X-Plane réécrit scenery_packs.ini quand il se ferme : il faut le fermer
    avant de modifier (rappelé à l'utilisateur).
"""

import os
import re
import subprocess
import sys

_KW_ON = "SCENERY_PACK "
_KW_OFF = "SCENERY_PACK_DISABLED "
_TILE_RE = re.compile(r"zOrtho4XP_([+-]\d{2})([+-]\d{3})")


# ------------------------------------------------------------------------------
# Bilingue interne
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
# Lecture du fichier (PUR)
# ------------------------------------------------------------------------------
def _entry(line):
    """PUR. (enabled, path) pour une ligne SCENERY_PACK, sinon None."""
    s = line.strip()
    if s.startswith(_KW_OFF):
        return (False, s[len(_KW_OFF):].strip())
    if s.startswith(_KW_ON):
        return (True, s[len(_KW_ON):].strip())
    return None


def kind_of(path):
    """PUR. Catégorie d'une scène d'après son nom de dossier."""
    name = path.rstrip("/\\").replace("\\", "/").split("/")[-1].lower()
    if "zortho4xp_" in name:
        return "photo"
    if name.startswith("z_autoortho") or name.startswith("z_ao_") \
            or "autoortho" in name or "osxp_live" in name and \
            not name.startswith("y_"):
        return "photo"
    if name.startswith("yortho4xp") or "simheaven" in name \
            or "global_airports" in name or "global airports" in name \
            or "overlay" in name:
        return "above"
    return "other"


def _norm(p):
    return p.replace("\\", "/").rstrip("/").lower()


# ------------------------------------------------------------------------------
# Transformations du texte (PURES, testables)
# ------------------------------------------------------------------------------
def fix_order(text):
    """PUR. Redescend les tuiles photo placées au-dessus de la DERNIÈRE ligne
    « à garder au-dessus » (overlays, SimHeaven, Global Airports). Renvoie
    (nouveau_texte, nombre_de_lignes_déplacées)."""
    lines = text.splitlines()
    idx_above = [i for i, l in enumerate(lines)
                 if _entry(l) and kind_of(_entry(l)[1]) == "above"]
    if not idx_above:
        return text, 0
    last_above = idx_above[-1]
    moved = [i for i, l in enumerate(lines)
             if i < last_above and _entry(l) and kind_of(_entry(l)[1]) == "photo"]
    if not moved:
        return text, 0
    keep = [l for i, l in enumerate(lines) if i not in set(moved)]
    # position d'insertion : juste après la dernière ligne « au-dessus »
    new_last = max(i for i, l in enumerate(keep)
                   if _entry(l) and kind_of(_entry(l)[1]) == "above")
    out = keep[:new_last + 1] + [lines[i] for i in moved] + keep[new_last + 1:]
    nl = "\n" if not text.endswith("\r\n") else "\r\n"
    res = nl.join(out)
    if text.endswith(("\n", "\r\n")):
        res += nl
    return res, len(moved)


def disable_duplicates(text):
    """PUR. Désactive les doublons ACTIVÉS d'une même tuile Ortho4XP (on garde
    la première). Renvoie (nouveau_texte, liste des lignes désactivées)."""
    lines = text.splitlines(True)
    seen = set()
    changed = []
    for i, raw in enumerate(lines):
        e = _entry(raw)
        if not e or not e[0]:
            continue
        m = _TILE_RE.search(e[1])
        if not m:
            continue
        key = m.group(1) + m.group(2)
        if key in seen:
            end = "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else "")
            lines[i] = _KW_OFF + e[1] + end
            changed.append(e[1])
        else:
            seen.add(key)
    return "".join(lines), changed


def ensure_pack(text, pack_path):
    """PUR. Fait figurer `pack_path` ACTIVÉ dans le fichier :
       - déjà présent activé : rien ;
       - présent désactivé : réactivé à sa place ;
       - absent : ajouté juste avant la première tuile photo existante (les
         tuiles photo restent groupées), sinon tout en bas du fichier (règle
         X-Plane : la photo sous tout le reste, aéroports perso compris).
    Renvoie (nouveau_texte, action) avec action dans
    {"present", "reactivee", "ajoutee"}."""
    lines = text.splitlines(True)
    target = _norm(pack_path)
    for i, raw in enumerate(lines):
        e = _entry(raw)
        if e and _norm(e[1]) == target:
            if e[0]:
                return text, "present"
            end = "\r\n" if raw.endswith("\r\n") else ("\n" if raw.endswith("\n") else "")
            lines[i] = _KW_ON + e[1] + end
            return "".join(lines), "reactivee"
    nl = "\r\n" if "\r\n" in text else "\n"
    new_line = _KW_ON + pack_path + nl
    pos = None
    for i, raw in enumerate(lines):
        e = _entry(raw)
        if e and kind_of(e[1]) == "photo":
            pos = i
            break
    if lines and not lines[-1].endswith(("\n", "\r\n")):
        lines[-1] += nl
    if pos is None:
        lines.append(new_line)
    else:
        lines.insert(pos, new_line)
    return "".join(lines), "ajoutee"


# ------------------------------------------------------------------------------
# X-Plane : où sont Custom Scenery et scenery_packs.ini ?
# ------------------------------------------------------------------------------
def find_ini():
    try:
        import O4_Tile_Library_Utils as TL
        p = TL.guess_ini_path()
        if p and os.path.isfile(p):
            return p
    except Exception:
        pass
    try:
        import O4_Config_Utils as CFG
        cs = getattr(CFG, "custom_scenery_dir", "") or ""
        p = os.path.join(cs, "scenery_packs.ini")
        if cs and os.path.isfile(p):
            return p
    except Exception:
        pass
    return ""


def pack_path_for(custom_scenery_dir, folder_name):
    """Ligne écrite dans scenery_packs.ini (même forme que X-Plane)."""
    return "Custom Scenery/" + folder_name + "/"


def is_inside(path, base):
    try:
        p = os.path.normcase(os.path.abspath(path)).rstrip("\\/")
        b = os.path.normcase(os.path.abspath(base)).rstrip("\\/")
        return p == b or p.startswith(b + os.sep)
    except Exception:
        return False


def make_link(target, link):
    """Crée le lien `link` -> `target` (dossier). Renvoie (ok, message)."""
    if os.path.lexists(link):
        try:
            if os.path.realpath(link) == os.path.realpath(target):
                return True, "deja"
        except Exception:
            pass
        if os.path.islink(link):
            return False, _L("un autre lien porte déjà ce nom",
                             "another link already has this name")
        return False, _L("un dossier porte déjà ce nom dans Custom Scenery",
                         "a folder already has this name in Custom Scenery")
    try:
        if sys.platform.startswith("win"):
            r = subprocess.run(["cmd", "/c", "mklink", "/J", link, target],
                               capture_output=True, text=True)
            if r.returncode != 0:
                return False, (r.stderr or r.stdout or "mklink").strip()
        else:
            os.symlink(target, link)
        return True, "lien"
    except Exception as e:
        return False, str(e)


def _write_with_bak(ini_path, new_text):
    with open(ini_path, "r", encoding="utf-8", errors="replace") as f:
        old = f.read()
    with open(ini_path + ".bak", "w", encoding="utf-8") as f:
        f.write(old)
    with open(ini_path, "w", encoding="utf-8") as f:
        f.write(new_text)


# ------------------------------------------------------------------------------
# Actions (avec écriture)
# ------------------------------------------------------------------------------
# ------------------------------------------------------------------------------
# X-Plane ouvert ?
# ------------------------------------------------------------------------------
_XP_NAMES = {
    "darwin": ["pgrep", "-x", "X-Plane"],
    "linux": ["pgrep", "-f", "X-Plane-x86_64"],
}


def xplane_running(platform=None, run=None):
    """True si X-Plane tourne, False sinon, None si on ne sait pas (outil du
    système absent) — dans ce cas on ne bloque rien.
      macOS   : pgrep -x X-Plane
      Windows : tasklist (X-Plane.exe)
      Linux   : pgrep -f X-Plane-x86_64"""
    platform = platform or sys.platform
    run = run or subprocess.run
    try:
        if platform.startswith("win"):
            kw = {}
            if hasattr(subprocess, "CREATE_NO_WINDOW"):
                kw["creationflags"] = subprocess.CREATE_NO_WINDOW
            r = run(["tasklist", "/FI", "IMAGENAME eq X-Plane.exe", "/NH"],
                    capture_output=True, text=True, timeout=10, **kw)
            return "x-plane.exe" in (r.stdout or "").lower()
        cmd = _XP_NAMES["darwin" if platform == "darwin" else "linux"]
        r = run(cmd, capture_output=True, text=True, timeout=10)
        if r.returncode == 0:
            return True
        if r.returncode == 1:
            return False
        return None
    except Exception:
        return None


def xplane_open_message():
    return _L("X-Plane est ouvert : la liste des scènes ne peut pas être "
              "modifiée maintenant (X-Plane la réécrirait). Quittez X-Plane, "
              "puis recommencez.",
              "X-Plane is running: the scenery list cannot be changed now "
              "(X-Plane would rewrite it). Quit X-Plane, then try again.")


def install_tiles(build_dirs, ini_path=None, linker=make_link,
                  running=xplane_running):
    """Installe / réinstalle des tuiles construites (liste de dossiers).
    Renvoie une liste de (nom_tuile, ok, message). Refuse si X-Plane est
    ouvert."""
    if running() is True:
        return [("", False, xplane_open_message())]
    ini = ini_path or find_ini()
    if not ini:
        return [("", False, _L(
            "Fichier scenery_packs.ini de X-Plane introuvable : indiquez-le "
            "une fois dans la Bibliothèque de tuiles.",
            "X-Plane scenery_packs.ini not found: set it once in the Tile "
            "library."))]
    cs = os.path.dirname(ini)
    with open(ini, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    report = []
    for bd in build_dirs:
        name = os.path.basename(os.path.normpath(bd))
        if not os.path.isdir(bd):
            report.append((name, False, _L("dossier de la tuile introuvable",
                                           "tile folder not found")))
            continue
        if is_inside(bd, cs) and os.path.dirname(os.path.normpath(bd)) == \
                os.path.normpath(cs):
            folder = name
        else:
            folder = name
            ok, msg = linker(os.path.abspath(bd), os.path.join(cs, folder))
            if not ok:
                report.append((name, False, msg))
                continue
        text, action = ensure_pack(text, pack_path_for(cs, folder))
        report.append((name, True, {
            "present": _L("déjà installée", "already installed"),
            "reactivee": _L("réactivée", "re-enabled"),
            "ajoutee": _L("installée", "installed")}[action]))
    _write_with_bak(ini, text)
    return report


def fix_order_in_file(ini_path=None, running=xplane_running):
    if running() is True:
        return (False, 0)
    ini = ini_path or find_ini()
    if not ini:
        return (False, 0)
    with open(ini, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    new, n = fix_order(text)
    if n:
        _write_with_bak(ini, new)
    return (True, n)


def disable_duplicates_in_file(ini_path=None, running=xplane_running):
    if running() is True:
        return (False, [])
    ini = ini_path or find_ini()
    if not ini:
        return (False, [])
    with open(ini, "r", encoding="utf-8", errors="replace") as f:
        text = f.read()
    new, changed = disable_duplicates(text)
    if changed:
        _write_with_bak(ini, new)
    return (True, changed)


def close_xplane_warning():
    return _L("Fermez X-Plane avant de continuer : il réécrit la liste des "
              "scènes quand il se ferme.",
              "Close X-Plane before continuing: it rewrites the scenery list "
              "when it quits.")
