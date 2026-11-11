# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# O4_Update_Utils.py
# Avertissement de nouvelle version d'Ortho4XP (novembre 2026).
# Auteur : Roland (Ypsos) - GPLv3
#
# 100 % ADDITIF. Rien n'est téléchargé ni installé : on demande seulement à
# GitHub le numéro de la dernière version publiée (au plus une fois par jour)
# et on affiche une ligne avec le lien vers sa page. Toute erreur (pas de
# réseau, dépôt introuvable…) = silence, rien ne s'affiche.
# Désactivable : fichier privé .update_check.json, clé "enabled".
# Compatible macOS / Windows / Linux.
# ------------------------------------------------------------------------------

import json
import os
import re
import time

REPO = "Ypsos/ORTHO4XP_V4"
API_URL = "https://api.github.com/repos/%s/releases/latest"
PAGE_URL = "https://github.com/%s/releases/latest"
DAY = 24 * 3600
_STATE_FILE = ".update_check.json"


def _lang_code():
    for modname, attr in (("O4_Lang", "_current_lang"),
                          ("O4_Lang", "current_lang")):
        try:
            mod = __import__(modname)
            code = getattr(mod, attr, None)
            if callable(code):
                code = code()
            if isinstance(code, str) and code:
                return code[:2].lower()
        except Exception:
            pass
    return "en"


def _L(fr, en):
    return fr if _lang_code() == "fr" else en


def version_tuple(text):
    """PUR. « V4.0 », « v4.0.1 », « 4.1 - sRGB… » -> (4, 0) / (4, 0, 1) /
    (4, 1). None si aucun numéro."""
    m = re.search(r"(\d+)(?:\.(\d+))?(?:\.(\d+))?", str(text or ""))
    if not m:
        return None
    nums = [int(g) for g in m.groups() if g is not None]
    while len(nums) > 1 and nums[-1] == 0:
        nums.pop()
    return tuple(nums)


def is_newer(latest, current):
    """PUR. La version publiée est-elle plus récente que celle-ci ?"""
    a, b = version_tuple(latest), version_tuple(current)
    if a is None or b is None:
        return False
    return a > b


def current_version():
    try:
        import O4_Version
        return getattr(O4_Version, "version_short", "") or ""
    except Exception:
        return ""


def _root_dir():
    try:
        import O4_File_Names as FNAMES
        return FNAMES.Ortho4XP_dir
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def state_path():
    return os.path.join(_root_dir(), _STATE_FILE)


def load_state(path=None):
    try:
        with open(path or state_path(), "r", encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def save_state(d, path=None):
    try:
        with open(path or state_path(), "w", encoding="utf-8") as f:
            json.dump(d, f)
        return True
    except Exception:
        return False


def is_enabled(path=None):
    return bool(load_state(path).get("enabled", True))


def set_enabled(flag, path=None):
    d = load_state(path)
    d["enabled"] = bool(flag)
    return save_state(d, path)


def fetch_latest(session=None, timeout=10, repo=REPO):
    """Numéro (tag) de la dernière version publiée, ou "" (jamais d'erreur)."""
    try:
        if session is None:
            import requests
            session = requests
        r = session.get(API_URL % repo, timeout=timeout,
                        headers={"Accept": "application/vnd.github+json"})
        if getattr(r, "status_code", 200) != 200:
            return ""
        d = r.json()
        if d.get("draft") or d.get("prerelease"):
            return ""
        return str(d.get("tag_name") or d.get("name") or "")
    except Exception:
        return ""


def check(now=None, force=False, session=None, path=None):
    """Renvoie (dernière_version, page) si une version plus récente existe,
    sinon None. GitHub est consulté au plus une fois par jour (sauf force)."""
    now = time.time() if now is None else now
    st = load_state(path)
    if not force and not st.get("enabled", True):
        return None
    latest = st.get("latest", "")
    if force or "last" not in st or \
            not (0 <= now - float(st.get("last") or 0) < DAY):
        got = fetch_latest(session=session)
        st["last"] = now
        if got:
            st["latest"] = latest = got
        save_state(st, path)
    if latest and is_newer(latest, current_version()):
        return (latest, PAGE_URL % REPO)
    return None


def message(found):
    """Texte de la ligne d'avertissement (ou "" si rien)."""
    if not found:
        return ""
    latest, _page = found
    return _L("🆕 Ortho4XP %s est disponible (vous avez %s). Rien n'est "
              "installé tout seul : cliquez pour ouvrir sa page.",
              "🆕 Ortho4XP %s is out (you have %s). Nothing is installed by "
              "itself: click to open its page.") % (latest, current_version())


def open_page(found=None):
    try:
        import webbrowser
        webbrowser.open(found[1] if found else PAGE_URL % REPO)
        return True
    except Exception:
        return False


def check_now_dialog(parent=None, session=None):
    """Pour le menu (mode expert comme mode simple) : vérification tout de
    suite, réponse dans une boîte de dialogue."""
    from tkinter import messagebox
    found = check(force=True, session=session)
    if found:
        if messagebox.askyesno("Ortho4XP", message(found), parent=parent):
            open_page(found)
        return found
    messagebox.showinfo("Ortho4XP", _L(
        "Vous avez la dernière version (%s), ou GitHub n'a pas pu être "
        "consulté." % current_version(),
        "You have the latest version (%s), or GitHub could not be "
        "reached." % current_version()), parent=parent)
    return None
