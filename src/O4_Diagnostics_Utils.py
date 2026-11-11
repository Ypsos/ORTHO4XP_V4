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
O4_Diagnostics_Utils.py — Diagnostic compréhensible par un débutant.

MODULE AUTONOME (100 % additif, LECTURE SEULE sur tout le projet) :
  - n'est importé par aucun fichier existant tant qu'on ne le raccorde pas ;
  - ne modifie AUCUN fichier d'Ortho4XP, de X-Plane ni de configuration ;
  - seule écriture possible : le ZIP « rapport » créé à la demande dans
    <Ortho4XP>/Rapports/ (bouton « Préparer un rapport »).

TROIS SOURCES DE DIAGNOSTIC
  1. Le journal Ortho4XP.log (dernière session ou toutes) : chaque message
     technique connu est traduit en langage simple (gravité, cause probable,
     solution). Un message ERROR inconnu est quand même signalé (brut).
  2. La machine : place libre, format du disque (FAT32 / exFAT), mémoire,
     outils Utils/, conseil Windows Defender.
  3. Les scènes X-Plane (scenery_packs.ini, lu sans écrire) : doublons de
     tuiles, ortho placée au-dessus des overlays/aéroports, conflit avec
     AutoOrtho / OrthoStudio Live, overlay Ortho4XP + SimHeaven, dossiers
     absents.
  4. Les réglages graphiques de X-Plane (X-Plane.prf, lu sans écrire) :
     qualité des textures inférieure au maximum.

POINTS D'ENTRÉE (à raccorder plus tard, ex. menu Outils) :
  run_diagnostics(parent=None)          -> fenêtre « Diagnostic »
  run_all(log_sessions=1, ini_path=None) -> liste de constats (sans fenêtre)
  format_text(findings)                  -> texte lisible (console/rapport)
  make_report_zip(findings=None)         -> chemin du ZIP créé

Un constat (finding) = dict :
  sev      : "rouge" | "orange" | "jaune" | "info" | "ok"
  source   : "journal" | "machine" | "scenes" | "xplane"
  title    : phrase simple
  explain  : explication simple
  cause    : cause probable
  solution : ce qu'il faut faire
  count    : nombre d'occurrences (journal)
  raw      : lignes techniques d'origine (panneau Expert)

Tout est défensif : une erreur interne du diagnostic ne remonte jamais.
"""

import os
import re
import sys
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


# ------------------------------------------------------------------------------
# Racine du projet (sans rien coder en dur)
# ------------------------------------------------------------------------------
def _root_dir():
    try:
        import O4_File_Names as FNAMES
        return FNAMES.Ortho4XP_dir
    except Exception:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _log_path():
    try:
        import O4_Log_Collector as LOGCOL
        p = LOGCOL.log_path()
        if p:
            return p
    except Exception:
        pass
    return os.path.join(_root_dir(), "Ortho4XP.log")


# ------------------------------------------------------------------------------
# Gravités
# ------------------------------------------------------------------------------
SEV_ORDER = {"rouge": 0, "orange": 1, "jaune": 2, "info": 3, "ok": 4}
SEV_ICON = {"rouge": "🔴", "orange": "🟠", "jaune": "🟡", "info": "🔵",
            "ok": "🟢"}


def sev_label(sev):
    return {
        "rouge": _L("Bloquant", "Blocking"),
        "orange": _L("Important", "Important"),
        "jaune": _L("À surveiller", "Worth checking"),
        "info": _L("Information", "Information"),
        "ok": _L("Tout va bien", "All good"),
    }.get(sev, sev)


def _finding(sev, source, title, explain="", cause="", solution="",
             count=1, raw=None, fid=""):
    return {
        "id": fid,
        "sev": sev,
        "source": source,
        "title": title,
        "explain": explain,
        "cause": cause,
        "solution": solution,
        "count": count,
        "raw": list(raw or []),
    }


# ------------------------------------------------------------------------------
# CHAPITRE 1 — Catalogue des messages connus du journal
# Chaque entrée : (id, motif regex insensible à la casse, gravité,
#                  (titre FR, EN), (explication FR, EN), (cause FR, EN),
#                  (solution FR, EN))
# Les motifs ont été écrits d'après les VRAIS messages du code et du journal.
# L'ordre compte : la première entrée qui correspond gagne.
# ------------------------------------------------------------------------------
_CATALOGUE = [
    ("parallel_task",
     r"unhandled exception in a parallel task",
     "rouge",
     ("Une tâche de construction a planté : la construction a été arrêtée.",
      "A build task crashed: the build was stopped."),
     ("Une des tâches lancées en parallèle (images, textures) a rencontré une "
      "erreur imprévue. Ortho4XP s'est arrêté proprement au lieu de fabriquer "
      "une tuile incomplète.",
      "One of the parallel tasks (images, textures) hit an unexpected error. "
      "Ortho4XP stopped cleanly instead of producing an incomplete tile."),
     ("Souvent une image illisible, un disque plein ou débranché, ou une "
      "source d'imagerie qui a répondu n'importe quoi.",
      "Often an unreadable image, a full or unplugged disk, or an imagery "
      "source that returned garbage."),
     ("Relancez la même étape. Si l'erreur revient, ouvrez le panneau Expert "
      "pour lire les lignes techniques, puis préparez un rapport pour le forum.",
      "Run the same step again. If it happens again, open the Expert panel to "
      "read the technical lines, then prepare a report for the forum.")),

    ("mesh_first",
     r"mesh file must first be constructed",
     "orange",
     ("Le terrain de la tuile n'a pas encore été construit.",
      "The tile terrain has not been built yet."),
     ("L'étape 3 (images) a besoin du terrain fabriqué à l'étape 2.",
      "Step 3 (imagery) needs the terrain made in step 2."),
     ("Étape 2 non faite, ou ses fichiers ont été effacés.",
      "Step 2 not done, or its files were erased."),
     ("Lancez l'étape 1 puis l'étape 2, ou « Tout construire ».",
      "Run step 1 then step 2, or « Build all ».")),

    ("mesh_truncated",
     r"mesh (output )?file.*(truncated|tronqu)|r[ée]g[ée]n[ée]rez le mesh",
     "rouge",
     ("Le fichier de terrain de la tuile est abîmé.",
      "The tile terrain file is damaged."),
     ("Le fichier fabriqué à l'étape 2 est incomplet ; on ne peut pas "
      "continuer avec.",
      "The file made in step 2 is incomplete; the build cannot go on with it."),
     ("Étape 2 interrompue (arrêt, disque plein, plantage).",
      "Step 2 was interrupted (stop, full disk, crash)."),
     ("Refaites l'étape 2 de cette tuile.", "Redo step 2 for this tile.")),

    ("bathy_global_absent",
     r"Global Scenery DSF absent, bathymetry skipped",
     "jaune",
     ("La profondeur de l'eau n'a pas pu être lue dans X-Plane.",
      "Water depth could not be read from X-Plane."),
     ("Ortho4XP récupère normalement la profondeur de la mer dans les "
      "fichiers d'origine de X-Plane. Ici il ne les a pas trouvés : l'eau "
      "sera affichée avec une profondeur simplifiée.",
      "Ortho4XP normally reads sea depth from X-Plane's own files. They were "
      "not found: water will use a simplified depth."),
     ("Dossier X-Plane mal renseigné, ou tuile sans fichier d'origine.",
      "X-Plane folder not set correctly, or tile without an original file."),
     ("Vérifiez le dossier X-Plane dans la configuration, ou utilisez le "
      "module Bathymétrie (EMODnet) pour une profondeur réelle.",
      "Check the X-Plane folder in the configuration, or use the Bathymetry "
      "module (EMODnet) for real depth.")),

    ("bathy_dsf_other",
     r"(corrupted Global Scenery DSF|could not copy Global Scenery DSF|"
     r"7z decompression failed), bathymetry skipped",
     "jaune",
     ("La profondeur de l'eau d'origine X-Plane n'a pas pu être lue.",
      "X-Plane's original water depth could not be read."),
     ("Le fichier d'origine existe mais il est illisible.",
      "The original file exists but cannot be read."),
     ("Fichier X-Plane abîmé ou outil de décompression absent.",
      "Damaged X-Plane file or missing decompression tool."),
     ("Faites vérifier les fichiers de X-Plane par son installateur, ou "
      "utilisez le module Bathymétrie.",
      "Let the X-Plane installer check its files, or use the Bathymetry "
      "module.")),

    ("white_blocks",
     r"pure white block",
     "jaune",
     ("Des images contiennent des zones toutes blanches.",
      "Some images contain fully white areas."),
     ("Le serveur d'imagerie a renvoyé des morceaux blancs. Cela peut aussi "
      "être normal (neige, marais salants).",
      "The imagery server sent white pieces. It can also be normal (snow, "
      "salt flats)."),
     ("Source d'imagerie sans donnée à cet endroit, ou serveur saturé.",
      "Imagery source without data there, or overloaded server."),
     ("Regardez la tuile avec « Visualiser la tuile » ; si c'est un défaut, "
      "cochez l'image « à corriger » ou essayez une autre source.",
      "Look at the tile with « View tile »; if it is a defect, tick the image "
      "« to correct » or try another source.")),

    ("xplane_root",
     r"ce dossier est la racine X-Plane|This is the X-Plane root folder",
     "orange",
     ("Le dossier de destination choisi est la racine de X-Plane.",
      "The chosen destination folder is the X-Plane root."),
     ("Une tuile posée là serait invisible pour X-Plane. Ortho4XP a vidé le "
      "champ et range la tuile dans son propre dossier.",
      "A tile placed there would be invisible to X-Plane. Ortho4XP cleared the "
      "field and stores the tile in its own folder."),
     ("Mauvais dossier choisi.", "Wrong folder chosen."),
     ("Choisissez le sous-dossier « Custom Scenery » de X-Plane, ou laissez "
      "le champ vide.",
      "Choose X-Plane's « Custom Scenery » subfolder, or leave the field "
      "empty.")),

    ("apt_missing",
     r"\.apt is missing",
     "jaune",
     ("Le fichier des aéroports de la tuile est introuvable.",
      "The tile's airport file is missing."),
     ("Ortho4XP n'a pas pu vérifier la netteté renforcée autour des "
      "aéroports.",
      "Ortho4XP could not check the sharper imagery around airports."),
     ("Fichier effacé après l'étape 1.", "File erased after step 1."),
     ("Refaites l'étape 1 si vous voulez des aéroports plus nets.",
      "Redo step 1 if you want sharper airports.")),

    ("permission",
     r"Permission denied|Operation not permitted",
     "rouge",
     ("Ortho4XP n'a pas le droit d'écrire ou de lire dans un dossier.",
      "Ortho4XP is not allowed to write or read a folder."),
     ("Le système refuse l'accès à un dossier utilisé par Ortho4XP.",
      "The system refuses access to a folder used by Ortho4XP."),
     ("Dossier protégé (Bureau, Documents sous macOS), disque en lecture "
      "seule, ou chemin incomplet.",
      "Protected folder (Desktop, Documents on macOS), read-only disk, or "
      "incomplete path."),
     ("Choisissez un dossier hors Bureau/Documents, ou autorisez Ortho4XP "
      "dans Réglages > Confidentialité > Accès complet au disque (macOS).",
      "Choose a folder outside Desktop/Documents, or allow Ortho4XP in "
      "Settings > Privacy > Full Disk Access (macOS).")),

    ("here_key",
     r"HERE access key",
     "orange",
     ("La source d'imagerie HERE ne répond plus.",
      "The HERE imagery source no longer answers."),
     ("Le site HERE a changé et sa clé d'accès n'est plus lisible.",
      "The HERE website changed and its access key cannot be read."),
     ("Changement côté HERE, pas un défaut d'Ortho4XP.",
      "Change on HERE's side, not an Ortho4XP defect."),
     ("Choisissez une autre source d'imagerie (BI, Arc, GON...).",
      "Choose another imagery source (BI, Arc, GON...).")),

    ("no_data_value",
     r"does not advertise its no_data",
     "info",
     ("Fichier de relief sans valeur « vide » déclarée (normal).",
      "Elevation file without a declared « empty » value (normal)."),
     ("Ortho4XP a pris la valeur habituelle −32768. Rien à faire.",
      "Ortho4XP used the usual −32768 value. Nothing to do."),
     ("Format du fichier (fréquent pour Copernicus).",
      "File format (common for Copernicus)."),
     ("Aucune action nécessaire.", "No action needed.")),

    ("copernicus_seam",
     r"Copernicus GLO-30 (est une source|is a single)",
     "info",
     ("Relief Copernicus : petite jointure possible au bord des tuiles.",
      "Copernicus elevation: a small seam is possible at tile edges."),
     ("Copernicus fournit une dalle par tuile, sans marge de raccord.",
      "Copernicus provides one block per tile, without a joining margin."),
     ("Fonctionnement de la source.", "How the source works."),
     ("Aucune action, sauf si la jointure se voit : utilisez alors une "
      "autre source de relief.",
      "No action, unless the seam is visible: then use another elevation "
      "source.")),

    ("network",
     r"Network or server unreachable",
     "rouge",
     ("Pas de connexion au serveur.", "No connection to the server."),
     ("Ortho4XP n'arrive pas à joindre Internet ou le serveur demandé.",
      "Ortho4XP cannot reach the Internet or the requested server."),
     ("Pas d'Internet, pare-feu, ou serveur en panne.",
      "No Internet, firewall, or server down."),
     ("Vérifiez la connexion Internet puis relancez l'étape.",
      "Check the Internet connection then run the step again.")),

    ("server_retry",
     r"Server could not be connected, retrying",
     "info",
     ("Serveur momentanément injoignable : Ortho4XP a réessayé seul.",
      "Server briefly unreachable: Ortho4XP retried by itself."),
     ("Ortho4XP refait la demande automatiquement.",
      "Ortho4XP repeats the request automatically."),
     ("Serveur chargé ou connexion instable.",
      "Busy server or unstable connection."),
     ("Rien à faire si la construction s'est terminée.",
      "Nothing to do if the build finished.")),

    ("osm_failed",
     r"OSM query failed|overpass server answer was corrupted",
     "orange",
     ("Les données de cartes (routes, côtes, eau) n'ont pas pu être "
      "téléchargées.",
      "Map data (roads, coasts, water) could not be downloaded."),
     ("Le serveur OpenStreetMap n'a pas répondu correctement.",
      "The OpenStreetMap server did not answer correctly."),
     ("Serveur OSM saturé (fréquent aux heures chargées).",
      "OSM server overloaded (common at busy hours)."),
     ("Réessayez dans quelques minutes ; utilisez le cache OSM local (.pbf) "
      "pour ne plus en dépendre.",
      "Try again in a few minutes; use the local OSM cache (.pbf) to stop "
      "depending on it.")),

    ("coastline",
     r"ERROR (in|is) OSM coastline data",
     "orange",
     ("Le trait de côte OpenStreetMap est cassé sur cette tuile.",
      "The OpenStreetMap coastline is broken on this tile."),
     ("Une ligne de côte s'arrête net : Ortho4XP ne sait pas où est la mer.",
      "A coastline stops abruptly: Ortho4XP cannot tell where the sea is."),
     ("Erreur dans les données OpenStreetMap (pas dans Ortho4XP).",
      "Error in OpenStreetMap data (not in Ortho4XP)."),
     ("Réessayez plus tard (OSM est corrigé régulièrement), ou corrigez la "
      "côte avec JOSM.",
      "Try later (OSM is fixed regularly), or fix the coast with JOSM.")),

    ("dsf_inactive",
     r"Build had errors - DSF left inactive|could not rename DSF",
     "rouge",
     ("La tuile n'a pas été activée à cause d'erreurs.",
      "The tile was not activated because of errors."),
     ("Ortho4XP a préféré ne pas activer une tuile peut-être incomplète.",
      "Ortho4XP chose not to activate a possibly incomplete tile."),
     ("Une erreur plus haut dans le journal.", "An earlier error in the log."),
     ("Corrigez l'erreur précédente puis relancez l'étape 3.",
      "Fix the previous error then run step 3 again.")),

    ("texture_abort",
     r"Aborting build - texture conversion failed",
     "rouge",
     ("Conversion des textures impossible : construction arrêtée.",
      "Texture conversion impossible: build stopped."),
     ("Les images n'ont pas pu être transformées au format de X-Plane.",
      "Images could not be converted to X-Plane's format."),
     ("Outil de conversion absent ou bloqué, ou disque plein.",
      "Conversion tool missing or blocked, or full disk."),
     ("Vérifiez la place disque ; sous macOS autorisez les outils du dossier "
      "Utils ; puis relancez l'étape 3.",
      "Check disk space; on macOS allow the tools in the Utils folder; then "
      "run step 3 again.")),

    ("texture_convert",
     r"Could not convert texture",
     "orange",
     ("Certaines textures n'ont pas pu être converties.",
      "Some textures could not be converted."),
     ("Quelques images n'ont pas été transformées au format X-Plane.",
      "A few images were not converted to X-Plane's format."),
     ("Image abîmée, outil de conversion bloqué, ou disque plein.",
      "Damaged image, blocked conversion tool, or full disk."),
     ("Relancez l'étape 3 ; si cela persiste, effacez les images de la tuile "
      "et relancez.",
      "Run step 3 again; if it persists, erase the tile images and run "
      "again.")),

    ("save_ortho",
     r"could not save orthophoto on disk",
     "rouge",
     ("Les images téléchargées n'ont pas pu être enregistrées.",
      "Downloaded images could not be saved."),
     ("Ortho4XP n'arrive pas à écrire sur le disque.",
      "Ortho4XP cannot write to the disk."),
     ("Disque plein, débranché ou protégé en écriture.",
      "Full, unplugged or write-protected disk."),
     ("Libérez de la place ou choisissez un autre disque.",
      "Free up space or choose another disk.")),

    ("triangle_fail",
     r"Triangle4XP really couldn't make it|triangle crashed",
     "rouge",
     ("Le terrain de la tuile n'a pas pu être fabriqué.",
      "The tile terrain could not be made."),
     ("L'outil qui découpe le terrain en triangles a échoué.",
      "The tool that cuts the terrain into triangles failed."),
     ("Souvent des données de côte ou d'eau OSM bizarres.",
      "Often odd OSM coast or water data."),
     ("Refaites l'étape 1 puis l'étape 2 ; si cela persiste, préparez un "
      "rapport pour le forum.",
      "Redo step 1 then step 2; if it persists, prepare a report for the "
      "forum.")),

    ("triangle_quality",
     r"Triangle4XP could not achieve the requested quality",
     "jaune",
     ("Le terrain a été fabriqué avec une qualité un peu réduite.",
      "The terrain was made with slightly reduced quality."),
     ("L'outil a assoupli ses exigences pour réussir.",
      "The tool relaxed its requirements to succeed."),
     ("Zone difficile (côtes très découpées).",
      "Difficult area (very jagged coasts)."),
     ("En général rien à faire.", "Usually nothing to do.")),

    ("dem_cache",
     r"Cached raster elevation does not match",
     "orange",
     ("Le relief mis en cache ne correspond pas à la tuile.",
      "The cached elevation does not match the tile."),
     ("Un ancien fichier de relief gardé en mémoire disque ne convient pas.",
      "An old elevation file kept on disk does not fit."),
     ("Changement de source de relief depuis la dernière construction.",
      "Elevation source changed since the last build."),
     ("Effacez le cache de relief de la tuile puis relancez l'étape 1.",
      "Erase the tile elevation cache then run step 1 again.")),

    ("dem_source",
     r"Could not determine the appropriate (elevation )?source|"
     r"Unknown elevation source",
     "rouge",
     ("Ortho4XP ne sait pas quelle source de relief utiliser.",
      "Ortho4XP does not know which elevation source to use."),
     ("Le champ relief (custom_dem) contient une valeur non reconnue.",
      "The elevation field (custom_dem) contains an unknown value."),
     ("Réglage relief mal rempli.", "Elevation setting filled incorrectly."),
     ("Choisissez une source dans la liste du champ relief, ou videz-le.",
      "Choose a source from the elevation field list, or empty it.")),

    ("dem_read",
     r"in reading elevation from|could not be read\. Skipped",
     "rouge",
     ("Le fichier de relief est illisible.", "The elevation file is unreadable."),
     ("Sans relief, la tuile serait plate (altitude zéro).",
      "Without elevation the tile would be flat (altitude zero)."),
     ("Disque externe débranché, fichier déplacé ou abîmé.",
      "External disk unplugged, file moved or damaged."),
     ("Branchez le disque qui contient le relief, ou corrigez le chemin dans "
      "la configuration.",
      "Plug in the disk holding the elevation, or fix the path in the "
      "configuration.")),

    ("disk_space",
     r"place disque insuffisante|not enough disk space",
     "rouge",
     ("Pas assez de place sur le disque.", "Not enough disk space."),
     ("Ortho4XP a refusé de démarrer pour ne pas remplir le disque.",
      "Ortho4XP refused to start so as not to fill the disk."),
     ("Disque presque plein.", "Disk almost full."),
     ("Libérez de la place ou choisissez un autre disque.",
      "Free up space or choose another disk.")),

    ("mount_missing",
     r"disque externe ou un serveur n'est peut-etre pas branche|"
     r"external disk or a server is maybe not plugged|"
     r"Build refuse pour ne pas fabriquer une tuile plate",
     "rouge",
     ("Un disque ou un dossier utilisé n'est pas accessible.",
      "A disk or folder in use is not accessible."),
     ("Ortho4XP a refusé de construire une tuile plate ou mal rangée.",
      "Ortho4XP refused to build a flat or misplaced tile."),
     ("Disque externe ou serveur non branché.",
      "External disk or server not plugged in."),
     ("Branchez le disque indiqué dans le panneau Expert, puis relancez.",
      "Plug in the disk shown in the Expert panel, then run again.")),

    ("masks_width",
     r"masks_width .* invalide|masks_width .* invalid",
     "orange",
     ("Réglage de largeur des masques d'eau trop grand.",
      "Water mask width setting too large."),
     ("Ortho4XP a arrêté l'étape des masques avant de mal faire.",
      "Ortho4XP stopped the masks step before doing it wrong."),
     ("Valeur masks_width (en mètres) hors limites.",
      "masks_width value (in metres) out of range."),
     ("Remettez une valeur plus petite dans la configuration (en mètres).",
      "Put back a smaller value in the configuration (in metres).")),

    ("overlay_src",
     r"overlay source directory needs to be set|DSFTool crashed",
     "orange",
     ("Les routes et forêts X-Plane (overlay) n'ont pas pu être extraites.",
      "X-Plane roads and forests (overlay) could not be extracted."),
     ("L'étape overlay a besoin du dossier Global Scenery de X-Plane.",
      "The overlay step needs X-Plane's Global Scenery folder."),
     ("Dossier source overlay non renseigné ou outil DSFTool bloqué.",
      "Overlay source folder not set or DSFTool blocked."),
     ("Renseignez le dossier overlay (Global Scenery) dans la configuration.",
      "Set the overlay folder (Global Scenery) in the configuration.")),

    ("tile_dirs",
     r"Cannot create tile subdirectories|could not create destination directory",
     "rouge",
     ("Impossible de créer les dossiers de la tuile.",
      "Cannot create the tile folders."),
     ("Ortho4XP n'arrive pas à fabriquer son dossier de travail.",
      "Ortho4XP cannot create its working folder."),
     ("Disque plein, protégé, ou chemin invalide.",
      "Full or protected disk, or invalid path."),
     ("Choisissez un autre dossier de destination.",
      "Choose another destination folder.")),

    ("gdal",
     r"gdal not present|install Gdal|unsupported EPSG",
     "jaune",
     ("Un outil de géographie (GDAL) manque ou ne connaît pas une projection.",
      "A geography tool (GDAL) is missing or does not know a projection."),
     ("Certaines fonctions avancées (géoréférencement, projections rares) "
      "sont sautées.",
      "Some advanced features (georeferencing, rare projections) are "
      "skipped."),
     ("Installation incomplète des prérequis.",
      "Incomplete prerequisites installation."),
     ("Relancez l'installation des prérequis.",
      "Run the prerequisites installation again.")),

    ("custom_url",
     r"O4_Custom_URL\.py contains invalid code",
     "orange",
     ("Le fichier de sources personnelles contient une erreur.",
      "The personal sources file contains an error."),
     ("Ortho4XP l'a ignoré pour ne pas planter.",
      "Ortho4XP ignored it so as not to crash."),
     ("Fichier modifié à la main.", "File edited by hand."),
     ("Recréez la source avec « Créer / modifier un provider (.lay) ».",
      "Recreate the source with « Create / edit a provider (.lay) ».")),

    ("seatex_providers",
     r"\[SeaTex\].*initiali[sz]ation providers",
     "orange",
     ("La préparation de la mer n'a pas pu charger la source d'imagerie.",
      "Sea preparation could not load the imagery source."),
     ("Les retouches photo de la mer côtière ont été sautées pour cette "
      "tuile.",
      "Coastal sea photo touch-ups were skipped for this tile."),
     ("Source d'imagerie (provider ou .comb) introuvable ou incomplète, "
      "zone (extent) absente.",
      "Imagery source (provider or .comb) missing or incomplete, missing "
      "zone (extent)."),
     ("Vérifiez la source d'imagerie choisie dans la fenêtre principale, "
      "puis relancez l'étape 3.",
      "Check the imagery source chosen in the main window, then run step 3 "
      "again.")),

    ("traceback",
     r"^Traceback \(most recent call last\)",
     "rouge",
     ("Erreur interne du programme.", "Internal program error."),
     ("Une partie d'Ortho4XP a rencontré une erreur de programmation.",
      "A part of Ortho4XP hit a programming error."),
     ("Cas non prévu par le code.", "Case not handled by the code."),
     ("Préparez un rapport et joignez-le sur le forum.",
      "Prepare a report and attach it on the forum.")),
]

_COMPILED = None


def _compiled():
    global _COMPILED
    if _COMPILED is None:
        out = []
        for entry in _CATALOGUE:
            try:
                out.append((entry, re.compile(entry[1], re.IGNORECASE)))
            except re.error:
                pass
        _COMPILED = out
    return _COMPILED


# Repère écrit par O4_Log_Collector au démarrage de chaque session
_SESSION_MARK = "démarrage de la session"
# Préfixe horodaté du collecteur : « Fri Oct  2 10:00:00 2026 | »
_TS_RE = re.compile(r"^[A-Z][a-z]{2} [A-Z][a-z]{2} +\d{1,2} \d\d:\d\d:\d\d \d{4} \| ?")
# Un message ERROR/ERREUR générique non catalogué
_GENERIC_ERR = re.compile(r"\bERROR\b|\bERREUR\b")
# Une session « active » : une étape, un batch, une erreur ou un avertissement
_ACTIVITY = re.compile(r"Step \d|Batch|ERROR|ERREUR|WARNING|Traceback",
                       re.IGNORECASE)


def strip_timestamp(line):
    """PUR. Retire le préfixe horodaté du collecteur."""
    return _TS_RE.sub("", line.rstrip("\r\n"))


def split_sessions(lines):
    """PUR. Découpe la liste de lignes en sessions (repère du collecteur).
    Les lignes avant le premier repère forment une session à part."""
    sessions = [[]]
    for ln in lines:
        if _SESSION_MARK in ln:
            sessions.append([])
            continue
        sessions[-1].append(ln)
    return [s for s in sessions if s]


def classify_line(text):
    """PUR. Renvoie l'entrée de catalogue correspondante, ou None."""
    for entry, rx in _compiled():
        if rx.search(text):
            return entry
    return None


def analyze_lines(lines, max_raw=6):
    """PUR et testable. Analyse une liste de lignes de journal.
    Regroupe par type de message ; renvoie la liste des constats."""
    found = {}
    order = []
    unknown = {}
    for ln in lines:
        text = strip_timestamp(ln).strip()
        if not text:
            continue
        entry = classify_line(text)
        if entry is not None:
            fid = entry[0]
            if fid not in found:
                found[fid] = {"entry": entry, "count": 0, "raw": []}
                order.append(fid)
            f = found[fid]
            f["count"] += 1
            if len(f["raw"]) < max_raw:
                f["raw"].append(strip_timestamp(ln))
            continue
        if _GENERIC_ERR.search(text):
            key = re.sub(r"\d+", "N", text)[:160]
            u = unknown.setdefault(key, {"count": 0, "raw": []})
            u["count"] += 1
            if len(u["raw"]) < max_raw:
                u["raw"].append(strip_timestamp(ln))

    fr = _lang_code() == "fr"
    k = 0 if fr else 1
    results = []
    for fid in order:
        f = found[fid]
        e = f["entry"]
        results.append(_finding(
            e[2], "journal", e[3][k], e[4][k], e[5][k], e[6][k],
            count=f["count"], raw=f["raw"], fid=fid))
    for key, u in unknown.items():
        results.append(_finding(
            "orange", "journal",
            _L("Erreur technique non répertoriée.",
               "Unlisted technical error."),
            _L("Ce message n'est pas encore traduit en langage simple.",
               "This message is not yet translated into plain language."),
            _L("Voir la ligne technique dans le panneau Expert.",
               "See the technical line in the Expert panel."),
            _L("Si la construction a échoué, préparez un rapport pour le "
               "forum.",
               "If the build failed, prepare a report for the forum."),
            count=u["count"], raw=u["raw"], fid="unknown"))
    return results


def read_log_lines(path=None, max_bytes=40 * 1024 * 1024):
    """Lit le journal (lecture seule, utf-8 tolérant). Seuls les derniers
    max_bytes sont lus pour rester rapide sur un très gros journal."""
    path = path or _log_path()
    if not path or not os.path.isfile(path):
        return None
    try:
        size = os.path.getsize(path)
        with open(path, "rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
                f.readline()  # ligne coupée
            data = f.read()
        return data.decode("utf-8", errors="replace").splitlines()
    except Exception:
        return None


def analyze_log(path=None, sessions=1):
    """Analyse le journal. sessions=1 -> dernière session ; 0 -> tout."""
    lines = read_log_lines(path)
    if lines is None:
        return [_finding(
            "info", "journal",
            _L("Aucun journal trouvé pour l'instant.",
               "No log found yet."),
            _L("Le journal Ortho4XP.log apparaît après une première "
               "utilisation.",
               "The Ortho4XP.log file appears after a first use."),
            fid="no_log")]
    sess = split_sessions(lines)
    if sessions and sessions > 0:
        # Dernières sessions où il s'est passé quelque chose (étape lancée,
        # erreur, avertissement) : ouvrir puis refermer Ortho4XP ne doit pas
        # masquer la construction précédente.
        active = [s for s in sess if any(_ACTIVITY.search(ln) for ln in s)]
        sess = (active or sess)[-sessions:]
    flat = [ln for s in sess for ln in s]
    res = analyze_lines(flat)
    if not res:
        res = [_finding(
            "ok", "journal",
            _L("Aucun problème trouvé dans le journal.",
               "No problem found in the log."),
            _L("La période analysée ne contient aucune erreur connue.",
               "The analysed period contains no known error."),
            fid="log_ok")]
    return res


# ------------------------------------------------------------------------------
# CHAPITRE 2 — Contrôles de la machine
# ------------------------------------------------------------------------------
_FAT_TYPES = ("msdos", "vfat", "fat", "fat32", "fat16")
_EXFAT_TYPES = ("exfat",)


def fs_type_for(path, partitions=None):
    """Type de système de fichiers du disque qui contient path (ou "")."""
    try:
        if partitions is None:
            import psutil
            partitions = psutil.disk_partitions(all=True)
        p = os.path.abspath(path or os.path.expanduser("~"))
        if sys.platform.startswith("win"):
            p = p.lower()
        best, best_len = "", -1
        for part in partitions:
            mp = part.mountpoint
            cmp_mp = mp.lower() if sys.platform.startswith("win") else mp
            if p == cmp_mp or p.startswith(cmp_mp.rstrip("/\\") + os.sep) \
                    or cmp_mp in ("/",):
                if len(cmp_mp) > best_len:
                    best, best_len = (part.fstype or ""), len(cmp_mp)
        return best.lower()
    except Exception:
        return ""


def _existing_parent(path):
    p = path or ""
    while p and not os.path.isdir(p):
        parent = os.path.dirname(p)
        if parent == p:
            break
        p = parent
    return p if p and os.path.isdir(p) else ""


def disk_findings(label, path, free_go, fstype):
    """PUR. Constats pour un emplacement (place + format)."""
    out = []
    if free_go is not None:
        if free_go < 20:
            out.append(_finding(
                "rouge", "machine",
                _L("Très peu de place sur le disque : ", "Very little disk space: ")
                + label,
                _L("Il reste %.0f Go. Une tuile peut demander de 2 à plus de "
                   "20 Go." % free_go,
                   "%.0f GB left. A tile can need from 2 to over 20 GB."
                   % free_go),
                _L("Disque presque plein.", "Disk almost full."),
                _L("Libérez de la place ou choisissez un autre disque.",
                   "Free up space or choose another disk."),
                raw=[path], fid="disk_low"))
        elif free_go < 60:
            out.append(_finding(
                "jaune", "machine",
                _L("Place disque limitée : ", "Limited disk space: ") + label,
                _L("Il reste %.0f Go : suffisant pour quelques tuiles "
                   "seulement." % free_go,
                   "%.0f GB left: enough for a few tiles only." % free_go),
                "", _L("Prévoyez de la place avant un gros lot de tuiles.",
                       "Plan space before a large batch of tiles."),
                raw=[path], fid="disk_mid"))
    if fstype in _FAT_TYPES:
        out.append(_finding(
            "rouge", "machine",
            _L("Disque au format FAT32 : ", "FAT32 disk: ") + label,
            _L("Ce format refuse les fichiers de plus de 4 Go et les noms "
               "longs : la construction peut échouer.",
               "This format refuses files over 4 GB and long names: the build "
               "may fail."),
            _L("Disque formaté pour Windows ancien / clés USB.",
               "Disk formatted for old Windows / USB sticks."),
            _L("Utilisez un disque au format APFS (Mac), NTFS (Windows) ou "
               "ext4 (Linux).",
               "Use an APFS (Mac), NTFS (Windows) or ext4 (Linux) disk."),
            raw=[path, fstype], fid="fs_fat"))
    elif fstype in _EXFAT_TYPES:
        out.append(_finding(
            "orange", "machine",
            _L("Disque au format exFAT : ", "exFAT disk: ") + label,
            _L("Ça fonctionne, mais lentement avec des milliers d'images, et "
               "macOS y ajoute des fichiers cachés « ._ ».",
               "It works, but slowly with thousands of images, and macOS adds "
               "hidden « ._ » files."),
            _L("Disque formaté pour être partagé Mac/Windows.",
               "Disk formatted to be shared Mac/Windows."),
            _L("Si possible, utilisez un disque APFS (Mac), NTFS (Windows) ou "
               "ext4 (Linux).",
               "If possible, use an APFS (Mac), NTFS (Windows) or ext4 (Linux) "
               "disk."),
            raw=[path, fstype], fid="fs_exfat"))
    return out


def ram_findings(total_go, avail_go):
    """PUR. Constats mémoire."""
    out = []
    if total_go is None:
        return out
    if total_go < 16:
        out.append(_finding(
            "orange", "machine",
            _L("Mémoire vive faible (%.0f Go)." % total_go,
               "Low memory (%.0f GB)." % total_go),
            _L("Ortho4XP et X-Plane aiment la mémoire. Avec moins de 16 Go, "
               "préférez la qualité « Rapide » ou « Équilibrée ».",
               "Ortho4XP and X-Plane like memory. With less than 16 GB, prefer "
               "the « Fast » or « Balanced » quality."),
            "", _L("Fermez les autres programmes pendant une construction.",
                   "Close other programs during a build."),
            raw=["total=%.1f Go" % total_go], fid="ram_low"))
    elif total_go < 32:
        out.append(_finding(
            "info", "machine",
            _L("Mémoire vive : %.0f Go." % total_go,
               "Memory: %.0f GB." % total_go),
            _L("Suffisant. En très haute netteté (ZL19 et plus), X-Plane peut "
               "saccader sous 32 Go.",
               "Enough. At very high sharpness (ZL19 and above), X-Plane may "
               "stutter under 32 GB."),
            raw=["total=%.1f Go" % total_go], fid="ram_info"))
    if avail_go is not None and avail_go < 3:
        out.append(_finding(
            "jaune", "machine",
            _L("Peu de mémoire libre en ce moment (%.1f Go)." % avail_go,
               "Little free memory right now (%.1f GB)." % avail_go),
            _L("D'autres programmes occupent la mémoire.",
               "Other programs are using memory."),
            "", _L("Fermez les programmes inutiles avant de construire.",
                   "Close unneeded programs before building."),
            raw=["disponible=%.1f Go" % avail_go], fid="ram_busy"))
    return out


def _utils_os_dir():
    if sys.platform.startswith("dar"):
        return "mac"
    if sys.platform.startswith("win"):
        return "win"
    return "lin"


def tools_findings(root=None):
    """Présence des outils indispensables dans Utils/<os>/ et de la carte."""
    out = []
    root = root or _root_dir()
    d = os.path.join(root, "Utils", _utils_os_dir())
    exe = ".exe" if sys.platform.startswith("win") else ""
    missing = []
    for name in ("Triangle4XP", "DSFTool", "nvcompress"):
        if not os.path.isfile(os.path.join(d, name + exe)):
            missing.append(name + exe)
    if missing:
        out.append(_finding(
            "rouge", "machine",
            _L("Outils de construction manquants.", "Build tools missing."),
            _L("Sans eux, Ortho4XP ne peut pas fabriquer le terrain ou les "
               "textures.",
               "Without them, Ortho4XP cannot make the terrain or textures."),
            _L("Installation incomplète ou antivirus qui les a retirés.",
               "Incomplete installation or antivirus removed them."),
            _L("Réinstallez Ortho4XP V3 depuis la page GitHub.",
               "Reinstall Ortho4XP V3 from the GitHub page."),
            raw=[os.path.join(d, m) for m in missing], fid="tools"))
    earth = os.path.join(root, "Utils", "Earth")
    try:
        n = len([f for f in os.listdir(earth) if f.endswith(".jpg")])
    except Exception:
        n = 0
    if n < 64:
        out.append(_finding(
            "jaune", "machine",
            _L("Carte du monde incomplète.", "World map incomplete."),
            _L("La carte de sélection des tuiles s'affichera en gris par "
               "endroits.",
               "The tile selection map will be grey in places."),
            "", _L("Réinstallez le dossier Utils/Earth.",
                   "Reinstall the Utils/Earth folder."),
            raw=[earth, "%d/64" % n], fid="earth"))
    return out


def windows_findings():
    if not sys.platform.startswith("win"):
        return []
    return [_finding(
        "info", "machine",
        _L("Conseil Windows : exclure Ortho4XP de l'antivirus.",
           "Windows tip: exclude Ortho4XP from the antivirus."),
        _L("Microsoft Defender analyse chacune des milliers d'images écrites, "
           "ce qui ralentit beaucoup la construction.",
           "Microsoft Defender scans each of the thousands of images written, "
           "which slows the build a lot."),
        "",
        _L("Ajoutez le dossier d'Ortho4XP (et celui des tuiles) aux "
           "exclusions de Microsoft Defender, et retirez-le de l'indexation "
           "de la recherche Windows.",
           "Add the Ortho4XP folder (and the tiles folder) to Microsoft "
           "Defender exclusions, and remove it from Windows Search indexing."),
        fid="defender")]


def _configured_locations():
    """Emplacements à contrôler : dossier Ortho4XP + dossier des tuiles."""
    locs = [(_L("dossier Ortho4XP", "Ortho4XP folder"), _root_dir())]
    try:
        import O4_Config_Utils as CFG
        cbd = getattr(CFG, "custom_build_dir", "") or ""
    except Exception:
        cbd = ""
    try:
        import O4_UI_Utils as UI
        g = getattr(UI, "gui", None)
        if g is not None and hasattr(g, "custom_build_dir"):
            cbd = g.custom_build_dir.get() or cbd
    except Exception:
        pass
    if cbd:
        locs.append((_L("dossier des tuiles", "tiles folder"), cbd))
    return locs


def check_machine():
    out = []
    seen = set()
    for label, path in _configured_locations():
        p = _existing_parent(path)
        if not p:
            continue
        try:
            dev = os.stat(p).st_dev
        except Exception:
            dev = p
        if dev in seen:
            continue
        seen.add(dev)
        try:
            import shutil
            free = shutil.disk_usage(p).free / (1024.0 ** 3)
        except Exception:
            free = None
        out.extend(disk_findings(label, p, free, fs_type_for(p)))
    try:
        import psutil
        vm = psutil.virtual_memory()
        out.extend(ram_findings(vm.total / 1024.0 ** 3,
                                vm.available / 1024.0 ** 3))
    except Exception:
        pass
    out.extend(tools_findings())
    out.extend(windows_findings())
    if not out:
        out.append(_finding(
            "ok", "machine",
            _L("Machine prête : place, disque et mémoire corrects.",
               "Machine ready: space, disk and memory OK."), fid="machine_ok"))
    return out


# ------------------------------------------------------------------------------
# CHAPITRE 3 — Scènes X-Plane (scenery_packs.ini, LECTURE SEULE)
# ------------------------------------------------------------------------------
_KW_ON = "SCENERY_PACK "
_KW_OFF = "SCENERY_PACK_DISABLED "
_TILE_RE = re.compile(r"zOrtho4XP_([+-]\d{2})([+-]\d{3})")


def parse_packs(text):
    """PUR. [{index, enabled, path, low}] dans l'ordre du fichier."""
    out = []
    for i, raw in enumerate(text.splitlines()):
        s = raw.strip()
        if s.startswith(_KW_OFF):
            out.append({"index": i, "enabled": False,
                        "path": s[len(_KW_OFF):].strip()})
        elif s.startswith(_KW_ON):
            out.append({"index": i, "enabled": True,
                        "path": s[len(_KW_ON):].strip()})
    for e in out:
        e["low"] = e["path"].lower()
    return out


def _kind(low):
    name = low.rstrip("/\\").replace("\\", "/").split("/")[-1]
    if "zortho4xp_" in name:
        return "o4x_tile"
    if "yortho4xp_overlay" in name or name.startswith("yortho4xp"):
        return "o4x_overlay"
    if "simheaven" in name:
        return "simheaven"
    if name.startswith("z_autoortho") or name.startswith("z_ao_") \
            or "autoortho" in name:
        return "autoortho"
    if "osxp_live" in name:
        return "osxp"
    if "global_airports" in name or "global airports" in name:
        return "airports"
    return "other"


def scenery_findings(text, exists_fn=None):
    """PUR (exists_fn injectable pour les tests). Constats sur l'ordre et les
    conflits des scènes. Ne modifie rien."""
    packs = parse_packs(text)
    out = []
    enabled = [p for p in packs if p["enabled"]]
    for p in packs:
        p["kind"] = _kind(p["low"])

    # 1) doublons d'une même tuile Ortho4XP activée deux fois
    by_tile = {}
    for p in enabled:
        if p["kind"] == "o4x_tile":
            m = _TILE_RE.search(p["path"])
            if m:
                by_tile.setdefault(m.group(1) + m.group(2), []).append(p)
    dups = {k: v for k, v in by_tile.items() if len(v) > 1}
    if dups:
        raw = []
        for k, v in sorted(dups.items()):
            raw.extend(x["path"] for x in v)
        out.append(_finding(
            "orange", "scenes",
            _L("Une même tuile est activée plusieurs fois dans X-Plane : ",
               "The same tile is enabled several times in X-Plane: ")
            + ", ".join(sorted(dups)),
            _L("X-Plane n'affiche que la première ; les autres occupent la "
               "mémoire pour rien.",
               "X-Plane only shows the first; the others waste memory."),
            _L("Ancienne et nouvelle version de la tuile toutes deux "
               "installées.",
               "Old and new versions of the tile both installed."),
            _L("Gardez une seule version (Bibliothèque de tuiles → Retirer).",
               "Keep one version only (Tile library → Remove)."),
            count=len(dups), raw=raw, fid="dup_tiles"))

    # 2) ortho au-dessus d'un overlay / aéroports / SimHeaven
    first_ortho = None
    for p in enabled:
        if p["kind"] in ("o4x_tile", "autoortho", "osxp"):
            first_ortho = p
            break
    if first_ortho is not None:
        below = [p for p in enabled
                 if p["index"] > first_ortho["index"]
                 and p["kind"] in ("simheaven", "o4x_overlay", "airports")]
        if below:
            out.append(_finding(
                "orange", "scenes",
                _L("Des tuiles photo sont placées au-dessus de scènes qui "
                   "doivent passer devant.",
                   "Photo tiles are placed above sceneries that must come "
                   "first."),
                _L("Les routes, forêts, bâtiments ou aéroports listés plus bas "
                   "risquent d'être cachés par la photo.",
                   "Roads, forests, buildings or airports listed lower may be "
                   "hidden by the photo."),
                _L("Ordre du fichier scenery_packs.ini.",
                   "Order of the scenery_packs.ini file."),
                _L("Dans scenery_packs.ini, les tuiles zOrtho4XP doivent être "
                   "tout en bas, sous les overlays, SimHeaven et Global "
                   "Airports.",
                   "In scenery_packs.ini, zOrtho4XP tiles must be at the very "
                   "bottom, below overlays, SimHeaven and Global Airports."),
                count=len(below),
                raw=[first_ortho["path"]] + [p["path"] for p in below[:5]],
                fid="order"))

    # 3) deux programmes d'ortho actifs en même temps
    has_o4x = any(p["kind"] == "o4x_tile" for p in enabled)
    others = sorted({p["kind"] for p in enabled
                     if p["kind"] in ("autoortho", "osxp")})
    if has_o4x and others:
        names = {"autoortho": "AutoOrtho", "osxp": "OrthoStudio Live"}
        out.append(_finding(
            "jaune", "scenes",
            _L("Plusieurs programmes de photos sont actifs : Ortho4XP + ",
               "Several photo programs are active: Ortho4XP + ")
            + ", ".join(names[o] for o in others),
            _L("Là où ils se recouvrent, X-Plane prend celui qui est le plus "
               "haut dans la liste.",
               "Where they overlap, X-Plane uses the one highest in the list."),
            "", _L("C'est possible, mais vérifiez qu'ils ne couvrent pas les "
                   "mêmes tuiles.",
                   "It is possible, but check they do not cover the same "
                   "tiles."),
            raw=[p["path"] for p in enabled
                 if p["kind"] in ("autoortho", "osxp")][:6],
            fid="multi_ortho"))

    # 4) overlay Ortho4XP + SimHeaven
    if any(p["kind"] == "o4x_overlay" for p in enabled) and \
            any(p["kind"] == "simheaven" for p in enabled):
        out.append(_finding(
            "jaune", "scenes",
            _L("Overlay Ortho4XP et SimHeaven activés ensemble.",
               "Ortho4XP overlay and SimHeaven enabled together."),
            _L("Les deux ajoutent des routes et des forêts : risque de "
               "doublons.",
               "Both add roads and forests: risk of duplicates."),
            "", _L("Si vous utilisez SimHeaven, désactivez yOrtho4XP_Overlays.",
                   "If you use SimHeaven, disable yOrtho4XP_Overlays."),
            fid="ovl_simheaven"))

    # 5) dossiers listés mais absents du disque
    if exists_fn is not None:
        missing = [p["path"] for p in enabled
                   if p["kind"] in ("o4x_tile", "o4x_overlay")
                   and not exists_fn(p["path"])]
        if missing:
            out.append(_finding(
                "jaune", "scenes",
                _L("Des tuiles listées dans X-Plane n'existent plus sur le "
                   "disque.",
                   "Tiles listed in X-Plane no longer exist on disk."),
                _L("X-Plane les ignore, mais cela peut cacher un disque "
                   "débranché.",
                   "X-Plane ignores them, but it can hide an unplugged disk."),
                _L("Dossier supprimé ou disque externe absent.",
                   "Folder deleted or external disk absent."),
                _L("Branchez le disque, ou retirez la ligne (Bibliothèque de "
                   "tuiles).",
                   "Plug in the disk, or remove the line (Tile library)."),
                count=len(missing), raw=missing[:8], fid="missing_dirs"))
    return out


def _guess_ini():
    try:
        import O4_Tile_Library_Utils as TL
        return TL.guess_ini_path()
    except Exception:
        return ""


def check_scenery(ini_path=None):
    ini = ini_path or _guess_ini()
    if not ini or not os.path.isfile(ini):
        return [_finding(
            "info", "scenes",
            _L("Fichier des scènes X-Plane non trouvé.",
               "X-Plane scenery file not found."),
            _L("Indiquez scenery_packs.ini une fois dans la Bibliothèque de "
               "tuiles : le diagnostic le retrouvera ensuite.",
               "Set scenery_packs.ini once in the Tile library: the diagnostic "
               "will find it afterwards."), fid="no_ini")]
    try:
        with open(ini, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as e:
        return [_finding("jaune", "scenes",
                         _L("Fichier des scènes illisible.",
                            "Scenery file unreadable."), raw=[ini, str(e)],
                         fid="ini_read")]
    cs_dir = os.path.dirname(ini)
    xp_root = os.path.dirname(cs_dir)

    def _exists(pack_path):
        p = pack_path.replace("\\", "/")
        cand = p if os.path.isabs(p) else os.path.join(xp_root, p)
        return os.path.exists(cand.rstrip("/"))

    res = scenery_findings(text, exists_fn=_exists)
    if not res:
        res = [_finding("ok", "scenes",
                        _L("Ordre des scènes X-Plane correct.",
                           "X-Plane scenery order OK."), raw=[ini],
                        fid="scenes_ok")]
    return res


# ------------------------------------------------------------------------------
# CHAPITRE 3 bis — Réglages graphiques de X-Plane (X-Plane.prf, LECTURE SEULE)
# Clé lue dans le VRAI fichier de X-Plane 12 : « renopt_tex_res_04 N ».
# Le suffixe _04 désigne un curseur de 0 à 4 (même convention que
# renopt_shadow_quality_04, renopt_draw_distance04…) : 4 = Maximum.
# ------------------------------------------------------------------------------
TEX_KEY = "renopt_tex_res_04"
TEX_KEY_VR = "vr_renopt_tex_res_04"
TEX_MAX = 4


def xplane_roots():
    """Racines X-Plane possibles, sans chemin en dur : déduites de
    scenery_packs.ini (Bibliothèque de tuiles) et du dossier overlay."""
    out = []
    ini = _guess_ini()
    if ini:
        out.append(os.path.dirname(os.path.dirname(ini)))
    for modname in ("O4_Overlay_Utils", "O4_Config_Utils"):
        try:
            mod = __import__(modname)
            src = getattr(mod, "custom_overlay_src", "") or ""
            if src:
                out.append(os.path.dirname(os.path.dirname(
                    os.path.abspath(src.rstrip("/\\")))))
        except Exception:
            pass
    res = []
    for p in out:
        if p and p not in res and os.path.isdir(p):
            res.append(p)
    return res


def find_prefs_file(roots=None):
    for root in (roots if roots is not None else xplane_roots()):
        p = os.path.join(root, "Output", "preferences", "X-Plane.prf")
        if os.path.isfile(p):
            return p
    return ""


def prf_value(text, key):
    """PUR. Valeur entière d'une clé de X-Plane.prf, ou None."""
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) >= 2 and parts[0] == key:
            try:
                return int(float(parts[1]))
            except ValueError:
                return None
    return None


def texture_findings(level, vr_level=None):
    """PUR. Constat si la qualité des textures de X-Plane n'est pas au
    maximum : les tuiles nettes (ZL17 et plus) seraient alors affichées
    moins nettes que ce qu'Ortho4XP a construit."""
    out = []
    if level is not None and level < TEX_MAX:
        out.append(_finding(
            "orange", "xplane",
            _L("La qualité des textures de X-Plane n'est pas au maximum "
               "(niveau %d sur %d)." % (level, TEX_MAX),
               "X-Plane texture quality is not at maximum (level %d of %d)."
               % (level, TEX_MAX)),
            _L("X-Plane réduit alors les photos : une tuile construite en "
               "haute netteté (ZL17 et plus) s'affiche moins nette, pour une "
               "construction plus longue et plus lourde.",
               "X-Plane then shrinks the photos: a tile built at high "
               "sharpness (ZL17 and above) looks less sharp, for a longer and "
               "heavier build."),
            _L("Réglage graphique de X-Plane.", "X-Plane graphics setting."),
            _L("Dans X-Plane : Réglages → Graphismes → Qualité des textures = "
               "Maximum. Sinon, choisissez la qualité « Rapide » dans "
               "Ortho4XP.",
               "In X-Plane: Settings → Graphics → Texture quality = Maximum. "
               "Otherwise, choose the « Fast » quality in Ortho4XP."),
            raw=["%s %d" % (TEX_KEY, level)], fid="xp_tex"))
    if vr_level is not None and vr_level < TEX_MAX and \
            (level is None or level >= TEX_MAX):
        out.append(_finding(
            "info", "xplane",
            _L("En réalité virtuelle, la qualité des textures n'est pas au "
               "maximum (niveau %d sur %d)." % (vr_level, TEX_MAX),
               "In VR, texture quality is not at maximum (level %d of %d)."
               % (vr_level, TEX_MAX)),
            _L("Seulement si vous volez avec un casque VR.",
               "Only if you fly with a VR headset."),
            raw=["%s %d" % (TEX_KEY_VR, vr_level)], fid="xp_tex_vr"))
    return out


def xplane_texture_level(prf_path=None):
    """Niveau de qualité des textures (0-4) ou None si inconnu."""
    p = prf_path or find_prefs_file()
    if not p:
        return None
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            return prf_value(f.read(), TEX_KEY)
    except Exception:
        return None


def check_xplane(prf_path=None):
    p = prf_path or find_prefs_file()
    if not p:
        return [_finding(
            "info", "xplane",
            _L("Réglages de X-Plane non trouvés.",
               "X-Plane settings not found."),
            _L("Indiquez une fois le fichier scenery_packs.ini dans la "
               "Bibliothèque de tuiles : le diagnostic retrouvera X-Plane.",
               "Set scenery_packs.ini once in the Tile library: the "
               "diagnostic will find X-Plane."), fid="no_prf")]
    try:
        with open(p, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception as e:
        return [_finding("info", "xplane",
                         _L("Réglages de X-Plane illisibles.",
                            "X-Plane settings unreadable."),
                         raw=[p, str(e)], fid="prf_read")]
    res = texture_findings(prf_value(text, TEX_KEY),
                           prf_value(text, TEX_KEY_VR))
    if not res:
        res = [_finding("ok", "xplane",
                        _L("Qualité des textures de X-Plane : maximum.",
                           "X-Plane texture quality: maximum."),
                        raw=[p], fid="xp_ok")]
    return res


# ------------------------------------------------------------------------------
# Synthèse
# ------------------------------------------------------------------------------
def sort_findings(findings):
    return sorted(findings, key=lambda f: (SEV_ORDER.get(f["sev"], 9),
                                           f.get("source", "")))


def run_all(log_sessions=1, ini_path=None):
    out = []
    for fn, args in ((analyze_log, (None, log_sessions)),
                     (check_machine, ()),
                     (check_scenery, (ini_path,)),
                     (check_xplane, ())):
        try:
            out.extend(fn(*args))
        except Exception as e:
            out.append(_finding("info", "machine",
                                _L("Une vérification n'a pas pu se faire.",
                                   "A check could not run."),
                                raw=[getattr(fn, "__name__", "?"), str(e)],
                                fid="internal"))
    return sort_findings(out)


def summary_counts(findings):
    c = {}
    for f in findings:
        c[f["sev"]] = c.get(f["sev"], 0) + 1
    return c


def format_text(findings, with_raw=True):
    """Texte lisible (console, rapport)."""
    src_name = {"journal": _L("Journal", "Log"),
                "machine": _L("Machine", "Machine"),
                "scenes": _L("Scènes X-Plane", "X-Plane sceneries"),
                "xplane": "X-Plane"}
    lines = [_L("DIAGNOSTIC ORTHO4XP V3", "ORTHO4XP V3 DIAGNOSTIC"),
             time.strftime("%Y-%m-%d %H:%M:%S"), ""]
    for f in findings:
        head = "%s [%s] %s" % (SEV_ICON.get(f["sev"], "-"),
                               src_name.get(f["source"], f["source"]),
                               f["title"])
        if f.get("count", 1) > 1:
            head += "  (x%d)" % f["count"]
        lines.append(head)
        for lab, key in ((_L("Explication", "Explanation"), "explain"),
                         (_L("Cause probable", "Likely cause"), "cause"),
                         (_L("Solution", "Solution"), "solution")):
            if f.get(key):
                lines.append("    %s : %s" % (lab, f[key]))
        if with_raw and f.get("raw"):
            for r in f["raw"]:
                lines.append("      | " + str(r))
        lines.append("")
    return "\n".join(lines)


# ------------------------------------------------------------------------------
# Rapport ZIP pour le forum (seule écriture du module, à la demande)
# ------------------------------------------------------------------------------
def _last_sessions_text(n=3):
    lines = read_log_lines()
    if not lines:
        return ""
    sess = split_sessions(lines)[-n:]
    return "\n".join(ln for s in sess for ln in s)


def _machine_text():
    import platform
    t = ["platform=" + platform.platform(),
         "python=" + sys.version.split()[0],
         "machine=" + platform.machine()]
    try:
        import O4_Version as V
        t.append("ortho4xp=" + str(getattr(V, "version", "?")))
    except Exception:
        pass
    try:
        import psutil
        t.append("ram_go=%.1f" % (psutil.virtual_memory().total / 1024.0 ** 3))
    except Exception:
        pass
    return "\n".join(t)


def make_report_zip(findings=None, dest_dir=None):
    """Crée un ZIP : diagnostic + 3 dernières sessions du journal + config
    générale + infos machine. Ne contient AUCUN fichier .lay (pas de clé).
    Renvoie (ok, chemin_ou_message)."""
    try:
        import zipfile
        root = _root_dir()
        dest_dir = dest_dir or os.path.join(root, "Rapports")
        os.makedirs(dest_dir, exist_ok=True)
        name = "Ortho4XP_rapport_" + time.strftime("%Y%m%d_%H%M%S") + ".zip"
        path = os.path.join(dest_dir, name)
        if findings is None:
            findings = run_all()
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("diagnostic.txt", format_text(findings))
            z.writestr("journal_dernieres_sessions.txt", _last_sessions_text())
            z.writestr("machine.txt", _machine_text())
            cfg = os.path.join(root, "Ortho4XP.cfg")
            if os.path.isfile(cfg):
                z.write(cfg, "Ortho4XP.cfg")
        return (True, path)
    except Exception as e:
        return (False, str(e))


# ------------------------------------------------------------------------------
# CHAPITRE 4 — Fenêtre « Diagnostic ». Point d'entrée : run_diagnostics(parent)
# Import tkinter LOCAL (le module reste importable sans interface).
# ------------------------------------------------------------------------------
def run_diagnostics(parent=None):
    import tkinter as tk
    from tkinter import messagebox

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
    FONT_B = ("Helvetica", 14, "bold") if IS_MAC else ("Segoe UI", 11, "bold")
    MONO = ("Menlo", 11) if IS_MAC else ("Consolas", 9)
    SEV_COL = {"rouge": "#ff6b6b", "orange": "#ffa94d", "jaune": "#ffe066",
               "info": "#74c0fc", "ok": "#8ce99a"}

    root_ref = parent
    if root_ref is None:
        try:
            root_ref = tk._default_root
        except Exception:
            root_ref = None
    win = tk.Toplevel(root_ref) if root_ref else tk.Tk()
    win.title(_L("Diagnostic — Ortho4XP V3", "Diagnostic — Ortho4XP V3"))
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

    state = {"findings": [], "sessions": 1}

    # --- haut : résumé + choix de période ---
    top = tk.Frame(win, bg=BG)
    top.pack(fill=tk.X, padx=12, pady=(12, 4))
    summary = tk.Label(top, text="", bg=BG, fg=FG, font=FONT_B, anchor="w",
                       justify="left")
    summary.pack(side=tk.LEFT, fill=tk.X, expand=True)
    sess_var = tk.IntVar(value=1)
    opt = tk.Frame(win, bg=BG)
    opt.pack(fill=tk.X, padx=12, pady=(0, 4))
    tk.Label(opt, text=_L("Journal analysé :", "Log analysed:"), bg=BG, fg=FG,
             font=FONT).pack(side=tk.LEFT)
    for val, txt in ((1, _L("dernière session", "last session")),
                     (0, _L("tout le journal", "whole log"))):
        tk.Radiobutton(opt, text=txt, variable=sess_var, value=val, bg=BG,
                       fg=FG, selectcolor=BG, activebackground=BG,
                       activeforeground=FG, highlightthickness=0, font=FONT,
                       command=lambda: _refresh()).pack(side=tk.LEFT, padx=6)

    # --- milieu : liste des constats (texte défilant, lecture seule) ---
    mid = tk.Frame(win, bg=BG)
    mid.pack(fill=tk.BOTH, expand=True, padx=12, pady=4)
    sb = tk.Scrollbar(mid)
    sb.pack(side=tk.RIGHT, fill=tk.Y)
    txt = tk.Text(mid, wrap="word", bg="#05140a", fg=FG, font=FONT,
                  yscrollcommand=sb.set, relief="flat", padx=10, pady=8,
                  height=18, highlightthickness=0)
    txt.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
    sb.config(command=txt.yview)
    for sev, col in SEV_COL.items():
        txt.tag_configure("t_" + sev, foreground=col, font=FONT_B)
    txt.tag_configure("lab", foreground=FG2)
    txt.tag_configure("raw", foreground="#9aa5a0", font=MONO)

    expert_var = tk.BooleanVar(value=False)

    def _render():
        txt.config(state="normal")
        txt.delete("1.0", tk.END)
        src_name = {"journal": _L("Journal", "Log"),
                    "machine": _L("Machine", "Machine"),
                    "scenes": _L("Scènes X-Plane", "X-Plane sceneries"),
                    "xplane": "X-Plane"}
        for f in state["findings"]:
            head = "%s  %s — %s" % (SEV_ICON.get(f["sev"], "-"),
                                    sev_label(f["sev"]), f["title"])
            if f.get("count", 1) > 1:
                head += "  (x%d)" % f["count"]
            txt.insert(tk.END, head + "\n", "t_" + f["sev"])
            txt.insert(tk.END, "   [" + src_name.get(f["source"], "") + "]\n",
                       "lab")
            for lab, key in ((_L("Explication", "Explanation"), "explain"),
                             (_L("Cause probable", "Likely cause"), "cause"),
                             (_L("Que faire", "What to do"), "solution")):
                if f.get(key):
                    txt.insert(tk.END, "   " + lab + " : ", "lab")
                    txt.insert(tk.END, f[key] + "\n")
            if expert_var.get() and f.get("raw"):
                for r in f["raw"]:
                    txt.insert(tk.END, "      | " + str(r) + "\n", "raw")
            txt.insert(tk.END, "\n")
        txt.config(state="disabled")
        c = summary_counts(state["findings"])
        parts = []
        for sev in ("rouge", "orange", "jaune"):
            if c.get(sev):
                parts.append("%s %d %s" % (SEV_ICON[sev], c[sev],
                                           sev_label(sev).lower()))
        summary.config(text=(" · ".join(parts) if parts else
                             SEV_ICON["ok"] + " " +
                             _L("Aucun problème important.",
                                "No important problem.")))

    def _refresh():
        summary.config(text=_L("Analyse en cours…", "Analysing…"))
        win.update_idletasks()
        try:
            state["findings"] = run_all(log_sessions=sess_var.get())
        except Exception as e:
            state["findings"] = [_finding("info", "machine",
                                          _L("Diagnostic impossible.",
                                             "Diagnostic impossible."),
                                          raw=[str(e)])]
        _render()

    def _report():
        ok, res = make_report_zip(state["findings"])
        if ok:
            messagebox.showinfo(
                _L("Rapport prêt", "Report ready"),
                _L("Rapport créé :\n", "Report created:\n") + res + "\n\n"
                + _L("Joignez ce fichier à votre message sur le forum.",
                     "Attach this file to your forum message."), parent=win)
            _open_folder(os.path.dirname(res))
        else:
            messagebox.showerror(_L("Rapport", "Report"),
                                 _L("Rapport impossible : ",
                                    "Report impossible: ") + res, parent=win)

    def _open_log():
        p = _log_path()
        if os.path.isfile(p):
            _open_path(p)

    # --- bas : boutons ---
    bot = tk.Frame(win, bg=BG)
    bot.pack(fill=tk.X, padx=12, pady=(4, 12))
    _btn(bot, _L("🔄 Relancer l'analyse", "🔄 Run again"),
         _refresh).pack(side=tk.LEFT, padx=(0, 6))
    _btn(bot, _L("📦 Préparer un rapport", "📦 Prepare a report"),
         _report).pack(side=tk.LEFT, padx=6)
    _btn(bot, _L("📄 Ouvrir le journal", "📄 Open the log"),
         _open_log).pack(side=tk.LEFT, padx=6)
    tk.Checkbutton(bot, text=_L("Panneau Expert (lignes techniques)",
                                "Expert panel (technical lines)"),
                   variable=expert_var, command=_render, bg=BG, fg=FG,
                   selectcolor=BG, activebackground=BG, activeforeground=FG,
                   highlightthickness=0, font=FONT).pack(side=tk.RIGHT)

    # Taille plafonnée à l'écran réel (règle Bible)
    try:
        w = min(900, int(win.winfo_screenwidth() * 0.95))
        h = min(700, int(win.winfo_screenheight() * 0.90))
        win.geometry("%dx%d" % (w, h))
        win.minsize(min(520, w), min(380, h))
    except Exception:
        pass
    win.lift()
    try:
        win.focus_force()
    except Exception:
        pass
    win.after(50, _refresh)
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


def _open_folder(d):
    _open_path(d)


if __name__ == "__main__":
    # Usage console : python O4_Diagnostics_Utils.py  -> texte du diagnostic
    print(format_text(run_all()))
