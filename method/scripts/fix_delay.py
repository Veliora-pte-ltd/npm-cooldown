#!/usr/bin/env python3
"""RQ5: extra delay a cooldown adds before a security fix can be installed.

Unit: (GHSA advisory, package, first fixed version) for npm GHSA records with
OSV `published` between 2025-10-01 and 2026-09-30 (inclusive), not withdrawn.
t_adv = earliest of OSV `published`, database_specific.github_reviewed_at and
nvd_published_at. t_fix = registry publish time of the fixed version.
extra(N) = max(0, (t_fix + N) - max(t_adv, t_fix)).
Primary set: packages in the top 1,000 by dependents (data/top1000.json).
Secondary set: all npm packages. Benign packages only; packuments only.
"""
import json, zipfile, sys, re, urllib.request, urllib.parse, datetime as dt, time
from concurrent.futures import ThreadPoolExecutor
ZIP, OUT = sys.argv[1], sys.argv[2]
NS = (1, 3, 7, 14)
def ts(s):
    s = re.sub(r"(\.\d{6})\d+", r"\1", s).replace("Z", "+00:00"); return dt.datetime.fromisoformat(s)
top = {p["name"]: p["rank"] for p in json.load(open("data/top1000.json"))}
z = zipfile.ZipFile(ZIP)
units = []
for n in z.namelist():
    if not n.startswith("GHSA-"): continue
    d = json.loads(z.read(n))
    p = d.get("published", "")
    if not ("2025-10-01" <= p[:10] <= "2026-09-30") or d.get("withdrawn"): continue
    ds = d.get("database_specific") or {}
    cands = [x for x in [p, ds.get("github_reviewed_at"), ds.get("nvd_published_at")] if x]
    t_adv = min(cands, key=ts)
    seen = set()
    for a in d.get("affected", []):
        name = a["package"]["name"]
        for r in a.get("ranges", []):
            for e in r.get("events", []):
                if "fixed" in e and (name, e["fixed"]) not in seen:
                    seen.add((name, e["fixed"]))
                    units.append({"id": d["id"], "package": name, "fixed": e["fixed"], "t_adv": t_adv,
                                  "osv_published": p, "severity": ds.get("severity"), "top1000_rank": top.get(name)})
names = sorted({u["package"] for u in units})
def times(name):
    url = "https://registry.npmjs.org/" + urllib.parse.quote(name, safe="@")
    assert "/-/" not in url
    for i in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"Accept": "application/json"}), timeout=40) as r:
                return name, {k: v for k, v in (json.load(r).get("time") or {}).items() if isinstance(v, str)}
        except urllib.error.HTTPError as e:
            if e.code == 404: return name, None
            time.sleep(2)
        except Exception:
            time.sleep(2)
    return name, None
with ThreadPoolExecutor(12) as ex: T = dict(ex.map(times, names))
with open(OUT, "w") as f:
    for u in units:
        t = T.get(u["package"]) or {}
        tf = t.get(u["fixed"])
        u["t_fix"] = tf
        if tf:
            a, fx = ts(u["t_adv"]), ts(tf)
            u["fix_minus_adv_days"] = round((fx - a).total_seconds() / 86400, 3)
            for N in NS:
                u[f"extra_{N}d"] = round(max(0.0, ((fx + dt.timedelta(days=N)) - max(a, fx)).total_seconds() / 86400), 3)
        f.write(json.dumps(u) + "\n")
print(len(units), "units;", sum(1 for u in units if u["top1000_rank"]), "in top1000;", len(names), "packages")
