#!/usr/bin/env python3
"""RQ1-RQ5 analysis. Reads results/timing.jsonl, results/mal2026.jsonl, results/fix_delay.jsonl,
the hand-validation verdicts, and writes results/summary.json (every number in the article comes
from that file or from results/friction-summary.json)."""
import json, math, statistics as st, datetime as dt, collections, hashlib, re

def P(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None

def wilson(k, n, z=1.96):
    if not n: return [None, None]
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 4), round(c + h, 4)]

def share(k, n):
    return {"k": k, "n": n, "share": round(k / n, 4) if n else None, "wilson": wilson(k, n)}

def km(durs):
    """durs: list of (hours, event). Kaplan-Meier; returns S(t) = share still listed after t hours, and the step list."""
    import bisect
    ev = sorted(durs, key=lambda x: (x[0], not x[1]))
    n = len(ev); s = 1.0; out = []; i = 0
    while i < n:
        t = ev[i][0]; d = c = 0
        j = i
        while j < n and ev[j][0] == t:
            d += ev[j][1]; c += not ev[j][1]; j += 1
        if d: s *= 1 - d / (n - i); out.append((t, s))
        i = j
    ts = [t for t, _ in out]
    def S(t):
        k = bisect.bisect_right(ts, t)
        return out[k - 1][1] if k else 1.0
    return S, out

recs = {json.loads(l)["id"]: json.loads(l) for l in open("data/results/mal2026.jsonl")}
T = [json.loads(l) for l in open("data/results/timing.jsonl")]
pk = {}
for l in open("data/packuments.jsonl"):
    d = json.loads(l); pk[d["name"]] = d
S_ = {}
S_["population"] = {"mal_published_2026": len(T), "withdrawn": sum(1 for x in T if x["withdrawn"])}
T = [x for x in T if not x["withdrawn"]]
N = len(T); S_["population"]["analysed"] = N
S_["population"]["packages"] = len({x["package"] for x in T})
S_["population"]["whole_package_range"] = sum(1 for x in T if x["whole_package_range"])
S_["population"]["http"] = dict(collections.Counter(str(x["http"]) for x in T))
S_["population"]["by_month"] = dict(sorted(collections.Counter(x["osv_published"][:7] for x in T).items()))

# ---------- timing ----------
cls = collections.Counter()
rows = []
neg_gone = 0
for x in T:
    tp, tg = P(x["t_pub"]), P(x["t_gone"])
    snap = P(pk[x["package"]]["fetched"])
    # t_flag: OSV `published` values of exactly 00:00:00Z are date-only (e.g. MAL-2026-3852: published
    # 2026-05-19T00:00:00Z, first source report 05:36Z, package published 01:56Z). Use the source origin
    # time instead when `published` is date-only.
    mr = recs[x["id"]]
    pubd = mr["published"]
    # Date-only: the flag is known only to have happened that day, so use the end of that day
    # (conservative) unless a source origin time is earlier.
    pubt = P(pubd) + dt.timedelta(days=1) if pubd.endswith("T00:00:00Z") else P(pubd)
    tf = min(z for z in [P(mr["earliest_origin_modified"]), pubt] if z)
    if pubd.endswith("T00:00:00Z"): cls["_flag_date_only_published"] += 1
    r = {"id": x["id"], "pkg": x["package"], "tp": tp, "vec": x["vector_labels"], "whole": x["whole_package_range"],
         "nprior": x["n_prior_versions"], "fprior": P(x["first_prior_publish"]), "src": x["t_gone_source"]}
    if tp is None:
        c = "no_publish_time"
    elif tg is not None:
        c = "removed_known"; h = (tg - tp).total_seconds() / 3600
        if h < 0: neg_gone += 1; h = 0.0
        r["dur"], r["event"] = h, True
    elif x["still_listed"]:
        c = "still_listed"; r["dur"], r["event"] = (snap - tp).total_seconds() / 3600, False
    else:
        c = "removed_time_unknown" if x["http"] == 200 else f"packument_{x['http']}"
    r["cls"] = c; cls[c] += 1
    if tp is not None:
        end = min(z for z in [tg, tf] if z)
        hf = (end - tp).total_seconds() / 3600
        r["dur_flag"] = max(hf, 0.0); r["flag_neg"] = hf < 0
    rows.append(r)
S_["timing"] = {"classes": dict(cls), "negative_removal_windows_clipped": neg_gone,
                "t_gone_source": dict(collections.Counter(x["t_gone_source"] or "none" for x in T)),
                "t_pub_source": dict(collections.Counter(x["t_pub_source"] or "none" for x in T))}
usable = [r for r in rows if r["cls"] in ("removed_known", "still_listed")]
S_["timing"]["usable"] = share(len(usable), N)
S_["timing"]["with_t_pub"] = share(sum(1 for r in rows if r["tp"]), N)
S_["timing"]["with_removal_time"] = share(cls["removed_known"], N)
rk = [r["dur"] for r in usable if r["event"]]
S_["timing"]["removed_known_hours"] = {"n": len(rk), "median": round(st.median(rk), 2),
    "p25": round(st.quantiles(rk, n=4)[0], 2), "p75": round(st.quantiles(rk, n=4)[2], 2)}
still = [r for r in rows if r["cls"] == "still_listed"]
S_["still_listed"] = {"records": len(still), "packages": len({r["pkg"] for r in still}),
    "share_of_usable": share(len(still), len(usable)),
    "median_days_listed": round(st.median([r["dur"] / 24 for r in still]), 1) if still else None,
    "note": "Counts only. Package names are deliberately not reported."}

Skm, curve = km([(r["dur"], r["event"]) for r in usable])
Skm_f, curve_f = km([(r["dur_flag"], True) for r in rows if r["tp"]])
H = {"1h": 1, "24h": 24, "1d": 24, "3d": 72, "7d": 168, "14d": 336}
def classify(rs, hours, key="dur"):
    stopped = sum(1 for r in rs if r["event"] and r[key] < hours)
    known = sum(1 for r in rs if (r["event"] and r[key] < hours) or r[key] >= hours)
    return share(stopped, known)
S_["cooldown"] = {}
for lab, h in [("1h", 1), ("1d", 24), ("3d", 72), ("7d", 168), ("14d", 336)]:
    S_["cooldown"][lab] = {"removal_simple": classify(usable, h),
        "removal_km_stopped": round(1 - Skm(h - 1e-9), 4),
        "flag_or_removal_km_stopped": round(1 - Skm_f(h - 1e-9), 4)}
S_["cooldown"]["flag_before_publish_clipped"] = sum(1 for r in rows if r.get("flag_neg"))
S_["cooldown"]["flag_population"] = sum(1 for r in rows if r["tp"])
# curves for charts (hours grid)
grid = [0.25, 0.5, 1, 2, 3, 6, 12, 24, 48, 72, 120, 168, 240, 336, 504, 720]
S_["km_curve"] = {"hours": grid, "removal": [round(Skm(h), 4) for h in grid],
                  "flag_or_removal": [round(Skm_f(h), 4) for h in grid]}

# ---------- vectors / npm 12 ----------
def vclass(v):
    if not v: return "unknown"
    if v == ["install_script"]: return "install_only"
    if "install_script" in v: return "install_plus"
    return "no_install"
vc = collections.Counter(vclass(x["vector_labels"]) for x in T)
stated = N - vc["unknown"]
S_["npm12"] = {"classes": dict(vc), "stated_vector": share(stated, N),
    "install_only_of_stated": share(vc["install_only"], stated),
    "install_any_of_stated": share(vc["install_only"] + vc["install_plus"], stated),
    "install_only_of_all": share(vc["install_only"], N)}
v1 = json.load(open("data/results/vector-validation-verdicts.json"))["verdicts"]
v2 = json.load(open("data/results/validation-verdicts-2.json"))["verdicts"]
lab2 = [v for v in v2 if v["group"] == "labelled"]; unc2 = [v for v in v2 if v["group"] == "unclear"]
S_["validation"] = {"labelled_n": len(v1) + len(lab2),
    "exact": share(sum(v["exact"] is True for v in v1) + sum(v["exact"] for v in lab2), len(v1) + len(lab2)),
    "npm12_binary": share(sum(v["npm12_binary"] is True for v in v1) + sum(v["npm12_binary"] for v in lab2), len(v1) + len(lab2)),
    "unclear_n": len(unc2), "unclear_with_stated_vector": share(sum(v["vector_stated"] for v in unc2), len(unc2)),
    "unclear_missed_install_script": sum(v["missed_install_script"] for v in unc2)}

# ---------- scenario matrix (records with stated vector and known 7-day outcome) ----------
def matrix(hours, key="dur", base=usable):
    m = collections.Counter()
    for r in base:
        if not r["vec"]: continue
        if not ((r["event"] and r[key] < hours) or r[key] >= hours): continue
        cd = r["event"] and r[key] < hours
        sb = vclass(r["vec"]) == "install_only"
        m[("both" if cd and sb else "cooldown_only" if cd else "scripts_only" if sb else "neither")] += 1
    n = sum(m.values())
    return {k: share(m[k], n) for k in ("both", "scripts_only", "cooldown_only", "neither")} | {"n": n}
def either_all(hours):
    """All records with a known outcome at N; an unstated vector counts as NOT stopped by npm 12 (conservative)."""
    k = n = 0
    for r in usable:
        if not ((r["event"] and r["dur"] < hours) or r["dur"] >= hours): continue
        n += 1
        k += (r["event"] and r["dur"] < hours) or vclass(r["vec"]) == "install_only"
    return share(k, n)
S_["either_all_conservative"] = {lab: either_all(h) for lab, h in [("1d", 24), ("3d", 72), ("7d", 168), ("14d", 336)]}
S_["matrix"] = {lab: matrix(h) for lab, h in [("1d", 24), ("3d", 72), ("7d", 168), ("14d", 336)]}

# ---------- hijacked established packages (RQ4) ----------
def hijack(r):
    return (not r["whole"]) and r["nprior"] >= 5 and r["fprior"] is not None and r["tp"] is not None \
        and (r["tp"] - r["fprior"]).days >= 90
HJ = [r for r in rows if hijack(r)]
S_["hijack"] = {"definition": "specific versions listed; >=5 earlier versions; first earlier version >=90 days before",
    "records": len(HJ), "packages": len({r["pkg"] for r in HJ}), "classes": dict(collections.Counter(r["cls"] for r in HJ)),
    "vector": dict(collections.Counter(vclass(r["vec"]) for r in HJ))}
HU = [r for r in HJ if r["cls"] in ("removed_known", "still_listed")]
Sh, _ = km([(r["dur"], r["event"]) for r in HU])
S_["hijack"]["usable"] = len(HU)
S_["hijack"]["cooldown"] = {lab: {"removal_simple": classify(HU, h), "removal_km_stopped": round(1 - Sh(h - 1e-9), 4)}
                            for lab, h in [("1h", 1), ("1d", 24), ("3d", 72), ("7d", 168), ("14d", 336)]}
hk = [r["dur"] for r in HU if r["event"]]
S_["hijack"]["removed_known_hours"] = {"n": len(hk), "median": round(st.median(hk), 2) if hk else None}
S_["hijack"]["matrix_7d"] = matrix(168, base=HU)
S_["hijack"]["still_listed"] = {"records": sum(1 for r in HU if not r["event"]), "packages": len({r["pkg"] for r in HU if not r["event"]})}
S_["km_curve"]["hijack"] = [round(Sh(h), 4) for h in grid]
json.dump(sorted([r["id"] for r in HJ]), open("data/results/hijack_ids.json", "w"))


# ---------- hijack: flag-or-removal (amendment 1) ----------
HF = [r for r in HJ if r["tp"] is not None]
Shf, _ = km([(r["dur_flag"], True) for r in HF])
S_["hijack"]["flag_or_removal"] = {"n": len(HF), "median_hours": round(st.median([r["dur_flag"] for r in HF]), 2),
    "stopped": {lab: share(sum(1 for r in HF if r["dur_flag"] < h), len(HF)) for lab, h in
                [("1h", 1), ("1d", 24), ("3d", 72), ("7d", 168), ("14d", 336)]}}
S_["km_curve"]["hijack_flag_or_removal"] = [round(Shf(h), 4) for h in grid]
S_["hijack"]["t_gone_source_of_removed_known"] = dict(collections.Counter(r["src"] for r in HJ if r["cls"] == "removed_known"))

# ---------- campaigns (hand codes) ----------
import re as _re
MC = json.load(open("data/results/manual_codes.json"))
import os
camp = {}
if os.environ.get("OSV_MAL_DIR"):
    # Match campaigns from the OSV advisory texts (one <id>.json per MAL record, unpacked from the OSV dump).
    for r in rows:
        o = json.load(open(os.path.join(os.environ["OSV_MAL_DIR"], f"{r['id']}.json")))
        t = o.get("summary", "") + " " + o.get("details", "")
        for c in MC["campaigns"]:
            if _re.search(c["pattern"], t):
                camp[r["id"]] = c["key"]; break
else:
    # Published dataset: the same regex matches, precomputed from the 8 October 2026 snapshot
    # (records still listed on the registry carry redacted ids).
    camp = json.load(open("data/campaign-assignments.json"))
S_["campaigns"] = {}
for c in MC["campaigns"]:
    rs = [r for r in rows if camp.get(r["id"]) == c["key"]]
    fr = [r for r in rs if r["tp"] is not None]
    S_["campaigns"][c["key"]] = {"label": c["label"], "code": c["code"], "records": len(rs),
        "in_hijack_subset": sum(1 for r in rs if hijack(r)),
        "rules_install_only": sum(1 for r in rs if vclass(r["vec"]) == "install_only"),
        "median_hours_to_flag_or_removal": round(st.median([r["dur_flag"] for r in fr]), 2) if fr else None,
        "stopped_7d_flag_or_removal": share(sum(1 for r in fr if r["dur_flag"] < 168), len(fr)),
        "stopped_1d_flag_or_removal": share(sum(1 for r in fr if r["dur_flag"] < 24), len(fr))}
# hijack subset vectors after hand codes (campaign code overrides rules)
def hvec(r):
    k = camp.get(r["id"])
    if k: return next(c["code"] for c in MC["campaigns"] if c["key"] == k)
    return vclass(r["vec"])
S_["hijack"]["vector_hand_corrected"] = dict(collections.Counter(hvec(r) for r in HJ))
S_["hijack"]["hand_coded_records"] = sum(1 for r in HJ if r["id"] in camp)
hs = [r for r in HJ if hvec(r) != "unknown"]
S_["hijack"]["install_only_of_stated_hand"] = share(sum(1 for r in hs if hvec(r) == "install_only"), len(hs))
S_["hijack"]["install_only_of_all_hand"] = share(sum(1 for r in HJ if hvec(r) == "install_only"), len(HJ))
# matrix for hijack, flag-or-removal at 7 days, hand-corrected vectors
mh = collections.Counter()
for r in HF:
    v = hvec(r)
    if v == "unknown": continue
    cd = r["dur_flag"] < 168; sb = v == "install_only"
    mh["both" if cd and sb else "cooldown_only" if cd else "scripts_only" if sb else "neither"] += 1
nh = sum(mh.values())
S_["hijack"]["matrix_7d_flag_hand"] = {k: share(mh[k], nh) for k in ("both", "scripts_only", "cooldown_only", "neither")} | {"n": nh}
mh1 = collections.Counter()
for r in HF:
    v = hvec(r)
    if v == "unknown": continue
    cd = r["dur_flag"] < 24; sb = v == "install_only"
    mh1["both" if cd and sb else "cooldown_only" if cd else "scripts_only" if sb else "neither"] += 1
S_["hijack"]["matrix_1d_flag_hand"] = {k: share(mh1[k], sum(mh1.values())) for k in ("both", "scripts_only", "cooldown_only", "neither")} | {"n": sum(mh1.values())}

# ---------- sensitivity (whole population) ----------
def sens(pred):
    rs = [r for r in usable if pred(r)]
    return {lab: classify(rs, h) for lab, h in [("1d", 24), ("7d", 168)]} | {"n": len(rs)}
S_["sensitivity"] = {"exclude_time_modified": sens(lambda r: r["src"] != "time.modified"),
    "version_publish_time_only": sens(lambda r: next(x for x in T if x["id"] == r["id"])["t_pub_source"] == "time[version]") if False else None,
    "exclude_hijack_subset": sens(lambda r: not hijack(r))}
tps = {x["id"]: x["t_pub_source"] for x in T}
S_["sensitivity"]["version_publish_time_only"] = sens(lambda r: tps[r["id"]] == "time[version]")
S_["sensitivity"]["whole_package_records_only"] = sens(lambda r: r["whole"])
S_["by_month_7d"] = {}
for mth in sorted({x["osv_published"][:7] for x in T}):
    ids = {x["id"] for x in T if x["osv_published"][:7] == mth}
    S_["by_month_7d"][mth] = classify([r for r in usable if r["id"] in ids], 168)
S_["campaign_share_of_records"] = share(len(camp), N)

# ---------- pnpm claim ----------
S_["pnpm_claim"] = {"claim": "In most cases, malicious releases are discovered and removed from the registry within an hour.",
    "removed_within_1h_simple": classify(usable, 1), "removed_within_1h_km": round(1 - Skm(1 - 1e-9), 4),
    "hijack_removed_within_1h_simple": classify(HU, 1),
    "hijack_flag_or_removal_within_1h": share(sum(1 for r in HF if r["dur_flag"] < 1), len(HF)),
    "removed_within_1h_excl_time_modified": classify([r for r in usable if r["src"] != "time.modified"], 1)}

# ---------- RQ5 fix delay ----------
F_all = [json.loads(l) for l in open("data/results/fix_delay.jsonl")]
F = [u for u in F_all if u.get("t_fix")]
def fsum(U):
    o = {"units": len(U), "packages": len({u["package"] for u in U}),
         "fix_before_advisory": share(sum(1 for u in U if u["fix_minus_adv_days"] <= 0), len(U))}
    for n in ("1d", "3d", "7d", "14d"):
        e = [u[f"extra_{n}"] for u in U]
        pos = [v for v in e if v > 0]
        o[n] = {"zero_extra": share(sum(1 for v in e if v == 0), len(e)), "median": round(st.median(e), 2),
                "mean": round(st.mean(e), 2), "median_if_delayed": round(st.median(pos), 2) if pos else 0,
                "over_3_days": share(sum(1 for v in e if v > 3), len(e))}
    return o
top = [u for u in F if u["top1000_rank"]]
S_["fix_delay"] = {"units_total": len(F_all), "units_no_fix_time": len(F_all) - len(F),
    "top1000_units_no_fix_time": sum(1 for u in F_all if u["top1000_rank"] and not u.get("t_fix")),
    "top1000": fsum(top), "all": fsum(F),
    "top1000_by_severity": {s: fsum([u for u in top if u["severity"] == s]) for s in ("CRITICAL", "HIGH", "MODERATE", "LOW")
                            if any(u["severity"] == s for u in top)},
    "all_critical_high": fsum([u for u in F if u["severity"] in ("CRITICAL", "HIGH")])}
pp = collections.defaultdict(list)
for u in top: pp[u["package"]].append(u)
S_["fix_delay"]["top1000_concentration"] = {"largest": collections.Counter(u["package"] for u in top).most_common(5),
    "package_weighted_zero_extra": {n: round(st.mean(sum(1 for u in us if u[f"extra_{n}"] == 0) / len(us) for us in pp.values()), 4)
                                    for n in ("1d", "3d", "7d", "14d")},
    "excluding_largest_two": fsum([u for u in top if u["package"] not in ("electron", "next")])}
json.dump(S_, open("data/results/summary.json", "w"), indent=1, default=str)
print(json.dumps({k: S_[k] for k in ("hijack", "campaigns", "sensitivity", "by_month_7d", "pnpm_claim", "validation", "fix_delay")}, indent=0, default=str))
