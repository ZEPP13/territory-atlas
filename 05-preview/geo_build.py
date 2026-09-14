#!/usr/bin/env python3
"""Build the self-contained vector basemap for the preview atlas.

Everything is US Census Bureau public-domain TIGER geography, pulled once from the
public TIGERweb ArcGIS REST endpoints. No API key, no account, no cost, and the
built artifact carries the geometry inline, so the published page makes no network
call for map data at runtime.

  python3 05-preview/geo_build.py            # uses cached raw pulls if present
  python3 05-preview/geo_build.py --refetch  # re-pull from census.gov

Output: 02-data/geo/basemap.json
"""
import json, os, sys, math, urllib.request, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW  = os.environ.get("ATLAS_GEO_CACHE") or os.path.join(ROOT, "02-data", "geo", "_raw")
OUT  = os.path.join(ROOT, "02-data", "geo", "basemap.json")

TIGER = "https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb"
BBOX  = "-79.6,36.2,-74.9,39.4"          # pull window, a little wider than the territory
VIEW  = (-79.10, 36.35, -74.95, 39.30)   # lon0, lat0, lon1, lat1 kept in the basemap

NEIGHBOR_STATES = ["24", "37", "54", "11"]   # MD, NC, WV, DC — context only

PULLS = {
    "counties": f"{TIGER}/State_County/MapServer/5/query?" + urllib.parse.urlencode({
        "where": "STATE='51'", "outFields": "GEOID,BASENAME,LSADC",
        "returnGeometry": "true", "outSR": "4326", "f": "geojson"}),
    "roads": f"{TIGER}/Transportation/MapServer/1/query?" + urllib.parse.urlencode({
        "where": "1=1", "geometry": BBOX, "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "outFields": "NAME,MTFCC", "returnGeometry": "true", "outSR": "4326", "f": "geojson"}),
    "hydro": f"{TIGER}/Hydro/MapServer/1/query?" + urllib.parse.urlencode({
        "where": "AREAWATER>3000000", "geometry": BBOX, "geometryType": "esriGeometryEnvelope",
        "inSR": "4326", "spatialRel": "esriSpatialRelIntersects",
        "outFields": "NAME,AREAWATER", "returnGeometry": "true", "outSR": "4326", "f": "geojson"}),
}

for _st in NEIGHBOR_STATES:
    PULLS[f"nb_{_st}"] = f"{TIGER}/State_County/MapServer/7/query?" + urllib.parse.urlencode({
        "where": f"STATE='{_st}'", "outFields": "GEOID,BASENAME",
        "returnGeometry": "true", "outSR": "4326", "f": "geojson"})

def fetch(key, refetch=False):
    os.makedirs(RAW, exist_ok=True)
    p = os.path.join(RAW, key + ".geojson")
    if os.path.exists(p) and not refetch:
        return json.load(open(p))
    sys.stderr.write(f"  fetching {key} from census.gov ...\n")
    req = urllib.request.Request(PULLS[key], headers={"User-Agent": "territory-atlas/1.0"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = r.read()
    open(p, "wb").write(data)
    return json.loads(data)

# ---------------------------------------------------------------- geometry utils
def rings(geom):
    """Yield every exterior/interior ring of a Polygon or MultiPolygon."""
    t = geom["type"]
    if t == "Polygon":
        for r in geom["coordinates"]: yield r
    elif t == "MultiPolygon":
        for poly in geom["coordinates"]:
            for r in poly: yield r

def lines(geom):
    t = geom["type"]
    if t == "LineString": yield geom["coordinates"]
    elif t == "MultiLineString":
        for l in geom["coordinates"]: yield l

def rdp(pts, eps):
    """Douglas-Peucker. pts is [[lon,lat],...]."""
    if len(pts) < 3: return pts
    keep = [False]*len(pts); keep[0] = keep[-1] = True
    stack = [(0, len(pts)-1)]
    while stack:
        a, b = stack.pop()
        if b <= a+1: continue
        x1, y1 = pts[a]; x2, y2 = pts[b]
        dx, dy = x2-x1, y2-y1
        den = math.hypot(dx, dy)
        worst, wi = -1.0, -1
        for i in range(a+1, b):
            x, y = pts[i]
            d = abs(dy*x - dx*y + x2*y1 - y2*x1)/den if den else math.hypot(x-x1, y-y1)
            if d > worst: worst, wi = d, i
        if worst > eps:
            keep[wi] = True; stack.append((a, wi)); stack.append((wi, b))
    return [p for p, k in zip(pts, keep) if k]

def clip_bbox(pts, box, pad=0.25):
    """Drop segments wholly outside the view box; keeps the polyline split into pieces."""
    lo_x, lo_y, hi_x, hi_y = box[0]-pad, box[1]-pad, box[2]+pad, box[3]+pad
    inside = lambda p: lo_x <= p[0] <= hi_x and lo_y <= p[1] <= hi_y
    out, cur = [], []
    for i, p in enumerate(pts):
        nb = inside(p) or (i and inside(pts[i-1])) or (i+1 < len(pts) and inside(pts[i+1]))
        if nb: cur.append(p)
        elif cur: out.append(cur); cur = []
    if cur: out.append(cur)
    return [c for c in out if len(c) > 1]

def bbox_hits(ring, box, pad=0.25):
    xs = [p[0] for p in ring]; ys = [p[1] for p in ring]
    return not (max(xs) < box[0]-pad or min(xs) > box[2]+pad or
                max(ys) < box[1]-pad or min(ys) > box[3]+pad)

def q(pts, nd=4):
    """Quantise to a fixed grid and delta-encode as integers — this is what keeps
    the inlined basemap small without a compression library at runtime."""
    s = 10**nd
    out, px, py = [], 0, 0
    for x, y in pts:
        ix, iy = round(x*s), round(y*s)
        out.append(ix-px); out.append(iy-py)
        px, py = ix, iy
    return out

# ------------------------------------------------------- territory union boundary
def union_boundary(polys):
    """TIGER county polygons are topologically consistent: an edge shared by two
    counties appears twice, with identical vertices. Edges that appear once are on
    the outer boundary of the union. Chain those into rings."""
    from collections import Counter, defaultdict
    count = Counter()
    for ring in polys:
        for i in range(len(ring)-1):
            a, b = tuple(ring[i]), tuple(ring[i+1])
            count[(a, b) if a <= b else (b, a)] += 1
    adj = defaultdict(list)
    for (a, b), n in count.items():
        if n == 1: adj[a].append(b); adj[b].append(a)
    seen, out = set(), []
    for start in list(adj):
        if start in seen: continue
        ring, cur, prev = [start], start, None
        seen.add(start)
        while True:
            nxt = None
            for cand in adj[cur]:
                if cand is not prev and cand != prev and cand not in seen:
                    nxt = cand; break
            if nxt is None:
                if start in adj[cur] and len(ring) > 2: ring.append(start)
                break
            ring.append(nxt); seen.add(nxt); prev, cur = cur, nxt
        if len(ring) > 3: out.append([list(p) for p in ring])
    return out

# ------------------------------------------------------------------------- build
def main():
    refetch = "--refetch" in sys.argv
    CL = json.load(open(os.path.join(ROOT, "02-data", "clusters.json")))
    want = {}
    for cid, (nm, band, js) in CL.items():
        for j in js: want[j] = cid

    co = fetch("counties", refetch)
    terr_polys, feats = [], []
    for f in co["features"]:
        p = f["properties"]
        key = p["BASENAME"] + (" (City)" if p["LSADC"] == "25" else "")
        inside = key in want
        rs = [r for r in rings(f["geometry"]) if bbox_hits(r, VIEW)]
        if not rs: continue
        if inside: terr_polys += [r for r in rings(f["geometry"])]
        feats.append({"n": key, "in": inside, "c": want.get(key, ""),
                      "r": [q(rdp(r, 0.0009)) for r in rs]})
    missing = sorted(set(want) - {f["n"] for f in feats if f["in"]})
    if missing:
        sys.exit(f"FATAL: territory jurisdictions not found in TIGER: {missing}")

    nbf = []
    for st in NEIGHBOR_STATES:
        for f in fetch(f"nb_{st}", refetch)["features"]:
            rs = [r for r in rings(f["geometry"]) if bbox_hits(r, VIEW, 0.05)]
            if rs: nbf.append([q(rdp(r, 0.004)) for r in rs])

    bound = [q(rdp(r, 0.0009)) for r in union_boundary(terr_polys)]

    rd = fetch("roads", refetch)
    roads = []
    for f in rd["features"]:
        nm = (f["properties"].get("NAME") or "").replace("I- ", "I-").strip()
        cls = "int" if nm.startswith("I-") else "us" if nm.lower().startswith("us hwy") else "oth"
        if cls == "oth": continue
        for ln in lines(f["geometry"]):
            for piece in clip_bbox(ln, VIEW, 0.1):
                roads.append({"n": nm, "k": cls, "p": q(rdp(piece, 0.0015))})

    hy = fetch("hydro", refetch)
    water = []
    for f in hy["features"]:
        nm = (f["properties"].get("NAME") or "").replace(" Riv", " River").replace(" Crk", " Creek")
        area = f["properties"].get("AREAWATER") or 0
        for r in rings(f["geometry"]):
            if not bbox_hits(r, VIEW, 0.1) or len(r) < 4: continue
            s = rdp(r, 0.0012)
            if len(s) < 4: continue
            water.append({"n": nm, "a": area, "p": q(s)})

    data = {
        "_source": "US Census Bureau TIGERweb (public domain). Counties/equivalents, "
                   "primary roads, areal hydrography. Pulled by 05-preview/geo_build.py; "
                   "embedded in the page, so no runtime network call and no map account.",
        "view": VIEW, "nd": 4,
        "jurisdictions": feats, "neighbors": nbf, "boundary": bound,
        "roads": roads, "water": water,
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    json.dump(data, open(OUT, "w"), separators=(",", ":"))
    n_in = sum(1 for f in feats if f["in"])
    print(f"basemap.json  {os.path.getsize(OUT)/1e6:.2f} MB")
    print(f"  jurisdictions {len(feats)} ({n_in} in territory)  boundary rings {len(bound)}")
    print(f"  neighbour polys {len(nbf)}  roads {len(roads)}  water polys {len(water)}")

if __name__ == "__main__":
    main()
