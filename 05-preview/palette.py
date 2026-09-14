#!/usr/bin/env python3
"""Industry colours and the icon set.

The colours were computed, not chosen by eye. Candidate sets were generated in OKLCH
inside the light/dark lightness bands with the hue of each family constrained to a
semantic window (fuels warm, paper green, water cyan, and so on) and then annealed to
maximise the worst-case colour separation across ALL pairs, measured with the
Machado-Oliveira-Fernandes colour-vision-deficiency simulation.

Measured result for the 13 families, all-pairs, OKLab dE x100:

    light  CVD dE 8.5   (>= 8.0 target)     normal-vision dE 14.3
    dark   CVD dE 7.2   (6-8 floor band)    normal-vision dE 12.3

The normal-vision floor of 15 is NOT met, and cannot be: thirteen categories do not fit
in the gamut with that much separation between every pair, at any lightness. A
hand-picked "sensible" palette measured far worse (CVD dE 3.1). So colour is deliberately
the SECONDARY channel here. Identity is carried by the icon glyph, which is distinct in
silhouette for every family, reinforced by the legend, the tooltip and the detail panel,
all of which name the industry in words. Selecting a few industries in the legend cuts
the palette actually on screen, which is the prescribed remedy.
"""

# family id -> (light hex, dark hex)
COLORS = {
    "data-center": ("#346ab9", "#0e51cc"),
    "chemicals":   ("#9a71f4", "#791dfe"),
    "food-bev":    ("#cdab10", "#947213"),
    "pharma":      ("#38c9a4", "#029a6d"),
    "power":       ("#777000", "#979e02"),
    "paper-wood":  ("#00a146", "#146f43"),
    "metals":      ("#853d1b", "#a23a05"),
    "oil-gas":     ("#fc5f67", "#f25771"),
    "marine":      ("#5c1ed4", "#937cee"),
    "federal":     ("#be3475", "#b53175"),
    "campus":      ("#7e2a89", "#8829a2"),
    "other-mfg":   ("#09bdfd", "#157cac"),
    "water":       ("#0099aa", "#00a7c2"),
}

# One coordinated set, drawn on a 24x24 grid, stroked in the marker's contrast ink.
# No emoji anywhere: emoji render differently on every platform and cannot be recoloured.
ICONS = {
 "server":   "M4 5h16v5H4z M4 14h16v5H4z M7 7.5h.01 M7 16.5h.01 M10.5 7.5h6 M10.5 16.5h6",
 "molecule": "M12 4.6a2 2 0 100 4 2 2 0 100-4z M5.6 15.4a2 2 0 100 4 2 2 0 100-4z "
             "M18.4 15.4a2 2 0 100 4 2 2 0 100-4z M10.6 8.4L7 13.8 M13.4 8.4L17 13.8 M8 17.4h8",
 "wheat":    "M12 21V9 M12 9c0-2.2 1.3-4 3-4.6.5 2.3-.5 4.5-3 5.6z "
             "M12 9C12 6.8 10.7 5 9 4.4 8.5 6.7 9.5 8.9 12 10z "
             "M12 14c0-2.2 1.3-4 3-4.6.5 2.3-.5 4.5-3 5.6z "
             "M12 14c0-2.2-1.3-4-3-4.6-.5 2.3.5 4.5 3 5.6z",
 "capsule":  "M8.6 4.4a4.5 4.5 0 016.4 6.4l-4.2 4.2a4.5 4.5 0 01-6.4-6.4z M6.2 6.8l6.4 6.4 "
             "M16.5 15.5h4 M18.5 13.5v4",
 "bolt":     "M13.5 3L5.5 13.5h5.2L10 21l8.2-10.7h-5.3z",
 "tree":     "M12 3.5L6.5 12h11z M12 8.5L4.8 18h14.4z M12 18v3 M9 21h6",
 "ingot":    "M6.6 13.5h10.8l2.2 4.5H4.4z M8.6 8.5h6.8l1.6 4H7z M10.4 4h4l1.2 3.5H9.2z",
 "tank":     "M5.5 8.5h13v11h-13z M5.5 8.5c0-1.4 2.9-2.5 6.5-2.5s6.5 1.1 6.5 2.5 "
             "M5.5 13h13 M9 4.5V6 M15 4.5V6",
 "ship":     "M3.5 15.5h17l-2.2 4.5H5.7z M6.5 15.5V10h11v5.5 M12 10V5 M8.5 7.5h7",
 "shield":   "M12 3.2l7 2.6v5.4c0 4.2-2.9 7.6-7 9.6-4.1-2-7-5.4-7-9.6V5.8z M9 12l2.2 2.3L15.5 10",
 "building": "M4.5 20.5V6.5l7-3 7 3v14 M8 10h.01 M12 10h.01 M15.5 10h.01 "
             "M8 14h.01 M12 14h.01 M15.5 14h.01 M10 20.5v-3.2h4v3.2",
 "factory":  "M3.5 20.5V11l5 3.2V11l5 3.2V11l5 3.2v6.3z M16.5 11V4.5h3V11 M7 17.5h2 M13 17.5h2",
 "droplet":  "M12 3.2c3.6 4.2 5.6 7.2 5.6 9.8a5.6 5.6 0 11-11.2 0c0-2.6 2-5.6 5.6-9.8z",
}

# potential band -> marker radius in screen px. Four sizes, deliberately far apart so the
# difference is readable without measuring, and never the only cue for anything.
MARKER_R = {4: 13.0, 3: 10.5, 2: 8.5, 1: 6.5}

SOURCE_LABELS = {
 "IIR plant list":    ("Industrial Info", "Licensed industrial plant export supplied by Joe.",
                       "current as supplied, Sept 2026"),
 "VA DEQ air permit": ("Virginia DEQ", "State active air-permit register (EDMA public service).",
                       "register queried Sept 2026"),
 "TRI 2024":          ("EPA TRI 2024", "Toxics Release Inventory, reporting year 2024.",
                       "reporting year 2024"),
 "GHGRP 2023":        ("EPA GHGRP 2023", "Greenhouse Gas Reporting Program, reporting year 2023.",
                       "reporting year 2023"),
 "eGRID 2023":        ("EPA eGRID 2023", "EPA's build of the EIA-860/923 generator forms.",
                       "reporting year 2023"),
 "Claude sweep":      ("Unverified research", "Named from an AI recall sweep. No registry source "
                       "confirms it. Not a citation.", "no source date"),
}
