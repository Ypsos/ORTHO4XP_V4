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
O4_Build_Comfort_Utils.py — Confort pendant et après une construction.

MODULE AUTONOME (100 % additif), utilisé par le mode simple
(O4_Grand_Public_Utils). Aucun accès réseau, aucun tkinter.
Compatible macOS, Windows et Linux : chaque fonction choisit la méthode du
système et, si elle échoue, se tait (elle ne gêne jamais la construction).

  1. KeepAwake : empêche la mise en veille de l'ordinateur pendant la
     construction (l'écran peut s'éteindre).
       macOS   : « caffeinate -i -w <pid Ortho4XP> » (s'arrête seul si
                 Ortho4XP se ferme) ;
       Windows : SetThreadExecutionState (API système, via ctypes) ;
       Linux   : « systemd-inhibit » s'il est présent.
  2. notify(titre, message) : signal de fin (son + notification système).
       macOS   : son Glass (afplay), sans notification système : aucune
                 autorisation à donner ;
       Windows : son système (winsound) ;
       Linux   : notify-send s'il est présent.
  3. Historique des durées : après chaque tuile construite, nombre de
     textures et durée réelle sont notés dans .grand_public_history.json
     (racine Ortho4XP, 30 dernières tuiles). La durée estimée suivante en
     découle (temps médian par texture).
  5. Mode expert : activity_begin() / activity_end(), appelées par la
     fenêtre principale à chaque étape lancée (boutons Étape 1 à 3, Tout
     construire, construction par lot). Pas de veille pendant les étapes ;
     signal de fin si l'ensemble a duré plus de 2 minutes. Le mode simple
     utilise directement KeepAwake et notify.
  4. Images téléchargées d'une tuile (JPG source) : recherche, taille et
     effacement SUR CONFIRMATION de l'utilisateur. Seuls des fichiers .jpg
     nommés comme le moteur les nomme (<y>_<x>_<source><ZL>.jpg) sont
     concernés ; jamais JPG-Patch, jamais les DDS de la tuile.
"""

import os
import re
import sys
import json
import math
import time
import shutil
import subprocess


# ------------------------------------------------------------------------------
# 1. Empêcher la mise en veille
# ------------------------------------------------------------------------------
_ES_CONTINUOUS = 0x80000000
_ES_SYSTEM_REQUIRED = 0x00000001


class KeepAwake(object):
    """with KeepAwake(): ... — ou start() / stop(). Ne lève jamais."""

    def __init__(self, platform=None, which=None, popen=None):
        self.platform = platform or sys.platform
        self._which = which or shutil.which
        self._popen = popen or subprocess.Popen
        self.proc = None
        self.group = False
        self.win_set = False
        self.method = ""

    def start(self):
        try:
            if self.platform == "darwin":
                if self._which("caffeinate"):
                    self.proc = self._popen(
                        ["caffeinate", "-i", "-w", str(os.getpid())],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    self.method = "caffeinate"
            elif self.platform.startswith("win"):
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(
                    _ES_CONTINUOUS | _ES_SYSTEM_REQUIRED)
                self.win_set = True
                self.method = "SetThreadExecutionState"
            else:
                if self._which("systemd-inhibit"):
                    # Groupe de processus propre : stop() arrête aussi la
                    # commande d'attente (rien ne reste derrière).
                    self.proc = self._popen(
                        ["systemd-inhibit", "--what=idle:sleep",
                         "--who=Ortho4XP", "--why=Ortho4XP build",
                         "sleep", "604800"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        start_new_session=True)
                    self.group = True
                    self.method = "systemd-inhibit"
        except Exception:
            self.proc = None
        return self.method

    def stop(self):
        try:
            if self.proc is not None:
                if self.group and hasattr(os, "killpg"):
                    import signal
                    os.killpg(self.proc.pid, signal.SIGTERM)
                else:
                    self.proc.terminate()
                try:
                    self.proc.wait(timeout=5)
                except Exception:
                    pass
        except Exception:
            pass
        self.proc = None
        self.group = False
        if self.win_set:
            try:
                import ctypes
                ctypes.windll.kernel32.SetThreadExecutionState(_ES_CONTINUOUS)
            except Exception:
                pass
            self.win_set = False

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *a):
        self.stop()
        return False


# ------------------------------------------------------------------------------
# 2. Signal de fin
# ------------------------------------------------------------------------------
def notify(title, message, platform=None, which=None, popen=None):
    """Son + notification système. Renvoie la liste des méthodes lancées."""
    platform = platform or sys.platform
    which = which or shutil.which
    popen = popen or subprocess.Popen
    done = []
    try:
        if platform == "darwin":
            # Son seul : la notification macOS (osascript) demanderait une
            # autorisation pour « Script Editor » que l'utilisateur risque de
            # refuser ou de ne pas comprendre. Le résultat reste affiché dans
            # la fenêtre Ortho4XP.
            snd = "/System/Library/Sounds/Glass.aiff"
            if which("afplay") and os.path.isfile(snd):
                popen(["afplay", snd], stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL)
                done.append("afplay")
        elif platform.startswith("win"):
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
            done.append("winsound")
        else:
            if which("notify-send"):
                popen(["notify-send", str(title), str(message)],
                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                done.append("notify-send")
    except Exception:
        pass
    return done


# ------------------------------------------------------------------------------
# 2b. Mode expert : suivi des étapes lancées depuis la fenêtre principale
# ------------------------------------------------------------------------------
def _L(fr, en):
    try:
        from O4_Lang import current_lang
        return fr if str(current_lang()).upper().startswith("FR") else en
    except Exception:
        return fr


class ActivityTracker(object):
    """Compteur d'étapes en cours (plusieurs étapes peuvent se chevaucher).
    Première étape → KeepAwake ; dernière terminée → fin du blocage de veille
    et, si l'ensemble a duré au moins min_notify_s, signal de fin.
    À appeler depuis le thread principal (Windows : même thread pour le
    début et la fin du blocage de veille)."""

    def __init__(self, min_notify_s=120.0, keep_cls=None, notifier=None,
                 clock=None):
        self.min_notify_s = min_notify_s
        self.keep_cls = keep_cls or KeepAwake
        self.notifier = notifier or notify
        self.clock = clock or time.time
        self.n = 0
        self.t0 = 0.0
        self.ka = None

    def begin(self):
        try:
            if self.n == 0:
                self.t0 = self.clock()
                self.ka = self.keep_cls()
                self.ka.start()
            self.n += 1
        except Exception:
            pass

    def end(self):
        try:
            if self.n <= 0:
                return False
            self.n -= 1
            if self.n:
                return False
            if self.ka is not None:
                self.ka.stop()
            self.ka = None
            if self.clock() - self.t0 >= self.min_notify_s:
                self.notifier("Ortho4XP V4", _L(
                    "Travail terminé — voyez la fenêtre Ortho4XP.",
                    "Work finished — see the Ortho4XP window."))
                return True
        except Exception:
            pass
        return False


_TRACKER = ActivityTracker()


def activity_begin():
    _TRACKER.begin()


def activity_end():
    return _TRACKER.end()


# ------------------------------------------------------------------------------
# 3. Historique des durées
# ------------------------------------------------------------------------------
HISTORY_NAME = ".grand_public_history.json"
HISTORY_MAX = 30


def _root_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def history_path(root=None):
    return os.path.join(root or _root_dir(), HISTORY_NAME)


def read_history(path=None):
    try:
        with open(path or history_path(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return [e for e in data if isinstance(e, dict)
                and float(e.get("textures", 0)) > 0
                and float(e.get("seconds", 0)) > 0]
    except Exception:
        return []


def record_build(tile_name, textures, seconds, quality="", path=None):
    """Ajoute une tuile construite à l'historique (30 dernières)."""
    try:
        textures = int(textures)
        seconds = float(seconds)
        if textures <= 0 or seconds <= 0:
            return False
        h = read_history(path)
        h.append({"tile": tile_name, "textures": textures,
                  "seconds": round(seconds, 3), "quality": quality,
                  "date": time.strftime("%Y-%m-%d")})
        h = h[-HISTORY_MAX:]
        with open(path or history_path(), "w", encoding="utf-8") as f:
            json.dump(h, f, indent=1)
        return True
    except Exception:
        return False


def sec_per_texture(path=None, last=10):
    """PUR (sur le fichier). Temps médian par texture sur les dernières
    constructions : (secondes, nombre de constructions) ou (None, 0)."""
    h = read_history(path)[-last:]
    if not h:
        return (None, 0)
    vals = sorted(e["seconds"] / float(e["textures"]) for e in h)
    n = len(vals)
    med = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2.0
    return (med, n)


def estimate_seconds(textures, path=None):
    """(min, max, n) d'après l'historique, ou None sans historique."""
    spt, n = sec_per_texture(path)
    if not spt or not textures:
        return None
    return (textures * spt * 0.8, textures * spt * 1.25, n)


# ------------------------------------------------------------------------------
# 4. Images téléchargées (JPG source) d'une tuile
# ------------------------------------------------------------------------------
_JPG_RE = re.compile(r"^(\d+)_(\d+)_.+?(\d\d)\.jpg$", re.IGNORECASE)


def _texture_center(til_y, til_x, zl):
    """PUR. Centre (lat, lon) d'une texture (16 × 16 dalles à partir de
    (til_x, til_y) au niveau zl, convention Ortho4XP)."""
    n = 2.0 ** zl
    x = til_x + 8
    y = til_y + 8
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return (lat, lon)


def _tile_names(lat, lon):
    short = "%+03d%+04d" % (lat, lon)
    rlat = int(math.floor(lat / 10.0) * 10)
    rlon = int(math.floor(lon / 10.0) * 10)
    long_ = os.path.join("%+03d%+04d" % (rlat, rlon), short)
    return short, long_


def tile_jpgs(lat, lon, imagery_dir):
    """Liste des JPG source de la tuile (chemins complets).
      - dossiers propres à la tuile (Orthophotos/<+LL+LLL> et
        Orthophotos/<+L0+LL0>/<+LL+LLL>) : tous les JPG nommés par le moteur ;
      - dossiers partagés par source (Orthophotos/<source>/...) : seulement
        les JPG dont le centre est DANS la tuile ;
      - jamais le dossier JPG-Patch."""
    short, long_ = _tile_names(lat, lon)
    out = []
    own = [os.path.join(imagery_dir, short), os.path.join(imagery_dir, long_)]
    own_n = [os.path.normpath(d) for d in own]
    for d in own:
        for root, dirs, files in os.walk(d):
            dirs[:] = [x for x in dirs if x != "JPG-Patch"]
            for f in files:
                if _JPG_RE.match(f):
                    out.append(os.path.join(root, f))
    try:
        top = sorted(os.listdir(imagery_dir))
    except Exception:
        top = []
    for name in top:
        full = os.path.join(imagery_dir, name)
        if name == "JPG-Patch" or not os.path.isdir(full):
            continue
        if re.match(r"^[+-]\d\d[+-]\d\d\d$", name):
            continue                          # dossier d'une tuile
        if any(os.path.normpath(full) == o for o in own_n):
            continue
        for root, dirs, files in os.walk(full):
            dirs[:] = [x for x in dirs if x != "JPG-Patch"
                       and not re.match(r"^[+-]\d\d[+-]\d\d\d$", x)]
            for f in files:
                m = _JPG_RE.match(f)
                if not m:
                    continue
                clat, clon = _texture_center(int(m.group(1)),
                                             int(m.group(2)),
                                             int(m.group(3)))
                if lat <= clat < lat + 1 and lon <= clon < lon + 1:
                    out.append(os.path.join(root, f))
    seen, uniq = set(), []
    for p in out:
        k = os.path.normpath(p)
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def files_size_go(paths):
    tot = 0
    for p in paths:
        try:
            tot += os.path.getsize(p)
        except Exception:
            pass
    return tot / 1024.0 ** 3


def delete_files(paths, remover=os.remove):
    """Efface les fichiers donnés (après confirmation de l'utilisateur).
    Renvoie le nombre de fichiers effacés."""
    n = 0
    for p in paths:
        try:
            if p.lower().endswith(".jpg") and os.path.isfile(p):
                remover(p)
                n += 1
        except Exception:
            pass
    return n
