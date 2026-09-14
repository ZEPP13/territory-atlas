#!/usr/bin/env python3
"""Elevation + bathymetry grid for the 3D map mockups.

Source: AWS Open Data "Terrain Tiles" (terrarium encoding) — public, no key, no account.
They blend USGS 3DEP/NED on land with NOAA/GEBCO bathymetry offshore, so the Chesapeake
and the tidal rivers carry real (if coarse) depths. Pulled once, resampled onto the SAME
world grid the basemap uses, and written as a 16-bit value packed into an RGB PNG so the
browser decodes it for free.

    python3 06-map-mockups/terrain_build.py
Output: 02-data/geo/terrain.png, 02-data/geo/terrain.json
"""
import os, io, json, math, urllib.request
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE = os.path.join(ROOT, "02-data", "geo", "_raw", "terrarium")
OUT_PNG = os.path.join(ROOT, "02-data", "geo", "terrain.png")
OUT_JSON = os.path.join(ROOT, "02-data", "geo", "terrain.json")
VIEW = json.load(open(os.path.join(ROOT, "02-data", "geo", "basemap.json")))["view"]
Z = 9
GRID_W = 640                                # columns; rows follow the world aspect ratio
KLAT = math.cos(math.radians(37.7))         # must match the basemap projection

def tile_xy(lon, lat, z):
    n = 2 ** z
    x = (lon + 180) / 360 * n
    y = (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n
    return x, y

def get_tile(x, y):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, f"{Z}_{x}_{y}.png")
    if not os.path.exists(p):
        url = f"https://s3.amazonaws.com/elevation-tiles-prod/terrarium/{Z}/{x}/{y}.png"
        with urllib.request.urlopen(url, timeout=60) as r:
            open(p, "wb").write(r.read())
    return Image.open(p).convert("RGB")

def main():
    lon0, lat0, lon1, lat1 = VIEW
    x0, y0 = tile_xy(lon0, lat1, Z)
    x1, y1 = tile_xy(lon1, lat0, Z)
    tx0, ty0, tx1, ty1 = int(x0), int(y0), int(x1), int(y1)
    tiles = {}
    for tx in range(tx0, tx1 + 1):
        for ty in range(ty0, ty1 + 1):
            tiles[(tx, ty)] = get_tile(tx, ty).load()

    def elev(lon, lat):
        fx, fy = tile_xy(lon, lat, Z)
        tx, ty = int(fx), int(fy)
        px = min(255, int((fx - tx) * 256)); py = min(255, int((fy - ty) * 256))
        r, g, b = tiles[(tx, ty)][px, py]
        return (r * 256 + g + b / 256) - 32768

    ww, wh = (lon1 - lon0) * KLAT, (lat1 - lat0)
    gw = GRID_W
    gh = round(gw * wh / ww)
    img = Image.new("RGB", (gw, gh))
    px = img.load()
    lo, hi = 1e9, -1e9
    OFF = 1000.0                       # store (m + 1000) * 10 -> 0.1 m resolution, 16-bit
    for j in range(gh):
        lat = lat1 - (j + 0.5) / gh * wh
        for i in range(gw):
            lon = lon0 + (i + 0.5) / gw * ww / KLAT
            e = elev(lon, lat)
            lo, hi = min(lo, e), max(hi, e)
            v = max(0, min(65535, round((e + OFF) * 10)))
            px[i, j] = (v >> 8, v & 255, 0)
    img.save(OUT_PNG, optimize=True)
    json.dump({"w": gw, "h": gh, "offset_m": OFF, "scale": 10, "min_m": round(lo, 1),
               "max_m": round(hi, 1), "view": VIEW, "zoom": Z,
               "source": "AWS Open Data Terrain Tiles (terrarium): USGS 3DEP/NED on land, "
                         "NOAA/GEBCO bathymetry offshore. Public, no key."},
              open(OUT_JSON, "w"), indent=1)
    print(f"terrain.png {gw}x{gh}  {os.path.getsize(OUT_PNG)/1e3:.0f} KB   "
          f"range {lo:.0f} .. {hi:.0f} m   tiles {len(tiles)}")

if __name__ == "__main__":
    main()
