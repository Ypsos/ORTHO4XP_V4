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

RÈGLES DE CONSTRUCTION (identiques au mode Expert) :
  - la tuile part des réglages globaux, puis de SON .cfg s'il existe
    (custom_dem, zones ZL… sont donc respectés) ;
  - par-dessus : la source d'imagerie de la fenêtre principale et les
    5 réglages du profil de qualité choisi ;
  - mesh_zl est relevé si besoin au ZL le plus haut utilisé (même règle que
    la fenêtre des zones ZL : évite les triangles dans X-Plane) ;
  - le .cfg de la tuile est complété au début (même méthode que l'Expert).

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


def quality_label(q):
    return {
        "fast": _L("🐇  Rapide", "🐇  Fast"),
        "balanced": _L("⚖  Équilibrée (conseillée)", "⚖  Balanced (advised)"),
        "quality": _L("💎  Haute", "💎  High"),
    }.get(q, q)


def quality_help(q):
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
    vals = QUALITIES.get(quality, QUALITIES[DEFAULT_QUALITY])
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


class BuildRunner(object):
    """Construit une liste de tuiles dans UN thread de travail (comme les
    boutons de l'Expert). L'interface lit self.state toutes les 0,5 s : aucun
    appel Tk depuis le thread."""

    def __init__(self, tiles, cbd, quality, provider, do_overlay):
        self.tiles = list(tiles)
        self.cbd = cbd
        self.quality = quality
        self.provider = provider
        self.do_overlay = do_overlay
        self.stop_asked = False
        self.state = {"running": False, "k": 0, "n": len(self.tiles),
                      "current": "", "ok": [], "failed": [], "t0": None,
                      "done": False, "message": ""}

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
        for k, (lat, lon) in enumerate(self.tiles, start=1):
            if self.stop_asked:
                break
            name = short_latlon(lat, lon)
            self.state["k"] = k
            self.state["current"] = name
            ok = False
            try:
                tile = make_tile(lat, lon, self.cbd, self.quality,
                                 self.provider)
                # Même complétion du .cfg tuile que l'Expert au Step 1
                if g is not None and hasattr(g, "_ensure_tile_cfg_complete"):
                    try:
                        g._ensure_tile_cfg_complete(tile)
                    except Exception:
                        pass
                UI.red_flag = False
                ok = bool(TILE.build_all(tile)) and not UI.red_flag
                if ok and self.do_overlay and not self.stop_asked:
                    try:
                        import O4_Overlay_Utils as OVL
                        OVL.build_overlay(lat, lon)
                    except Exception:
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
            (self.state["ok"] if ok else self.state["failed"]).append(name)
            try:
                UI.red_flag = False
            except Exception:
                pass
        self.state["running"] = False
        self.state["done"] = True


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
    win.title(_L("Ortho4XP V3 — Mode simple", "Ortho4XP V3 — Simple mode"))
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

    def _btn(parent_w, text, cmd, bg=None):
        bgc = bg or BTN_BG
        if _HAS_CTK:
            b = _ctk.CTkButton(parent_w, text=text, command=cmd,
                               corner_radius=8, border_width=1, height=34,
                               fg_color=bgc, hover_color=HOVER,
                               border_color=BORDER, text_color=BTN_FG)
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
        "done": set(),
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

    # ============== mise en page : panneau gauche + carte à droite ==========
    win.columnconfigure(1, weight=1)
    win.rowconfigure(0, weight=1)
    left = tk.Frame(win, bg=BG)
    left.grid(row=0, column=0, sticky="nsw", padx=(12, 6), pady=12)
    right = tk.Frame(win, bg=BG)
    right.grid(row=0, column=1, sticky="nsew", padx=(6, 12), pady=12)
    right.rowconfigure(0, weight=1)
    right.columnconfigure(0, weight=1)

    def _title(txt):
        tk.Label(left, text=txt, bg=BG, fg=FG2, font=FONT_T,
                 anchor="w").pack(fill=tk.X, pady=(10, 2))

    # --- 1. Tuiles ---
    _title(_L("1. Choisissez vos tuiles", "1. Choose your tiles"))
    tk.Label(left, text=_L("Clic sur la carte = choisir / retirer une tuile.\n"
                           "Glisser = déplacer la carte.\n"
                           "Vert = déjà construite.",
                           "Click on the map = choose / remove a tile.\n"
                           "Drag = move the map.\nGreen = already built."),
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
    tk.Label(left, text=_L("ex. LFEY, Nantes, +46-003, 46.7, -2.3",
                           "e.g. LFEY, Nantes, +46-003, 46.7, -2.3"),
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
    sel_var = tk.StringVar(value="")
    tk.Label(left, textvariable=sel_var, bg=BG, fg=FG, font=FONT,
             justify="left", anchor="w", wraplength=300).pack(fill=tk.X,
                                                              pady=(6, 2))

    # --- 2. Qualité ---
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

    # --- 3. Vérifier ---
    _title(_L("3. Vérifiez", "3. Check"))
    _btn(left, _L("🔍 Vérifier le projet", "🔍 Check the project"),
         lambda: _check()).pack(fill=tk.X, pady=2)

    # --- 4. Construire ---
    _title(_L("4. Construisez", "4. Build"))
    _btn(left, _L("▶  Construire", "▶  Build"),
         lambda: _build()).pack(fill=tk.X, pady=2)
    _btn(left, _L("⏹  Arrêter", "⏹  Stop"),
         lambda: _stop()).pack(fill=tk.X, pady=2)
    prog_var = tk.StringVar(value="")
    tk.Label(left, textvariable=prog_var, bg=BG, fg=FG, font=FONT,
             justify="left", anchor="w", wraplength=300).pack(fill=tk.X,
                                                              pady=(4, 2))
    pbar = None
    if ttk is not None:
        try:
            pbar = ttk.Progressbar(left, orient="horizontal", mode="determinate",
                                   maximum=100, length=260)
            pbar.pack(fill=tk.X, pady=2)
        except Exception:
            pbar = None
    end_f = tk.Frame(left, bg=BG)
    end_f.pack(fill=tk.X, pady=(8, 0))
    _btn(end_f, _L("📂 Dossier des tuiles", "📂 Tiles folder"),
         lambda: _open_path(working_dir(cbd))).pack(fill=tk.X, pady=2)
    _btn(end_f, _L("🗃 Bibliothèque de tuiles", "🗃 Tile library"),
         lambda: _open_module("O4_Tile_Library_Utils",
                              "run_tile_library")).pack(fill=tk.X, pady=2)
    _btn(end_f, _L("🩺 Diagnostic", "🩺 Diagnostic"),
         lambda: _open_module("O4_Diagnostics_Utils",
                              "run_diagnostics")).pack(fill=tk.X, pady=2)

    # ============== carte ==============
    canvas = tk.Canvas(right, bg="#2b3a33", highlightthickness=0,
                       width=820, height=620,
                       scrollregion=(0, 0, MAP_SIZE, MAP_SIZE))
    canvas.grid(row=0, column=0, sticky="nsew")
    hover_var = tk.StringVar(value="")
    tk.Label(right, textvariable=hover_var, bg=BG, fg=FG, font=FONT_S,
             anchor="w").grid(row=1, column=0, sticky="ew")
    summary_box = tk.Text(right, height=9, wrap="word", bg="#05140a", fg=FG,
                          font=FONT_S, relief="flat", padx=8, pady=6,
                          highlightthickness=0)
    summary_box.grid(row=2, column=0, sticky="ew", pady=(6, 0))
    summary_box.insert("1.0", _L("Le résumé du projet s'affichera ici après "
                                 "« Vérifier le projet ».",
                                 "The project summary will appear here after "
                                 "« Check the project »."))
    summary_box.config(state="disabled")

    earth_prefix = os.path.join(_root_dir(), "Utils", "Earth",
                                "Earth2_ZL%d_" % MAP_ZL)

    def _view_box():
        x0 = canvas.canvasx(0)
        y0 = canvas.canvasy(0)
        w = max(1, canvas.winfo_width())
        h = max(1, canvas.winfo_height())
        return (x0, y0, x0 + w, y0 + h)

    def _load_chunks():
        if Image is None or ImageTk is None:
            return
        want = chunks_for_view(*_view_box())
        for key in want:
            if key in st["chunks"]:
                continue
            fn = earth_prefix + "%d_%d.jpg" % key
            try:
                im = Image.open(fn)
                ph = ImageTk.PhotoImage(im)
            except Exception:
                continue
            iid = canvas.create_image(key[0] * CHUNK, key[1] * CHUNK,
                                      anchor="nw", image=ph)
            canvas.tag_lower(iid)
            st["chunks"][key] = (iid, ph)
        # garder au plus 12 images en mémoire (chacune ~12 Mo)
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
        for lon in range(-180, 181):
            x, _y = latlon_to_pix(0, lon)
            canvas.create_line(x, 0, x, MAP_SIZE, fill="#1e2a24", width=1,
                               tags=("grid",))
        for lat in range(-85, 86):
            _x, y = latlon_to_pix(lat, 0)
            canvas.create_line(0, y, MAP_SIZE, y, fill="#1e2a24", width=1,
                               tags=("grid",))

    def _outlined_rect(lat, lon, color, width):
        """Contour vif + liseré noir dessous (règle §31 : visible sur la
        carte claire comme sombre). Pas de remplissage hachuré : non pris
        en charge par Tk sous macOS. Renvoie la liste des id."""
        box = tile_rect_pix(lat, lon)
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
        if is_grouped(cbd):
            return
        try:
            import O4_File_Names as FNAMES
            ll = FNAMES.long_latlon
        except Exception:
            ll = None
        st["done"] = scan_built_tiles(working_dir(cbd), ll)
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
        n = len(st["sel"])
        if not n:
            sel_var.set(_L("Aucune tuile choisie.", "No tile chosen."))
            return
        names = [short_latlon(*t) for t in sorted_tiles(st["sel"])]
        shown = ", ".join(names[:8]) + (" …" if n > 8 else "")
        sel_var.set(_L("%d tuile(s) : " % n, "%d tile(s): " % n) + shown)

    def _toggle_tile(lat, lon):
        if not valid_tile(lat, lon):
            return
        t = (lat, lon)
        if toggle(st["sel"], t):
            ids = _outlined_rect(lat, lon, COL_SEL, 3)
            # croix fine au centre : la tuile choisie se repère d'un coup d'œil
            x0, y0, x1, y1 = tile_rect_pix(lat, lon)
            ids.append(canvas.create_line(x0 + 4, y0 + 4, x1 - 4, y1 - 4,
                                          fill=COL_SEL, width=2))
            ids.append(canvas.create_line(x0 + 4, y1 - 4, x1 - 4, y0 + 4,
                                          fill=COL_SEL, width=2))
            st["rects"][t] = ids
        else:
            _delete_ids(st["rects"].pop(t, None))
        _refresh_sel_label()

    def _center_on(lat, lon):
        x, y = latlon_to_pix(lat, lon)
        x0, y0, x1, y1 = _view_box()
        w, h = x1 - x0, y1 - y0
        canvas.xview_moveto(max(0.0, (x - w / 2.0) / MAP_SIZE))
        canvas.yview_moveto(max(0.0, (y - h / 2.0) / MAP_SIZE))
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
            lat, lon = pix_to_latlon(canvas.canvasx(e.x), canvas.canvasy(e.y))
            _toggle_tile(*tile_of_point(lat, lon))
        st["press"] = None
        st["panning"] = False

    def _on_hover(e):
        try:
            lat, lon = pix_to_latlon(canvas.canvasx(e.x), canvas.canvasy(e.y))
            t = tile_of_point(lat, lon)
            if valid_tile(*t):
                extra = ""
                if t in st["done"]:
                    extra = _L("  — déjà construite", "  — already built")
                if t in st["sel"]:
                    extra += _L("  — choisie", "  — chosen")
                hover_var.set(_L("Tuile ", "Tile ") + short_latlon(*t) + extra)
        except Exception:
            pass

    canvas.bind("<ButtonPress-1>", _on_press)
    canvas.bind("<B1-Motion>", _on_motion_drag)
    canvas.bind("<ButtonRelease-1>", _on_release)
    canvas.bind("<Motion>", _on_hover)
    canvas.bind("<Configure>", lambda e: _load_chunks())

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
        p = parse_goto(text)
        if p is not None:
            _center_on(*p)
            return
        _search_airport(text)

    goto_entry.bind("<Return>", _goto)
    _btn(goto_f, "→", _goto).pack(side=tk.LEFT)

    def _on_quality():
        st["quality"] = q_var.get()
        q_help.set(quality_help(st["quality"]))

    # ============== 3. Vérification ==============
    def _set_summary(text):
        summary_box.config(state="normal")
        summary_box.delete("1.0", tk.END)
        summary_box.insert("1.0", text)
        summary_box.config(state="disabled")

    def _summary_lines(est_pack):
        tiles = sorted_tiles(st["sel"])
        prov = current_provider()
        q = st["quality"]
        vals = QUALITIES[q]
        lines = []
        lines.append(_L("Tuiles : ", "Tiles: ") + "%d  (%s)" % (
            len(tiles), ", ".join(short_latlon(*t) for t in tiles[:10])
            + (" …" if len(tiles) > 10 else "")))
        lines.append(_L("Qualité : ", "Quality: ") + quality_label(q).strip()
                     + "  (ZL%d)" % vals["default_zl"])
        lines.append(_L("Source d'imagerie : ", "Imagery source: ") + prov
                     + _L("  (choisie dans la fenêtre principale)",
                          "  (chosen in the main window)"))
        wd = working_dir(cbd)
        lines.append(_L("Dossier des tuiles : ", "Tiles folder: ") + wd)
        if not is_in_custom_scenery(wd):
            lines.append(_L(
                "   ℹ Ce dossier n'est pas dans X-Plane : après la "
                "construction, activez les tuiles avec la Bibliothèque de "
                "tuiles.",
                "   ℹ This folder is not inside X-Plane: after the build, "
                "enable the tiles with the Tile library."))
        rebuilt = [short_latlon(*t) for t in tiles if t in st["done"]]
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
                lines.append(_L("Durée estimée : ", "Estimated time: ")
                             + "%s – %s" % (fmt_duration(tmin),
                                             fmt_duration(tmax)))
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
        prov = current_provider()
        box = {}

        def _work():
            try:
                box["est"] = estimate_tiles(tiles, cbd, q, prov)
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
            except Exception:
                pass
            box["probs"] = probs

        th = threading.Thread(target=_work, daemon=True)
        th.start()

        def _poll():
            if th.is_alive():
                win.after(300, _poll)
                return
            lines = _summary_lines(box.get("est"))
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
    def _poll_build():
        r = st["runner"]
        if r is None:
            return
        s = r.state
        n = max(1, s["n"])
        el = time.time() - (s["t0"] or time.time())
        if s["running"]:
            prog_var.set(_L("Tuile %d / %d : %s\nConstruction en cours… "
                            "(%s écoulées)\nLe détail s'affiche dans la "
                            "fenêtre principale."
                            % (s["k"], n, s["current"], fmt_duration(el)),
                            "Tile %d / %d: %s\nBuilding… (%s elapsed)\n"
                            "Details are shown in the main window."
                            % (s["k"], n, s["current"], fmt_duration(el))))
            if pbar is not None:
                try:
                    pbar["value"] = 100.0 * (s["k"] - 1) / n
                except Exception:
                    pass
            win.after(500, _poll_build)
            return
        if pbar is not None:
            try:
                pbar["value"] = 100.0 * len(s["ok"]) / n
            except Exception:
                pass
        msg = s.get("message") or ""
        res = _L("Terminé en %s.\n" % fmt_duration(el),
                 "Finished in %s.\n" % fmt_duration(el))
        res += _L("✅ Réussies : ", "✅ Succeeded: ") + (
            ", ".join(s["ok"]) or "—") + "\n"
        if s["failed"]:
            res += _L("❌ En échec : ", "❌ Failed: ") + ", ".join(s["failed"])
            res += _L("\n→ Ouvrez le Diagnostic pour savoir pourquoi.",
                      "\n→ Open the Diagnostic to find out why.")
        if r.stop_asked:
            res += _L("\n(Construction arrêtée à votre demande.)",
                      "\n(Build stopped at your request.)")
        prog_var.set((msg + "\n" if msg else "") + res)
        st["runner"] = None
        _draw_done()

    def _build():
        if st["runner"] is not None:
            messagebox.showinfo(_L("Construction", "Build"),
                                _L("Une construction est déjà en cours.",
                                   "A build is already running."), parent=win)
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
        r = BuildRunner(tiles, cbd, q, current_provider(),
                        bool(ovl_var.get()) and bool(ovl_src))
        st["runner"] = r
        if not r.start():
            st["runner"] = None
            messagebox.showinfo(_L("Construction", "Build"),
                                r.state.get("message", ""), parent=win)
            return
        win.after(300, _poll_build)

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

    def _on_close():
        if st["runner"] is not None and st["runner"].state.get("running"):
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
    _show_licence_once(tk, win, (BG, FG), _btn, FONT, lambda: None)
    return win


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
