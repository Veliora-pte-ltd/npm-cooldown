#!/usr/bin/env python3
"""Draw the second hand-validation sample: 30 rule-labelled + 30 'unclear' records (seed 20261008),
excluding withdrawn records and the 30 pilot records. Prints summary + details (trimmed) for hand coding."""
import json, random, re, os
OSV_MAL_DIR = os.environ["OSV_MAL_DIR"]  # unpacked MAL-*.json records from the OSV npm dump
recs = [json.loads(l) for l in open("data/results/mal2026.jsonl")]
pilot = {v["id"] for v in json.load(open("data/results/vector-validation-verdicts.json"))["verdicts"]}
pool = [r for r in recs if not r["withdrawn"] and r["id"] not in pilot]
lab = sorted([r for r in pool if r["vector_labels"]], key=lambda r: r["id"])
unc = sorted([r for r in pool if not r["vector_labels"]], key=lambda r: r["id"])
rng = random.Random(20261008)
sample = [("labelled", r) for r in rng.sample(lab, 30)] + [("unclear", r) for r in rng.sample(unc, 30)]
out = []
for i, (grp, r) in enumerate(sample):
    o = json.load(open(os.path.join(OSV_MAL_DIR, f"{r['id']}.json")))
    txt = re.sub(r"\s+", " ", (o.get("summary", "") + " || " + o.get("details", "")))
    out.append({"i": i, "group": grp, "id": r["id"], "rules": r["vector_labels"], "text": txt[:700]})
json.dump(out, open("data/results/validation-sample-2.json", "w"), indent=1)
for s in out:
    print(f"[{s['i']}] {s['group']} {s['id']} rules={s['rules']}\n  {s['text']}\n")
