# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# O4_Route_Utils.py
# Choisir des tuiles autour d'un aéroport (novembre 2026).
# Auteur : Roland (Ypsos) - GPLv3
#
# 100 % ADDITIF, sans réseau. Compatible macOS / Windows / Linux
# (bibliothèque standard).
#
#   - tiles_around(lat, lon, rayon_km)    : tuiles touchées par un cercle ;
#   - is_open_sea(lat, lon, racine_xp)    : pas de scène X-Plane 12 = mer ;
#   - run_route_picker(parent, on_tiles)  : fenêtre « autour d'un aéroport ».
# (Le choix le long d'un plan de vol a été retiré à la demande de Roland.)
# ------------------------------------------------------------------------------

import math
import os

EARTH_KM = 6371.0


# ------------------------------------------------------------------------------
# Géométrie (PUR)
# ------------------------------------------------------------------------------
def distance_km(lat1, lon1, lat2, lon2):
    """PUR. Distance orthodromique (haversine) en km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = p2 - p1
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * \
        math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def _valid_tile(lat, lon):
    return -85 <= lat <= 84 and -180 <= lon <= 179


def tile_distance_km(lat, lon, tlat, tlon):
    """PUR. Distance (km) du point au carré 1°×1° (tlat, tlon) : 0 dedans."""
    clat = min(max(lat, tlat), tlat + 1)
    # longitude : point le plus proche dans le carré (gestion simple, sans
    # passage de l'antiméridien pour le point lui-même)
    clon = min(max(lon, tlon), tlon + 1)
    return distance_km(lat, lon, clat, clon)


def tiles_around(lat, lon, radius_km):
    """PUR. Tuiles (lat, lon) touchées par le cercle de rayon radius_km
    autour du point ; rayon 0 = seulement la tuile du point. Triées de la
    plus proche à la plus lointaine."""
    t0 = (int(math.floor(lat)), int(math.floor(lon)))
    if radius_km <= 0:
        return [t0] if _valid_tile(*t0) else []
    dlat = radius_km / 111.0
    cosl = max(0.05, math.cos(math.radians(min(84.0, abs(lat) + dlat))))
    dlon = min(180.0, radius_km / (111.0 * cosl))
    out = []
    for tlat in range(int(math.floor(lat - dlat)), int(math.floor(lat + dlat)) + 1):
        for k in range(int(math.floor(lon - dlon)), int(math.floor(lon + dlon)) + 1):
            tlon = ((k + 180) % 360) - 180
            if not _valid_tile(tlat, tlon):
                continue
            # distance avec la longitude « dépliée » k (antiméridien)
            d = tile_distance_km(lat, lon, tlat, k)
            if d <= radius_km and (tlat, tlon) not in out:
                out.append((tlat, tlon))
    out.sort(key=lambda t: (tile_distance_km(lat, lon, t[0], t[1]), t))
    if t0 in out:
        out.remove(t0)
        out.insert(0, t0)
    return out


# ------------------------------------------------------------------------------
# Pleine mer : pas de scène X-Plane 12 pour ce carré
# ------------------------------------------------------------------------------
def xplane_root():
    try:
        import O4_XP12_Relief_Utils as XR
        return XR.find_xplane_root() or ""
    except Exception:
        return ""


def is_open_sea(lat, lon, root):
    """Vrai seulement si X-Plane 12 est trouvé ET n'a aucune scène (DSF)
    pour ce carré. X-Plane introuvable -> jamais « mer » (rien n'est
    laissé de côté par erreur)."""
    if not root:
        return False
    try:
        import O4_XP12_Relief_Utils as XR
        earth = os.path.join(root, "Global Scenery",
                             "X-Plane 12 Global Scenery", "Earth nav data")
        if not os.path.isdir(earth):
            return False
        return not os.path.isfile(XR.global_dsf_path(root, lat, lon))
    except Exception:
        return False


# ------------------------------------------------------------------------------
# Bilingue interne (ne touche pas aux fichiers O4_Lang_*)
# ------------------------------------------------------------------------------
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


def short_latlon(lat, lon):
    return "%+03d%+04d" % (lat, lon)


RADII = (0, 20, 50, 100)


def radius_label(r):
    return _L("sa tuile seulement", "its tile only") if r == 0 else "%d km" % r


# ------------------------------------------------------------------------------
# Fenêtre « Choisir des tuiles autour d'un aéroport »
# Point d'entrée : run_route_picker(parent, on_tiles)
#   on_tiles(liste de (lat, lon)) est appelé quand l'utilisateur valide.
# Même fenêtre pour le mode simple et pour le mode expert (fenêtre des
# tuiles). Couleurs : thème de Roland (O4_Theme_Manager).
# ------------------------------------------------------------------------------
_OPEN = {"win": None}


def run_route_picker(parent=None, on_tiles=None):
    import threading
    import tkinter as tk
    from tkinter import messagebox
    try:
        from tkinter import ttk
    except Exception:
        ttk = None

    try:
        w0 = _OPEN.get("win")
        if w0 is not None and w0.winfo_exists():
            w0._route_on_tiles = on_tiles
            w0.deiconify()
            w0.lift()
            return w0
    except Exception:
        pass

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
    LIST_BG = _c("canvas_bg", BG)
    SEL_BG = _c("btn_active", HOVER)
    FONT = ("Helvetica", 12) if ("dar" in __import__("sys").platform) \
        else ("Segoe UI", 10)
    FONT_S = (FONT[0], FONT[1] - 1)
    FONT_B = (FONT[0], FONT[1], "bold")

    root_ref = parent
    if root_ref is None:
        try:
            root_ref = tk._default_root
        except Exception:
            root_ref = None
    win = tk.Toplevel(root_ref) if root_ref else tk.Tk()
    _OPEN["win"] = win
    win._route_on_tiles = on_tiles
    win.title(_L("Tuiles autour d'un aéroport - Ortho4XP V4",
                 "Tiles around an airport - Ortho4XP V4"))
    win.configure(bg=BG)
    if _TM is not None:
        try:
            _TM.apply_to_root(win)
        except Exception:
            pass
    try:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry("%dx%d" % (min(560, int(sw * 0.95)),
                                min(620, int(sh * 0.9))))
    except Exception:
        pass
    win.lift()

    try:
        import customtkinter as _ctk
        _HAS_CTK = True
    except Exception:
        _HAS_CTK = False

    def _btn(parent_w, text, cmd):
        if _HAS_CTK:
            b = _ctk.CTkButton(parent_w, text=text, command=cmd,
                               corner_radius=8, border_width=1, height=32,
                               fg_color=BTN_BG, hover_color=HOVER,
                               border_color=BORDER, text_color=BTN_FG)
            b.after_idle(lambda w=b, c=BTN_BG:
                         w.winfo_exists() and w.configure(fg_color=c))
            return b
        frame = tk.Frame(parent_w, bg=BTN_BG, highlightthickness=1,
                         highlightbackground=BORDER, bd=0)
        lbl = tk.Label(frame, text=text, bg=BTN_BG, fg=BTN_FG, padx=10,
                       pady=6, font=FONT, cursor="hand2")
        lbl.pack(fill="both", expand=True)
        lbl.bind("<ButtonRelease-1>", lambda e=None: cmd())
        return frame

    def _title(text):
        tk.Label(win, text=text, bg=BG, fg=FG2, font=FONT_B,
                 anchor="w").pack(fill=tk.X, padx=10, pady=(10, 2))

    st = {"tiles": [], "index": None, "loading": False, "results": [],
          "what": ""}
    root_xp = xplane_root()

    # --- Rayon ---
    _title(_L("Rayon autour de l'aéroport", "Radius around the airport"))
    rad_f = tk.Frame(win, bg=BG)
    rad_f.pack(fill=tk.X, padx=10)
    rad_var = tk.StringVar(value=radius_label(20))
    rad_vals = [radius_label(r) for r in RADII]
    if ttk is not None:
        try:
            cb = ttk.Combobox(rad_f, textvariable=rad_var, values=rad_vals,
                              state="readonly", width=20)
            cb.pack(side=tk.LEFT)
            cb.bind("<<ComboboxSelected>>", lambda e: _recompute())
        except Exception:
            pass
    sea_var = tk.BooleanVar(value=bool(root_xp))
    tk.Checkbutton(win, text=_L("Laisser de côté la pleine mer (carrés sans "
                                "scène X-Plane 12)",
                                "Leave out open sea (squares with no X-Plane "
                                "12 scenery)"),
                   variable=sea_var, bg=BG, fg=FG, selectcolor=BG,
                   activebackground=BG, activeforeground=FG,
                   highlightthickness=0, font=FONT_S, anchor="w",
                   command=lambda: _recompute(),
                   state=("normal" if root_xp else "disabled")).pack(
        fill=tk.X, padx=10)

    def _radius():
        v = rad_var.get()
        for r in RADII:
            if radius_label(r) == v:
                return r
        return 20

    # --- Aéroport ---
    _title(_L("✈ Autour d'un aéroport", "✈ Around an airport"))
    a_f = tk.Frame(win, bg=BG)
    a_f.pack(fill=tk.X, padx=10)
    a_var = tk.StringVar(value="")
    a_entry = tk.Entry(a_f, textvariable=a_var, width=24, font=FONT)
    a_entry.pack(side=tk.LEFT, padx=(0, 6))
    _btn(a_f, _L("Chercher", "Search"), lambda: _search()).pack(side=tk.LEFT)
    a_entry.bind("<Return>", lambda e=None: _search())
    res_lb = tk.Listbox(win, height=5, bg=LIST_BG, fg=FG,
                        selectbackground=SEL_BG, selectforeground=BTN_FG,
                        highlightthickness=0, font=FONT_S, exportselection=False)
    res_lb.pack(fill=tk.X, padx=10, pady=(4, 0))
    res_lb.bind("<<ListboxSelect>>", lambda e=None: _pick())

    # --- Résultat ---
    _title(_L("Résultat", "Result"))
    out_var = tk.StringVar(value=_L("Cherchez un aéroport, puis cliquez-le.",
                                    "Search an airport, then click it."))
    tk.Label(win, textvariable=out_var, bg=BG, fg=FG, font=FONT_S,
             justify="left", anchor="w", wraplength=520).pack(
        fill=tk.X, padx=10)
    end_f = tk.Frame(win, bg=BG)
    end_f.pack(fill=tk.X, padx=10, pady=10)
    _btn(end_f, _L("✅ Ajouter ces tuiles à la sélection",
                   "✅ Add these tiles to the selection"),
         lambda: _add()).pack(fill=tk.X)

    # Aéroport choisi : recalculé si le rayon change.
    src = {"kind": None, "points": [], "label": ""}

    def _skip():
        if sea_var.get() and root_xp:
            return lambda la, lo: is_open_sea(la, lo, root_xp)
        return None

    def _recompute():
        if not src["points"]:
            return
        r = _radius()
        la, lo = src["points"][0]
        tiles = tiles_around(la, lo, r)
        sk = _skip()
        left = 0
        if sk is not None:
            keep = [t for t in tiles if not sk(*t)]
            left = len(tiles) - len(keep)
            tiles = keep
        st["tiles"] = tiles
        txt = src["label"] + "\n" + _L("%d tuile(s) : ", "%d tile(s): ") \
            % len(tiles) + ", ".join(short_latlon(*t) for t in tiles[:14]) \
            + (" …" if len(tiles) > 14 else "")
        if left:
            txt += "\n" + _L("%d carré(s) laissé(s) de côté : pleine mer ou "
                             "région X-Plane non installée.",
                             "%d square(s) left out: open sea or X-Plane "
                             "region not installed.") % left
        out_var.set(txt)

    def _show_results(items):
        st["results"] = items
        res_lb.delete(0, tk.END)
        try:
            import O4_Airport_Search_Utils as AS
            for a in items:
                res_lb.insert(tk.END, AS.label(a))
        except Exception:
            pass
        if not items:
            out_var.set(_L("Aucun aéroport trouvé.", "No airport found."))

    def _search():
        q = a_var.get().strip()
        if not q:
            return
        if st["index"] is not None:
            try:
                import O4_Airport_Search_Utils as AS
                _show_results(AS.search(q, st["index"], limit=12))
            except Exception:
                _show_results([])
            return
        if st["loading"]:
            return
        st["loading"] = True
        out_var.set(_L("Préparation de la liste des aéroports de X-Plane "
                       "(une seule fois, quelques secondes)…",
                       "Preparing X-Plane's airport list (once only, a few "
                       "seconds)…"))
        box = {}

        def _work():
            try:
                import O4_Airport_Search_Utils as AS
                box["idx"] = AS.load_or_build_index()
            except Exception:
                box["idx"] = []

        th = threading.Thread(target=_work, daemon=True)
        th.start()

        def _poll():
            if th.is_alive():
                win.after(250, _poll)
                return
            st["loading"] = False
            st["index"] = box.get("idx") or []
            if not st["index"]:
                out_var.set(_L("Liste des aéroports introuvable : indiquez "
                               "votre X-Plane (Bibliothèque de tuiles).",
                               "Airport list not found: set your X-Plane "
                               "(Tile library)."))
                return
            _search()

        win.after(250, _poll)

    def _pick():
        sel = res_lb.curselection()
        if not sel:
            return
        a = st["results"][sel[0]]
        try:
            import O4_Airport_Search_Utils as AS
            lab = AS.label(a).strip()
        except Exception:
            lab = str(a.get("icao") or a.get("id") or "")
        src.update({"kind": "airport", "points": [(a["lat"], a["lon"])],
                    "label": lab})
        _recompute()

    def _add():
        if not st["tiles"]:
            messagebox.showinfo(
                _L("Tuiles", "Tiles"),
                _L("Choisissez d'abord un aéroport.",
                   "First choose an airport."), parent=win)
            return
        cb_ = getattr(win, "_route_on_tiles", None)
        if callable(cb_):
            try:
                cb_(list(st["tiles"]))
            except Exception:
                pass
        out_var.set(out_var.get() + "\n" + _L("→ Ajoutées à la sélection.",
                                              "→ Added to the selection."))

    def _on_close():
        _OPEN["win"] = None
        try:
            win.destroy()
        except Exception:
            pass

    try:
        win.protocol("WM_DELETE_WINDOW", _on_close)
    except Exception:
        pass
    return win
