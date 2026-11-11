# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# O4_Cleanup_Utils.py
# Grand nettoyage des fichiers de travail d'Ortho4XP (novembre 2026).
# Auteur : Roland (Ypsos) - GPLv3
#
# Une seule fenêtre, bilingue (_L interne), 100 % ADDITIF. Point d'entrée :
# run_cleanup(parent). Ouverte depuis le mode simple (bouton « 🧹 Grand
# nettoyage ») et depuis la barre de menus (Outils), donc en mode simple comme
# en mode expert. Compatible macOS / Windows / Linux (os / shutil seulement).
#
# Ce que la fenêtre montre, tuile par tuile, avec la place prise :
#   - Images téléchargées : JPG source dans Orthophotos/ (jamais JPG-Patch) ;
#   - Données OSM        : fichiers .osm / .osm.bz2 / .pbf de OSM_data/<groupe>/<tuile>/ ;
#   - Masques d'eau      : fichiers .png de Masks/<groupe>/<tuile>/ ;
#   - Bords de mer       : JPG de Patches/<tuile>/PATCH_<zl>/ (refaits au build) ;
#   - Aperçus            : Previews/<tuile>_*.jpg ;
#   - Relief téléchargé  : Elevation_data/<groupe>/N46W003*.hgt / _COP30.tif…
#     (seulement les fichiers que le moteur télécharge lui-même ; jamais un
#     .tif « simple » posé par l'utilisateur ; case NON cochée d'office).
#
# Ce qui n'est JAMAIS touché :
#   - la tuile construite elle-même (Tiles/zOrtho4XP_…, ses DDS, son DSF) :
#     elle reste utilisable dans X-Plane après le nettoyage ;
#   - le relief (Elevation_data, Altimétrie, Bathymétrie), les Providers,
#     Extents, Filters, la configuration ;
#   - tout sous-dossier ou fichier d'un autre type dans ces dossiers
#     (custom_coastline, custom_water, sauvegardes, patches de piste .patch,
#     fichiers .osm faits à la main dans Patches/…) : seuls les fichiers
#     listés ci-dessus, par leur extension, sont effacés ;
#   - rien n'est effacé sans la confirmation de l'utilisateur, et rien
#     pendant une construction.
#
# Conséquence (dite à l'utilisateur) : refaire une tuile nettoyée sera plus
# long (téléchargement des images et des données OSM à nouveau).
# ------------------------------------------------------------------------------

import math
import os
import re
import threading

CATS = ("jpg", "osm", "masks", "patches", "previews", "relief")
CATS_DEFAULT_OFF = ("relief",)
# Relief téléchargé par le moteur : <N|S>lat<E|W>lon + suffixe connu.
_RELIEF_RE = re.compile(r"^([NS])(\d\d)([EW])(\d\d\d)"
                        r"(\.hgt|_SRTMv3\.hgt|_XP12\.hgt|_COP30\.tif|"
                        r"_ALOS3W30\.tif|_NED13\.tif|_NED1\.tif|"
                        r"_CA_MRDEM\.tif|_ANADEM\.tif)$")
_TILE_RE = re.compile(r"^[+-]\d\d[+-]\d\d\d$")
_JPG_RE = re.compile(r"^(\d+)_(\d+)_.+?(\d\d)\.jpg$", re.IGNORECASE)
_OSM_EXT = (".osm", ".osm.bz2", ".pbf")


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


def cat_label(cat):
    return {"jpg": _L("Images téléchargées", "Downloaded images"),
            "osm": _L("Données OSM", "OSM data"),
            "masks": _L("Masques d'eau", "Water masks"),
            "patches": _L("Bords de mer", "Coastline patches"),
            "previews": _L("Aperçus", "Previews"),
            "relief": _L("Relief téléchargé", "Downloaded relief")}.get(cat,
                                                                     cat)


# ------------------------------------------------------------------------------
# Cœur PUR (testable en headless)
# ------------------------------------------------------------------------------
def short_latlon(lat, lon):
    return "%+03d%+04d" % (lat, lon)


def parse_tile(name):
    """PUR. « +48-005 » -> (48, -5) ; None si ce n'est pas un nom de tuile."""
    if not _TILE_RE.match(name or ""):
        return None
    return (int(name[:3]), int(name[3:]))


def texture_center(til_y, til_x, zl):
    """PUR. Centre (lat, lon) d'une texture (16 × 16 dalles, convention
    Ortho4XP) : même calcul que O4_Build_Comfort_Utils._texture_center."""
    n = 2.0 ** zl
    x = til_x + 8
    y = til_y + 8
    lon = x / n * 360.0 - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lat, lon


def tile_of_relief(fname):
    """PUR. Tuile d'un fichier de relief téléchargé (N46W003.hgt,
    N42E008_COP30.tif…), ou None (fichier de l'utilisateur, autre nom)."""
    m = _RELIEF_RE.match(fname)
    if not m:
        return None
    lat = int(m.group(2)) * (1 if m.group(1) == "N" else -1)
    lon = int(m.group(4)) * (1 if m.group(3) == "E" else -1)
    return (lat, lon)


def tile_of_jpg(rel_parts, fname):
    """PUR. Tuile d'un JPG source d'après son chemin relatif à Orthophotos
    (liste des dossiers) et son nom. Même règle que BC.tile_jpgs :
      - Orthophotos/<tuile>/… ou Orthophotos/<groupe>/<tuile>/… : cette tuile ;
      - dossier partagé par source : tuile qui contient le centre de l'image.
    None si ce n'est pas un JPG source."""
    m = _JPG_RE.match(fname)
    if not m:
        return None
    if "JPG-Patch" in rel_parts:
        return None
    if rel_parts and parse_tile(rel_parts[0]):
        if len(rel_parts) >= 2 and parse_tile(rel_parts[1]):
            return parse_tile(rel_parts[1])
        return parse_tile(rel_parts[0])
    if any(parse_tile(p) for p in rel_parts):
        return None          # comme BC.tile_jpgs : sous-dossier « tuile » ignoré
    clat, clon = texture_center(int(m.group(1)), int(m.group(2)),
                                int(m.group(3)))
    return (int(math.floor(clat)), int(math.floor(clon)))


def _add(index, tile, cat, path, size):
    d = index.setdefault(tile, {c: [[], 0] for c in CATS})
    d[cat][0].append(path)
    d[cat][1] += size


def _size(p):
    try:
        return os.path.getsize(p)
    except Exception:
        return 0


def scan(dirs, stop=None):
    """Inventaire. dirs = {"imagery", "osm", "masks", "patches", "previews"}
    (chemins absolus). Renvoie {(lat, lon): {cat: [liste_fichiers, octets]}}.
    Lecture seule. stop() vrai -> arrêt anticipé."""
    index = {}
    stop = stop or (lambda: False)
    # 1. Images téléchargées
    img = dirs.get("imagery") or ""
    if os.path.isdir(img):
        for root, sub, files in os.walk(img):
            if stop():
                return index
            sub[:] = [s for s in sub if s != "JPG-Patch"]
            rel = os.path.relpath(root, img)
            parts = [] if rel == "." else rel.split(os.sep)
            for f in files:
                t = tile_of_jpg(parts, f)
                if t is not None:
                    p = os.path.join(root, f)
                    _add(index, t, "jpg", p, _size(p))
    # 2. OSM / 3. Masques : <dossier>/<groupe>/<tuile>/ (fichiers directs)
    for cat, key, ok in (("osm", "osm", lambda f: f.lower().endswith(_OSM_EXT)),
                         ("masks", "masks", lambda f: f.lower().endswith(".png"))):
        base = dirs.get(key) or ""
        try:
            groups = sorted(os.listdir(base))
        except Exception:
            groups = []
        for g in groups:
            if not parse_tile(g):
                continue
            gdir = os.path.join(base, g)
            try:
                names = sorted(os.listdir(gdir))
            except Exception:
                continue
            for n in names:
                t = parse_tile(n)
                tdir = os.path.join(gdir, n)
                if t is None or not os.path.isdir(tdir):
                    continue
                for f in sorted(os.listdir(tdir)):
                    p = os.path.join(tdir, f)
                    if os.path.isfile(p) and not os.path.islink(p) and ok(f):
                        _add(index, t, cat, p, _size(p))
    # 4. Bords de mer : Patches/<tuile>/PATCH_<zl>/*.jpg
    base = dirs.get("patches") or ""
    try:
        names = sorted(os.listdir(base))
    except Exception:
        names = []
    for n in names:
        t = parse_tile(n)
        tdir = os.path.join(base, n)
        if t is None or not os.path.isdir(tdir):
            continue
        for sub in sorted(os.listdir(tdir)):
            sdir = os.path.join(tdir, sub)
            if not (sub.startswith("PATCH_") and os.path.isdir(sdir)
                    and not os.path.islink(sdir)):
                continue
            for f in sorted(os.listdir(sdir)):
                p = os.path.join(sdir, f)
                if os.path.isfile(p) and f.lower().endswith(".jpg"):
                    _add(index, t, "patches", p, _size(p))
    # 6. Relief téléchargé : Elevation_data/<groupe>/<N46W003…>
    base = dirs.get("relief") or ""
    try:
        groups = sorted(os.listdir(base))
    except Exception:
        groups = []
    for g in groups:
        gdir = os.path.join(base, g)
        if not parse_tile(g) or not os.path.isdir(gdir):
            continue
        for f in sorted(os.listdir(gdir)):
            t = tile_of_relief(f)
            p = os.path.join(gdir, f)
            if t and os.path.isfile(p) and not os.path.islink(p):
                _add(index, t, "relief", p, _size(p))
    # 5. Aperçus : Previews/<tuile>_*.jpg
    base = dirs.get("previews") or ""
    try:
        names = sorted(os.listdir(base))
    except Exception:
        names = []
    for f in names:
        t = parse_tile(f[:7])
        p = os.path.join(base, f)
        if t and f[7:8] == "_" and f.lower().endswith(".jpg") and \
                os.path.isfile(p):
            _add(index, t, "previews", p, _size(p))
    return index


def tile_total(entry, cats):
    """PUR. Octets d'une tuile pour les catégories choisies."""
    return sum(entry[c][1] for c in cats if c in entry)


def files_for(index, tiles, cats):
    """PUR. Fichiers à effacer pour les tuiles et catégories choisies."""
    out = []
    for t in tiles:
        e = index.get(t)
        if not e:
            continue
        for c in cats:
            out.extend(e.get(c, [[], 0])[0])
    return out


def fmt_size(b):
    """PUR. Taille lisible (Go / Mo / Ko)."""
    b = float(b or 0)
    if b >= 1024 ** 3:
        return ("%.1f Go" if _lang_code() == "fr" else "%.1f GB") % (b / 1024 ** 3)
    if b >= 1024 ** 2:
        return ("%.0f Mo" if _lang_code() == "fr" else "%.0f MB") % (b / 1024 ** 2)
    if b > 0:
        return ("%.0f Ko" if _lang_code() == "fr" else "%.0f KB") % max(1, b / 1024)
    return "0"


def _allowed(path, dirs):
    """Sécurité : un fichier n'est effacé que s'il est un fichier ordinaire,
    d'un type prévu, et situé sous l'un des dossiers inventoriés."""
    if not path or os.path.islink(path) or not os.path.isfile(path):
        return False
    low = path.lower()
    if not (low.endswith(".jpg") or low.endswith(".png")
            or low.endswith(_OSM_EXT) or
            tile_of_relief(os.path.basename(path)) is not None):
        return False
    rp = os.path.realpath(path)
    for d in dirs.values():
        if d:
            rd = os.path.realpath(d)
            if rp.startswith(rd.rstrip(os.sep) + os.sep):
                return True
    return False


def delete(paths, dirs, remover=os.remove, busy=None):
    """Efface les fichiers confirmés. Refuse tout pendant une construction.
    Renvoie (nb_effacés, octets_libérés, message)."""
    if busy is None:
        busy = is_busy
    if busy():
        return (0, 0, _L("Une construction est en cours : nettoyage refusé.",
                         "A build is running: cleanup refused."))
    n, freed = 0, 0
    for p in paths:
        if not _allowed(p, dirs):
            continue
        s = _size(p)
        try:
            remover(p)
            n += 1
            freed += s
        except Exception:
            pass
    return (n, freed, "")


def is_busy():
    try:
        import O4_UI_Utils as UI
        return bool(getattr(UI, "is_working", False))
    except Exception:
        return False


def default_dirs():
    """Dossiers d'Ortho4XP (via O4_File_Names, aucun chemin en dur)."""
    try:
        import O4_File_Names as FN
        return {"imagery": FN.Imagery_dir, "osm": FN.OSM_dir,
                "masks": FN.Mask_dir, "patches": FN.Patch_dir,
                "previews": FN.Preview_dir, "relief": FN.Elevation_dir}
    except Exception:
        return {}


# ------------------------------------------------------------------------------
# Fenêtre. Point d'entrée : run_cleanup(parent)
# ------------------------------------------------------------------------------
_OPEN = {"win": None}


def run_cleanup(parent=None, dirs=None):
    import tkinter as tk
    from tkinter import messagebox

    try:
        w0 = _OPEN.get("win")
        if w0 is not None and w0.winfo_exists():
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
    BTN_BG = _c("btn_bg", "#4a6b59")
    BTN_FG = _c("btn_fg", "#ffffff")
    HOVER = _c("accent", "#5a7b69")
    BORDER = _c("border", BTN_BG)
    FONT = ("Helvetica", 12) if ("dar" in __import__("sys").platform) \
        else ("Segoe UI", 10)
    FONT_S = (FONT[0], FONT[1] - 1)

    dirs = dirs if dirs is not None else default_dirs()
    st = {"index": {}, "tile_vars": {}, "scanning": False, "stop": False}

    root_ref = parent
    if root_ref is None:
        try:
            root_ref = tk._default_root
        except Exception:
            root_ref = None
    win = tk.Toplevel(root_ref) if root_ref else tk.Tk()
    _OPEN["win"] = win
    win.title(_L("Grand nettoyage - Ortho4XP V4", "Big cleanup - Ortho4XP V4"))
    win.configure(bg=BG)
    if _TM is not None:
        try:
            _TM.apply_to_root(win)
        except Exception:
            pass
    try:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        w_, h_ = min(760, int(sw * 0.95)), min(640, int(sh * 0.9))
        win.geometry("%dx%d" % (w_, h_))
        win.minsize(min(520, w_), min(420, h_))
    except Exception:
        pass
    win.lift()
    try:
        win.focus_force()
    except Exception:
        pass

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

    def _cb(parent_w, text, var, cmd=None):
        return tk.Checkbutton(parent_w, text=text, variable=var, bg=BG,
                              fg=FG, selectcolor=BG, activebackground=BG,
                              activeforeground=FG, highlightthickness=0,
                              font=FONT_S, anchor="w",
                              command=(cmd or (lambda: _update_total())))

    tk.Label(win, text=_L(
        "Libérez de la place : cochez les tuiles et ce que vous voulez "
        "effacer. Les tuiles déjà construites restent utilisables dans "
        "X-Plane. Refaire une tuile nettoyée sera plus long (téléchargement "
        "à nouveau).",
        "Free up space: tick the tiles and what you want to delete. Tiles "
        "already built stay usable in X-Plane. Rebuilding a cleaned tile "
        "will take longer (downloaded again)."),
        bg=BG, fg=FG, font=FONT, justify="left", anchor="w",
        wraplength=700).pack(fill=tk.X, padx=10, pady=(10, 4))

    cat_f = tk.Frame(win, bg=BG)
    cat_f.pack(fill=tk.X, padx=10)
    cat_vars = {}
    for i, c in enumerate(CATS):
        cat_vars[c] = tk.BooleanVar(value=c not in CATS_DEFAULT_OFF)
        _cb(cat_f, cat_label(c), cat_vars[c],
            lambda: _refresh_rows()).grid(row=i // 3, column=i % 3,
                                          sticky="w", padx=(0, 12))

    # Liste défilante des tuiles
    list_f = tk.Frame(win, bg=BG)
    list_f.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
    canvas = tk.Canvas(list_f, bg=BG, highlightthickness=0)
    sb = tk.Scrollbar(list_f, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    rows = tk.Frame(canvas, bg=BG)
    canvas.create_window((0, 0), window=rows, anchor="nw")
    rows.bind("<Configure>",
              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

    def _wheel(e):
        try:
            d = e.delta
            step = -1 if d > 0 else 1
            if abs(d) >= 120:
                step = int(-d / 120)
            canvas.yview_scroll(step, "units")
        except Exception:
            pass
    canvas.bind("<MouseWheel>", _wheel)
    rows.bind("<MouseWheel>", _wheel)

    total_var = tk.StringVar(value=_L("Inventaire en cours…",
                                      "Taking inventory…"))
    tk.Label(win, textvariable=total_var, bg=BG, fg=FG, font=FONT,
             justify="left", anchor="w", wraplength=700).pack(
        fill=tk.X, padx=10)

    btn_f = tk.Frame(win, bg=BG)
    btn_f.pack(fill=tk.X, padx=10, pady=(4, 10))

    def _cats():
        return [c for c in CATS if cat_vars[c].get()]

    def _chosen():
        return [t for t, v in st["tile_vars"].items() if v.get()]

    def _update_total():
        if st["scanning"]:
            return
        cats = _cats()
        tot = sum(tile_total(st["index"][t], cats) for t in _chosen()
                  if t in st["index"])
        alltot = sum(tile_total(e, CATS) for e in st["index"].values())
        total_var.set(_L("Sélection : %s à libérer  (tout Ortho4XP : %s)",
                         "Selection: %s to free  (all Ortho4XP: %s)")
                      % (fmt_size(tot), fmt_size(alltot)))

    def _refresh_rows():
        for ch in list(rows.winfo_children()):
            try:
                ch.destroy()
            except Exception:
                pass
        old = {t: v.get() for t, v in st["tile_vars"].items()}
        st["tile_vars"] = {}
        cats = _cats()
        tiles = sorted(st["index"], key=lambda t: (-t[0], t[1]))
        if not tiles:
            tk.Label(rows, text=_L("Rien à nettoyer.", "Nothing to clean."),
                     bg=BG, fg=FG, font=FONT).pack(anchor="w")
        for t in tiles:
            e = st["index"][t]
            if tile_total(e, CATS) <= 0:
                continue
            v = tk.BooleanVar(value=old.get(t, False))
            st["tile_vars"][t] = v
            parts = ["%s %s" % (cat_label(c), fmt_size(e[c][1]))
                     for c in cats if e[c][1] > 0]
            txt = "%s   %s   →  %s" % (
                short_latlon(*t), fmt_size(tile_total(e, cats)),
                " · ".join(parts) or "—")
            w_ = _cb(rows, txt, v)
            w_.pack(fill=tk.X, anchor="w")
            w_.bind("<MouseWheel>", _wheel)
        _update_total()

    def _set_all(val):
        for v in st["tile_vars"].values():
            v.set(val)
        _update_total()

    def _scan():
        if st["scanning"]:
            return
        st["scanning"] = True
        total_var.set(_L("Inventaire en cours… (quelques secondes)",
                         "Taking inventory… (a few seconds)"))
        box = {}

        def _work():
            try:
                box["index"] = scan(dirs, stop=lambda: st["stop"])
            except Exception as e:
                box["err"] = str(e)
                box["index"] = {}

        th = threading.Thread(target=_work, daemon=True)
        th.start()

        def _poll():
            if th.is_alive():
                try:
                    win.after(200, _poll)
                except Exception:
                    pass
                return
            st["scanning"] = False
            st["index"] = box.get("index", {})
            _refresh_rows()

        win.after(200, _poll)

    def _clean():
        tiles, cats = _chosen(), _cats()
        paths = files_for(st["index"], tiles, cats)
        if not tiles or not cats or not paths:
            messagebox.showinfo(_L("Grand nettoyage", "Big cleanup"),
                                _L("Cochez au moins une tuile et un type de "
                                   "fichiers.",
                                   "Tick at least one tile and one file "
                                   "type."), parent=win)
            return
        if is_busy():
            messagebox.showwarning(
                _L("Grand nettoyage", "Big cleanup"),
                _L("Une construction est en cours : attendez la fin pour "
                   "nettoyer.", "A build is running: wait for the end "
                   "before cleaning."), parent=win)
            return
        tot = sum(tile_total(st["index"][t], cats) for t in tiles)
        names = ", ".join(short_latlon(*t) for t in sorted(tiles)[:12]) + (
            " …" if len(tiles) > 12 else "")
        if not messagebox.askyesno(
                _L("Grand nettoyage", "Big cleanup"),
                _L("Effacer %d fichiers (%s) ?\n\nTuiles : %s\nTypes : %s\n\n"
                   "Les tuiles construites restent utilisables dans X-Plane. "
                   "Les refaire sera plus long.",
                   "Delete %d files (%s)?\n\nTiles: %s\nTypes: %s\n\n"
                   "Built tiles stay usable in X-Plane. Rebuilding them will "
                   "take longer.")
                % (len(paths), fmt_size(tot), names,
                   ", ".join(cat_label(c) for c in cats)),
                default="no", parent=win):
            return
        n, freed, msg = delete(paths, dirs)
        if msg:
            messagebox.showwarning(_L("Grand nettoyage", "Big cleanup"), msg,
                                   parent=win)
            return
        try:
            import O4_UI_Utils as UI
            UI.logprint("Grand nettoyage / Big cleanup:", n, "files,",
                        freed, "bytes,", names)
        except Exception:
            pass
        messagebox.showinfo(_L("Grand nettoyage", "Big cleanup"),
                            _L("%d fichiers effacés, %s libérés.",
                               "%d files deleted, %s freed.")
                            % (n, fmt_size(freed)), parent=win)
        _scan()

    for i, (txt, cmd) in enumerate((
            (_L("Tout cocher", "Tick all"), lambda: _set_all(True)),
            (_L("Tout décocher", "Untick all"), lambda: _set_all(False)),
            (_L("↻ Recompter", "↻ Recount"), _scan),
            (_L("🧹 Nettoyer la sélection", "🧹 Clean the selection"),
             _clean))):
        _btn(btn_f, txt, cmd).grid(row=0, column=i, sticky="ew", padx=2)
        btn_f.columnconfigure(i, weight=1)

    def _on_close():
        st["stop"] = True
        _OPEN["win"] = None
        try:
            win.destroy()
        except Exception:
            pass

    try:
        win.protocol("WM_DELETE_WINDOW", _on_close)
    except Exception:
        pass
    _scan()
    return win
