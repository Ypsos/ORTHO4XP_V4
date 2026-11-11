# -*- coding: utf-8 -*-
# ------------------------------------------------------------------------------
# O4_Cloud_Utils.py
# Nuages sur les images d'une tuile : repérage, puis remplacement par la même
# zone prise chez une autre source (novembre 2026).
# Auteur : Roland (Ypsos) - GPLv3
#
# 100 % ADDITIF. Point d'entrée : run_cloud_window(parent, tile=None).
# Ouvert depuis le mode simple et depuis la barre de menus (Outils), donc en
# mode simple comme en mode expert. macOS / Windows / Linux (numpy + Pillow,
# déjà requis par Ortho4XP ; aucun modèle à télécharger).
#
# Repérage (sur une image réduite à 512 px, rapide) : un nuage est clair
# (luminosité haute), presque sans couleur (saturation basse), flou (peu de
# détail) et surtout à BORDS FONDUS. L'image est découpée en carrés de
# 16 × 16 px ; un carré est « nuage » si la plupart de ses pixels le sont.
# Écartés : les petits ensembles (bateau), les ensembles à bord net (toits
# d'entrepôts, bâches, serres : vérifié sur de vraies images Esri d'Alsace),
# le blanc pur et les aplats parfaitement unis (zones sans donnée du
# fournisseur, que le pipeline mer traite déjà). RIEN n'est changé à ce stade :
# l'utilisateur voit chaque image, coche celles à corriger et choisit la
# source de remplacement.
#
# Remplacement (images cochées seulement) :
#   1. l'image de la même zone est téléchargée chez l'autre source par la
#      fonction du moteur IMG.download_jpeg_ortho, dans un dossier temporaire ;
#   2. ses couleurs sont ajustées à celles de l'image d'origine (autour du
#      nuage), puis seule la zone du nuage est remplacée, bords fondus ;
#   3. l'image d'origine est gardée à côté (<nom>.jpg.o4x_cloud_orig) :
#      « Remettre les photos d'origine » la restaure à tout moment ;
#   4. le DDS de cette image est effacé ; l'étape 3 de la tuile le refait
#      (proposée tout de suite, même fonction que la réparation des images
#      blanches).
# Jamais pendant une construction. Les ombres des nuages ne sont pas traitées.
# ------------------------------------------------------------------------------

import os
import re
import shutil
import tempfile
import threading

BACKUP_SUFFIX = ".o4x_cloud_orig"
SCAN_SIZE = 512
BLOCK = 16
V_MIN = 200          # luminosité (0-255) au moins
S_MAX = 45           # saturation (0-255) au plus
GRAD_MAX = 10.0      # détail moyen (pente de luminosité) au plus
BLOCK_FILL = 0.6     # part de pixels « nuage » pour qu'un carré le soit
MIN_BLOCKS = 4       # ensemble de carrés plus petit = ignoré
EDGE_MIN = 2.5       # largeur de bord (px à 512) : moins = bord net = objet
EDGE_LO = 165        # niveau bas de la rampe de bord
BLUE_MIN = -6        # bleu - rouge : un nuage est neutre ou bleuté, un toit
                     # clair est souvent beige (bleu nettement sous le rouge)
WHITE_MIN = 250      # blanc pur = zone sans donnée du fournisseur, pas nuage
FLAT_MIN = 0.05      # teinte parfaitement unie = remplissage, pas nuage
REPORT_MIN = 0.02    # image signalée à partir de 2 % de nuages
TICK_MIN = 0.05      # cochée d'office à partir de 5 %
_JPG_RE = re.compile(r"^(\d+)_(\d+)_(.+?)(\d\d)\.jpg$", re.IGNORECASE)


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


# ------------------------------------------------------------------------------
# Cœur PUR (numpy / Pillow, testable en headless)
# ------------------------------------------------------------------------------
def parse_jpg_name(name):
    """PUR. « 45376_63824_BI17.jpg » -> (til_y, til_x, "BI", 17) ou None."""
    m = _JPG_RE.match(os.path.basename(name))
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2)), m.group(3), int(m.group(4)))


def _features(img):
    """PUR. (masque pixels « nuage », pente sur 4 pixels) d'une image RGB."""
    import numpy as np
    rgb = np.asarray(img.convert("RGB"), dtype=np.int16)
    hsv = np.asarray(img.convert("RGB").convert("HSV"), dtype=np.int16)
    s, v = hsv[..., 1], hsv[..., 2]
    vf = v.astype(np.float32)
    gy = np.zeros_like(vf)
    gx = np.zeros_like(vf)
    gy[1:, :] = np.abs(vf[1:, :] - vf[:-1, :])
    gx[:, 1:] = np.abs(vf[:, 1:] - vf[:, :-1])
    grad = gx + gy
    # détail moyen sur 5 × 5 pixels (somme glissante par sommes cumulées)
    k = 5
    pad = np.pad(grad, ((k // 2 + 1, k // 2), (k // 2 + 1, k // 2)),
                 mode="edge")
    cs = pad.cumsum(0).cumsum(1)
    loc = (cs[k:, k:] - cs[:-k, k:] - cs[k:, :-k] + cs[:-k, :-k]) / (k * k)
    loc = loc[:grad.shape[0], :grad.shape[1]]
    white = rgb.min(axis=2) >= WHITE_MIN
    blue = (rgb[..., 2] - rgb[..., 0]) >= BLUE_MIN
    m = (v >= V_MIN) & (s <= S_MAX) & (loc <= GRAD_MAX) & ~white & \
        (loc >= FLAT_MIN) & blue
    return m, v


def pixel_mask(img):
    """PUR. Tableau booléen des pixels « nuage » (clair, sans couleur,
    flou ; ni blanc pur ni aplat) d'une image PIL RGB."""
    return _features(img)[0]


def _components(grid):
    """PUR. Ensembles de carrés voisins (voisinage 4) : liste de listes."""
    gh, gw = grid.shape
    seen = [[False] * gw for _ in range(gh)]
    comps = []
    for y in range(gh):
        for x in range(gw):
            if not grid[y, x] or seen[y][x]:
                continue
            stack, comp = [(y, x)], []
            seen[y][x] = True
            while stack:
                cy, cx = stack.pop()
                comp.append((cy, cx))
                for ny, nx in ((cy - 1, cx), (cy + 1, cx), (cy, cx - 1),
                               (cy, cx + 1)):
                    if 0 <= ny < gh and 0 <= nx < gw and grid[ny, nx] and \
                            not seen[ny][nx]:
                        seen[ny][nx] = True
                        stack.append((ny, nx))
            comps.append(comp)
    return comps


def _close(mask):
    """PUR. Fermeture 3 × 3 (bouche les trous d'un pixel)."""
    d = mask.copy()
    d[1:, :] |= mask[:-1, :]
    d[:-1, :] |= mask[1:, :]
    d[:, 1:] |= mask[:, :-1]
    d[:, :-1] |= mask[:, 1:]
    e = d.copy()
    e[1:, :] &= d[:-1, :]
    e[:-1, :] &= d[1:, :]
    e[:, 1:] &= d[:, :-1]
    e[:, :-1] &= d[:, 1:]
    return e


def edge_width(v, comp, block=BLOCK, hi=V_MIN, lo=EDGE_LO):
    """PUR. Largeur moyenne (pixels) du bord de cet ensemble : un nuage
    passe du clair au sol en douceur (bord large), un toit d'un coup (bord
    d'un ou deux pixels). = (surface ≥ lo − surface ≥ hi) / périmètre."""
    import numpy as np
    h, w = v.shape
    zone = np.zeros(v.shape, dtype=bool)
    for (y, x) in comp:
        zone[max(0, (y - 1) * block):min(h, (y + 2) * block),
             max(0, (x - 1) * block):min(w, (x + 2) * block)] = True
    m_hi = _close((v >= hi) & zone)
    m_lo = _close((v >= lo) & zone)
    inner = m_hi.copy()
    inner[1:, :] &= m_hi[:-1, :]
    inner[:-1, :] &= m_hi[1:, :]
    inner[:, 1:] &= m_hi[:, :-1]
    inner[:, :-1] &= m_hi[:, 1:]
    per = int((m_hi & ~inner).sum())
    if per == 0:
        return 0.0
    return float((m_lo & ~m_hi).sum()) / per


def block_mask(pmask, block=BLOCK, fill=BLOCK_FILL, min_blocks=MIN_BLOCKS,
               v=None, edge_min=EDGE_MIN):
    """PUR. Grille de carrés « nuage » (booléens) ; les ensembles de moins de
    min_blocks carrés voisins sont retirés, et (si v, la luminosité, est
    donnée) ceux dont le bord est net (objet, pas nuage)."""
    import numpy as np
    h, w = pmask.shape
    gh, gw = h // block, w // block
    if gh == 0 or gw == 0:
        return np.zeros((max(gh, 1), max(gw, 1)), dtype=bool)
    m = pmask[:gh * block, :gw * block].reshape(gh, block, gw, block)
    grid = m.mean(axis=(1, 3)) >= fill
    out = np.zeros_like(grid)
    for comp in _components(grid):
        if len(comp) < min_blocks:
            continue
        if v is not None and edge_width(v, comp, block) < edge_min:
            continue
        for cy, cx in comp:
            out[cy, cx] = True
    return out


def detect(img):
    """PUR. (part de nuages 0-1, grille de carrés) pour une image PIL."""
    im = img.convert("RGB")
    if max(im.size) > SCAN_SIZE:
        im = im.resize((SCAN_SIZE, SCAN_SIZE))
    pm, v = _features(im)
    grid = block_mask(pm, v=v)
    frac = float(grid.mean()) if grid.size else 0.0
    return frac, grid


def load_small(path):
    """Ouvre un JPG directement en petit (mode « draft » de Pillow : très
    rapide sur une image 4096 px)."""
    from PIL import Image
    im = Image.open(path)
    try:
        im.draft("RGB", (SCAN_SIZE, SCAN_SIZE))
    except Exception:
        pass
    return im.convert("RGB")


def full_alpha(grid, size, grow=1, feather=None):
    """PUR. Masque de fondu (PIL « L », 0-255) à la taille de l'image, à
    partir de la grille : carrés agrandis de `grow` carrés, bords fondus."""
    import numpy as np
    from PIL import Image, ImageFilter
    g = grid.copy()
    for _ in range(max(0, grow)):
        gg = g.copy()
        gg[1:, :] |= g[:-1, :]
        gg[:-1, :] |= g[1:, :]
        gg[:, 1:] |= g[:, :-1]
        gg[:, :-1] |= g[:, 1:]
        g = gg
    small = Image.fromarray((g * 255).astype(np.uint8), "L")
    big = small.resize(size, Image.NEAREST)
    feather = feather if feather is not None else max(4, size[0] // 160)
    return big.filter(ImageFilter.GaussianBlur(feather))


def match_colours(src, ref, alpha):
    """PUR. Ajuste les couleurs de src (image de remplacement) à celles de
    ref (image d'origine) sur la zone SANS nuage (alpha bas) : même moyenne
    et même écart par canal. Renvoie une image PIL RGB."""
    import numpy as np
    from PIL import Image
    a = np.asarray(alpha, dtype=np.float32) / 255.0
    s = np.asarray(src.convert("RGB"), dtype=np.float32)
    r = np.asarray(ref.convert("RGB"), dtype=np.float32)
    clear = a < 0.05
    if clear.sum() < 100:
        return src.convert("RGB")
    out = s.copy()
    for c in range(3):
        ms, ss = s[..., c][clear].mean(), s[..., c][clear].std() + 1e-3
        mr, sr = r[..., c][clear].mean(), r[..., c][clear].std() + 1e-3
        out[..., c] = (s[..., c] - ms) * (sr / ss) + mr
    return Image.fromarray(np.clip(out, 0, 255).astype(np.uint8), "RGB")


def compose(orig, repl, grid):
    """PUR. Image d'origine avec la zone du nuage prise dans repl (mêmes
    dimensions), couleurs ajustées, bords fondus."""
    from PIL import Image
    o = orig.convert("RGB")
    rp = repl.convert("RGB")
    if rp.size != o.size:
        rp = rp.resize(o.size, Image.BICUBIC)
    alpha = full_alpha(grid, o.size)
    rp = match_colours(rp, o, alpha)
    return Image.composite(rp, o, alpha)


def overlay_preview(img, grid):
    """PUR. Image réduite avec les nuages repérés teintés en rouge."""
    from PIL import Image
    im = img.convert("RGB")
    if max(im.size) > SCAN_SIZE:
        im = im.resize((SCAN_SIZE, SCAN_SIZE))
    a = full_alpha(grid, im.size, grow=0, feather=2).point(lambda p: p // 2)
    red = Image.new("RGB", im.size, (230, 40, 40))
    return Image.composite(red, im, a)


# ------------------------------------------------------------------------------
# Fichiers
# ------------------------------------------------------------------------------
def tile_jpgs(lat, lon):
    try:
        import O4_Build_Comfort_Utils as BC
        import O4_File_Names as FNAMES
        return [p for p in BC.tile_jpgs(lat, lon, FNAMES.Imagery_dir)
                if parse_jpg_name(p)]
    except Exception:
        return []


def scan_tile(lat, lon, progress=None, stop=None, paths=None):
    """[(chemin, part, grille)] des images de la tuile ayant au moins
    REPORT_MIN de nuages, de la plus nuageuse à la moins nuageuse."""
    paths = paths if paths is not None else tile_jpgs(lat, lon)
    out = []
    n = len(paths)
    for i, p in enumerate(paths):
        if stop is not None and stop():
            break
        try:
            frac, grid = detect(load_small(p))
        except Exception:
            continue
        if frac >= REPORT_MIN:
            out.append((p, frac, grid))
        if progress is not None:
            progress(i + 1, n)
    out.sort(key=lambda t: -t[1])
    return out


def backup_path(jpg):
    return jpg + BACKUP_SUFFIX


def has_backup(jpg):
    return os.path.isfile(backup_path(jpg))


def dds_for(jpg, lat, lon, cbd=""):
    """DDS de cette image dans le dossier de la tuile (même recherche que la
    réparation des images blanches)."""
    try:
        import O4_Image_Repair_Utils as IR
        import O4_File_Names as FNAMES
        wdirs = [FNAMES.Tile_dir]
        if cbd:
            wdirs.append(cbd if cbd.endswith(("/", "\\")) else
                         os.path.dirname(cbd))
        it = IR.locate([os.path.basename(jpg)], FNAMES.Imagery_dir, wdirs)
        return (it[0].get("dds_all") or ([it[0]["dds"]] if it[0]["dds"]
                                         else [])) if it else []
    except Exception:
        return []


def replace_one(jpg, grid, alt_code, downloader=None, workdir=None):
    """Remplace les nuages d'UNE image. Renvoie (ok, message). L'original
    est gardé à côté (une seule fois : la 1re version reste la référence)."""
    from PIL import Image
    info = parse_jpg_name(jpg)
    if not info:
        return (False, "name")
    til_y, til_x, _code, zl = info
    tmp = workdir or tempfile.mkdtemp(prefix="o4x_cloud_")
    name = "repl_%d_%d_%s%d.jpg" % (til_y, til_x, alt_code, zl)
    try:
        if downloader is None:
            import O4_Imagery_Utils as IMG
            downloader = IMG.download_jpeg_ortho
        ok = downloader(tmp, name, til_x, til_y, zl, alt_code)
        rp = os.path.join(tmp, name)
        if not ok or not os.path.isfile(rp):
            return (False, _L("la source %s n'a pas répondu" % alt_code,
                              "source %s did not answer" % alt_code))
        orig = Image.open(jpg).convert("RGB")
        repl = Image.open(rp).convert("RGB")
        frac_r, _g = detect(repl)
        new = compose(orig, repl, grid)
        if not has_backup(jpg):
            shutil.copy2(jpg, backup_path(jpg))
        new.save(jpg + ".tmp.jpg", quality=95)
        os.replace(jpg + ".tmp.jpg", jpg)
        msg = "ok"
        if frac_r >= REPORT_MIN:
            msg = _L("remplacée, mais %s a aussi %d %% de nuages ici"
                     % (alt_code, round(100 * frac_r)),
                     "replaced, but %s also has %d %% clouds here"
                     % (alt_code, round(100 * frac_r)))
        return (True, msg)
    except Exception as e:
        return (False, str(e))
    finally:
        if workdir is None:
            shutil.rmtree(tmp, ignore_errors=True)


def restore_tile(lat, lon, paths=None):
    """Remet les photos d'origine de la tuile. Renvoie la liste des JPG
    remis (leurs DDS sont à refaire)."""
    paths = paths if paths is not None else tile_jpgs(lat, lon)
    done = []
    for p in paths:
        b = backup_path(p)
        if os.path.isfile(b):
            try:
                os.replace(b, p)
                done.append(p)
            except Exception:
                pass
    return done


def drop_dds(paths):
    n = 0
    for p in paths:
        try:
            if p.lower().endswith(".dds") and os.path.isfile(p):
                os.remove(p)
                n += 1
        except Exception:
            pass
    return n


def is_busy():
    try:
        import O4_UI_Utils as UI
        return bool(getattr(UI, "is_working", False))
    except Exception:
        return False


def replacement_sources(lat, lon, exclude=""):
    """Sources simples proposées pour remplacer (nationales qui couvrent la
    tuile d'abord, puis mondiales), sans la source d'origine."""
    out = []
    try:
        import O4_Imagery_Utils as IMG
        pd = getattr(IMG, "providers_dict", {})
        try:
            import O4_Grand_Public_Utils as GP
            for code, _c in GP.candidate_providers(IMG, lat, lon):
                if code in pd and code != exclude and code not in out:
                    out.append(code)
        except Exception:
            pass
        for code in sorted(pd):
            p = pd[code]
            try:
                if not p.get("in_GUI", True) or \
                        p.get("request_type") == "local_tms":
                    continue
                if p.get("extent", "global") != "global":
                    continue
            except Exception:
                continue
            if code != exclude and code not in out:
                out.append(code)
    except Exception:
        pass
    return out


# ------------------------------------------------------------------------------
# Fenêtre. Point d'entrée : run_cloud_window(parent, tile=None)
# ------------------------------------------------------------------------------
_OPEN = {"win": None}


def run_cloud_window(parent=None, tile=None, cbd=""):
    import tkinter as tk
    from tkinter import messagebox
    try:
        from tkinter import ttk
    except Exception:
        ttk = None
    try:
        from PIL import ImageTk
    except Exception:
        ImageTk = None

    try:
        w0 = _OPEN.get("win")
        if w0 is not None and w0.winfo_exists():
            if tile is not None and hasattr(w0, "_cloud_set_tile"):
                w0._cloud_set_tile(tile)
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
    win.title(_L("Nuages sur les images - Ortho4XP V4",
                 "Clouds on the images - Ortho4XP V4"))
    win.configure(bg=BG)
    if _TM is not None:
        try:
            _TM.apply_to_root(win)
        except Exception:
            pass
    try:
        sw, sh = win.winfo_screenwidth(), win.winfo_screenheight()
        win.geometry("%dx%d" % (min(900, int(sw * 0.95)),
                                min(700, int(sh * 0.9))))
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

    if tile is None:
        # Mode expert : la tuile et le dossier de la fenêtre principale
        try:
            tile = (int(parent.lat.get()), int(parent.lon.get()))
        except Exception:
            tile = None
        if not cbd:
            try:
                cbd = parent.custom_build_dir.get() or ""
            except Exception:
                cbd = ""
    st = {"tile": tuple(tile) if tile else None, "found": [], "vars": [],
          "scanning": False, "stop": False, "cur": None}

    tk.Label(win, text=_L(
        "Repère les nuages sur les images téléchargées d'une tuile. Vous "
        "voyez chaque image (nuages en rouge), vous cochez celles à corriger "
        "et la source qui remplacera les nuages. Les photos d'origine sont "
        "gardées : « Remettre les photos d'origine » les rend à tout moment.",
        "Finds clouds on a tile's downloaded images. You see each image "
        "(clouds in red), tick those to fix and the source that will replace "
        "the clouds. The original photos are kept: « Put back the original "
        "photos » brings them back at any time."), bg=BG, fg=FG, font=FONT_S,
        justify="left", anchor="w", wraplength=860).pack(fill=tk.X, padx=10,
                                                         pady=(10, 4))
    top = tk.Frame(win, bg=BG)
    top.pack(fill=tk.X, padx=10)
    tk.Label(top, text=_L("Tuile :", "Tile:"), bg=BG, fg=FG,
             font=FONT).pack(side=tk.LEFT)
    tile_var = tk.StringVar(value=short_latlon(*st["tile"]) if st["tile"]
                            else "")
    tk.Entry(top, textvariable=tile_var, width=10, font=FONT).pack(
        side=tk.LEFT, padx=6)
    _btn(top, _L("☁ Chercher les nuages", "☁ Find the clouds"),
         lambda: _scan()).pack(side=tk.LEFT, padx=4)

    body = tk.Frame(win, bg=BG)
    body.pack(fill=tk.BOTH, expand=True, padx=10, pady=6)
    body.columnconfigure(0, weight=1)
    body.columnconfigure(1, weight=1)
    body.rowconfigure(0, weight=1)
    # liste défilante des images à nuages
    lf = tk.Frame(body, bg=BG)
    lf.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
    canvas = tk.Canvas(lf, bg=BG, highlightthickness=0)
    sb = tk.Scrollbar(lf, orient="vertical", command=canvas.yview)
    canvas.configure(yscrollcommand=sb.set)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    rows = tk.Frame(canvas, bg=BG)
    canvas.create_window((0, 0), window=rows, anchor="nw")
    rows.bind("<Configure>",
              lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    # aperçu
    pv = tk.Frame(body, bg=BG)
    pv.grid(row=0, column=1, sticky="nsew")
    pv_title = tk.StringVar(value="")
    tk.Label(pv, textvariable=pv_title, bg=BG, fg=FG2, font=FONT_B,
             anchor="w").pack(fill=tk.X)
    pv_img = tk.Label(pv, bg=BG)
    pv_img.pack(pady=4)

    opt = tk.Frame(win, bg=BG)
    opt.pack(fill=tk.X, padx=10)
    tk.Label(opt, text=_L("Remplacer les nuages par la source :",
                          "Replace the clouds with the source:"), bg=BG,
             fg=FG, font=FONT_S).pack(side=tk.LEFT)
    alt_var = tk.StringVar(value="")
    alt_cb = None
    if ttk is not None:
        try:
            alt_cb = ttk.Combobox(opt, textvariable=alt_var, values=[],
                                  state="readonly", width=24)
            alt_cb.pack(side=tk.LEFT, padx=6)
        except Exception:
            alt_cb = None
    status_var = tk.StringVar(value="")
    tk.Label(win, textvariable=status_var, bg=BG, fg=FG, font=FONT_S,
             justify="left", anchor="w", wraplength=860).pack(fill=tk.X,
                                                              padx=10)
    bot = tk.Frame(win, bg=BG)
    bot.pack(fill=tk.X, padx=10, pady=(4, 10))

    def _parse_tile():
        m = re.match(r"^\s*([+-]?\d{1,2})\s*([+-]\d{1,3})\s*$",
                     tile_var.get())
        if not m:
            return None
        t = (int(m.group(1)), int(m.group(2)))
        return t if (-90 <= t[0] < 90 and -180 <= t[1] < 180) else None

    def _set_tile(t):
        st["tile"] = tuple(t)
        tile_var.set(short_latlon(*t))

    win._cloud_set_tile = _set_tile

    def _show(i):
        if i is None or i >= len(st["found"]):
            return
        p, frac, grid = st["found"][i]
        st["cur"] = i
        pv_title.set("%s — %d %%" % (os.path.basename(p), round(100 * frac))
                     + (_L("  (déjà corrigée)", "  (already fixed)")
                        if has_backup(p) else ""))
        if ImageTk is None:
            return
        try:
            im = overlay_preview(load_small(p), grid)
            side = 380
            im.thumbnail((side, side))
            ph = ImageTk.PhotoImage(im)
            pv_img.configure(image=ph)
            pv_img.image = ph            # garder l'image (ramasse-miettes Tk)
        except Exception:
            pass

    def _fill_rows():
        for ch in list(rows.winfo_children()):
            try:
                ch.destroy()
            except Exception:
                pass
        st["vars"] = []
        if not st["found"]:
            tk.Label(rows, text=_L("Aucun nuage repéré.", "No cloud found."),
                     bg=BG, fg=FG, font=FONT).pack(anchor="w")
            return
        for i, (p, frac, _g) in enumerate(st["found"]):
            v = tk.BooleanVar(value=frac >= TICK_MIN and not has_backup(p))
            st["vars"].append(v)
            f = tk.Frame(rows, bg=BG)
            f.pack(fill=tk.X, anchor="w")
            tk.Checkbutton(f, variable=v, bg=BG, fg=FG, selectcolor=BG,
                           activebackground=BG, highlightthickness=0).pack(
                side=tk.LEFT)
            lab = tk.Label(f, text="%s   %d %%%s" % (
                os.path.basename(p), round(100 * frac),
                _L("  ✔ corrigée", "  ✔ fixed") if has_backup(p) else ""),
                bg=BG, fg=FG, font=FONT_S, cursor="hand2", anchor="w")
            lab.pack(side=tk.LEFT, fill=tk.X)
            lab.bind("<ButtonRelease-1>", lambda e=None, k=i: _show(k))
        _show(0)

    def _scan():
        if st["scanning"]:
            return
        t = _parse_tile()
        if t is None:
            messagebox.showinfo(win.title(), _L(
                "Tapez une tuile, par exemple +46-003.",
                "Type a tile, for example +46-003."), parent=win)
            return
        st["tile"] = t
        paths = tile_jpgs(*t)
        if not paths:
            status_var.set(_L("Aucune image téléchargée pour %s : construisez "
                              "d'abord la tuile." % short_latlon(*t),
                              "No downloaded image for %s: build the tile "
                              "first." % short_latlon(*t)))
            return
        codes = []
        info = parse_jpg_name(paths[0])
        srcs = replacement_sources(t[0], t[1],
                                   exclude=info[2] if info else "")
        if alt_cb is not None:
            try:
                alt_cb.configure(values=srcs)
            except Exception:
                pass
        if srcs and alt_var.get() not in srcs:
            alt_var.set(srcs[0])
        st["scanning"] = True
        st["stop"] = False
        prog = {"i": 0, "n": len(paths)}
        box = {}

        def _work():
            box["r"] = scan_tile(t[0], t[1], paths=paths,
                                 progress=lambda i, n: prog.update(i=i),
                                 stop=lambda: st["stop"])

        th = threading.Thread(target=_work, daemon=True)
        th.start()

        def _poll():
            if th.is_alive():
                status_var.set(_L("Recherche : %d / %d images…",
                                  "Searching: %d / %d images…")
                               % (prog["i"], prog["n"]))
                try:
                    win.after(300, _poll)
                except Exception:
                    pass
                return
            st["scanning"] = False
            st["found"] = box.get("r", [])
            status_var.set(_L("%d image(s) sur %d avec des nuages. Cliquez "
                              "un nom pour la voir.",
                              "%d image(s) of %d with clouds. Click a name "
                              "to see it.") % (len(st["found"]), len(paths)))
            _fill_rows()

        win.after(300, _poll)

    def _offer_rebuild(t, n_dds):
        if not messagebox.askyesno(win.title(), _L(
                "%d image(s) à refaire en texture. Refaire l'étape 3 de %s "
                "maintenant ? (seules ces images sont reconverties ; le "
                "détail s'affiche dans la fenêtre principale)"
                % (n_dds, short_latlon(*t)),
                "%d image(s) to make into textures again. Redo step 3 of %s "
                "now? (only these images are converted again; details show "
                "in the main window)" % (n_dds, short_latlon(*t))),
                parent=win):
            status_var.set(_L("Pensez à refaire l'étape 3 de la tuile.",
                              "Remember to redo the tile's step 3."))
            return
        try:
            import O4_Image_Repair_Utils as IR
            import O4_File_Names as FNAMES
            import O4_Config_Utils as CFG
            bd = CFG.Tile(t[0], t[1], cbd).build_dir
        except Exception as e:
            messagebox.showerror(win.title(), str(e), parent=win)
            return
        state = {}
        th = threading.Thread(target=lambda: IR.rebuild_tiles([(t, bd)],
                                                              state),
                              daemon=True)
        th.start()

        def _poll():
            if th.is_alive():
                status_var.set(_L("Étape 3 en cours…", "Step 3 running…"))
                win.after(1000, _poll)
                return
            ok = state.get("ok") or []
            status_var.set(_L("Étape 3 terminée : ", "Step 3 finished: ")
                           + (_L("réussie", "succeeded") if ok else
                              _L("échec, voir le Diagnostic",
                                 "failed, see the Diagnostic")))

        win.after(1000, _poll)

    def _replace():
        t = st["tile"]
        chosen = [st["found"][i] for i, v in enumerate(st["vars"]) if v.get()]
        alt = alt_var.get()
        if not chosen or not alt:
            messagebox.showinfo(win.title(), _L(
                "Cochez au moins une image et choisissez une source.",
                "Tick at least one image and choose a source."), parent=win)
            return
        if is_busy():
            messagebox.showwarning(win.title(), _L(
                "Une construction est en cours : attendez la fin.",
                "A build is running: wait for it to end."), parent=win)
            return
        if not messagebox.askyesno(win.title(), _L(
                "Remplacer les nuages de %d image(s) par la source %s ?\n\n"
                "Les photos d'origine sont gardées." % (len(chosen), alt),
                "Replace the clouds of %d image(s) with source %s?\n\nThe "
                "original photos are kept." % (len(chosen), alt)),
                parent=win):
            return
        prog = {"i": 0}
        box = {"ok": [], "ko": [], "notes": []}

        def _work():
            for p, _f, grid in chosen:
                ok, msg = replace_one(p, grid, alt)
                (box["ok"] if ok else box["ko"]).append(
                    (os.path.basename(p), msg))
                prog["i"] += 1

        th = threading.Thread(target=_work, daemon=True)
        th.start()

        def _poll():
            if th.is_alive():
                status_var.set(_L("Remplacement : %d / %d…",
                                  "Replacing: %d / %d…")
                               % (prog["i"], len(chosen)))
                win.after(500, _poll)
                return
            done = [p for p, _f, _g in chosen
                    if os.path.basename(p) in [x[0] for x in box["ok"]]]
            dds = []
            for p in done:
                dds.extend(dds_for(p, t[0], t[1], cbd))
            drop_dds(dds)
            try:
                import O4_UI_Utils as UI
                UI.logprint("Clouds / Nuages:", short_latlon(*t), alt,
                            len(done), "replaced")
            except Exception:
                pass
            txt = _L("%d image(s) corrigée(s)", "%d image(s) fixed") \
                % len(done)
            notes = [n + " : " + m for n, m in box["ok"] if m != "ok"]
            if notes or box["ko"]:
                txt += "\n" + "\n".join(
                    notes[:5] + ["%s : %s" % x for x in box["ko"][:5]])
            status_var.set(txt)
            _fill_rows()
            if done:
                _offer_rebuild(t, len(done))

        win.after(500, _poll)

    def _restore():
        t = _parse_tile()
        if t is None:
            return
        if is_busy():
            messagebox.showwarning(win.title(), _L(
                "Une construction est en cours : attendez la fin.",
                "A build is running: wait for it to end."), parent=win)
            return
        paths = [p for p in tile_jpgs(*t) if has_backup(p)]
        if not paths:
            messagebox.showinfo(win.title(), _L(
                "Aucune photo corrigée sur cette tuile.",
                "No fixed photo on this tile."), parent=win)
            return
        if not messagebox.askyesno(win.title(), _L(
                "Remettre les %d photo(s) d'origine de %s ?"
                % (len(paths), short_latlon(*t)),
                "Put back the %d original photo(s) of %s?"
                % (len(paths), short_latlon(*t))), parent=win):
            return
        done = restore_tile(t[0], t[1], paths=paths)
        dds = []
        for p in done:
            dds.extend(dds_for(p, t[0], t[1], cbd))
        drop_dds(dds)
        status_var.set(_L("%d photo(s) d'origine remise(s).",
                          "%d original photo(s) put back.") % len(done))
        _fill_rows()
        if done:
            _offer_rebuild(t, len(done))

    def _tick(val):
        for v in st["vars"]:
            v.set(val)

    for i, (txt, cmd) in enumerate((
            (_L("Tout cocher", "Tick all"), lambda: _tick(True)),
            (_L("Tout décocher", "Untick all"), lambda: _tick(False)),
            (_L("☁→🖼 Remplacer les nuages cochés", "☁→🖼 Replace the "
                "ticked clouds"), _replace),
            (_L("↩ Remettre les photos d'origine", "↩ Put back the "
                "original photos"), _restore))):
        _btn(bot, txt, cmd).grid(row=0, column=i, sticky="ew", padx=2)
        bot.columnconfigure(i, weight=1)

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
    return win
