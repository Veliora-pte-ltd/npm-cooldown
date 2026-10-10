#!/usr/bin/env python3
"""Pilot census of OSV npm MAL- records (metadata only; no package code is fetched).

Reads the OSV npm dump zip directly, keeps MAL- records whose OSV `published`
falls in 2026, and writes one JSONL row per record with the fields the main
study needs, plus a summary JSON.

Execution vector is classified from advisory TEXT only (regex over `summary`
and `details`). Rules are deliberately conservative; anything without an
explicit cue is `unclear`.
"""
import json, re, sys, zipfile, collections, datetime as dt

ZIP, OUT_JSONL, OUT_SUM = sys.argv[1], sys.argv[2], sys.argv[3]

# Ordered cue lists. A record can carry several vectors (multi-label).
CUES = {
    "install_script": [
        r"\b(pre|post)install\b", r"\binstall (script|hook)s?\b", r"\"install\"\s*:", r"lifecycle (script|hook)",
        r"install[- ]time", r"\binstall script", r"binding\.gyp", r"node-gyp", r"\bgypfile\b",
        r"during (package )?install(ation)?", r"upon install(ation)?", r"on install(ation)?\b",
        r"when (the package is )?installed", r"\"scripts\"\s*:", r"\bprepare script",
    ],
    "import_time": [
        r"\bon (require|import)\b", r"when (it is |the (package|module|library) is )?(required|imported|loaded)",
        r"(at|on) (library[- ]|module[- ])?load[- ]time", r"import[- ]time", r"require[- ]time",
        r"upon (require|import|load)", r"\bmain entry\b", r"\bentry ?point\b", r"top[- ]level code",
        r"(executes|runs|triggers) (when|on|upon) (require|import)", r"any `?require\(",
        r"is (required|imported)", r"\bindex\.js\b.*\b(executes|runs)\b",
    ],
    "runtime_call": [
        r"when (a|the) (function|method|api) is (called|invoked)", r"runtime method",
        r"(called|invoked) at runtime", r"when .* is (called|invoked)", r"hidden in (a|the) (function|method)",
    ],
    "bin": [r"\bbin(ary)? (entry|field|script|command)\b", r"\"bin\"\s*:", r"\bcli command\b", r"when (the )?(cli|command) is run", r"\bnpx\b"],
}
CUES = {k: [re.compile(p, re.I) for p in v] for k, v in CUES.items()}

NEG = re.compile(r"\b(no|not|never|without|nor|neither|lacks?|absent|declares no|has no|there (is|are) no)\b[^.;]{0,60}$", re.I)

def classify(text):
    """Return (labels, cues, negated). A cue preceded in the same clause by a
    negation ("declares no preinstall hook") is recorded as negated, not as a hit."""
    hits = {k: [] for k in CUES}
    neg = {k: [] for k in CUES}
    for k, pats in CUES.items():
        for p in pats:
            for m in p.finditer(text):
                before = text[max(0, m.start() - 70):m.start()]
                (neg if NEG.search(before) else hits)[k].append(m.group(0)[:60])
    labels = [k for k, v in hits.items() if v]
    return labels, {k: v[:3] for k, v in hits.items() if v}, sorted(k for k, v in neg.items() if v)

def ts(s):
    if not s: return None
    s = re.sub(r"(\.\d{6})\d+", r"\1", s).replace("Z", "+00:00")
    return dt.datetime.fromisoformat(s)

z = zipfile.ZipFile(ZIP)
rows = []
idyear = collections.Counter()
for name in z.namelist():
    if not name.startswith("MAL-"): continue
    d = json.loads(z.read(name))
    pub = d.get("published", "")
    if not pub.startswith("2026"):
        if name.startswith("MAL-2026"): idyear["MAL-2026 id but published other year"] += 1
        continue
    idyear[name[:8]] += 1
    text = (d.get("summary", "") + "\n" + d.get("details", ""))
    labels, hits, negated = classify(text)
    aff = d.get("affected", [])
    pkgs = [a["package"]["name"] for a in aff]
    versions = sorted({v for a in aff for v in a.get("versions", [])})
    whole_pkg = any(e.get("introduced") == "0" and len(r.get("events", [])) == 1
                    for a in aff for r in a.get("ranges", []) for e in r.get("events", []))
    origins = (d.get("database_specific") or {}).get("malicious-packages-origins") or []
    o_mod = [ts(o.get("modified_time")) for o in origins if o.get("modified_time")]
    o_imp = [ts(o.get("import_time")) for o in origins if o.get("import_time")]
    rows.append({
        "id": d["id"], "packages": pkgs, "versions": versions, "n_versions": len(versions),
        "whole_package_range": whole_pkg,
        "published": pub, "modified": d.get("modified"), "withdrawn": d.get("withdrawn"),
        "earliest_origin_modified": min(o_mod).isoformat() if o_mod else None,
        "earliest_origin_import": min(o_imp).isoformat() if o_imp else None,
        "sources": sorted({o.get("source") for o in origins}),
        "vector_labels": labels, "vector_cues": hits, "vector_negated": negated,
        "details_chars": len(d.get("details", "")),
    })

with open(OUT_JSONL, "w") as f:
    for r in rows: f.write(json.dumps(r) + "\n")

n = len(rows)
lab = collections.Counter()
for r in rows:
    L = r["vector_labels"]
    lab["unclear" if not L else ("+".join(sorted(L)))] += 1
any_ = collections.Counter(l for r in rows for l in r["vector_labels"])
months = collections.Counter(r["published"][:7] for r in rows)
src = collections.Counter(s for r in rows for s in r["sources"])
summary = {
    "dump_file": ZIP, "n_mal_published_2026": n,
    "id_prefix_counts": dict(idyear),
    "by_month_published": dict(sorted(months.items())),
    "withdrawn": sum(1 for r in rows if r["withdrawn"]),
    "with_explicit_versions": sum(1 for r in rows if r["n_versions"]),
    "whole_package_range": sum(1 for r in rows if r["whole_package_range"]),
    "sources_any": dict(src),
    "vector_exclusive": dict(lab.most_common()),
    "vector_any": dict(any_),
    "explicit_no_install_script_and_no_install_hit": sum(1 for r in rows if "install_script" in r["vector_negated"] and "install_script" not in r["vector_labels"]),
    "vector_clear_fraction": round(sum(1 for r in rows if r["vector_labels"]) / n, 4) if n else None,
    "vector_single_clear_fraction": round(sum(1 for r in rows if len(r["vector_labels"]) == 1) / n, 4) if n else None,
}
json.dump(summary, open(OUT_SUM, "w"), indent=1)
print(json.dumps(summary, indent=1))
