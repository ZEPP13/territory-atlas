"""Unified merge, v6.  Backbone = Industrial Info Resources plant list (licensed, supplied by Joe).
EPA TRI / GHGRP / eGRID and VA DEQ air permits enrich it and add what IIR lacks.
Claude's original recall sweep contributes narrative and the Pass-2 enrichment only.
Everything is scoped to the OFFICIAL 74-jurisdiction territory."""
import json,glob,os,re,math
ROOT=os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MUNI={"municipal-water","municipal-wastewater"}
CLUST=json.load(open(os.path.join(ROOT,"02-data/clusters.json")))
J2C={j.lower():(cid,b,j) for cid,(n,b,js) in CLUST.items() for j in js}
CO={j for cid,(n,b,js) in CLUST.items() for j in js if not j.endswith("(City)")}
CITY={j.replace(" (City)","") for cid,(n,b,js) in CLUST.items() for j in js if j.endswith("(City)")}
COL={c.lower() for c in CO}; CITYL={c.lower() for c in CITY}
def juris(raw):
    s=re.sub(r"\s+"," ",(raw or "").strip().lower())
    if not s: return None
    if s in COL: return next(c for c in CO if c.lower()==s)
    iscity=bool(re.search(r"\s(city|cit)$",s))
    base=re.sub(r"\s+(city|cit)$","",s)
    if iscity and base in CITYL: return next(c for c in CITY if c.lower()==base)+" (City)"
    if not iscity and base in COL: return next(c for c in CO if c.lower()==base)
    if base in CITYL: return next(c for c in CITY if c.lower()==base)+" (City)"
    return None

STOP=set("""INC LLC CORP CORPORATION COMPANY PLANT MILL STATION FACILITY FACILITIES SYSTEMS SYSTEM
USA VIRGINIA THE AND HOLDINGS PRODUCTS SERVICE SERVICES GROUP LIMITED PARTNERSHIP OPERATING
INCORPORATED CENTER DATA""".split())
def toks(n): return {t for t in re.findall(r"[A-Z0-9]{3,}",(n or "").upper()) if t not in STOP}
def norm(s):
    s=(s or "").upper()
    for w in [" INCORPORATED"," INC"," LLC"," CORP"," CO."," COMPANY"," LP"," LTD"," PLANT",
              " STATION"," MILL"," WORKS"," FACILITY"," USA"," THE ","-"," & "," AND "]: s=s.replace(w," ")
    return re.sub(r"[^A-Z0-9]","",s)
def sim(a,b):
    if not a or not b: return False
    return a in b or b in a or (len(a)>8 and len(b)>8 and a[:9]==b[:9])
def milesbetween(a,b):
    dy=(a["lat"]-b["lat"])*69.0
    dx=(a["lon"]-b["lon"])*69.0*math.cos(math.radians(37.7))
    return math.hypot(dx,dy)

def load():
    cfg=json.load(open(os.path.join(ROOT,"02-data/model_config.json")))
    iir=json.load(open(os.path.join(ROOT,"02-data/registry/iir_sites.json")))
    extra=[]
    for f in ("registry_sites.json","deq_sites.json"):
        try: extra+=json.load(open(os.path.join(ROOT,"02-data/registry/",f)))
        except Exception: pass
    recall=[]
    for f in sorted(glob.glob(os.path.join(ROOT,"02-data/pass1/*.json"))): recall+=json.load(open(f))
    p2={}
    for f in sorted(glob.glob(os.path.join(ROOT,"02-data/pass2/*.json"))):
        for e in json.load(open(f)): p2[e["id"]]=e
    for r in recall:
        r["existence"]="recall"; r["sources"]=["Claude sweep"]
    for r in extra: r.setdefault("existence","registry")

    # --- anchor geography off IIR, which carries authoritative jurisdictions ---
    def place(r):
        j=juris(r.get("jurisdiction")) or juris(r.get("city"))
        if j: cid,b,_=J2C[j.lower()]; r["jurisdiction"],r["cluster"],r["band"]=j,cid,b; return True
        best=None;bd=9e9
        for a in iir:
            d=milesbetween(r,a)
            if d<bd: best,bd=a,d
        if best and bd<25:
            r["jurisdiction"],r["cluster"],r["band"]=best["jurisdiction"],best["cluster"],best["band"]
            return True
        return False
    keep=[]
    for r in extra+recall:
        if not r.get("lat") or not r.get("lon"): continue
        if r["lon"]>0: r["lon"]=-r["lon"]
        if r["lon"]<-78.9 or not (36.4<r["lat"]<39.3): continue
        r["scope"]="core"
        if place(r): keep.append(r)
        else: r["scope"]="out_of_territory"; keep.append(r)
    rows=iir+keep

    # --- dedupe: IIR wins, others fold in ---
    def rank(r):
        s=0
        if "IIR plant list" in (r.get("sources") or []): s+=10000
        if r.get("enriched"): s+=5000
        if r["existence"]=="registry": s+=200
        return s+len(r.get("note") or "")
    rows.sort(key=rank,reverse=True)
    kept=[];log=[]
    for r in rows:
        hit=None
        for k in kept:
            if abs(k["lat"]-r["lat"])>0.06: continue
            d=milesbetween(k,r)
            ta,tb=toks(k["name"]),toks(r["name"])
            if not ta or not tb: continue
            jac=len(ta&tb)/len(ta|tb)
            both_precise = k.get("coord_precision")=="site" and r.get("coord_precision")=="site"
            ok=(d<=0.6 and (jac>=0.34 or ta<=tb or tb<=ta)) if both_precise else \
               (d<=3.0 and (jac>=0.5 or ta<=tb or tb<=ta))
            if ok: hit=k;break
        if hit is None: kept.append(r); continue
        for f in ("note","flexim_why","triggers","parent","naics","subparts","deq_class","deq_reg",
                  "employees","sqft","url","operator"):
            if not hit.get(f) and r.get(f): hit[f]=r[f]
        hit["sources"]=sorted(set((hit.get("sources") or [])+(r.get("sources") or [])))
        if r.get("enriched"): 
            hit["_p2id"]=r["id"]
        for t in ("flexim","coriolis","magmeter","vortex"):
            hit[t]=max(hit.get(t,0),r.get(t,0))
        log.append(f"{r['name']}  ->  {hit['name']}")
    with open(os.path.join(ROOT,"02-data/registry/dedupe_log.txt"),"w") as fh: fh.write("\n".join(log))
    rows=kept
    for r in rows:
        r.setdefault("enriched",False); r.setdefault("subparts",""); r.setdefault("employees",0)
        r.setdefault("flexim_why",""); r.setdefault("triggers",""); r.setdefault("iir_status","")
        if r["sector"] in MUNI and r.get("scope")!="out_of_territory": r["scope"]="out_of_portfolio"
    rows=apply_exclusions(rows)
    attach_egrid(rows); colocate(rows)

    asp=cfg["asp"];mult=cfg["strategic_multiplier"];bands=cfg["tier_bands"]
    for r in rows:
        e=p2.get(r.get("_p2id") or r["id"])
        r["enriched"]=bool(e)
        if not e:
            r.update(bookings=0,flexim_dollars=0,strategic_weighted=0,flexim_pct=0,
                     tier_modeled="",tier_delta=False); continue
        keepname=r["name"]; r.update(e); r["name"]=keepname
        i=e["installed"]
        mro=sum(i[t]*e["turn"]*asp[t] for t in ("coriolis","magmeter","vortex"))
        fxd=e["flexim_points"]*e["capture"]*asp["flexim"]; bk=mro+fxd+e["project_adder"]
        r.update(bookings=round(bk),flexim_dollars=round(fxd),
                 flexim_pct=round(100*fxd/bk) if bk else 0,
                 strategic_weighted=round((bk-fxd)+mult*fxd))
        tm="D"
        for t in ("A","B","C"):
            if bk>=bands[t]: tm=t;break
        r["tier_modeled"]=tm; r["tier_delta"]=(tm!=r["tier"])
    return rows,cfg

def attach_egrid(rows):
    try: plants=json.load(open(os.path.join(ROOT,"02-data/registry/egrid_plants.json")))
    except Exception: return
    POWER={"power-generation","district-energy"}
    for p in plants:
        tp=toks(p["name"]);best=None;bs=-1
        for r in rows:
            if not r.get("lat") or milesbetween(p,r)>2.0: continue
            ov=tp&toks(r["name"])
            if not ov: continue
            sc=len(ov)*2+(10 if r["sector"] in POWER else 0)
            if sc>bs: best,bs=r,sc
        if best is None: continue
        best["sources"]=sorted(set((best.get("sources") or [])+["eGRID 2023"]))
        if best["sector"] in POWER:
            best["mw"]=p["mw"];best["fuel"]=p["fuel"];best["gen_mwh"]=p["gen_mwh"]
            if p["mw"]>=400 and best["tier"] in "BCD": best["tier"]="A"
            elif p["mw"]>=100 and best["tier"] in "CD": best["tier"]="B"
            if p["gen_mwh"]==0: best["status"]="eGRID reports ZERO 2023 generation - idle"; best["tier"]="D"
        else:
            best["onsite_gen_mw"]=p["mw"];best["onsite_gen_fuel"]=p["fuel"]
            best["vortex"]=max(best.get("vortex",0),3)

def colocate(rows,radius=0.3):
    gid=0
    for r in rows: r["site_group"]=None; r["colocated"]=[]
    for i,a in enumerate(rows):
        for b in rows[i+1:]:
            if abs(a["lat"]-b["lat"])>0.01: continue
            if milesbetween(a,b)<=radius:
                if a["site_group"] is None and b["site_group"] is None:
                    gid+=1; a["site_group"]=b["site_group"]=gid
                elif a["site_group"] is None: a["site_group"]=b["site_group"]
                elif b["site_group"] is None: b["site_group"]=a["site_group"]
    byg={}
    for r in rows:
        if r["site_group"]: byg.setdefault(r["site_group"],[]).append(r)
    for g,mem in byg.items():
        if len(mem)>8: continue
        for r in mem: r["colocated"]=[m["name"] for m in mem if m is not r]


def apply_exclusions(rows):
    """Drop categories Joe has ruled non-actionable. Rules live in 02-data/exclusions.json
    so they are auditable and reversible; source data is never mutated."""
    try: cfg=json.load(open(os.path.join(ROOT,"02-data/exclusions.json")))
    except Exception: return rows
    pats=[]
    for rule in cfg.get("rules",[]):
        if not rule.get("enabled"): continue
        pats.append((set(rule.get("match_sector") or []),
                     re.compile(rule["match_text"],re.I) if rule.get("match_text") else None,
                     rule["id"]))
    kept=[];dropped={}
    for r in rows:
        blob=" ".join(str(r.get(k) or "") for k in ("name","subsector","note","sector"))
        hit=None
        for secs,rx,rid in pats:
            if r.get("sector") in secs or (rx and rx.search(blob)): hit=rid;break
        if hit: dropped[hit]=dropped.get(hit,0)+1
        else: kept.append(r)
    with open(os.path.join(ROOT,"02-data/registry/excluded_counts.json"),"w") as fh:
        json.dump(dropped,fh,indent=1)
    return kept
