#!/usr/bin/env python3
"""Full timing pass: for every 2026 OSV MAL npm record, fetch the registry
packument (JSON METADATA ONLY) and derive t_pub, t_gone, t_flag.

SAFETY: only https://registry.npmjs.org/<name> is requested. Any URL that
contains '/-/' or ends in '.tgz' (tarball paths) is refused by fetch().
A trimmed copy of each packument (time map, version keys, dist-tags; no
tarball URLs) is cached in data/packuments.jsonl for reproducibility.
"""
import json, sys, re, time, urllib.request, urllib.parse, os, datetime as dt
from concurrent.futures import ThreadPoolExecutor

SRC, OUT, CACHE = sys.argv[1], sys.argv[2], sys.argv[3]
SNAP = sys.argv[4] if len(sys.argv) > 4 else None  # ISO snapshot time for censoring

def guard(url):
    if "/-/" in url or url.endswith(".tgz") or not url.startswith("https://registry.npmjs.org/"):
        raise RuntimeError("refused non-packument URL: " + url)

def fetch(name):
    url = "https://registry.npmjs.org/" + urllib.parse.quote(name, safe="@")
    guard(url)
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "veliora-eng-notes-02"})
            with urllib.request.urlopen(req, timeout=40) as r:
                return 200, json.load(r)
        except urllib.error.HTTPError as e:
            if e.code in (404, 410): return e.code, None
            time.sleep(2 * (attempt + 1))
        except Exception:
            time.sleep(2 * (attempt + 1))
    return "error", None

rows = [json.loads(l) for l in open(SRC)]
names = sorted({r["packages"][0] for r in rows})
cache = {}
if os.path.exists(CACHE):
    for l in open(CACHE):
        d = json.loads(l); cache[d["name"]] = d

def trim(name):
    if name in cache: return cache[name]
    st, p = fetch(name)
    d = {"name": name, "http": st, "fetched": dt.datetime.now(dt.timezone.utc).isoformat()}
    if p:
        t = p.get("time", {}) or {}
        d["time"] = {k: v for k, v in t.items() if isinstance(v, str)}
        if isinstance(t.get("unpublished"), dict):
            d["unpublished"] = {"time": t["unpublished"].get("time"), "versions": t["unpublished"].get("versions")}
        d["versions"] = list((p.get("versions") or {}).keys())
        d["dist_tags"] = p.get("dist-tags", {})
    return d

t0 = time.time()
todo = [n for n in names if n not in cache]
print(f"{len(names)} packages, {len(todo)} to fetch", flush=True)
with ThreadPoolExecutor(12) as ex:
    for i, d in enumerate(ex.map(trim, todo)):
        cache[d["name"]] = d
        if i % 1000 == 0: print(i, round(time.time() - t0), "s", flush=True)
with open(CACHE, "w") as f:
    for n in names: f.write(json.dumps(cache[n]) + "\n")

out = []
for r in rows:
    name = r["packages"][0]; p = cache[name]
    t = p.get("time", {}); vs = set(p.get("versions", [])); unp = p.get("unpublished")
    affected = r["versions"] or []
    vt = {v: t[v] for v in affected if v in t}
    x = {"id": r["id"], "package": name, "n_affected": len(affected), "whole_package_range": r["whole_package_range"],
         "http": p["http"], "withdrawn": r["withdrawn"], "osv_published": r["published"],
         "t_flag": min(z for z in [r["earliest_origin_modified"], r["published"]] if z),
         "vector_labels": r["vector_labels"], "vector_negated": r.get("vector_negated", [])}
    x["t_pub"] = min(vt.values()) if vt else None
    x["t_pub_source"] = "time[version]" if vt else None
    if not vt and t.get("created") and (r["whole_package_range"] or not affected):
        x["t_pub"] = t["created"]; x["t_pub_source"] = "time.created"
    sec = [t[v] for v in vs if "-security" in v and v in t]
    if unp and unp.get("time"):
        x["t_gone"], x["t_gone_source"] = unp["time"], "unpublished.time"
    elif sec:
        x["t_gone"], x["t_gone_source"] = min(sec), "security-holding"
    else:
        x["t_gone"], x["t_gone_source"] = None, None
        still = sorted(set(affected) & vs) if affected else (sorted(vs) if r["whole_package_range"] and vs else [])
        x["still_listed"] = bool(still)
        if vt and not (set(affected) & vs):
            later = [k for k, v in t.items() if k not in ("created", "modified") and v > max(vt.values())]
            if not later and t.get("modified"):
                x["t_gone"], x["t_gone_source"] = t["modified"], "time.modified"
            else:
                x["t_gone_source"] = "removed-time-unknown"
    x.setdefault("still_listed", False)
    first = x["t_pub"]
    prior = [k for k, v in t.items() if k not in ("created", "modified") and k not in affected and "-security" not in k and first and v < first]
    x["n_prior_versions"] = len(prior)
    x["first_prior_publish"] = min((t[k] for k in prior), default=None)
    out.append(x)
with open(OUT, "w") as f:
    for x in out: f.write(json.dumps(x) + "\n")
print("done", len(out), round(time.time() - t0), "s")
