# -*- coding: utf-8 -*-
# ============================================================
# Copyright (c) 2024-2026 Roland (Ypsos)
#
# CRÉDIT — AUTEUR : Roland (Ypsos) — Novembre 2026
# Module conçu et spécifié par Roland (Ypsos) pour Ortho4XP V4.
# Cette notice d'auteur et de copyright doit être conservée
# conformément à la GPLv3.
# Licence : GPLv3 + conditions additionnelles (art. 7),
# voir AVERTISSEMENT_LICENCE_LEGAL.md, section 16.
# ============================================================
# Copyright (c) 2024-2026 Roland (Ypsos)
#
# CREDIT — AUTHOR: Roland (Ypsos) — November 2026
# Module designed and specified by Roland (Ypsos) for Ortho4XP V4.
# This authorship and copyright notice must be retained
# in accordance with GPLv3.
# License: GPLv3 + additional terms (Sec. 7),
# see AVERTISSEMENT_LICENCE_LEGAL.md, Section 16.
# ============================================================
# ------------------------------------------------------------------------------
# O4_America_DEM_Utils.py
# Reliefs du Canada (MRDEM-30, terrain nu) et d'Amérique du Sud (ANADEM, sol
# sous la forêt), pour la source d'élévation d'Ortho4XP (novembre 2026).
# Auteur : Roland (Ypsos) - GPLv3
#
# 100 % ADDITIF : appelé seulement par O4_DEM_Utils.ensure_elevation quand
# l'utilisateur choisit l'une de ces deux sources. macOS / Windows / Linux
# (rasterio, déjà utilisé par Ortho4XP).
#
# Sortie : une grille 3601 × 3601 (1″, ~30 m) en EPSG:4326 qui couvre
# exactement la tuile (même grille que les .hgt 1″), GeoTIFF float32,
# « sans donnée » = -32768, relue par la branche rasterio existante de
# read_elevation_from_file.
#
# CANADA — MRDEM-30-DTM de Ressources naturelles Canada : un seul fichier COG
#   public (aucune clé), qui intègre déjà le lidar HRDEM là où il existe. Seule
#   la fenêtre de la tuile est lue (GDAL ne télécharge que les blocs utiles),
#   reprojetée de EPSG:3979 vers EPSG:4326. Hors du Canada (frontière avec les
#   États-Unis, mer) : complété avec Copernicus GLO-30.
# AMÉRIQUE DU SUD — ANADEM v1 (Agência Nacional de Águas / UFRGS) : publié par
#   grandes dalles MGRS (ex. anadem_v1_mgrs_21j.tif), sans lien direct stable :
#   l'utilisateur télécharge UNE fois la dalle indiquée et la range dans
#   Elevation_data/ANADEM/. Tant qu'elle manque : message clair + Copernicus
#   GLO-30 à la place (la tuile reste correcte).
# ------------------------------------------------------------------------------

import math
import os
import re

MRDEM_URL = ("https://datacube-prod-data-public.s3.ca-central-1.amazonaws.com"
             "/store/elevation/mrdem/mrdem-30/mrdem-30-dtm.tif")
ANADEM_PAGE = "https://hge-iph.github.io/anadem/"
GRID = 3601
NODATA = -32768.0
_BANDS = "CDEFGHJKLMNPQRSTUVWX"          # bandes MGRS (sans I ni O), 8° chacune


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


# ------------------------------------------------------------------------------
# PUR
# ------------------------------------------------------------------------------
def mgrs_gzd(lat, lon):
    """PUR. Zone MGRS (zone UTM + bande de latitude) d'un point, ex.
    (-23.5, -46.6) -> « 23K ». Règle standard (exceptions Norvège /
    Svalbard sans objet en Amérique du Sud)."""
    zone = int(math.floor((lon + 180.0) / 6.0)) + 1
    zone = max(1, min(60, zone))
    idx = int(math.floor((lat + 80.0) / 8.0))
    idx = max(0, min(len(_BANDS) - 1, idx))
    return "%d%s" % (zone, _BANDS[idx])


def tile_gzds(lat, lon):
    """PUR. Zone(s) MGRS touchées par la tuile 1° × 1° (souvent une seule,
    parfois deux ou quatre aux limites)."""
    out = []
    eps = 1e-6
    for la in (lat + eps, lat + 1 - eps):
        for lo in (lon + eps, lon + 1 - eps):
            z = mgrs_gzd(la, lo)
            if z not in out:
                out.append(z)
    return out


def grid_transform(lat, lon):
    """PUR. Géoréférencement de la grille 3601 × 3601 : centres de pixels
    exactement sur les points 1″ de la tuile (comme un .hgt)."""
    from rasterio.transform import Affine
    res = 1.0 / (GRID - 1)
    return Affine(res, 0.0, lon - res / 2.0, 0.0, -res, lat + 1 + res / 2.0)


def anadem_name_matches(fname, gzd):
    """PUR. Le fichier est-il la dalle ANADEM de cette zone ? Accepte
    anadem_v1_mgrs_21j.tif, anadem_v1_21J.tif, ANADEM_v1_mgrs_21J.TIF…"""
    low = fname.lower()
    return (low.startswith("anadem") and low.endswith(".tif") and
            re.search(r"(^|_)%s\.tif$" % re.escape(gzd.lower()), low)
            is not None)


# ------------------------------------------------------------------------------
# Raster (rasterio)
# ------------------------------------------------------------------------------
def read_window_grid(src, lat, lon, resampling="bilinear"):
    """Grille de la tuile depuis un raster OUVERT (rasterio) : seule la
    fenêtre utile est lue (marge 0,02°), puis reprojetée vers EPSG:4326
    (même appel reproject(tableau…) que le module Altimétrie validé)."""
    import numpy as np
    from rasterio.warp import reproject, transform_bounds, Resampling
    from rasterio.windows import Window, from_bounds
    dst = np.full((GRID, GRID), NODATA, dtype=np.float32)
    crs = src.crs or "EPSG:4326"
    m = 0.02
    b = transform_bounds("EPSG:4326", crs, lon - m, lat - m, lon + 1 + m,
                         lat + 1 + m, densify_pts=21)
    win = from_bounds(*b, transform=src.transform)
    col0 = int(math.floor(win.col_off))
    row0 = int(math.floor(win.row_off))
    col1 = int(math.ceil(win.col_off + win.width))
    row1 = int(math.ceil(win.row_off + win.height))
    col0, row0 = max(0, col0), max(0, row0)
    col1, row1 = min(src.width, col1), min(src.height, row1)
    if col1 <= col0 or row1 <= row0:
        return dst                     # la tuile est hors de ce raster
    win = Window(col0, row0, col1 - col0, row1 - row0)
    data = src.read(1, window=win).astype(np.float32)
    src_nd = src.nodata if src.nodata is not None else NODATA
    reproject(
        source=data,
        destination=dst,
        src_transform=src.window_transform(win),
        src_crs=crs,
        src_nodata=src_nd,
        dst_transform=grid_transform(lat, lon),
        dst_crs="EPSG:4326",
        dst_nodata=NODATA,
        resampling=getattr(Resampling, resampling),
    )
    # valeurs aberrantes (anciens codes « sans donnée » -9999, -3.4e38…)
    dst[(dst < -1000) | (dst > 9000)] = NODATA
    return dst


def grid_from_raster(src_path, lat, lon, resampling="bilinear"):
    """Grille de la tuile (numpy float32, 3601 × 3601, -32768 = sans donnée)
    lue dans un raster quelconque (fichier local ou URL https d'un COG)."""
    import rasterio
    with rasterio.open(src_path) as src:
        return read_window_grid(src, lat, lon, resampling)


def valid_fraction(arr):
    import numpy as np
    return float(np.mean(arr != NODATA)) if arr.size else 0.0


def fill_from(arr, other):
    """Complète les trous de arr avec other (même grille). Renvoie arr."""
    if other is None:
        return arr
    m = (arr == NODATA) & (other != NODATA)
    arr[m] = other[m]
    return arr


def write_grid(arr, lat, lon, out_path):
    import rasterio
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp = out_path + ".tmp.tif"
    with rasterio.open(tmp, "w", driver="GTiff", width=GRID, height=GRID,
                       count=1, dtype="float32", crs="EPSG:4326",
                       transform=grid_transform(lat, lon), nodata=NODATA,
                       compress="deflate", tiled=True) as ds:
        ds.write(arr, 1)
    os.replace(tmp, out_path)
    return out_path


def _cop30_grid(lat, lon, cop30):
    """Grille Copernicus de la tuile (ou None). cop30 = (ensure, path)."""
    if cop30 is None:
        return None
    ensure, path = cop30
    try:
        p = path(lat, lon)
        if not os.path.isfile(p) and not ensure(lat, lon):
            return None
        return grid_from_raster(p, lat, lon)
    except Exception:
        return None


# ------------------------------------------------------------------------------
# Canada
# ------------------------------------------------------------------------------
def ensure_canada(lat, lon, out_path, cop30=None, log=None, url=MRDEM_URL,
                  reader=None):
    """Relief MRDEM-30 de la tuile, complété par Copernicus hors Canada.
    Renvoie 1 (fichier écrit) ou 0 (rien d'utilisable)."""
    log = log or (lambda m: None)
    reader = reader or grid_from_raster
    if os.path.isfile(out_path):
        return 1
    try:
        arr = reader(url, lat, lon)
    except Exception as e:
        log(_L("    Relief du Canada : lecture impossible (%s)." % e,
               "    Canada relief: cannot read (%s)." % e))
        arr = None
    frac = valid_fraction(arr) if arr is not None else 0.0
    if frac < 1.0:
        cop = _cop30_grid(lat, lon, cop30)
        if arr is None:
            arr = cop
        else:
            fill_from(arr, cop)
    if arr is None or valid_fraction(arr) == 0.0:
        log(_L("    Relief du Canada : aucune donnée pour cette tuile.",
               "    Canada relief: no data for this tile."))
        return 0
    write_grid(arr, lat, lon, out_path)
    log(_L("    Relief du Canada (MRDEM-30) : %d %% de la tuile, le reste en "
           "Copernicus." % round(100 * frac),
           "    Canada relief (MRDEM-30): %d %% of the tile, the rest from "
           "Copernicus." % round(100 * frac)))
    return 1


# ------------------------------------------------------------------------------
# Amérique du Sud
# ------------------------------------------------------------------------------
def anadem_dir():
    try:
        import O4_File_Names as FNAMES
        return os.path.join(FNAMES.Elevation_dir, "ANADEM")
    except Exception:
        return os.path.join("Elevation_data", "ANADEM")


def find_anadem(gzd, folder=None):
    """Chemin de la dalle ANADEM de cette zone, rangée par l'utilisateur
    (dans le dossier ANADEM ou un de ses sous-dossiers), ou ""."""
    folder = folder or anadem_dir()
    for root, _dirs, files in os.walk(folder):
        for f in sorted(files):
            if anadem_name_matches(f, gzd):
                return os.path.join(root, f)
    return ""


def ensure_anadem(lat, lon, out_path, cop30=None, log=None, folder=None,
                  reader=None):
    """Relief ANADEM de la tuile (dalles MGRS rangées par l'utilisateur),
    complété par Copernicus. Dalle manquante : message + Copernicus seul."""
    log = log or (lambda m: None)
    reader = reader or grid_from_raster
    zones = tile_gzds(lat, lon)
    if os.path.isfile(out_path):
        if not is_partial(out_path):
            return 1
        if any(not find_anadem(z, folder) for z in zones):
            return 1          # toujours incomplet : on réutilise
        # les dalles manquantes sont arrivées : on refait le fichier
        for f in (out_path, out_path + ".partial"):
            try:
                os.remove(f)
            except Exception:
                pass
    arr, missing = None, []
    for z in zones:
        p = find_anadem(z, folder)
        if not p:
            missing.append(z)
            continue
        try:
            g = reader(p, lat, lon)
        except Exception as e:
            log("    ANADEM %s : %s" % (z, e))
            missing.append(z)
            continue
        arr = g if arr is None else fill_from(arr, g)
    if missing:
        names = ", ".join("anadem_v1_mgrs_%s.tif" % z.lower() for z in missing)
        log(_L("    ANADEM : dalle(s) à télécharger une fois : %s — page %s — "
               "puis à ranger dans %s. Copernicus GLO-30 utilisé en attendant."
               % (names, ANADEM_PAGE, folder or anadem_dir()),
               "    ANADEM: tile(s) to download once: %s — page %s — then put "
               "them in %s. Copernicus GLO-30 used meanwhile."
               % (names, ANADEM_PAGE, folder or anadem_dir())))
    frac = valid_fraction(arr) if arr is not None else 0.0
    if frac < 1.0:
        cop = _cop30_grid(lat, lon, cop30)
        arr = cop if arr is None else fill_from(arr, cop)
    if arr is None or valid_fraction(arr) == 0.0:
        return 0
    write_grid(arr, lat, lon, out_path)
    if missing:
        # marqué « incomplet » : refait tout seul dès que les dalles
        # manquantes sont rangées dans le dossier ANADEM
        try:
            open(out_path + ".partial", "w").close()
        except Exception:
            pass
    return 1


def is_partial(out_path):
    """Le fichier ANADEM a-t-il été fait sans toutes ses dalles ?"""
    return os.path.isfile(out_path + ".partial")
